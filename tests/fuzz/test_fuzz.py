"""T2 (+T3): the corpus-mutation sweep (grammar-fuzzing.md, "Stage 1").

Every `(corpus game, operator, seed)` triple in the fixed CI grid below
produces one mutant (`mutate.mutate_text`), which is run through the T1
oracle (`oracle.run_oracle`) and, if it passes the pipeline, the T3 playout
invariants (`oracle.run_playout`). Three outcomes are all fine and cost
nothing: `"rejected"` (a `DiagnosticError` — the pipeline did its job),
`"terminated"`, and `"cutoff"` (the playout ran clean, whether or not it
reached a natural end within the step budget — see `oracle.py`,
"Termination"). Two outcomes are findings: an oracle `"crash"`
(wrong-currency) or a playout `"crash"` (accepted-then-crashes-at-playout).

A finding at an `EXCUSED` triple is expected — it is already shrunk,
classified, and pinned in `findings.KNOWN_FINDINGS` — and does not fail this
sweep. A finding at ANY OTHER triple is new and fails the sweep with a
message pointing at `findings.py`'s feed-forward rule: shrink it, classify
it, add it to the ledger (do not edit `cardlang/` to make it go away — see
`oracle.py`'s module docstring on why this package makes zero such edits).
`test_known_findings_still_reproduce` is the separate, ALWAYS-RUNNING check
that each `EXCUSED`/ledger entry is still live — the "loud and pinned"
half: it runs the frozen `known_findings/*.cardlang` file directly (no
`EXCUSED` lookup, no dependency on the live corpus or `mutate.py`) and fails
if the recorded crash stops reproducing, which is the prompt to retire it
via the feed-forward rule rather than let the ledger go stale silently.

CI budget vs. the open-ended local mode (grammar-fuzzing.md, "CI is
deterministic"). `MUTATION_SEEDS` is a small fixed, checked-in seed list —
not a contiguous `range`, an explicit tuple chosen to include every seed at
which the `EXCUSED` findings below were discovered, so the sweep actually
exercises the suppression path on every CI run rather than only in theory.
Measured: 18 games x 5 operators x `MUTATION_SEEDS` (2 seeds) = 180 mutants,
~45-55s locally (dominated by Lark parse cost — the grammar is Earley, not
LALR, and cost scales with source size: `docs/games/doppelkopf.cardlang`
alone costs ~1s per parse). `CARDLANG_FUZZ_SEEDS` overrides the list
(comma-separated) for a deeper but still-bounded run; `FUZZ_BUDGET_SECONDS`
(seconds) turns on `test_fuzz_open_ended_local`, a single unparametrized
test that keeps sweeping increasing seeds until the wall-clock budget is
spent — the plan's env-var knob for local/scheduled use.

Ledger (decisions.md "Closed-domain completeness")
----------------------------------------------------
property:   every mutant produced by `MUTATORS` (mutate.py) over
            `docs/games/*.cardlang`, at the seeds in `MUTATION_SEEDS`,
            either (a) is rejected by `check_dsl` with a `DiagnosticError`,
            (b) passes and its playout terminates or is cleanly cut off, or
            (c) crashes at a triple already recorded in `EXCUSED` +
            `findings.KNOWN_FINDINGS`.
domain:     `CORPUS x OPERATORS x MUTATION_SEEDS` — 18 games (the full
            `docs/games/*.cardlang` glob, mirroring every other corpus-wide
            harness in this repo) x 5 operators (`mutate.MUTATORS`, the
            plan's full Stage-1 list) x 2 seeds by default.
registry:   `mutate.MUTATORS` (closed, pinned by `test_mutate.py`'s own
            enumeration test) and `findings.KNOWN_FINDINGS` (closed, pinned
            by `test_known_findings_directory_matches_ledger` below against
            `known_findings/*.cardlang`).
covered:    a discovery sweep at authoring time (seeds 0-4, all 18 games, all
            5 operators — 450 mutants, ~123s) found 6 crashing triples, all
            under `delete_line`; all 6 are in `EXCUSED`/`KNOWN_FINDINGS`.
            `MUTATION_SEEDS = (0, 2)` was chosen specifically because it
            covers 5 of those 6 triples (`getaway_no_legal_play...` needed
            seed 4 and is validated only by the frozen pinned test, not by
            this live sweep — see its `EXCUSED` comment below).
sampled:    every other `(game, operator, seed)` triple outside that
            discovery sweep — a fixed 2-seed default is a small slice of a
            5-operator x 18-game x unbounded-seed space.
residual:   grammar-DIRECTED generation (the plan's T4, walking
            `cardlang.grammar` productions) and mechanized shrinking (T5)
            are not implemented — every finding above was shrunk by hand
            (`oracle.py`'s "Residual"). `duplicate_declaration` and
            `swap_adjacent_tokens` found nothing in the discovery sweep;
            that is evidence those walls hold against THESE five seeds on
            THIS corpus, not a completeness claim about the operators
            themselves — a wider `CARDLANG_FUZZ_SEEDS` or `FUZZ_BUDGET_SECONDS`
            run may surface more.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from .findings import KNOWN_FINDINGS, FINDINGS_DIR, Finding
from .mutate import MUTATORS, mutate_text
from .oracle import OracleOutcome, PlayoutOutcome, run_oracle, run_playout

GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"
CORPUS: tuple[Path, ...] = tuple(sorted(GAMES_DIR.glob("*.cardlang")))
OPERATORS: tuple[str, ...] = tuple(sorted(MUTATORS))

_DEFAULT_SEEDS = "0,2"
MUTATION_SEEDS: tuple[int, ...] = tuple(
    int(s) for s in os.environ.get("CARDLANG_FUZZ_SEEDS", _DEFAULT_SEEDS).split(",") if s
)

# (corpus filename, operator, seed) -> the `findings.KNOWN_FINDINGS` slug it
# reproduces. Every key here is a triple this sweep will actually hit at the
# default `MUTATION_SEEDS`, EXCEPT `getaway_no_legal_play_no_if_impossible`
# (needs seed 4, outside the default 2-seed CI list) — kept in the table
# anyway so a `CARDLANG_FUZZ_SEEDS` run that DOES include seed 4 is still
# correctly excused rather than reported as a spurious new finding.
EXCUSED: dict[tuple[str, str, int], str] = {
    ("gops.cardlang", "delete_line", 0): "missing_cards_declaration",
    ("cribbage.cardlang", "delete_line", 2): "cribbage_repeat_until_nonterminate",
    ("getaway.cardlang", "delete_line", 0): "getaway_missing_deal_no_hand_holder",
    ("getaway.cardlang", "delete_line", 4): "getaway_no_legal_play_no_if_impossible",
    ("gops.cardlang", "delete_line", 2): "gops_empty_legal_set",
    ("skat.cardlang", "delete_line", 2): "skat_trick_winner_wrong_count",
}


def _new_finding_message(
    game_path: Path, operator: str, seed: int, outcome: OracleOutcome | PlayoutOutcome, stage: str
) -> str:
    return (
        f"NEW fuzz finding at {game_path.name} / {operator} / seed={seed} "
        f"({stage}): {outcome.summary()}\n"
        "This is not a regression to fix here — shrink it by hand, classify "
        "it (wrong-currency-crash / accepted-then-crashes-at-playout), and "
        "record it in tests/fuzz/findings.py's KNOWN_FINDINGS (see that "
        "module's docstring for the ledger format and the feed-forward "
        "rule) plus add it to this module's EXCUSED table."
    )


def _run_one(game_path: Path, operator: str, seed: int) -> None:
    """Mutate, run the T1 oracle, and — if it passed — the T3 playout
    invariants. Fails loudly on any crash not already in `EXCUSED`."""
    text = game_path.read_text()
    mutated = mutate_text(text, operator, seed, label=game_path.name)
    if mutated is None or mutated == text:
        pytest.skip(f"{operator} produced no mutant for {game_path.name} seed={seed}")
    key = (game_path.name, operator, seed)
    excused = EXCUSED.get(key)

    oracle_outcome = run_oracle(mutated, f"{game_path.name}[{operator}#{seed}]")
    if oracle_outcome.kind == "crash":
        assert excused is not None, _new_finding_message(
            game_path, operator, seed, oracle_outcome, "oracle"
        )
        return
    if oracle_outcome.kind == "rejected":
        return  # the expected, correctly-diagnosed outcome
    assert oracle_outcome.kind == "passed"
    assert oracle_outcome.game is not None

    playout_outcome = run_playout(oracle_outcome.game, seed=seed)
    if playout_outcome.kind == "crash":
        assert excused is not None, _new_finding_message(
            game_path, operator, seed, playout_outcome, "playout"
        )
        return
    # "terminated" or "cutoff": both are clean (oracle.py, "Termination").


def _grid() -> list[tuple[Path, str, int]]:
    return [
        (path, operator, seed)
        for path in CORPUS
        for operator in OPERATORS
        for seed in MUTATION_SEEDS
    ]


@pytest.mark.parametrize(
    "game_path,operator,seed",
    _grid(),
    ids=[f"{p.stem}-{op}-{s}" for p, op, s in _grid()],
)
def test_mutant_obeys_oracle_contract(game_path: Path, operator: str, seed: int) -> None:
    _run_one(game_path, operator, seed)


@pytest.mark.parametrize("finding", KNOWN_FINDINGS, ids=[f.slug for f in KNOWN_FINDINGS])
def test_known_findings_still_reproduce(finding: Finding) -> None:
    """The "loud and pinned" half of the ledger (findings.py's module
    docstring): replay each frozen `known_findings/*.cardlang` file
    directly — no corpus, no `mutate.py` — and assert the SAME crash still
    happens. If this test fails, the underlying issue was fixed without the
    ledger being updated: follow findings.py's feed-forward rule instead of
    re-skipping this test."""
    text = finding.text
    oracle_outcome = run_oracle(text, finding.slug)

    if finding.stage == "oracle":
        assert oracle_outcome.kind == "crash", (
            f"{finding.slug} no longer crashes the T1 oracle (got "
            f"{oracle_outcome.kind}: {oracle_outcome.summary()}) — if this "
            "was fixed, retire this ledger entry per findings.py's "
            "feed-forward rule instead of leaving it stale."
        )
        exc: BaseException | None = oracle_outcome.exception
    else:
        assert oracle_outcome.kind == "passed", (
            f"{finding.slug}: expected the pipeline to accept this frozen "
            f"input, got {oracle_outcome.kind}: {oracle_outcome.summary()}"
        )
        assert oracle_outcome.game is not None
        playout_outcome = run_playout(oracle_outcome.game, seed=0)
        assert playout_outcome.kind == "crash", (
            f"{finding.slug} no longer crashes at T3 playout (got "
            f"{playout_outcome.kind}: {playout_outcome.summary()}) — if "
            "this was fixed, retire this ledger entry per findings.py's "
            "feed-forward rule instead of leaving it stale."
        )
        exc = playout_outcome.exception

    assert exc is not None
    assert type(exc).__name__ == finding.exception_type_name, (
        f"{finding.slug}: expected {finding.exception_type_name}, got "
        f"{type(exc).__name__}: {exc}"
    )
    assert finding.message_substring in str(exc), (
        f"{finding.slug}: expected {finding.message_substring!r} in the "
        f"exception message, got: {exc}"
    )


def test_known_findings_directory_matches_ledger() -> None:
    """Registry closure (decisions.md "Closed-domain completeness"): every
    `known_findings/*.cardlang` file has a `KNOWN_FINDINGS` entry and vice
    versa — an orphan file or a ledger entry with no file fails loudly
    rather than silently going stale, mirroring
    `tests/rejections/test_every_cardlang_case_has_a_matching_expected`'s
    idiom for the same shape of registry."""
    on_disk = {p.stem for p in FINDINGS_DIR.glob("*.cardlang")}
    in_ledger = {f.slug for f in KNOWN_FINDINGS}
    assert on_disk == in_ledger, (
        f"known_findings/*.cardlang and findings.KNOWN_FINDINGS disagree: "
        f"only on disk: {on_disk - in_ledger}; only in the ledger: "
        f"{in_ledger - on_disk}"
    )


def test_excused_table_targets_known_findings() -> None:
    """Every `EXCUSED` value must name a real ledger entry — a typo'd slug
    would silently excuse nothing (the `.get` returns `None`, so the sweep
    would just treat that triple as un-excused) rather than failing loudly,
    which is a much worse failure mode to debug than this one-line check."""
    slugs = {f.slug for f in KNOWN_FINDINGS}
    for key, slug in EXCUSED.items():
        assert slug in slugs, f"EXCUSED[{key}] names unknown finding {slug!r}"


def test_fuzz_open_ended_local() -> None:
    """The plan's env-var knob (grammar-fuzzing.md, "CI is deterministic"):
    with `FUZZ_BUDGET_SECONDS` set, sweep increasing seeds across the whole
    corpus x operator grid until the wall-clock budget runs out. Skipped by
    default — this is the local/scheduled mode, not part of ordinary CI."""
    budget = os.environ.get("FUZZ_BUDGET_SECONDS")
    if not budget:
        pytest.skip(
            "FUZZ_BUDGET_SECONDS not set — this is the open-ended local "
            "mode (grammar-fuzzing.md's env-var knob), not part of the "
            "default CI sweep"
        )
    deadline = time.monotonic() + float(budget)
    seed = 0
    checked = 0
    while time.monotonic() < deadline:
        for game_path in CORPUS:
            for operator in OPERATORS:
                if time.monotonic() >= deadline:
                    break
                _run_one(game_path, operator, seed)
                checked += 1
        seed += 1
    print(f"open-ended fuzz: checked {checked} mutants across seeds 0..{seed - 1}")
