"""Random-playout harness for Spades.

Spades is the first team trump game on the runtime. Its invariants
exercise the seams Hearts/Getaway never touched: a value (integer-bid) decision,
a trump-aware trick winner, and team-indexed capture/scoring. The trump check is
the one that would go red under a wrong outcome function — it recomputes each
trick's winner from the cards played and compares against what the runtime chose.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

SPADES = Path(__file__).parent.parent / "docs" / "games" / "spades.cardlang"


def _spades() -> Any:
    return check_source(SPADES)


def _expected_winner(group: list[tuple[int, Card]]) -> int:
    """The trick winner under Spades rules: highest spade if any spade was
    played, otherwise the highest card of the led suit."""
    led = group[0][1].suit
    spades = [(p, c) for p, c in group if c.suit == "spades"]
    if spades:
        return max(spades, key=lambda pc: pc[1].rank_order)[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: pc[1].rank_order)[0]


def test_200_random_games_satisfy_invariants() -> None:
    game = _spades()
    for seed in range(200):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Terminates at a real threshold, and the winner is the top-scoring team.
        assert result.winner in (0, 1)
        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert max(result.scores.values()) >= 500 or min(result.scores.values()) <= -200

        # Conservation: all 52 cards still exist; no hand holds cards at the end.
        assert census["total"] == 52, f"seed {seed}: census {census}"
        assert census["hands_with_cards"] == 0

        # 13 tricks per hand, four plays per trick.
        assert len(tricks) == 13 * result.hands_played
        assert len(plays) == 4 * len(tricks)

        # Trump resolution: every trick was won by the right player.
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert len(group) == 4
            assert {p for p, _ in group} == {0, 1, 2, 3}  # all four play once
            assert winner == _expected_winner(group), f"seed {seed}, trick {i}"
            assert [c for _, c in group] == cards
