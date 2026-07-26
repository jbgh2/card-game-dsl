"""Random-playout harness for Bridge (rubber, simplified).

Bridge reuses the ordinary Trick engine (its play needs only follow-suit) but
adds a real auction (ascending bids over C D H S NT, double/redouble) and rubber
scoring. Falsifiable invariants: card conservation, per-trick winner correctness
against the contract's trump (none for a no-trump contract), termination (the
rubber loop only exits when a side reaches two games), and the winner being the
side with the higher total. Random bids are capped at level 3, so rubbers are a
realistic dozen-odd hands rather than hundreds.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"


def _bridge() -> Any:
    return check_source(BRIDGE)


def _expected_winner(group: list[tuple[int, Card]], trump: str | None) -> int:
    led = group[0][1].suit
    if trump is not None:
        trumps = [(p, c) for p, c in group if c.suit == trump]
        if trumps:
            return max(trumps, key=lambda pc: pc[1].rank_order)[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: pc[1].rank_order)[0]


def test_40_random_rubbers_satisfy_invariants() -> None:
    game = _bridge()
    for seed in range(40):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        trumps: list[str | None] = []
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

        # Terminated with a winner who has the higher total.
        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert census["total"] == 52, f"seed {seed}: {census}"

        # Played hands are 13 tricks of four plays; all-pass hands add none.
        assert len(plays) == 4 * len(tricks)
        assert len(trumps) == len(tricks)
        assert len(tricks) % 13 == 0  # every played hand contributes exactly 13

        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _expected_winner(group, trumps[i]), f"seed {seed} trick {i}"
