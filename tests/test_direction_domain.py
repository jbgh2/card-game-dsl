"""The movement-direction domain (`dir`): a second named-member domain end to end.

A `board: grid(...)` game mints a SECOND named-member domain, `dir`, whose
members are the three seat-relative forward directions (`ahead`, `ahead_left`,
`ahead_right`, in that fixed order). Unlike the board's `cell` domain, `dir` is
a SEPARATE per-game source (`cardlang/board_domains.py::directions_of`), NOT a
`PositionDecl` in `game.positions` (decisions.md "Boards and cells", rung-2
movement). Keeping it out of `game.positions` is load-bearing: the zone-index
wall (`_resolve_zone`), the quantifier wall (`_check_domain_query`) and the
for-each wall (`_ITERATION_ROLES`) all admit only `game.positions`/known roles,
so `zone[dir]`, `any dir where`, `for each dir` are rejected FOR FREE by the
existing walls -- no new exclusion wall. `dir` rides ONLY the move-parameter
enumeration (a new `DomainSources.directions` sibling of `positions`) plus IR
and the OpenSpiel encoding. Direction values type as the new `TDir`; a member
name is NOT expression-nameable (no direction literals -- `ahead` stays an
unknown name, the cell-literal twin).

This module is the grid for Task 1. Its axes derive from registries and the
language's value-position surface, never from a wall's own coverage:

  * GRID 1 -- the `Type`-consumer sweep (the centerpiece). The `Type` union has
    NO `assert_never` (it is handled by permissive isinstance-chains: `unify`,
    `assignable`, `subscriptable`, `_type_name`, the operand walls), so a
    brand-new value type risks falling through EVERY type wall SILENTLY (the
    permissive-top defect class, [[permissive-top-split]]). The axis is the
    grep-confirmed set of every function that consumes a `Type` -- the SAME
    surface `tests/test_board_clause.py` sweeps for `TCell` -- re-proven for a
    `dir` value. `TDir` is structurally identical to `TCell` (there is no
    `isinstance(_, TCell)` / `is_cell` anywhere in the front end -- both ride
    only the generic chains), so every consumer's reject branch
    (`unify -> None`, `assignable -> False`, `subscriptable -> False`, the
    operand walls' `else`) fires for `dir` by construction; each cell below
    PROVES it, so no permissive accept survives.
  * GRID 2 -- the use-position of the NAME `dir`: the one accepting slot (move
    parameter) against every rejecting slot (zone index, bare/collection
    quantifier, `for each`, member literal, state type, state index).
  * GRID 3 -- minting and collision: the `dir` source is minted with `cell` by
    the board; a declared `positions { dir : ... }` collides; a boardless `dir`
    parameter is unsupported; the movement `dir` domain is orthogonal to the
    turn-order `direction:` clause (`DIRECTION_VALUES` / `GAME_DIRECTIONS`).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a `board:` game mints the `dir` domain (the three seat-relative
            members in fixed order) as a SEPARATE source from `game.positions`;
            `dir` flows through the move-parameter enumeration (vocab ids that
            round-trip) typed as `TDir`; every `TDir`-consuming operation is
            either accepted or rejected with a diagnostic, never silently
            ignored; the name `dir` is admitted ONLY at a move parameter and
            rejected at every other use-position by the existing
            positions/roles walls; a member name is not expression-nameable.
domain:     {TDir value positions} x {accept | reject}   (GRID 1)
            UNION {use-positions of the name `dir`} x {accept | reject}  (GRID 2)
            UNION {minting / collision cases} x {accept | reject}        (GRID 3)
registry:   cardlang/board_domains.py (`directions_of`, `DIRECTION_DOMAIN`);
            cardlang/stdlib/boards.py (`BoardEntry.directions`); the
            `Type`-consumer surface (grep-confirmed: `types.py::unify`,
            `assignable`, `subscriptable`; `typecheck.py::_type_name`,
            `_check_equality_operands`, `_check_ordering_operands`,
            `_check_arithmetic_operands`, `_check_membership_operands`,
            `_check_offset_by_operands`, the subscript-key and assign-key
            checks); the value-position surface (grammar + Expr/Stmt unions).
covered:    GRID 1 -- each cell a run probe below --
              move parameter `pick(along : dir)`     -> accept (TDir, 3 vocab)
              let binder `let d = along`             -> accept (TDir)
              equality dir-vs-dir `along is along2`  -> accept (unify)
              equality dir-vs-cell `at is along`     -> reject (typecheck)
              equality dir-vs-int  `along is 3`      -> reject (typecheck)
              ordering `along < along2`              -> reject (typecheck)
              arithmetic `along + 1`                 -> reject (typecheck)
              subscript `along[actor]`               -> reject (subscriptable)
              zone-index `square[along]`             -> reject (keyed by Cell)
              assign-key `result[along] := 1`        -> reject (keyed by Player)
              membership `along in reserve[actor]`   -> reject (unify None)
              offset_by  `actor offset_by along`     -> reject (wants Direction)
                                                (the dir vs turn-order Direction
                                                disambiguation -- TDir is not
                                                TEnum("Direction"))
            GRID 2 -- use-position of the name `dir` (`dir` is move-param-only) --
              move parameter `along : dir`           -> accept (the ONE slot)
              zone index `sq[dir] : Cell<dir>`       -> reject (resolve, free)
              bare quantifier `any dir where`        -> reject (resolve, free)
              collection quantifier `any dir in ...` -> reject (resolve, free)
              for each `for each dir d`              -> reject (resolve, free)
              member literal `along is ahead`        -> reject (unknown name)
              state type `foo : dir`                 -> reject (resolve, free)
              state index `r[dir] : Integer`         -> reject (resolve, free)
              function parameter `f(x : dir)`        -> reject (unknown type
                                                'dir' -- NOT admitted like the
                                                position `cell`; `dir` is a
                                                separate, move-param-only source)
              variant payload `Won(dir)`             -> reject (unknown type,
                                                the loud twin)
            GRID 3 -- minting / collision --
              `dir` minted with `cell` (both present)-> accept
              directions_of / enumerate_domain order -> the 3 members, fixed
              action-space round-trip (3 dir ids)    -> encode/decode agree
              scripted playout picks a direction     -> the move applies
              `positions { dir : 1..3 }` (board game) -> reject (mint-site,
                                                mirrors the `cell` collision)
              `type dir = { … }` (board game)         -> reject (mint-site vs
                                                the reserved set, `cell`'s twin)
              boardless `foo(x : dir)`               -> reject (unsupported
                                                param domain -- no board, no
                                                `dir` source)
              orthogonal to the turn-order direction -> DIRECTION_DOMAIN == "dir"
                                                and a game with BOTH `direction:
                                                clockwise` and a `dir` parameter
                                                checks clean (born-green pin)
            byte-identity -- a card game (no board) emits no `directions` IR key.
sampled:    the action-space round-trip is proven on the three `pick` vocab ids
            of grid(3,3); the members-in-order property on the fixed
            seat-relative order (the registry owns it, pinned in
            tests/test_boards_registry.py once Task 2 lands the offsets).
residual:   * `role_static_members` (cardlang/domains.py) grows NO `dir` branch:
              `dir` is not a `for each` role (`_ITERATION_ROLES` excludes it, so
              `for each dir` is rejected at resolve -- proven below), so the
              function can never be asked for `"dir"` at runtime. Its existing
              `AssertionError` ("unknown role") is the live backstop; a `dir`
              branch there would be dead code (a vacuously-green cell). Reddening
              mutation: were `dir` ever added to `_ITERATION_ROLES`, the
              `for_each_dir_is_rejected` cell below flips and the backstop would
              fire -- the loud signal to wire the branch honestly.
            * a member name (`ahead`) as an expression stays an unknown-name
              diagnostic (no direction literals); witness for direction
              constants is deferred (issue #124), the cell-literal twin.
            * the movement VERBS (`neighbor`/`has_step`/`is_diagonal`) and the
              per-player frame offsets are later tasks; `BoardEntry.directions()`
              returns only the member NAMES here.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.board_domains import DIRECTION_DOMAIN, directions_of
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DomainSources, enumerate_domain
from cardlang.ir import emit
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# The three seat-relative forward directions, in the fixed registry order.
THREE_DIRS = ("ahead", "ahead_left", "ahead_right")


def direction_game(
    *,
    board: str = "  board: grid(3, 3)\n",
    positions: str = "",
    turn_direction: str = "  direction: clockwise\n",
    square: str = "    square[cell]    : Cell<cell>\n",
    state: str = "    result[player] : Integer = 0\n",
    setup: str = (
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
    ),
    vocab: str = "pick, stop",
    moves: str = (
        "move_type pick(along : dir) {\n"
        "  when: not done\n"
        "  effect { done := true }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    ),
    extra: str = "",
) -> str:
    """A minimal board game exposing a `dir` move parameter (the board_clause
    piece game + a `pick(along : dir)` move). The header carries the turn-order
    `direction: clockwise` clause AND the movement `dir` parameter, so the base
    game is the born-green orthogonality pin: the two namespaces coexist.

    Parameters let a probe perturb exactly one surface (swap the move's
    guard/effect, add a colliding `positions` block, drop the board) and leave
    the rest a proven-honest game."""
    return (
        "game DirectionSkeleton {\n"
        "  players: 2\n"
        f"{turn_direction}"
        "  max_length: 30\n"
        f"{board}"
        "  pieces: xo_marks\n"
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
        f"{extra}"
    )


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "dir.cardlang")
    parts = [exc.value.diagnostic.message]
    parts.extend(getattr(exc.value, "__notes__", []) or [])
    return "\n".join(parts)


def _pick_guard(guard: str) -> str:
    return direction_game(
        moves=(
            f"move_type pick(along : dir) {{\n"
            f"  when: {guard}\n"
            f"  effect {{ done := true }}\n"
            f"}}\n"
            f"move_type stop {{ effect {{ done := true }} }}\n"
        )
    )


def _pick_effect(effect: str) -> str:
    return direction_game(
        moves=(
            f"move_type pick(along : dir) {{\n"
            f"  when: not done\n"
            f"  effect {{ {effect} }}\n"
            f"}}\n"
            f"move_type stop {{ effect {{ done := true }} }}\n"
        )
    )


# --- positive: the minimal direction game is honest end to end ----------------


def test_minimal_direction_game_checks_clean() -> None:
    check_dsl(direction_game(), "dir.cardlang")


def test_directions_of_returns_the_three_seat_relative_members() -> None:
    game = check_dsl(direction_game(), "dir.cardlang")
    domains = directions_of(game)
    assert domains[DIRECTION_DOMAIN] == THREE_DIRS


def test_direction_domain_is_not_in_game_positions() -> None:
    # The load-bearing separation: `dir` is a SEPARATE source, so the board's
    # only `game.positions` entry is `cell` -- which is what gives `zone[dir]`,
    # `any dir where`, `for each dir` their free rejection below.
    game = check_dsl(direction_game(), "dir.cardlang")
    assert DIRECTION_DOMAIN not in {p.name for p in game.positions}
    assert "cell" in {p.name for p in game.positions}


def test_enumerate_domain_yields_three_members_in_order() -> None:
    game = check_dsl(direction_game(), "dir.cardlang")
    static = enumerate_domain(
        DIRECTION_DOMAIN,
        DomainSources(
            suits=(), ranks=(), players=(0, 1), directions=dict(directions_of(game))
        ),
    )
    assert static == list(THREE_DIRS)


def test_driver_enumerates_the_three_directions_as_candidates() -> None:
    game = check_dsl(direction_game(), "dir.cardlang")
    seen: dict[str, list[Any]] = {}

    def scripted(player: int, candidates: list[Any], k: int) -> list[Any]:
        seen.setdefault("cands", list(candidates))
        return [next(c for c in candidates if c == ("stop", None))]

    play_game(game, random.Random(0), chooser=scripted)
    picks = {c[1] for c in seen["cands"] if isinstance(c, tuple) and c[0] == "pick"}
    assert picks == set(THREE_DIRS)


def test_pick_mints_three_vocab_ids_and_round_trips() -> None:
    game = check_dsl(direction_game(), "dir.cardlang")
    space = ActionSpace.for_game(game)
    entries = [("pick", d) for d in THREE_DIRS]
    for entry in entries:
        aid = space.encode(entry)
        assert space.decode(aid) == entry
    ids = [space.encode(e) for e in entries]
    assert len(set(ids)) == 3


def test_scripted_playout_picks_a_direction_and_applies_the_move() -> None:
    game = check_dsl(direction_game(), "dir.cardlang")
    picks: list[Any] = []

    def scripted(player: int, candidates: list[Any], k: int) -> list[Any]:
        # `next(...)` would raise StopIteration if ("pick", "ahead_left") were
        # not a live candidate, so a completed run proves the direction move is
        # a valid, applied action.
        chosen = next(c for c in candidates if c == ("pick", "ahead_left"))
        picks.append(chosen)
        return [chosen]

    result = play_game(game, random.Random(0), chooser=scripted)
    # `pick` sets `done := true`, so player 0's single direction pick drives the
    # game to termination -- exactly one decision, and a result is produced.
    assert picks == [("pick", "ahead_left")]
    assert result is not None


# --- GRID 1: the Type-consumer sweep (accept the dir-domain uses) -------------


def test_let_binder_carries_tdir() -> None:
    check_dsl(_pick_effect("let d = along\n    done := true"), "dir.cardlang")


def test_two_dir_params_compare_by_equality() -> None:
    check_dsl(
        direction_game(
            moves=(
                "move_type twin(along : dir, along2 : dir) {\n"
                "  when: along is along2\n"
                "  effect { done := true }\n"
                "}\n"
                "move_type stop { effect { done := true } }\n"
            ),
            vocab="twin, stop",
        ),
        "dir.cardlang",
    )


# --- GRID 1: the Type-consumer sweep (reject the wrong-kind operand) ----------


def test_dir_vs_cell_equality_is_rejected() -> None:
    # A move with both a cell and a dir parameter: comparing them is a
    # cross-domain `is` the disjointness rule rejects (TDir vs TCell).
    src = direction_game(
        moves=(
            "move_type mix(at : cell, along : dir) {\n"
            "  when: at is along\n"
            "  effect { done := true }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        ),
        vocab="mix, stop",
    )
    assert "can never be equal" in _reject(src)


def test_dir_vs_integer_equality_is_rejected() -> None:
    assert "can never be equal" in _reject(_pick_guard("along is 3"))


def test_dir_ordering_is_rejected() -> None:
    src = direction_game(
        moves=(
            "move_type twin(along : dir, along2 : dir) {\n"
            "  when: along < along2\n"
            "  effect { done := true }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
        ),
        vocab="twin, stop",
    )
    assert "compares Integers" in _reject(src)


def test_dir_arithmetic_is_rejected() -> None:
    assert "expects Integer operands" in _reject(
        _pick_effect("result[actor] := along + 1\n    done := true")
    )


def test_subscripting_a_dir_is_rejected() -> None:
    # `along[...]` -- a direction is not a collection; `subscriptable(TDir)` is
    # False, so this rejects rather than falling through permissively.
    assert "not a collection" in _reject(_pick_guard("along[actor] is empty"))


def test_dir_as_a_zone_index_is_rejected() -> None:
    # `square[along]` -- the cell-keyed family rejects a direction key (the
    # subscript-key check: `assignable(TDir, TCell)` is False), so `dir` cannot
    # index a zone even though nothing declares that exclusion for `dir`.
    assert "keyed by Cell" in _reject(_pick_guard("square[along] is empty"))


def test_dir_as_an_assign_store_key_is_rejected() -> None:
    # `result[along] := 1` -- the write twin of the subscript-key check;
    # `result` is keyed by Player, so a direction key rejects.
    assert "keyed by Player" in _reject(
        _pick_effect("result[along] := 1\n    done := true")
    )


def test_dir_membership_is_rejected() -> None:
    # `along in reserve[actor]` -- the collection holds cards, and `unify(TDir,
    # TCard)` is None, so the membership can never be true.
    assert "never true" in _reject(_pick_guard("along in reserve[actor]"))


def test_dir_as_an_offset_by_operand_is_rejected() -> None:
    # `actor offset_by along` -- offset_by rotates a Player by the TURN-ORDER
    # Direction enum (left/right/across/hold). A movement `dir` (TDir) is a
    # DISTINCT type from TEnum("Direction"), so it rejects here -- the pin that
    # the two direction namespaces do not interact.
    assert "expects a Direction" in _reject(_pick_guard("(actor offset_by along) is actor"))


# --- GRID 2: dir is move-parameter-only (non-move-param declared slots reject) -


def test_dir_function_parameter_is_rejected() -> None:
    # `dir` is usable ONLY as a MOVE parameter -- NOT a function parameter. It
    # is a separate source, absent from `game.positions`, so resolve's declared-
    # type-name admit-set (positions + known types + declared types) excludes it
    # and rejects LOUDLY here (unlike the position `cell`, which that set
    # admits). This is the move-parameter-only restriction, not a silent TAny.
    assert "unknown type 'dir'" in _reject(
        direction_game(extra="function f(x : dir) = 1\n")
    )


def test_dir_variant_payload_is_rejected() -> None:
    # Same restriction at a variant payload slot: `dir` is rejected at resolve
    # ("unknown type 'dir'"), the loud twin of the function-parameter reject.
    assert "unknown type 'dir'" in _reject(
        direction_game(extra="define D -> { Won(dir) | Lost } { produce Lost }\n")
    )


# --- GRID 2: use-position of the name `dir` (rejected slots, free walls) -------


def test_dir_as_a_zone_index_role_is_rejected() -> None:
    # `sq[dir] : Cell<dir>` -- `dir` is not a `game.positions` name, so the
    # zone-index wall (`_resolve_zone`) rejects it with no new exclusion.
    assert "unknown index role 'dir'" in _reject(
        direction_game(square="    square[cell] : Cell<cell>\n    sq[dir] : Cell<dir>\n")
    )


def test_bare_quantifier_over_dir_is_rejected() -> None:
    # `any dir where ...` -- the quantifier wall validates against
    # `game.positions`, which excludes `dir`, so it rejects for free.
    assert "unknown position domain 'dir'" in _reject(
        _pick_guard("any dir where not done")
    )


def test_collection_quantifier_over_dir_is_rejected() -> None:
    # `any dir in <expr> where ...` -- `dir` is not a rung-1 collection noun
    # ({line, cell}), so the collection form rejects for free.
    assert "unknown collection noun 'dir'" in _reject(
        _pick_guard("any dir in reserve[actor] where not done")
    )


def test_for_each_dir_is_rejected() -> None:
    # `for each dir d:` -- `dir` is not in `_ITERATION_ROLES`, so it rejects for
    # free. (Reddening pin for the `role_static_members` residual: were `dir`
    # added to `_ITERATION_ROLES`, this cell would flip and the runtime backstop
    # would fire.)
    assert "unknown `for each` role 'dir'" in _reject(
        _pick_effect("for each dir d: done := true")
    )


def test_dir_member_name_is_an_unknown_name() -> None:
    # Naming a member (`ahead`) in an expression stays an unknown-name
    # diagnostic -- no direction literals, the cell-literal twin.
    assert "unresolved name 'ahead'" in _reject(_pick_guard("along is ahead"))


def test_dir_typed_state_variable_is_rejected() -> None:
    # `foo : dir` -- a direction domain is not a declarable state TYPE.
    assert "unknown type 'dir'" in _reject(
        direction_game(state="    result[player] : Integer = 0\n    foo : dir = ahead\n")
    )


def test_dir_indexed_state_variable_is_rejected() -> None:
    # `r[dir] : Integer` -- `dir` is not a zone-index role for state either.
    assert "not an indexable role" in _reject(
        direction_game(state="    result[player] : Integer = 0\n    r[dir] : Integer = 0\n")
    )


# --- GRID 3: minting and collision --------------------------------------------


def test_dir_collides_with_a_declared_position_name() -> None:
    # `positions { dir : 1..3 }` in a board game -- the board mints `dir`, so a
    # declared domain of the same name collides (the mint-site check, mirroring
    # the `cell` collision in test_board_clause.py).
    msg = _reject(direction_game(positions="  positions { dir : 1..3 }\n"))
    assert "dir" in msg


def test_dir_collides_with_a_declared_type_name() -> None:
    # `type dir = { … }` in a board game: the board mints `dir`, and direction
    # lookup precedes struct lookup, so without this wall `along : dir` reads
    # the minted domain while `dir` elsewhere denotes the struct -- one spelling,
    # two meanings. The `cell` mint already rejected this via the reserved set
    # (which includes declared type names); `dir` gets the same second check.
    msg = _reject(direction_game(extra="type dir = { x : Integer }\n"))
    assert "dir" in msg and ("built-in domain or type name" in msg)


def test_boardless_dir_parameter_is_unsupported() -> None:
    # A boardless game has no `dir` source, so a `dir` move parameter is an
    # unsupported parameter domain (the standing `_check_move_params` wall).
    src = (
        "game Boardless {\n"
        "  players: 2\n"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { done : Boolean = false }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [pick]\n"
        "    }\n"
        "  }\n"
        "  winner: highest done\n"
        "}\n"
        "move_type pick(along : dir) { effect { done := true } }\n"
    )
    assert "unsupported parameter domain 'dir'" in _reject(src)


def test_direction_domain_name_is_dir_not_direction() -> None:
    # The domain is `dir`, never `direction` (a reserved clause keyword, and the
    # turn-order enum's tag). This pins the orthogonality with the turn-order
    # `direction:` clause. Reddening mutation: rename DIRECTION_DOMAIN to
    # "direction" -> collides with the reserved keyword / TEnum("Direction").
    assert DIRECTION_DOMAIN == "dir"


def test_turn_order_direction_and_movement_dir_coexist() -> None:
    # The base game already carries `direction: clockwise` (turn order) AND a
    # `dir` move parameter; that it checks clean is the born-green orthogonality
    # pin. Made explicit here with a counterclockwise ring to vary the axis.
    check_dsl(direction_game(turn_direction="  direction: counterclockwise\n"), "dir.cardlang")


# --- byte-identity: a card game mints no direction source ---------------------


def test_card_game_emits_no_directions_ir_key() -> None:
    # `directions` is a board-minted source; a card game (no board) neither
    # mints it nor emits the IR key, so the card-game IR stays byte-stable.
    card = (
        "game Cardish {\n"
        "  players: 2\n"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { done : Boolean = false }\n"
        "  phase play { shuffle deck }\n"
        "  winner: highest done\n"
        "}\n"
    )
    game = check_dsl(card, "card.cardlang")
    assert directions_of(game) == {}
    assert "directions" not in emit(game)
