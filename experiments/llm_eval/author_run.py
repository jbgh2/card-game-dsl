"""The authoring benchmark: a model writes a game from its rules source, the
checker answers, and the rig records how the loop went.

    python -m experiments.llm_eval.author_run \\
        --config experiments/llm_eval/config_authoring.yaml --rules-dir RULES

Given a game's rules text (a file the operator supplies, with the URL it was
read from) and `docs/authoring.md` with the configured reference files, a
model drafts a `.cardlang` file; `cardlang check` runs on it (`author_check`);
the checker's words go back to the model verbatim; and the loop runs until
the file checks green, the model gives up, or the round limit is reached.
Each attempt is one line of `attempts.jsonl` in the run's own directory,
holding every round raw: the reply, the draft, and what the checker printed.
Everything the report says is derived from those rounds (`followups`,
`author_report`), so a reader can re-derive any figure from the record.

**Held-out games.** A game's set is derived, never labelled: a slug with a
corpus file (`docs/games/<slug>.cardlang`) is CORPUS, its file withheld and
its facts the real-game reference; a slug that is a heading of
`docs/games/_candidates.md` and has no corpus file is CANDIDATE, with no
reference and its real-game question left to a rules read. The model is
never shown a game's corpus file or its rulebook twin: `context_files`
refuses either, for every game in the run, before any model is called.

**A refusal the model could not act on** (`FollowupStatus.STANDS`): an
error the checker printed for one draft, standing again for the model's next
draft under the same `refusal_key`, at the same source line carried through
the edit unchanged (`carried_line`). The other outcomes are recorded and not counted:
gone, persisting elsewhere or on an edited line, masked (the next draft
stopped at a syntax error, which the checker reports before any other
stage), not edited (the model returned the same file), and no next edit.

**Spend.** The config's `token_budget` is checked before every model call
against the spend log, and every call is recorded in the log as soon as it
returns (`spend.py`, `run_eval.budget_of`); a run the ceiling stops records
the attempt it stopped in as stopped, never as a result.

Contract
--------
Assumes: the config names models defined under `models:`, games by slug, and
reference files by repository path; the rules directory holds each game's
rules file.
Establishes: `<run_dir>/run.json` (the provenance, written before the first
call) and `<run_dir>/attempts.jsonl` (one `AttemptRecord` per attempt,
appended as each ends); every attempt's `outcome` is one of
`AttemptOutcome`.
Illegal after: showing a model a held-out game's corpus file or twin;
counting a round's refusals from anywhere but its recorded check; a model
call the budget was not checked before.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import inspect
import json
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Final

import yaml

from . import layout
from .agents import code_closure
from .author_check import (
    CHECK_FORMS,
    Checker,
    CheckResult,
    CheckVerdict,
    Refusal,
    checker_import_root,
    refusal_key,
    repo_root,
)
from .author_facts import (
    Differential,
    DifferentialVerdict,
    FactsRecord,
    FactsRunner,
    FactsStatus,
    ReferenceCache,
    compare,
)
from .author_prompt import (
    GameBrief,
    Reference,
    ReplyKind,
    RoundView,
    build_prompt,
    read_reply,
    task_text,
)
from .providers import PRICES, Provider
from .run_eval import Budget, budget_of, ensure_provider, smoke, spend_log
from .spend import SpendLog, billed_since, snapshot, spent

GAMES_DIR: Final = Path("docs/games")
CANDIDATES_FILE: Final = GAMES_DIR / "_candidates.md"
_CANDIDATE_HEADING = re.compile(r"^### ([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE)


class HeldOutSet(Enum):
    """Which held-out set a game belongs to, derived from the tree."""

    #: A corpus game, its `.cardlang` withheld: the differential applies.
    CORPUS = "corpus_withheld"
    #: A candidate from `_candidates.md` with no corpus file: a rules read.
    CANDIDATE = "candidate"


def held_out_set(slug: str, root: Path) -> HeldOutSet:
    """The set `slug` belongs to, or a refusal naming why it is neither."""
    if (root / GAMES_DIR / f"{slug}.cardlang").is_file():
        return HeldOutSet.CORPUS
    candidates = set(_CANDIDATE_HEADING.findall((root / CANDIDATES_FILE).read_text(encoding="utf-8")))
    if slug in candidates:
        return HeldOutSet.CANDIDATE
    raise ValueError(
        f"game {slug!r} is neither a corpus game ({GAMES_DIR}/{slug}.cardlang) "
        f"nor a heading of {CANDIDATES_FILE}"
    )


def withheld_paths(slug: str) -> tuple[Path, ...]:
    """The repository files a model writing `slug` is never shown: its
    corpus file and its rulebook twin, which is written against it."""
    return (GAMES_DIR / f"{slug}.cardlang", GAMES_DIR / f"{slug}.md")


def context_files(
    references: Sequence[str], slugs: Sequence[str], root: Path
) -> tuple[Reference, ...]:
    """The reference documents, read, after refusing any that is a withheld
    file of a game in the run."""
    withheld = {p for slug in slugs for p in withheld_paths(slug)}
    out: list[Reference] = []
    for name in references:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"reference {name!r} must be a path inside the repository")
        if path in withheld:
            raise ValueError(
                f"reference {name!r} is a withheld file of a game in this run; a "
                f"model writing that game is never shown it"
            )
        out.append(Reference(label=path.as_posix(), text=(root / path).read_text(encoding="utf-8")))
    return tuple(out)


@dataclass(frozen=True)
class GameSpec:
    """One game of the run, as the config names it and the tree places it."""

    slug: str
    name: str
    variant: str
    source_url: str
    rules_file: Path
    held_out: HeldOutSet

    def brief(self) -> GameBrief:
        return GameBrief(
            name=self.name,
            variant=self.variant,
            source_url=self.source_url,
            rules_text=self.rules_file.read_text(encoding="utf-8"),
        )


def game_specs(config: Mapping[str, Any], rules_dir: Path, root: Path) -> tuple[GameSpec, ...]:
    """The config's games, each placed and its rules file found."""
    games_root = (root / GAMES_DIR).resolve()
    resolved = rules_dir.resolve()
    if resolved == games_root or games_root in resolved.parents:
        raise ValueError(
            f"rules directory {rules_dir} is inside {GAMES_DIR}/, whose files are "
            f"written against the withheld corpus files"
        )
    specs = []
    for entry in config["games"]:
        unknown = sorted(set(entry) - {"slug", "name", "variant", "source_url", "rules_file"})
        if unknown:
            raise ValueError(f"game entry {entry.get('slug')!r} names {unknown}, which nothing reads")
        rules_file = rules_dir / entry["rules_file"]
        if not rules_file.is_file():
            raise ValueError(
                f"no rules file for {entry['slug']!r} at {rules_file}: save the text "
                f"of {entry['source_url']} there"
            )
        specs.append(
            GameSpec(
                slug=entry["slug"],
                name=entry["name"],
                variant=entry["variant"],
                source_url=entry["source_url"],
                rules_file=rules_file,
                held_out=held_out_set(entry["slug"], root),
            )
        )
    return tuple(specs)


# --- outcomes --------------------------------------------------------------


class AttemptOutcome(Enum):
    """How one attempt ended."""

    GREEN = "green"
    ROUND_LIMIT = "round_limit"
    GAVE_UP = "gave_up"
    #: The checker crashed, hung, or printed nothing readable at exit 1.
    CHECKER_FAILED = "checker_failed"
    #: The provider raised; the attempt has no result.
    PROVIDER_ERROR = "provider_error"
    #: The spend ceiling stopped the attempt before it ended.
    STOPPED_BY_CEILING = "stopped_by_ceiling"
    #: The checker could not be invoked (exit 2): the rig's fault.
    HARNESS_ERROR = "harness_error"


class RealGameVerdict(Enum):
    """Whether the green file is the real game, as far as the rig can say."""

    #: A corpus game whose facts agree with the corpus file's. Not proof:
    #: `author_facts` says what passes unseen.
    AGREES_ON_FACTS = "agrees_on_facts_compared"
    #: A corpus game whose facts differ: the run FAILED, pending a rules
    #: read that may find an encoding difference instead.
    DIVERGES = "diverges"
    #: The green file does not play: its rules refuse, it crashes, it hangs.
    DOES_NOT_PLAY = "does_not_play"
    #: A candidate that plays: whether it is the game is a rules read.
    RULES_READ_PENDING = "rules_read_pending"
    #: The reference yielded no facts: a rig problem, nothing compared.
    NOT_COMPARABLE = "not_comparable"
    #: The attempt reached no green file.
    NOT_REACHED = "not_reached"


class FollowupStatus(Enum):
    """What became of one refusal at the model's next draft."""

    #: Same refusal key, at the line the earlier refusal stood at, carried
    #: into the next draft unedited (`carried_line`). The one status counted
    #: as a refusal the model could not act on.
    STANDS = "stands"
    #: Same refusal key in the next draft, at another line or an edited one.
    PERSISTS = "persists"
    GONE = "gone"
    #: The next draft stopped at a syntax error and this refusal is not
    #: one: the check that would have reported it did not run.
    MASKED = "masked"
    #: The next draft is byte-identical: a non-edit, not a diagnostic
    #: failure.
    NOT_EDITED = "not_edited"
    #: No later draft was checked.
    NO_NEXT_EDIT = "no_next_edit"


def _syntax(refusal: Refusal) -> bool:
    """Whether a refusal is the parse stage's: the one stage order the text
    form shows, since a syntax error is reported before anything else runs.
    Issue #1046's codes replace this reading."""
    return refusal.message.startswith("syntax error")


def anchor(refusal: Refusal, draft: str) -> str | None:
    """The text of the source line a refusal stands at, stripped, for a
    reader of the report."""
    if refusal.line is None:
        return None
    lines = draft.splitlines()
    if not 1 <= refusal.line <= len(lines):
        return None
    return lines[refusal.line - 1].strip()


@dataclass(frozen=True)
class Followup:
    round: int
    next_round: int | None
    refusal: Refusal
    key: str
    anchor: str | None
    status: FollowupStatus


def followups(rounds: Sequence[Mapping[str, Any]]) -> list[Followup]:
    """Every error refusal of every checked draft, with what became of it at
    the next checked draft. Derived from the recorded rounds alone."""
    checked = [
        (r["round"], r["draft"], CheckResult.from_dict(r["check"]))
        for r in rounds
        if r.get("draft") is not None and r.get("check") is not None
    ]
    out: list[Followup] = []
    for index, (number, draft, check) in enumerate(checked):
        if check.verdict is not CheckVerdict.REFUSED:
            continue
        later = checked[index + 1] if index + 1 < len(checked) else None
        for refusal in check.refusals:
            if refusal.severity != "error":
                continue
            key = refusal_key(refusal)
            here = anchor(refusal, draft)
            if later is None:
                status = FollowupStatus.NO_NEXT_EDIT
                next_round = None
            else:
                next_round, next_draft, next_check = later
                status = _status(refusal, key, draft, next_draft, next_check)
            out.append(Followup(number, next_round, refusal, key, here, status))
    return out


def carried_line(line: int, draft: str, next_draft: str) -> int | None:
    """Where line `line` of `draft` stands in `next_draft`, when the edit
    left it untouched: its image inside a block the two drafts share, by
    `difflib`'s alignment of their lines, or None for a line the edit
    changed or removed. An alignment rather than a text match, because a
    line like `}` recurs throughout a file and its text alone does not say
    which one a refusal stood at."""
    before, after = draft.splitlines(), next_draft.splitlines()
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
        if tag == "equal" and i1 <= line - 1 < i2:
            return j1 + (line - 1 - i1) + 1
    return None


def _status(
    refusal: Refusal,
    key: str,
    draft: str,
    next_draft: str,
    next_check: CheckResult,
) -> FollowupStatus:
    if next_draft == draft:
        return FollowupStatus.NOT_EDITED
    same = [r for r in next_check.refusals if r.severity == "error" and refusal_key(r) == key]
    image = None if refusal.line is None else carried_line(refusal.line, draft, next_draft)
    if image is not None and any(r.line == image for r in same):
        return FollowupStatus.STANDS
    if same:
        return FollowupStatus.PERSISTS
    errors = [r for r in next_check.refusals if r.severity == "error"]
    if errors and all(_syntax(r) for r in errors) and not _syntax(refusal):
        return FollowupStatus.MASKED
    return FollowupStatus.GONE


# --- the loop --------------------------------------------------------------


@dataclass
class AttemptRecord:
    game: str
    held_out: str
    model_ref: str
    model: str
    attempt: int
    round_limit: int
    outcome: AttemptOutcome = AttemptOutcome.ROUND_LIMIT
    detail: str = ""
    rounds: list[dict[str, Any]] = field(default_factory=list)
    real_game: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def drafts(self) -> list[dict[str, Any]]:
        return [r for r in self.rounds if r.get("draft") is not None]

    def summary(self) -> dict[str, Any]:
        drafts = self.drafts
        first = drafts[0]["check"]["verdict"] if drafts else None
        green_at = next(
            (i for i, r in enumerate(drafts) if r["check"]["verdict"] == CheckVerdict.GREEN.value),
            None,
        )
        stands = [f for f in followups(self.rounds) if f.status is FollowupStatus.STANDS]
        return {
            "rounds": len(self.rounds),
            "drafts": len(drafts),
            "first_draft_green": first == CheckVerdict.GREEN.value,
            "fix_rounds_to_green": green_at,
            "could_not_act_on": len(stands),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "held_out": self.held_out,
            "model_ref": self.model_ref,
            "model": self.model,
            "attempt": self.attempt,
            "round_limit": self.round_limit,
            "outcome": self.outcome.value,
            "detail": self.detail,
            "summary": self.summary(),
            "real_game": self.real_game,
            "usage": self.usage,
            "rounds": self.rounds,
        }


@dataclass
class Bench:
    """Everything one invocation shares across its attempts."""

    config: Mapping[str, Any]
    task: str
    references: tuple[Reference, ...]
    checker: Checker
    facts: ReferenceCache
    registry: dict[str, Provider]
    log: SpendLog
    budget: Budget
    run_name: str
    round_limit: int
    root: Path


def run_attempt(bench: Bench, game: GameSpec, model_ref: str, attempt: int) -> AttemptRecord:
    """One attempt: drafts until green, a give-up, the limit or a stop."""
    provider = ensure_provider(dict(bench.config), model_ref, bench.registry)
    providers = {model_ref: provider}
    record = AttemptRecord(
        game=game.slug,
        held_out=game.held_out.value,
        model_ref=model_ref,
        model=provider.model,
        attempt=attempt,
        round_limit=bench.round_limit,
    )
    brief = game.brief()
    history: list[RoundView] = []
    before = snapshot(providers)
    logged = before
    green_draft: str | None = None
    with tempfile.TemporaryDirectory(prefix="authoring-") as scratch:
        workdir = Path(scratch)
        for number in range(1, bench.round_limit + 1):
            crossed = bench.budget.exceeded(bench.log, spent(billed_since(providers, logged)))
            if crossed is not None:
                record.outcome = AttemptOutcome.STOPPED_BY_CEILING
                record.detail = f"{crossed} reached over the {bench.budget.counts.spelling()} window"
                break
            prompt = build_prompt(bench.task, bench.references, brief, history)
            try:
                reply = provider.complete(prompt)
            except Exception as exc:  # noqa: BLE001 -- any provider failure ends the attempt, recorded
                record.outcome = AttemptOutcome.PROVIDER_ERROR
                record.detail = f"{type(exc).__name__}: {exc}"
                break
            finally:
                bench.log.record(
                    bench.run_name,
                    f"{game.slug}/{model_ref}/{attempt}",
                    billed_since(providers, logged),
                )
                logged = snapshot(providers)
            read = read_reply(reply.text, reply.stop_reason)
            row: dict[str, Any] = {
                "round": number,
                "prompt_sha256": hashlib.sha256(prompt.text.encode("utf-8")).hexdigest(),
                "prompt_blocks": len(prompt.blocks),
                "reply": reply.text,
                "stop_reason": reply.stop_reason,
                "reply_kind": read.kind.value,
                "reason": read.reason,
                "draft": read.draft,
                "check": None,
                "usage": {
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "cache_read_input_tokens": reply.cache_read_input_tokens,
                    "cache_creation_input_tokens": reply.cache_creation_input_tokens,
                },
            }
            record.rounds.append(row)
            if read.kind is ReplyKind.GAVE_UP:
                record.outcome = AttemptOutcome.GAVE_UP
                record.detail = read.reason
                break
            if read.draft is None:
                history.append(RoundView(number, None, read.reason))
                continue
            check = bench.checker.check(read.draft, workdir)
            row["check"] = check.as_dict()
            if check.verdict is CheckVerdict.GREEN:
                record.outcome = AttemptOutcome.GREEN
                green_draft = read.draft
                break
            if check.verdict is CheckVerdict.CANNOT_PROCEED:
                record.outcome = AttemptOutcome.HARNESS_ERROR
                record.detail = check.said
                break
            if check.verdict is not CheckVerdict.REFUSED:
                record.outcome = AttemptOutcome.CHECKER_FAILED
                record.detail = f"{check.verdict.value}: {check.said[-2000:]}"
                break
            history.append(RoundView(number, read.draft, check.said, check.exit_code))
        else:
            record.outcome = AttemptOutcome.ROUND_LIMIT
        record.real_game = real_game(bench, game, green_draft, workdir)
    delta = billed_since(providers, before)
    record.usage = {
        "calls": sum(b.calls for b in delta),
        "input_tokens": sum(b.spend.input_tokens for b in delta),
        "output_tokens": sum(b.spend.output_tokens for b in delta),
        "cache_read_input_tokens": sum(b.spend.cache_read_input_tokens for b in delta),
        "cache_creation_input_tokens": sum(b.spend.cache_creation_input_tokens for b in delta),
        "cost_usd": round(sum(b.spend.cost_usd for b in delta), 6),
    }
    return record


def real_game(bench: Bench, game: GameSpec, green: str | None, workdir: Path) -> dict[str, Any]:
    """The real-game check of an attempt's green file."""
    if green is None:
        return {"verdict": RealGameVerdict.NOT_REACHED.value}
    draft_path = workdir / "green.cardlang"
    draft_path.write_text(green, encoding="utf-8")
    candidate = bench.facts.runner.run(draft_path)
    if game.held_out is HeldOutSet.CANDIDATE:
        verdict = (
            RealGameVerdict.RULES_READ_PENDING
            if candidate.status is FactsStatus.OK
            else RealGameVerdict.DOES_NOT_PLAY
        )
        return {"verdict": verdict.value, "candidate_facts": candidate.as_dict()}
    reference = bench.facts.facts(bench.root / GAMES_DIR / f"{game.slug}.cardlang")
    differential = compare(reference, candidate)
    return {
        "verdict": _real_game_verdict(differential).value,
        "differential": differential.as_dict(),
        "candidate_facts": candidate.as_dict(),
    }


def _real_game_verdict(differential: Differential) -> RealGameVerdict:
    return {
        DifferentialVerdict.AGREES: RealGameVerdict.AGREES_ON_FACTS,
        DifferentialVerdict.DIVERGES: RealGameVerdict.DIVERGES,
        DifferentialVerdict.DOES_NOT_PLAY: RealGameVerdict.DOES_NOT_PLAY,
        DifferentialVerdict.NOT_COMPARABLE: RealGameVerdict.NOT_COMPARABLE,
    }[differential.verdict]


# --- provenance ------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=60, check=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def builder_digest() -> str:
    """The digest of the rig code a model's input and the reading of its
    output pass through: the prompt builder's and the reply reader's code
    closures, one line per function or class."""
    objects = {
        f"{obj.__module__}.{obj.__qualname__}": obj
        for root_fn in (build_prompt, read_reply, task_text)
        for obj in code_closure(root_fn)
    }
    return _sha256(
        "\n".join(f"{name} {_sha256(inspect.getsource(obj))}" for name, obj in sorted(objects.items()))
    )


def provenance(
    config: Mapping[str, Any],
    config_path: Path,
    games: Sequence[GameSpec],
    references: Sequence[Reference],
    task: str,
    checker: Checker,
    facts: FactsRunner,
    models: Sequence[str],
    root: Path,
    checker_root: Path,
) -> dict[str, Any]:
    return {
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config_path": str(config_path),
        "config": config,
        "git_head": _git(repo_root(), "rev-parse", "HEAD"),
        "git_dirty": _git(repo_root(), "status", "--porcelain").splitlines(),
        "tree": str(root),
        "python": platform.python_version(),
        "checker": {
            "argv": checker.command(),
            "form": checker.form,
            "imports_cardlang_from": str(checker_root),
            "timeout_seconds": checker.timeout_seconds,
        },
        "facts": {
            "playouts": facts.playouts,
            "seed_start": facts.seed_start,
            "timeout_seconds": facts.timeout_seconds,
        },
        "task_sha256": _sha256(task),
        "builder_sha256": builder_digest(),
        "references": [{"label": r.label, "sha256": _sha256(r.text)} for r in references],
        "games": [
            {
                "slug": g.slug,
                "held_out": g.held_out.value,
                "name": g.name,
                "variant": g.variant,
                "source_url": g.source_url,
                "rules_file": str(g.rules_file),
                "rules_sha256": _sha256(g.rules_file.read_text(encoding="utf-8")),
                "withheld": [p.as_posix() for p in withheld_paths(g.slug)]
                if g.held_out is HeldOutSet.CORPUS
                else [],
            }
            for g in games
        ],
        "models": {m: config["models"][m] for m in models},
    }


# --- the command -----------------------------------------------------------


def preflight_models(config: Mapping[str, Any], models: Sequence[str]) -> None:
    """Every model named is defined, and every real one priced."""
    for name in models:
        if name not in config.get("models", {}):
            raise ValueError(f"model {name!r} is not defined under `models:` in the config")
        spec = config["models"][name]
        if spec.get("kind", "anthropic") == "anthropic" and spec["model"] not in PRICES:
            raise ValueError(
                f"model {name!r} names {spec['model']!r}, which has no published "
                f"price; its cost would report as $0.00"
            )


def checker_of(config: Mapping[str, Any], root: Path) -> Checker:
    block = dict(config.get("checker", {}))
    form = block.get("form", "text")
    if form not in CHECK_FORMS:
        raise ValueError(f"checker.form {form!r} is not one of {', '.join(CHECK_FORMS)}")
    if form == "json":
        raise ValueError("checker.form json waits on `cardlang check --json` (issue #1046)")
    return Checker(root=root, form=form, timeout_seconds=float(block.get("timeout_seconds", 120)))


def facts_of(config: Mapping[str, Any], root: Path) -> FactsRunner:
    block = dict(config.get("facts", {}))
    return FactsRunner(
        repo_root=root,
        playouts=int(block.get("playouts", 100)),
        seed_start=int(block.get("seed_start", 0)),
        timeout_seconds=float(block.get("timeout_seconds", 900)),
    )


def run(
    config: Mapping[str, Any],
    config_path: Path,
    rules_dir: Path,
    *,
    games_filter: Sequence[str] | None = None,
    models_filter: Sequence[str] | None = None,
    registry: dict[str, Provider] | None = None,
    checker: Checker | None = None,
    facts: FactsRunner | None = None,
    tree: Path | None = None,
    dry_run: bool = False,
    out: Any = sys.stdout,
) -> Path | None:
    """Run the benchmark the config describes. Returns the run directory, or
    None for a dry run. Everything that can be refused is refused before the
    first model call.

    `tree` is where the games, the candidates and the references are read
    from, this checkout unless a caller names another; the checker and the
    facts always run against this checkout's engine."""
    root = tree or repo_root()
    specs = game_specs(config, rules_dir, root)
    if games_filter:
        unknown = sorted(set(games_filter) - {s.slug for s in specs})
        if unknown:
            raise ValueError(f"--game {unknown} is not a game of the config")
        specs = tuple(s for s in specs if s.slug in games_filter)
    models = list(config["roster"])
    if models_filter:
        unknown = sorted(set(models_filter) - set(models))
        if unknown:
            raise ValueError(f"--model {unknown} is not in the config's roster")
        models = [m for m in models if m in models_filter]
    preflight_models(config, models)
    round_limit = int(config["round_limit"])
    attempts = int(config.get("attempts", 1))
    task = task_text(round_limit)
    references = context_files(
        list(config["references"]), [s.slug for s in specs], root
    )
    checker = checker or checker_of(config, repo_root())
    facts = facts or facts_of(config, repo_root())
    budget = budget_of(dict(config))
    results_dir = Path(config.get("results_dir", "experiments/llm_eval/results_authoring"))
    log = spend_log(dict(config), results_dir)
    log.total(budget.counts)
    checker_root = checker_import_root(checker.python, checker.root)
    if checker_root != checker.root.resolve():
        raise ValueError(
            f"the checker imports cardlang from {checker_root}, not from the "
            f"checkout it was pointed at ({checker.root.resolve()}); the "
            f"benchmark would measure another tree"
        )
    cache = ReferenceCache(facts)
    for spec in specs:
        if spec.held_out is HeldOutSet.CORPUS:
            reference = cache.facts(root / GAMES_DIR / f"{spec.slug}.cardlang")
            if reference.status is not FactsStatus.OK:
                raise ValueError(
                    f"the corpus file for {spec.slug!r} yields no facts "
                    f"({reference.status.value}: {reference.detail[:500]}); nothing "
                    f"could be compared against it"
                )
    print(
        f"{len(specs)} game(s) x {len(models)} model(s) x {attempts} attempt(s), "
        f"round limit {round_limit}; spend log {log.path} (window {budget.window})",
        file=out,
    )
    if dry_run:
        print("dry run: every check passed; no model was called", file=out)
        return None
    results_dir.mkdir(parents=True, exist_ok=True)
    run_dir = layout.new_run_dir(results_dir)
    record_path = run_dir / "run.json"
    payload = provenance(
        config, config_path, specs, references, task, checker, facts, models, root, checker_root
    )
    payload["reference_facts"] = {str(p.relative_to(root)): r.as_dict() for p, r in cache.taken.items()}
    record_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    bench = Bench(
        config=config,
        task=task,
        references=references,
        checker=checker,
        facts=cache,
        registry=registry if registry is not None else {},
        log=log,
        budget=budget,
        run_name=run_dir.name,
        round_limit=round_limit,
        root=root,
    )
    stopped: str | None = None
    with (run_dir / "attempts.jsonl").open("w", encoding="utf-8") as handle:
        for spec in specs:
            for model_ref in models:
                for attempt in range(attempts):
                    record = run_attempt(bench, spec, model_ref, attempt)
                    handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
                    handle.flush()
                    print(
                        f"[{spec.slug} {model_ref} #{attempt}] {record.outcome.value} "
                        f"{record.summary()} real game: {record.real_game.get('verdict')}",
                        file=out,
                    )
                    if record.outcome in (
                        AttemptOutcome.STOPPED_BY_CEILING,
                        AttemptOutcome.PROVIDER_ERROR,
                        AttemptOutcome.HARNESS_ERROR,
                    ):
                        stopped = f"{record.outcome.value}: {record.detail}"
                        break
                if stopped:
                    break
            if stopped:
                break
    payload["stopped"] = stopped
    record_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if stopped:
        print(f"RUN STOPPED: {stopped}", file=out)
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument("--config", default="experiments/llm_eval/config_authoring.yaml")
    parser.add_argument(
        "--rules-dir",
        required=True,
        help="the directory holding each game's rules file, as the config names it",
    )
    parser.add_argument("--game", action="append", help="run only this game (repeatable)")
    parser.add_argument("--model", action="append", help="run only this model (repeatable)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run every check that needs no model call, then exit",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="make ONE real call per roster model to verify the request shape, then exit",
    )
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if args.smoke:
        roster = [m for m in config["roster"] if not args.model or m in args.model]
        results_dir = Path(config.get("results_dir", "experiments/llm_eval/results_authoring"))
        return smoke(
            config,
            [{"name": "smoke", "agents": [{"model": m} for m in roster]}],
            spend_log(config, results_dir),
        )
    try:
        run_dir = run(
            config,
            config_path,
            Path(args.rules_dir),
            games_filter=args.game,
            models_filter=args.model,
            dry_run=args.dry_run,
        )
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 2
    if run_dir is not None:
        print(f"wrote {run_dir}; report: python -m experiments.llm_eval.author_report {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
