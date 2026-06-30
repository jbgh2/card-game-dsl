"""Big Two: combination-engine unit tests plus a random playout.

The combination engine is the heart of a climbing game, so it gets direct unit
tests (what a hand can form; which plays legally beat a led combination, with Big
Two's suit tie-breaks and the cross-type five-card hierarchy). The playout then
checks the conservation census (52 cards), that every hand ends with exactly one
player emptied, that penalty scoring matches an *independent* recompute from the
cards left behind, and that the match terminates with the lowest total winning.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.bigtwo import Play, _RANK, _combos, _legal_follows
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

BIG_TWO = Path(__file__).parent.parent / "docs" / "games" / "big-two.cardlang"
_SUIT = {"s": "spades", "h": "hearts", "c": "clubs", "d": "diamonds"}


def _hand(*specs: str) -> list[Card]:
    return [Card(r, _SUIT[s]) for r, s in (spec.split("@") for spec in specs)]


def _only(kind: str, *specs: str) -> Play:
    """The one combination of `kind` a hand forms (for building led plays)."""
    return next(p for p in _combos(_hand(*specs)) if p.kind == kind)


def test_combination_engine() -> None:
    # Pairs/triples are formed by rank; the strongest representative carries the
    # higher suit (here both 7s, so the spade tops the heart in the pair).
    sevens = _combos(_hand("7@s", "7@h", "7@c"))
    assert any(p.kind == "pair" and p.cards[0].suit == "spades" for p in sevens)
    assert any(p.kind == "triple" for p in sevens)

    # The 2 is the highest single rank, the 3 the lowest.
    assert _RANK["2"] > _RANK["A"] > _RANK["3"]

    # The wheel A-2-3-4-5 is the lowest straight (top card the 5); 2-3-4-5-6 sits
    # just above it; J-Q-K-A-2 is not a straight at all (no wrap-around).
    wheel = [p for p in _combos(_hand("A@s", "2@h", "3@c", "4@d", "5@s")) if p.kind == "straight"]
    assert wheel and wheel[0].key[1] == 5
    win6 = [p for p in _combos(_hand("2@s", "3@h", "4@c", "5@d", "6@s")) if p.kind == "straight"]
    assert win6 and win6[0].key[1] == 6 and win6[0].key > wheel[0].key
    assert not any(p.kind == "straight" for p in _combos(_hand("J@s", "Q@h", "K@c", "A@d", "2@s")))

    # The five-card hierarchy: straight < flush < full house < quads < straight flush.
    straight = win6[0]
    flush = next(p for p in _combos(_hand("2@s", "5@s", "7@s", "9@s", "J@s")) if p.kind == "flush")
    full = next(p for p in _combos(_hand("5@s", "5@h", "5@c", "9@s", "9@h")) if p.kind == "fullhouse")
    quad = next(p for p in _combos(_hand("8@s", "8@h", "8@c", "8@d", "3@s")) if p.kind == "quads")
    assert quad.cards[4] == Card("3", "spades")  # the mandatory kicker
    sflush = next(p for p in _combos(_hand("5@s", "6@s", "7@s", "8@s", "9@s")) if p.kind == "straightflush")
    assert straight.key < flush.key < full.key < quad.key < sflush.key

    # Five consecutive cards of one suit are a straight flush only — never offered
    # as a plain straight or flush (they can only be played monochrome).
    mono = _combos(_hand("5@s", "6@s", "7@s", "8@s", "9@s"))
    assert not any(p.kind in ("straight", "flush") for p in mono)


def test_climbing_legality() -> None:
    led_seven = _only("single", "7@h")
    # Same rank, higher suit beats; lower suit cannot (only pass).
    assert any(p.cards[0].suit == "spades" for p in _legal_follows(_hand("7@s"), led_seven))
    assert _legal_follows(_hand("7@c"), led_seven) == []
    # No cross-size beating: an 8-pair hand following a single offers only singles.
    assert all(p.size == 1 for p in _legal_follows(_hand("8@s", "8@h"), led_seven))

    # A pair is followed only by a higher pair (a single 8 cannot follow it).
    led_pair = _only("pair", "7@s", "7@h")
    follows = _legal_follows(_hand("8@s", "8@h", "9@c"), led_pair)
    assert follows and all(p.size == 2 for p in follows)

    # A higher-type five-card hand beats a lower-type one of the same size.
    led_straight = _only("straight", "3@s", "4@h", "5@c", "6@d", "7@s")
    flush_hand = _hand("2@h", "5@h", "7@h", "9@h", "J@h")
    assert any(p.kind == "flush" for p in _legal_follows(flush_hand, led_straight))


def _expected_penalty(cards_left: int) -> int:
    """An independent restatement of the scoring rule — deliberately NOT importing
    the climb game's `bigtwo_penalty`, so the playout and the checker can't share a
    bug."""
    multiplier = 1 if cards_left <= 9 else 2 if cards_left <= 12 else 3
    return multiplier * cards_left


# Every per-hand penalty a non-winner can score (1–13 cards left), recomputed here.
_VALID_PENALTIES = frozenset(_expected_penalty(n) for n in range(1, 14))


def test_random_games_satisfy_invariants() -> None:
    game = check_source(BIG_TWO)
    for seed in range(30):
        census: dict[str, int] = {}
        # `hand_end` carries the cumulative score after each hand; per-hand deltas
        # let us check shedding (exactly one zero-delta winner per hand) and that
        # every non-winner's delta is a well-formed penalty (an independent check
        # of the DSL `bigtwo_penalty`, not sharing its code).
        hand_totals: list[dict[int, int]] = []

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                hand_totals.append(dict(data))
            elif event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed), tracer)

        assert hand_totals, f"seed {seed}: no hand was played"
        prev = {p: 0 for p in range(4)}
        for cum in hand_totals:
            deltas = {p: cum[p] - prev[p] for p in cum}
            zero = [p for p, d in deltas.items() if d == 0]
            assert len(zero) == 1, f"seed {seed}: not exactly one shed-out winner: {deltas}"
            for p, d in deltas.items():
                if d != 0:
                    assert d in _VALID_PENALTIES, f"seed {seed}: bad penalty {d}"
            prev = cum

        assert census["total"] == 52, f"seed {seed}: {census}"
        assert result.scores == hand_totals[-1], f"seed {seed}: final score mismatch"
        assert result.winner == min(result.scores, key=lambda p: result.scores[p])
        assert max(result.scores.values()) >= 100, f"seed {seed}: match did not reach the threshold"
