"""The authoring benchmark's loop, driven by a scripted fake provider.

No test here calls a model. `FakeProvider` serves each reply in turn, the
real checker answers every draft (a stand-in command where the case is a
checker crash), and the real-game check plays the green file against the
corpus file of a miniature tree, HighCard, whose withheld file stands where
`docs/games/<slug>.cardlang` would.
"""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from ..author_check import DRAFT_NAME, Checker, CheckResult, CheckVerdict, Refusal, repo_root
from ..author_facts import FactsRunner
from ..author_prompt import (
    GameBrief,
    Reference,
    RoundView,
    build_prompt,
    task_text,
)
from ..author_report import report
from ..author_run import (
    AttemptOutcome,
    FollowupStatus,
    HeldOutSet,
    RealGameVerdict,
    context_files,
    followups,
    game_specs,
    held_out_set,
    run,
    withheld_paths,
)
from ..prompts import Prompt
from ..run_eval import budget_of
from ..providers import FakeProvider, Provider, Reply, Usage
from ..spend import Billed, Spend, SpendLog
from .test_author_check import HIGH_CARD, TWO_TYPOS
from .test_author_facts import REDUCED

ROOT = repo_root()
SHIPPED_CONFIG = ROOT / "experiments" / "llm_eval" / "config_authoring.yaml"
ONE_TYPO = HIGH_CARD.replace("score[0] += 1", "scroe[0] += 1")


def block(text: str) -> str:
    return f"Here is the file.\n\n```cardlang\n{text}```\n"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A miniature repository: one corpus game, one candidate, a guide."""
    root = tmp_path / "tree"
    games = root / "docs" / "games"
    games.mkdir(parents=True)
    (games / "highcard.cardlang").write_text(HIGH_CARD, encoding="utf-8")
    (games / "highcard.md").write_text("# High Card\n\nThe twin.\n", encoding="utf-8")
    (games / "_candidates.md").write_text("# Candidates\n\n### lowcard\n\nA game.\n", encoding="utf-8")
    (root / "docs" / "authoring.md").write_text("# Writing a game\n\nA guide.\n", encoding="utf-8")
    return root


@pytest.fixture
def rules(tmp_path: Path) -> Path:
    folder = tmp_path / "rules"
    folder.mkdir()
    (folder / "highcard.txt").write_text("Each player is dealt two cards and shows one.\n")
    (folder / "lowcard.txt").write_text("Each player is dealt two cards and the lowest shown wins.\n")
    return folder


def config(tmp_path: Path, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "results_dir": str(tmp_path / "results"),
        "round_limit": 4,
        "attempts": 1,
        "references": ["docs/authoring.md"],
        "facts": {"playouts": 20},
        "games": [
            {
                "slug": "highcard",
                "name": "High Card",
                "variant": "2 players",
                "source_url": "https://example.invalid/highcard",
                "rules_file": "highcard.txt",
            }
        ],
        "token_budget": {},
        "roster": ["fake"],
        "models": {"fake": {"kind": "fake"}},
    }
    base.update(over)
    return base


def bench(
    tmp_path: Path,
    tree: Path,
    rules: Path,
    replies: Sequence[str],
    *,
    provider: Provider | None = None,
    checker: Checker | None = None,
    **over: Any,
) -> tuple[Path | None, Provider, list[dict[str, Any]]]:
    """Run the config against the tree with one scripted provider; return
    the run directory, the provider and the attempt records."""
    used = provider or FakeProvider(replies=list(replies))
    cfg = config(tmp_path, **over)
    run_dir = run(
        cfg,
        tmp_path / "config.yaml",
        rules,
        registry={"fake": used},
        checker=checker,
        facts=FactsRunner(repo_root=ROOT, playouts=int(cfg["facts"]["playouts"])),
        tree=tree,
        out=io.StringIO(),
    )
    attempts = []
    if run_dir is not None:
        lines = (run_dir / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
        attempts = [json.loads(line) for line in lines if line.strip()]
    return run_dir, used, attempts


# --- the outcomes ------------------------------------------------------------


def test_a_first_draft_that_checks_green(tmp_path: Path, tree: Path, rules: Path) -> None:
    _, provider, [attempt] = bench(tmp_path, tree, rules, [block(HIGH_CARD)])
    assert attempt["outcome"] == AttemptOutcome.GREEN.value
    assert attempt["summary"]["first_draft_green"] is True
    assert attempt["summary"]["fix_rounds_to_green"] == 0
    assert attempt["real_game"]["verdict"] == RealGameVerdict.AGREES_ON_FACTS.value
    assert provider.usage.calls == 1


def test_green_after_two_fix_rounds(tmp_path: Path, tree: Path, rules: Path) -> None:
    replies = [block(TWO_TYPOS), block(ONE_TYPO), block(HIGH_CARD)]
    _, _, [attempt] = bench(tmp_path, tree, rules, replies)
    assert attempt["outcome"] == AttemptOutcome.GREEN.value
    assert attempt["summary"]["first_draft_green"] is False
    assert attempt["summary"]["fix_rounds_to_green"] == 2
    # `scroe` stood at an unchanged line from draft 1 to draft 2.
    assert attempt["summary"]["could_not_act_on"] == 1


def test_the_round_limit_ends_an_attempt(tmp_path: Path, tree: Path, rules: Path) -> None:
    replies = [block(TWO_TYPOS), block("// again\n" + TWO_TYPOS), block("// and again\n" + TWO_TYPOS)]
    _, provider, [attempt] = bench(tmp_path, tree, rules, replies, round_limit=3)
    assert attempt["outcome"] == AttemptOutcome.ROUND_LIMIT.value
    assert len(attempt["rounds"]) == 3
    assert provider.usage.calls == 3
    assert attempt["real_game"]["verdict"] == RealGameVerdict.NOT_REACHED.value


def test_a_give_up_names_the_rule(tmp_path: Path, tree: Path, rules: Path) -> None:
    replies = ["I would rather explain.", "CANNOT EXPRESS: a card that changes suit"]
    _, provider, [attempt] = bench(tmp_path, tree, rules, replies)
    assert attempt["outcome"] == AttemptOutcome.GAVE_UP.value
    assert attempt["detail"] == "a card that changes suit"
    assert [r["reply_kind"] for r in attempt["rounds"]] == ["no_draft", "gave_up"]
    assert isinstance(provider, FakeProvider)
    assert "It held no file" in provider.prompts[1]


@dataclass
class TruncatingProvider:
    """Every reply cut off at the output limit."""

    model: str = "fake"
    usage: Usage = field(default_factory=Usage)
    params: dict[str, Any] = field(default_factory=dict)

    def complete(self, prompt: Prompt) -> Reply:
        reply = Reply(text="```cardlang\ngame X {", input_tokens=10, output_tokens=16000, stop_reason="max_tokens")
        self.usage.add(reply)
        return reply


def test_a_truncated_reply_is_never_checked(tmp_path: Path, tree: Path, rules: Path) -> None:
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=TruncatingProvider(), round_limit=2)
    assert attempt["outcome"] == AttemptOutcome.ROUND_LIMIT.value
    assert [r["reply_kind"] for r in attempt["rounds"]] == ["truncated", "truncated"]
    assert all(r["check"] is None for r in attempt["rounds"])


def test_a_checker_crash_is_its_own_outcome(tmp_path: Path, tree: Path, rules: Path) -> None:
    crashing = Checker(argv=("{python}", "-c", "raise RuntimeError('the checker fell over')"))
    run_dir, _, [attempt] = bench(tmp_path, tree, rules, [block(HIGH_CARD)], checker=crashing)
    assert attempt["outcome"] == AttemptOutcome.CHECKER_FAILED.value
    assert attempt["rounds"][0]["check"]["verdict"] == "crashed"
    assert attempt["summary"]["could_not_act_on"] == 0
    assert followups(attempt["rounds"]) == []
    assert run_dir is not None
    printed = io.StringIO()
    report(run_dir, printed)
    assert "Checker failures (each draft is a witness)" in printed.getvalue()


def test_a_green_but_reduced_game_fails_the_real_game_check(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    run_dir, _, [attempt] = bench(tmp_path, tree, rules, [block(REDUCED)])
    assert attempt["outcome"] == AttemptOutcome.GREEN.value
    assert attempt["real_game"]["verdict"] == RealGameVerdict.DIVERGES.value
    assert run_dir is not None
    printed = io.StringIO()
    report(run_dir, printed)
    assert "FAIL: diverges" in printed.getvalue()


def test_a_candidate_is_left_to_a_rules_read(tmp_path: Path, tree: Path, rules: Path) -> None:
    games = [
        {
            "slug": "lowcard",
            "name": "Low Card",
            "variant": "2 players",
            "source_url": "https://example.invalid/lowcard",
            "rules_file": "lowcard.txt",
        }
    ]
    lowest = HIGH_CARD.replace("HighCard", "LowCard").replace("highest score", "lowest score")
    _, _, [attempt] = bench(tmp_path, tree, rules, [block(lowest)], games=games)
    assert attempt["held_out"] == HeldOutSet.CANDIDATE.value
    assert attempt["real_game"]["verdict"] == RealGameVerdict.RULES_READ_PENDING.value


# --- a refusal the model could not act on ------------------------------------


def _fates(replies: Sequence[str], tmp_path: Path, tree: Path, rules: Path) -> dict[str, FollowupStatus]:
    _, _, [attempt] = bench(tmp_path, tree, rules, [block(r) for r in replies])
    return {f.refusal.message: f.status for f in followups(attempt["rounds"]) if f.round == 1}


def test_a_refusal_at_an_unchanged_line_stands_though_the_line_moved(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    second = "// a line above everything\n" + ONE_TYPO
    fates = _fates([TWO_TYPOS, second, HIGH_CARD], tmp_path, tree, rules)
    assert fates == {
        "unresolved name 'hnad'": FollowupStatus.GONE,
        "unresolved name 'scroe'": FollowupStatus.STANDS,
    }


def test_a_refusal_on_an_edited_line_persists_and_is_not_counted(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    second = ONE_TYPO.replace("scroe[0] += 1", "scroe[0] += 1 + 0")
    fates = _fates([TWO_TYPOS, second, HIGH_CARD], tmp_path, tree, rules)
    assert fates["unresolved name 'scroe'"] is FollowupStatus.PERSISTS


def test_a_refusal_behind_a_new_syntax_error_is_masked(tmp_path: Path, tree: Path, rules: Path) -> None:
    second = ONE_TYPO.replace("zones {", "zones {{")
    fates = _fates([TWO_TYPOS, second, HIGH_CARD], tmp_path, tree, rules)
    assert fates["unresolved name 'scroe'"] is FollowupStatus.MASKED


def test_an_unchanged_file_is_a_non_edit(tmp_path: Path, tree: Path, rules: Path) -> None:
    fates = _fates([TWO_TYPOS, TWO_TYPOS, HIGH_CARD], tmp_path, tree, rules)
    assert set(fates.values()) == {FollowupStatus.NOT_EDITED}


REPEATED_BRACES = "game A {\n  x {\n    a\n  }\n  y {\n    b\n  }\n}\n"


def _round(number: int, draft: str, line: int) -> dict[str, Any]:
    refusal = Refusal(DRAFT_NAME, line, 3, "error", "a refusal at a closing brace")
    check = CheckResult(CheckVerdict.REFUSED, 1, "", "", (refusal,))
    return {"round": number, "draft": draft, "check": check.as_dict()}


@pytest.mark.parametrize(
    ("next_line", "status"),
    [(4, FollowupStatus.STANDS), (7, FollowupStatus.PERSISTS)],
    ids=["the same brace", "another brace with the same text"],
)
def test_a_refusal_stands_only_at_the_line_it_stood_at(next_line: int, status: FollowupStatus) -> None:
    edited = REPEATED_BRACES.replace("    b\n", "    b2\n")
    rounds = [_round(1, REPEATED_BRACES, 4), _round(2, edited, next_line)]
    [fate] = [f for f in followups(rounds) if f.round == 1]
    assert fate.status is status


def test_the_report_lists_each_refusal_ready_to_file(tmp_path: Path, tree: Path, rules: Path) -> None:
    replies = [block(TWO_TYPOS), block("// above\n" + ONE_TYPO), block(HIGH_CARD)]
    run_dir, _, _ = bench(tmp_path, tree, rules, replies)
    assert run_dir is not None
    printed = io.StringIO()
    report(run_dir, printed)
    text = printed.getvalue()
    assert "Refusals a model could not act on: 1 occurrence(s) under 1 key(s)" in text
    assert "Title: a model writing highcard is told `unresolved name 'scroe'`" in text
    assert "if a > b { scroe[0] += 1 }" in text


# --- the spend ceiling --------------------------------------------------------


def test_the_ceiling_stops_a_run_between_calls(tmp_path: Path, tree: Path, rules: Path) -> None:
    replies = [block(TWO_TYPOS)]
    run_dir, provider, attempts = bench(
        tmp_path, tree, rules, replies, attempts=2, token_budget={"max_input_tokens": 50}
    )
    assert run_dir is not None
    assert [a["outcome"] for a in attempts] == [AttemptOutcome.STOPPED_BY_CEILING.value]
    assert provider.usage.calls == 1
    assert json.loads((run_dir / "run.json").read_text())["stopped"].startswith("stopped_by_ceiling")
    log = SpendLog(tmp_path / "results" / "spend" / "log.jsonl")
    assert sum(e["calls"] for e in log.entries()) == 1


def test_a_ceiling_already_crossed_calls_nothing(tmp_path: Path, tree: Path, rules: Path) -> None:
    earlier = SpendLog(tmp_path / "results" / "spend" / "log.jsonl")
    earlier.record("earlier", "x", [Billed("m", "fake", 1, Spend(input_tokens=1000))])
    _, provider, [attempt] = bench(
        tmp_path,
        tree,
        rules,
        [block(HIGH_CARD)],
        token_budget={"max_input_tokens": 500, "window": "all"},
    )
    assert attempt["outcome"] == AttemptOutcome.STOPPED_BY_CEILING.value
    assert provider.usage.calls == 0


# --- held-out sets and the leak-freeness pins ---------------------------------


def test_the_held_out_set_is_derived_from_the_tree() -> None:
    assert held_out_set("hearts", ROOT) is HeldOutSet.CORPUS
    assert held_out_set("crazy-eights", ROOT) is HeldOutSet.CANDIDATE
    # Listed as a candidate and in the corpus: the corpus file decides.
    assert held_out_set("gops", ROOT) is HeldOutSet.CORPUS
    with pytest.raises(ValueError, match="neither a corpus game"):
        held_out_set("nonesuch", ROOT)


def test_a_withheld_file_is_refused_as_a_reference(tree: Path) -> None:
    for path in withheld_paths("highcard"):
        with pytest.raises(ValueError, match="withheld file"):
            context_files(["docs/authoring.md", path.as_posix()], ["highcard"], tree)


def test_a_rules_directory_inside_the_games_is_refused(tmp_path: Path, tree: Path) -> None:
    inside = tree / "docs" / "games"
    (inside / "highcard.txt").write_text("rules")
    with pytest.raises(ValueError, match="inside docs/games"):
        game_specs(config(tmp_path), inside, tree)


def _windows(text: str, width: int = 3) -> set[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {"\n".join(lines[i : i + width]) for i in range(len(lines) - width + 1)}


def leaked(prompt_text: str, withheld: Sequence[str], allowed: Sequence[str]) -> set[str]:
    """Windows of a withheld file that appear in a prompt and in no allowed
    source: what only a leak could have put there."""
    prompt = _windows(prompt_text)
    seen_elsewhere = set().union(*(_windows(a) for a in allowed)) if allowed else set()
    return {w for text in withheld for w in _windows(text) if w in prompt and w not in seen_elsewhere}


def test_the_leak_check_catches_a_planted_leak() -> None:
    target = (ROOT / "docs" / "games" / "hearts.cardlang").read_text()
    guide = (ROOT / "docs" / "authoring.md").read_text()
    brief = GameBrief("Hearts", "4 players", "https://example.invalid", "rules")
    clean = build_prompt(task_text(2), [Reference("docs/authoring.md", guide)], brief, [])
    planted = build_prompt(
        task_text(2),
        [Reference("docs/authoring.md", guide), Reference("docs/x.cardlang", target)],
        brief,
        [],
    )
    assert leaked(clean.text, [target], [guide]) == set()
    assert leaked(planted.text, [target], [guide])


def test_no_shipped_prompt_shows_a_held_out_games_withheld_files(tmp_path: Path) -> None:
    shipped = yaml.safe_load(SHIPPED_CONFIG.read_text(encoding="utf-8"))
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    for game in shipped["games"]:
        (rules_dir / game["rules_file"]).write_text(f"The rules of {game['name']}.\n")
    cfg = dict(shipped)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        attempts=1,
        roster=["fake"],
        models={"fake": {"kind": "fake"}},
        token_budget={},
    )
    provider = FakeProvider(replies=["CANNOT EXPRESS: nothing, this is the leak pin"])
    run(
        cfg,
        SHIPPED_CONFIG,
        rules_dir,
        registry={"fake": provider},
        facts=FactsRunner(repo_root=ROOT, playouts=2),
        out=io.StringIO(),
    )
    allowed = [(ROOT / r).read_text(encoding="utf-8") for r in shipped["references"]]
    assert len(provider.prompts) == len(shipped["games"])
    corpus = 0
    for game, prompt in zip(shipped["games"], provider.prompts):
        if held_out_set(game["slug"], ROOT) is not HeldOutSet.CORPUS:
            continue
        corpus += 1
        withheld = [(ROOT / p).read_text(encoding="utf-8") for p in withheld_paths(game["slug"])]
        assert leaked(prompt, withheld, allowed) == set(), game["slug"]
    assert corpus, "the shipped config holds no corpus game, so the pin guards nothing"


# --- the prompt ----------------------------------------------------------------


def test_the_prompt_is_pure_and_cache_shaped() -> None:
    brief = GameBrief("High Card", "2 players", "https://example.invalid", "rules")
    refs = [Reference("docs/authoring.md", "guide")]
    first = build_prompt(task_text(3), refs, brief, [])
    assert first == build_prompt(task_text(3), refs, brief, [])
    assert first.cache_at == 1
    history = [RoundView(1, TWO_TYPOS, "game.cardlang:21:50: error: x", 1)]
    second = build_prompt(task_text(3), refs, brief, history)
    third = build_prompt(task_text(3), refs, brief, [*history, RoundView(2, ONE_TYPO, "y", 1)])
    # Each round reproduces the previous round's prefix through its breakpoint.
    assert second.blocks[: first.cache_at + 1] == first.blocks[: first.cache_at + 1]
    assert second.cache_at is not None and third.cache_at is not None
    assert third.blocks[: second.cache_at + 1] == second.blocks[: second.cache_at + 1]
    assert third.cache_at == len(third.blocks) - 2


def test_the_shipped_config_reads(tmp_path: Path) -> None:
    shipped = yaml.safe_load(SHIPPED_CONFIG.read_text(encoding="utf-8"))
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    for game in shipped["games"]:
        (rules_dir / game["rules_file"]).write_text("rules\n")
    specs = game_specs(shipped, rules_dir, ROOT)
    sets = {s.slug: s.held_out for s in specs}
    assert HeldOutSet.CORPUS in sets.values() and HeldOutSet.CANDIDATE in sets.values()
    context_files(shipped["references"], list(sets), ROOT)
    assert set(shipped["roster"]) <= set(shipped["models"])
    assert budget_of(shipped).max_cost_usd > 0
