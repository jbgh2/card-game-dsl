"""Known-value net for Canasta's runtime primitives (cardlang/runtime/canasta.py).

Targets the PURE core — the point/threshold/bonus tables and the meld-attempt
legality function — with hand-built values, the Gin/Cribbage pattern: the
ctx-adapters above the core are exercised end-to-end by every playout seed
(tests/test_playout_canasta.py), which would crash loudly on a wedged meld
window; the JOINT conditions themselves are pinned here at their boundaries.

property:   the meld-attempt core states every joint meld condition of
            Classic Canasta — composition (>= 2 naturals, <= 3 wilds,
            size >= 3), the frozen/unfrozen pile-take justification, the
            initial-meld minimum with best-value wild selection, and the
            go-out safety rule — and the card-point / minimum / bonus
            tables are the Pagat values
domain:     each `_close_legal` condition arm x {satisfied, violated at its
            boundary}; each table x its bracket boundaries
registry:   canasta.py: POINTS, WILD_RANKS, NATURAL_MELD_RANKS,
            initial_minimum, canasta_bonus_for, red3_bonus_for,
            _Attempt/_close_legal/_completable
covered:    every condition arm probed on and off at its boundary below;
            every table bracket probed at both edges
sampled:    `_completable`'s (a, b) search — probed at representative cells;
            the search is a two-variable brute force over the FULL pool
            ranges by construction, so cells differ only in data
residual:   none
"""

from __future__ import annotations

from cardlang.runtime.canasta import (
    NATURAL_MELD_RANKS,
    POINTS,
    WILD_RANKS,
    _Attempt,
    _close_legal,
    _completable,
    canasta_bonus_for,
    card_points,
    initial_minimum,
    is_black3,
    is_red3,
    is_wild,
    red3_bonus_for,
)
from cardlang.runtime.values import Card, build_deck


def _attempt(
    rank: str = "K",
    existing_n: int = 0,
    existing_w: int = 0,
    staged_n: int = 0,
    staged_w: int = 0,
    staged_value: int = 0,
    hand_nat: int = 0,
    wild_values: tuple[int, ...] = (),
    hand_size: int = 8,
    taking: bool = False,
    flush_gain: int = 0,
    frozen: bool = False,
    minimum: int | None = None,
    other_canasta: bool = False,
) -> _Attempt:
    return _Attempt(
        rank=rank,
        existing_n=existing_n,
        existing_w=existing_w,
        staged_n=staged_n,
        staged_w=staged_w,
        staged_value=staged_value,
        hand_nat=hand_nat,
        wild_values=wild_values,
        hand_size=hand_size,
        taking=taking,
        flush_gain=flush_gain,
        frozen=frozen,
        minimum=minimum,
        other_canasta=other_canasta,
    )


# --- the tables --------------------------------------------------------------


def test_card_points_are_the_pagat_values() -> None:
    assert POINTS["Joker"] == 50
    assert POINTS["2"] == 20 and POINTS["A"] == 20
    for r in ("K", "Q", "J", "10", "9", "8"):
        assert POINTS[r] == 10
    for r in ("7", "6", "5", "4", "3"):
        assert POINTS[r] == 5
    # Every rank the canasta108 deck holds is valued (no KeyError at scoring).
    assert {c.rank for c in build_deck("canasta108")} == set(POINTS)


def test_card_classes_partition_the_deck() -> None:
    deck = build_deck("canasta108")
    assert sum(is_wild(c) for c in deck) == 12  # 8 deuces + 4 jokers
    assert sum(is_red3(c) for c in deck) == 4
    assert sum(is_black3(c) for c in deck) == 4
    assert set(WILD_RANKS) == {"Joker", "2"}
    # The meldable natural ranks are exactly the declared partial ranking's
    # eleven (threes and the wild ranks excluded).
    assert len(NATURAL_MELD_RANKS) == 11
    assert set(NATURAL_MELD_RANKS).isdisjoint({"3", *WILD_RANKS})
    assert card_points(Card("Joker", "joker")) == 50


def test_initial_minimum_brackets() -> None:
    assert initial_minimum(-5) == 15
    assert initial_minimum(0) == 50
    assert initial_minimum(1495) == 50
    assert initial_minimum(1500) == 90
    assert initial_minimum(2995) == 90
    assert initial_minimum(3000) == 120
    assert initial_minimum(9000) == 120


def test_canasta_bonus_by_composition() -> None:
    naturals = [Card("K", "spades")] * 7
    assert canasta_bonus_for(naturals) == 500  # natural canasta
    assert canasta_bonus_for(naturals[:6] + [Card("2", "hearts")]) == 300  # mixed
    assert canasta_bonus_for(naturals[:6]) == 0  # six cards: not a canasta
    assert canasta_bonus_for(naturals + [Card("Joker", "joker")]) == 300  # wild added


def test_red3_bonus_signs_and_all_four() -> None:
    assert red3_bonus_for(0, True) == 0 and red3_bonus_for(0, False) == 0
    assert red3_bonus_for(1, True) == 100
    assert red3_bonus_for(3, False) == -300
    assert red3_bonus_for(4, True) == 800
    assert red3_bonus_for(4, False) == -800


# --- composition arms --------------------------------------------------------


def test_composition_needs_three_cards_two_naturals() -> None:
    # Three naturals: legal; two: not (size boundary).
    assert _close_legal(_attempt(staged_n=3), 0, 0)
    assert not _close_legal(_attempt(staged_n=2), 0, 0)
    # Two naturals + one wild: legal; one natural + two wilds: not (the
    # >=2-naturals boundary).
    assert _close_legal(_attempt(staged_n=2, staged_w=1), 0, 0)
    assert not _close_legal(_attempt(staged_n=1, staged_w=2), 0, 0)


def test_composition_caps_wilds_at_three_counting_existing() -> None:
    assert _close_legal(_attempt(staged_n=4, staged_w=3), 0, 0)
    assert not _close_legal(_attempt(staged_n=4, staged_w=4), 0, 0)
    # A standing meld's wilds count toward the cap for additions.
    assert not _close_legal(
        _attempt(existing_n=2, existing_w=3, staged_n=0, staged_w=1), 0, 0
    )
    assert _close_legal(
        _attempt(existing_n=2, existing_w=2, staged_n=1, staged_w=1), 0, 0
    )


# --- pile-take justification -------------------------------------------------


def test_frozen_take_needs_a_natural_pair_from_hand() -> None:
    # staged_n includes the pile's top card: 3 staged naturals = top + pair.
    frozen_pair = _attempt(taking=True, frozen=True, staged_n=3)
    assert _close_legal(frozen_pair, 0, 0)
    # Top + one natural + one wild is NOT enough against a frozen pile.
    assert not _close_legal(
        _attempt(taking=True, frozen=True, staged_n=2, staged_w=1), 0, 0
    )
    # A standing meld of the rank does not waive the frozen pair rule.
    assert not _close_legal(
        _attempt(taking=True, frozen=True, existing_n=3, staged_n=1), 0, 0
    )


def test_unfrozen_take_pair_or_wild_or_standing_meld() -> None:
    # Top + natural + wild: legal unfrozen.
    assert _close_legal(
        _attempt(taking=True, frozen=False, staged_n=2, staged_w=1), 0, 0
    )
    # Top alone onto the side's standing meld: legal unfrozen.
    assert _close_legal(
        _attempt(taking=True, frozen=False, existing_n=3, staged_n=1), 0, 0
    )
    # Top alone with NO standing meld: not a take (two cards from hand
    # required) — the added < 3 boundary.
    assert not _close_legal(_attempt(taking=True, frozen=False, staged_n=1), 0, 0)


# --- the initial-meld minimum ------------------------------------------------


def test_initial_minimum_counts_staged_value_and_additions() -> None:
    # Three kings = 30 < 50: below the standard bracket.
    kings30 = _attempt(staged_n=3, staged_value=30, minimum=50)
    assert not _close_legal(kings30, 0, 0)
    # A-A-Joker = 90 >= 50 (the staged value counts the wild's 50).
    assert _close_legal(_attempt(rank="A", staged_n=2, staged_value=90, staged_w=1, minimum=50), 0, 0)
    # Additions count at the rank's value and best-value wilds first: from
    # 2 staged kings (20), adding one king (10) + the JOKER (50) reaches 80;
    # with only the deuce (20) it reaches 50 exactly — both witnessed by
    # `_completable`, and the deuce-only pool fails a 55 minimum where the
    # joker pool passes it.
    base = _attempt(staged_n=2, staged_value=20, hand_nat=1, minimum=55)
    assert _completable(_attempt(**{**base.__dict__, "wild_values": (50,)}))
    assert not _completable(_attempt(**{**base.__dict__, "wild_values": (20,)}))


# --- go-out safety -----------------------------------------------------------


def test_go_out_safety_keeps_two_cards_or_a_canasta() -> None:
    # Closing 3 staged naturals with 2 cards left in hand: fine.
    assert _close_legal(_attempt(staged_n=3, hand_size=2), 0, 0)
    # Only 1 card left, no canasta anywhere: refused (the forced-discard
    # would be an illegal go-out next turn).
    assert not _close_legal(_attempt(staged_n=3, hand_size=1), 0, 0)
    # The same close with a canasta already on the row: legal (go out).
    assert _close_legal(_attempt(staged_n=3, hand_size=1, other_canasta=True), 0, 0)
    # Or when this very close completes the canasta (7 cards).
    assert _close_legal(_attempt(staged_n=7, hand_size=0), 0, 0)
    assert not _close_legal(_attempt(staged_n=6, hand_size=0), 0, 0)
    # A pile take's flush restores the hand: top + pair staged, hand
    # emptied, but the flushed pile cards land in hand before the discard.
    assert _close_legal(
        _attempt(taking=True, frozen=True, staged_n=3, hand_size=0, flush_gain=2), 0, 0
    )
    assert not _close_legal(
        _attempt(taking=True, frozen=True, staged_n=3, hand_size=0, flush_gain=1), 0, 0
    )


# --- the completability search -----------------------------------------------


def test_completable_searches_hand_pools() -> None:
    # Nothing staged, two naturals + a wild in hand: a legal close exists.
    assert _completable(_attempt(hand_nat=2, wild_values=(20,)))
    # Two naturals alone: no third card exists, so size three is unreachable.
    assert not _completable(_attempt(hand_nat=2))
    # One natural + three wilds: n never reaches 2 with size 3 — refused.
    assert not _completable(_attempt(hand_nat=1, wild_values=(50, 20, 20)))
    # Three naturals: legal (a=3).
    assert _completable(_attempt(hand_nat=3))
