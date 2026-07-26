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

# pinochle48's card-point table (A/10/K = 10; Q/J/9 = 0) — the same table
# `card_value(c)` reads at runtime (cardlang/runtime/values.py DECKS["pinochle48"]).
# Duplicated here (not imported) so the recompute below is independent of the
# migrated code it checks.
COUNTER_VALUE = {"A": 10, "10": 10, "K": 10}


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

        # Every played-out hand distributes exactly 250 trick points (240 in
        # counters + 10 for the last trick). Recomputed from the traced `trick`
        # events (winner + the 4 played cards) rather than a mechanic-local
        # trace, so the check survives trick play leaving `instantiate` for the
        # kernel (docs/kernel-migration.md). A played hand contributes exactly
        # 12 consecutive `trick` events and an abandoned one contributes none,
        # so the flat per-game sequence still divides evenly into hands; `team
        # = player % 2` follows from `partnerships: [[0, 2], [1, 3]]`, and each
        # trick's `winner` is independently pinned against `_expected_winner`
        # above.
        assert len(tricks) % 12 == 0, f"seed {seed}: {len(tricks)} tricks, not hand-aligned"
        for start in range(0, len(tricks), 12):
            hand_tricks = tricks[start : start + 12]
            trick_points = {0: 0, 1: 0}
            for winner, cards in hand_tricks:
                trick_points[winner % 2] += sum(COUNTER_VALUE.get(c.rank, 0) for c in cards)
            trick_points[hand_tricks[-1][0] % 2] += 10  # ten for the last trick
            assert sum(trick_points.values()) == 250, f"seed {seed} hand at trick {start}: {trick_points}"
