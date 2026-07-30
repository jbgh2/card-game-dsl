"""Known-value tests for Cribbage's stdlib primitives
(cardlang/runtime/cribbage.py), following the test_tarot_primitives.py /
test_pinochle_meld.py precedent for a migrated game's pure-primitive module.

`peg_origin` is the pure decoder for the kernel's card-provenance residue
(`seq_bits`/`seq_len`, packed MSB-first, 1 = dealer — see cribbage.py's module
docstring and docs/kernel-migration.md WS4). `peg_origin_of` is its ctx-adapter
over the live `play_pile`; a routing round-trip test confirms that applying its
predicate through the two split "close" movements (`... where
peg_origin_of(card) is dealer ...` then the unfiltered remainder) reproduces the
per-player partition of a synthetic play sequence, in order — the property the
DSL's close-routing statements actually rely on.
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.runtime import reads, sidecar
from cardlang.runtime.cribbage import (
    ROW,
    cribbage_crib_value,
    cribbage_show_value,
    peg_origin,
    peg_origin_of,
)
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating, expand_ranking_convention

# --- peg_origin: the pure bit-decoder ---


def test_peg_origin_strict_alternation() -> None:
    # Non-dealer leads (bit 0), then strict alternation: 0, 1, 0, 1.
    seq_bits = 0b0101
    seq_len = 4
    assert [peg_origin(seq_bits, seq_len, i) for i in range(4)] == [0, 1, 0, 1]


def test_peg_origin_dealer_led_alternation() -> None:
    # Dealer leads (bit 1), then strict alternation: 1, 0, 1, 0.
    seq_bits = 0b1010
    seq_len = 4
    assert [peg_origin(seq_bits, seq_len, i) for i in range(4)] == [1, 0, 1, 0]


def test_peg_origin_a_go_inside_the_count() -> None:
    # Non-dealer leads, dealer goes (no play, no bit appended), so non-dealer
    # plays twice running: bits 0, 0, 1 — two consecutive equal bits at
    # positions 0/1, the "a go inside a count" shape.
    seq_bits = 0b001
    seq_len = 3
    assert peg_origin(seq_bits, seq_len, 0) == 0
    assert peg_origin(seq_bits, seq_len, 1) == 0
    assert peg_origin(seq_bits, seq_len, 2) == 1


def test_peg_origin_31_reset_boundary() -> None:
    # After a 31 (or a two-go close) resets seq_bits/seq_len to 0, the next
    # sub-round's first play is decoded fresh at position 0 regardless of the
    # previous sub-round's (now-discarded) bit width.
    assert peg_origin(0, 1, 0) == 0  # a fresh sub-round, non-dealer leads
    assert peg_origin(1, 1, 0) == 1  # a fresh sub-round, dealer leads


# --- peg_origin_of / cribbage_show_value / cribbage_crib_value: ctx-adapters ---


def _zone_decls() -> tuple[n.ZoneDecl, ...]:
    return (
        n.ZoneDecl(name="play_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
        n.ZoneDecl(name="played", index="player", type_ref=n.TypeRef(name="PlayerPile")),
        n.ZoneDecl(name="starter", index=None, type_ref=n.TypeRef(name="Discard")),
        n.ZoneDecl(name="crib", index=None, type_ref=n.TypeRef(name="FaceDownPile")),
    )


def _aces_low_index() -> dict[str, int]:
    """The driver's `rank_index` for cribbage's declared `ranking: aces low` —
    derived through the same public expansion the resolver uses, so the
    fixture can't drift into a private copy of the order."""
    order = expand_ranking_convention("aces low", "standard52")
    return {r: len(order) - 1 - i for i, r in enumerate(order)}


_Bundles = tuple[sidecar.EngineFacts, reads.GameReads]


def _peg_rs(
    play_pile: list[Card], seq_bits: int, seq_len: int, dealer: int = 1
) -> RuntimeState:
    rs = RuntimeState(Seating(2), ZoneStore(_zone_decls(), (0, 1)), random.Random(0))
    rs.rank_index = _aces_low_index()
    rs.push_frame()
    rs.declare("dealer", False, dealer)
    rs.declare("seq_bits", False, seq_bits)
    rs.declare("seq_len", False, seq_len)
    rs.zones.single("play_pile").add_all(play_pile)
    return rs


def _peg_ctx(
    play_pile: list[Card], seq_bits: int, seq_len: int, dealer: int = 1
) -> _Bundles:
    return sidecar.bind(_peg_rs(play_pile, seq_bits, seq_len, dealer), None, ROW)


def test_peg_origin_of_reads_the_pile_position() -> None:
    c0, c1, c2 = Card("5", "clubs"), Card("6", "hearts"), Card("K", "spades")
    # Non-dealer (0) leads, dealer (1) follows, non-dealer (0) plays third.
    ctx = _peg_ctx([c0, c1, c2], seq_bits=0b010, seq_len=3, dealer=1)
    assert peg_origin_of(*ctx, c0) == 0
    assert peg_origin_of(*ctx, c1) == 1
    assert peg_origin_of(*ctx, c2) == 0


def test_peg_origin_of_routing_round_trip() -> None:
    # A synthetic (player, card) play sequence for a 5-play sub-round, dealer
    # (1) leading: dealer, non-dealer, non-dealer (a go by dealer), dealer,
    # non-dealer.
    sequence = [
        (1, Card("2", "clubs")),
        (0, Card("3", "clubs")),
        (0, Card("4", "clubs")),
        (1, Card("5", "clubs")),
        (0, Card("6", "clubs")),
    ]
    seq_bits = 0
    for player, _ in sequence:
        seq_bits = seq_bits * 2 + (1 if player == 1 else 0)
    rs = _peg_rs([c for _, c in sequence], seq_bits=seq_bits, seq_len=len(sequence), dealer=1)
    # Bound ONCE, against the intact pile — which is what the DSL's two split
    # movements do, and what the bundle now makes structural: the snapshot
    # cannot shift under the reads as the pile drains below.
    ctx = sidecar.bind(rs, None, ROW)
    play_pile = rs.zones.single("play_pile")
    # The DSL's close routing: filter the dealer's cards first (predicate over
    # the intact pile), then take the unfiltered remainder — reproduced here
    # directly against `peg_origin_of`, exactly as the two split movements do.
    dealer_cards = [c for c in play_pile.cards if peg_origin_of(*ctx, c) == 1]
    for c in dealer_cards:
        play_pile.remove(c)
    nondealer_cards = list(play_pile.cards)
    assert dealer_cards == [card for player, card in sequence if player == 1]
    assert nondealer_cards == [card for player, card in sequence if player == 0]


def test_peg_origin_of_requires_reading_before_the_pile_drains() -> None:
    # Evaluating peg_origin_of after the pile has been partially drained would
    # index into the wrong (shrunk) pile — the DSL never does this (both split
    # movements read `peg_origin_of` against the intact pile), but pin the
    # ValueError a stale reference would raise, so a future refactor that
    # breaks this ordering fails loudly rather than silently misrouting cards.
    c0, c1 = Card("5", "clubs"), Card("6", "hearts")
    rs = _peg_rs([c0, c1], seq_bits=0b01, seq_len=2, dealer=1)
    rs.zones.single("play_pile").remove(c0)
    with pytest.raises(ValueError):
        peg_origin_of(*sidecar.bind(rs, None, ROW), c0)


def _show_ctx(
    played0: list[Card], played1: list[Card], crib: list[Card], starter: Card
) -> _Bundles:
    rs = RuntimeState(Seating(2), ZoneStore(_zone_decls(), (0, 1)), random.Random(0))
    rs.rank_index = _aces_low_index()
    # The bundle materialises the module's WHOLE declared row, so a fixture
    # must declare every name in it — an omission is indistinguishable from
    # the game file and the module having drifted apart.
    rs.push_frame()
    rs.declare("dealer", False, 1)
    rs.declare("seq_bits", False, 0)
    rs.declare("seq_len", False, 0)
    rs.zones.instance("played", 0).add_all(played0)
    rs.zones.instance("played", 1).add_all(played1)
    rs.zones.single("crib").add_all(crib)
    rs.zones.single("starter").add(starter)
    return sidecar.bind(rs, None, ROW)


def test_cribbage_show_value_reads_the_players_pegged_hand() -> None:
    # The classic perfect 29: three 5s + the J of diamonds, with the fourth 5
    # (also diamonds) as the starter. Fifteens: four (5+5+5) + four (5+J) = 8 -> 16;
    # pairs: C(4,2) = 6 -> 12; his nob: the J matches the diamond starter -> 1.
    # Total 29.
    hand = [Card("5", "clubs"), Card("5", "hearts"), Card("5", "spades"), Card("J", "diamonds")]
    starter = Card("5", "diamonds")
    ctx = _show_ctx(hand, [], [], starter)
    assert cribbage_show_value(*ctx, 0) == 29
    assert cribbage_show_value(*ctx, 1) == 0  # player 1's played hand is empty


def test_cribbage_crib_value_reads_the_crib_against_the_starter() -> None:
    hand = [Card("5", "clubs"), Card("5", "hearts"), Card("5", "spades"), Card("J", "diamonds")]
    starter = Card("5", "diamonds")
    ctx = _show_ctx([], [], hand, starter)
    # The crib scores the same combination points as a hand would, EXCEPT the
    # crib-only flush rule (is_crib=True: a 4-flush is worth 0, not 4) — moot
    # here (the sample hand isn't a flush), so the value is the same 29.
    assert cribbage_crib_value(*ctx) == 29
