"""Unit tests for oracle.py's T1/T3 machinery, independent of the corpus
and of mutate.py (test_fuzz.py exercises the two together)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError

from .oracle import _CappedSortedChooser, run_oracle, run_playout

GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"


def test_chooser_rejects_pick_from_empty_pool() -> None:
    chooser = _CappedSortedChooser(cap=10)
    with pytest.raises(AssertionError, match="playout invariant violated"):
        chooser(0, [], 1)


def test_chooser_rejects_oversized_pick_from_nonempty_pool() -> None:
    # The runtime chooser's full contract (cardlang/runtime/chooser.py raises
    # on n > len(candidates)), not just the empty-pool special case: a
    # harness chooser that quietly truncated to the short prefix would let a
    # mutant PROCEED where the real runtime errors, masking the exact
    # accepted-then-crashes-at-playout class T3 pins.
    chooser = _CappedSortedChooser(cap=10)
    with pytest.raises(AssertionError, match="playout invariant violated"):
        chooser(0, ["only-one"], 2)


def test_chooser_allows_exact_and_undersized_picks() -> None:
    chooser = _CappedSortedChooser(cap=10)
    assert chooser(0, ["b", "a"], 2) == ["a", "b"]  # sorted, deterministic
    assert chooser(0, ["b", "a"], 1) == ["a"]
    assert chooser(0, [], 0) == []  # k=0 from empty is legal, as in the runtime


def test_run_oracle_rejects_syntax_error() -> None:
    outcome = run_oracle("this is not cardlang at all {{{", "bad")
    assert outcome.kind == "rejected"
    assert isinstance(outcome.diagnostic, DiagnosticError)
    assert outcome.game is None


def test_run_oracle_rejects_missing_winner_or_loser() -> None:
    # A proper DiagnosticError from resolve — this case demonstrates the
    # oracle's EXPECTED branch: "rejected" is not itself a finding.
    text = (
        "game NoWinnerOrLoser {\n"
        "  players: 2\n"
        "  max_length: 10\n"
        "  cards: standard52\n"
        "  zones { deck : Deck\n hand[player] : Hand<player> }\n"
        "  phase play { deal 3 cards from deck to each hand }\n"
        "}\n"
    )
    outcome = run_oracle(text, "no-winner-or-loser")
    assert outcome.kind == "rejected"
    assert isinstance(outcome.diagnostic, DiagnosticError)
    assert outcome.game is None


def test_run_oracle_passes_a_real_corpus_game() -> None:
    path = GAMES_DIR / "gops.cardlang"
    outcome = run_oracle(path.read_text(), str(path))
    assert outcome.kind == "passed"
    assert outcome.game is not None


def test_run_playout_terminates_or_cuts_off_cleanly_on_corpus_games() -> None:
    for name in ("gops.cardlang", "big-two.cardlang", "getaway.cardlang"):
        path = GAMES_DIR / name
        outcome = run_oracle(path.read_text(), str(path))
        assert outcome.kind == "passed", f"{name}: {outcome.summary()}"
        assert outcome.game is not None
        for seed in range(3):
            playout = run_playout(outcome.game, seed=seed)
            assert playout.kind in ("terminated", "cutoff"), (
                f"{name} seed={seed}: {playout.summary()}"
            )
