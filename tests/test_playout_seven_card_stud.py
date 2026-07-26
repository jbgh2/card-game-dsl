"""Seven-Card Stud: poker-evaluator unit tests plus a random playout.

The strongest falsifiable checks for a betting game: the poker hand evaluator
against known orderings/tiebreakers, and chip conservation (total chips never
change — the test of the betting and side-pot logic). The playout also checks
card conservation and that the game terminates with one player holding all the
chips.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.stud import hand_rank
from cardlang.runtime.values import Card

STUD = Path(__file__).parent.parent / "docs" / "games" / "seven-card-stud.cardlang"


def _h(*specs: str) -> list[Card]:
    suit = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}
    return [Card(s[:-1], suit[s[-1]]) for s in specs]


def test_hand_evaluator_category_order() -> None:
    sf = hand_rank(_h("AS", "KS", "QS", "JS", "10S", "2D", "3C"))  # royal flush
    quads = hand_rank(_h("9S", "9D", "9H", "9C", "KS", "2D", "3C"))
    boat = hand_rank(_h("9S", "9D", "9H", "KC", "KS", "2D", "3C"))
    flush = hand_rank(_h("AS", "JS", "8S", "5S", "2S", "KD", "3C"))
    straight = hand_rank(_h("9S", "8D", "7H", "6C", "5S", "KD", "2C"))
    trips = hand_rank(_h("9S", "9D", "9H", "KC", "5S", "2D", "3C"))
    two_pair = hand_rank(_h("9S", "9D", "KH", "KC", "5S", "2D", "3C"))
    pair = hand_rank(_h("9S", "9D", "KH", "QC", "5S", "2D", "3C"))
    high = hand_rank(_h("AS", "JD", "9H", "7C", "5S", "3D", "2C"))
    ordered = [high, pair, two_pair, trips, straight, flush, boat, quads, sf]
    assert ordered == sorted(ordered)  # strictly increasing strength

    # The wheel A-2-3-4-5 is a straight (the five-high).
    wheel = hand_rank(_h("AS", "2D", "3H", "4C", "5S", "KD", "QC"))
    assert wheel[0] == 4 and wheel[1] == 5
    # Tiebreak: higher kicker wins within a category.
    assert hand_rank(_h("AS", "AD", "KH", "5C", "3S", "2D", "7C")) > hand_rank(
        _h("AS", "AD", "QH", "5C", "3S", "2D", "7C")
    )


def test_15_random_games_satisfy_invariants() -> None:
    game = check_source(STUD)
    start = time.monotonic()
    for seed in range(15):
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Chip conservation: 4 players × 100 starting chips, always.
        assert sum(result.scores.values()) == 400, f"seed {seed}: {result.scores}"
        # Terminates with at most one player holding chips; winner holds them all.
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1, f"seed {seed}: {result.scores}"
        assert result.winner == with_chips[0]
        assert result.scores[result.winner] == 400
        # Card conservation.
        assert census["total"] == 52, f"seed {seed}: {census}"
    assert time.monotonic() - start < 60  # stays comfortably fast
