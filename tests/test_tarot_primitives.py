"""Known-value tests for French Tarot's stdlib primitives
(cardlang/runtime/tarot.py) and the `Card.__str__` glyph fix they depend on.

The playout invariants (test_playout_french_tarot.py) cannot catch a misvalued
primitive on their own — a wrong `tarot_per_opp` could still zero-sum by
construction. These pin the published values directly (issue #83), following the test_pinochle_meld.py /
test_stud_settle.py precedent for a migrated game's pure-primitive module.
`tarot_per_opp`'s synthetic `_scoring_ctx` also declares the fidelity stage's
`discard[player]` zone, so a hand with (or without) taker discards can be
constructed directly.
"""

from __future__ import annotations

import random

import pytest

from cardlang.runtime import reads, sidecar
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.tarot import ROW
from cardlang.runtime.tarot import (
    tarot_card_points,
    tarot_excuse_player,
    tarot_led_suit,
    tarot_per_opp,
    tarot_trick_winner,
    tarot_trump_height,
)
from cardlang.runtime.values import Card, Seating, build_deck

EXCUSE = Card("Excuse", "excuse")


def _atout(rank: str) -> Card:
    return Card(rank, "atouts")


# --- tarot_card_points ---


def test_card_points_sum_to_182_doubled_units() -> None:
    assert sum(tarot_card_points(c) for c in build_deck("tarot78")) == 182


def test_card_points_known_values() -> None:
    assert tarot_card_points(EXCUSE) == 9
    assert tarot_card_points(_atout("1")) == 9  # the petit, a bout
    assert tarot_card_points(_atout("21")) == 9  # the 21, a bout
    assert tarot_card_points(_atout("10")) == 1  # a plain atout
    assert tarot_card_points(Card("K", "clubs")) == 9
    assert tarot_card_points(Card("Q", "hearts")) == 7
    assert tarot_card_points(Card("C", "spades")) == 5  # the Cavalier
    assert tarot_card_points(Card("J", "diamonds")) == 3
    assert tarot_card_points(Card("10", "clubs")) == 1
    assert tarot_card_points(Card("2", "clubs")) == 1


# --- tarot_trump_height ---


def test_trump_height_is_the_atout_rank_int() -> None:
    assert tarot_trump_height(_atout("1")) == 1
    assert tarot_trump_height(_atout("21")) == 21
    assert tarot_trump_height(_atout("14")) == 14


def test_trump_height_is_zero_for_non_atouts() -> None:
    assert tarot_trump_height(Card("K", "clubs")) == 0
    assert tarot_trump_height(EXCUSE) == 0



# The bundle materialises tarot.py's WHOLE declared row (taker, bid_level;
# captured, discard; trick_pile, chien), so every fixture declares all of it —
# a partial fixture is indistinguishable from the game file and the module
# having drifted apart, which is exactly what the registry refuses.
_Bundles = tuple[sidecar.EngineFacts, reads.GameReads]


def _tarot_rs() -> RuntimeState:
    from cardlang.ast import nodes as n

    zone_decls = (
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
        n.ZoneDecl(name="chien", index=None, type_ref=n.TypeRef(name="FaceDownPile")),
        n.ZoneDecl(
            name="captured", index="player", type_ref=n.TypeRef(name="PlayerPile")
        ),
        n.ZoneDecl(
            name="discard", index="player", type_ref=n.TypeRef(name="HiddenPile")
        ),
    )
    rs = RuntimeState(Seating(4), ZoneStore(zone_decls, (0, 1, 2, 3)), random.Random(0))
    rs.push_frame()
    rs.declare("taker", False, 0)
    rs.declare("bid_level", False, 1)
    return rs


# --- tarot_led_suit ---


def _pile_ctx(cards: list[Card]) -> _Bundles:
    rs = _tarot_rs()
    rs.zones.single("trick_pile").add_all(cards)
    return sidecar.bind(rs, None, ROW)


def test_led_suit_is_the_first_non_excuse_card() -> None:
    ctx = _pile_ctx([Card("5", "hearts"), Card("K", "clubs")])
    assert tarot_led_suit(*ctx) == "hearts"


def test_led_suit_when_the_excuse_is_led() -> None:
    # The Excuse alone: no non-Excuse card yet -> "excuse" (the quirk that
    # forces the second player to trump if able).
    ctx = _pile_ctx([EXCUSE])
    assert tarot_led_suit(*ctx) == "excuse"


def test_led_suit_skips_the_excuse_when_led_then_a_real_card_follows() -> None:
    ctx = _pile_ctx([EXCUSE, Card("9", "atouts")])
    assert tarot_led_suit(*ctx) == "atouts"


# --- tarot_trick_winner ---


def test_trick_winner_highest_atout_wins() -> None:
    played = [
        (0, Card("K", "clubs")),
        (1, _atout("5")),
        (2, _atout("14")),
        (3, _atout("2")),
    ]
    assert tarot_trick_winner(played, "clubs", "atouts", {}) == 2


def test_trick_winner_no_atout_highest_of_led_suit() -> None:
    played = [(0, Card("Q", "hearts")), (1, Card("K", "hearts")), (2, Card("5", "clubs"))]
    assert tarot_trick_winner(played, "hearts", "atouts", {}) == 1  # K > Q in-suit


def test_excuse_never_wins_even_when_led() -> None:
    played = [(0, EXCUSE), (1, Card("2", "hearts"))]
    assert tarot_trick_winner(played, "excuse", "atouts", {}) == 1


def test_excuse_never_wins_against_a_lone_atout() -> None:
    played = [(0, EXCUSE), (1, _atout("1"))]
    assert tarot_trick_winner(played, "excuse", "atouts", {}) == 1


# --- tarot_excuse_player ---


def _excuse_ctx(played: list[tuple[int, Card]], live_round: bool) -> _Bundles:
    rs = _tarot_rs()
    state = {"played": played}
    if live_round:
        rs.mech_state.append(state)
    else:
        rs.last_round_state = state
    return sidecar.bind(rs, None, ROW)


def test_excuse_player_found_via_last_round_state() -> None:
    played = [(0, Card("K", "clubs")), (1, EXCUSE), (2, Card("2", "hearts"))]
    ctx = _excuse_ctx(played, live_round=False)
    assert tarot_excuse_player(*ctx) == 1


def test_excuse_player_found_via_live_mech_state() -> None:
    played = [(0, EXCUSE), (1, Card("2", "hearts"))]
    ctx = _excuse_ctx(played, live_round=True)
    assert tarot_excuse_player(*ctx) == 0


def test_excuse_player_none_when_nobody_played_it() -> None:
    played = [(0, Card("K", "clubs")), (1, Card("2", "hearts"))]
    ctx = _excuse_ctx(played, live_round=False)
    assert tarot_excuse_player(*ctx) is None


# --- tarot_per_opp ---


def _scoring_ctx(
    taker: int,
    bid_level: int,
    captured_taker: list[Card],
    chien: list[Card],
    discard_taker: list[Card] | None = None,
) -> _Bundles:
    rs = _tarot_rs()
    rs.set("taker", taker)
    rs.set("bid_level", bid_level)
    rs.zones.single("chien").add_all(chien)
    rs.zones.instance("captured", taker).add_all(captured_taker)
    if discard_taker is not None:
        rs.zones.instance("discard", taker).add_all(discard_taker)
    return sidecar.bind(rs, None, ROW)


def test_per_opp_at_petite_threshold_with_three_bouts() -> None:
    # 3 bouts -> threshold 36 (doubled). Taker holds exactly 36 doubled points
    # (18 real) worth of cards including all 3 bouts: pt = 36/2 - 36 = -18.
    # per_opp = round((25 - 18 + 0) * 1) = 7.
    # Build a hand whose doubled total is exactly 36 with 3 bouts (9+9+9=27
    # from the bouts; 9 more doubled points needed from plain-suit cards, each
    # worth 1 except K/Q/C/J which are worth 9/7/5/3 — nine "2..10" cards give
    # exactly 9).
    captured = [EXCUSE, _atout("1"), _atout("21")] + [
        Card(r, "clubs") for r in ("2", "3", "4", "5", "6", "7", "8", "9", "10")
    ]
    assert sum(tarot_card_points(c) for c in captured) == 36
    ctx = _scoring_ctx(taker=0, bid_level=1, captured_taker=captured, chien=[])
    assert tarot_per_opp(*ctx, pb=0) == 7


def test_per_opp_garde_sans_counts_the_chien() -> None:
    # Garde sans le chien (level 3, mult=4): the chien's points and bouts count
    # to the taker even though the chien is never moved into captured[taker].
    captured = [_atout("1"), _atout("21")] + [Card(r, "clubs") for r in ("2", "3")]
    chien = [EXCUSE, Card("4", "hearts")]
    # bouts = 3 (both atout bouts + the Excuse in the chien); doubled total =
    # (9+9+1+1) + (9+1) = 30. threshold(3 bouts) = 36. pt = 30/2 - 36 = -21.
    # per_opp = round((25 - 21 + 0) * 4) = 16.
    assert sum(tarot_card_points(c) for c in captured) + sum(
        tarot_card_points(c) for c in chien
    ) == 30
    ctx = _scoring_ctx(taker=0, bid_level=3, captured_taker=captured, chien=chien)
    assert tarot_per_opp(*ctx, pb=0) == 16


def test_per_opp_counts_the_taker_discard() -> None:
    # The fidelity stage reroutes the chien discard to a hidden `discard[taker]`
    # zone, not commingled into `captured[taker]` — tarot_per_opp must
    # still count it toward the taker's total (same 36-doubled-point, 3-bout
    # hand as test_per_opp_at_petite_threshold_with_three_bouts, but split
    # across captured + discard instead of sitting entirely in captured).
    captured = [EXCUSE, _atout("1"), _atout("21")]  # the 3 bouts: 27 doubled
    discard = [
        Card(r, "clubs") for r in ("2", "3", "4", "5", "6", "7", "8", "9", "10")
    ]  # 9 plain cards: 9 doubled
    assert sum(tarot_card_points(c) for c in captured) + sum(
        tarot_card_points(c) for c in discard
    ) == 36
    ctx = _scoring_ctx(
        taker=0, bid_level=1, captured_taker=captured, chien=[], discard_taker=discard
    )
    assert tarot_per_opp(*ctx, pb=0) == 7  # identical to the all-in-captured case


def test_per_opp_petit_au_bout_adjustment() -> None:
    captured = [EXCUSE, _atout("1"), _atout("21")] + [
        Card(r, "clubs") for r in ("2", "3", "4", "5", "6", "7", "8", "9", "10")
    ]
    ctx = _scoring_ctx(taker=0, bid_level=1, captured_taker=captured, chien=[])
    assert tarot_per_opp(*ctx, pb=10) == 17  # round((25 - 18 + 10) * 1)
    assert tarot_per_opp(*ctx, pb=-10) == -3  # round((25 - 18 - 10) * 1)


def test_per_opp_banker_rounding_at_petite() -> None:
    # pt a half-integer -> Python's round() (banker's rounding) on the exact
    # .5 boundary, verbatim from the monolith (no manual round-half-up).
    # 0 bouts -> threshold 56 (doubled). One plain card (1 doubled point):
    # pt = 1/2 - 56 = -55.5 -> (25 - 55.5) = -30.5 -> round(-30.5) == -30
    # (round-to-even: -30 is even, -31 is odd).
    ctx = _scoring_ctx(taker=0, bid_level=1, captured_taker=[Card("2", "clubs")], chien=[])
    assert tarot_per_opp(*ctx, pb=0) == -30  # round(-30.5) == -30, round-half-to-even


# --- Card.__str__ glyphs ---


def test_str_standard_suits_unchanged() -> None:
    assert str(Card("A", "clubs")) == "A♣"
    assert str(Card("K", "hearts")) == "K♥"


def test_str_atouts_and_excuse_glyphs() -> None:
    assert str(_atout("1")) == "1★"
    assert str(_atout("21")) == "21★"
    assert str(EXCUSE) == "Excuse☆"


def test_str_unknown_suit_fallback() -> None:
    assert str(Card("Duke", "court")) == "Duke:court"
