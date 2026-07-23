"""Runtime implementations of the stdlib functions Hearts names.

These are the deferred runtime-primitives the front end only signatured
(library.md "Stdlib functions" / "Outcome functions"). The card query
(`cards in <zone> where <pred>`) lives in the evaluator; this module holds the
bare `f(...)` calls and the value-callbacks.
"""

from __future__ import annotations

from typing import Any, Callable

from cardlang.runtime import reads, sidecar
from cardlang.runtime.state import Ctx, IllegalMove, elements
from cardlang.runtime.values import SUITS, Card, Player
from cardlang.stdlib.boards import BoardEntry
from cardlang.stdlib.signatures import CALL_SIGS
from cardlang.types import TAny, TCollection

# This module's per-game functions (the auction outcomes; the pegging-scorer
# call sites) read state on behalf of specific games — one declared-reads row
# per game served (cardlang/runtime/reads.py).
_BRIDGE_R = reads.row("cardlang/runtime/stdlib.py", "bridge.cardlang")
_CRIBBAGE_R = reads.row("cardlang/runtime/stdlib.py", "cribbage.cardlang")
_PINOCHLE_R = reads.row("cardlang/runtime/stdlib.py", "pinochle.cardlang")
_TAROT_R = reads.row("cardlang/runtime/stdlib.py", "french-tarot.cardlang")


def _bind(
    ctx: Ctx, row: reads.PrimitiveReads
) -> tuple[sidecar.EngineFacts, reads.GameReads]:
    """The two value bundles for one narrowed primitive call."""
    return sidecar.bind(ctx.rs, ctx.current_player, row)


def _emit(ctx: Ctx, events: tuple[sidecar.TraceEvent, ...]) -> None:
    """Perform a narrowed primitive's deferred trace emissions. A game module
    holds no tracer, so the events travel back as data and are emitted here,
    in the order the primitive returned them (cardlang/runtime/sidecar.py)."""
    for event, payload in events:
        ctx.trace(event, payload)


def _coerce_args(sig: Any, args: list[Any]) -> list[Any]:
    """Freeze the collection-shaped arguments crossing into a game module.

    A collection-typed expression evaluates to either a Zone or a plain list
    (the zone facet is not part of assignability, so `gin_valid_meld(hand[p])`
    typechecks), and the adapters are bare Python that iterates — a
    TCollection param receives elements, never a Zone handle. `elements()`
    yields the Zone's LIVE `.cards` list, so the coercion additionally
    `deep_freeze`s it: the positional args are the second channel a primitive
    can touch (the bundles are the first), and `cards.clear()` on a live zone
    list would corrupt engine state exactly as a bundle write would. The
    A SCALAR `Card` argument (a `TCard` param — `canasta_stage_ok(p, card)`,
    `president_is_top_rank(p, c)`) is frozen too: evaluation preserves the
    engine's `Card` by identity, and a frozen+slots `Card` is still mutable
    via `object.__setattr__`, so an unfrozen scalar card is the same leak as
    an unfrozen collection. The freeze is SIGNATURE-DRIVEN, not blanket: a
    TAny param passes RAW, because its adapter dispatches on the shape itself
    (`suit_of`: a card or a single-card zone — blanket coercion broke the
    schnapsen trump indicator, and `deep_freeze` would refuse a Zone). Every
    other param is `deep_freeze`d: a copy for a `Card`, a no-op for the
    immutable scalars (`Player`, `Integer`, `Rank`, ...). The registry side is
    pinned by tests/test_stdlib_boundary.py (every TCollection param probed
    with a Zone, the TAny set pinned, no param zone=True)."""
    coerced: list[Any] = []
    for p, a in zip(sig.params, args):
        if isinstance(p, TCollection):
            coerced.append(reads.deep_freeze(elements(a)))
        elif isinstance(p, TAny):
            coerced.append(a)  # raw: the adapter dispatches on the shape
        else:
            coerced.append(reads.deep_freeze(a))  # copies a Card, no-ops scalars
    return coerced + args[len(sig.params) :]


def call(name: str, args: list[Any], ctx: Ctx) -> Any:
    sig = CALL_SIGS.get(name)
    if sig is not None:
        args = _coerce_args(sig, args)
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
        case "bring_in_seat":
            from cardlang.runtime.stud import ROW, bring_in_seat

            return bring_in_seat(*_bind(ctx, ROW))
        case "first_to_act_seat":
            from cardlang.runtime.stud import ROW, first_to_act_seat

            return first_to_act_seat(*_bind(ctx, ROW))
        case "pot_share":
            from cardlang.runtime.stud import ROW, pot_share

            return pot_share(*_bind(ctx, ROW), args[0])
        case "bigtwo_first_leader":
            from cardlang.runtime.bigtwo import ROW, first_leader_seat

            return first_leader_seat(*_bind(ctx, ROW))
        case "rank_value":
            return ctx.rs.rank_index[args[0].rank]
        case "card_value":
            return ctx.rs.card_values.get(args[0].rank, 0)
        case "top_of":
            return _end_card(args[0], "top_of", -1)
        case "bottom_of":
            return _end_card(args[0], "bottom_of", 0)
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
        case "tarot_card_points":
            from cardlang.runtime.tarot import tarot_card_points

            return tarot_card_points(args[0])
        case "schnapsen_trick_winner":
            from cardlang.runtime.schnapsen import ROW, schnapsen_trick_winner

            winner, events = schnapsen_trick_winner(
                *sidecar.bind(ctx.rs, ctx.current_player, ROW), args[0], args[1]
            )
            _emit(ctx, events)
            return winner
        case "skat_next_bid":
            from cardlang.runtime.skat import skat_next_bid

            return skat_next_bid(args[0])
        case "skat_follow_ok":
            from cardlang.runtime.skat import ROW, skat_follow_ok

            return skat_follow_ok(*_bind(ctx, ROW), args[0], args[1])
        case "skat_trick_winner":
            from cardlang.runtime.skat import ROW, skat_trick_winner

            winner, events = skat_trick_winner(*_bind(ctx, ROW), args[0])
            _emit(ctx, events)
            return winner
        case "doko_trick_winner":
            from cardlang.runtime.doko import ROW, doko_trick_winner

            winner, events = doko_trick_winner(*_bind(ctx, ROW), args[0])
            _emit(ctx, events)
            return winner
        case "skat_matadors":
            from cardlang.runtime.skat import ROW, skat_matadors

            return skat_matadors(*_bind(ctx, ROW), args[0])
        case "skat_effective_loss":
            from cardlang.runtime.skat import skat_effective_loss

            return skat_effective_loss(args[0], args[1], args[2])
        case "tichu_mahjong_holder":
            from cardlang.runtime.tichu import ROW, tichu_mahjong_holder

            return tichu_mahjong_holder(*_bind(ctx, ROW))
        case "tichu_players_holding":
            from cardlang.runtime.tichu import ROW, tichu_players_holding

            return tichu_players_holding(*_bind(ctx, ROW))
        case "tichu_double_victory":
            from cardlang.runtime.tichu import ROW, tichu_double_victory

            return tichu_double_victory(*_bind(ctx, ROW))
        case "tichu_partner":
            from cardlang.runtime.tichu import ROW, tichu_partner

            return tichu_partner(*_bind(ctx, ROW), args[0])
        case "tichu_next_holder":
            from cardlang.runtime.tichu import ROW, tichu_next_holder

            return tichu_next_holder(*_bind(ctx, ROW), args[0])
        case "tichu_dragon_won":
            from cardlang.runtime.tichu import ROW, tichu_dragon_won

            return tichu_dragon_won(*_bind(ctx, ROW))
        case "tichu_opponent_team":
            from cardlang.runtime.tichu import ROW, tichu_opponent_team

            return tichu_opponent_team(*_bind(ctx, ROW), args[0])
        case "tichu_first_out":
            from cardlang.runtime.tichu import ROW, tichu_first_out

            return tichu_first_out(*_bind(ctx, ROW))
        case "tichu_card_points":
            from cardlang.runtime.tichu import ROW as TICHU_ROW
            from cardlang.runtime.tichu import tichu_card_points

            return tichu_card_points(*_bind(ctx, TICHU_ROW), args[0])
        case "president_next_holder":
            from cardlang.runtime.president import ROW, president_next_holder

            return president_next_holder(*_bind(ctx, ROW), args[0])
        case "president_is_top_rank":
            from cardlang.runtime.president import ROW, president_is_top_rank

            return president_is_top_rank(*_bind(ctx, ROW), args[0], args[1])
        case "coup_players_in":
            from cardlang.runtime.coup import ROW, coup_players_in

            return coup_players_in(*_bind(ctx, ROW))
        case "coup_next_in_game":
            from cardlang.runtime.coup import ROW, coup_next_in_game

            return coup_next_in_game(*_bind(ctx, ROW), args[0])
        case "coup_has_char":
            from cardlang.runtime.coup import ROW, coup_has_char

            return coup_has_char(*_bind(ctx, ROW), args[0], args[1])
        case "coup_game_summary":
            from cardlang.runtime.coup import ROW, coup_game_summary

            total, events = coup_game_summary(*_bind(ctx, ROW))
            _emit(ctx, events)
            return total
        case "peg_value":
            from cardlang.runtime.cribbage import value

            return value(args[0])
        case "peg_pair_points":
            from cardlang.runtime.cribbage import peg_pair_points

            # These two read live engine state directly rather than through a
            # bundle, so their collection args are frozen here at the call site
            # (the same boundary `_coerce_args` enforces for DSL arguments).
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
        case "gin_card_points":
            from cardlang.runtime.gin import card_points

            return card_points(args[0])
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
        case "gin_flat_points":
            from cardlang.runtime.gin import ROW, gin_flat_points

            return gin_flat_points(*_bind(ctx, ROW), args[0])
        case "gin_shown_points":
            from cardlang.runtime.gin import ROW, gin_shown_points

            return gin_shown_points(*_bind(ctx, ROW), args[0])
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
        case "five_hundred_follow_ok":
            from cardlang.runtime.five_hundred import ROW, five_hundred_follow_ok

            return five_hundred_follow_ok(*_bind(ctx, ROW), args[0], args[1])
        case "five_hundred_lead_ok":
            from cardlang.runtime.five_hundred import ROW, five_hundred_lead_ok

            return five_hundred_lead_ok(*_bind(ctx, ROW), args[0], args[1])
        case "five_hundred_trick_winner":
            from cardlang.runtime.five_hundred import ROW, five_hundred_trick_winner

            winner, events = five_hundred_trick_winner(*_bind(ctx, ROW), args[0])
            _emit(ctx, events)
            return winner
        case "belote_trump_height":
            from cardlang.runtime.belote import belote_trump_height

            return belote_trump_height(args[0])
        case "belote_opp_winning":
            from cardlang.runtime.belote import ROW, belote_opp_winning

            return belote_opp_winning(*_bind(ctx, ROW))
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
        case "canasta_is_red3":
            from cardlang.runtime.canasta import ROW, canasta_is_red3

            return canasta_is_red3(*_bind(ctx, ROW), args[0])
        case "canasta_is_black3":
            from cardlang.runtime.canasta import ROW, canasta_is_black3

            return canasta_is_black3(*_bind(ctx, ROW), args[0])
        case "canasta_top_starts_pile":
            from cardlang.runtime.canasta import ROW, canasta_top_starts_pile

            return canasta_top_starts_pile(*_bind(ctx, ROW))
        case "canasta_top_is_wild":
            from cardlang.runtime.canasta import ROW, canasta_top_is_wild

            return canasta_top_is_wild(*_bind(ctx, ROW))
        case "canasta_pile_rank":
            from cardlang.runtime.canasta import ROW, canasta_pile_rank

            return canasta_pile_rank(*_bind(ctx, ROW))
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
        case "canasta_add_ok":
            from cardlang.runtime.canasta import ROW, canasta_add_ok

            return canasta_add_ok(*_bind(ctx, ROW), args[0], args[1], args[2])
        case "canasta_discard_ok":
            from cardlang.runtime.canasta import ROW, canasta_discard_ok

            return canasta_discard_ok(*_bind(ctx, ROW), args[0], args[1])
        case "canasta_black3_ok":
            from cardlang.runtime.canasta import ROW, canasta_black3_ok

            return canasta_black3_ok(*_bind(ctx, ROW), args[0])
        case "canasta_meld_points":
            from cardlang.runtime.canasta import ROW, canasta_meld_points

            return canasta_meld_points(*_bind(ctx, ROW), args[0])
        case "canasta_canasta_bonus":
            from cardlang.runtime.canasta import ROW, canasta_canasta_bonus

            return canasta_canasta_bonus(*_bind(ctx, ROW), args[0])
        case "canasta_red3_bonus":
            from cardlang.runtime.canasta import ROW, canasta_red3_bonus

            return canasta_red3_bonus(*_bind(ctx, ROW), args[0])
        case "canasta_hand_points":
            from cardlang.runtime.canasta import ROW, canasta_hand_points

            return canasta_hand_points(*_bind(ctx, ROW), args[0])
        case _:
            raise AssertionError(f"unknown stdlib function '{name}'")


def _lines(ctx: Ctx, k: int) -> tuple[tuple[str, ...], ...]:
    """The board's length-`k` lines (cell-name tuples) -- the source the
    `any line in lines(k) where …` register iterates. Reads the board entry
    T5 already computed (`cardlang/stdlib/boards.py`), never re-derives the
    geometry."""
    board = ctx.rs.board
    if board is None:
        # Resolve walls `lines()` in a boardless game (BOARD_ONLY_CALL_FUNCS);
        # this backstops that wall in the runtime's own currency, should the
        # call ever reach here without a board.
        raise RuntimeError(
            "lines() reads the board's lines, but the game declares no `board:`"
        )
    try:
        return board.lines(k)
    except ValueError as exc:
        # A LITERAL out-of-range `k` is a resolve diagnostic (static bounds
        # check at the call site); a non-literal `k` (no rung-1 witness) is
        # only knowable at runtime, so its out-of-range value surfaces here as
        # a typed runtime error, never a bare ValueError escaping the boundary.
        raise RuntimeError(str(exc)) from exc


def _board_of(ctx: Ctx, fn: str) -> BoardEntry:
    """The instantiated `board:` entry the class-1 movement/region verbs read
    (the `_lines` twin). Resolve walls a board-only call in a boardless game
    (BOARD_ONLY_CALL_FUNCS); this backstops that resolve wall in the runtime's
    own currency, naming the missing `board:`, should such a call ever reach
    here without a board."""
    board = ctx.rs.board
    if board is None:
        raise RuntimeError(
            f"{fn}() reads the `board:`, but the game declares no `board:`"
        )
    return board


def _seat(ctx: Ctx, fn: str, player: int) -> int:
    """A frame verb's player argument must be a seat of this game. The resolve
    wall (typecheck `_check_player_literal`) rejects a LITERAL out-of-range seat
    statically, and the frame verbs are two-player-only (resolve), so a bad seat
    is unreachable from a well-formed game -- this backstops the COMPUTED case
    in the runtime's currency (a typed, game-facing rejection) in place of the
    frame's internal `_player_sign` `ValueError`, which reads as a registry bug
    rather than a game one."""
    if player not in ctx.rs.seating.players:
        raise RuntimeError(
            f"`{fn}` reads seat {player!r}, not a seat of this "
            f"{len(ctx.rs.seating.players)}-player game"
        )
    return player


def _neighbor(ctx: Ctx, cell: str, direction: str, player: int) -> str:
    """The cell one step along `direction` in `player`'s frame -- the geometry
    the `step` move reads (cardlang/stdlib/boards.py). Total by contract: every
    call site is `has_step`-gated (the guard short-circuits before any off-board
    `neighbor` runs; the effect runs only after that guard passed), so an
    off-board result is unreachable from a game. The None-return raise is a
    backstop of that `has_step` guard, in the runtime's currency -- not a
    game-reachable error."""
    dest = _board_of(ctx, "neighbor").neighbor(cell, direction, _seat(ctx, "neighbor", player))
    if dest is None:
        raise RuntimeError(
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
            raise RuntimeError("suit_of: the zone is empty — no card to read a suit from")
        return value.cards[0].suit
    if not isinstance(value, Card):
        raise RuntimeError(
            f"suit_of expects a card or a zone, got {type(value).__name__}"
        )
    return value.suit


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
        raise RuntimeError(
            f"{fn}: the collection is empty — no card to read; guard the "
            f"read (`… is not empty`) so it only runs when a card is there"
        )
    card = seq[end]
    if not isinstance(card, Card):
        raise RuntimeError(
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
    raise RuntimeError(f"player_holding: no hand contains {card}")


# --- value-callbacks (mechanic functions passed by name) ---

# An outcome function picks the trick winner from the plays, the led suit, the
# trump suit (None when no trump), and the game's rank-strength map.
RankIndex = dict[str, int]
OutcomeFn = Callable[[list[tuple[Player, Card]], str, "str | None", RankIndex], Player]
# An early-termination predicate: does this play end the trick? (card, led_suit)
EarlyTermFn = Callable[[Card, str], bool]


def value_function(name: str) -> Callable[..., Any]:
    match name:
        case "highest_of_led_suit":
            return highest_of_led_suit
        case "highest_trump_or_led_suit":
            return highest_trump_or_led_suit
        case "on_play_of_tochoo":
            return on_play_of_tochoo
        case "tarot_trick_winner":
            from cardlang.runtime.tarot import tarot_trick_winner

            return tarot_trick_winner
        case "belote_trick_winner":
            from cardlang.runtime.belote import belote_trick_winner

            return belote_trick_winner
        case _:
            raise AssertionError(f"unknown stdlib value '{name}'")


# --- climbing-form combination-engine queries (named on a `round climb`) ---
#
# A *lead* query returns every combination a hand may lead; a *follows* query
# returns those that beat the standing play. Both take the runtime ctx (a lead
# query may read game state, e.g. Big Two's opening 3♦ filter). The engines are
# game-local, so these dispatch to per-game modules.


ClimbLeadFn = Callable[[sidecar.EngineFacts, reads.GameReads, list[Card]], list[Any]]
ClimbFollowFn = Callable[
    [sidecar.EngineFacts, reads.GameReads, list[Card], Any], list[Any]
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
    joint predicate with no registered codec is walled loudly at
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


def highest_of_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The player who played the highest-ranked card of the led suit."""
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return max(of_suit, key=lambda pc: rank_index[pc[1].rank])[0]


def highest_trump_or_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The highest trump if any trump was played, else the highest card of the
    led suit (the standard trick winner for a trump game)."""
    trumps = [(p, c) for (p, c) in played if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: rank_index[pc[1].rank])[0]
    return highest_of_led_suit(played, led_suit, trump, rank_index)


def on_play_of_tochoo(card: Card, led_suit: str) -> bool:
    """A tochoo is a card that fails to follow the led suit; playing one (only
    possible when void) ends the trick early (Getaway: the highest led-suit
    card then picks up the pile)."""
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
        # mismatch is the game description's error, in the runtime's currency.
        raise RuntimeError(
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
            # error, in the runtime's currency.
            raise RuntimeError(
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
