"""Random-playout harness for French Tarot.

Tarot is the corpus's first non-uniform deck (78 cards: four 14-card suits, 21
atouts, the Excuse). Falsifiable invariants: card conservation (78 cards), the
card-point total (182 doubled units = 91 real, split between taker and
opponents), the zero-sum score (the taker collects exactly what the three
opponents pay), a fixed 36 hands, and per-trick winner correctness — highest
atout wins, else highest of the led suit, and the Excuse never wins.
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
        bad_total = 0
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            nonlocal hand_ends, bad_total
            if event == "play":
                plays.append(data)
            elif event == "trick":
                tricks.append(data)
            elif event == "hand_end":
                hand_ends += 1
            elif event == "tarot_hand":
                if data["taker_doubled"] + data["opp_doubled"] != 182:
                    bad_total += 1
            elif event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed), tracer)

        assert hand_ends == 36
        assert bad_total == 0  # card points always total 182 doubled units
        assert sum(result.scores.values()) == 0  # zero-sum
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])
        assert census["total"] == 78, f"seed {seed}: {census}"

        assert len(plays) == 4 * len(tricks)
        for i, (winner, cards) in enumerate(tricks):
            group = plays[i * 4 : (i + 1) * 4]
            assert {p for p, _ in group} == {0, 1, 2, 3}
            assert winner == _winner(group), f"seed {seed} trick {i}"
            # The Excuse never wins a trick.
            won_card = next(c for p, c in group if p == winner)
            assert won_card.suit != "excuse"
