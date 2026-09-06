"""Cribbage: unit tests for the show scorers (known hands) plus a random playout.

A counting game has no card-conservation point total, so the strongest
falsifiable check is the combination scorer against hands whose values are
famous/known (the 29-hand, runs with multiplicity, flushes, his nob). The
playout then checks termination, that exactly one player crosses 121, and that
the winner is that player.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.cribbage import (
    count_fifteens,
    flush_score,
    nob_score,
    peg_pairs,
    peg_run,
    run_score,
    show_score,
)
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, expand_ranking_convention

CRIBBAGE = Path(__file__).parent.parent / "docs" / "games" / "cribbage.cardlang"

# The declared `ranking: aces low`'s rank_index, derived through the same
# expansion the resolver uses (never a private copy of the order).
_ORDER = {
    r: i
    for i, r in enumerate(reversed(expand_ranking_convention("aces low", "standard52")))
}



def _c(spec: str) -> Card:
    rank, suit = spec[:-1], {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[spec[-1]]
    return Card(rank, suit)


def test_show_scorer_known_hands() -> None:
    # The perfect 29: J + three fives matching the starter's suit on the J.
    assert show_score([_c("5C"), _c("5D"), _c("5S"), _c("JH")], _c("5H"), False, _ORDER, "cribbage_show_value") == 29
    # Run of five plus two fifteens (7+8, 4+5+6).
    assert show_score([_c("4C"), _c("5D"), _c("6S"), _c("7H")], _c("8C"), False, _ORDER, "cribbage_show_value") == 9
    # Double run of three (4 5 5 6) + pair + two fifteens.
    assert run_score([_c("4C"), _c("5D"), _c("5S"), _c("6H"), _c("9C")], _ORDER, "cribbage_show_value") == 6
    # Fifteens: K + 5 = 15.
    assert count_fifteens([_c("KC"), _c("5D")]) == 2
    # Flush: four of a suit scores 4 in hand, 5 with matching starter, 5-only in crib.
    assert flush_score([_c("2C"), _c("5C"), _c("8C"), _c("JC")], _c("9D"), False) == 4
    assert flush_score([_c("2C"), _c("5C"), _c("8C"), _c("JC")], _c("9C"), False) == 5
    assert flush_score([_c("2C"), _c("5C"), _c("8C"), _c("JC")], _c("9D"), True) == 0
    # His nob: J of the starter's suit in hand.
    assert nob_score([_c("JC"), _c("2D"), _c("3S"), _c("4H")], _c("9C")) == 1
    assert nob_score([_c("JC"), _c("2D"), _c("3S"), _c("4H")], _c("9D")) == 0


def test_pegging_scorers() -> None:
    assert peg_pairs([_c("7C"), _c("7D")]) == 2  # a pair
    assert peg_pairs([_c("7C"), _c("7D"), _c("7S")]) == 6  # pair royal
    assert peg_run([_c("4C"), _c("6D"), _c("5S")], _ORDER) == 3  # run regardless of order
    assert peg_run([_c("9C"), _c("4D"), _c("6S"), _c("5H")], _ORDER) == 3  # only the suffix


def test_50_random_games_satisfy_invariants() -> None:
    game = check_source(CRIBBAGE)
    for seed in range(50):
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        crossed = [p for p, s in result.scores.items() if s >= 121]
        assert len(crossed) == 1, f"seed {seed}: {result.scores}"  # exactly one winner
        assert result.winner == crossed[0]
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])
        assert census["total"] == 52, f"seed {seed}: {census}"
