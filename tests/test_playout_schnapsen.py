"""Random-playout harness for Schnapsen.

Schnapsen is the first game with heterogeneous lead moves and a non-standard
deck (schnapsen20, A 10 K Q J). The invariants that would go red under a real
bug: card-point integrity (the deck holds exactly 120 points — catches a wrong
value table or a lost card), per-trick winner correctness against the
schnapsen20 rank order *and* trump (catches the rank-order landmine for a
non-standard deck), and that every hand awards game points (settlement fires).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

SCHNAPSEN = Path(__file__).parent.parent / "docs" / "games" / "schnapsen.cardlang"

# schnapsen20 strength, high to low: A 10 K Q J.
RANK = {r: i for i, r in enumerate(("J", "Q", "K", "10", "A"))}


def _schnapsen() -> Any:
    return check_source(SCHNAPSEN)


def _expected_winner(group: list[tuple[int, Card]], trump: str) -> int:
    led = group[0][1].suit
    trumps = [(p, c) for p, c in group if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: RANK[pc[1].rank])[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: RANK[pc[1].rank])[0]


def test_200_random_games_satisfy_invariants() -> None:
    game = _schnapsen()
    for seed in range(200):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        trumps: list[str] = []
        score_sums: list[int] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick_end":
                trumps.append(data["trump"])  # noqa: B023 -- consumed before the loop advances
            elif event == "hand_end":
                score_sums.append(sum(data.values()))  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Terminates with a winner who reached 0 (or below); winner is lowest.
        assert result.winner == min(result.scores, key=lambda p: result.scores[p])
        assert result.scores[result.winner] <= 0

        # Deck integrity: 20 cards, exactly 120 card points, across all zones.
        assert census["total"] == 20, f"seed {seed}: {census}"
        assert census["total_value"] == 120, f"seed {seed}: {census}"

        # Two plays per trick; winner correct against rank order and trump.
        assert len(plays) == 2 * len(tricks)
        assert len(trumps) == len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 2 : (i + 1) * 2]
            assert winner == _expected_winner(group, trumps[i]), f"seed {seed} trick {i}"

        # Every hand settles to someone's cost: the total game score strictly
        # falls hand over hand (game points are always awarded).
        assert len(score_sums) == result.hands_played
        for a, b in zip([14, *score_sums], score_sums):  # 7 + 7 at the start
            assert b < a, f"seed {seed}: game score did not fall ({a} -> {b})"
