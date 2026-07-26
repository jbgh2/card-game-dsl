"""Random-playout harness for Oh Hell.

Oh Hell adds variable hand size (10 down to 1, then back to 10 — 19 hands), a
per-hand trump turned up from the deck, and an exact-bid bonus. The trump check
recomputes each trick's winner against the hand's trump suit (read from the
trick_end trace), so a wrong outcome function or a mis-threaded per-hand trump
turns the test red.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

OH_HELL = Path(__file__).parent.parent / "docs" / "games" / "oh-hell.cardlang"

# Hand sizes 10,9,...,1,2,...,10 sum to 109 tricks across a whole game.
TOTAL_TRICKS = sum(range(10, 0, -1)) + sum(range(2, 11))


def _oh_hell() -> Any:
    return check_source(OH_HELL)


def _expected_winner(group: list[tuple[int, Card]], trump: str) -> int:
    led = group[0][1].suit
    trumps = [(p, c) for p, c in group if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: pc[1].rank_order)[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: pc[1].rank_order)[0]


def test_100_random_games_satisfy_invariants() -> None:
    game = _oh_hell()
    for seed in range(100):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        trumps: list[str] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "trick_end":
                trumps.append(data["trump"])  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        assert result.hands_played == 19
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])

        # Conservation: 52 cards survive; no hand holds cards at the end.
        assert census["total"] == 52, f"seed {seed}: census {census}"
        assert census["hands_with_cards"] == 0

        # Total tricks over the whole game is fixed by the hand-size sequence.
        assert len(tricks) == TOTAL_TRICKS
        assert len(plays) == 4 * len(tricks)
        assert len(trumps) == len(tricks)

        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _expected_winner(group, trumps[i]), f"seed {seed}, trick {i}"
