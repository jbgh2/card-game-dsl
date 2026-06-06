"""Random-playout harness for Skat.

Skat has three trump structures: Suit (four jacks + the trump suit), Grand (four
jacks only), and Null (no trumps, a distinct A-K-Q-J-10-9-8-7 order). The
falsifiable check recomputes every trick's winner from the cards played and the
contract type recorded in the trace, so a wrong jack-ordering, trump structure,
or rank order turns it red. Plus deck integrity (32 cards / 120 card points) and
a fixed 36-hand game with the highest score winning.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

SKAT = Path(__file__).parent.parent / "docs" / "games" / "skat.cardlang"

_SKAT_RANK = {"A": 7, "10": 6, "K": 5, "Q": 4, "9": 3, "8": 2, "7": 1}
_NULL_RANK = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
_JACK = {"clubs": 4, "spades": 3, "hearts": 2, "diamonds": 1}


def _skat() -> Any:
    return check_source(SKAT)


def _is_trump(c: Card, gt: str, trump: str | None) -> bool:
    return gt != "null" and (c.rank == "J" or (gt == "suit" and c.suit == trump))


def _winner(group: list[tuple[int, Card]], gt: str, trump: str | None) -> int:
    led = group[0][1].suit
    if gt == "null":
        of_led = [(p, c) for p, c in group if c.suit == led]
        return max(of_led, key=lambda pc: _NULL_RANK[pc[1].rank])[0]
    trumps = [(p, c) for p, c in group if _is_trump(c, gt, trump)]
    if trumps:
        return max(
            trumps,
            key=lambda pc: 100 + _JACK[pc[1].suit] if pc[1].rank == "J" else _SKAT_RANK[pc[1].rank],
        )[0]
    of_led = [(p, c) for p, c in group if c.suit == led and not _is_trump(c, gt, trump)]
    return max(of_led, key=lambda pc: _SKAT_RANK[pc[1].rank])[0]


def test_50_random_games_satisfy_invariants() -> None:
    game = _skat()
    for seed in range(50):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        contracts: list[tuple[str, str | None]] = []
        hand_ends = 0
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            nonlocal hand_ends
            if event == "play":
                plays.append(data)
            elif event == "trick":
                tricks.append(data)
            elif event == "trick_end":
                contracts.append((data["game_type"], data["trump"]))
            elif event == "hand_end":
                hand_ends += 1
            elif event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed), tracer)

        assert hand_ends == 36  # fixed 36-hand game
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])

        # Deck integrity.
        assert census["total"] == 32, f"seed {seed}: {census}"
        assert census["total_value"] == 120, f"seed {seed}: {census}"

        # Three plays per trick; winner correct under the contract's trumps.
        assert len(plays) == 3 * len(tricks)
        assert len(contracts) == len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 3 : (i + 1) * 3]
            assert {p for p, _ in group} == {0, 1, 2}
            gt, trump = contracts[i]
            assert winner == _winner(group, gt, trump), f"seed {seed} trick {i} ({gt})"
