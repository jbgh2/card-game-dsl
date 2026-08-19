"""Known-value tests for 500's Primitives
(cardlang/runtime/five_hundred.py), following the gin/cribbage pattern: the
pure decision core -- the 27-rung bid ladder with the misere insertions -- is
proven against ordinals whose values are known by construction, independent of
the ctx-adapter wiring.

The contract's ORDER is not here and has no known-value table: the joker, the
bowers and the no-trump family's suitless joker are the game's declared Trick
Order (issue #250 PR 3), so what once needed a table of positions is now
proven by execution instead -- an independent recomputation of every trick's
winner and every follow and lead decision over forty seeded games
(tests/test_playout_five_hundred.py, with a census pinning that each joker and
bower role actually occurs), and a 200-seed byte-identity pin against the
pre-migration engine (tests/test_trick_order_migration.py). The construct's own
domain is tests/test_trick_order.py.

Completeness ledger (surface-totality audit, this change):

property:   every bid ordinal maps to its Pagat value/target or refuses, and
            the deck is the 43-card pack
domain:     bid ordinals {10..250 by tens, 105, 235} + non-ordinals x the
            three ladder readers; the five strains including the
            never-biddable "joker" pseudo-strain
registry:   cardlang/runtime/five_hundred.py (_STRAIN_ORD, _MISERE_ORD,
            _OPEN_MISERE_ORD, _SUIT_BID_ORDS); the deck in
            cardlang/runtime/values.py (five_hundred43)
covered:    the full 27-rung ladder value/order table (exhaustive below); each
            strain's opening rung and cheapest raise; the exhausted-ladder 0;
            the never-biddable "joker" pseudo-strain; the off-ladder refusals
            (bid_value / bid_level)
sampled:    full-game reachability of each contract family via the playout
            suite (tests/test_playout_five_hundred.py) and the driven
            open-misere line (tests/openspiel_ready/test_five_hundred.py)
residual:   the lead-time joker nomination Pagat allows when leading an
            un-nominated joker (modelled as "not before the holder's last
            card" -- now the game file's own `lead_ok` function, loud as an
            empty candidate set never arises and the restriction is documented
            in five-hundred.md "Chosen ruleset (modelling notes)"; recorded in
            issue #106)
"""

from __future__ import annotations

import pytest

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.five_hundred import (
    five_hundred_bid_level,
    five_hundred_bid_value,
    five_hundred_next_bid,
)
from cardlang.runtime.values import build_deck

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
    # No card-point assertion: a Deck carries composition only — the class
    # cannot represent a point table at all (500 declares no `card_points`).


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
        with pytest.raises(OwnerGuardError, match="not a contract ordinal"):
            five_hundred_bid_value(bad)
    # The misères have no trick target; asking is the description's error.
    for bad in (105, 235, 0, 37):
        with pytest.raises(OwnerGuardError, match="not a suit/no-trump contract"):
            five_hundred_bid_level(bad)
