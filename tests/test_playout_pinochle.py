"""Random-playout harness for Pinochle.

Pinochle is the corpus's first auction + melding game, on the 48-card double
pack (A 10 K Q J 9). Falsifiable invariants: card/value conservation (48 cards,
240 counter points), per-trick winner correctness against the pinochle rank
order and trump, and trick-point reconciliation — every hand that is actually
played out distributes exactly 250 trick points (240 in counters + 10 for the
last trick). A wrong rank order, value table, or last-trick award turns these red.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

PINOCHLE = Path(__file__).parent.parent / "docs" / "games" / "pinochle.cardlang"

# pinochle48 strength, low to high: 9 J Q K 10 A.
RANK = {r: i for i, r in enumerate(("9", "J", "Q", "K", "10", "A"))}


def _pinochle() -> Any:
    return check_source(PINOCHLE)


def _expected_winner(group: list[tuple[int, Card]], trump: str) -> int:
    led = group[0][1].suit
    trumps = [(p, c) for p, c in group if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: RANK[pc[1].rank])[0]
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: RANK[pc[1].rank])[0]


def test_150_random_games_satisfy_invariants() -> None:
    game = _pinochle()
    for seed in range(150):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        trumps: list[str] = []
        hand_results: list[dict[str, Any]] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "play":
                plays.append(data)
            elif event == "trick":
                tricks.append(data)
            elif event == "trick_end":
                trumps.append(data["trump"])
            elif event == "pinochle_hand":
                hand_results.append(data)
            elif event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed), tracer)

        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert max(result.scores.values()) >= 150

        # Card and counter-value conservation.
        assert census["total"] == 48, f"seed {seed}: {census}"
        assert census["total_value"] == 240, f"seed {seed}: {census}"

        # Four plays per trick; winner correct against rank order and trump.
        assert len(plays) == 4 * len(tricks)
        assert len(trumps) == len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _expected_winner(group, trumps[i]), f"seed {seed} trick {i}"

        # Every played-out hand distributes exactly 250 trick points, and meld
        # is never negative.
        for h in hand_results:
            assert sum(h["trick"].values()) == 250, f"seed {seed}: {h}"
            assert all(m >= 0 for m in h["meld"].values())
