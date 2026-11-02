"""A board verb is answered by a family that declares what it reads, and
refused, naming the family, by one that does not.

A `board:` family declares its topology as data on `BoardEntry`
(`cardlang/stdlib/boards.py`): its cells, an optional adjacency (`edges`),
the line lengths it answers, and an optional movement frame. Every board
verb reads one of them (`builtins.functions.BOARD_VERB_NEEDS`), and so does
the board direction domain `dir`, which only a frame mints. This module is
the family-by-verb grid, the entry-integrity grid over every family's built
entry, and the misuse probes:

  * GRID V -- {family: `BOARD_FAMILIES`} x {position: each board verb of
    `BOARD_ONLY_CALL_FUNCS` but `lines` at a call, `lines(k)` for a literal
    k in 1..4, and `dir` at each position that admits it -- the move
    parameter, the bare quantifier, a function parameter and an outcome
    payload}, crossed with {answered, refused naming the family}. The
    expected column is the hand table `ANSWERS`, authored from the
    family-by-verb matrix of issue #976, never read off `BOARD_VERB_NEEDS`.
    An answered cell checks and plays its probe; a refused cell is refused at
    resolve on a line naming the position and the family, and a call's
    refusal names every verb the family answers. Behind it, each refused
    (family, verb) cell, and `lines` on an entry declaring no topology, is
    called at play and meets the runtime Shadow Guard.
  * GRID E -- over every family's built entry: cells unique, nonempty and
    within the position-domain ceiling; edges joining two distinct cells,
    total over the cells; every line a straight run of declared length along
    the edges where the family declares edges; `neighbors(c)` in board cell
    order; a frame present exactly where the checked game's board mints
    `dir`. The `morris9` hand tables (thirty-two edges, the degree sequence,
    the sixteen mills written out, every point in exactly two) are its
    independent cross-checks.
  * The misuse probes -- the plausible wrong sentences around the new
    family, each refused loud; their rendered diagnostics are pinned in
    `tests/rejections/` as well.
  * The witness -- a placing-and-sliding morris skeleton whose offered
    placements and slides equal, at every decision, the sets a hand-drawn
    adjacency of the board gives.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a board verb, a literal `lines(k)` and the direction domain `dir`
            are answered on exactly the families that declare what each
            reads, and refused at resolve, naming the family, the thing it
            lacks and the verbs it answers, on every other; every built
            entry's topology is self-consistent; the mills are the straight
            runs of three along the declared adjacency.
domain:     `BOARD_FAMILIES` x the positions above x {answered, refused}
            (GRID V); the entry-integrity properties over every family's
            built entry (GRID E). Outside it, by design, each waiting on a
            witness game (issue #124): relations beyond one adjacency set,
            jump triples, track frames, double-indexed families, in-file
            boards. A family library spells no `cell` type and no `dir`, so
            of the board verbs it reaches `home`, `far_row` and `lines`, and
            `neighbors` through a `for each cell` binder; its
            reach is the `uses`-line row of `resolve._CLAUSE_GATES` that the
            game's own call reads (tests/test_library_clause_gates.py).
registry:   `cardlang.stdlib.boards.BOARD_FAMILIES`, `BoardEntry`;
            `cardlang.builtins.functions.BOARD_ONLY_CALL_FUNCS`,
            `BOARD_VERB_NEEDS`; `cardlang.builtins.signatures.CALL_SIGS`;
            `cardlang.runtime.values.COMPONENT_SETS`; the direction positions
            `resolve._minted_directions` gates.
held by:    the availability refusal is Derived and Pinned: `BOARD_VERB_NEEDS`
            is one table mapping each board verb to the `BoardEntry` field it
            reads, pinned total against `BOARD_ONLY_CALL_FUNCS`, and the
            resolve row and the runtime `_board_of` Shadow Guard both read
            it; not higher, because the Builtin namespace is a string
            registry throughout (`BUILTIN_CALL_FUNCS`, the `call` match, the
            arm-home grid of tests/test_native_dispatch_split.py) and an enum
            for the board verbs alone would give one registry two shapes.
            The edge data is a Born-Green Pin: the edges are authored with no
            source above them in the tree, so the pin is GRID E's hand table,
            and part-03's differential against the oracle's own neighbour
            table (issue #978) is its executed witness. The mills are
            Unrepresentable: `lines(3)` on `morris9` is derived from the one
            edge set and the points' file and rank, so a mill off the edges
            cannot be written. A frameless family minting no `dir` is
            Unrepresentable: `BoardEntry.frame` is optional,
            `board_domains.directions_of` reads it, and the `dir` source is
            empty without it.
does not prove:  that `neighbors` is the adjacency a player of the real game
            knows: the hand table is checked against itself and the derived
            mills, and the differential against OpenSpiel's
            `nine_mens_morris` (issue #978) carries that. Nor that an
            answered verb returns the right cells: GRID V runs each answered
            probe; the frame verbs' values are tests/test_boards_registry.py's
            and tests/test_movement_verbs.py's, and `neighbors`' are the
            hand table of tests/test_boards_registry.py and the slide witness
            here, which holds every offered slide set equal to a hand-drawn
            adjacency. The availability row for `lines`
            refuses nothing while every family declares lines; its cells are
            marked.

red under (edges): dropping `("a1", "d1")` from `boards._MORRIS9_EDGES`
reddens the degree table, the edge count and the mills table of GRID E.
red under (availability): mapping `neighbors` to `frame` in
`BOARD_VERB_NEEDS` reddens GRID V's `call neighbors` cells on both families.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.board_domains import directions_of
from cardlang.builtins.functions import BOARD_ONLY_CALL_FUNCS
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.evaluate import native_call
from cardlang.stdlib.boards import BOARD_FAMILIES, BoardEntry, board_entry
from cardlang.types import TBoolean, TCell, TCollection, TDir, TInteger, TPlayer
from tests.test_cell_queries import _board_ctx

_FILE = "availability.cardlang"

# The `board:` clause each family is checked under, spelled as a designer
# writes it.
BOARD_CLAUSES: dict[str, str] = {
    "grid": "grid(8, 8)",
    "morris9": "morris9",
}

LINE_LENGTHS: tuple[int, ...] = (1, 2, 3, 4)

DIR_POSITIONS: tuple[str, ...] = (
    "dir move parameter",
    "dir quantifier",
    "dir function parameter",
    "dir payload",
)


def _positions() -> list[str]:
    calls = [f"call {v}" for v in sorted(BOARD_ONLY_CALL_FUNCS - {"lines"})]
    return calls + [f"lines({k})" for k in LINE_LENGTHS] + list(DIR_POSITIONS)


# The expected column, authored from issue #976's family-by-verb matrix: the
# positions each family answers; every other position is refused.
ANSWERS: dict[str, frozenset[str]] = {
    "grid": frozenset(
        {
            "call far_row",
            "call has_step",
            "call home",
            "call is_diagonal",
            "call neighbor",
            "lines(1)",
            "lines(2)",
            "lines(3)",
            "lines(4)",
            *DIR_POSITIONS,
        }
    ),
    "morris9": frozenset({"call neighbors", "lines(3)"}),
}

# The board verbs each family answers, as its refusals list them.
ANSWERED_VERBS: dict[str, tuple[str, ...]] = {
    "grid": ("far_row", "has_step", "home", "is_diagonal", "lines", "neighbor"),
    "morris9": ("lines", "neighbors"),
}

FAMILIES = sorted(set(BOARD_FAMILIES) | set(ANSWERS))


def test_the_expected_column_covers_every_family() -> None:
    """The hand table names every registered family and no other, so a family
    added to the registry is a red here until its row is authored."""
    assert set(ANSWERS) == set(BOARD_FAMILIES)
    assert set(BOARD_CLAUSES) == set(BOARD_FAMILIES)
    assert set(ANSWERED_VERBS) == set(BOARD_FAMILIES)


def test_the_expected_column_covers_every_position() -> None:
    """Each family's answered set is drawn from the derived positions, and
    its answered verbs are the call positions it answers plus `lines`."""
    positions = set(_positions())
    for family, answered in ANSWERS.items():
        assert answered <= positions, sorted(answered - positions)
        calls = {p.removeprefix("call ") for p in answered if p.startswith("call ")}
        assert set(ANSWERED_VERBS[family]) == calls | {"lines"}


def test_every_board_verb_reads_one_declared_part() -> None:
    """`BOARD_VERB_NEEDS` is total over the board verbs, each mapped to a part
    a `BoardEntry` declares, and resolve holds one availability row per part
    whose members are exactly that part's verbs.

    red under: adding a board verb to `BOARD_ONLY_CALL_FUNCS` with no
    `BOARD_VERB_NEEDS` row."""
    import cardlang.resolve as resolve_module
    from cardlang.builtins.functions import BOARD_VERB_NEEDS
    from cardlang.builtins.functions import BOARD_NEEDS

    assert set(BOARD_VERB_NEEDS) == BOARD_ONLY_CALL_FUNCS
    assert set(BOARD_VERB_NEEDS.values()) <= set(BOARD_NEEDS)
    rows = [row.members for row in resolve_module._BOARD_NEED_GATES]
    assert rows == [
        frozenset(v for v, need in BOARD_VERB_NEEDS.items() if need == part) for part in BOARD_NEEDS
    ]
    assert all(row in resolve_module._CLAUSE_GATES for row in resolve_module._BOARD_NEED_GATES)


def _game(
    family: str,
    *,
    params: str = "at : cell",
    state: str = "",
    setup: str = "",
    extra: str = "",
) -> str:
    """A two-seat piece game on `family`'s board with one `pick` move and a
    `stop`; each keyword is a position a probe rewrites."""
    return (
        "game Availability {\n"
        "  players: 2\n"
        "  max_length: 30\n"
        f"  board: {BOARD_CLAUSES[family]}\n"
        "  pieces: xo_marks\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    square[cell]    : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state {\n"
        "    result[player] : Integer = 0\n"
        "    probe : Integer = 0\n"
        "    flag : Boolean = false\n"
        "    done : Boolean = false\n"
        f"{state}"
        "  }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        f"{setup}"
        "  }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [pick, stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest result\n"
        "}\n"
        f"move_type pick({params}) {{\n"
        "  when: not done\n"
        "  effect { done := true }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
        f"{extra}"
    )


_DECLS = {TCell: "c : cell", TDir: "d : dir", TPlayer: "p : Player"}
_ARGS = {TCell: "cell", TDir: "dir", TPlayer: "0"}


def _call_probe(family: str, verb: str) -> str:
    """`verb` in a function whose parameters its signature types, and a setup
    statement that calls the function over the board's cells (and directions,
    where the verb takes one), so an answered verb runs at play."""
    sig = CALL_SIGS[verb]
    decls = ", ".join(_DECLS[type(p)] for p in sig.params)
    names = ", ".join(_DECLS[type(p)].split(" : ")[0] for p in sig.params)
    call = f"probe_fn({', '.join(_ARGS[type(p)] for p in sig.params)})"
    ret = sig.ret
    if isinstance(ret, TBoolean):
        use = call
    elif isinstance(ret, TCell):
        use = f"(has_step(cell, dir, 0) and (square[{call}] is empty))"
    elif isinstance(ret, TCollection) and isinstance(ret.element, TCell):
        use = f"(cell in {call})"
    else:
        raise AssertionError(f"{verb} returns {ret}; give it a reading here")
    if any(isinstance(p, TDir) for p in sig.params) or "dir" in use:
        use = f"(any dir where {use})"
    if "cell" in use:
        count = f"number of cells where {use}"
    else:
        count = f"number of dirs where {use}"
    return _game(
        family,
        setup=f"    probe := {count}\n",
        extra=f"function probe_fn({decls}) = {verb}({names})\n",
    )


def _source(family: str, position: str) -> str:
    if position.startswith("call "):
        return _call_probe(family, position.removeprefix("call "))
    if position.startswith("lines("):
        return _game(family, setup=f"    if any line in {position} where true {{ probe := 1 }}\n")
    match position:
        case "dir move parameter":
            return _game(family, params="at : cell, along : dir")
        case "dir quantifier":
            return _game(
                family,
                setup="    flag := scan(0)\n",
                extra="function scan(p : Player) = any dir where true\n",
            )
        case "dir function parameter":
            return _game(family, extra="function f(d : dir) = true\n")
        case "dir payload":
            return _game(
                family,
                setup=(
                    "    phase d -> outcome { Won(dir) | Lost } { produce Lost }\n"
                    "    d produces:\n"
                    "      Won(x) { }\n"
                    "      Lost   { }\n"
                ),
            )
    raise AssertionError(f"no probe for position {position!r}")


def _rendered(source: str) -> str | None:
    try:
        check_dsl(source, _FILE)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None)
        return "\n".join([exc.diagnostic.format(), *(notes or [])])
    return None


def _stop(player: int, candidates: list[Any], k: int) -> list[Any]:
    return [next(c for c in candidates if c == ("stop", None))]


def _word(position: str) -> str:
    """What a refusal of `position` must name: the verb, the length it was
    asked for, or `dir`."""
    if position.startswith("call "):
        return f"`{position.removeprefix('call ')}`"
    if position.startswith("lines("):
        return f"got {position.removeprefix('lines(').removesuffix(')')}"
    return "dir"


@pytest.mark.parametrize("position", _positions())
@pytest.mark.parametrize("family", FAMILIES)
def test_a_board_position_is_answered_or_refused_naming_the_family(
    family: str, position: str
) -> None:
    source = _source(family, position)
    rendered = _rendered(source)
    if position in ANSWERS.get(family, frozenset()):
        assert rendered is None, rendered
        play_game(check_dsl(source, _FILE), random.Random(0), chooser=_stop)
        return
    assert rendered is not None, f"`board: {BOARD_CLAUSES[family]}` accepted {position}"
    hits = [
        line
        for line in rendered.splitlines()
        if _word(position) in line and family in line
    ]
    assert hits, rendered
    if position.startswith("call "):
        assert any(all(f"`{v}`" in line for v in ANSWERED_VERBS[family]) for line in hits), hits


# --- the runtime Shadow Guard behind the availability refusal ------------------

# A board entry declaring no topology at all: no edges, no line lengths, no
# frame. No family builds one; it is the board on which `lines` is refused.
_BARE = BoardEntry(family="bare", args=(), cells=("a1", "b1"))


def _shadow_cells() -> list[tuple[str, str]]:
    """Every (family, verb) the expected column refuses at a call, plus
    `lines` on the topology-free entry."""
    verbs = sorted(BOARD_ONLY_CALL_FUNCS)
    cells = [
        (family, verb)
        for family in sorted(ANSWERED_VERBS)
        for verb in verbs
        if verb not in ANSWERED_VERBS[family]
    ]
    return cells + [("bare", "lines")]


_SHADOW_ARGS = {TCell: "a1", TDir: "ahead", TPlayer: 0, TInteger: 3}


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize(("family", "verb"), _shadow_cells())
def test_a_verb_on_a_board_lacking_its_part_meets_the_runtime_shadow_guard(
    family: str, verb: str
) -> None:
    """Should a board verb reach play on a board whose family does not declare
    what it reads, the runtime refuses it in its own channel, naming the
    resolve check that should have refused it -- never a registry-bug
    `ValueError` from inside the entry.

    red under: deleting the `answers` check in `runtime/builtins._board_of`."""
    game = check_dsl(_game("grid"), _FILE)
    ctx = _board_ctx(game, {})
    ctx.rs.board = _BARE if family == "bare" else board_entry(family, _args(family))
    args = [_SHADOW_ARGS[type(p)] for p in CALL_SIGS[verb].params]
    with pytest.raises(ShadowGuardError, match="resolve._check_board_call"):
        native_call(verb, args, ctx)


# --- GRID E: the integrity of every family's built entry -----------------------


def _args(family: str) -> tuple[int, ...]:
    row = BOARD_FAMILIES[family]
    return tuple(min(max(row.lo, 3), row.hi) for _ in range(row.arity))


@pytest.mark.parametrize("family", sorted(BOARD_FAMILIES))
def test_every_entry_holds_its_topology_together(family: str) -> None:
    entry = board_entry(family, _args(family))
    cells = entry.cells
    assert cells and len(set(cells)) == len(cells) and len(cells) <= 256
    cellset = set(cells)
    if entry.edges is not None:
        for edge in entry.edges:
            assert len(edge) == 2 and edge <= cellset, sorted(edge)
        assert set().union(*entry.edges) == cellset
        for c in cells:
            nbrs = entry.neighbors(c)
            assert nbrs == tuple(x for x in cells if frozenset((c, x)) in entry.edges)
    assert entry.line_lengths, (
        f"{family} declares no line length: a lineless family is the witness the "
        "`board_lines` cells of tests/test_library_clause_gates.py wait on, so "
        "unskip them rather than give the family lines"
    )
    for k in entry.line_lengths:
        lines = entry.lines(k)
        assert lines == entry.lines(k)
        for line in lines:
            assert len(line) == k and len(set(line)) == k and set(line) <= cellset
            if entry.edges is not None:
                assert all(
                    frozenset(pair) in entry.edges for pair in zip(line, line[1:])
                ), line


@pytest.mark.parametrize("family", sorted(BOARD_FAMILIES))
def test_a_frame_stands_exactly_where_the_board_mints_directions(family: str) -> None:
    game = check_dsl(_game(family), _FILE)
    entry = board_entry(family, game.board.args if game.board is not None else ())
    assert (entry.frame is not None) == bool(directions_of(game))


# The mill board's hand tables: thirty-two edges, twelve points of degree two,
# eight of three, four of four, and the sixteen mills written out.
MORRIS9_CELLS = (
    "a1 d1 g1 b2 d2 f2 c3 d3 e3 a4 b4 c4 e4 f4 g4 c5 d5 e5 b6 d6 f6 a7 d7 g7"
).split()

MORRIS9_MILLS: set[tuple[str, ...]] = {
    ("a1", "d1", "g1"),
    ("b2", "d2", "f2"),
    ("c3", "d3", "e3"),
    ("a4", "b4", "c4"),
    ("e4", "f4", "g4"),
    ("c5", "d5", "e5"),
    ("b6", "d6", "f6"),
    ("a7", "d7", "g7"),
    ("a1", "a4", "a7"),
    ("b2", "b4", "b6"),
    ("c3", "c4", "c5"),
    ("d1", "d2", "d3"),
    ("d5", "d6", "d7"),
    ("e3", "e4", "e5"),
    ("f2", "f4", "f6"),
    ("g1", "g4", "g7"),
}


def test_morris9_cells_are_the_wmd_points_in_board_order() -> None:
    assert board_entry("morris9", ()).cells == tuple(MORRIS9_CELLS)


def test_morris9_edges_hold_the_hand_degree_table() -> None:
    entry = board_entry("morris9", ())
    assert entry.edges is not None and len(entry.edges) == 32
    degrees = [len(entry.neighbors(c)) for c in entry.cells]
    assert {d: degrees.count(d) for d in set(degrees)} == {2: 12, 3: 8, 4: 4}


def test_morris9_mills_are_the_sixteen_lines_and_each_point_is_in_two() -> None:
    entry = board_entry("morris9", ())
    assert entry.line_lengths == (3,)
    mills = entry.lines(3)
    assert set(mills) == MORRIS9_MILLS and len(mills) == 16
    assert all(sum(c in m for m in mills) == 2 for c in entry.cells)


# --- misuse probes ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        pytest.param(
            _game("morris9").replace("board: morris9", "board: morris9(3)"),
            "board family 'morris9' takes 0 argument(s), got 1",
            id="morris9 with an argument",
        ),
        pytest.param(
            _game("grid").replace("board: grid(8, 8)", "board: grid"),
            "board family 'grid' takes 2 argument(s), got 0",
            id="grid without its arguments",
        ),
        pytest.param(
            _game(
                "morris9",
                setup="    probe := number of cells where (any cell in neighbors(cell) where true)\n",
            ),
            "iterates a single line",
            id="collection quantifier over neighbors",
        ),
        pytest.param(
            _game("morris9").replace("pieces: xo_marks", "pieces: morris_men\n  cards: standard52"),
            "cards:",
            id="morris_men beside cards",
        ),
    ],
)
def test_a_plausible_wrong_sentence_is_refused(source: str, needle: str) -> None:
    rendered = _rendered(source)
    assert rendered is not None and needle in rendered, rendered


# A literal position into a board region whose argument the sentence does not
# fix: the board bounds the region by its largest count over every argument
# it admits -- every cell for `neighbors(c)` (the mill board's largest degree
# is four), every declared length for a computed `lines(k)` (on the mill
# board, the sixteen mills; on `grid(8, 8)` the lines of two, 56 across, 56
# up and 98 diagonal). (family, region expression, the first position past
# it.)
_UNFIXED_REGIONS = [
    ("morris9", "neighbors(c)", 4),
    ("morris9", "lines(k)", 16),
    ("grid", "lines(k)", 210),
]


@pytest.mark.parametrize(("family", "region", "past"), _UNFIXED_REGIONS)
def test_a_position_past_every_argument_of_a_region_is_refused(
    family: str, region: str, past: int
) -> None:
    """Position `past` is refused where it is written, and the last position
    inside is not.

    red under: `resolve._static_length` answering None for a cell-parameter
    region (the `TCell` arm)."""
    def source(position: int) -> str:
        return _game(
            family,
            extra=f"function f(c : cell, k : Integer) = {region}[{position}]\n",
        )

    rendered = _rendered(source(past))
    assert rendered is not None and f"position {past} is past the end" in rendered, rendered
    inside = _rendered(source(past - 1))
    assert inside is None or "is past the end" not in inside, inside


def test_a_declared_dir_domain_stands_beside_a_frameless_board() -> None:
    """`morris9` mints no `dir`, so a game may declare a position domain of
    that name beside it; on a framed board the same declaration collides with
    the minted domain."""
    positions = "  positions { dir : 1..3 }\n"
    morris = _game("morris9", params="at : cell, along : dir").replace(
        "  pieces:", positions + "  pieces:"
    )
    play_game(check_dsl(morris, _FILE), random.Random(0), chooser=_stop)
    grid = _game("grid").replace("  pieces:", positions + "  pieces:")
    rendered = _rendered(grid)
    assert rendered is not None and "collides with the declared" in rendered, rendered


# The mill board's adjacency, drawn by hand from the board picture: three
# concentric squares, each walked corner to midpoint to corner, and the four
# spokes joining the squares' midpoints. Never read off the registry, so the
# witness below holds `neighbors` against a second definition of the board.
def _square(files: str, ranks: str) -> list[tuple[str, str]]:
    f1, f2, f3 = files[0], files[1], files[2]
    r1, r2, r3 = ranks[0], ranks[1], ranks[2]
    ring = [f1 + r1, f2 + r1, f3 + r1, f3 + r2, f3 + r3, f2 + r3, f1 + r3, f1 + r2]
    return list(zip(ring, ring[1:] + ring[:1]))


_HAND_EDGES = (
    _square("adg", "147")
    + _square("bdf", "246")
    + _square("cde", "345")
    + [("d1", "d2"), ("d2", "d3"), ("d5", "d6"), ("d6", "d7")]
    + [("a4", "b4"), ("b4", "c4"), ("e4", "f4"), ("f4", "g4")]
)
HAND_ADJACENCY: dict[str, frozenset[str]] = {
    p: frozenset({b for a, b in _HAND_EDGES if a == p} | {a for a, b in _HAND_EDGES if b == p})
    for p in MORRIS9_CELLS
}


def test_the_hand_adjacency_is_the_board_picture() -> None:
    """The hand picture's own shape: thirty-two edges, every point joined."""
    assert len({frozenset(e) for e in _HAND_EDGES}) == 32
    assert all(HAND_ADJACENCY[p] for p in MORRIS9_CELLS)


def _member(value: Any) -> Any:
    return value[0] if isinstance(value, tuple) and len(value) == 1 else value


@pytest.mark.parametrize("seed", range(12))
def test_a_morris_game_offers_exactly_the_slides_its_adjacency_draws(seed: int) -> None:
    """The witness: a placing-and-sliding morris skeleton plays, and at every
    decision the offered placements are exactly the empty points while the
    actor holds men in reserve, and the offered slides exactly the pairs
    (f, t) with the actor's man on f, t empty and t joined to f on the hand
    picture of the board.

    red under: `runtime/builtins._neighbors` returning
    `.neighbors(cell)[:1]` -- the offered slides fall short of the hand set."""
    game = check_dsl(MORRIS_SKELETON, _FILE)
    owner: dict[str, int] = {}
    reserve = [9, 9]
    slide_decisions = [0]
    rng = random.Random(seed)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        places = {_member(c[1]) for c in candidates if c[0] == "place"}
        slides = {tuple(c[1]) for c in candidates if c[0] == "slide"}
        empty = set(MORRIS9_CELLS) - set(owner)
        if reserve[player]:
            assert places == empty, sorted(places ^ empty)
            assert not slides, sorted(slides)
        else:
            expected = {
                (f, t)
                for f, who in owner.items()
                if who == player
                for t in HAND_ADJACENCY[f]
                if t in empty
            }
            assert not places, sorted(places)
            assert slides == expected, sorted(slides ^ expected)
            slide_decisions[0] += 1
        choice = rng.choice(candidates)
        if choice[0] == "place":
            owner[_member(choice[1])] = player
            reserve[player] -= 1
        elif choice[0] == "slide":
            frm, to = choice[1]
            owner[to] = owner.pop(frm)
        return [choice]

    play_game(game, random.Random(seed), chooser=chooser)
    assert slide_decisions[0], "no slide decision was reached"


MORRIS_SKELETON = (
        "game MorrisSkeleton {\n"
        "  players: 2\n"
        "  max_length: 80\n"
        "  board: morris9\n"
        "  pieces: morris_men\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    point[cell]     : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state { result[player] : Integer = 0  moves : Integer = 0 }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is white to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        "  }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until moves >= 60 {\n"
        "      offer to t one of [place, slide, pass]\n"
        "    }\n"
        "  }\n"
        "  winner: highest result\n"
        "}\n"
        "function side_of(p : Player) = if p is 0 then white else black\n"
        "move_type place(at : cell) {\n"
        "  when: (reserve[actor] is not empty) and (point[at] is empty)\n"
        "  effect { move one piece from reserve[actor] to point[at]  moves := moves + 1 }\n"
        "}\n"
        "move_type slide(from : cell, to : cell) {\n"
        "  when: (reserve[actor] is empty) and (point[from] is not empty)\n"
        "        and (top_of(point[from]).side is side_of(actor))\n"
        "        and (point[to] is empty) and (to in neighbors(from))\n"
        "  effect { move one piece from point[from] to point[to]  moves := moves + 1 }\n"
        "}\n"
        "move_type pass {\n"
        "  when: reserve[actor] is empty\n"
        "  effect { moves := moves + 1 }\n"
        "}\n"
)
