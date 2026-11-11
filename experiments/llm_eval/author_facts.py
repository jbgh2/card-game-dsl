"""The authoring benchmark's real-game check: encoding-invariant facts of a
game file, and the differential that compares two files by them.

A model-written game and the corpus file for the same game number their
actions differently, deal through different statement sequences and name
their zones as they like, so neither a byte comparison nor a same-seed replay
says whether they are one game: the random draws diverge at the first
statement that consumes one differently. What two faithful encodings of one
game share is the game's decision tree up to relabelling, and under
uniform-random play over the offered candidates a tree's outcome
distribution is a property of the tree, not of its labels. So the check
compares facts that survive relabelling:

- the table: the seat count and the Component Set, exactly;
- per playout, under uniform-random play: the choices made (decisions
  offering two or more candidates, so a forced pick one encoding offers and
  another performs is not counted), the hands played, whether the playout
  reached the game's `max_length` (a Length Stop), how many seats share the
  win, and the mean number of distinct card identities the deciding seat
  has been shown (its zones' identity views plus every card its observation
  log names) at each of its choices.

The playout facts are compared as distributions, sample against sample, by
a two-sample Kolmogorov-Smirnov test (`ks_two_sample`), with a family-wise
level split evenly across the facts. A fact whose two samples differ beyond
that level refutes the file; a file that refutes no fact AGREES ON THE FACTS
COMPARED, which is the strongest claim this instrument makes. It is never
"is the real game": a rule uniform play rarely reaches (shooting the moon), a
scoring magnitude (the winner set is compared, never the returns), and an
information structure that differs only in what a seat may infer rather
than in what it is shown, all pass unseen. And a refutation can be an
encoding that changes the tree's shape without changing the game (a choice
offered as two decisions where the reference offers one), so a refuted file
carries the facts that disagreed for a rules read to confirm or overturn.

The facts are taken in a subprocess (`python -m
experiments.llm_eval.author_facts FILE`), so a model-written file that hangs
or crashes the engine is a recorded outcome of the run rather than the end
of it.

Contract
--------
Assumes: the file checks green (the extraction re-checks it and reports a
refusal as `refused`, never as facts).
Establishes: `FactsRecord`, one per file, carrying the table facts and one
`PlayoutFacts` per seeded playout or the reason there are none; `compare`
returning a `Differential` whose verdict is one of `DifferentialVerdict`.
Illegal after: reading a returns vector as a fact (two faithful encodings may
score on different scales), and comparing two files' playouts line by line.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from .author_check import checker_env

#: The per-playout facts, in the order a report lists them. One registry:
#: `PlayoutFacts` carries exactly these fields and `compare` tests exactly
#: these, so a fact cannot be extracted and never compared.
PLAYOUT_FACTS: Final[tuple[str, ...]] = (
    "choices",
    "hands_played",
    "length_stopped",
    "winner_count",
    "known_at_choice",
)

#: The family-wise level the playout facts are refuted at. Split evenly
#: across `PLAYOUT_FACTS` (Bonferroni), so a faithful file is refuted on any
#: fact by chance at most this often.
FAMILY_ALPHA: Final = 1e-3


class FactsStatus(Enum):
    """How a facts extraction ended."""

    OK = "ok"
    #: The file did not check green when the extraction re-checked it.
    REFUSED = "refused"
    #: A playout raised one of the engine's refusals of game text: the
    #: file checks green and its rules refuse at play.
    PLAY_REFUSED = "play_refused"
    #: Anything else escaped, or the subprocess died.
    CRASHED = "crashed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class PlayoutFacts:
    """One seeded uniform-random playout's facts (`PLAYOUT_FACTS`)."""

    seed: int
    choices: int
    hands_played: int
    length_stopped: int
    winner_count: int
    known_at_choice: float


@dataclass(frozen=True)
class FactsRecord:
    """Everything the extraction learned about one file."""

    status: FactsStatus
    players: int | None = None
    component_set: str | None = None
    playouts: tuple[PlayoutFacts, ...] = ()
    detail: str = ""
    wall_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["status"] = self.status.value
        return out

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> FactsRecord:
        return FactsRecord(
            status=FactsStatus(data["status"]),
            players=data.get("players"),
            component_set=data.get("component_set"),
            playouts=tuple(PlayoutFacts(**p) for p in data.get("playouts", ())),
            detail=str(data.get("detail", "")),
            wall_seconds=float(data.get("wall_seconds", 0.0)),
        )


# --- extraction (runs inside the subprocess) -------------------------------


def _known_identities(view: Any, names: frozenset[str]) -> int:
    """Distinct card identities a seat view shows: its zones' identity views,
    and every card name its observation log carries."""
    seen: set[str] = set()
    for _label, zone in view.zones:
        if isinstance(zone, tuple):
            seen.update(str(card) for card in zone)

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if value in names:
                seen.add(value)
        elif isinstance(value, (tuple, list, frozenset, set)):
            for item in value:
                walk(item)
        elif type(value).__name__ == "Card":
            seen.add(str(value))

    for event in view.obs_log:
        walk(event)
    return len(seen)


def _all_card_names(rs: Any) -> frozenset[str]:
    """Every card name in the world: what a log string must be to be a card."""
    names: set[str] = set()
    for zone in rs.zones.singles.values():
        names.update(str(card) for card in zone.cards)
    for family in rs.zones.families.values():
        for zone in family.values():
            names.update(str(card) for card in zone.cards)
    return frozenset(names)


def _playout(game: Any, seed: int) -> PlayoutFacts:
    from cardlang.openspiel.infostate import derive
    from cardlang.runtime.chooser import random_chooser, sequential_decisions
    from cardlang.runtime.driver import EndedBy, play_game

    seats = game.players.count
    rng = random.Random(seed)
    play_uniformly = random_chooser(rng)
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(seats)}
    world: list[Any] = []
    names: list[frozenset[str]] = []
    counts = {"choices": 0, "known": 0}

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    def hold(rs: Any) -> None:
        world.append(rs)
        names.append(_all_card_names(rs))

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        taken = iter(play_uniformly(player, candidates, count))

        def decide(actor: int, pool: list[Any]) -> Any:
            if len(pool) >= 2:
                counts["choices"] += 1
                counts["known"] += _known_identities(
                    derive(actor, world[0], logs[actor]), names[0]
                )
            return next(taken)

        return sequential_decisions(player, candidates, count, decide)

    result = play_game(
        game, rng, None, chooser=choose, observer=observe, on_first_decision=hold
    )
    choices = counts["choices"]
    return PlayoutFacts(
        seed=seed,
        choices=choices,
        hands_played=result.hands_played,
        length_stopped=int(result.ended_by is EndedBy.LENGTH),
        winner_count=len(result.winners),
        known_at_choice=round(counts["known"] / choices, 6) if choices else 0.0,
    )


def extract(path: Path, *, playouts: int, seed_start: int) -> FactsRecord:
    """The facts of the file at `path`, in this process."""
    from cardlang.diagnostics import DiagnosticError
    from cardlang.pipeline import check_source
    from cardlang.runtime.errors import GameDescriptionError
    from cardlang.runtime.state import IllegalMove

    started = time.monotonic()
    try:
        game = check_source(path)
    except DiagnosticError as exc:
        return FactsRecord(FactsStatus.REFUSED, detail=exc.diagnostic.format())
    rows: list[PlayoutFacts] = []
    for seed in range(seed_start, seed_start + playouts):
        try:
            rows.append(_playout(game, seed))
        except (GameDescriptionError, IllegalMove) as exc:
            return FactsRecord(
                FactsStatus.PLAY_REFUSED,
                players=game.players.count,
                component_set=game.deck,
                playouts=tuple(rows),
                detail=f"seed {seed}: {type(exc).__name__}: {exc}",
                wall_seconds=round(time.monotonic() - started, 3),
            )
    return FactsRecord(
        FactsStatus.OK,
        players=game.players.count,
        component_set=game.deck,
        playouts=tuple(rows),
        wall_seconds=round(time.monotonic() - started, 3),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="print a game file's facts as JSON")
    parser.add_argument("file")
    parser.add_argument("--playouts", type=int, required=True)
    parser.add_argument("--seed-start", type=int, default=0)
    args = parser.parse_args(argv)
    record = extract(Path(args.file), playouts=args.playouts, seed_start=args.seed_start)
    print(json.dumps(record.as_dict(), ensure_ascii=False))
    return 0


# --- the subprocess boundary ----------------------------------------------


@dataclass(frozen=True)
class FactsRunner:
    """How the rig takes a file's facts: which interpreter, against which
    checkout, under which wall-clock bound."""

    repo_root: Path
    python: str = sys.executable
    timeout_seconds: float = 600.0
    playouts: int = 100
    seed_start: int = 0

    def run(self, path: Path) -> FactsRecord:
        argv = [
            self.python,
            "-m",
            "experiments.llm_eval.author_facts",
            str(path),
            "--playouts",
            str(self.playouts),
            "--seed-start",
            str(self.seed_start),
        ]
        started = time.monotonic()
        try:
            done = subprocess.run(
                argv,
                cwd=self.repo_root,
                env=checker_env(self.repo_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return FactsRecord(
                FactsStatus.TIMED_OUT,
                detail=f"no answer within {self.timeout_seconds}s",
                wall_seconds=round(time.monotonic() - started, 3),
            )
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        if done.returncode != 0 or not lines:
            return FactsRecord(
                FactsStatus.CRASHED,
                detail=f"exit {done.returncode}: {done.stderr[-4000:]}",
                wall_seconds=round(time.monotonic() - started, 3),
            )
        try:
            return FactsRecord.from_dict(json.loads(lines[-1]))
        except (ValueError, KeyError, TypeError) as exc:
            return FactsRecord(
                FactsStatus.CRASHED,
                detail=f"unreadable facts ({exc}): {lines[-1][:2000]}",
                wall_seconds=round(time.monotonic() - started, 3),
            )


# --- the differential ------------------------------------------------------


def ks_two_sample(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """The two-sample Kolmogorov-Smirnov statistic and its asymptotic p-value.

    Hand-rolled, as `compare.py` hand-rolls Fisher's test, so a reader can
    reproduce a verdict without a statistics package. The p-value is the
    Kolmogorov distribution's tail at the effective sample size, with the
    small-sample correction of Stephens (1970); on discrete samples, which
    every fact here is, it is conservative, which is the direction a
    refutation wants.
    """
    if not a or not b:
        raise ValueError("a two-sample test needs two non-empty samples")
    xs, ys = sorted(a), sorted(b)
    n, m = len(xs), len(ys)
    i = j = 0
    d = 0.0
    while i < n and j < m:
        value = min(xs[i], ys[j])
        while i < n and xs[i] == value:
            i += 1
        while j < m and ys[j] == value:
            j += 1
        d = max(d, abs(i / n - j / m))
    effective = math.sqrt(n * m / (n + m))
    lam = (effective + 0.12 + 0.11 / effective) * d
    return d, _kolmogorov_tail(lam)


def _kolmogorov_tail(lam: float) -> float:
    """P(K > lam) for the Kolmogorov distribution."""
    if lam < 1e-3:
        return 1.0
    total = 0.0
    for k in range(1, 101):
        term = 2.0 * (-1) ** (k - 1) * math.exp(-2.0 * k * k * lam * lam)
        total += term
        if abs(term) < 1e-12:
            break
    return min(1.0, max(0.0, total))


class DifferentialVerdict(Enum):
    """What the differential could say about a candidate file."""

    #: Every fact compared agrees at the family-wise level. Not "is the
    #: real game": the module docstring says what passes unseen.
    AGREES = "agrees_on_facts_compared"
    #: A table fact differs, or a playout fact's distributions differ.
    DIVERGES = "diverges"
    #: The candidate checks green and does not play: its rules refuse, it
    #: crashes the engine, or it outruns the bound.
    DOES_NOT_PLAY = "does_not_play"
    #: The reference itself yielded no facts; nothing is compared.
    NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True)
class FactComparison:
    fact: str
    reference: str
    candidate: str
    statistic: float | None
    p_value: float | None
    agrees: bool


@dataclass(frozen=True)
class Differential:
    verdict: DifferentialVerdict
    comparisons: tuple[FactComparison, ...] = ()
    detail: str = ""
    alpha_per_fact: float = FAMILY_ALPHA / len(PLAYOUT_FACTS)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "comparisons": [asdict(c) for c in self.comparisons],
            "detail": self.detail,
            "alpha_per_fact": self.alpha_per_fact,
        }


def _summary(values: Sequence[float]) -> str:
    if not values:
        return "none"
    mean = sum(values) / len(values)
    return f"mean {mean:.3f}, range {min(values):g}..{max(values):g}, n={len(values)}"


def compare(reference: FactsRecord, candidate: FactsRecord) -> Differential:
    """The candidate's facts against the reference's."""
    if reference.status is not FactsStatus.OK or not reference.playouts:
        return Differential(
            DifferentialVerdict.NOT_COMPARABLE,
            detail=f"reference facts: {reference.status.value} {reference.detail}",
        )
    if candidate.status is not FactsStatus.OK or not candidate.playouts:
        return Differential(
            DifferentialVerdict.DOES_NOT_PLAY,
            detail=f"candidate facts: {candidate.status.value} {candidate.detail}",
        )
    alpha = FAMILY_ALPHA / len(PLAYOUT_FACTS)
    rows: list[FactComparison] = []
    for fact, ref_value, cand_value in (
        ("players", reference.players, candidate.players),
        ("component_set", reference.component_set, candidate.component_set),
    ):
        rows.append(
            FactComparison(
                fact, str(ref_value), str(cand_value), None, None, ref_value == cand_value
            )
        )
    for fact in PLAYOUT_FACTS:
        ref = [float(getattr(p, fact)) for p in reference.playouts]
        cand = [float(getattr(p, fact)) for p in candidate.playouts]
        statistic, p_value = ks_two_sample(ref, cand)
        rows.append(
            FactComparison(
                fact,
                _summary(ref),
                _summary(cand),
                round(statistic, 6),
                p_value,
                p_value >= alpha,
            )
        )
    verdict = (
        DifferentialVerdict.AGREES
        if all(row.agrees for row in rows)
        else DifferentialVerdict.DIVERGES
    )
    return Differential(verdict, tuple(rows), alpha_per_fact=alpha)


@dataclass
class ReferenceCache:
    """Each reference file's facts, taken once per run."""

    runner: FactsRunner
    taken: dict[Path, FactsRecord] = field(default_factory=dict)

    def facts(self, path: Path) -> FactsRecord:
        if path not in self.taken:
            self.taken[path] = self.runner.run(path)
        return self.taken[path]


if __name__ == "__main__":
    raise SystemExit(main())
