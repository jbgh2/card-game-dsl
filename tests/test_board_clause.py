"""The `board:` clause: named-member position domains end to end.

A `board: grid(3, 3)` clause mints one position domain named `cell` whose
members are the board's cells (`a1`..`c3`, string members), riding the
landed `positions {}` substrate (decisions.md "Boards and cells"): same
collision guard, same two consumption surfaces (zone-family index,
move-parameter domain), same unowned rule. Cell values type as the new
`TCell`; integer position domains keep `TInteger` exactly.

This module is the grid for Task 6. Its two axes both derive from
registries, never from the guard's own coverage:

  * the clause-combination axis from `BOARD_FAMILIES`
    (cardlang/stdlib/boards.py) x the content-flavor stamp x the position
    collision `taken` set;
  * the TCell-consuming-operation axis from the language's value-position
    surface (the framing-check enumeration of every place a typed value can
    appear): parameter, let binder, zone index/type-arg, subscript index,
    each comparison/arithmetic operand class, state declaration type and
    index, quantifier role, bare-name expression.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a `board: <family>(<args>)` clause is validated against
            BOARD_FAMILIES, mints the `cell` domain (string members in
            registry order) only alongside `pieces:`, and that domain flows
            through every surface the integer position domains flow through
            (zone index, move parameter, unowned projection, action space)
            typed as TCell; every other TCell-consuming operation is either
            accepted or rejected with a diagnostic, never silently ignored.
domain:     {clause combinations} x {pipeline layers} UNION
            {TCell value positions} x {accept | reject | inexpressible}
registry:   cardlang/stdlib/boards.py::BOARD_FAMILIES (family/arity/bounds);
            cardlang/domains.py (position substrate); the value-position
            surface (grammar + Expr/Stmt unions).
covered:    clause axis, each cell proven by a run probe below --
              board alone (no pieces)        -> reject (resolve)
              board + cards                  -> reject (resolve)
              board + pieces                 -> accept
              duplicate board:               -> reject (parse, once())
              unknown family                 -> reject (resolve, board_entry)
              bad arity / bad bounds         -> reject (resolve, board_entry)
              missing arg list `board: grid` -> reject (resolve, arity 0 --
                                                the parse builder filters the
                                                placeholder None)
              collision with positions{cell} -> reject (resolve, names both)
              collision with a built-in name -> reject (reuses the standing
                                                guard; constant today, swept)
            TCell value-position axis, each proven by a run probe below --
              move parameter `place(at:cell)`        -> accept (TCell)
              let binder `let c = at`                -> accept (TCell)
              zone index + type arg `square[cell]:Cell<cell>` -> accept
              subscript index `square[at]`           -> accept
              subscript index `square[7]` (int)      -> reject (typecheck)
              subscript `tableau[at]` (cell on int)  -> reject (typecheck)
              equality `at is at2`                   -> accept
              equality `at is 3`                     -> reject (typecheck)
              ordering  `at < at2`                   -> reject (typecheck)
              arithmetic `at + 1`                    -> reject (typecheck)
              state decl type `foo : cell`           -> reject (resolve)
              state decl index `r[cell] : Integer`   -> reject (resolve)
              function parameter `f(x : cell)`       -> ADMIT, types as TCell
                                                (the payload-admit policy of
                                                `_check_declared_type_names`;
                                                x + 1 then rejects, proving it
                                                is TCell, not a TAny leak)
              variant payload `Won(cell)`            -> ADMIT, same policy
sampled:    the action-space round-trip (encode/decode) is proven on the
            nine `place` vocab ids of grid(3,3); the members-in-order
            property is proven on grid(3,3)'s row-major order (the registry
            owns the order, pinned in tests/test_boards_registry.py).
residual:   * cell CONSTANTS in expressions (a bare `a1`) are not
              expression surface at rung 1 -- `a1` stays an unknown-name
              diagnostic (proven below); witness = a game naming specific
              cells (breakthrough); issue #111.
            * quantifiers over `cell`/`line` (`any cell where`, `any line in
              lines(3) where`) LANDED in Task 7 -- the cell/line query
              register (tests/test_cell_queries.py owns that grid); the
              board-clause marker that the residual retired is
              test_quantifier_over_cell_is_accepted_after_the_task_7_lift
              below. `for each cell` STAYS rejected (no iteration witness;
              tests/test_cell_queries.py pins the standing diagnostic).
            * an INTEGER position-domain name (`lane`/`column`) in a function-
              parameter or variant-payload slot ADMITS identically, resolving
              to TInteger -- main's type-name grid
              (tests/test_type_name_positions.py) owns the integer cell; the
              board `cell` extension (TCell) is pinned here. Not a residual
              gap -- listed for the cross-module reader.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.board_domains import position_domains_of
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DomainSources, enumerate_domain, zone_observer_key
from cardlang.ir import emit
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

# grid(3, 3) cells, row-major from a1 (the boards registry's declared order;
# file letter = column from left, number = row from bottom).
NINE_CELLS = ("a1", "b1", "c1", "a2", "b2", "c2", "a3", "b3", "c3")


def board_game(
    *,
    content: str = "  pieces: xo_marks\n",
    board: str = "  board: grid(3, 3)\n",
    positions: str = "",
    square: str = "    square[cell]    : Cell<cell>\n",
    state: str = "    result[player] : Integer = 0\n",
    setup: str = (
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
    ),
    vocab: str = "place, stop",
    moves: str = (
        "move_type place(at : cell) {\n"
        "  when: square[at] is empty\n"
        "  effect { move one piece from reserve[actor] to square[at] }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    ),
) -> str:
    """A minimal board game (the Task 3 piece game + board + a placement).

    Parameters let a probe perturb exactly one surface (drop pieces, add a
    colliding positions block, swap a subscript) and leave the rest a proven
    honest game."""
    return (
        "game BoardSkeleton {\n"
        "  players: 2\n"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        f"{board}"
        f"{content}"
        f"{positions}"
        "  zones {\n"
        "    box             : Deck\n"
        f"{square}"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state {\n"
        f"{state}"
        "    done : Boolean = false\n"
        "  }\n"
        "  phase setup {\n"
        f"{setup}"
        "  }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        f"      offer to t one of [{vocab}]\n"
        "    }\n"
        "  }\n"
        "  winner: highest result\n"
        "}\n"
        f"{moves}"
    )


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "board.cardlang")
    parts = [exc.value.diagnostic.message]
    parts.extend(getattr(exc.value, "__notes__", []) or [])
    return "\n".join(parts)


# --- positive: the minimal board game is honest end to end -------------------


def test_minimal_board_game_checks_clean() -> None:
    check_dsl(board_game(), "board.cardlang")


def test_position_domains_of_returns_the_cell_union() -> None:
    game = check_dsl(board_game(), "board.cardlang")
    domains = position_domains_of(game)
    assert domains["cell"] == NINE_CELLS


def test_position_domains_of_unions_declared_positions_and_the_board() -> None:
    game = check_dsl(
        board_game(positions="  positions { lane : 1..2 }\n"), "board.cardlang"
    )
    domains = position_domains_of(game)
    assert domains["cell"] == NINE_CELLS
    assert domains["lane"] == (1, 2)


def test_enumerate_domain_yields_nine_members_in_registry_order() -> None:
    game = check_dsl(board_game(), "board.cardlang")
    static = enumerate_domain(
        "cell",
        DomainSources(suits=(), ranks=(), players=(0, 1), positions=position_domains_of(game)),
    )
    assert static == list(NINE_CELLS)


def test_driver_instantiates_nine_cell_zones_keyed_by_name() -> None:
    game = check_dsl(board_game(), "board.cardlang")
    captured: dict[str, RuntimeState] = {}

    def grab(rs: RuntimeState) -> None:
        captured["rs"] = rs

    def stopper(player: int, candidates: list[Any], k: int) -> list[Any]:
        return [next(c for c in candidates if c == ("stop", None))]

    play_game(game, random.Random(0), chooser=stopper, on_first_decision=grab)
    rs = captured["rs"]
    assert set(rs.zones.families["square"]) == set(NINE_CELLS)
    # every square instance is reachable by its string key
    for cell in NINE_CELLS:
        assert rs.zones.instance("square", cell).cards == []


def test_cell_zone_is_unowned_for_every_observer() -> None:
    game = check_dsl(board_game(), "board.cardlang")
    captured: dict[str, RuntimeState] = {}

    def grab(rs: RuntimeState) -> None:
        captured["rs"] = rs

    def stopper(player: int, candidates: list[Any], k: int) -> list[Any]:
        return [next(c for c in candidates if c == ("stop", None))]

    play_game(game, random.Random(0), chooser=stopper, on_first_decision=grab)
    rs = captured["rs"]
    # No observer IS a cell -- the family projects through `others` for all.
    for observer in (0, 1):
        assert zone_observer_key("cell", rs, observer) is None


def test_place_mints_nine_vocab_ids_and_round_trips() -> None:
    game = check_dsl(board_game(), "board.cardlang")
    space = ActionSpace.for_game(game)
    entries = [("place", cell) for cell in NINE_CELLS]
    for entry in entries:
        aid = space.encode(entry)
        assert space.decode(aid) == entry
    # nine distinct ids, one per member in registry order
    ids = [space.encode(e) for e in entries]
    assert len(set(ids)) == 9


def test_scripted_history_lands_pieces_on_named_squares() -> None:
    """Drive place(a1) [x], place(b1) [o], place(c1) [x], then stop; assert
    exact zone contents -- the three named squares hold one piece each, the
    other six are empty, and each reserve dropped by exactly its placements."""
    game = check_dsl(board_game(), "board.cardlang")
    captured: dict[str, RuntimeState] = {}
    script = iter(["a1", "b1", "c1"])

    def grab(rs: RuntimeState) -> None:
        captured["rs"] = rs

    def scripted(player: int, candidates: list[Any], k: int) -> list[Any]:
        want = next(script, None)
        if want is None:
            return [next(c for c in candidates if c == ("stop", None))]
        return [next(c for c in candidates if c == ("place", want))]

    play_game(game, random.Random(0), chooser=scripted, on_first_decision=grab)
    rs = captured["rs"]
    for cell in ("a1", "b1", "c1"):
        assert len(rs.zones.instance("square", cell).cards) == 1
    for cell in ("a2", "b2", "c2", "a3", "b3", "c3"):
        assert rs.zones.instance("square", cell).cards == []
    # reserve[0] = 5 x pieces, played a1 + c1 -> 3; reserve[1] = 4 o, played b1 -> 3
    assert len(rs.zones.instance("reserve", 0).cards) == 3
    assert len(rs.zones.instance("reserve", 1).cards) == 3


# --- TCell typing: accept the named-domain uses --------------------------------


def test_let_binder_carries_tcell() -> None:
    check_dsl(
        board_game(
            moves=(
                "move_type place(at : cell) {\n"
                "  when: square[at] is empty\n"
                "  effect {\n"
                "    let c = at\n"
                "    move one piece from reserve[actor] to square[c]\n"
                "  }\n"
                "}\n"
                "move_type stop { effect { done := true } }\n"
            )
        ),
        "board.cardlang",
    )


def test_two_cell_params_compare_by_equality() -> None:
    check_dsl(
        board_game(
            moves=(
                "move_type place(at : cell) {\n"
                "  when: square[at] is empty\n"
                "  effect { move one piece from reserve[actor] to square[at] }\n"
                "}\n"
                "move_type twin(at : cell, at2 : cell) {\n"
                "  when: at is at2\n"
                "  effect { done := true }\n"
                "}\n"
                "move_type stop { effect { done := true } }\n"
            ),
            vocab="place, twin, stop",
        ),
        "board.cardlang",
    )


# --- TCell typing: reject the wrong-kind operand -------------------------------


def _place_guard(guard: str) -> str:
    return board_game(
        moves=(
            f"move_type place(at : cell) {{\n"
            f"  when: {guard}\n"
            f"  effect {{ move one piece from reserve[actor] to square[at] }}\n"
            f"}}\n"
            f"move_type stop {{ effect {{ done := true }} }}\n"
        )
    )


def test_cell_equality_with_integer_is_rejected() -> None:
    assert "can never be equal" in _reject(_place_guard("at is 3"))


def test_cell_ordering_is_rejected() -> None:
    # ordering needs a second cell to compare; a lone `at < at` still hits the
    # Integers-only ordering guard.
    src = board_game(
        moves=(
            "move_type place(at : cell, at2 : cell) {\n"
            "  when: at < at2\n"
            "  effect { move one piece from reserve[actor] to square[at] }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        )
    )
    assert "compares Integers" in _reject(src)


def test_cell_arithmetic_is_rejected() -> None:
    src = board_game(
        moves=(
            "move_type place(at : cell) {\n"
            "  when: square[at] is empty\n"
            "  effect {\n"
            "    result[actor] := at + 1\n"
            "    move one piece from reserve[actor] to square[at]\n"
            "  }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        )
    )
    assert "expects Integer operands" in _reject(src)


def test_integer_subscript_of_a_cell_family_is_rejected() -> None:
    # square is keyed by TCell; a bare integer index can never denote a cell.
    assert "keyed by Cell" in _reject(_place_guard("square[7] is empty"))


def test_cell_index_on_an_integer_family_is_rejected() -> None:
    # `at : cell` (TCell) indexing an integer-keyed family (`rack[lane]`) is a
    # type error the other way -- one mechanism, both member kinds.
    src = board_game(
        positions="  positions { lane : 1..2 }\n",
        square="    square[cell]    : Cell<cell>\n    rack[lane]      : Cell<lane>\n",
        moves=(
            "move_type place(at : cell) {\n"
            "  when: rack[at] is empty\n"
            "  effect { move one piece from reserve[actor] to square[at] }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        ),
    )
    assert "keyed by Integer" in _reject(src)


# --- clause combination guards -------------------------------------------------


def test_board_without_pieces_is_rejected() -> None:
    # a card game with a board: the same guard as board+cards (parse enforces
    # cards XOR pieces, so "no pieces" and "has cards" are one condition).
    msg = _reject(
        board_game(
            content="  cards: standard52\n",
            setup="    move all cards from box to reserve[0]\n",
            state="    result[player] : Integer = 0\n",
        )
    )
    assert "board:" in msg and "pieces:" in msg


def test_board_with_cards_is_rejected() -> None:
    msg = _reject(
        board_game(
            content="  cards: standard52\n",
            setup="    move all cards from box to reserve[0]\n",
        )
    )
    assert "board:" in msg and "pieces:" in msg


def test_unknown_board_family_is_rejected() -> None:
    assert "unknown board family" in _reject(board_game(board="  board: hexgrid(3, 3)\n"))


def test_bad_board_arity_is_rejected() -> None:
    assert "argument" in _reject(board_game(board="  board: grid(3)\n"))


def test_missing_arg_list_is_rejected_not_a_crash() -> None:
    # `board: grid` (no parens) parses to zero args (the maybe_placeholders
    # None is filtered in the parse builder) and rejects at resolve with the
    # registry's arity message -- found as an int(None) VisitError crash by the
    # adversarial probe run.
    assert "takes 2 argument(s), got 0" in _reject(board_game(board="  board: grid\n"))


def test_out_of_bounds_board_args_are_rejected() -> None:
    assert "1..16" in _reject(board_game(board="  board: grid(0, 3)\n"))


def test_board_cell_collides_with_a_declared_position_name() -> None:
    msg = _reject(board_game(positions="  positions { cell : 1..9 }\n"))
    assert "cell" in msg and "board" in msg.lower()


def test_duplicate_board_clause_is_rejected() -> None:
    assert "board:" in _reject(
        board_game(board="  board: grid(3, 3)\n  board: grid(3, 3)\n")
    )


# --- position-typed state stays guarded (KNOWN_TYPE_NAMES unchanged) -----------


def test_cell_typed_state_variable_is_rejected() -> None:
    # `foo : cell` -- a position domain is not a declarable state TYPE.
    assert "unknown type 'cell' in declaration of 'foo'" in _reject(
        board_game(state="    result[player] : Integer = 0\n    foo : cell = a1\n")
    )


def test_cell_indexed_state_variable_is_rejected() -> None:
    # `r[cell] : Integer` -- cell is not a zone-index role for state either.
    assert "state variable 'r' is indexed by 'cell', which is not an indexable role" in _reject(
        board_game(state="    result[player] : Integer = 0\n    r[cell] : Integer = 0\n")
    )


def test_cell_function_parameter_admits_and_types_as_tcell() -> None:
    # A position domain is ADMITTED at a function parameter, resolving to its
    # member type rather than the permissive TAny (`_check_declared_type_names`;
    # tests/test_type_name_positions.py P6). For a board `cell` that member
    # type is TCell -- so `f(x : cell)` checks clean, and TCell's operand guards
    # fire (arithmetic on x is a type error), which is the leak-free guarantee
    # main's grid cannot reach (it exercises the integer `column`, not `cell`).
    check_dsl(board_game() + "function f(x : cell) = 1\n", "b.cardlang")
    assert "got Cell" in _reject(board_game() + "function f(x : cell) = x + 1\n")


def test_cell_variant_payload_admits() -> None:
    # The outcome/variant payload slot admits a position domain too -- the
    # sibling of the function-parameter slot, same policy (P7 in the grid).
    check_dsl(
        board_game() + "define D -> { Won(cell) | Lost } { produce Lost }\n",
        "b.cardlang",
    )


def test_integer_position_function_parameter_admits() -> None:
    # An INTEGER position domain in the same slot admits identically,
    # resolving to TInteger (main's grid covers this cell with `column`).
    check_dsl(
        board_game(positions="  positions { lane : 1..2 }\n")
        + "function f(x : lane) = 1\n",
        "b.cardlang",
    )


# --- residuals proven rejected (recorded above) -------------------------------


def test_bare_cell_constant_is_an_unknown_name() -> None:
    # cell CONSTANTS are not expression surface at rung 1: `a1` names nothing.
    assert _reject(_place_guard("at is a1"))


def test_quantifier_over_cell_is_accepted_after_the_task_7_lift() -> None:
    # `any cell where ...` was the Task-7 guard-lift; it is now LIVE (the
    # cell/line query register, tests/test_cell_queries.py). Kept here as the
    # cross-module marker that this board-clause residual retired.
    check_dsl(
        board_game(
            moves=(
                "move_type place(at : cell) {\n"
                "  when: any cell where square[cell] is empty\n"
                "  effect { move one piece from reserve[actor] to square[at] }\n"
                "}\n"
                "move_type stop { effect { done := true } }\n"
            )
        ),
        "board.cardlang",
    )


# --- byte-identity: integer positions untouched -------------------------------


def test_integer_position_ir_is_unchanged() -> None:
    # An integer position domain still emits {kind, name, lo, hi} with no
    # members key -- the board's named members must not perturb this.
    game = check_dsl(
        board_game(positions="  positions { lane : 1..2 }\n"), "board.cardlang"
    )
    ir_positions = emit(game)["positions"]
    assert isinstance(ir_positions, list)
    lane = next(p for p in ir_positions if isinstance(p, dict) and p["name"] == "lane")
    assert lane == {"kind": "position", "name": "lane", "lo": 1, "hi": 2}
