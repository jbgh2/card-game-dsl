"""Class-1 movement/region stdlib verbs: neighbor / has_step / is_diagonal /
home / far_row -- the `lines` twin (a BOARD_ONLY call reading the `board:`).

The five verbs are the geometry the rung-2 `step(from : cell, along : dir)`
move reads (decisions.md "Boards and cells", rung-2 movement): `neighbor` is
the destination cell one step along a direction in a player's frame,
`has_step` the guard that gates it, `is_diagonal` whether the step captures,
and `home`/`far_row` the setup and reach-goal cell regions. Each wraps a
`BoardEntry` method (cardlang/stdlib/boards.py); each is classified BOARD_ONLY
(cardlang/builtins/functions.py::BOARD_ONLY_CALL_FUNCS) so a boardless game
rejects the call at resolve, exactly as `lines` does. The surfaces are
`cardlang/builtins/signatures.py` (CALL_SIGS), `cardlang/runtime/primitives.py`
(the `call` dispatch + the `_board_of`/`_neighbor`/... impls), and
`cardlang/builtins/functions.py` (CALL_FUNCS + BOARD_ONLY_CALL_FUNCS).

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   each of the five verbs is (a) legal and correctly evaluated in a
            board game at its declared `Sig` arg/return types, (b) rejected at
            resolve in a boardless game naming the missing `board:` (the
            `lines` twin, BOARD_ONLY), and (c) enforced for arity and argument
            type at its call site; `neighbor` is total-with-backstop (an
            off-board step raises a typed RuntimeError, never returns None);
            and the two NEW value shapes the verbs introduce -- `home`/
            `far_row`'s `Collection<Cell>` and `neighbor`'s `TCell` return --
            are either given correct meaning or loudly walled at every existing
            operation that consumes them, never silently accepted-and-ignored.
domain:     {the five verbs} x {board game: typecheck + evaluate; boardless:
            resolve reject + runtime backstop; wrong arity; wrong arg type},
            crossed with the classification partition {generic, deck-only,
            board-only}; PLUS the pairwise interactions of the two new value
            shapes (`Collection<Cell>`, a call-return `TCell`) against every
            existing collection/cell consumer (the framing-check b-table).
registry:   the verb set -- cardlang.builtins.functions.CALL_FUNCS +
            BOARD_ONLY_CALL_FUNCS; the signatures -- cardlang.stdlib.
            signatures.CALL_SIGS; the runtime -- cardlang.runtime.evaluate.native_call
            (the five arms + _board_of/_neighbor/... helpers) over cardlang.
            stdlib.boards.BoardEntry (geometry exhaustively pinned by Task 2's
            tests/test_boards_registry.py); the resolve wall -- cardlang.
            resolve._check_board_call; the typecheck call walls -- cardlang.
            typecheck (infer's Call arm -> sig.ret; _check_expr's Call arm ->
            arity + per-arg assignable); the pairwise consumers -- cardlang.
            typecheck (_domain_query_binder_type, _check_movement/_is_zone_type,
            _check_card_source, _check_is_check, _check_membership_operands) and
            the movement-source grammar.
covered:    the grid below, each a running row --
            classification: test_the_five_verbs_are_board_only (the five in
            BOARD_ONLY ∩ CALL_FUNCS); the TOTAL partition (every
            CALL_FUNCS member classified generic/deck-only/board-only,
            none unclassified) is pinned ONCE at tests/test_signatures.py::
            test_deck_only_classification_partitions_call_funcs and tests/
            test_piece_content_walls.py -- cited, not re-copied (CLAUDE.md
            rule 4);
            positive typecheck in situ: test_witness_game_typechecks -- the
            witness `step(from : cell, along : dir)` calls all five in a real
            guard/effect, including the intended-use `square[neighbor(from,
            along, actor)]` movement destination (the TCell return into a
            cell-keyed zone subscript, decisions.md "Boards and cells") and
            `home`/`far_row` bare lets (Collection<Cell> accepted);
            positive evaluate: test_verb_evaluates_to_expected_value -- 16
            cells over both player frames and edge cells, values hand-computed
            from BoardEntry's offsets;
            neighbor total-with-backstop: test_neighbor_offboard_backstop_raises;
            boardless reject (resolve): test_verb_in_boardless_game_is_rejected
            (all five) + message goldens tests/rejections/{neighbor,has_step,
            is_diagonal,home,far_row}_boardless;
            boardless Shadow Guard (runtime): test_verb_runtime_boardless_
            backstop_raises (all five, ShadowGuardError naming the leaked
            resolve._check_board_call);
            frame verb x player count: the per-player frame is two-seat, so a
            frame verb (the player-taking board verbs, DERIVED into
            _FRAME_CALL_FUNCS -- pinned by test_frame_call_funcs_is_the_player_
            taking_board_verbs) is rejected in a non-two-player game
            (test_frame_verb_in_a_non_two_player_game_is_rejected: 3, 4, and a
            RANGE) and accepted at exactly two
            (test_frame_verb_in_a_two_player_game_is_accepted); the wall is
            VERB-level not board-level (test_non_two_player_grid_without_a_
            frame_verb_is_accepted) and player-free board verbs are untouched
            (test_player_free_board_verb_in_a_non_two_player_game_is_accepted);
            arity + arg-type: test_wrong_arity_is_rejected,
            test_is_diagonal_cell_for_dir_is_rejected (TCell for TDir),
            test_home_cell_for_player_is_rejected (TCell for TPlayer),
            test_along_dir_for_player_is_rejected (TDir for TPlayer) + goldens
            tests/rejections/{neighbor_wrong_arity,is_diagonal_cell_for_dir,
            home_cell_for_player};
            pairwise (the new Collection<Cell> is not silently swallowed):
            test_any_cell_in_a_region_is_rejected_not_silently_iterated (the
            cell quantifier demands a single TLine, typecheck) and
            test_a_region_is_not_a_movement_source (a call expression is
            grammatically inexpressible as a movement source).
sampled:    the geometry values -- representative cells per verb (a1/d4/h8 +
            edges), not all 64 cells x 3 dirs x 2 frames: BoardEntry geometry
            is exhaustively integrity-pinned in Task 2's tests/
            test_boards_registry.py; this module samples the stdlib WRAPPING
            (dispatch + coercion + backstop) over it;
            the arg-type matrix -- sampled across is_diagonal/home/neighbor
            (Cell->Dir, Cell->Player, Dir->Player, arity); has_step's three
            slots are neighbor's types and are not separately misused (the
            per-arg `assignable` loop is total, one representative per
            type-pair suffices);
            the Collection<Cell> REJECT fan-out beyond the two headline cells
            (`any line in <region>`, `over cards in <region>`, `turns over`/
            `as` <region>, equality, epistemic-target) -- each rejected by an
            existing total wall (framing-check-mapped); the two likeliest
            author mistakes are pinned, the rest sampled;
            the ACCEPT surface consumed today -- `home(p) is empty`/`is not
            empty` and membership `c in home(p)` both typecheck AND evaluate
            correctly end to end (runtime `in` is `left in elements(right)`,
            `elements` yields the cell tuple); the value cells pin the produced
            tuple, `for each cell` iteration and membership's own dedicated
            coverage are Task 4.
residual:   FIELD ACCESS on a position/board type is a SILENT permissive
            fall-through: `.field` on a TCell/TDir/TLine receiver (a `cell`/
            `dir` binder, or `neighbor`'s TCell return) infers TAny with NO
            diagnostic -- the typecheck Member arm (cardlang/typecheck.py::
            _check_expr) has no arm for these types. PRE-EXISTING (rung-1 cell
            binders, Task-1 dir binders); the rung-2 verbs' TCell return newly
            reaches it. NOT walled here -- the fix is class-wide (the
            no-Member-arm Type members swept as one), out of the five-verb
            scope. Recorded in issue #111 (the field-access bullet) and
            spawned as a follow-up.
            Positional subscript index-type unchecked -- `home(p)[<anything>]`
            typechecks (home/far_row produce key=None positional collections;
            the Subscript key-check runs only when key is not None) --
            pre-existing for ALL positional collections, benign; same roadmap
            bullet class.
            Cell/region CONSUMPTION beyond membership + is-empty -- `for each
            cell` iteration over a region is Task 4 (walled today by
            _ITERATION_ROLES, tests/test_cell_queries.py::
            test_for_each_cell_stays_rejected); membership `c in home(p)`
            already works (sampled above).
            State persistence of a cell/region -- `state { x : cell }` /
            `{ x : dir }` is REJECTED at resolve (the StateDecl type-name wall;
            cell/dir are not KNOWN_TYPE_NAMES), so there is no silent-TAny
            state-storage sink; closed by reject, stated so it is recorded.

red under (the born-green classification pin): test_the_five_verbs_are_board_
only is a membership assertion over two frozensets, born green once the verbs
register. Its reddening witness: dropping any of the five from
BOARD_ONLY_CALL_FUNCS while leaving it in CALL_FUNCS reddens the TOTAL
partition pin at tests/test_signatures.py::test_deck_only_classification_
partitions_call_funcs (union != CALL_FUNCS); dropping it here reddens
this focused assertion directly. Every other grid row was born RED (the verbs
did not exist -- "call to unknown function"), its pre-implementation red run
the witness.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.board_domains import position_domains_of
from cardlang.builtins.functions import (
    BOARD_ONLY_CALL_FUNCS,
    CALL_FUNCS,
)
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.evaluate import native_call as call
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Seating, axis_attributes
from cardlang.stdlib.boards import board_entry

# The five verbs this ledger adds, in the fixed order the grid parametrizes.
MOVEMENT_VERBS = ("neighbor", "has_step", "is_diagonal", "home", "far_row")


# --- the inline board witness game -------------------------------------------
#
# A minimal `board: grid(8, 8)` + `pieces:` game whose `step(from : cell,
# along : dir)` move calls all five verbs in a real guard/effect, so a single
# `check_dsl` proves they typecheck with the right argument types in situ.
# Mirrors tests/test_cell_queries.py's board_game builder (kept local, the
# per-module convention).

WITNESS_SRC = """
game MoveVerbs {
  players: 2
  direction: clockwise
  max_length: 30
  board: grid(8, 8)
  pieces: xo_marks
  zones {
    box             : Deck
    square[cell]    : Cell<cell>
    reserve[player] : PlayerPile<player>
  }
  state { done : Boolean = false }
  phase setup {
    move all pieces from box where piece.side is x to reserve[0]
    move all pieces from box to reserve[1]
  }
  phase play {
    turns t from 0 over all players until done {
      offer to t one of [step, stop]
    }
  }
  winner: highest done
}
move_type step(from : cell, along : dir) {
  when: has_step(from, along, actor) and is_diagonal(along)
  effect {
    let h = home(actor)
    let f = far_row(actor)
    move one piece from reserve[actor] to square[neighbor(from, along, actor)]
    done := true
  }
}
move_type stop { effect { done := true } }
"""


def _unused_chooser(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("verb evaluation makes no decision")


def _board_ctx(family: str, args: tuple[int, ...]) -> Ctx:
    """A Ctx over a bare instantiated board (no piece placements needed -- the
    verbs read geometry, not occupancy). `acting_as(0)` supplies `actor`."""
    game = check_dsl(WITNESS_SRC, "witness.cardlang")
    positions = dict(position_domains_of(game))
    zones = ZoneStore(game.zones, (0, 1), positions=positions)
    rs = RuntimeState(Seating(2), zones, random.Random(0))
    rs.position_domains = positions
    rs.board = board_entry(family, args)
    rs.axis_attr = axis_attributes(game.deck)
    rs.content_flavor = game.content_flavor
    return Ctx(rs=rs, chooser=_unused_chooser).acting_as(0)


_BOARDLESS_SRC = """
game NoBoard {
  players: 2
  direction: clockwise
  max_length: 30
  pieces: xo_marks
  zones { box : Deck  pile[player] : PlayerPile<player> }
  state { done : Boolean = false }
  phase play {
    turns t from 0 over all players until done {
      offer to t one of [stop]
    }
  }
  winner: highest done
}
move_type stop { effect { done := true } }
"""


def _boardless_ctx() -> Ctx:
    """A Ctx whose runtime state carries no board (`rs.board is None`) -- the
    runtime backstop's domain (the resolve wall is the static twin,
    tests/rejections/). Built from a genuinely boardless game (no cell-keyed
    zone), so `rs.board` stays at its `None` default."""
    game = check_dsl(_BOARDLESS_SRC, "noboard.cardlang")
    zones = ZoneStore(game.zones, (0, 1))
    rs = RuntimeState(Seating(2), zones, random.Random(0))
    return Ctx(rs=rs, chooser=_unused_chooser).acting_as(0)


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "mv.cardlang")
    parts = [exc.value.diagnostic.message]
    parts.extend(getattr(exc.value, "__notes__", []) or [])
    return "\n".join(parts)


def _boardless_game(body: str) -> str:
    """A boardless piece game whose `foo` move body is `body` -- the universe
    a board-only call has no `board:` to read. A piece game (not a card game)
    so a piece-flavored move body is well-formed; the board-only wall keys on
    `game.board is None`, orthogonal to the flavor."""
    return (
        "game Boardless {\n"
        "  players: 2\n"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        "  pieces: xo_marks\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    pile[player]    : PlayerPile<player>\n"
        "  }\n"
        "  state { n : Integer = 0  done : Boolean = false }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [foo, stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest n\n"
        "}\n"
        "move_type foo {\n"
        "  effect {\n"
        f"{body}"
        "    done := true\n"
        "  }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )


def _board_game(*, guard: str = "square[from] is empty", body: str = "") -> str:
    """A grid(8,8) board witness whose `step(from : cell, along : dir)` move
    carries `guard`/`body` -- the frame the arity/arg-type probes misuse."""
    return (
        "game BoardMisuse {\n"
        "  players: 2\n"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        "  board: grid(8, 8)\n"
        "  pieces: xo_marks\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    square[cell]    : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state { done : Boolean = false }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        "  }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [step, stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest done\n"
        "}\n"
        "move_type step(from : cell, along : dir) {\n"
        f"  when: {guard}\n"
        "  effect {\n"
        f"{body}"
        "    move one piece from reserve[actor] to square[from]\n"
        "  }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )


# =============================================================================
# POSITIVE: the witness game typechecks (all five verbs, right arg types in a
# real guard/effect), and each verb evaluates to the hand-computed value.
# =============================================================================


def test_witness_game_typechecks() -> None:
    """One `check_dsl` proves all five verbs typecheck in situ: `has_step`/
    `is_diagonal` in the guard (Boolean), `neighbor` -> a `let` of a Cell,
    `home`/`far_row` -> `let`s of a Collection<Cell> (bare lets, nothing
    consumes them until Task 4 -- accepted, not a totality defect)."""
    check_dsl(WITNESS_SRC, "witness.cardlang")


# (verb, args, expected) on a grid(8, 8), hand-computed from
# cardlang/stdlib/boards.py's offsets: ahead=(drow1,dcol0),
# ahead_left=(1,-1), ahead_right=(1,1); player 1 is the 180-degree flip.
# a1=(col0,row0), h8=(col7,row7); _cell_name(col,row)=FILES[col]+str(row+1).
_EIGHT = tuple("abcdefgh")
_HOME0 = tuple(f"{f}{r}" for r in (1, 2) for f in _EIGHT)  # ranks 1-2, 16 cells
_HOME1 = tuple(f"{f}{r}" for r in (7, 8) for f in _EIGHT)  # ranks 7-8
_FAR0 = tuple(f"{f}8" for f in _EIGHT)  # top rank (player 0's reach goal)
_FAR1 = tuple(f"{f}1" for f in _EIGHT)  # bottom rank


@pytest.mark.parametrize(
    "verb,args,expected",
    [
        pytest.param("neighbor", ["a1", "ahead", 0], "a2", id="neighbor-p0-straight"),
        pytest.param("neighbor", ["a1", "ahead_right", 0], "b2", id="neighbor-p0-diag"),
        pytest.param("neighbor", ["d4", "ahead", 0], "d5", id="neighbor-p0-interior"),
        pytest.param("neighbor", ["h8", "ahead", 1], "h7", id="neighbor-p1-frame"),
        pytest.param("neighbor", ["h8", "ahead_right", 1], "g7", id="neighbor-p1-diag"),
        pytest.param("has_step", ["a1", "ahead", 0], True, id="has_step-onboard"),
        pytest.param("has_step", ["a1", "ahead_left", 0], False, id="has_step-offedge"),
        pytest.param("has_step", ["a8", "ahead", 0], False, id="has_step-toprow-p0"),
        pytest.param("has_step", ["h8", "ahead", 1], True, id="has_step-p1-onboard"),
        pytest.param("is_diagonal", ["ahead"], False, id="is_diagonal-straight"),
        pytest.param("is_diagonal", ["ahead_left"], True, id="is_diagonal-left"),
        pytest.param("is_diagonal", ["ahead_right"], True, id="is_diagonal-right"),
        pytest.param("home", [0], _HOME0, id="home-p0"),
        pytest.param("home", [1], _HOME1, id="home-p1"),
        pytest.param("far_row", [0], _FAR0, id="far_row-p0"),
        pytest.param("far_row", [1], _FAR1, id="far_row-p1"),
    ],
)
def test_verb_evaluates_to_expected_value(
    verb: str, args: list[object], expected: object
) -> None:
    ctx = _board_ctx("grid", (8, 8))
    assert call(verb, list(args), ctx) == expected


def test_neighbor_offboard_backstop_raises() -> None:
    """`neighbor` is total-with-backstop: an off-board step (unreachable in a
    game because every call site is `has_step`-gated) raises a typed
    RuntimeError here, never returns None or a bare crash."""
    ctx = _board_ctx("grid", (8, 8))
    with pytest.raises(OwnerGuardError, match=r"stepped off the board"):
        call("neighbor", ["a1", "ahead_left", 0], ctx)


# =============================================================================
# BOARDLESS: each verb rejected at resolve (the board-only wall, `lines`'s
# twin) -- the inline sweep of the whole class; tests/rejections/ pins the
# rendered message.
# =============================================================================


@pytest.mark.parametrize("verb", MOVEMENT_VERBS)
def test_verb_in_boardless_game_is_rejected(verb: str) -> None:
    args = {
        "neighbor": "neighbor(n, n, n)",
        "has_step": "has_step(n, n, n)",
        "is_diagonal": "is_diagonal(n)",
        "home": "home(n)",
        "far_row": "far_row(n)",
    }[verb]
    msg = _reject(_boardless_game(f"    if {args} is not empty {{ n := 1 }}\n"
                                  if verb in ("home", "far_row")
                                  else f"    if {args} {{ n := 1 }}\n"))
    assert f"`{verb}` reads the board" in msg
    assert "the game declares no `board:`" in msg


@pytest.mark.parametrize("verb", MOVEMENT_VERBS)
@pytest.mark.expects_shadow_guard
def test_verb_runtime_boardless_backstop_raises(verb: str) -> None:
    """The Shadow Guard behind `resolve._check_board_call`: should a board-only
    call ever reach `call()` without a board, it raises `ShadowGuardError`
    naming the guard that leaked, never dereferences None.

    Marked `expects_shadow_guard` because reaching it IS the engine gap the
    suite-wide Pin exists to catch — this test constructs one on purpose, and
    without the mark tests/conftest.py fails the run.
    """
    ctx = _boardless_ctx()
    args_by_verb: dict[str, list[Any]] = {
        "neighbor": ["a1", "ahead", 0],
        "has_step": ["a1", "ahead", 0],
        "is_diagonal": ["ahead"],
        "home": [0],
        "far_row": [0],
    }
    with pytest.raises(ShadowGuardError, match=r"declares no `board:`") as caught:
        call(verb, args_by_verb[verb], ctx)
    # The leaked guard is part of the contract, not decoration: a Shadow Guard
    # that does not name who should have refused earlier sends the maintainer
    # nowhere.
    assert caught.value.leaked == "resolve._check_board_call"


@pytest.mark.parametrize("verb", ("neighbor", "has_step", "home", "far_row"))
def test_frame_verb_runtime_seat_backstop(verb: str) -> None:
    """The runtime companion to the static player-literal wall
    (tests/test_player_literal_range.py): a COMPUTED out-of-range seat reaching
    a frame verb is a typed, game-facing RuntimeError naming the seat count, not
    the frame's internal `_player_sign` registry-bug ValueError. On a 2-seat
    board ctx, seat 5 is out of range."""
    ctx = _board_ctx("grid", (8, 8))  # Seating(2)
    args_by_verb: dict[str, list[Any]] = {
        "neighbor": ["a1", "ahead", 5],
        "has_step": ["a1", "ahead", 5],
        "home": [5],
        "far_row": [5],
    }
    with pytest.raises(OwnerGuardError, match=r"seat 5, not a seat of this 2-player game"):
        call(verb, args_by_verb[verb], ctx)


# =============================================================================
# FRAME VERBS x PLAYER COUNT (Codex P2, PR #92): a grid's per-player frame is
# defined for two opposed seats (one's forward is the other's, the 180-degree
# opposite), so the board-only verbs that read it -- the ones taking a player --
# are rejected in a game that is not exactly two players. Without the wall a
# 3-plus-player game resolves clean and then dies at play with the frame's
# registry-bug ValueError for seat 2. `_FRAME_CALL_FUNCS` is DERIVED from the
# signatures (board-only + a player param), so the wall's domain cannot drift.
# =============================================================================


def test_frame_call_funcs_is_the_player_taking_board_verbs() -> None:
    # The wall's domain, pinned to its derivation rather than hand-listed: the
    # board-only calls whose Sig takes a player. A new player-taking board verb
    # joins _FRAME_CALL_FUNCS -- and the two-seat wall -- by construction; a new
    # player-free one (a second `lines`/`is_diagonal`) does not.
    from cardlang.builtins.functions import BOARD_ONLY_CALL_FUNCS
    from cardlang.builtins.signatures import CALL_SIGS
    from cardlang.resolve import _FRAME_CALL_FUNCS
    from cardlang.types import TPlayer

    assert _FRAME_CALL_FUNCS == {"neighbor", "has_step", "home", "far_row"}
    assert _FRAME_CALL_FUNCS <= BOARD_ONLY_CALL_FUNCS
    assert _FRAME_CALL_FUNCS == {
        fn
        for fn in BOARD_ONLY_CALL_FUNCS
        if any(isinstance(p, TPlayer) for p in CALL_SIGS[fn].params)
    }


def _grid_game(players_line: str, setup_extra: str = "") -> str:
    """A grid(8, 8) board game with a chosen `players:` line; `setup_extra`
    runs after the deal, where a frame call lands."""
    return (
        "game FrameCount {\n"
        f"{players_line}"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        "  board: grid(8, 8)\n"
        "  pieces: xo_marks\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    square[cell]    : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state { done : Boolean = false }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        f"{setup_extra}"
        "  }\n"
        "  phase play { turns t from 0 over all players until done "
        "{ offer to t one of [stop] } }\n"
        "  winner: highest done\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )


_HOME_SETUP = (
    "    for each cell c: if c in home(0) "
    "{ move one piece from reserve[0] to square[c] }\n"
)


@pytest.mark.parametrize(
    "players_line, count",
    [("  players: 3\n", "3"), ("  players: 4\n", "4"), ("  players: 2..4\n", "2-4")],
)
def test_frame_verb_in_a_non_two_player_game_is_rejected(players_line: str, count: str) -> None:
    # 3+, or a RANGE (refused even though it includes two -- the game may be
    # instantiated with more).
    msg = _reject(_grid_game(players_line, _HOME_SETUP))
    assert "`home` reads a grid's two-player movement frame" in msg
    assert f"declares {count} players" in msg


def test_frame_verb_in_a_two_player_game_is_accepted() -> None:
    # The witness count: exactly two, the frame's domain. (breakthrough itself.)
    check_dsl(_grid_game("  players: 2\n", _HOME_SETUP), "frame2.cardlang")


def test_non_two_player_grid_without_a_frame_verb_is_accepted() -> None:
    # The wall is VERB-level, not board-level: a 3-player grid game that reads
    # no frame (empty `setup_extra`, so no `home`/`neighbor`/... call) is
    # legitimate and stays accepted -- the frame's two-seat limit binds only
    # where the frame is actually consulted.
    check_dsl(_grid_game("  players: 3\n", setup_extra=""), "frame3place.cardlang")


@pytest.mark.parametrize(
    "body",
    [
        "  when: is_diagonal(along)\n",  # is_diagonal takes a dir, not a player
    ],
)
def test_player_free_board_verb_in_a_non_two_player_game_is_accepted(body: str) -> None:
    # is_diagonal / lines read no frame (no player arg), so the two-seat limit
    # does not touch them: a 3-player grid game may call them.
    src = (
        "game FreeVerb {\n"
        "  players: 3\n"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        "  board: grid(8, 8)\n"
        "  pieces: xo_marks\n"
        "  zones { box : Deck  square[cell] : Cell<cell>  reserve[player] : PlayerPile<player> }\n"
        "  state { done : Boolean = false }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        "  }\n"
        "  phase play { turns t from 0 over all players until done "
        "{ offer to t one of [step, stop] } }\n"
        "  winner: highest done\n"
        "}\n"
        "move_type step(from : cell, along : dir) {\n"
        f"{body}"
        "  effect { move one piece from reserve[actor] to square[from] }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )
    check_dsl(src, "freeverb.cardlang")


# =============================================================================
# ARITY + ARG TYPE: each verb's Sig is enforced at the call site.
# =============================================================================


def test_wrong_arity_is_rejected() -> None:
    msg = _reject(_board_game(body="    let x = neighbor(from)\n"))
    assert "neighbor() expects 3 argument(s), got 1" in msg


def test_is_diagonal_cell_for_dir_is_rejected() -> None:
    # `from : cell` in scope -> a TCell where `is_diagonal` wants a TDir. (A
    # bare `a1` would be the walled cell-literal -> unresolved-name, a
    # different wall; a cell-typed binder is the real TCell-for-TDir probe.)
    msg = _reject(_board_game(body="    let x = is_diagonal(from)\n"))
    assert "is_diagonal() expects Dir, got Cell" in msg


def test_home_cell_for_player_is_rejected() -> None:
    msg = _reject(_board_game(body="    let x = home(from)\n"))
    assert "home() expects Player, got Cell" in msg


def test_along_dir_for_player_is_rejected() -> None:
    # `along : dir` -> a TDir where `home`/`neighbor`'s player slot wants a
    # TPlayer; proves TDir does not silently satisfy a Player parameter.
    msg = _reject(_board_game(body="    let x = home(along)\n"))
    assert "home() expects Player, got Dir" in msg


# =============================================================================
# CLASSIFICATION: the five verbs are BOARD_ONLY. The TOTAL partition (every
# CALL_FUNCS member classified generic/deck-only/board-only, none
# unclassified) is pinned once at tests/test_signatures.py::
# test_deck_only_classification_partitions_call_funcs and
# tests/test_piece_content_walls.py -- NOT re-copied here (CLAUDE.md rule 4).
# This focused pin names the five new members so their omission from
# BOARD_ONLY reddens with a message about THESE verbs.
#
# red under (the born-green partition pin, cited): dropping any of these five
# from BOARD_ONLY_CALL_FUNCS while leaving it in CALL_FUNCS reddens the
# partition assertion in test_signatures.py (union != CALL_FUNCS);
# dropping it here reddens this focused assertion directly.
# =============================================================================


def test_the_five_verbs_are_board_only() -> None:
    assert set(MOVEMENT_VERBS) <= BOARD_ONLY_CALL_FUNCS
    assert set(MOVEMENT_VERBS) <= CALL_FUNCS


# =============================================================================
# PAIRWISE: home/far_row are the language's first Collection<Cell> producers.
# Prove the new value shape is not SILENTLY swallowed by an existing operation
# that has no meaning for it (accepted-but-ignored), at the layer that owns
# each: the cell collection-quantifier (typecheck) and movement (resolve).
# =============================================================================


def test_any_cell_in_a_region_is_rejected_not_silently_iterated() -> None:
    # `any cell in <expr>` demands a SINGLE line (typecheck.py's
    # _domain_query_binder_type); a Collection<Cell> region is the wrong
    # source shape, so it is rejected -- home/far_row's shape is NOT quietly
    # accepted by the cell quantifier. (Region membership is `c in home(...)`,
    # built in Task 4; this pins that the QUANTIFIER form stays loud.)
    msg = _reject(
        _board_game(
            body=(
                "    if any cell in home(actor) where square[cell] is empty "
                "{ done := true }\n"
            )
        )
    )
    assert "iterates a single line, but the source is Collection<Cell>" in msg


def test_a_region_is_not_a_movement_source() -> None:
    # `move ... from home(actor)` -- a region is a computed Collection<Cell>,
    # not a zone. The movement `from` clause admits only a zone reference (a
    # bare/subscripted zone family), so a call expression is GRAMMATICALLY
    # inexpressible there: the region shape cannot even be spelled as a
    # movement source, the strongest form of "not silently treated as a zone".
    msg = _reject(
        _board_game(body="    move one piece from home(actor) to square[from]\n")
    )
    assert "syntax error" in msg
