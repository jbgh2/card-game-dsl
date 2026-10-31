"""The board's direction domain as a quantifier noun and a declared type.

A `board:` game mints the movement-direction domain `dir`
(`cardlang/board_domains.py`, `DIRECTION_DOMAIN`). Beside the move parameter,
the name is admitted at the bare quantifier family (`any dir where`, `all dirs
where`, `number of dirs where`, binder typed `TDir`) and at the two declared-
type positions resolve's `_check_declared_type_names` owns, function
parameters and outcome payloads (decisions.md "Boards and cells"). A direction
is not a position, so `zone[dir]` and `for each dir` stay refused
(tests/test_direction_domain.py, GRID 2).

This module is the grid for the lift, its misuse probes, and its execution
witness:

  * GRID A -- the quantifier kind (`n.DOMAIN_QUERY_KIND_PHRASE`) crossed with
    the expression host. Each host's template is pinned to the AST field the
    query lands in, so two hosts can never collapse into one position.
  * GRID R -- the runtime value of each kind, the expected fold computed from
    the board entry's own geometry (`BoardEntry.directions`, `is_diagonal`,
    `has_step`), read in a function body, a state default and a nested
    cell-and-direction scan.
  * GRID C -- the binder at every argument slot of every Builtin whose
    signature takes a `TDir` (`CALL_SIGS`): admitted at the `TDir` slot,
    refused at every other slot, and a cell refused at the `TDir` slot.
  * GRID T -- the declared type at a function parameter and an outcome
    payload types `TDir`, never the permissive top: each is used where only a
    direction is legal, and misused where only a direction is wrong.
  * The misuse probes -- the plausible wrong sentences, each refused loud.
  * The witness -- a draughts-shaped probe over breakthrough's board whose
    mandatory capture is the conditional offer over `can_jump`, a function
    scanning `any cell where ... (any dir where jump_ok(cell, dir, p))`; a
    uniform playout checks at every decision that the scan's verdict and the
    enumerated `jump` candidates agree.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   in a game whose board mints `dir`, every bare quantifier kind over
            `dir` checks in every expression host, binds a `TDir` that every
            `TDir`-consuming Builtin slot admits and every other slot refuses,
            and evaluates over the board entry's direction members; `dir` at
            a function parameter or outcome payload types `TDir`; and a
            function both a move type's When Clause and a turn-body scan call
            gives the two one answer, so the scan's verdict is the offer's.
domain:     {kind: `n.DOMAIN_QUERY_KIND_PHRASE`} x {host: function body,
            When Clause, phase predicate, `until`, the result clause's
            selection, effect condition, state default} (GRID A), each host
            pinned to its AST field; {kind} x {reader: function body, state
            default} plus the nested cell-and-direction scan (GRID R);
            {Builtin with a `TDir` parameter in `CALL_SIGS`} x {argument
            slot} (GRID C); {function parameter, outcome payload} x {use that
            only a direction admits, misuse that only a direction refuses}
            (GRID T). Rule clauses sit outside the host axis by construction:
            a rule binds at a trick round's card decision, and a board game
            holds pieces, never a trick round. A frame-free scan checks at any
            seat count. Library text names no board-minted domain, so a
            library's `dir` -- a quantifier noun, a function parameter, a
            `requires` row -- is refused in the library's file, as its `cell`
            is. A `primitives { }` entry, a procedure parameter, a state type
            and an optional move parameter keep their own closed domains,
            which hold no `dir`. The noun's spelling, the boardless and
            invalid-board cells, and the use-positions that stay refused are
            tests/test_direction_domain.py's GRID 2 and GRID 3.
registry:   kinds: cardlang/ast/nodes.py::DOMAIN_QUERY_KIND_PHRASE; Builtin
            slots: cardlang/builtins/signatures.py::CALL_SIGS; direction
            members and geometry: cardlang/stdlib/boards.py::BoardEntry;
            the minted name: cardlang/board_domains.py::DIRECTION_DOMAIN;
            the use-position grid: tests/test_direction_domain.py; the
            primitive entry's refusal:
            tests/test_primitives_block.py::test_an_unspellable_type_name_is_refused.
held by:    Derived and Pinned. The admission is one Owner Guard over one
            gate in resolve, which the move parameter, the bare quantifier
            and the declared type all read, so the three positions cannot
            disagree on whether a board minted `dir`; the binder's type and
            the evaluator's members each read the one direction source behind
            it, and each raises as a Shadow Guard on a noun in neither source.
            The noun is a string resolved against a per-game source, which no
            union the type checker sees can hold.
does not prove:  that the host axis is every expression position a
            quantifier can occupy. The hosts are the positions a designer
            writes a board predicate in, authored rather than derived from
            the AST's `Expr` fields; what carries the rest is that resolve
            validates every `DomainQuery` in one walk of the whole game and
            the type checker types every one in one arm, so a host outside
            this grid reaches the same two sites. And the witness's
            agreement is measured over the seeds it plays, not proven for
            every line of the probe.

red under (witness, game): adding `and (from in home(actor))` to the probe's
`jump` When Clause makes `jump` stricter than `can_jump`, and the playout ends
in the no-implicit-actions refusal for a `jump` offer with no legal member.

red under (witness, engine): in `cardlang/runtime/evaluate.py::_domain_query`,
truncating the direction members to their first (`ahead`, never diagonal)
makes `can_jump` false where a jump stands, and the playout meets a `jump`
candidate offered beside the steps.
"""

from __future__ import annotations

import random
import typing
from collections.abc import Callable, Iterator
from dataclasses import fields, is_dataclass, replace
from typing import Any

import pytest

import cardlang.resolve as resolve_module
from cardlang.ast import nodes as n
from cardlang.board_domains import DIRECTION_DOMAIN, directions_of, position_domains_of
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import RuntimeState
from cardlang.stdlib.boards import board_entry
from cardlang.typecheck import TypeEnv, _domain_query_binder_type, _type_name
from cardlang.types import TBoolean, TCell, TDir, TPlayer, Type
from tests.test_cell_queries import _board_ctx, _checked_board_expr

KINDS = tuple(n.DOMAIN_QUERY_KIND_PHRASE)


def _noun(kind: str) -> str:
    # `any` takes the singular noun, `all` and `number of` the plural (the
    # plural convention resolve's `_check_domain_query` holds).
    return DIRECTION_DOMAIN if kind == "any" else DIRECTION_DOMAIN + "s"


def _query(kind: str, pred: str) -> str:
    return f"{n.DOMAIN_QUERY_KIND_PHRASE[kind]} {_noun(kind)} where {pred}"


def _boolean(kind: str, pred: str = f"is_diagonal({DIRECTION_DOMAIN})") -> str:
    """The kind's query as a Boolean: a count is compared, the folds stand."""
    q = _query(kind, pred)
    return f"(({q}) > 0)" if kind == "count" else f"({q})"


def board_game(
    *,
    board: str = "  board: grid(3, 3)\n",
    state: str = "",
    setup: str = "",
    phase_qualifier: str = "",
    until: str = "done",
    when: str = "not done",
    effect: str = "done := true",
    result: str = "  winner: highest result\n",
    extra: str = "",
) -> str:
    """A two-seat `grid(3, 3)` piece game with one `pick(at : cell, along :
    dir)` move and a `stop`; every keyword argument is one host a probe
    rewrites, and the defaults are a game that checks and plays."""
    return (
        "game DirectionLift {\n"
        "  players: 2\n"
        "  max_length: 30\n"
        f"{board}"
        "  pieces: xo_marks\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    square[cell]    : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state {\n"
        "    result[player] : Integer = 0\n"
        "    done : Boolean = false\n"
        f"{state}"
        "  }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        f"{setup}"
        "  }\n"
        f"  phase play{phase_qualifier} {{\n"
        f"    turns t from 0 over all players until {until} {{\n"
        "      offer to t one of [pick, stop]\n"
        "    }\n"
        "  }\n"
        f"{result}"
        "}\n"
        "move_type pick(at : cell, along : dir) {\n"
        f"  when: {when}\n"
        f"  effect {{ {effect} }}\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
        f"{extra}"
    )


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "lift.cardlang")
    parts = [str(exc.value), exc.value.diagnostic.message]
    parts.extend(getattr(exc.value, "__notes__", []) or [])
    return "\n".join(parts)


_EXPR_TYPES: frozenset[type] = frozenset(typing.get_args(n.Expr))


def _query_hosts(node: object, host: tuple[str, str] | None = None) -> Iterator[tuple[str, str]]:
    """For every bare `dir` query in `node`, the (node type, field) of its
    nearest enclosing node that is not an expression: the position it is
    hosted in, seen through any expression wrapping it."""
    if isinstance(node, (tuple, list)):
        for item in node:
            yield from _query_hosts(item, host)
        return
    if not is_dataclass(node) or isinstance(node, type):
        return
    if (
        isinstance(node, n.DomainQuery)
        and node.source is None
        and node.binder == DIRECTION_DOMAIN
    ):
        assert host is not None
        yield host
    for f in fields(node):
        child_host = host if type(node) in _EXPR_TYPES else (type(node).__name__, f.name)
        yield from _query_hosts(getattr(node, f.name), child_host)


# --- GRID A: kind x host ------------------------------------------------------

# A predicate with no call in it: a state default refuses every call
# (`resolve._check_state_default_scope`), the Builtins' included, so that host
# reads the members without a verb.
CALL_FREE = "true"

# host -> (the game with the Boolean query `b` hosted there, the AST field the
# query must land in).
HOSTS: dict[str, tuple[Callable[[str], str], tuple[str, str]]] = {
    "function body": (
        lambda b: board_game(
            state="    probe : Boolean = false\n",
            setup="    probe := scan(0)\n",
            extra=f"function scan(p : Player) = {b}\n",
        ),
        ("FunctionDef", "body"),
    ),
    "When Clause": (
        lambda b: board_game(when=f"(not done) and ({b} or true)"),
        ("MoveTypeDef", "when"),
    ),
    "phase predicate": (
        lambda b: board_game(phase_qualifier=f" repeat until {b} or done"),
        ("PhaseQualifier", "expr"),
    ),
    "until": (
        lambda b: board_game(until=f"done or ({b} and done)"),
        ("Turns", "until"),
    ),
    "result clause": (
        lambda b: board_game(
            result=f"  loser: the player where {b} and (result[player] < 0)\n"
        ),
        ("Loser", "selection"),
    ),
    "effect condition": (
        lambda b: board_game(effect=f"if {b} {{ result[actor] := 1 }}\n    done := true"),
        ("IfStmt", "cond"),
    ),
    "state default": (
        lambda b: board_game(state=f"    probe : Boolean = {b}\n"),
        ("StateDecl", "default"),
    ),
}


def test_the_skeleton_checks_and_plays() -> None:
    """The control: the host-free game checks and plays to its end, so a
    host cell's verdict is the host's alone."""
    game = check_dsl(board_game(), "lift.cardlang")
    play_game(game, random.Random(0))


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize("host", sorted(HOSTS))
@pytest.mark.parametrize("kind", KINDS)
def test_a_direction_quantifier_checks_in_every_host(kind: str, host: str) -> None:
    build, field = HOSTS[host]
    pred = CALL_FREE if host == "state default" else f"is_diagonal({DIRECTION_DOMAIN})"
    game = check_dsl(build(_boolean(kind, pred)), "lift.cardlang")
    assert list(_query_hosts(game)) == [field]


# --- GRID R: the runtime value of each kind ------------------------------------


def _fold(kind: str, truths: list[bool]) -> bool | int:
    match kind:
        case "any":
            return any(truths)
        case "all":
            return all(truths)
        case "count":
            return sum(truths)
    raise AssertionError(f"kind {kind!r} has no fold here")


def _entry() -> Any:
    return board_entry("grid", (3, 3))


def _played_state(source: str, *names: str) -> dict[str, Any]:
    """Play `source` to its end with the first seat stopping at once, and read
    the named game-level state variables off the live world."""
    game = check_dsl(source, "lift.cardlang")
    held: list[RuntimeState] = []

    def stop(player: int, candidates: list[Any], k: int) -> list[Any]:
        return [next(c for c in candidates if c == ("stop", None))]

    play_game(game, random.Random(0), chooser=stop, on_first_decision=held.append)
    assert held, "the game made no decision"
    return {name: held[0].get(name) for name in names}


def _state_type(kind: str) -> str:
    return "Integer = 0" if kind == "count" else "Boolean = false"


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize("kind", KINDS)
def test_a_function_body_folds_the_board_directions(kind: str) -> None:
    entry = _entry()
    expected = _fold(kind, [entry.is_diagonal(d) for d in entry.directions()])
    source = board_game(
        state=f"    probe : {_state_type(kind)}\n",
        setup="    probe := scan(0)\n",
        extra=f"function scan(p : Player) = {_query(kind, 'is_diagonal(dir)')}\n",
    )
    assert _played_state(source, "probe") == {"probe": expected}


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize("kind", KINDS)
def test_a_state_default_folds_the_board_directions(kind: str) -> None:
    # The predicate holds of every member, so the fold reads the member count.
    expected = _fold(kind, [True for _ in _entry().directions()])
    source = board_game(
        state=f"    probe : {'Integer' if kind == 'count' else 'Boolean'} = "
        f"{_query(kind, CALL_FREE)}\n"
    )
    assert _played_state(source, "probe") == {"probe": expected}


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize("seat", [0, 1])
@pytest.mark.parametrize("kind", ["any", "all"])
def test_a_nested_scan_reads_each_seat_frame(kind: str, seat: int) -> None:
    """`number of cells where <kind> dir... where has_step(cell, dir, p)`: the
    direction binder is the Builtin's `TDir` argument, the cell binder its
    `TCell`, and the seat its frame -- each seat's count from the board entry."""
    entry = _entry()
    cells = position_domains_of(check_dsl(board_game(), "lift.cardlang"))["cell"]
    expected = sum(
        1
        for c in cells
        if _fold(kind, [entry.has_step(c, d, seat) for d in entry.directions()])
    )
    source = board_game(
        state="    probe : Integer = 0\n",
        setup=f"    probe := scan({seat})\n",
        extra=(
            "function scan(p : Player) = number of cells where "
            f"({_query(kind, 'has_step(cell, dir, p)')})\n"
        ),
    )
    assert _played_state(source, "probe") == {"probe": expected}


# --- GRID C: the binder at every Builtin slot -----------------------------------

_DIR_SIGS = {name: sig for name, sig in CALL_SIGS.items() if any(isinstance(p, TDir) for p in sig.params)}

# A well-typed argument for each slot type the `TDir` Builtins hold.
_FILLERS: dict[type, str] = {TCell: "cell", TDir: DIRECTION_DOMAIN, TPlayer: "p"}


def _slot_cells() -> list[tuple[str, int]]:
    return [(name, i) for name, sig in sorted(_DIR_SIGS.items()) for i in range(len(sig.params))]


def _call(name: str, args: list[str]) -> str:
    call = f"{name}({', '.join(args)})"
    ret = CALL_SIGS[name].ret
    if isinstance(ret, TBoolean):
        return call
    assert isinstance(ret, TCell), f"{name} returns {ret}; give it a Boolean reading here"
    return f"(square[{call}] is empty)"


def _scan_game(call: str) -> str:
    return board_game(
        extra=(
            "function scan(p : Player) = any cell where "
            f"(any {DIRECTION_DOMAIN} where {call})\n"
        )
    )


def test_the_direction_builtins_are_the_movement_verbs() -> None:
    """The axis is non-empty and every slot type has a filler, so no slot is
    dropped from the grid for want of a well-typed argument."""
    assert _DIR_SIGS
    for sig in _DIR_SIGS.values():
        assert {type(p) for p in sig.params} <= set(_FILLERS)


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize("name", sorted(_DIR_SIGS))
def test_the_binder_fills_every_direction_slot(name: str) -> None:
    args = [_FILLERS[type(p)] for p in CALL_SIGS[name].params]
    check_dsl(_scan_game(_call(name, args)), "lift.cardlang")


def _wrong_slot_cells() -> list[tuple[str, int, str, Type, Type]]:
    """(builtin, slot, argument, slot type, argument type): the direction
    binder at every slot that is not a direction, and a cell at every slot
    that is."""
    cells: list[tuple[str, int, str, Type, Type]] = []
    for name, i in _slot_cells():
        want = CALL_SIGS[name].params[i]
        if isinstance(want, TDir):
            cells.append((name, i, "cell", want, TCell()))
        else:
            cells.append((name, i, DIRECTION_DOMAIN, want, TDir()))
    return cells


@pytest.mark.xfail(raises=AssertionError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize(("name", "slot", "arg", "want", "got"), _wrong_slot_cells())
def test_a_wrong_slot_argument_is_refused(name: str, slot: int, arg: str, want: Type, got: Type) -> None:
    args = [_FILLERS[type(p)] for p in CALL_SIGS[name].params]
    args[slot] = arg
    msg = _reject(_scan_game(_call(name, args)))
    assert f"{name}() expects {_type_name(want)}, got {_type_name(got)}" in msg


# The binder against each operator class and the zone index: a direction is an
# opaque member, compared only with another direction.
_OPERAND_MISUSES: dict[str, tuple[str, str]] = {
    "against a cell": ("cell is dir", "can never be equal"),
    "against an integer": ("dir is 3", "can never be equal"),
    "ordered": ("dir < dir", "compares Integers"),
    "arithmetic": ("(dir + 1) > 0", "expects Integer operands"),
    "zone index": ("square[dir] is empty", "keyed by Cell"),
    "field": ("dir.side is x", "has no fields"),
}


@pytest.mark.xfail(raises=AssertionError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize("use", sorted(_OPERAND_MISUSES))
def test_the_binder_is_an_opaque_member(use: str) -> None:
    pred, needle = _OPERAND_MISUSES[use]
    msg = _reject(
        board_game(extra=f"function scan(p : Player) = any cell where (any dir where {pred})\n")
    )
    assert needle in msg
    assert "unknown position domain" not in msg


# --- GRID T: the declared type is TDir, never the top -------------------------


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
def test_a_direction_parameter_reaches_the_movement_verbs() -> None:
    check_dsl(
        board_game(
            when="(not done) and step_ok(at, along, actor)",
            extra=(
                "function step_ok(from : cell, d : dir, p : Player) =\n"
                "  has_step(from, d, p) and (square[neighbor(from, d, p)] is empty)\n"
            ),
        ),
        "lift.cardlang",
    )


@pytest.mark.xfail(raises=AssertionError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ("d is 3", "can never be equal"),
        ("d is c", "can never be equal"),
        ("square[d] is empty", "keyed by Cell"),
        ("home(d) is empty", "home() expects Player, got Dir"),
    ],
)
def test_a_direction_parameter_types_dir(body: str, needle: str) -> None:
    msg = _reject(board_game(extra=f"function f(d : dir, c : cell) = {body}\n"))
    assert needle in msg
    assert "unknown type 'dir'" not in msg


def _payload_game(*, produce: str = "produce Lost", arm: str = "") -> str:
    return board_game(
        setup=(
            "    phase d -> outcome { Won(dir) | Lost } { " + produce + " }\n"
            "    d produces:\n"
            "      Won(x) { " + arm + " }\n"
            "      Lost   { }\n"
        )
    )


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
def test_a_direction_payload_binds_a_direction() -> None:
    check_dsl(_payload_game(arm="if is_diagonal(x) { done := false }"), "lift.cardlang")


@pytest.mark.xfail(raises=AssertionError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.parametrize(
    ("produce", "arm", "needle"),
    [
        ("produce Won(1)", "", "outcome case 'Won' expects Dir, got Integer"),
        ("produce Lost", "result[x] := 1", "keyed by Player"),
    ],
)
def test_a_direction_payload_types_dir(produce: str, arm: str, needle: str) -> None:
    msg = _reject(_payload_game(produce=produce, arm=arm))
    assert needle in msg
    assert "unknown type 'dir'" not in msg


# --- misuse probes --------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        # The turn-order word for the movement noun: the universe names `dir`.
        pytest.param(
            board_game(when="any direction where is_diagonal(direction)"),
            "movement-direction domain: dir",
            marks=pytest.mark.xfail(
                raises=AssertionError, strict=True, reason="the dir lift is not built yet"
            ),
        ),
        # A direction parameter on a procedure: the procedure domains stay closed.
        (
            board_game(extra="procedure turn_to(d : dir) { done := true }\n"),
            "procedure parameter 'd: dir' has an unsupported domain",
        ),
        # An optional direction on a move parameter: the move domain is `dir` exactly.
        (
            board_game().replace("along : dir)", "along : dir?)"),
            "unsupported parameter domain 'dir?'",
        ),
        # A direction-typed state variable: still no declarable state type.
        (
            board_game(state="    facing : dir = ahead\n"),
            "unknown type 'dir'",
        ),
    ],
    ids=["turn-order word", "procedure parameter", "optional move parameter", "state type"],
)
def test_a_plausible_wrong_sentence_is_refused(source: str, needle: str) -> None:
    assert needle in _reject(source)


_LIB = "probe_lib"


@pytest.mark.parametrize(
    "body",
    [
        "function lib_scan(p : Player) = any dir where is_diagonal(dir)",
        "function lib_f(d : dir) = is_diagonal(d)",
        "requires { lib_g(d : dir) : Boolean }",
    ],
    ids=["quantifier", "function parameter", "requires row"],
)
def test_a_library_naming_dir_is_refused_in_its_own_file(
    body: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library cannot assume the importing game's board, so `dir` stays a
    name a library lacks, as `cell` is; the refusal stands in the library's
    file. Its words are issue #1008."""
    library = parse_library(f"library {_LIB} {{\n{body}\n}}\n", f"docs/libraries/{_LIB}.cardlang")
    monkeypatch.setattr(resolve_module, "library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr(resolve_module, "load_library", lambda name: library)
    msg = _reject(board_game().replace("  players: 2\n", f"  uses {_LIB}\n  players: 2\n", 1))
    assert f"docs/libraries/{_LIB}.cardlang" in msg
    assert "'dir'" in msg or "d : dir" in msg


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
def test_a_frame_free_direction_scan_checks_at_any_seat_count() -> None:
    """`is_diagonal` reads no seat's frame, so a three-seat grid game scans its
    directions; the frame verbs' two-seat gate is theirs alone."""
    check_dsl(
        board_game(extra="function scan(p : Player) = any dir where is_diagonal(dir)\n").replace(
            "players: 2", "players: 3"
        ),
        "lift.cardlang",
    )


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
def test_a_nested_direction_binder_shadows_the_outer() -> None:
    """The inner `dir` rebinds, as a nested `cell` does: legal, and the inner
    binder is the one the predicate reads."""
    entry = _entry()
    expected = any(any(entry.is_diagonal(inner) for inner in entry.directions()) for _ in entry.directions())
    source = board_game(
        state="    probe : Boolean = false\n",
        setup="    probe := scan(0)\n",
        extra="function scan(p : Player) = any dir where (any dir where is_diagonal(dir))\n",
    )
    assert _played_state(source, "probe") == {"probe": expected}


# --- the Shadow Guards behind resolve's noun check --------------------------------


def _unknown_noun_query() -> tuple[n.Game, n.DomainQuery]:
    """A checked bare `cell` query, renamed to a noun no source holds: the tree
    resolve's `_check_domain_query` never lets through."""
    game, expr = _checked_board_expr("any cell where true")
    assert isinstance(expr, n.DomainQuery)
    return game, replace(expr, binder="nowhere", spelled="nowhere")


@pytest.mark.xfail(raises=pytest.fail.Exception, strict=True, reason="the dir lift is not built yet")
@pytest.mark.expects_shadow_guard
def test_the_binder_type_refuses_a_noun_in_neither_source() -> None:
    """Red under: the bare arm of `typecheck._domain_query_binder_type` falling
    back to the permissive top for a noun it does not find."""
    game, query = _unknown_noun_query()
    env = TypeEnv(positions={"cell": TCell()}, directions={DIRECTION_DOMAIN: TDir()})
    with pytest.raises(ShadowGuardError, match="_check_domain_query"):
        _domain_query_binder_type(query, env, DiagnosticBag())


@pytest.mark.xfail(raises=KeyError, strict=True, reason="the dir lift is not built yet")
@pytest.mark.expects_shadow_guard
def test_the_evaluator_refuses_a_noun_in_neither_source() -> None:
    """Red under: the bare arm of `evaluate._domain_query` indexing the position
    domains alone (a raw `KeyError`, outside the typed channel)."""
    game, query = _unknown_noun_query()
    ctx = _board_ctx(game, {})
    ctx.rs.direction_domains = dict(directions_of(game))
    with pytest.raises(ShadowGuardError, match="_check_domain_query"):
        evaluate(query, ctx)


# --- the execution witness: one body, two readers --------------------------------

# Breakthrough's board and men; a man steps one square forward onto an empty
# square, and captures by a diagonal jump over an adjacent enemy man to the
# empty square beyond. Capture is mandatory: a seat that can jump must jump
# (the conditional offer). The `else` branch offers `jump` beside `step` so a
# jump the scan missed would surface as a candidate there.
WITNESS = """
game MandatoryCaptureProbe {
  players: 2
  direction: clockwise
  max_length: 500
  board: grid(8, 8)
  pieces: breakthrough_men
  zones {
    box              : Deck
    square[cell]     : Cell<cell>
    reserve[player]  : PlayerPile<player>
    captured[player] : PlayerPile<player>
  }
  state {
    result[player]      : Integer = 0
    pieces_left[player] : Integer = 16
    capturing           : Boolean = false
  }
  phase setup {
    move all pieces from box where piece.side is light to reserve[0]
    move all pieces from box to reserve[1]
    for each cell c: if c in home(0) { move one piece from reserve[0] to square[c] }
    for each cell c: if c in home(1) { move one piece from reserve[1] to square[c] }
  }
  phase play {
    turns t from 0 over all players
          until (any player where result[player] is 1)
                or (any player where pieces_left[player] is 0) {
      capturing := can_jump(t)
      if capturing {
        offer to t one of [jump]
      } else {
        offer to t one of [step, jump]
      }
    }
  }
  winner: highest result
}

function side_of(p : Player) = if p is 0 then light else dark
function opponent_of(p : Player) = if p is 0 then 1 else 0
function mine(c : cell, p : Player) =
  (square[c] is not empty) and (top_of(square[c]).side is side_of(p))

function jump_ok(from : cell, along : dir, p : Player) =
  mine(from, p)
  and is_diagonal(along)
  and has_step(from, along, p)
  and (square[neighbor(from, along, p)] is not empty)
  and (top_of(square[neighbor(from, along, p)]).side is not side_of(p))
  and has_step(neighbor(from, along, p), along, p)
  and (square[neighbor(neighbor(from, along, p), along, p)] is empty)

function can_jump(p : Player) =
  any cell where mine(cell, p) and (any dir where jump_ok(cell, dir, p))

move_type step(from : cell, along : dir) {
  when: mine(from, actor)
        and has_step(from, along, actor)
        and (square[neighbor(from, along, actor)] is empty)
  effect {
    let foe = opponent_of(actor)
    let dest = neighbor(from, along, actor)
    move one piece from square[from] to square[dest]
    if dest in far_row(actor) {
      result[actor] := 1
      result[foe] := -1
    }
  }
}

move_type jump(from : cell, along : dir) {
  when: jump_ok(from, along, actor)
  effect {
    let foe = opponent_of(actor)
    let over = neighbor(from, along, actor)
    let dest = neighbor(over, along, actor)
    move one piece from square[over] to captured[foe]
    pieces_left[foe] := pieces_left[foe] - 1
    if pieces_left[foe] is 0 {
      result[actor] := 1
      result[foe] := -1
    }
    move one piece from square[from] to square[dest]
    if dest in far_row(actor) {
      result[actor] := 1
      result[foe] := -1
    }
  }
}
"""

WITNESS_SEEDS = (0, 1, 2)


def _candidate_kind(candidate: Any) -> str:
    assert isinstance(candidate, tuple) and isinstance(candidate[0], str), candidate
    return candidate[0]


@pytest.mark.xfail(raises=DiagnosticError, strict=True, reason="the dir lift is not built yet")
def test_the_capture_scan_agrees_with_the_jump_offer() -> None:
    """At every decision of a uniform playout: when `can_jump` holds, the
    offer is jumps only and is not empty (an empty one ends in the
    no-implicit-actions refusal); when it fails, no jump is offered. Both
    branches are reached, so neither half of the agreement is vacuous."""
    game = check_dsl(WITNESS, "mandatory-capture.cardlang")
    branches = {True: 0, False: 0}
    for seed in WITNESS_SEEDS:
        rng = random.Random(seed)
        held: list[RuntimeState] = []

        def agree(player: int, candidates: list[Any], k: int) -> list[Any]:
            capturing = held[0].get("capturing")
            kinds = {_candidate_kind(c) for c in candidates}
            if capturing:
                assert candidates and kinds == {"jump"}, (player, sorted(kinds))
            else:
                assert "jump" not in kinds, (player, candidates)
            branches[bool(capturing)] += 1
            return [rng.choice(candidates)]

        play_game(game, random.Random(seed), chooser=agree, on_first_decision=held.append)
    assert branches[True] > 0 and branches[False] > 0, branches


def test_directions_of_the_witness_board_are_the_registry_members() -> None:
    """The witness's direction source is the board entry the grid folds over."""
    game = check_dsl(board_game(), "lift.cardlang")
    assert directions_of(game)[DIRECTION_DOMAIN] == _entry().directions()
