"""Execution semantics of the movement `where` filter (cardlang/runtime/execute.py
`_select_filtered`): the pool is the source's matching cards in source order;
`chosen`/`random` draw from that narrowed pool; the default (dealt) form takes
the pool's first `count` — first MATCH, not top-of-source; `all` takes every
match and leaves the rest; an over-large count fails loudly, like the
unfiltered form.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.execute import execute
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

HEARTS_A = Card("A", "hearts")
HEARTS_2 = Card("2", "hearts")
CLUBS_K = Card("K", "clubs")


def _parse(stmt_src: str) -> tuple[n.Game, n.Movement]:
    src = f"""
game Mini {{
  players: 1
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    {stmt_src}
  }}
  winner: highest score
}}
"""
    game = check_dsl(src, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.Movement)
    return game, stmt


def _ctx(game: n.Game, hand_cards: list[Card], chooser: Any) -> Ctx:
    rs = RuntimeState(Seating(1), ZoneStore(game.zones, (0,)), random.Random(0))
    rs.zones.instance("hand", 0).add_all(hand_cards)
    return Ctx(rs=rs, chooser=chooser).acting_as(0)


def test_chosen_draws_from_the_filtered_pool_only() -> None:
    game, stmt = _parse(
        "move chosen 2 cards from hand[0] where card.suit is hearts to pile"
    )
    seen_candidates: list[Any] = []

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        seen_candidates.extend(candidates)
        return list(candidates[:k])

    ctx = _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2], chooser)
    execute(stmt, ctx)

    # The chooser was offered only the two hearts, in hand order — never the club.
    assert seen_candidates == [HEARTS_A, HEARTS_2]
    assert set(ctx.rs.zones.single("pile").cards) == {HEARTS_A, HEARTS_2}
    # The non-matching club was never touched.
    assert ctx.rs.zones.instance("hand", 0).cards == [CLUBS_K]


def test_default_form_takes_the_pools_first_match_not_top_of_source() -> None:
    game, stmt = _parse(
        "move one cards from hand[0] where card.suit is hearts to pile"
    )
    # The club sits first in the hand; the filter must skip it and take the
    # first HEART, not the first card of the unfiltered source.
    ctx = _ctx(game, [CLUBS_K, HEARTS_A, HEARTS_2], chooser=None)
    execute(stmt, ctx)

    assert ctx.rs.zones.single("pile").cards == [HEARTS_A]
    assert ctx.rs.zones.instance("hand", 0).cards == [CLUBS_K, HEARTS_2]


def test_all_takes_every_match_and_leaves_the_rest() -> None:
    game, stmt = _parse(
        "move all cards from hand[0] where card.suit is hearts to pile"
    )
    ctx = _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2], chooser=None)
    execute(stmt, ctx)

    assert ctx.rs.zones.single("pile").cards == [HEARTS_A, HEARTS_2]
    assert ctx.rs.zones.instance("hand", 0).cards == [CLUBS_K]


def test_random_draws_from_the_filtered_pool_only() -> None:
    game, stmt = _parse(
        "move random 1 cards from hand[0] where card.suit is hearts to pile"
    )
    ctx = _ctx(game, [CLUBS_K, HEARTS_A, HEARTS_2], chooser=None)
    execute(stmt, ctx)

    # Only a heart could ever be drawn, no matter the RNG stream.
    picked = ctx.rs.zones.single("pile").cards
    assert len(picked) == 1 and picked[0].suit == "hearts"
    assert CLUBS_K in ctx.rs.zones.instance("hand", 0).cards


def test_fail_loud_when_the_filtered_pool_is_too_small() -> None:
    game, stmt = _parse(
        "move 2 cards from hand[0] where card.suit is hearts to pile"
    )
    ctx = _ctx(game, [HEARTS_A, CLUBS_K], chooser=None)  # only one heart available
    with pytest.raises(OwnerGuardError):
        execute(stmt, ctx)


def test_unfiltered_movement_is_unaffected() -> None:
    game, stmt = _parse("move chosen 1 cards from hand[0] to pile")
    assert stmt.filter is None

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        return list(candidates[:k])

    ctx = _ctx(game, [HEARTS_A, CLUBS_K], chooser)
    execute(stmt, ctx)
    assert ctx.rs.zones.single("pile").cards == [HEARTS_A]
    assert ctx.rs.zones.instance("hand", 0).cards == [CLUBS_K]


# --- The filter on a round-robin (`as-equally-as-possible to each`) deal. The
# round-robin path (`_deal_round_robin`) is separate from `_select`, so it must
# honor the filter too — otherwise a filtered round-robin deal silently deals the
# whole source. ---

SPADES_3 = Card("3", "spades")


def _parse_deal(n_players: int, stmt_src: str) -> tuple[n.Game, n.Movement]:
    src = f"""
game Mini {{
  players: {n_players}
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    {stmt_src}
  }}
  winner: highest score
}}
"""
    game = check_dsl(src, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.Movement)
    return game, stmt


def _deal_ctx(game: n.Game, n_players: int, deck_cards: list[Card]) -> Ctx:
    players = tuple(range(n_players))
    rs = RuntimeState(
        Seating(n_players), ZoneStore(game.zones, players), random.Random(0)
    )
    rs.zones.single("deck").add_all(deck_cards)
    # A round-robin deal never draws; the chooser is present but unused.
    return Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))


def test_filtered_round_robin_deals_only_the_matching_subset() -> None:
    game, stmt = _parse_deal(
        2,
        "deal all cards from deck where card.suit is hearts "
        "as-equally-as-possible to each hand",
    )
    ctx = _deal_ctx(game, 2, [HEARTS_A, CLUBS_K, HEARTS_2, SPADES_3])
    execute(stmt, ctx)

    # Only the two hearts are dealt, round-robin in source order (p0 first).
    assert ctx.rs.zones.instance("hand", 0).cards == [HEARTS_A]
    assert ctx.rs.zones.instance("hand", 1).cards == [HEARTS_2]
    # The non-hearts are left untouched in the deck, in order.
    assert ctx.rs.zones.single("deck").cards == [CLUBS_K, SPADES_3]


def test_filtered_to_each_draws_each_players_pick_from_the_pool() -> None:
    # The non-round-robin `to each` form goes through _select per player, so the
    # filter narrows each player's candidate pool — and the pool shrinks as
    # earlier players take from it.
    game, stmt = _parse_deal(
        2,
        "deal chosen 1 cards from deck where card.suit is hearts to each hand",
    )
    seen: list[tuple[int, int, int]] = []

    def chooser(p: int, c: list[Any], k: int) -> list[Any]:
        seen.append((p, len(c), k))
        return list(c[:k])

    ctx = _deal_ctx(game, 2, [HEARTS_A, CLUBS_K, HEARTS_2, SPADES_3])
    ctx = Ctx(rs=ctx.rs, chooser=chooser)
    execute(stmt, ctx)

    # Each player chose from the hearts-only pool; the pool shrank 2 -> 1.
    assert seen == [(0, 2, 1), (1, 1, 1)]
    assert ctx.rs.zones.instance("hand", 0).cards == [HEARTS_A]
    assert ctx.rs.zones.instance("hand", 1).cards == [HEARTS_2]
    assert ctx.rs.zones.single("deck").cards == [CLUBS_K, SPADES_3]


def test_unfiltered_round_robin_still_deals_the_whole_source() -> None:
    game, stmt = _parse_deal(
        2, "deal all cards from deck as-equally-as-possible to each hand"
    )
    assert stmt.filter is None
    ctx = _deal_ctx(game, 2, [HEARTS_A, CLUBS_K, HEARTS_2, SPADES_3])
    execute(stmt, ctx)

    # Whole deck round-robin (unchanged byte-for-byte): p0 gets 1st+3rd, p1 gets
    # 2nd+4th, the deck is emptied.
    assert ctx.rs.zones.instance("hand", 0).cards == [HEARTS_A, HEARTS_2]
    assert ctx.rs.zones.instance("hand", 1).cards == [CLUBS_K, SPADES_3]
    assert ctx.rs.zones.single("deck").cards == []
