"""Known-value tests for 500's stdlib primitives
(cardlang/runtime/five_hundred.py), following the gin/cribbage pattern: the
pure decision cores — the bid ladder, follow/lead legality, the trick winner
— are proven against positions whose answers are known by construction,
independent of the ctx-adapter wiring (the playout harness re-verifies the
same rules end-to-end from the emitted traces).

Completeness ledger (surface-totality audit, this change):

property:   every 500 contract shape resolves follow/lead/winner correctly,
            and every bid ordinal maps to its Pagat value/target or refuses
domain:     contract shapes {4 trump suits, no-trumps, misère, open misère}
            x joker states {absent, un-nominated, nominated} x card classes
            {joker, right bower, left bower, plain trump, led suit, off
            suit}; bid ordinals {10..250 by tens, 105, 235} + non-ordinals
registry:   cardlang/runtime/five_hundred.py (_STRAIN_ORD, _MISERE_ORD,
            _OPEN_MISERE_ORD, _SUIT_BID_ORDS, _PLAIN_RANK, _SAME_COLOUR);
            the deck in cardlang/runtime/values.py (five_hundred43)
covered:    the full 27-rung ladder value/order table (exhaustive below);
            bower/joker follow-class remap and trump strength; the no-trump
            joker in all three nomination states incl. the misère forced
            play; the never-biddable/never-nominable "joker" pseudo-strain;
            the off-ladder refusals (bid_value / bid_level / trick size)
sampled:    full-game reachability of each contract family via the playout
            suite (tests/test_playout_five_hundred.py) and the driven
            open-misère line (tests/openspiel_ready/test_five_hundred.py)
residual:   the lead-time joker nomination Pagat allows when leading an
            un-nominated joker (modelled as "not before the holder's last
            card" — the wall is `lead_ok` returning False, loud as an empty
            candidate set never arises and the restriction is documented in
            five-hundred.md "Chosen ruleset"; recorded in roadmap.md,
            "Deferred work")
"""

from __future__ import annotations

import pytest

from cardlang.runtime.five_hundred import (
    five_hundred_bid_level,
    five_hundred_bid_value,
    five_hundred_next_bid,
    follow_ok,
    lead_ok,
    trick_winner,
)
from cardlang.runtime.values import DECKS, Card, build_deck

JOKER = Card("Joker", "joker")


def _c(spec: str) -> Card:
    rank, suit = spec[:-1], {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[spec[-1]]
    return Card(rank, suit)


def _h(*specs: str) -> list[Card]:
    return [_c(s) for s in specs]


# --- the deck ---------------------------------------------------------------


def test_five_hundred43_composition() -> None:
    cards = build_deck("five_hundred43")
    assert len(cards) == 43
    by_suit: dict[str, int] = {}
    for c in cards:
        by_suit[c.suit] = by_suit.get(c.suit, 0) + 1
    assert by_suit == {"clubs": 10, "spades": 10, "diamonds": 11, "hearts": 11, "joker": 1}
    # The black suits stop at 5; the red suits carry the 4; no 3s or 2s.
    assert not any(c.rank in ("3", "2") for c in cards)
    assert {c.suit for c in cards if c.rank == "4"} == {"diamonds", "hearts"}
    assert DECKS["five_hundred43"].values == {}  # no card-point values


# --- the bid ladder (exhaustive over the 27 rungs) ---------------------------

# (ordinal, value, level) for every suit/no-trump contract, plus the misères.
_LADDER = [
    (10, 40, 6), (20, 60, 6), (30, 80, 6), (40, 100, 6), (50, 120, 6),
    (60, 140, 7), (70, 160, 7), (80, 180, 7), (90, 200, 7), (100, 220, 7),
    (110, 240, 8), (120, 260, 8), (130, 280, 8), (140, 300, 8), (150, 320, 8),
    (160, 340, 9), (170, 360, 9), (180, 380, 9), (190, 400, 9), (200, 420, 9),
    (210, 440, 10), (220, 460, 10), (230, 480, 10), (240, 500, 10), (250, 520, 10),
]


def test_bid_values_and_levels_match_the_pagat_table() -> None:
    for ordinal, value, level in _LADDER:
        assert five_hundred_bid_value(ordinal) == value, ordinal
        assert five_hundred_bid_level(ordinal) == level, ordinal
    assert five_hundred_bid_value(105) == 250  # misère
    assert five_hundred_bid_value(235) == 500  # open misère


def test_next_bid_walks_every_strain_ladder() -> None:
    # From silence, each strain opens at its six-level rung.
    for strain, opening in [("spades", 10), ("clubs", 20), ("diamonds", 30), ("hearts", 40), (None, 50)]:
        assert five_hundred_next_bid(0, strain) == opening
    # The cheapest raise is the strain's next level above the standing bid.
    assert five_hundred_next_bid(10, "spades") == 60      # 6♠ -> 7♠
    assert five_hundred_next_bid(10, "clubs") == 20       # 6♠ -> 6♣
    assert five_hundred_next_bid(100, "hearts") == 140    # 7NT -> 8♥
    assert five_hundred_next_bid(105, "spades") == 110    # misère -> 8♠
    assert five_hundred_next_bid(235, "hearts") == 240    # open misère -> 10♥
    assert five_hundred_next_bid(235, None) == 250        # open misère -> 10NT
    # Exhausted ladders refuse with 0 (never a raise).
    assert five_hundred_next_bid(210, "spades") == 0      # no bid above 10♠ in ♠
    assert five_hundred_next_bid(250, None) == 0          # nothing above 10NT
    assert five_hundred_next_bid(235, "diamonds") == 0    # 10♦ ranks below open misère


def test_joker_pseudo_strain_is_never_biddable() -> None:
    # The deck-derived Suit domain carries "joker"; it is not a strain.
    for standing in (0, 10, 105, 235):
        assert five_hundred_next_bid(standing, "joker") == 0


def test_off_ladder_ordinals_refuse_loudly() -> None:
    for bad in (0, 5, 37, 105 + 1, 251, -10):
        with pytest.raises(RuntimeError, match="not a contract ordinal"):
            five_hundred_bid_value(bad)
    # The misères have no trick target; asking is the description's error.
    for bad in (105, 235, 0, 37):
        with pytest.raises(RuntimeError, match="not a suit/no-trump contract"):
            five_hundred_bid_level(bad)


# --- follow legality ---------------------------------------------------------


def test_trump_contract_bowers_and_joker_are_one_follow_class() -> None:
    # Hearts trump: joker, J♥ (right), J♦ (left) and hearts are the class.
    pool = _h("JD", "5H", "AD", "8C") + [JOKER]
    led = _c("KH")
    # Holding trump-class cards obliges a trump-class play.
    assert follow_ok(pool, led, _c("5H"), "hearts", False, None)
    assert follow_ok(pool, led, _c("JD"), "hearts", False, None)   # left bower follows hearts
    assert follow_ok(pool, led, JOKER, "hearts", False, None)      # joker follows hearts
    assert not follow_ok(pool, led, _c("AD"), "hearts", False, None)
    assert not follow_ok(pool, led, _c("8C"), "hearts", False, None)
    # The left bower's printed suit does NOT follow its colour-mate lead:
    # diamonds led, J♦ is a heart (trump) — holding another diamond, the
    # jack is not a legal follow.
    pool2 = _h("JD", "7D", "8C")
    assert follow_ok(pool2, _c("AD"), _c("7D"), "hearts", False, None)
    assert not follow_ok(pool2, _c("AD"), _c("JD"), "hearts", False, None)
    # Void of the led class: anything goes (no obligation to trump).
    pool3 = _h("8C", "5S")
    assert follow_ok(pool3, _c("KH"), _c("8C"), "hearts", False, None)
    assert follow_ok(pool3, _c("KH"), _c("5S"), "hearts", False, None)


def test_no_trump_joker_plays_only_when_void_and_is_forced_in_misere() -> None:
    pool = _h("7D", "8C") + [JOKER]
    led = _c("KD")
    # Holding the led suit: must follow — the suitless joker is not legal.
    assert follow_ok(pool, led, _c("7D"), None, False, None)
    assert not follow_ok(pool, led, JOKER, None, False, None)
    # Void in plain no-trumps: the joker becomes playable but stays optional.
    pool_void = _h("8C") + [JOKER]
    assert follow_ok(pool_void, led, JOKER, None, False, None)
    assert follow_ok(pool_void, led, _c("8C"), None, False, None)
    # Void in a misère: the un-nominated joker is FORCED.
    assert follow_ok(pool_void, led, JOKER, None, True, None)
    assert not follow_ok(pool_void, led, _c("8C"), None, True, None)
    # Nominated, the joker is a member of its suit: not forced when void of
    # the led suit (it is just a discard), and obliged when its suit is led.
    assert follow_ok(pool_void, led, _c("8C"), None, True, "clubs")
    assert follow_ok(pool_void, _c("4C"), JOKER, None, False, "clubs")
    # Hearts led with the joker nominated hearts: the joker IS the holder's
    # only heart, so the club is no longer a legal play.
    assert not follow_ok(pool_void, _c("4H"), _c("8C"), None, False, "hearts")


def test_lead_legality_for_the_joker() -> None:
    pool = _h("7D", "8C") + [JOKER]
    # Trump contract: the joker is the top trump and leads freely.
    assert lead_ok(pool, JOKER, "spades", None)
    # No-trump family, un-nominated: not before the holder's last card.
    assert not lead_ok(pool, JOKER, None, None)
    assert lead_ok([JOKER], JOKER, None, None)
    # Nominated: leads as the highest card of its suit.
    assert lead_ok(pool, JOKER, None, "hearts")
    # Plain cards always lead.
    assert lead_ok(pool, _c("7D"), None, None)


# --- the trick winner --------------------------------------------------------


def test_trump_trick_winner_joker_over_right_over_left_over_ace() -> None:
    trump = "hearts"
    assert trick_winner([(0, _c("AH")), (1, _c("JD")), (2, _c("JH")), (3, JOKER)], trump, None) == 3
    assert trick_winner([(0, _c("AH")), (1, _c("JD")), (2, _c("JH")), (3, _c("KH"))], trump, None) == 2
    assert trick_winner([(0, _c("AH")), (1, _c("JD")), (2, _c("10H")), (3, _c("KH"))], trump, None) == 1
    # No trump played: highest of the suit led.
    assert trick_winner([(2, _c("9C")), (3, _c("QC")), (0, _c("4D")), (1, _c("AS"))], trump, None) == 3
    # The left bower TRUMPS a plain lead of its printed suit.
    assert trick_winner([(0, _c("AD")), (1, _c("JD")), (2, _c("KD")), (3, _c("QD"))], trump, None) == 1


def test_no_trump_trick_winner_and_the_nominated_joker() -> None:
    # Un-nominated joker wins any trick it is played to.
    assert trick_winner([(0, _c("AD")), (1, JOKER), (2, _c("KD")), (3, _c("QD"))], None, None) == 1
    # No joker: highest of the suit led (aces high, off-suit never wins).
    assert trick_winner([(1, _c("9C")), (2, _c("QC")), (3, _c("AD")), (0, _c("KC"))], None, None) == 0
    # Nominated joker wins when its suit is led...
    assert trick_winner([(0, _c("AD")), (1, JOKER), (2, _c("KD"))], None, "diamonds") == 1
    # ...and LOSES when discarded on another suit (it is just a diamond).
    assert trick_winner([(0, _c("AC")), (1, JOKER), (2, _c("KC"))], None, "diamonds") == 0
    # A nominated joker led sets its suit as the led class.
    assert trick_winner([(1, JOKER), (2, _c("AD")), (3, _c("AC"))], None, "diamonds") == 1
