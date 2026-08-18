"""T2 (+T3): the corpus-mutation sweep (grammar-fuzzing.md, "Stage 1 — corpus mutation").

Every `(corpus game, operator, seed)` triple in the fixed CI grid below
produces one mutant (`mutate.mutate_text`), which is run through the T1
oracle (`oracle.run_oracle`) and, if it passes the pipeline, the T3 playout
invariants (`oracle.run_playout`). Three outcomes are all fine and cost
nothing: `"rejected"` (a `DiagnosticError` — the pipeline did its job),
`"terminated"`, and `"cutoff"` (the playout ran clean, whether or not it
reached a natural end within the step budget — see `oracle.py`,
"Termination"). Two outcomes are findings: an oracle `"crash"`
(wrong-channel) or a playout `"crash"` (accepted-then-crashes-at-playout).

A finding at an `EXCUSED` triple is expected — it is already shrunk,
classified, and pinned in `findings.KNOWN_FINDINGS` — and does not fail this
sweep, PROVIDED the live crash matches the recorded finding (same stage,
exception type, and message substring — `_assert_crash_matches_excused`): a
corpus or mutator change producing a DIFFERENT crash at an excused triple is
a new finding wearing an old excuse's key and fails loudly with both crashes
shown. A finding at ANY OTHER triple is new and fails the sweep with a
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
The sweep is the full corpus x every operator in `mutate.MUTATORS` x
`MUTATION_SEEDS`; its cost is dominated by Lark parsing, since the grammar
is Earley rather than LALR and parse cost scales with source size.
`CARDLANG_FUZZ_SEEDS` overrides the list
(comma-separated) for a deeper but still-bounded run; `FUZZ_BUDGET_SECONDS`
(seconds) turns on `test_fuzz_open_ended_local`, a single unparametrized
test that keeps sweeping increasing seeds until the guard-clock budget is
spent — the plan's env-var knob for local/scheduled use.

Ledger (decisions.md "Closed-domain completeness")
----------------------------------------------------
property:   every mutant produced by `MUTATORS` (mutate.py) over
            `docs/games/*.cardlang`, at the seeds in `MUTATION_SEEDS`,
            either (a) is rejected by `check_dsl` with a `DiagnosticError`,
            (b) passes and its playout terminates or is cleanly cut off, or
            (c) crashes at a triple already recorded in `EXCUSED` +
            `findings.KNOWN_FINDINGS`.
domain:     `CORPUS x OPERATORS x MUTATION_SEEDS` — the full
            `docs/games/*.cardlang` glob (mirroring every other corpus-wide
            harness in this repo) x every operator (`mutate.MUTATORS`, the
            plan's full Stage-1 list) x 2 seeds by default.
registry:   `mutate.MUTATORS` (closed, pinned by `test_mutate.py`'s own
            enumeration test) and `findings.KNOWN_FINDINGS` (closed, pinned
            by `test_known_findings_directory_matches_ledger` below against
            `known_findings/*.cardlang`).
covered:    a discovery sweep at authoring time (seeds 0-4, the whole corpus,
            every operator) found 6 crashing triples,
            all under `delete_line`; all 6 were in `EXCUSED`/`KNOWN_FINDINGS`.
            Re-run in full after the chooser was strengthened to the runtime
            chooser's whole `k <= len(candidates)` contract (it previously
            checked only the empty-pool special case): identical 6 findings —
            no mutant at these seeds requests an over-sized pick from a
            non-empty pool within the step budget.
            Two of the six were Skat's, and both were FIXED rather than
            re-keyed when the Trick Order retired the Primitives whose reads
            crashed (issue #250 PR 2, the `EXCUSED` comment below); they left
            the ledger by the feed-forward rule, so four remain.
            `MUTATION_SEEDS = (0, 2)` was chosen specifically because it
            covers 3 of those 4 triples (`getaway_no_legal_play...` needed
            seed 4 and is validated only by the frozen pinned test, not by
            this live sweep — see its `EXCUSED` comment below).
sampled:    every other `(game, operator, seed)` triple outside that
            discovery sweep — the checked-in default is a small slice of an
            all-operator x whole-corpus x unbounded-seed space.
residual:   grammar-DIRECTED generation (the plan's T4, walking
            `cardlang.grammar` productions) and mechanized shrinking (T5)
            are not implemented — every finding above was shrunk by hand
            (`oracle.py`'s "Residual"). `duplicate_declaration` and
            `swap_adjacent_tokens` found nothing in the discovery sweep;
            that is evidence those guards hold against THESE five seeds on
            THIS corpus, not a completeness claim about the operators
            themselves — a wider `CARDLANG_FUZZ_SEEDS` or `FUZZ_BUDGET_SECONDS`
            run may surface more.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from .findings import FINDINGS_DIR, KNOWN_FINDINGS, Finding
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
    ("klondike.cardlang", "delete_line", 0): "klondike_flip_from_empty_stack",
    # `cribbage_repeat_until_nonterminate` has NO live-corpus key anymore: the
    # card_points clause (issue #249) shifted cribbage.cardlang, and the seed-2
    # deletion now removes a `repeat until ... {` opener — the mutant is
    # REJECTED at parse (unbalanced braces), so the old excuse would excuse
    # nothing (the vacuously-green class). The finding itself stays in the
    # ledger under its frozen fixture, which still reproduces it.
    ("getaway.cardlang", "delete_line", 0): "getaway_missing_deal_no_hand_holder",
    ("getaway.cardlang", "delete_line", 4): "getaway_no_legal_play_no_if_impossible",
    ("gops.cardlang", "delete_line", 2): "gops_empty_legal_set",
    # Skat has NO key here anymore, and no ledger entry either. Both of its
    # findings were reads that the Trick Order retired with the Primitives that
    # made them (issue #250 PR 2): `skat_follow_ok`'s bare `IndexError` on
    # `trick_pile[0]` cannot happen because nothing reads the led card that way
    # -- `follows_lead` on a pile with nothing led is the VALUE false (issue
    # #345), pinned by tests/test_trick_order.py -- and the completed-trick
    # count guard was `recorded_plays`', which the kernel winner deliberately
    # does not consult (a mid-trick read is the winner so far, issue #350). The
    # same deliberate deletion of the leader's play now surfaces in the
    # harness's own T3 invariant instead, the `gops_empty_legal_set` channel.
}


def _new_finding_message(
    game_path: Path, operator: str, seed: int, outcome: OracleOutcome | PlayoutOutcome, stage: str
) -> str:
    return (
        f"NEW fuzz finding at {game_path.name} / {operator} / seed={seed} "
        f"({stage}): {outcome.summary()}\n"
        "This is not a regression to fix here — shrink it by hand, classify "
        "it (wrong-channel-crash / accepted-then-crashes-at-playout), and "
        "record it in tests/fuzz/findings.py's KNOWN_FINDINGS (see that "
        "module's docstring for the ledger format and the feed-forward "
        "rule) plus add it to this module's EXCUSED table."
    )


def _finding_by_slug(slug: str) -> Finding:
    # `test_excused_table_targets_known_findings` pins that every EXCUSED
    # slug resolves; this lookup is its Shadow Guard at use time.
    matches = [f for f in KNOWN_FINDINGS if f.slug == slug]
    assert matches, f"EXCUSED names unknown finding {slug!r}"
    return matches[0]


def _assert_crash_matches_excused(
    finding: Finding,
    stage: str,
    exc: BaseException,
    game_path: Path,
    operator: str,
    seed: int,
) -> None:
    """An excused triple is only excused for the SPECIFIC crash its ledger
    entry records — same stage, same exception type, same message substring.
    A corpus or mutator change that produces a DIFFERENT crash at the same
    (file, operator, seed) triple is a NEW finding wearing an old excuse's
    key, and silently accepting it would hide it exactly the way an
    un-excused crash is never hidden."""
    mismatches: list[str] = []
    if stage != finding.stage:
        mismatches.append(f"stage: observed {stage!r}, recorded {finding.stage!r}")
    if type(exc).__name__ != finding.exception_type_name:
        mismatches.append(
            f"exception type: observed {type(exc).__name__!r}, recorded "
            f"{finding.exception_type_name!r}"
        )
    if finding.message_substring not in str(exc):
        mismatches.append(
            f"message: observed {str(exc)!r}, which does not contain the "
            f"recorded substring {finding.message_substring!r}"
        )
    assert not mismatches, (
        f"the crash at {game_path.name} / {operator} / seed={seed} no longer "
        f"matches its EXCUSED ledger entry {finding.slug!r}:\n  "
        + "\n  ".join(mismatches)
        + "\nThis is a NEW finding hiding behind an old excuse's key — "
        "record it as its own KNOWN_FINDINGS entry (findings.py's ledger "
        "format), or update the existing entry if the recorded crash "
        "genuinely evolved with the corpus."
    )


def _run_one(game_path: Path, operator: str, seed: int) -> None:
    """Mutate, run the T1 oracle, and — if it passed — the T3 playout
    invariants. Fails loudly on any crash not already in `EXCUSED`, and on
    any crash that IS in `EXCUSED` but differs from the recorded finding."""
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
        assert oracle_outcome.exception is not None
        _assert_crash_matches_excused(
            _finding_by_slug(excused), "oracle", oracle_outcome.exception,
            game_path, operator, seed,
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
        assert playout_outcome.exception is not None
        _assert_crash_matches_excused(
            _finding_by_slug(excused), "playout", playout_outcome.exception,
            game_path, operator, seed,
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


def test_excused_mismatch_fails_loudly() -> None:
    """The suppression path's own misuse probe: an excused triple whose live
    crash DIFFERS from the recorded finding (here: wrong exception type and
    message) must fail with both crashes shown, not be silently excused."""
    finding = _finding_by_slug("gops_empty_legal_set")  # any playout-stage entry
    wrong_crash = ValueError("an entirely different failure")
    with pytest.raises(AssertionError, match="no longer matches its EXCUSED ledger entry"):
        _assert_crash_matches_excused(
            finding, "playout", wrong_crash, Path("gops.cardlang"), "delete_line", 2
        )
    # Stage mismatch alone is also enough.
    right_crash = AssertionError("playout invariant violated: ...")
    with pytest.raises(AssertionError, match="stage: observed 'oracle'"):
        _assert_crash_matches_excused(
            finding, "oracle", right_crash, Path("gops.cardlang"), "delete_line", 2
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
    corpus x operator grid until the guard-clock budget runs out. Skipped by
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
