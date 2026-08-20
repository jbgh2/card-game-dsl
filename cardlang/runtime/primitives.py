"""[[primitive]]s: the sanctioned game-local Python.

A Primitive is native code whose meaning belongs to ONE game — Skat's trick
winner, Canasta's pile-take legality, Belote's declaration classes. Its inputs
are the **facts** (`narrowing.EngineFacts`) and its declared **reads**
(`reads.GameReads`); the pair is the [[primitive-bundle]]. The arms below are
the dispatch seam, and their count is the elimination metric: it trends to zero
as `design-notes/primitive-inventory.md`'s constructs land in the language.

Its two siblings are deliberately separate words: **[[builtins]]** are the
generic native functions the language ships (`cardlang/runtime/builtins.py`),
and the **[[stdlib]]** is the layer written in the language itself
(`cardlang/stdlib/`).

Contract
--------
Assumes: `name` reached resolve's registries and its arguments were coerced by
the caller (`reads.coerce_args`) — this module never freezes an argument
itself, and `_bind` hands a game module only what its declared-reads row
permits.
Establishes: a value for every game-local call, or the loud refusal below.
Illegal after: reading engine state by any route other than a declared row.

This module must not import `runtime/builtins.py`. Which half of the registry a
name belongs to is the caller's question (`runtime/evaluate.py`), and keeping
the dependency absent is what makes the two arm counts independently readable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cardlang.runtime import narrowing, reads, winners
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# This module's per-game functions (the auction outcomes; the pegging-scorer
# call sites) read state on behalf of specific games — one declared-reads row
# per game served (cardlang/runtime/reads.py).
_BRIDGE_R = reads.row("cardlang/runtime/primitives.py", "bridge.cardlang")
_CRIBBAGE_R = reads.row("cardlang/runtime/primitives.py", "cribbage.cardlang")
_PINOCHLE_R = reads.row("cardlang/runtime/primitives.py", "pinochle.cardlang")
_TAROT_R = reads.row("cardlang/runtime/primitives.py", "french-tarot.cardlang")


def _bind(
    ctx: Ctx, row: reads.PrimitiveReads
) -> tuple[narrowing.EngineFacts, reads.GameReads]:
    """The two value bundles for one narrowed primitive call."""
    return narrowing.bind(ctx.rs, ctx.current_player, row)


def _emit(ctx: Ctx, events: tuple[narrowing.TraceEvent, ...]) -> None:
    """Perform a narrowed primitive's deferred trace emissions. A game module
    holds no tracer, so the events travel back as data and are emitted here,
    in the order the primitive returned them (cardlang/runtime/narrowing.py)."""
    for event, payload in events:
        ctx.trace(event, payload)


def call(name: str, args: list[Any], ctx: Ctx) -> Any:
    """Dispatch a game-local native call. Arguments arrive already coerced."""
    match name:
        case "bring_in_seat":
            from cardlang.runtime.stud import ROW, bring_in_seat

            return bring_in_seat(*_bind(ctx, ROW))
        case "first_to_act_seat":
            from cardlang.runtime.stud import ROW, first_to_act_seat

            return first_to_act_seat(*_bind(ctx, ROW))
        case "pot_share":
            from cardlang.runtime.stud import ROW, pot_share

            return pot_share(*_bind(ctx, ROW), args[0])
        case "holdem_pot_share":
            from cardlang.runtime.holdem import ROW, holdem_pot_share

            return holdem_pot_share(*_bind(ctx, ROW), args[0])
        case "holdem_heads_up_pot_share":
            from cardlang.runtime.holdem_heads_up import (
                ROW,
                holdem_heads_up_pot_share,
            )

            return holdem_heads_up_pot_share(*_bind(ctx, ROW), args[0])
        case "pinochle_meld_value":
            from cardlang.runtime.pinochle import ROW, pinochle_meld_value

            return pinochle_meld_value(*_bind(ctx, ROW), args[0])
        case "tarot_led_suit":
            from cardlang.runtime.tarot import ROW, tarot_led_suit

            return tarot_led_suit(*_bind(ctx, ROW))
        case "tarot_trump_height":
            from cardlang.runtime.tarot import tarot_trump_height

            return tarot_trump_height(args[0])
        case "tarot_excuse_player":
            from cardlang.runtime.tarot import ROW, tarot_excuse_player

            return tarot_excuse_player(*_bind(ctx, ROW))
        case "tarot_per_opp":
            from cardlang.runtime.tarot import ROW, tarot_per_opp

            return tarot_per_opp(*_bind(ctx, ROW), args[0])
        case "skat_next_bid":
            from cardlang.runtime.skat import skat_next_bid

            return skat_next_bid(args[0])
        case "skat_matadors":
            from cardlang.runtime.skat import ROW, skat_matadors

            return skat_matadors(*_bind(ctx, ROW), args[0])
        case "tichu_dragon_won":
            from cardlang.runtime.tichu import ROW, tichu_dragon_won

            return tichu_dragon_won(*_bind(ctx, ROW))
        case "coup_game_summary":
            from cardlang.runtime.coup import ROW, coup_game_summary

            total, events = coup_game_summary(*_bind(ctx, ROW))
            _emit(ctx, events)
            return total
        case "peg_pair_points":
            from cardlang.runtime.cribbage import peg_pair_points

            # These two read live engine state directly rather than through a
            # bundle, so their collection args are frozen here at the call site
            # (the same boundary `reads.coerce_args` enforces for DSL arguments).
            return peg_pair_points(
                reads.deep_freeze(reads.single(ctx.rs, _CRIBBAGE_R, "play_pile").cards)
            )
        case "peg_run_points":
            from cardlang.runtime.cribbage import peg_run_points

            return peg_run_points(
                reads.deep_freeze(reads.single(ctx.rs, _CRIBBAGE_R, "play_pile").cards),
                reads.deep_freeze(ctx.rs.rank_index),
            )
        case "peg_origin_of":
            from cardlang.runtime.cribbage import ROW, peg_origin_of

            return peg_origin_of(*_bind(ctx, ROW), args[0])
        case "cribbage_show_value":
            from cardlang.runtime.cribbage import ROW, cribbage_show_value

            return cribbage_show_value(*_bind(ctx, ROW), args[0])
        case "cribbage_crib_value":
            from cardlang.runtime.cribbage import ROW, cribbage_crib_value

            return cribbage_crib_value(*_bind(ctx, ROW))
        case "gin_deadwood":
            from cardlang.runtime.gin import ROW, gin_deadwood

            return gin_deadwood(*_bind(ctx, ROW), args[0])
        case "gin_can_knock":
            from cardlang.runtime.gin import ROW, gin_can_knock

            return gin_can_knock(*_bind(ctx, ROW), args[0])
        case "gin_knock_ok":
            from cardlang.runtime.gin import ROW, gin_knock_ok

            return gin_knock_ok(*_bind(ctx, ROW), args[0], args[1])
        case "gin_valid_meld":
            from cardlang.runtime.gin import ROW, gin_valid_meld

            return gin_valid_meld(*_bind(ctx, ROW), args[0])
        case "gin_arrange_ok":
            from cardlang.runtime.gin import ROW, gin_arrange_ok

            return gin_arrange_ok(*_bind(ctx, ROW), args[0], args[1])
        case "gin_can_declare":
            from cardlang.runtime.gin import ROW, gin_can_declare

            return gin_can_declare(*_bind(ctx, ROW), args[0])
        case "gin_can_declare_free":
            from cardlang.runtime.gin import ROW, gin_can_declare_free

            return gin_can_declare_free(*_bind(ctx, ROW), args[0])
        case "gin_lay_ok_a":
            from cardlang.runtime.gin import ROW, gin_lay_ok_a

            return gin_lay_ok_a(*_bind(ctx, ROW), args[0], args[1])
        case "gin_lay_ok_b":
            from cardlang.runtime.gin import ROW, gin_lay_ok_b

            return gin_lay_ok_b(*_bind(ctx, ROW), args[0], args[1])
        case "gin_lay_ok_c":
            from cardlang.runtime.gin import ROW, gin_lay_ok_c

            return gin_lay_ok_c(*_bind(ctx, ROW), args[0], args[1])
        case "five_hundred_next_bid":
            from cardlang.runtime.five_hundred import five_hundred_next_bid

            return five_hundred_next_bid(args[0], args[1])
        case "five_hundred_bid_value":
            from cardlang.runtime.five_hundred import five_hundred_bid_value

            return five_hundred_bid_value(args[0])
        case "five_hundred_bid_level":
            from cardlang.runtime.five_hundred import five_hundred_bid_level

            return five_hundred_bid_level(args[0])
        case "belote_royal_player":
            from cardlang.runtime.belote import ROW, belote_royal_player

            return belote_royal_player(*_bind(ctx, ROW))
        case "belote_best_is":
            from cardlang.runtime.belote import ROW, belote_best_is

            return belote_best_is(*_bind(ctx, ROW), args[0], args[1], args[2], args[3])
        case "belote_decl_points":
            from cardlang.runtime.belote import ROW, belote_decl_points

            return belote_decl_points(*_bind(ctx, ROW), args[0])
        case "belote_decl_class":
            from cardlang.runtime.belote import ROW, belote_decl_class

            return belote_decl_class(*_bind(ctx, ROW), args[0])
        case "belote_decl_height":
            from cardlang.runtime.belote import ROW, belote_decl_height

            return belote_decl_height(*_bind(ctx, ROW), args[0])
        case "belote_decl_trump":
            from cardlang.runtime.belote import ROW, belote_decl_trump

            return belote_decl_trump(*_bind(ctx, ROW), args[0])
        case "belote_decl_size":
            from cardlang.runtime.belote import ROW, belote_decl_size

            return belote_decl_size(*_bind(ctx, ROW), args[0])
        case "belote_decl_slot":
            from cardlang.runtime.belote import ROW, belote_decl_slot

            return belote_decl_slot(*_bind(ctx, ROW), args[0], args[1], args[2])
        case "canasta_can_take_pile":
            from cardlang.runtime.canasta import ROW, canasta_can_take_pile

            return canasta_can_take_pile(*_bind(ctx, ROW), args[0])
        case "canasta_must_take_pile":
            from cardlang.runtime.canasta import ROW, canasta_must_take_pile

            return canasta_must_take_pile(*_bind(ctx, ROW), args[0])
        case "canasta_can_start":
            from cardlang.runtime.canasta import ROW, canasta_can_start

            return canasta_can_start(*_bind(ctx, ROW), args[0], args[1])
        case "canasta_stage_ok":
            from cardlang.runtime.canasta import ROW, canasta_stage_ok

            return canasta_stage_ok(*_bind(ctx, ROW), args[0], args[1])
        case "canasta_close_ok":
            from cardlang.runtime.canasta import ROW, canasta_close_ok

            return canasta_close_ok(*_bind(ctx, ROW), args[0])
        case "canasta_canasta_bonus":
            from cardlang.runtime.canasta import ROW, canasta_canasta_bonus

            return canasta_canasta_bonus(*_bind(ctx, ROW), args[0])
        case _:
            raise AssertionError(
                f"unknown native function '{name}' — neither a Builtin "
                f"(cardlang/runtime/builtins.py) nor a Primitive"
            )


# --- value-callbacks (mechanic functions passed by name) ---

# The Builtin winner comparisons (`BUILTIN_TRICK_WINNERS`) live in
# `runtime/winners.py` — both dispatch halves consume them and may not import
# each other. `value_function` below is the ONE winner-slot dispatcher and
# keys both homes' winners (the Builtins through winners.py, the game-local
# pair through their modules); its file is the dispatcher's home, not a
# classification of what it keys (tests/test_native_dispatch_split.py).
#
# It returns callables under one of TWO contracts, keyed by
# `TRICK_ORDER_GATED_WINNERS` (cardlang/builtins/functions.py):
#
# * the UNIFORM contract, `OutcomeFn` below — (played, led_suit, trump,
#   rank_index) -> Player — for every winner whose comparison is configured by
#   the ROUND;
# * the TRICK ORDER contract, `trick_order.TrickOrderWinner` — (played, ctx)
#   -> Player — for the winner whose trumps, classes and strengths are the
#   GAME's `trick_order { }` rows, which need a ctx to evaluate under.
#
# The caller (`mechanics.TrickForm.outcome`) selects the contract from the
# registry and then invokes what THIS function returned, so the dispatcher
# stays the single site that maps a name to an implementation.
RankIndex = winners.RankIndex
OutcomeFn = Callable[[list[tuple[Player, Card]], str, "str | None", RankIndex], Player]
# An early-termination predicate: does this play end the trick? (card, led_suit)
EarlyTermFn = Callable[[Card, str], bool]


def value_function(name: str) -> Callable[..., Any]:
    match name:
        case "highest_of_led_suit":
            return winners.highest_of_led_suit
        case "highest_trump_or_led_suit":
            return winners.highest_trump_or_led_suit
        case "highest_by_trick_order":
            from cardlang.runtime.trick_order import TrickOrderWinner

            return TrickOrderWinner()
        case "on_play_off_led_suit":
            return on_play_off_led_suit
        case "tarot_trick_winner":
            from cardlang.runtime.tarot import tarot_trick_winner

            return tarot_trick_winner
        case _:
            raise AssertionError(f"unknown Primitive value callback '{name}'")


# --- climbing-form combination-engine queries (named on a `round climb`) ---
#
# A *lead* query returns every combination a hand may lead; a *follows* query
# returns those that beat the standing play. Both take the runtime ctx (a lead
# query may read game state, e.g. Big Two's opening 3♦ filter). The engines are
# game-local, so these dispatch to per-game modules.


ClimbLeadFn = Callable[[narrowing.EngineFacts, reads.GameReads, list[Card]], list[Any]]
ClimbFollowFn = Callable[
    [narrowing.EngineFacts, reads.GameReads, list[Card], Any], list[Any]
]


def climb_row(name: str) -> reads.PrimitiveReads:
    """The declared-reads row of the module implementing a climb query.
    Climb queries are named on a `round climb` and invoked by the round
    machinery rather than through `call`, so the binder needs their row
    from here — keyed by the LEAD query's name, the same key
    `climb_universe_function` uses."""
    match name:
        case "bigtwo_lead_options" | "bigtwo_follows":
            from cardlang.runtime.bigtwo import ROW

            return ROW
        case "tichu_lead_options" | "tichu_follows":
            from cardlang.runtime.tichu import ROW

            return ROW
        case "president_lead_options" | "president_follows":
            from cardlang.runtime.president import ROW

            return ROW
        case _:
            raise AssertionError(f"unknown climb query '{name}'")


def climb_lead_function(name: str) -> ClimbLeadFn:
    match name:
        case "bigtwo_lead_options":
            from cardlang.runtime.bigtwo import bigtwo_lead_options

            return bigtwo_lead_options
        case "tichu_lead_options":
            from cardlang.runtime.tichu import tichu_lead_options

            return tichu_lead_options
        case "president_lead_options":
            from cardlang.runtime.president import president_lead_options

            return president_lead_options
        case _:
            raise AssertionError(f"unknown climb lead query '{name}'")


def climb_follow_function(name: str) -> ClimbFollowFn:
    match name:
        case "bigtwo_follows":
            from cardlang.runtime.bigtwo import bigtwo_follows

            return bigtwo_follows
        case "tichu_follows":
            from cardlang.runtime.tichu import tichu_follows

            return tichu_follows
        case "president_follows":
            from cardlang.runtime.president import president_follows

            return president_follows
        case _:
            raise AssertionError(f"unknown climb follows query '{name}'")


def climb_universe_function(name: str) -> Callable[[], list[Any]]:
    """The engine's full play universe — every combination it can ever emit —
    keyed by the SAME name as its `combinations` lead query. The OpenSpiel
    adapter derives the climb action space from this; the lead query itself
    cannot serve (its representatives depend on the live hand and game state).
    An engine whose universe is too large to enumerate provides a codec via
    `climb_codec_function` instead and never reaches this dispatch."""
    match name:
        case "bigtwo_lead_options":
            from cardlang.runtime.bigtwo import bigtwo_universe

            return bigtwo_universe
        case "president_lead_options":
            from cardlang.runtime.president import president_universe

            return president_universe
        case _:
            raise AssertionError(
                f"no declared combination universe for climb engine '{name}' — "
                f"register one here or provide a codec (climb_codec_function)"
            )


def joint_codec_function(name: str) -> Any | None:
    """The subset codec for a joint selection (`where jointly`) whose
    predicate is rooted in the named call — the climb-engine codec pattern
    (`climb_codec_function` below) one construct over: pure card-set <->
    action-index functions (`size` / `encode_cards` / `decode` / `kind_of`)
    over the predicate's satisfying-subset universe. Keyed corpus-first; a
    joint predicate with no registered codec meets a loud [[owner-guard]] at
    `ActionSpace.for_game`, never silently absent from the action space."""
    match name:
        case "gin_arrange_ok" | "gin_valid_meld":
            # Both gin arrangement guards admit only valid melds, so their
            # satisfying-subset universe IS the meld universe.
            from cardlang.runtime.gin import GIN_MELD_CODEC

            return GIN_MELD_CODEC
        case _:
            return None


def climb_codec_function(name: str) -> Any | None:
    """The engine's arithmetic combo codec — pure card-set <-> action-index
    functions (`size` / `encode_cards` / `decode` / `kind_of`) — keyed by the
    lead-query name, for engines whose play universe is too large to enumerate
    (Tichu's is 211,204,694; straights dominate). `None` means the engine
    enumerates via `climb_universe_function` (Big Two: 19,898, golden-pinned),
    keeping that path and its pinned ids byte-identical."""
    match name:
        case "tichu_lead_options":
            from cardlang.runtime.tichu import TICHU_COMBO_CODEC

            return TICHU_COMBO_CODEC
        case _:
            return None


def on_play_off_led_suit(card: Card, led_suit: str) -> bool:
    """The played card fails to follow the led suit; playing one ends the
    trick early. Under a must-follow rule only a void player can do so
    (Getaway, where the highest led-suit card then picks up the pile)."""
    return card.suit != led_suit


# --- auction outcome callbacks (the auction form of `round`) -----------------
#
# An auction outcome receives the bid history (`(player, move_type, param)` per
# accepted move) and the live `Ctx` (the auction's terminal phase state and
# `team_of`), and returns the typed `(tag, payloads)` the phase's `produces:`
# consumes. It consumes no RNG — it is a pure read of the threaded state/history.

AuctionHistory = list[tuple[Player, str, Any]]
AuctionOutcomeFn = Callable[[AuctionHistory, Ctx], "tuple[str, list[Any]]"]


def auction_outcome_function(name: str) -> AuctionOutcomeFn:
    match name:
        case "bridge_auction_outcome":
            return bridge_auction_outcome
        case "pinochle_auction_outcome":
            return pinochle_auction_outcome
        case "tarot_auction_outcome":
            return tarot_auction_outcome
        case _:
            raise AssertionError(f"unknown auction outcome '{name}'")


def bridge_auction_outcome(
    history: AuctionHistory, ctx: Ctx
) -> tuple[str, list[Any]]:
    """Bridge's auction result: a pass-out, or the final contract with its
    declarer — the first player of the high-bidding side to have named the final
    strain (their left-hand opponent leads, so the exact seat matters)."""
    rs = ctx.rs
    if not reads.state(rs, _BRIDGE_R, "made_bid"):
        ctx.trace("bridge_contract", {"all_pass": True})
        return ("all_pass", [])
    high_bidder = reads.state(rs, _BRIDGE_R, "high_bidder")
    high_team = rs.team_of[high_bidder]
    strain = reads.state(rs, _BRIDGE_R, "cur_strain")
    level = reads.state(rs, _BRIDGE_R, "cur_level")
    doubled = reads.state(rs, _BRIDGE_R, "doubled")
    declarer = next(
        (
            p
            for (p, move, param) in history
            if move == "submit_bid" and param == strain and rs.team_of[p] == high_team
        ),
        None,
    )
    if declarer is None:
        # Whether the history holds the bid that set `made_bid` is runtime
        # data (both come from the hosting game's own moves and state), so a
        # mismatch is the game description's error, so this raise is its Owner Guard.
        raise OwnerGuardError(
            f"bridge auction: made_bid is set but no submit_bid in the history "
            f"names the final strain {strain!r} for the high team {high_team} "
            f"(high_bidder={high_bidder})"
        )
    ctx.trace(
        "bridge_contract",
        {
            "all_pass": False,
            "declarer_team": high_team,
            "level": level,
            "strain": strain,
            "doubled_mult": doubled,
        },
    )
    return ("contract_finalized", [declarer, level, strain, doubled])


def pinochle_auction_outcome(
    history: AuctionHistory, ctx: Ctx
) -> tuple[str, list[Any]]:
    """Pinochle's ascending auction always settles on a declarer: the standing
    high bidder at the bid he reached, or — if every seat passed without a bid —
    the opener at the minimum 50. (The bidding side must reach this in meld +
    tricks or be set back; see `pinochle.cardlang`.)"""
    rs = ctx.rs
    lead_bidder = reads.state(rs, _PINOCHLE_R, "lead_bidder")
    if lead_bidder is None:
        declarer, bid = reads.state(rs, _PINOCHLE_R, "opener"), 50
        if declarer is None:
            # Whether `opener` was set before the round is runtime data — the
            # hosting game's own setup — so its absence is the description's
            # error, so this raise is its Owner Guard.
            raise OwnerGuardError(
                "pinochle auction: all-pass fallback has no opener — the "
                "`auction` phase must set `opener := dealer offset_by left` "
                "before the round"
            )
        ctx.trace("pinochle_contract", {"all_pass": True, "declarer": declarer, "bid": bid})
        return ("bid_won", [declarer, bid])
    bid = reads.state(rs, _PINOCHLE_R, "working_bid")
    ctx.trace(
        "pinochle_contract", {"all_pass": False, "declarer": lead_bidder, "bid": bid}
    )
    return ("bid_won", [lead_bidder, bid])


def tarot_auction_outcome(
    history: AuctionHistory, ctx: Ctx
) -> tuple[str, list[Any]]:
    """French Tarot's four-level bid: the high bidder becomes the taker at the
    level he reached, or — if every seat passed — the hand is thrown in (re-dealt,
    no score). `current_level` is 1..4 (petite..garde_contre; 0 = no bid)."""
    rs = ctx.rs
    taker = reads.state(rs, _TAROT_R, "lead_taker")
    if taker is None:
        ctx.trace("tarot_contract", {"thrown_in": True})
        return ("thrown_in", [])
    level = reads.state(rs, _TAROT_R, "current_level")
    ctx.trace("tarot_contract", {"thrown_in": False, "taker": taker, "level": level})
    return ("taken", [taker, level])
