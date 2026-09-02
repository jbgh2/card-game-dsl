"""Known-value tests for French Tarot's Primitives
(cardlang/runtime/tarot.py), its declared [[trick-order]], and the
`Card.__str__` glyph fix they depend on.

The playout invariants (test_playout_french_tarot.py) cannot catch a misvalued
primitive on their own — a wrong `tarot_per_opp` could still zero-sum by
construction. These pin the published values directly (issue #83), following the test_pinochle_meld.py /
test_stud_settle.py precedent for a migrated game's pure-primitive module.
`tarot_per_opp`'s synthetic `_scoring_ctx` also declares the fidelity stage's
`discard[player]` zone, so a hand with (or without) taker discards can be
constructed directly.

The trick-order section is where the three retired Primitives'
(`tarot_trump_height`, `tarot_led_suit`, `tarot_trick_winner`) known values
went when the game migrated onto `trick_order { }` (issue #250 PR 5): the
declaration's rows are read off the same materialized table every consumer
reads, over the whole pack rather than at sampled cards. The CONSTRUCT's own
cells (what a row may read, which names it gates, the winner's comparison)
belong to tests/test_trick_order.py's grid; what belongs here is French
Tarot's numbers.
"""

from __future__ import annotations

import random
from functools import cache
from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.runtime import narrowing, reads
from cardlang.runtime.driver import declared_primitives, declared_trick_order
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.tarot import (
    tarot_card_points,
    tarot_excuse_player,
    tarot_per_opp,
)
from cardlang.runtime.trick_order import TrickOrderTable
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


# --- the declared Trick Order ---
#
# `tarot_trump_height`, `tarot_led_suit` and `tarot_trick_winner` retired into
# the game's own `trick_order { }` block (issue #250 PR 5). Their published
# values became the block's, so the known-value pin moves here rather than
# being dropped -- and it is DERIVED over the pack instead of sampled, because
# the row that replaced the height Primitive is the corpus's first with a
# per-rank chain, where a single wrong arm is exactly what a handful of
# examples misses.


# A bundle materialises ONE entry's declared row, and the two entries declare
# opposite extremes -- everything the settlement scores, and nothing at all --
# so each fixture binds the row of the primitive it calls. The state a fixture
# declares is the union, since `_tarot_rs` serves both.
_Bundles = tuple[narrowing.EngineFacts, reads.GameReads]


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


TAROT = Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"


@cache
def _row(primitive: str) -> reads.PrimitiveReads:
    """The row the game's own `primitives { }` block declares for `primitive`,
    built through the driver's one load site -- so a fixture cannot bind a row
    the game does not declare, and this file holds no second copy of the
    clause to drift from it."""
    entries = declared_primitives(check_source(TAROT))
    assert entries is not None, "french-tarot declares a `primitives { }` block"
    return entries[primitive].row


def _trick_order_ctx() -> tuple[TrickOrderTable, Ctx]:
    """The game's materialized Trick Order, and a context its rows can be
    asked under -- the same table every consumer reads, built by the driver's
    one load site."""
    rs = _tarot_rs()
    game = check_source(TAROT)
    table = declared_trick_order(game)
    assert table is not None, "french-tarot declares a `trick_order { }` block"
    rs.trick_order = table
    # The `card_strength:` row reaches the game's own `numeral` function, so
    # the fixture loads the function index exactly as the driver does.
    rs.function_index = {f.name: f for f in game.functions}
    return table, Ctx(rs=rs, chooser=lambda p, cands, n: list(cands)[:n])


def _expected_strength(c: Card) -> int:
    """The row's value, written from the game file's prose rather than its
    expression: the Excuse is class-less and sits under everything, the
    twenty-one atouts band above every plain card, and a plain card keeps
    K > Q > Cavalier > J > 10 > ... > 1."""
    if c.suit == "excuse":
        return 0
    if c.suit == "atouts":
        return 100 + int(c.rank)
    return {"K": 14, "Q": 13, "C": 12, "J": 11}.get(c.rank) or int(c.rank)


def test_the_three_rows_value_every_card_of_the_pack() -> None:
    table, ctx = _trick_order_ctx()
    for c in build_deck("tarot78"):
        assert table.is_trump(c, ctx) == (c.suit == "atouts"), c
        assert table.follow_class(c, ctx) == (
            None if c.suit == "excuse" else c.suit
        ), c
        assert table.card_strength(c, ctx) == _expected_strength(c), c


def test_the_excuse_is_the_pack_s_only_class_less_card() -> None:
    """What makes "the Excuse never wins" fall out of the kernel rather than
    being asserted anywhere: a card that is neither a trump nor of the
    effective lead's class is never a candidate, and the Excuse is the only
    card in the pack with no class at all."""
    table, ctx = _trick_order_ctx()
    class_less = [
        c
        for c in build_deck("tarot78")
        if not table.is_trump(c, ctx) and table.follow_class(c, ctx) is None
    ]
    assert class_less == [Card("Excuse", "excuse")]


def test_every_atout_outranks_every_plain_card_and_the_excuse() -> None:
    """The band `MustOverTrump` rests on. That rule compares a candidate
    against the pile's BEST card without first asking whether that card is a
    trump, which is sound only while no plain card and no Excuse can outrank
    an atout -- so the banding is load-bearing legality, not presentation."""
    table, ctx = _trick_order_ctx()
    atouts = [c for c in build_deck("tarot78") if c.suit == "atouts"]
    others = [c for c in build_deck("tarot78") if c.suit != "atouts"]
    assert min(table.card_strength(c, ctx) for c in atouts) > max(
        table.card_strength(c, ctx) for c in others
    )


# --- tarot_excuse_player ---


def _excuse_ctx(played: list[tuple[int, Card]], live_round: bool) -> _Bundles:
    rs = _tarot_rs()
    state = {"played": played}
    if live_round:
        rs.mech_state.append(state)
    else:
        rs.last_round_state = state
    return narrowing.bind(rs, None, _row("tarot_excuse_player"))


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
    return narrowing.bind(rs, None, _row("tarot_per_opp"))


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
