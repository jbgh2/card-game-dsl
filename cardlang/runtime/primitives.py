"""[[primitive]]s: the sanctioned game-local Python.

A Primitive is native code whose meaning belongs to ONE game — Skat's trick
winner, Canasta's pile-take legality, Belote's declaration classes. Its inputs
are the **facts** (`narrowing.EngineFacts`) and its declared **reads**
(`reads.GameReads`); the pair is the [[primitive-bundle]]. Every Primitive is
reached by DECLARATION: the calling game names it in a `primitives { }` block
and `call_declared` derives the dispatch from that. The elimination metric is
the REGISTRY (`PRIMITIVE_CALL_FUNCS`,
`design-notes/primitive-inventory.md`) — a name leaves it when the construct
that replaces its Primitive lands in the language, which is the only event
that moves Python out of the package.

Its two siblings are deliberately separate words: **[[builtins]]** are the
generic native functions the language ships (`cardlang/runtime/builtins.py`),
and the **[[stdlib]]** is the layer written in the language itself
(`cardlang/stdlib/`).

Contract
--------
Assumes: `name` reached resolve's registries and its arguments were coerced by
the caller (`reads.coerce_args`) — this module never freezes an argument
itself, and `narrowing.bind` hands a game module only what its declared-reads
row permits.
Establishes: a value for every declared call (`call_declared`); the walled
dispatchers keep their own arms.
Illegal after: reading engine state by any route other than a declared row;
an arm for a call-position Primitive anywhere — there is no dispatcher here to
add one to, and a Primitive that could be reached without a declaration would
be Python a game file never claimed.

This module must not import `runtime/builtins.py`. Which half of the registry a
name belongs to is the caller's question (`runtime/evaluate.py`), and keeping
the dependency absent is what keeps the two halves independently readable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cardlang.runtime import narrowing, reads, winners
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# This module's per-game functions (the auction outcomes) read state on behalf
# of specific games — one declared-reads row per game served
# (cardlang/runtime/reads.py).
_BRIDGE_R = reads.row("cardlang/runtime/primitives.py", "bridge.cardlang")
_PINOCHLE_R = reads.row("cardlang/runtime/primitives.py", "pinochle.cardlang")
_TAROT_R = reads.row("cardlang/runtime/primitives.py", "french-tarot.cardlang")


@dataclass(frozen=True, slots=True)
class Declared:
    """One `primitives { }` entry, materialized for dispatch.

    Everything a call needs, resolved once at load: the implementation the
    index named, the row the entry's `reads` clause declares, which of those
    reads a parameter keys, and the contract the implementation answers. There
    is no arm for a declared Primitive and there never will be — the whole
    point of the block is that the dispatch DERIVES."""

    name: str
    impl: Callable[..., Any]
    row: reads.PrimitiveReads
    binders: tuple[tuple[str, int], ...]
    """Declared read name -> the index of the parameter that keys it, for the
    indexed reads an entry narrowed (`reads hand[p]`). Empty for an entry whose
    reads are all whole."""
    bundled: bool
    """Whether the implementation takes the [[primitive-bundle]] — `False` for
    one pure over its arguments (`primitives_block.InvocationContract`)."""
    scopes: tuple[tuple[str, str], ...] = ()
    """Declared read name -> the phase that declares it, for the entry's
    [[phase-scoped-read]]s. Carried for the MESSAGE alone: materialization is
    identical either way, and resolve's containment check has already
    established that the phase is running wherever this entry is called — so
    the only use of this is to name that phase, and its Owner Guard, if the
    frame is somehow not standing."""


def call_declared(entry: Declared, args: list[Any], ctx: Ctx) -> Any:
    """Invoke one declared Primitive. Arguments arrive already coerced against
    the DECLARED signature, so what the implementation receives is what the
    game file says it receives."""
    if not entry.bundled:
        return entry.impl(*args)
    keys = {name: args[i] for name, i in entry.binders}
    return entry.impl(
        *narrowing.bind(
            ctx.rs,
            ctx.current_player,
            entry.row,
            keys,
            entry.name,
            dict(entry.scopes),
        ),
        *args,
    )


# --- value-callbacks (mechanic functions passed by name) ---

# The Builtin winner comparisons (`BUILTIN_TRICK_WINNERS`) live in
# `runtime/winners.py` — both dispatch halves consume them and may not import
# each other. `value_function` below is the ONE winner-slot dispatcher and
# keys both homes' winners: the Builtins through winners.py, and any
# game-local winner (`PRIMITIVE_TRICK_WINNERS`) through its own module. Its
# file is the dispatcher's home, not a classification of what it keys
# (tests/test_native_dispatch_split.py).
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
