"""Big Two: the declared plays on hands built for each shape, plus a random playout.

The catalogue and its follows function are the heart of a climbing game, so
they get direct tests on built hands (what a hand can form; which plays
legally beat a led combination, with Big Two's suit tie-breaks and the
cross-type five-card hierarchy); tests/test_bigtwo_combinations.py holds them
to an independent oracle over sampled hands. The playout then checks the
conservation census (52 cards), that every hand ends with exactly one player
emptied, that penalty scoring matches an *independent* recompute from the
cards left behind, and that the match terminates with the lowest total winning.
"""

from __future__ import annotations

import random
from functools import cache
from pathlib import Path
from collections.abc import Callable
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Combination
from tests.test_bigtwo_combinations import _asker

BIG_TWO = Path(__file__).parent.parent / "docs" / "games" / "big-two.cardlang"
_SUIT = {"s": "spades", "h": "hearts", "c": "clubs", "d": "diamonds"}


def _hand(*specs: str) -> list[Card]:
    return [Card(r, _SUIT[s]) for r, s in (spec.split("@") for spec in specs)]


@cache
def _ask() -> Callable[[list[Card], Combination | None], list[Combination]]:
    return _asker(opened=True)


def _combos(hand: list[Card]) -> list[Combination]:
    """Every play a hand may lead."""
    return _ask()(hand, None)


def _legal_follows(hand: list[Card], standing: Combination) -> list[Combination]:
    return _ask()(hand, standing)


def _only(shape: str, *specs: str) -> Combination:
    """The first play of `shape` a hand forms (for building led plays)."""
    return next(p for p in _combos(_hand(*specs)) if p.shape == shape)


def _beats(a: Combination, b: Combination) -> bool:
    return any(p.cards == a.cards for p in _legal_follows(list(a.cards), b))


def test_the_catalogue_on_built_hands() -> None:
    # Pairs/triples are formed by rank, every suit choice offered: three 7s are
    # three pairs and one triple.
    sevens = _combos(_hand("7@s", "7@h", "7@c"))
    assert sum(p.shape == "pair" for p in sevens) == 3
    assert sum(p.shape == "triple" for p in sevens) == 1

    # The 2 is the highest single, the 3 the lowest.
    two, ace, three = (_only("single", spec) for spec in ("2@s", "A@s", "3@s"))
    assert _beats(two, ace) and _beats(ace, three) and not _beats(three, ace)

    # The wheel A-2-3-4-5 is the lowest straight; 2-3-4-5-6 sits just above it;
    # J-Q-K-A-2 is not a straight at all (no wrap-around).
    wheel = _only("straight", "A@s", "2@h", "3@c", "4@d", "5@s")
    win6 = _only("straight", "2@s", "3@h", "4@c", "5@d", "6@s")
    assert _beats(win6, wheel) and not _beats(wheel, win6)
    assert not any(p.shape == "straight" for p in _combos(_hand("J@s", "Q@h", "K@c", "A@d", "2@s")))

    # The five-card hierarchy: straight < flush < full house < quads < straight flush.
    flush = _only("flush", "2@s", "5@s", "7@s", "9@s", "J@s")
    full = _only("full_house", "5@s", "5@h", "5@c", "9@s", "9@h")
    quad = _only("quads", "8@s", "8@h", "8@c", "8@d", "3@s")
    assert Card("3", "spades") in quad.cards  # the mandatory kicker
    sflush = _only("straight_flush", "5@s", "6@s", "7@s", "8@s", "9@s")
    ladder = [win6, flush, full, quad, sflush]
    for low, high in zip(ladder, ladder[1:]):
        assert _beats(high, low) and not _beats(low, high), (low, high)

    # Five consecutive cards of one suit are a straight flush only — never offered
    # as a plain straight or flush (they can only be played monochrome).
    mono = _combos(_hand("5@s", "6@s", "7@s", "8@s", "9@s"))
    assert not any(p.shape in ("straight", "flush") for p in mono)


def test_climbing_legality() -> None:
    led_seven = _only("single", "7@h")
    # Same rank, higher suit beats; lower suit cannot (only pass).
    assert any(p.cards[0].suit == "spades" for p in _legal_follows(_hand("7@s"), led_seven))
    assert _legal_follows(_hand("7@c"), led_seven) == []
    # No cross-size beating: an 8-pair hand following a single offers only singles.
    assert all(len(p.cards) == 1 for p in _legal_follows(_hand("8@s", "8@h"), led_seven))

    # A pair is followed only by a higher pair (a single 8 cannot follow it).
    led_pair = _only("pair", "7@s", "7@h")
    follows = _legal_follows(_hand("8@s", "8@h", "9@c"), led_pair)
    assert follows and all(len(p.cards) == 2 for p in follows)

    # A higher-type five-card hand beats a lower-type one of the same size.
    led_straight = _only("straight", "3@s", "4@h", "5@c", "6@d", "7@s")
    flush_hand = _hand("2@h", "5@h", "7@h", "9@h", "J@h")
    assert any(p.shape == "flush" for p in _legal_follows(flush_hand, led_straight))


def _expected_penalty(cards_left: int) -> int:
    """An independent restatement of the scoring rule — deliberately NOT importing
    the climb game's `bigtwo_penalty`, so the playout and the checker can't share a
    bug."""
    multiplier = 1 if cards_left <= 9 else 2 if cards_left <= 12 else 3
    return multiplier * cards_left


# Every per-hand penalty a non-winner can score (1–13 cards left), recomputed here.
_VALID_PENALTIES = frozenset(_expected_penalty(n) for n in range(1, 14))
# What a liable seat can pay: three losers' penalties at once.
_LIABLE_TOTALS = frozenset(a + b + c for a in _VALID_PENALTIES for b in _VALID_PENALTIES for c in _VALID_PENALTIES)


def test_random_games_satisfy_invariants() -> None:
    game = check_source(BIG_TWO)
    for seed in range(30):
        census: dict[str, int] = {}
        # `hand_end` carries the cumulative score after each hand; per-hand deltas
        # let us check shedding and that every delta is well formed (an
        # independent check of the DSL `bigtwo_penalty`, not sharing its code):
        # one zero-delta winner and a penalty for each other seat, or — the
        # precaution rule — one liable seat paying three penalties at once.
        # Which hands are liable is tests/test_bigtwo_precaution.py's.
        hand_totals: list[dict[int, int]] = []

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                hand_totals.append(dict(data))  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        assert hand_totals, f"seed {seed}: no hand was played"
        prev = {p: 0 for p in range(4)}
        for cum in hand_totals:
            deltas = {p: cum[p] - prev[p] for p in cum}
            paying = [d for d in deltas.values() if d != 0]
            if len(paying) == 1:
                assert paying[0] in _LIABLE_TOTALS, f"seed {seed}: bad liable total {deltas}"
            else:
                assert len(paying) == 3, f"seed {seed}: not exactly one shed-out winner: {deltas}"
                assert all(d in _VALID_PENALTIES for d in paying), f"seed {seed}: bad penalty {deltas}"
            prev = cum

        assert census["total"] == 52, f"seed {seed}: {census}"
        assert result.scores == hand_totals[-1], f"seed {seed}: final score mismatch"
        low = min(result.scores.values())
        assert result.winners == {p for p, s in result.scores.items() if s == low}
        assert max(result.scores.values()) >= 100, f"seed {seed}: match did not reach the threshold"


def test_a_seat_that_passes_plays_again_in_the_same_trick() -> None:
    """Pagat: "Passing does not prevent you from playing when your turn comes
    round again." A lead is the one ask offering no pass, so it opens a trick;
    within one, some seat that passed must later be asked and play.

    red under: a climb ring that drops a passing seat from the trick."""
    game = check_source(BIG_TWO)
    rng = random.Random(0)
    asks: list[tuple[int, list[Any], list[Any]]] = []

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        picked = rng.sample(candidates, n)
        asks.append((player, candidates, picked))
        return picked

    play_game(game, random.Random(0), chooser=chooser)
    passed: set[int] = set()
    replayed = 0
    for player, candidates, picked in asks:
        if "pass" not in candidates:
            passed.clear()  # a lead: a new trick
        elif picked == ["pass"]:
            passed.add(player)
        elif player in passed:
            replayed += 1
    assert replayed > 0, "no seat ever played after passing in the same trick"
