"""The multi-parameter fold: `concrete_moves` enumerates a move type's
guard-filtered cross product (arity-N), `param_domain` supplies each
parameter's value-domain, and `bind_params` binds a candidate's value(s) as
locals for guard/effect evaluation. This is the runtime half of declared
move-parameter domains — the static surface (grammar, `enumerate_domain`) is
covered elsewhere; this file exercises the fold itself.

The `Ctx`/`RuntimeState` here is built directly (not via `play_game`): these
helpers read only `rs.seating`, `rs.rank_index`, and `rs.suits` (never the
chooser, and zones only for a `Card`-typed param, which none of these test
moves use), so the full dealing/phase-loop scaffolding `play_game` sets up is
not needed. The `MoveTypeDef`s under test come from a real `check_dsl` pass
(not hand-built AST) so their guards carry properly resolved `NameRef`s
(`actor` as a pronoun, params as scoped locals) exactly as a real game would
see them — the game below declares `ping`/`bid_or_notrump` standalone,
referenced by no `offer`/`round`, so this file exercises the runtime fold in
isolation without needing a full vocabulary/round wiring in the game (that
wiring, and the closed set of accepted/rejected parameter domains it
enforces, is tests/test_resolve_param_domains.py's concern).
"""

from __future__ import annotations

import random

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import DECKS, Seating

GAME = """
game G {
  players: 3
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0  rounds : Integer = 0 }
  phase play repeats until rounds >= 3 {
    before_each { rounds += 1 }
    for each player p: coins[p] += 1
  }
  winner: highest coins
}

move_type ping(target : Player, rank : Rank) {
  when: target != actor
  effect { coins[actor] += 1 }
}

move_type bid_or_notrump(strain : Suit?) {
  // Reflexive on purpose: forces a dereference of `strain` (even when its
  // value is None, the no-trump candidate) without filtering anything out,
  // so a `bind_params` that fails to bind an arity-1 None value raises
  // KeyError here instead of silently passing.
  when: strain == strain
  effect { coins[actor] += 1 }
}
"""


def _build_ctx(game: n.Game, actor: int) -> Ctx:
    """A minimal runtime context for calling the move-parameter helpers
    directly, mirroring the fields `driver.play_game` sets up (seating,
    rank_index, suits) without its dealing/phase-loop machinery."""
    seating = Seating(game.players.low)
    zones = ZoneStore(game.zones, seating.players)
    rng = random.Random(0)
    rs = RuntimeState(seating, zones, rng)
    rs.rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    rs.suits = DECKS[game.deck].suits
    rs.move_type_index = {m.name: m for m in game.move_types}
    ctx = Ctx(rs=rs, chooser=random_chooser(rng))
    return ctx.acting_as(actor)


def test_concrete_moves_is_the_guard_filtered_cross_product() -> None:
    from cardlang.runtime.mechanics import concrete_moves

    game = check_dsl(GAME, "g.cardlang")
    mt_ping = next(m for m in game.move_types if m.name == "ping")
    ctx = _build_ctx(game, actor=0)

    cands = concrete_moves(mt_ping, actor=0, ctx=ctx)

    assert len(cands) == 2 * 13  # 2 targets (players 1, 2) x 13 ranks
    assert all(name == "ping" for name, _ in cands)
    assert all(isinstance(v, tuple) and len(v) == 2 for _, v in cands)  # arity-2
    assert all(v[0] != 0 for _, v in cands)  # target != actor, the guard
    assert {v[0] for _, v in cands} == {1, 2}
    assert {v[1] for _, v in cands} == set(game.ranking)


def test_concrete_moves_arity_one_stays_bare_including_the_none_value() -> None:
    """The `_pack` arity rule: arity-1 candidates carry the bare value, never a
    1-tuple — existing single-parameter auctions (Bridge's `submit_bid`,
    Pinochle/Skat's trump declares, Schnapsen's marriage) depend on this for
    byte-identical vocabulary keys. `Suit?`'s domain legitimately includes
    `None` (no-trump) as a VALUE, distinct from a nullary candidate's `None` —
    both must survive guard evaluation without a bare-value/nullary mixup."""
    from cardlang.runtime.mechanics import concrete_moves

    game = check_dsl(GAME, "g.cardlang")
    mt = next(m for m in game.move_types if m.name == "bid_or_notrump")
    ctx = _build_ctx(game, actor=0)

    cands = concrete_moves(mt, actor=0, ctx=ctx)

    suits = DECKS[game.deck].suits
    assert len(cands) == len(suits) + 1  # every suit, plus None (no-trump)
    for name, value in cands:
        assert name == "bid_or_notrump"
        assert not isinstance(value, tuple)  # bare, never a 1-tuple
    assert set(suits) <= {v for _, v in cands}
    assert any(value is None for _, value in cands)  # no-trump survived the guard


def test_concrete_moves_nullary_is_the_empty_product() -> None:
    """Nullary is the empty-product case: `itertools.product()` over zero
    domains yields exactly one (empty) combo, so a nullary move produces one
    `(name, None)` candidate when its guard holds (or is absent), and none
    when a guard rejects it."""
    from cardlang.runtime.mechanics import concrete_moves

    game = check_dsl(GAME, "g.cardlang")
    ctx = _build_ctx(game, actor=0)

    unguarded = n.MoveTypeDef(name="always", guard=None, effect=())
    assert concrete_moves(unguarded, actor=0, ctx=ctx) == [("always", None)]

    always_false = n.MoveTypeDef(name="never", guard=n.NameRef("false", ref_kind="bool"), effect=())
    assert concrete_moves(always_false, actor=0, ctx=ctx) == []


def test_bind_params_disambiguates_nullary_from_arity_one_none_by_arity() -> None:
    """The regression this task must not reintroduce: an arity-1 `Suit?`
    domain's `None` value (no-trump) must bind, exactly like any other value —
    `bind_params` must key off `len(params)`, never off `value is None`
    (that check order would silently drop the binding, and any guard/effect
    read of the param would then raise `KeyError`)."""
    from cardlang.runtime.mechanics import bind_params

    game = check_dsl(GAME, "g.cardlang")
    mt = next(m for m in game.move_types if m.name == "bid_or_notrump")
    ctx = _build_ctx(game, actor=0)

    bound = bind_params(ctx, mt.params, None)
    assert bound.locals["strain"] is None  # bound, not merely absent-and-defaulted

    nullary_ctx = bind_params(ctx, (), None)
    assert nullary_ctx.locals == {}  # truly nullary: nothing to bind
