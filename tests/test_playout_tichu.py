"""Tichu: combination-engine unit tests plus a policy-driven playout.

The combination engine is the heart of a climbing game, so it gets direct unit
tests (what a hand can form; which plays legally beat a led combination). The
playout then checks card conservation (56), that non-double-victory hands always
distribute exactly 100 card points (Dragon +25 / Phoenix -25 net out against the
40+40+20 from kings/tens/fives), and termination with the higher team winning.

The playout drives the call windows through a REFERENCE POLICY, not the uniform
chooser: a uniform chooser calls tichu at ~50% of every offer, a random call is
worth about -50 in expectation, and the 1000-point race then diverges —
measured at 2,200+ hands with no terminus. That divergence is real Tichu (a
table of indiscriminate callers never finishes; recorded as the second witness
in open-questions/unbounded-lines-and-max-length.md), so the game text stays
faithful and the play-style assumption lives here: grand tichu gated at 4% per
offer, small tichu at 2% per poll offer (approximating the pre-WS5 per-hand
call profile), uniform otherwise.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.combinations import Play, _combos, _legal_follows
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Player
from tests.playout_trace import TichuHands

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"
SUITS = ("clubs", "diamonds", "hearts", "spades")


def tichu_reference_policy(
    rng: random.Random, stats: dict[str, int] | None = None
) -> Callable[[Player, list[Any], int], list[Any]]:
    """The playout policy: uniform play except at the call windows, which are
    gated at rates approximating the pre-WS5 per-hand call profile."""
    base = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        names = {c[0]: c for c in candidates if isinstance(c, tuple) and c}
        if "call_grand_tichu" in names:
            pick = names["call_grand_tichu"] if rng.random() < 0.04 else names["decline_grand"]
        elif "call_tichu" in names:
            pick = names["call_tichu"] if rng.random() < 0.02 else names["no_call"]
        else:
            return base(player, candidates, n)
        if stats is not None:
            stats[str(pick[0])] = stats.get(str(pick[0]), 0) + 1
        return [pick]

    return chooser


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
    team_of = {
        p: ti for ti, members in enumerate(game.partnerships) for p in members
    }
    calls: dict[str, int] = {}
    for seed in range(30):
        bad_points = 0
        census: dict[str, int] = {}
        log = TichuHands(team_of)

        def tracer(event: str, data: Any, _log: TichuHands = log) -> None:
            nonlocal bad_points
            if event == "hand_end":
                double_victory, card_points = _log.hand_summary()
                if not double_victory and card_points != 100:
                    bad_points += 1
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        rng = random.Random(seed)
        result = play_game(
            game, rng, tracer, tichu_reference_policy(rng, calls), observer=log.observer
        )

        assert bad_points == 0, f"seed {seed}: a hand miscounted card points"
        assert census["total"] == 56, f"seed {seed}: {census}"
        assert result.winner == max(result.scores, key=lambda t: result.scores[t])
        assert max(result.scores.values()) >= 1000

    # The windows are live, not vacuously green: across the suite the policy
    # actually called (and mostly declined) both call types.
    assert calls.get("call_tichu", 0) > 0 and calls.get("call_grand_tichu", 0) > 0, calls
    assert calls.get("no_call", 0) > calls.get("call_tichu", 0), calls
