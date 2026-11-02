"""`connected(from, to, via)`: whether two cell sets join through a third along
the board's declared adjacency.

`connected(from : Collection<Cell>, to : Collection<Cell>, via :
Collection<Cell>) : Boolean` is true exactly when some cell of `from` reaches
some cell of `to` along the board's declared adjacency with every cell on the
path, both ends included, in `via` (decisions.md "Boards and cells"). It is a
Builtin that owns its loop: a breadth-first search expanding each cell at most
once, seeded in `from`'s order, neighbours taken in the board's cell order.

The grid, axis by axis, each read from where the language defines it:

  * GRID T -- argument position {from, to, via} x argument type x board. The
    type axis is `cardlang.types.Type`'s closed union, each member given the
    witnesses a board game writes for it (`WITNESSES`), or the reason no
    expression yields it (`UNWRITABLE`); `Collection` is split by element and
    facet. The board axis is `BOARD_FAMILIES` plus a boardless game with an
    integer Position Domain named `cell`. A witness is crossed with every board it is
    written on. The expected column: a boardless game is refused naming
    `board:`; a family in `ANSWERS` (authored by hand: the families
    declaring an adjacency) admits the cell collections and refuses every
    other type in the signature checker's words; every other family is
    refused naming its missing adjacency. An admitted cell also plays.
  * GRID H -- the host: the call at every expression host of the direction
    lift's grid (`tests/test_direction_lift.py::HOSTS`) on `hex_rhombus(3)`,
    landing in the host's AST field and playing; a state default refuses it,
    as it refuses every call.
  * The misuse probes -- the plausible wrong sentences, each refused loud.
  * The oracles -- an exhaustive differential against a union-find written
    here from its own six offsets, over every assignment of {empty, black,
    white} to the cells of `hex_rhombus(n)`, n in 1..3, for both seats; the
    hex theorem over every full two-colouring of the same boards; the
    expansion bound on `hex_rhombus(11)`; the expansion order.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   `connected` checks in every expression host with three cell
            collections on a family declaring an adjacency and answers
            exactly the union-find's reachability there; an argument typed
            as anything but a cell collection, an optional one or the
            Permissive Top is refused at check, a family declaring no
            adjacency is refused at resolve naming it, and a boardless game
            is refused naming `board:`; at play, a none argument or a none
            member is refused, and so is a value typed as the Permissive
            Top that is not a collection of the board's cells.
domain:     {from, to, via} x {each witness of `WITNESSES`} x {each board it
            is written on: `BOARD_FAMILIES`, boardless} (GRID T); {host:
            tests/test_direction_lift.py::HOSTS} on `hex_rhombus(3)` (GRID
            H); the misuse probes; the oracles over `hex_rhombus(n)`, n in
            1..3, every cell assignment, and `hex_rhombus(11)`. A `Line` and
            a `Collection<Line>` are written on the families declaring lines,
            a `dir` on the family minting directions, a cell-typed witness on
            a board; a boardless game writes the board-free witnesses.
registry:   types: cardlang/types.py::Type; boards:
            cardlang/stdlib/boards.py::BOARD_FAMILIES; hosts:
            tests/test_direction_lift.py::HOSTS; the verb's registry
            memberships: tests/test_piece_content_guards.py,
            tests/test_hidden_reads.py::test_the_builtin_zone_read_partition_is_total,
            tests/test_native_dispatch_split.py,
            tests/test_trick_order.py::test_row_callable_partition_is_total,
            tests/test_board_verb_availability.py.
held by:    an argument typed as neither a cell collection nor the
            Permissive Top is Unrepresentable past the type layer: `CALL_SIGS`
            types each slot `Collection<Cell>` and the signature checker
            refuses any other before a run. The Permissive Top passes it by
            design: an `if` with no join (issue #116) and a chip stack
            (issue #655) reach the verb, and a chip stack in an effect checks
            clean. The family refusal is
            Derived and Pinned: `BOARD_VERB_NEEDS` maps `connected` to
            `edges`, read by resolve's need row and the runtime `_board_of`
            (tests/test_board_verb_availability.py); not higher, because the
            family is the designer's string until resolve. A none argument or
            member is refused at play by `reads.coerce_args`, the none class's
            Owner Guard (tests/test_native_call_boundary.py), GRID T's
            optional rows its witnesses here. The refusal at play of a value
            that is not the board's cells stands in, in `BoardEntry.connected`,
            for the type layer's missing Owner Guard (issue #116), GRID T's
            Permissive Top rows its witnesses. Agreement
            with the union-find, the hex theorem, the expansion bound and the
            expansion order are Born-Green Pins, each red under the mutation
            named below; not higher, because a differential against a second
            implementation is evidence by execution, and no type states
            termination or an order.
does not prove:  that the adjacency is the real game's: the union-find reads
            this module's six offsets, and the Hex differential against
            OpenSpiel's own flood fill (issue #973) carries that.

red under (adjacency): `(1, 1)` in place of `(1, -1)` in
`boards._HEX_FORWARD_OFFSETS` reddens the union-find differential on n = 2
and n = 3. It leaves the hex theorem green, because the mirrored rhombus is a
hex board too.
red under (theorem): dropping `(1, -1)` from `boards._HEX_FORWARD_OFFSETS`
reddens the hex theorem on n = 2 and n = 3 (neither seat connected), and
adding `(1, 1)` beside it reddens them too (both seats connected); the n = 2
witness is {a1, b2 black; b1, a2 white}.
red under (bound): dropping the visited test from `BoardEntry.connected`, or
seeding the frontier with `from` as written rather than once per cell,
reddens the bound pin (the expansions pass the board's cell count).
red under (order): taking a cell's neighbours from a set in
`BoardEntry.connected` reddens the full-size order pin.
red under (axes): a member added to `Type`, or a family to `BOARD_FAMILIES`,
reddens the axis pin naming it.
red under (probes): skipping resolve's unresolved-name or unknown-function
refusal reddens the bare cell name probe or the design note's spelling probe, and
skipping its native-shadow refusal reddens the game-function probe.
red under (element guard): deleting `BoardEntry.connected`'s
`_require_cell_collection` calls reddens GRID T's Permissive Top rows.
red under (none member): deleting the none-member test from
`reads.coerce_args` reddens GRID T's `Collection<cell?>` rows.
"""

from __future__ import annotations

import itertools
import random
import typing
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.evaluate import native_call
from cardlang.stdlib.boards import BOARD_FAMILIES, BoardEntry, board_entry
from cardlang.types import TBoolean, TCell, TCollection, Type
from tests import test_direction_lift as lift
from tests.test_cell_queries import _board_ctx, board_game

_FILE = "connected.cardlang"

BOARDLESS = "boardless"

# The `board:` clause each family is checked under; the boardless game
# declares an integer Position Domain named `cell` in its place.
BOARD_CLAUSES: dict[str, str] = {
    "grid": "  board: grid(3, 3)\n",
    "morris9": "  board: morris9\n",
    "hex_rhombus": "  board: hex_rhombus(3)\n",
    BOARDLESS: "  positions { cell : 1..9 }\n",
}
BOARD_SPELLINGS: dict[str, str] = {
    "grid": "grid(3, 3)",
    "morris9": "morris9",
    "hex_rhombus": "hex_rhombus(3)",
}
BOARDS = (*sorted(BOARD_FAMILIES), BOARDLESS)

# The expected column's board half, authored by hand: the families that
# declare an adjacency, the part `connected` reads.
ANSWERS: frozenset[str] = frozenset({"hex_rhombus", "morris9"})

BOARDLESS_REFUSAL = "`connected` reads the board, but the game declares no `board:`"


def _adjacency_refusal(family: str) -> str:
    return (
        "`connected` reads the board's declared adjacency (which points it joins), "
        f"but `board: {BOARD_SPELLINGS[family]}` has none"
    )


def _type_refusal(got: str) -> str:
    return f"connected() expects Collection<Cell>, got {got}"


_ON_BOARDS = ("grid", "morris9", "hex_rhombus")
_EVERYWHERE = (*_ON_BOARDS, BOARDLESS)


@dataclass(frozen=True)
class Witness:
    """One argument a designer writes: its text on each board it is written
    on, the type the signature checker names refusing it (None where the slot
    admits it), and what the call needs around it: a binder (`wrap`), a state
    variable, a zone, `teams:`, or a function parameter (`param`, the call
    then a function body the When Clause calls with `call_with`); whether an
    admitted witness is refused at play (a pattern of the refusal); and the
    refusal at check, where an earlier
    guard than the signature checker gives it (`message`)."""

    label: str
    text: str
    boards: tuple[str, ...]
    got: str | None
    wrap: str = "{call}"
    state: str = ""
    teams: bool = False
    param: str = ""
    call_with: str = ""
    zone: str = ""
    per_board: Mapping[str, str] | None = None
    refused_at_play: str = ""
    message: str | None = None

    def on(self, board: str) -> str:
        if self.per_board is not None:
            return self.per_board[board]
        return self.text


SET_FORM = "(cells where square[cell] is empty)"

# Each member of the `Type` union, by class name -> its witnesses.
WITNESSES: dict[str, tuple[Witness, ...]] = {
    "TInteger": (Witness("Integer", "1", _EVERYWHERE, "Integer"),),
    "TBoolean": (Witness("Boolean", "true", _EVERYWHERE, "Boolean"),),
    "TString": (Witness("String", '"a1"', _EVERYWHERE, "String"),),
    "TPlayer": (Witness("Player", "actor", _EVERYWHERE, "Player"),),
    "TTeam": (Witness("Team", "team_of(actor)", _EVERYWHERE, "Team", teams=True),),
    "TCard": (Witness("Card", "top_of(reserve[actor])", _EVERYWHERE, "Card"),),
    "TCell": (Witness("Cell", "at", _ON_BOARDS, "Cell"),),
    "TDir": (Witness("dir", "dir", ("grid",), "dir", wrap="(any dir where {call})"),),
    "TLine": (
        Witness("Line", "line", ("grid", "morris9"), "Line", wrap="(any line in lines(3) where {call})"),
    ),
    "TCombination": (
        Witness(
            "Combination",
            "c",
            _EVERYWHERE,
            "Combination",
            param="c : Combination",
            message=(
                "`connected` takes a zone or collection, and a play is neither: it has no "
                "top card and no order of its own \u2014 read its cards as `cards in play`"
            ),
        ),
    ),
    "TEnum": (Witness("an enum", "x", _EVERYWHERE, "side"),),
    # An optional is admitted where its base is: a set of cells that may be
    # none checks, and a none reaching the verb is refused at play.
    "TOptional": (
        Witness("Player?", "lead", _EVERYWHERE, "Player?", state="    lead : Player? = none\n"),
        Witness("Cell?", "(if done then at else none)", _ON_BOARDS, "Cell?"),
        Witness(
            "Collection<Card>?",
            "(if done then reserve[actor] else none)",
            _EVERYWHERE,
            "Collection<Card>?",
        ),
        Witness(
            "Collection<Cell>?",
            "",
            _ON_BOARDS,
            None,
            per_board={
                "grid": "(if done then home(actor) else none)",
                "morris9": "(if done then neighbors(at) else none)",
                "hex_rhombus": "(if done then near_edge(actor) else none)",
            },
            refused_at_play="`connected` was given none where it needs",
        ),
    ),
    "TCollection": (
        Witness(
            "Collection<Cell> from a Region Verb",
            "",
            _ON_BOARDS,
            None,
            per_board={"grid": "home(actor)", "morris9": "neighbors(at)", "hex_rhombus": "near_edge(actor)"},
        ),
        Witness("Collection<Cell> from the Set Form", SET_FORM, _ON_BOARDS, None),
        Witness("Collection<Cell> as a list", "[at]", _ON_BOARDS, None),
        Witness(
            "Collection<cell?> as a list",
            "[d]",
            _ON_BOARDS,
            None,
            param="d : cell?",
            call_with="none",
            refused_at_play="`connected` was given a collection holding none",
        ),
        # A chip stack types as a collection of the Permissive Top, and a
        # When Clause's Hidden Read Owner Guard refuses it first.
        Witness(
            "a chip stack",
            "bank[actor]",
            _ON_BOARDS,
            "",
            zone="    bank[player]    : ChipStack<player>\n",
            message=(
                "move type `place`'s `when:` is decided by the acting seat, so the acting "
                "seat must be able to check it, but it reads the cards in `bank[actor]`, "
                "which the acting seat cannot see. Read the deciding seat's own cards, or "
                "have the holder announce or reveal the fact first"
            ),
        ),
        Witness("Collection<Card> as a zone", "reserve[actor]", _EVERYWHERE, "Collection<Card>"),
        Witness("Collection<Card> as a list", "[top_of(reserve[actor])]", _EVERYWHERE, "Collection<Card>"),
        Witness("Collection<Player>", "[actor]", _EVERYWHERE, "Collection<Player>"),
        Witness("Collection<Integer>", "[1]", _EVERYWHERE, "Collection<Integer>"),
        Witness(
            "Collection<Integer> keyed by Player",
            "score",
            _EVERYWHERE,
            "Collection<Integer> keyed by Player",
        ),
        Witness("Collection<Line>", "lines(3)", ("grid", "morris9"), "Collection<Line>"),
        Witness("Collection<Collection<Cell>>", "[[at]]", _ON_BOARDS, "Collection<Collection<Cell>>"),
    ),
    "TNull": (Witness("none", "none", _EVERYWHERE, "none"),),
    # The Permissive Top: an `if` whose branches have no join. The type layer
    # admits it by design; the verb refuses at play a value that is not a
    # collection of the board's cells.
    "TAny": (
        Witness(
            "the Permissive Top",
            "(if true then at else 1)",
            _ON_BOARDS,
            None,
            refused_at_play="argument is a1, which is not one",
        ),
    ),
}

# Members no expression yields, with the reason.
UNWRITABLE: dict[str, str] = {
    "TOutcome": "an outcome phase's type, read by its `produce` statements and consumers; no expression evaluates to one",
}

POSITIONS = ("from", "to", "via")



def test_the_type_axis_is_the_type_union() -> None:
    """Every member of `Type` has witnesses or a reason, and nothing else is
    named, so a member added to the union is a red here until it has one."""
    members = {cls.__name__ for cls in typing.get_args(Type)}
    assert set(WITNESSES) | set(UNWRITABLE) == members
    assert not set(WITNESSES) & set(UNWRITABLE)


def test_the_board_axis_is_the_family_registry() -> None:
    assert set(BOARD_CLAUSES) == set(BOARD_FAMILIES) | {BOARDLESS}
    assert set(BOARD_SPELLINGS) == set(BOARD_FAMILIES)
    assert ANSWERS <= set(BOARD_FAMILIES)


def _game(
    board: str,
    when: str,
    *,
    state: str = "",
    zone: str = "",
    teams: bool = False,
    extra: str = "",
) -> str:
    src = board_game(
        board=BOARD_CLAUSES[board],
        moves=(
            "move_type place(at : cell) {\n"
            f"  when: (square[at] is empty) and ({when})\n"
            "  effect { move one piece from reserve[actor] to square[at] }\n"
            "}\n"
            "move_type stop { effect { done := true } }\n"
            f"{extra}"
        ),
    )
    if state:
        src = src.replace("    done : Boolean = false\n", "    done : Boolean = false\n" + state)
    if zone:
        src = src.replace("    box             : Deck\n", "    box             : Deck\n" + zone)
    if teams:
        src = src.replace("  players: 2\n", "  players: 2\n  teams: [[0], [1]]\n")
    return src


def _call(witness: Witness, board: str, position: str) -> str:
    args = [SET_FORM] * 3
    args[POSITIONS.index(position)] = witness.on(board)
    return f"connected({', '.join(args)})"


def _source(witness: Witness, board: str, position: str) -> str:
    call = witness.wrap.format(call=_call(witness, board, position))
    if witness.param:
        return _game(
            board,
            f"probe_fn({witness.call_with})" if witness.call_with else "true",
            state=witness.state,
            zone=witness.zone,
            teams=witness.teams,
            extra=f"function probe_fn({witness.param}) = {call}\n",
        )
    return _game(board, call, state=witness.state, zone=witness.zone, teams=witness.teams)


def _rendered(source: str) -> tuple[str | None, str]:
    """The first refusal's message and every line the refusal renders, or
    (None, "") where the source checks."""
    try:
        check_dsl(source, _FILE)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None) or []
        return exc.diagnostic.message, "\n".join([exc.diagnostic.format(), *notes])
    return None, ""


def _stop(player: int, candidates: list[Any], k: int) -> list[Any]:
    return [next(c for c in candidates if c == ("stop", None))]


def _type_cells() -> list[Any]:
    cells: list[Any] = []
    for member in sorted(WITNESSES):
        for witness in WITNESSES[member]:
            for board in witness.boards:
                for position in POSITIONS:
                    cells.append(
                        pytest.param(witness, board, position, id=f"{witness.label}-{board}-{position}")
                    )
    return cells


@pytest.mark.parametrize(("witness", "board", "position"), _type_cells())
def test_an_argument_is_admitted_or_refused_in_the_right_layer(
    witness: Witness, board: str, position: str
) -> None:
    source = _source(witness, board, position)
    first, rendered = _rendered(source)
    if board == BOARDLESS:
        assert BOARDLESS_REFUSAL in rendered, rendered
        return
    if board not in ANSWERS:
        assert _adjacency_refusal(board) in rendered, rendered
        return
    if witness.message is not None:
        assert first == witness.message, rendered
        return
    if witness.got is not None:
        assert first == _type_refusal(witness.got), rendered
        return
    assert first is None, rendered
    game = check_dsl(source, _FILE)
    if witness.refused_at_play:
        with pytest.raises(OwnerGuardError, match=witness.refused_at_play):
            play_game(game, random.Random(0), chooser=_stop)
        return
    play_game(game, random.Random(0), chooser=_stop)


def test_the_type_axis_commands_both_outcomes() -> None:
    """GRID T holds admitted and refused witnesses on an answering family, so
    its equality cannot hold vacuously.

    red under: dropping the three admitted `Collection<Cell>` witnesses and
    the Permissive Top's from `WITNESSES`."""
    gots = [w.got for ws in WITNESSES.values() for w in ws if "hex_rhombus" in w.boards]
    assert any(g is None for g in gots) and any(g is not None for g in gots)


# --- GRID H: the host ---------------------------------------------------------

HEX_CALL = f"connected(near_edge(0), far_edge(0), {SET_FORM})"


def _on_hex(source: str) -> str:
    return source.replace("  board: grid(3, 3)\n", "  board: hex_rhombus(3)\n").replace(
        "pick(at : cell, along : dir)", "pick(at : cell)"
    )


def _call_hosts(node: object, host: tuple[str, str] | None = None) -> Iterator[tuple[str, str]]:
    """For every `connected` call in `node`, the (node type, field) of its
    nearest enclosing node that is not an expression."""
    if isinstance(node, (tuple, list)):
        for item in node:
            yield from _call_hosts(item, host)
        return
    if not is_dataclass(node) or isinstance(node, type):
        return
    if isinstance(node, n.Call) and node.func == "connected":
        assert host is not None
        yield host
    for f in fields(node):
        child_host = host if type(node) in lift._EXPR_TYPES else (type(node).__name__, f.name)
        yield from _call_hosts(getattr(node, f.name), child_host)


@pytest.mark.parametrize("host", sorted(lift.HOSTS))
def test_the_call_checks_and_plays_in_every_host(host: str) -> None:
    build, field = lift.HOSTS[host]
    source = _on_hex(build(HEX_CALL))
    first, rendered = _rendered(source)
    if host == "state default":
        assert first is not None and "cannot call 'connected'" in first, rendered
        return
    assert first is None, rendered
    game = check_dsl(source, _FILE)
    assert list(_call_hosts(game)) == [field]
    if host == "result clause":
        # The host's `loser:` names a seat whose result is negative, which no
        # seat's is: the selection runs the call for each seat and names none.
        with pytest.raises(OwnerGuardError, match="matched 0 players"):
            play_game(game, random.Random(0))
        return
    play_game(game, random.Random(0))


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #655: a chip stack is accepted wherever a collection is wanted",
)
def test_a_chip_stack_is_refused_in_an_effect() -> None:
    """An effect decides no seat's choice, so the Hidden Read Owner Guard
    leaves a chip stack to the type layer, which admits it as a collection of
    the Permissive Top."""
    source = _game(
        "hex_rhombus",
        "true",
        zone="    bank[player]    : ChipStack<player>\n",
    ).replace(
        "effect { move one piece",
        f"effect {{ if connected({SET_FORM}, {SET_FORM}, bank[actor]) {{ done := true }}\n    move one piece",
    )
    first, rendered = _rendered(source)
    assert first is not None, "a chip stack checked as a `connected` argument"


# --- The misuse probes ----------------------------------------------------------


@pytest.mark.parametrize(
    ("board", "when", "needle"),
    [
        pytest.param(
            "hex_rhombus",
            "connected(near_edge(actor), far_edge(actor))",
            "connected() expects 3 argument(s), got 2",
            id="arity",
        ),
        pytest.param(
            "hex_rhombus",
            f"connected(a1, c3, {SET_FORM})",
            "unresolved name 'a1'",
            id="bare-cell-names",
        ),
        pytest.param(
            "hex_rhombus",
            "connected(near_edge(actor), far_edge(actor), square[at])",
            _type_refusal("Collection<Card>"),
            id="a-zone-for-via",
        ),
        pytest.param(
            "grid",
            f"connected(lines(3), far_row(actor), {SET_FORM})",
            _adjacency_refusal("grid"),
            id="lines-on-a-grid",
        ),
        pytest.param(
            "hex_rhombus",
            f"connected(near_edge(actor), far_edge(actor), {SET_FORM}, 6)",
            "connected() expects 3 argument(s), got 4",
            id="a-connectivity-argument",
        ),
        pytest.param(
            "hex_rhombus",
            f"reachable(near_edge(actor), far_edge(actor), {SET_FORM})",
            "call to unknown function 'reachable'",
            id="the-design-notes-name",
        ),
    ],
)
def test_a_misuse_is_refused(board: str, when: str, needle: str) -> None:
    first, rendered = _rendered(_game(board, when))
    assert first is not None, when
    assert needle in rendered, rendered


def test_a_game_function_named_connected_is_refused() -> None:
    source = _game(
        "hex_rhombus",
        "connected(actor)",
        extra="function connected(p : Player) = true\n",
    )
    first, _ = _rendered(source)
    assert first is not None and first.startswith(
        "function 'connected' shadows the native function of the same name"
    ), first


# --- The oracles ----------------------------------------------------------------

_SIDES = ("empty", "black", "white")

# OpenSpiel's `hex` neighbours (hex.cc), as (drow, dcol).
_UF_OFFSETS: tuple[tuple[int, int], ...] = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, -1), (-1, 1))


def _uf_name(col: int, row: int) -> str:
    return f"{'abcdefghijklmnop'[col]}{row + 1}"


def _uf_connected(side: int, colour: Mapping[tuple[int, int], str], seat: int) -> bool:
    """Whether `seat`'s stones join its two borders on the side-by-side
    rhombus: seat 0 rank 1 to the last rank, seat 1 file `a` to the last file,
    by a union-find over its stones."""
    parent: dict[tuple[int, int], tuple[int, int]] = {}

    def find(x: tuple[int, int]) -> tuple[int, int]:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    mine = [rc for rc, s in colour.items() if s == ("black" if seat == 0 else "white")]
    for rc in mine:
        parent[rc] = rc
    for (r, c) in mine:
        for dr, dc in _UF_OFFSETS:
            other = (r + dr, c + dc)
            if other in parent:
                parent[find((r, c))] = find(other)
    near = {find(rc) for rc in mine if (rc[0] if seat == 0 else rc[1]) == 0}
    far = {find(rc) for rc in mine if (rc[0] if seat == 0 else rc[1]) == side - 1}
    return bool(near & far)


def _verb(entry: BoardEntry) -> Callable[[int, tuple[str, ...]], bool]:
    """The verb as the runtime calls it, through the native-call boundary,
    for `seat`'s borders and a `via`."""
    game = check_dsl(_game("hex_rhombus", "true").replace("hex_rhombus(3)", entry.spelling), _FILE)
    ctx = _board_ctx(game, {})
    borders = {p: (entry.near_edge(p), entry.far_edge(p)) for p in (0, 1)}

    def answer(seat: int, via: tuple[str, ...]) -> bool:
        near, far = borders[seat]
        return bool(native_call("connected", [near, far, via], ctx))

    return answer


@pytest.mark.parametrize("side", [1, 2, 3])
def test_the_verb_agrees_with_a_union_find_on_every_position(side: int) -> None:
    entry = board_entry("hex_rhombus", (side,))
    verb = _verb(entry)
    coords = [(r, c) for r in range(side) for c in range(side)]
    for sides in itertools.product(_SIDES, repeat=len(coords)):
        colour = dict(zip(coords, sides))
        for seat, stone in ((0, "black"), (1, "white")):
            via = tuple(_uf_name(c, r) for (r, c), s in colour.items() if s == stone)
            assert verb(seat, via) == _uf_connected(side, colour, seat), (colour, seat)


@pytest.mark.parametrize("side", [1, 2, 3])
def test_exactly_one_seat_joins_its_borders_on_a_full_board(side: int) -> None:
    """The hex theorem: on a full board exactly one seat is connected."""
    entry = board_entry("hex_rhombus", (side,))
    verb = _verb(entry)
    for blacks in itertools.product((True, False), repeat=len(entry.cells)):
        black = tuple(c for c, b in zip(entry.cells, blacks) if b)
        white = tuple(c for c, b in zip(entry.cells, blacks) if not b)
        assert verb(0, black) != verb(1, white), (black, white)


def test_each_cell_is_expanded_at_most_once() -> None:
    entry = board_entry("hex_rhombus", (11,))
    expanded: list[str] = []

    def visit(cell: str) -> None:
        expanded.append(cell)
        if len(expanded) > len(entry.cells):
            raise AssertionError(f"expanded {len(expanded)} cells on a board of {len(entry.cells)}")

    assert not entry.connected(entry.near_edge(0), (), entry.cells, visit=visit)
    assert sorted(expanded) == sorted(entry.cells)
    expanded.clear()
    assert not entry.connected(entry.near_edge(0) * 2, (), entry.cells, visit=visit)
    assert sorted(expanded) == sorted(entry.cells)


def test_the_expansion_order_is_the_seeds_then_board_order() -> None:
    """From `c3` across a full `hex_rhombus(3)`: breadth first, each cell's
    neighbours taken in the board's cell order."""
    entry = board_entry("hex_rhombus", (3,))
    traces: list[list[str]] = []
    for _ in range(2):
        trace: list[str] = []
        entry.connected(("c3",), (), entry.cells, visit=trace.append)
        traces.append(trace)
    assert traces[0] == traces[1] == ["c3", "c2", "b3", "c1", "b2", "a3", "b1", "a2", "a1"]


def _reference_order(side: int, seeds: tuple[str, ...]) -> list[str]:
    """Breadth first over the whole rhombus from `seeds`, by this module's six
    offsets, each cell's neighbours in board order (rank, then file)."""
    coords = {_uf_name(c, r): (r, c) for r in range(side) for c in range(side)}
    names = {rc: name for name, rc in coords.items()}
    seen = set(seeds)
    order: list[str] = []
    queue = list(seeds)
    while queue:
        cell = queue.pop(0)
        order.append(cell)
        r, c = coords[cell]
        joined = sorted(
            (r + dr, c + dc) for dr, dc in _UF_OFFSETS if (r + dr, c + dc) in names
        )
        for rc in joined:
            if names[rc] not in seen:
                seen.add(names[rc])
                queue.append(names[rc])
    return order


def test_the_expansion_order_on_the_full_size_board_is_the_reference_order() -> None:
    entry = board_entry("hex_rhombus", (11,))
    for seeds in (("k11",), ("f6",), entry.near_edge(1)):
        trace: list[str] = []
        entry.connected(seeds, (), entry.cells, visit=trace.append)
        assert trace == _reference_order(11, seeds), seeds


@pytest.mark.parametrize(
    ("frm", "to", "via", "expected"),
    [
        pytest.param(("a1",), ("a1",), (), False, id="empty-via"),
        pytest.param(("a1",), ("c3",), ("b2", "c3"), False, id="from-outside-via"),
        pytest.param(("b2",), ("b2",), ("b2",), True, id="one-shared-cell"),
        pytest.param(("a1",), ("c3",), ("a1", "c3"), False, id="ends-not-adjacent"),
        pytest.param(("a1",), ("c3",), ("a1", "b2", "c3"), False, id="a-diagonal-hex-does-not-join"),
        pytest.param(("a1",), ("c3",), ("a1", "a2", "b2", "b3", "c3"), True, id="a-chain"),
        pytest.param(("c1",), ("a3",), ("c1", "b2", "a3"), True, id="the-joined-diagonal"),
    ],
)
def test_the_edge_cases(frm: tuple[str, ...], to: tuple[str, ...], via: tuple[str, ...], expected: bool) -> None:
    entry = board_entry("hex_rhombus", (3,))
    assert entry.connected(frm, to, via) is expected


def test_the_signature_is_three_cell_collections_to_a_boolean() -> None:
    sig = CALL_SIGS["connected"]
    assert sig.params == (TCollection(TCell()),) * 3
    assert sig.ret == TBoolean()

