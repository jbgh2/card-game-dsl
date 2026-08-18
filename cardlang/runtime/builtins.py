"""[[builtins]]: the generic native functions the language ships.

A Builtin's meaning belongs to the language, not to one game — a board step,
a card's rank strength under the declared ranking, the [[seat]] holding a card.
The checker declares them (`cardlang/builtins/functions.py`,
`cardlang/builtins/signatures.py`); this module implements them.

Its two siblings are deliberately separate words: **[[primitive]]s** are
sanctioned game-local Python (`cardlang/runtime/primitives.py`), and the
**[[stdlib]]** is the layer written in the language itself (`cardlang/stdlib/`).
Builtins shrink as functions become expressible and migrate into the Stdlib.

Contract
--------
Assumes: `name` reached resolve's call registry (`CALL_FUNCS`) and its
arguments were coerced by the caller (`reads.coerce_args`) — this module never
freezes an argument itself.
Establishes: a value for every generic call, or `NOT_A_BUILTIN` when the name
belongs to the Primitives half of the registry.
Illegal after: nothing — this module holds no state.

This module must not import `runtime/primitives.py`. Which half of the registry
a name belongs to is the caller's question (`runtime/evaluate.py`), and keeping
the dependency absent is what makes the two arm counts independently readable:
the Primitive count is the elimination metric, the Builtin count the irreducible
core it is measured against.
"""

from __future__ import annotations

from typing import Any

from cardlang.runtime import reads, trick_order, winners
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.state import Ctx, IllegalMove
from cardlang.runtime.values import SUITS, Card, Player, rank_strength
from cardlang.stdlib.boards import BoardEntry


class _NotABuiltin:
    """The miss sentinel's type, so the miss is a value the caller matches on
    rather than an exception it catches — a name outside this half is ordinary
    control flow, not an error."""

    def __repr__(self) -> str:
        return "NOT_A_BUILTIN"


NOT_A_BUILTIN = _NotABuiltin()


def call(name: str, args: list[Any], ctx: Ctx) -> Any:
    """Dispatch a generic native call, or `NOT_A_BUILTIN` if the name is not
    one. Arguments arrive already coerced."""
    match name:
        case "lines":
            return _lines(ctx, args[0])
        case "neighbor":
            return _neighbor(ctx, args[0], args[1], args[2])
        case "has_step":
            return _has_step(ctx, args[0], args[1], args[2])
        case "is_diagonal":
            return _is_diagonal(ctx, args[0])
        case "home":
            return _home(ctx, args[0])
        case "far_row":
            return _far_row(ctx, args[0])
        case "player_holding":
            return _player_holding(args[0], ctx)
        case "team_of":
            return ctx.rs.team_of[args[0]]
        case "suit_of":
            return _suit_of(args[0])
        case "strain_index":
            return _strain_index(args[0])
        case "error":
            raise IllegalMove(args[0] if args else "illegal move")
        case "rank_value":
            # `rank_strength` is the Owner Guard for a rank outside a partial
            # `ranking:` (a runtime fact -- which cards reach the read); the
            # no-`ranking:` case is typecheck's RANKING_GATED_FUNCS gate.
            return rank_strength(ctx.rs.rank_index, args[0].rank, "rank_value")
        case "card_points":
            # Total by construction: the driver materialized the declared
            # `card_points { }` table over every deck rank (unlisted ranks at
            # the else value, or 0), and resolve's clause-required guard
            # refuses the call in a game with no table — so a plain subscript,
            # never a defaulted get that would re-derive either fact.
            return ctx.rs.card_points[args[0].rank]
        case "top_of":
            return _end_card(args[0], "top_of", -1)
        case "bottom_of":
            return _end_card(args[0], "bottom_of", 0)
        case "highest_trump_or_led_suit":
            return _pile_trick_winner(args[0], args[1], ctx)
        # The Trick Order's five (decisions.md "Trick Order"). The three
        # readers answer from the table the driver materialized; the two
        # Builtins over the declaration delegate to the neutral module. None
        # of the five emits a `trick` trace: a call form's read may be
        # mid-trick (the winner so far, issue #350), and a trace there would
        # announce trick ends that did not happen (issue #250 PR 1, ruled
        # point 7) -- the round form's `outcome` keeps its trace.
        case "is_trump":
            return bool(_trick_order_table(ctx, "is_trump").is_trump(args[0], ctx))
        case "follow_class":
            return _trick_order_table(ctx, "follow_class").follow_class(args[0], ctx)
        case "card_strength":
            return _trick_order_table(ctx, "card_strength").card_strength(args[0], ctx)
        case "follows_lead":
            return trick_order.follows_lead_over_pile(args[0], args[1], ctx)
        case "highest_by_trick_order":
            return trick_order.winner_over_pile(args[0], ctx)
        case _:
            return NOT_A_BUILTIN


def _trick_order_table(ctx: Ctx, reader: str) -> trick_order.TrickOrderTable:
    """The materialized [[trick-order]] a minted reader reads. [[shadow-guard]]
    behind resolve's presence partition, which refuses every reader in a game
    declaring no block."""
    return trick_order.table_of(ctx, f"{reader}(card)")


def _lines(ctx: Ctx, k: int) -> tuple[tuple[str, ...], ...]:
    """The board's length-`k` lines (cell-name tuples) -- the source the
    `any line in lines(k) where …` register iterates. Reads the board entry
    T5 already computed (`cardlang/stdlib/boards.py`), never re-derives the
    geometry."""
    board = ctx.rs.board
    if board is None:
        # Resolve's Owner Guard rejects `lines()` in a boardless game
        # (BOARD_ONLY_CALL_FUNCS); this Shadow Guard stands behind it in the
        # runtime's own channel, should the call ever reach here without a
        # board.
        raise ShadowGuardError(
            "resolve._check_board_call",
            "lines() reads the board's lines, but the game declares no `board:`",
        )
    # A LITERAL out-of-range `k` is a resolve diagnostic (static bounds check
    # at the call site); a non-literal `k` (no rung-1 witness) is only knowable
    # at runtime. `lines` raises `OwnerGuardError` for both, so there is
    # nothing to convert here — the bound's Owner Guard already speaks the
    # runtime's typed channel and names the game author.
    return board.lines(k)


def _board_of(ctx: Ctx, fn: str) -> BoardEntry:
    """The instantiated `board:` entry the class-1 movement/region verbs read
    (the `_lines` twin). Resolve's [[owner-guard]] rejects a board-only call in a
    boardless game (BOARD_ONLY_CALL_FUNCS); this [[shadow-guard]] stands behind it
    in the runtime's own channel, naming the missing `board:`, should such a
    call ever reach here without a board."""
    board = ctx.rs.board
    if board is None:
        raise ShadowGuardError(
            "resolve._check_board_call",
            f"{fn}() reads the `board:`, but the game declares no `board:`",
        )
    return board


def _seat(ctx: Ctx, fn: str, player: int) -> int:
    """A frame verb's player argument must be a seat of this game. A LITERAL
    out-of-range seat is refused statically (typecheck `_check_role_literal`),
    but that check returns early on anything that is not an integer literal, so
    a COMPUTED seat -- `home(1 + 1)` -- reaches here unchallenged. Nothing
    upstream owns the computed case, so this is its Owner Guard, and it stands
    in place of the frame's internal `_player_sign` `ValueError`, which reads as
    a registry bug rather than a game one. Game-facing by design: the author who
    wrote the expression is who must change it."""
    if player not in ctx.rs.seating.players:
        raise OwnerGuardError(
            f"`{fn}` reads seat {player!r}, not a seat of this "
            f"{len(ctx.rs.seating.players)}-player game"
        )
    return player


def _neighbor(ctx: Ctx, cell: str, direction: str, player: int) -> str:
    """The cell one step along `direction` in `player`'s frame -- the geometry
    the `step` move reads (cardlang/stdlib/boards.py). Total by AUTHORING
    CONVENTION, not by construction: the corpus writes every call site
    `has_step`-guarded (the predicate short-circuits before any off-board
    `neighbor` runs; the effect runs only after it passed), but no pass enforces
    that -- the convention lives in prose and in a comment in
    docs/games/breakthrough.cardlang. So an ungated call is reachable from a
    game, and the None-return raise is this class's Owner Guard, addressed to
    the author who wrote it."""
    dest = _board_of(ctx, "neighbor").neighbor(cell, direction, _seat(ctx, "neighbor", player))
    if dest is None:
        raise OwnerGuardError(
            f"neighbor({cell!r}, {direction!r}, {player}) stepped off the board "
            "-- a total neighbor must be has_step-gated at its call site"
        )
    return dest


def _has_step(ctx: Ctx, cell: str, direction: str, player: int) -> bool:
    """Whether the step along `direction` stays on the board -- the guard
    predicate that gates the total `neighbor`."""
    return _board_of(ctx, "has_step").has_step(cell, direction, _seat(ctx, "has_step", player))


def _is_diagonal(ctx: Ctx, direction: str) -> bool:
    """Whether a step along `direction` captures (changes file)."""
    return _board_of(ctx, "is_diagonal").is_diagonal(direction)


def _home(ctx: Ctx, player: int) -> tuple[str, ...]:
    """A player's home region (back two ranks) -- a Collection<Cell>."""
    return _board_of(ctx, "home").home(_seat(ctx, "home", player))


def _far_row(ctx: Ctx, player: int) -> tuple[str, ...]:
    """The rank at the far edge of `player`'s frame (the reach-to-win goal)
    -- a Collection<Cell>."""
    return _board_of(ctx, "far_row").far_row(_seat(ctx, "far_row", player))


def _strain_index(strain: str | None) -> int:
    """The bidding rank of a strain: clubs<diamonds<hearts<spades<no-trump. A
    suit's ordinal in the deck's suit order; `none` (no-trump) ranks above every
    suit. Used by an ascending contract auction to compare bid strains."""
    return len(SUITS) if strain is None else SUITS.index(strain)


def _suit_of(value: Any) -> str:
    """The suit of a card, or of the single card in a zone (a face-up trump
    indicator). Asking for the suit of an EMPTY zone is a game-logic error and
    fails loudly here, at the cause — returning `none` instead would propagate
    silently into a `Suit?` variable and surface later as a wrong trick. The
    argument types `TAny` (polymorphic: card or zone), so a non-card value is
    user-reachable and gets a typed error, not a bare assert."""
    from cardlang.runtime.state import Zone

    if isinstance(value, Zone):
        if not value.cards:
            raise OwnerGuardError("suit_of: the zone is empty — no card to read a suit from")
        return value.cards[0].suit
    if not isinstance(value, Card):
        raise OwnerGuardError(
            f"suit_of expects a card or a zone, got {type(value).__name__}"
        )
    return value.suit


def _pile_trick_winner(value: Any, trump: str | None, ctx: Ctx) -> Player:
    """`highest_trump_or_led_suit(zone, trump)` — the standard trump-game
    trick winner over a public pile's [[arrival-record]]: the pairs are the
    kernel-recorded (deciding actor, card) arrivals in play order, the led
    suit is the first arrival's, the strengths the game's `ranking:` (issue
    #256; the same comparison the trick form's `winner` clause names, made
    callable for hand-rolled tricks — Schnapsen's).

    The pile argument reaches the shared Arrival-Record boundary
    (`runtime/trick_order.public_pile_plays`), which every member of
    `ARRIVAL_RECORD_CALLS` uses: the argument being a zone, and that zone's
    type projecting identity to EVERY observer, are decided STATICALLY now
    (`resolve._check_arrival_record_pile_args`, issue #250 PR 1) and stand
    there as [[shadow-guard]]s; every arrival carrying a deciding actor stays
    the boundary's own [[owner-guard]], a fact of what ran. Emptiness is this
    winner's own Owner Guard — the boundary returns possibly-empty pairs so
    `follows_lead` can answer false on them."""
    label, played = trick_order.public_pile_plays(
        value, ctx, "highest_trump_or_led_suit"
    )
    if not played:
        raise OwnerGuardError(
            f"highest_trump_or_led_suit over '{label}': the pile is empty — "
            f"no plays to name a winner from; guard the read "
            f"(`{label} is not empty`)"
        )
    return winners.highest_trump_or_led_suit(
        played, played[0][1].suit, trump, ctx.rs.rank_index
    )


def _end_card(cards: Any, fn: str, end: int) -> Card:
    """The card at one end of an ordered collection (`top_of` = the sequence
    end, `bottom_of` = the front — decisions.md "Position domains and
    positional zones", sequence orientation). The `call` boundary already
    coerced the TCollection param to elements, so `cards` is a plain list.
    An empty collection is a game-logic error reported at the cause (guard
    the read: `Z is not empty`); a non-card element is user-reachable
    (`top_of([1])` typechecks only per element type, but a TAny-typed source
    can reach here) and gets a typed error, not a bare attribute crash."""
    seq = list(cards)
    if not seq:
        raise OwnerGuardError(
            f"{fn}: the collection is empty — no card to read; guard the "
            f"read (`… is not empty`) so it only runs when a card is there"
        )
    card = seq[end]
    if not isinstance(card, Card):
        raise OwnerGuardError(
            f"{fn} expects a collection of cards, got an element of type "
            f"{type(card).__name__}"
        )
    return card


def _player_holding(card: Card, ctx: Ctx) -> Player:
    """The player whose hand contains `card`. CALL_SIGS declares the result
    `Player`, not `Player?`, and every corpus call site relies on that (`leader
    := player_holding(2 of clubs)` right after the full deal) — so a card in
    nobody's hand is a game-logic error reported here, at the cause, rather
    than a silent `None` that key-errors some later subscript."""
    for player, zone in reads.magic_hand(ctx.rs).items():
        if card in zone.cards:
            return player
    raise OwnerGuardError(f"player_holding: no hand contains {card}")
