"""Tichu: combination-engine unit tests plus a random playout.

The combination engine is the heart of a climbing game, so it gets direct unit
tests (what a hand can form; which plays legally beat a led combination). The
playout then checks card conservation (56), that non-double-victory hands always
distribute exactly 100 card points (Dragon +25 / Phoenix -25 net out against the
40+40+20 from kings/tens/fives), and termination with the higher team winning.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.combinations import Play, _combos, _legal_follows
from cardlang.runtime.values import Card

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"
SUITS = ("clubs", "diamonds", "hearts", "spades")


def _hand(*specs: str) -> list[Card]:
    out = []
    for s in specs:
        rank, suit = s.split("@") if "@" in s else (s, "clubs")
        out.append(Card(rank, suit))
    return out


def test_combination_engine() -> None:
    quads = _hand("7@clubs", "7@diamonds", "7@hearts", "7@spades")
    kinds = {p.kind for p in _combos(quads)}
    assert "bomb" in kinds and "pair" in kinds and "triple" in kinds

    straight = _hand("5@clubs", "6@diamonds", "7@hearts", "8@spades", "9@clubs")
    assert any(p.kind == "straight" and p.length == 5 for p in _combos(straight))

    full = _hand("5@clubs", "5@diamonds", "5@hearts", "9@clubs", "9@diamonds")
    assert any(p.kind == "fullhouse" for p in _combos(full))

    twopairs = _hand("5@clubs", "5@diamonds", "6@hearts", "6@spades")
    assert any(p.kind == "pairseq" and p.length == 2 for p in _combos(twopairs))


def test_climbing_legality() -> None:
    led_eight = Play("single", 1, 8, (Card("8", "clubs"),))
    # A nine beats the eight; a seven cannot (only pass).
    assert any(p.key > 8 for p in _legal_follows(_hand("9@clubs"), led_eight))
    assert _legal_follows(_hand("7@clubs"), led_eight) == []
    # A bomb beats a single.
    bomb = _hand("3@clubs", "3@diamonds", "3@hearts", "3@spades")
    assert any(p.is_bomb for p in _legal_follows(bomb, led_eight))
    # Phoenix beats a single (but never the Dragon).
    assert any(p.cards[0].rank == "Phoenix" for p in _legal_follows(_hand("Phoenix@special"), led_eight))
    led_dragon = Play("single", 1, 15, (Card("Dragon", "special"),))
    assert _legal_follows(_hand("Phoenix@special"), led_dragon) == []


def test_30_random_games_satisfy_invariants() -> None:
    game = check_source(TICHU)
    for seed in range(30):
        bad_points = 0
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            nonlocal bad_points
            if event == "tichu_hand":
                if not data["double_victory"] and data["card_points"] != 100:
                    bad_points += 1
            elif event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed), tracer)

        assert bad_points == 0, f"seed {seed}: a hand miscounted card points"
        assert census["total"] == 56, f"seed {seed}: {census}"
        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert max(result.scores.values()) >= 1000
