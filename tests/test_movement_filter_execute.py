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
        "move chosen 2 cards from hand[0] where c => c.suit == hearts to pile"
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
        "move one cards from hand[0] where c => c.suit == hearts to pile"
    )
    # The club sits first in the hand; the filter must skip it and take the
    # first HEART, not the first card of the unfiltered source.
    ctx = _ctx(game, [CLUBS_K, HEARTS_A, HEARTS_2], chooser=None)
    execute(stmt, ctx)

    assert ctx.rs.zones.single("pile").cards == [HEARTS_A]
    assert ctx.rs.zones.instance("hand", 0).cards == [CLUBS_K, HEARTS_2]


def test_all_takes_every_match_and_leaves_the_rest() -> None:
    game, stmt = _parse(
        "move all cards from hand[0] where c => c.suit == hearts to pile"
    )
    ctx = _ctx(game, [HEARTS_A, CLUBS_K, HEARTS_2], chooser=None)
    execute(stmt, ctx)

    assert ctx.rs.zones.single("pile").cards == [HEARTS_A, HEARTS_2]
    assert ctx.rs.zones.instance("hand", 0).cards == [CLUBS_K]


def test_random_draws_from_the_filtered_pool_only() -> None:
    game, stmt = _parse(
        "move random 1 cards from hand[0] where c => c.suit == hearts to pile"
    )
    ctx = _ctx(game, [CLUBS_K, HEARTS_A, HEARTS_2], chooser=None)
    execute(stmt, ctx)

    # Only a heart could ever be drawn, no matter the RNG stream.
    picked = ctx.rs.zones.single("pile").cards
    assert len(picked) == 1 and picked[0].suit == "hearts"
    assert CLUBS_K in ctx.rs.zones.instance("hand", 0).cards


def test_fail_loud_when_the_filtered_pool_is_too_small() -> None:
    game, stmt = _parse(
        "move 2 cards from hand[0] where c => c.suit == hearts to pile"
    )
    ctx = _ctx(game, [HEARTS_A, CLUBS_K], chooser=None)  # only one heart available
    with pytest.raises(ValueError):
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
