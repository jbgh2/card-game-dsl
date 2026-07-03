"""Random-playout harness for French Tarot.

Tarot is the corpus's first non-uniform deck (78 cards: four 14-card suits, 21
atouts, the Excuse). Falsifiable invariants: card conservation (78 cards), a
fixed 36 hands, per-trick winner correctness (highest atout wins, else highest
of the led suit, and the Excuse never wins), and the zero-sum bouts/multiplier
settlement — recomputed independently per hand from the driver's own
`hand_end` cumulative-score snapshots (never a mechanic-internal trace): each
hand's delta is either all-zero (thrown in) or {+3x, -x, -x, -x} for some
taker and per-opponent amount x.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

TAROT = Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"
_SUIT_STR = {"K": 14, "Q": 13, "C": 12, "J": 11}


def _tarot() -> Any:
    return check_source(TAROT)


def _suit_strength(c: Card) -> int:
    return _SUIT_STR.get(c.rank, 0) or int(c.rank)


def _winner(group: list[tuple[int, Card]]) -> int:
    atouts = [(p, c) for p, c in group if c.suit == "atouts"]
    if atouts:
        return max(atouts, key=lambda pc: int(pc[1].rank))[0]
    led = next(c.suit for _, c in group if c.suit != "excuse")
    of_led = [(p, c) for p, c in group if c.suit == led]
    return max(of_led, key=lambda pc: _suit_strength(pc[1]))[0]


def test_40_random_games_satisfy_invariants() -> None:
    game = _tarot()
    for seed in range(40):
        plays: list[tuple[int, Card]] = []
        tricks: list[tuple[int, list[Card]]] = []
        hand_ends = 0
        hand_end_scores: list[dict[int, int]] = []
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            nonlocal hand_ends
            if event == "play":
                plays.append(data)
            elif event == "trick":
                tricks.append(data)
            elif event == "hand_end":
                hand_ends += 1
                hand_end_scores.append(dict(data))
            elif event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed), tracer)

        assert hand_ends == 36
        assert sum(result.scores.values()) == 0  # zero-sum
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])
        assert census["total"] == 78, f"seed {seed}: {census}"

        # Independent per-hand settlement recompute, from the driver's own
        # cumulative `hand_end` snapshots (dict(score) after each hand) — never
        # a mechanic-internal trace. Each hand's delta is either all-zero (a
        # thrown-in hand skips scoring entirely) or the zero-sum {3d, -d, -d,
        # -d} shape for some taker and per-opponent amount `d` — `d` may be
        # NEGATIVE (the taker misses the bid: the taker pays 3x and each
        # opponent collects x, sign-flipped from the taker-succeeds case), so
        # this does not presuppose which side gains.
        prev = {p: 0 for p in range(4)}
        for hand_no, snapshot in enumerate(hand_end_scores):
            delta = {p: snapshot[p] - prev[p] for p in range(4)}
            prev = snapshot
            if all(d == 0 for d in delta.values()):
                continue
            counts: dict[int, int] = {}
            for d in delta.values():
                counts[d] = counts.get(d, 0) + 1
            shared = [d for d, c in counts.items() if c == 3]
            assert len(shared) == 1, (seed, hand_no, delta)
            per_opp = shared[0]
            taker = next(p for p, d in delta.items() if d != per_opp)
            assert delta[taker] == -3 * per_opp, (seed, hand_no, delta)

        assert len(plays) == 4 * len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _winner(group), f"seed {seed} trick {i}"
            # The Excuse never wins a trick.
            won_card = next(c for p, c in group if p == winner)
            assert won_card.suit != "excuse"
