"""The `draughts` board family, the `draughts_men` piece set and the
`is_forward` direction verb.

`draughts(width, height)` builds the board a game of the draughts family is
played on: its cells are the playable squares of a `width` by `height`
rectangle, its movement frame has four diagonal directions, two of them
backward, and each seat's home is its back three ranks. `is_forward` says
which of a frame's directions a man may take. `draughts_men` holds a side's
men and the kings they are crowned into. This module is their grid:

  * GRID G -- {family: grid, draughts} x {verb: neighbor, has_step,
    is_diagonal, is_forward, home, far_row, lines} x {seat: 0, 1, where the
    verb takes one} x {direction: the union of both families' members, where
    the verb takes one} x {size: each family's smallest admitted board,
    8x8, a non-square board, the largest}, every cell of the board inside
    each row. The expected column is `_Spec`'s independent geometry -- its
    own offsets, playable rule, home depth and forward set, never read off
    the registry -- and a direction of the other family is a registry-bug
    refusal on the entry.
  * The hand tables for `draughts(8, 8)` and `draughts(3, 7)`: cells, homes,
    king-rows and steps written out.
  * The integrity sweep over every admitted `(width, height)`.
  * The native oracle: OpenSpiel's `checkers` -- its playable squares and
    starting men against the cells and homes, its four absolute directions
    against each seat's frame, and its men's directions against
    `is_forward`.
  * `board_entry`'s refusals, the piece set's composition and axes, and the
    misuse probes.
  * The witnesses: a stepping-and-crowning skeleton over `draughts_men`
    whose offered steps equal OpenSpiel's legal moves at every node before
    the first capture, and, with one side alone on the board, equal a
    hand-computed set through crowning and a king's backward steps; and the
    crowning's movements as both seats observe them, the king named a king.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   `draughts(w, h)` builds, for every admitted size, a board whose
            cells are the squares `(h - rank + file)` odd (file 0-based),
            row-major from rank 1; whose four diagonal directions step from
            a cell onto a cell or off the board, seat 1's frame the
            180-degree rotation of seat 0's; whose homes are each seat's back
            three ranks and king-rows its far rank, every one of them the
            playable squares only; which declares no lines; and whose
            `is_forward` is true of exactly the two `ahead_*` members, while
            the grid's three members are all forward. `draughts_men` is
            twelve men and twelve kings a side, `side` and `kind` its axes.
domain:     GRID G's axes above; every `(width, height)` the family's bounds
            admit for the integrity sweep; OpenSpiel's `checkers` at the
            sizes `_ORACLE_SIZES` names, each no wider than it is tall, each
            parity of width and height among them; `board_entry`'s refusal shapes {unknown family,
            arity, each bound's low and high side}; `draughts_men` x
            {`piece.kind is king`, `piece.side is red`, `piece.kind is red`}.
            The family by every board verb and the `dir` positions is
            tests/test_board_verb_availability.py's GRID V.
registry:   the family: `cardlang.stdlib.boards.BOARD_FAMILIES["draughts"]`,
            `BoardEntry`; the verbs: `cardlang.builtins.functions.
            BOARD_VERB_NEEDS`; the piece set: `cardlang.runtime.values.
            COMPONENT_SETS`, `cardlang.stdlib.enums.deck_size`; the oracle:
            OpenSpiel's `checkers` (pyspiel; skipped without it).
            availability: tests/test_board_verb_availability.py::
            test_a_board_position_is_answered_or_refused_naming_the_family.
held by:    a frame's directions are a Born-Green Pin against `_Spec` and
            the oracle: offsets are integers no type relates to a name.
            `is_forward` is Unrepresentable as disagreeing with its offset:
            it is read off the offset's rank step, as `is_diagonal` is off
            its file step, so a direction flagged forward that steps back
            has no spelling. The playable region is one definition, the
            family builder's cell list: the frame verbs land on a cell or
            off the board, and `__post_init__` refuses a step that stays on
            the rectangle and lands off the cells. A family's arity is
            Unrepresentable as disagreeing with its bounds: the arity is the
            length of the bounds. The piece set's composition is a
            Born-Green Pin, as every set's is (tests/test_component_sets.py).
does not prove:  that a game of draughts plays the WCDF rules: the jump,
            the continuing capture, crowning that ends a move and the draw
            are a game's sentences over these verbs, and the differential
            of that game against `checkers` carries them. The witnesses
            here walk steps alone, so a line stops at its first capture.
            Nor that the family agrees with the oracle on a board wider than
            it is tall: the oracle loses a continuing jump's piece there, so
            those sizes are held by `_Spec` and the sweep alone.

red under (cells): `% 2 == 0` in place of `% 2 == 1` in the draughts
builder's playable test reddens the hand tables, GRID G's `draughts` rows,
the sweep and the oracle's squares.
red under (directions): swapping `back_left` and `back_right`'s offsets in
the draughts direction table reddens GRID G's `neighbor` rows on `back_*`,
the hand step table and the oracle's direction mapping.
red under (home depth): a draughts home depth of 2 reddens the hand homes,
the sweep's home count and the oracle's starting men.
red under (forward): reading `is_forward` off the file step (`dcol`) in
place of the rank step reddens GRID G's `is_forward` rows and the oracle's
men's directions.
red under (lines): giving the draughts builder `line_lengths=(1,)` refuses
the entry at construction (lines derive from the frame's full rectangle).
red under (verb needs): mapping `is_forward` to `edges` in
`BOARD_VERB_NEEDS` reddens tests/test_board_verb_availability.py's GRID V
`call is_forward` cells on every family.
The entry pins `__post_init__` holds for a frame of one colour -- a step
landing on a cell, a home of every cell of its back ranks, a king-row of
every cell of its rank, no lines off a partial rectangle -- are each fed the
fault they name by a focused test below, and each asserts its own refusal.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.evaluate import native_call
from cardlang.stdlib import boards
from cardlang.stdlib.boards import BOARD_FAMILIES, BoardEntry, board_entry
from tests.test_movement_verbs import _boardless_ctx

_FILE = "draughts.cardlang"

# The family's admitted arguments, authored from the board: two files admit
# no jump, and two three-rank homes need an empty rank between them.
DRAUGHTS_BOUNDS: tuple[tuple[int, int], tuple[int, int]] = ((3, 16), (7, 16))

_FILES = "abcdefghijklmnop"


@dataclass(frozen=True)
class _Spec:
    """A family's geometry, authored here and never read off the registry:
    each direction's seat-0 offset (drank, dfile), the forward members,
    whether only one colour of square is played, and the home depth."""

    offsets: dict[str, tuple[int, int]]
    forward: frozenset[str]
    dark_only: bool
    home_depth: int

    def playable(self, file: int, rank: int, height: int) -> bool:
        return not self.dark_only or (height - rank + file) % 2 == 1

    def cells(self, width: int, height: int) -> tuple[str, ...]:
        return tuple(
            f"{_FILES[f]}{r}"
            for r in range(1, height + 1)
            for f in range(width)
            if self.playable(f, r, height)
        )

    def step(self, cell: str, direction: str, seat: int, width: int, height: int) -> str | None:
        drank, dfile = self.offsets[direction]
        if seat == 1:
            drank, dfile = -drank, -dfile
        f, r = _FILES.index(cell[0]) + dfile, int(cell[1:]) + drank
        if 0 <= f < width and 1 <= r <= height and self.playable(f, r, height):
            return f"{_FILES[f]}{r}"
        return None

    def ranks(self, ranks: range, width: int, height: int) -> tuple[str, ...]:
        return tuple(
            c for c in self.cells(width, height) if int(c[1:]) in ranks
        )

    def home(self, seat: int, width: int, height: int) -> tuple[str, ...]:
        if seat == 0:
            return self.ranks(range(1, self.home_depth + 1), width, height)
        return self.ranks(range(height - self.home_depth + 1, height + 1), width, height)

    def far_row(self, seat: int, width: int, height: int) -> tuple[str, ...]:
        rank = height if seat == 0 else 1
        return self.ranks(range(rank, rank + 1), width, height)


SPECS: dict[str, _Spec] = {
    "grid": _Spec(
        offsets={"ahead": (1, 0), "ahead_left": (1, -1), "ahead_right": (1, 1)},
        forward=frozenset({"ahead", "ahead_left", "ahead_right"}),
        dark_only=False,
        home_depth=2,
    ),
    "draughts": _Spec(
        offsets={
            "ahead_left": (1, -1),
            "ahead_right": (1, 1),
            "back_left": (-1, -1),
            "back_right": (-1, 1),
        },
        forward=frozenset({"ahead_left", "ahead_right"}),
        dark_only=True,
        home_depth=3,
    ),
}

# Each family's smallest admitted board, 8x8, a non-square board, and the
# largest.
SIZES: dict[str, tuple[tuple[int, int], ...]] = {
    "grid": ((1, 1), (8, 8), (8, 3), (16, 16)),
    "draughts": ((3, 7), (8, 8), (10, 7), (16, 16)),
}

ALL_DIRECTIONS: tuple[str, ...] = tuple(
    sorted({d for spec in SPECS.values() for d in spec.offsets})
)

_SEAT_VERBS = ("neighbor", "has_step")
_DIRECTION_VERBS = ("is_diagonal", "is_forward")
_REGION_VERBS = ("home", "far_row")


def _cells() -> list[Any]:
    rows: list[Any] = []
    for family, sizes in SIZES.items():
        for width, height in sizes:
            size = f"{width}x{height}"
            for verb in _SEAT_VERBS:
                for seat in (0, 1):
                    for d in ALL_DIRECTIONS:
                        rows.append(
                            pytest.param(
                                family, verb, seat, d, width, height,
                                id=f"{family}-{size}-{verb}-p{seat}-{d}",
                            )
                        )
            for verb in _DIRECTION_VERBS:
                for d in ALL_DIRECTIONS:
                    rows.append(
                        pytest.param(
                            family, verb, None, d, width, height,
                            id=f"{family}-{size}-{verb}-{d}",
                        )
                    )
            for verb in _REGION_VERBS:
                for seat in (0, 1):
                    rows.append(
                        pytest.param(
                            family, verb, seat, None, width, height,
                            id=f"{family}-{size}-{verb}-p{seat}",
                        )
                    )
            rows.append(
                pytest.param(
                    family, "lines", None, None, width, height,
                    id=f"{family}-{size}-lines",
                )
            )
    return rows


@pytest.mark.parametrize(("family", "verb", "seat", "direction", "width", "height"), _cells())
def test_a_frame_verb_answers_the_familys_geometry(
    family: str, verb: str, seat: int | None, direction: str | None, width: int, height: int
) -> None:
    entry = board_entry(family, (width, height))
    spec = SPECS[family]
    assert entry.cells == spec.cells(width, height)
    if direction is not None and direction not in spec.offsets:
        with pytest.raises(ValueError, match="no offset for direction") as caught:
            if seat is None:
                getattr(entry, verb)(direction)
            else:
                getattr(entry, verb)(entry.cells[0], direction, seat)
        assert not isinstance(caught.value, OwnerGuardError)
        return
    match verb:
        case "neighbor" | "has_step":
            assert seat is not None and direction is not None
            for cell in entry.cells:
                expected = spec.step(cell, direction, seat, width, height)
                if verb == "neighbor":
                    assert entry.neighbor(cell, direction, seat) == expected, cell
                else:
                    assert entry.has_step(cell, direction, seat) == (expected is not None), cell
        case "is_diagonal":
            assert direction is not None
            assert entry.is_diagonal(direction) == (spec.offsets[direction][1] != 0)
        case "is_forward":
            assert direction is not None
            assert entry.is_forward(direction) == (direction in spec.forward)
        case "home":
            assert seat is not None
            assert entry.home(seat) == spec.home(seat, width, height)
        case "far_row":
            assert seat is not None
            assert entry.far_row(seat) == spec.far_row(seat, width, height)
        case "lines":
            if family == "grid":
                assert entry.line_lengths == tuple(range(1, max(width, height) + 1))
                assert entry.lines(1) == tuple((c,) for c in sorted(entry.cells))
            else:
                assert entry.line_lengths == ()
                with pytest.raises(OwnerGuardError, match=r"draughts\(\d+, \d+\) declares none"):
                    entry.lines(1)
        case _:
            raise AssertionError(f"no reading for {verb}")


# --- the hand tables -------------------------------------------------------------


DRAUGHTS_8x8_CELLS = (
    "a1 c1 e1 g1 b2 d2 f2 h2 a3 c3 e3 g3 b4 d4 f4 h4 "
    "a5 c5 e5 g5 b6 d6 f6 h6 a7 c7 e7 g7 b8 d8 f8 h8"
).split()
DRAUGHTS_3x7_CELLS = "b1 a2 c2 b3 a4 c4 b5 a6 c6 b7".split()

# (size, cell, direction, seat, the square a step lands on).
DRAUGHTS_STEPS: list[tuple[tuple[int, int], str, str, int, str | None]] = [
    ((8, 8), "a1", "ahead_left", 0, None),
    ((8, 8), "a1", "ahead_right", 0, "b2"),
    ((8, 8), "a1", "back_left", 0, None),
    ((8, 8), "a1", "back_right", 0, None),
    ((8, 8), "d4", "ahead_left", 0, "c5"),
    ((8, 8), "d4", "ahead_right", 0, "e5"),
    ((8, 8), "d4", "back_left", 0, "c3"),
    ((8, 8), "d4", "back_right", 0, "e3"),
    ((8, 8), "d4", "ahead_left", 1, "e3"),
    ((8, 8), "d4", "ahead_right", 1, "c3"),
    ((8, 8), "d4", "back_left", 1, "e5"),
    ((8, 8), "d4", "back_right", 1, "c5"),
    ((8, 8), "h8", "ahead_left", 0, None),
    ((8, 8), "h8", "back_left", 0, "g7"),
    ((8, 8), "h8", "back_right", 0, None),
    ((8, 8), "h8", "ahead_left", 1, None),
    ((8, 8), "h8", "ahead_right", 1, "g7"),
    ((8, 8), "h8", "back_left", 1, None),
    ((8, 8), "h2", "ahead_left", 0, "g3"),
    ((8, 8), "h2", "ahead_right", 0, None),
    ((8, 8), "h2", "back_left", 0, "g1"),
    ((3, 7), "b1", "ahead_left", 0, "a2"),
    ((3, 7), "b1", "ahead_right", 0, "c2"),
    ((3, 7), "b1", "back_left", 0, None),
    ((3, 7), "b1", "ahead_left", 1, None),
    ((3, 7), "b1", "back_left", 1, "c2"),
    ((3, 7), "b1", "back_right", 1, "a2"),
    ((3, 7), "b7", "ahead_left", 1, "c6"),
    ((3, 7), "b7", "ahead_right", 1, "a6"),
    ((3, 7), "a4", "ahead_left", 0, None),
    ((3, 7), "a4", "ahead_right", 0, "b5"),
    ((3, 7), "a4", "back_right", 0, "b3"),
]


def test_draughts_8x8_is_the_thirty_two_dark_squares() -> None:
    entry = board_entry("draughts", (8, 8))
    assert entry.cells == tuple(DRAUGHTS_8x8_CELLS)
    assert entry.home(0) == tuple("a1 c1 e1 g1 b2 d2 f2 h2 a3 c3 e3 g3".split())
    assert entry.home(1) == tuple("b6 d6 f6 h6 a7 c7 e7 g7 b8 d8 f8 h8".split())
    assert entry.far_row(0) == ("b8", "d8", "f8", "h8")
    assert entry.far_row(1) == ("a1", "c1", "e1", "g1")
    assert entry.directions() == ("ahead_left", "ahead_right", "back_left", "back_right")


def test_draughts_3x7_is_the_smallest_board_with_a_jump() -> None:
    entry = board_entry("draughts", (3, 7))
    assert entry.cells == tuple(DRAUGHTS_3x7_CELLS)
    assert entry.home(0) == ("b1", "a2", "c2", "b3")
    assert entry.home(1) == ("b5", "a6", "c6", "b7")
    assert entry.far_row(0) == ("b7",)
    assert entry.far_row(1) == ("b1",)


@pytest.mark.parametrize(
    ("size", "cell", "direction", "seat", "expected"),
    [pytest.param(*row, id=f"{row[0][0]}x{row[0][1]}-{row[1]}-{row[2]}-p{row[3]}")
     for row in DRAUGHTS_STEPS],
)
def test_draughts_step_table(
    size: tuple[int, int], cell: str, direction: str, seat: int, expected: str | None
) -> None:
    entry = board_entry("draughts", size)
    assert entry.neighbor(cell, direction, seat) == expected
    assert entry.has_step(cell, direction, seat) == (expected is not None)


# --- the integrity sweep ----------------------------------------------------------


def _admitted() -> list[tuple[int, int]]:
    (wlo, whi), (hlo, hhi) = DRAUGHTS_BOUNDS
    return [(w, h) for w in range(wlo, whi + 1) for h in range(hlo, hhi + 1)]


def test_the_family_admits_the_authored_bounds() -> None:
    family = BOARD_FAMILIES["draughts"]
    assert tuple((b.lo, b.hi) for b in family.bounds) == DRAUGHTS_BOUNDS
    assert tuple(b.name for b in family.bounds) == ("width", "height")


@pytest.mark.parametrize(
    ("width", "height"),
    [pytest.param(w, h, id=f"{w}x{h}") for w, h in _admitted()],
)
def test_every_admitted_board_holds_its_geometry(width: int, height: int) -> None:
    """Every admitted size builds; its cells are the playable squares; every
    direction is live for both seats; each step stays on a cell or leaves the
    board; the homes are disjoint, each the playable squares of three ranks;
    each king-row is the far rank's playable squares; the cell count is
    within the position-domain cap."""
    spec = SPECS["draughts"]
    entry = board_entry("draughts", (width, height))
    cells = set(entry.cells)
    assert entry.cells == spec.cells(width, height) and len(cells) <= 256
    for d in entry.directions():
        for seat in (0, 1):
            assert any(entry.has_step(c, d, seat) for c in entry.cells), (d, seat)
            for c in entry.cells:
                nb = entry.neighbor(c, d, seat)
                assert nb is None or nb in cells
    assert not set(entry.home(0)) & set(entry.home(1))
    for seat in (0, 1):
        assert entry.home(seat) == spec.home(seat, width, height)
        assert entry.far_row(seat) == spec.far_row(seat, width, height)
        assert set(entry.far_row(1 - seat)) <= set(entry.home(seat))


# --- the native oracle ----------------------------------------------------------

# OpenSpiel's `checkers` at each parity of width and height: (columns, rows).
# Each is no wider than it is tall: the oracle keeps a continuing jump's
# square as `row * rows + column` (checkers.cc, `multiple_jump_piece_`), so
# on a wider board it loses the jumping piece and fails its own check.
_ORACLE_SIZES: list[tuple[int, int]] = [(8, 8), (3, 7), (6, 7), (5, 8)]

# The oracle's four absolute directions (checkers.cc, `kDirRowOffsets`,
# `kDirColumnOffsets`; its row 0 is the top rank) as each seat's frame names
# them: index 0 up-left, 1 up-right, 2 down-right, 3 down-left.
ORACLE_DIRECTIONS: dict[int, tuple[str, str, str, str]] = {
    0: ("ahead_left", "ahead_right", "back_right", "back_left"),
    1: ("back_right", "back_left", "ahead_left", "ahead_right"),
}


def _oracle_square(rows: int, row: int, column: int) -> str:
    return f"{_FILES[column]}{rows - row}"


def _oracle(columns: int, rows: int) -> Any:
    pyspiel = pytest.importorskip("pyspiel")
    return pyspiel.load_game("checkers", {"rows": rows, "columns": columns})


def _decode(action: int, rows: int, columns: int) -> tuple[int, int, int, int]:
    """(row, column, direction, capture) -- `checkers.cc`'s mixed-base action
    id over (rows, columns, 4 directions, 2 move types)."""
    action, capture = divmod(action, 2)
    action, direction = divmod(action, 4)
    row, column = divmod(action, columns)
    return row, column, direction, capture


@pytest.mark.parametrize(
    ("columns", "rows"),
    [pytest.param(c, r, id=f"{c}x{r}") for c, r in _ORACLE_SIZES],
)
def test_the_cells_and_homes_are_the_oracles_squares_and_men(columns: int, rows: int) -> None:
    """The oracle's playable squares are `(row + column)` odd; its first
    player's men start on rows nearest it and its second player's on the far
    three, which are `home(0)` and `home(1)`."""
    entry = board_entry("draughts", (columns, rows))
    state = _oracle(columns, rows).new_initial_state()
    lines = str(state).splitlines()
    squares: dict[str, str] = {}
    for row in range(rows):
        board_row = lines[row][len(str(rows - row)):]
        for column in range(columns):
            squares[_oracle_square(rows, row, column)] = board_row[column]
    playable = {
        _oracle_square(rows, row, column)
        for row in range(rows)
        for column in range(columns)
        if (row + column) % 2 == 1
    }
    assert set(entry.cells) == playable
    assert {s for s, ch in squares.items() if ch == "o"} == set(entry.home(0))
    assert {s for s, ch in squares.items() if ch == "+"} == set(entry.home(1))


@pytest.mark.parametrize(
    ("columns", "rows"),
    [pytest.param(c, r, id=f"{c}x{r}") for c, r in _ORACLE_SIZES],
)
def test_each_seats_frame_names_the_oracles_directions(columns: int, rows: int) -> None:
    """Over uniform playouts of the oracle, every legal move it offers lands
    where `neighbor` -- once for a step, twice for a jump -- lands along the
    member `ORACLE_DIRECTIONS` names for the mover's seat, and a man is
    offered exactly the directions `is_forward` admits."""
    entry = board_entry("draughts", (columns, rows))
    game = _oracle(columns, rows)
    checked = 0
    for seed in range(8):
        rng = random.Random(seed)
        state = game.new_initial_state()
        while not state.is_terminal():
            seat = state.current_player()
            board = str(state).splitlines()
            for action in state.legal_actions():
                row, column, direction, capture = _decode(action, rows, columns)
                member = ORACLE_DIRECTIONS[seat][direction]
                start = _oracle_square(rows, row, column)
                land = entry.neighbor(start, member, seat)
                if capture:
                    assert land is not None
                    land = entry.neighbor(land, member, seat)
                name = state.action_to_string(seat, action)
                assert name == f"{start}{land}", (seed, name, member)
                piece = board[row][len(str(rows - row)) + column]
                if piece in "o+":
                    assert entry.is_forward(member), (seed, name, member)
                checked += 1
            state.apply_action(rng.choice(state.legal_actions()))
    assert checked


def test_a_man_moves_along_exactly_the_forward_members() -> None:
    """The oracle's men move along directions 0 and 1 for its first player
    and 2 and 3 for its second; those are each seat's `is_forward` members."""
    entry = board_entry("draughts", (8, 8))
    for seat, men in ((0, (0, 1)), (1, (2, 3))):
        assert [entry.is_forward(ORACLE_DIRECTIONS[seat][i]) for i in range(4)] == [
            i in men for i in range(4)
        ]


# --- the entry pins, each fed the fault it names ---------------------------------


def _home_two_ranks(self: BoardEntry, player: int) -> tuple[str, ...]:
    height = self.args[1]
    rows = range(2) if player == 0 else range(height - 2, height)
    return tuple(c for c in self.cells if int(c[1:]) - 1 in rows)


def _far_row_short(self: BoardEntry, player: int) -> tuple[str, ...]:
    rank = self.args[1] if player == 0 else 1
    return tuple(c for c in self.cells if int(c[1:]) == rank)[1:]


def test_a_straight_step_on_the_dark_squares_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A straight direction on a board of one colour lands on a square that
    is no cell: the entry refuses it at construction."""
    monkeypatch.setitem(boards._DRAUGHTS_DIRECTION_OFFSETS, "ahead_left", (1, 0))
    with pytest.raises(ValueError, match="land on a board cell"):
        board_entry("draughts", (8, 8))


def test_a_home_short_of_its_depth_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BoardEntry, "home", _home_two_ranks)
    with pytest.raises(ValueError, match="every cell of its 3 back ranks"):
        board_entry("draughts", (8, 8))


def test_a_king_row_short_of_its_rank_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BoardEntry, "far_row", _far_row_short)
    with pytest.raises(ValueError, match="every cell of one rank"):
        board_entry("draughts", (8, 8))


def test_lines_off_a_frame_of_one_colour_are_refused() -> None:
    """Lines are read off a frame's whole rectangle, so an entry with a
    frame its cells do not fill declares no lines."""
    entry = board_entry("draughts", (8, 8))
    with pytest.raises(ValueError, match="where the board answers lines") as caught:
        BoardEntry(
            family=entry.family,
            args=entry.args,
            cells=entry.cells,
            frame=entry.frame,
            line_lengths=(1,),
        )
    assert not isinstance(caught.value, OwnerGuardError)


# --- board_entry's refusals -----------------------------------------------------


@pytest.mark.parametrize(
    ("family", "args", "needle"),
    [
        pytest.param("checkers", (8, 8), "unknown board family 'checkers'", id="unknown"),
        pytest.param(
            "draughts", (8,), "board family 'draughts' takes 2 argument(s), got 1",
            id="one-argument",
        ),
        pytest.param(
            "draughts", (8, 8, 8), "board family 'draughts' takes 2 argument(s), got 3",
            id="three-arguments",
        ),
        pytest.param(
            "draughts", (2, 7), "board family 'draughts' takes a width in 3..16, got 2",
            id="width-2",
        ),
        pytest.param(
            "draughts", (17, 8), "board family 'draughts' takes a width in 3..16, got 17",
            id="width-17",
        ),
        pytest.param(
            "draughts", (8, 6), "board family 'draughts' takes a height in 7..16, got 6",
            id="height-6",
        ),
        pytest.param(
            "draughts", (8, 17), "board family 'draughts' takes a height in 7..16, got 17",
            id="height-17",
        ),
    ],
)
def test_board_entry_refuses_a_misused_draughts_board(
    family: str, args: tuple[int, ...], needle: str
) -> None:
    """Each refusal names the bound the arguments break, in the game
    author's channel."""
    with pytest.raises(OwnerGuardError) as caught:
        board_entry(family, args)
    assert needle in str(caught.value), caught.value


# --- the piece set and the game sentences ----------------------------------------


def _game(*, board: str = "draughts(8, 8)", when: str = "true", extra: str = "") -> str:
    """A two-seat game over `draughts_men` with one stepping move whose
    guard is `when`."""
    return (
        "game DraughtsProbe {\n"
        "  players: 2\n"
        "  max_length: 30\n"
        f"  board: {board}\n"
        "  pieces: draughts_men\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    square[cell]    : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state { result[player] : Integer = 0  done : Boolean = false }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is red to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        "  }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [go, stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest result\n"
        "}\n"
        "move_type go(from : cell, along : dir) {\n"
        f"  when: {when}\n"
        "  effect { done := true }\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
        f"{extra}"
    )


def _rendered(source: str) -> str | None:
    try:
        check_dsl(source, _FILE)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", None)
        return "\n".join([exc.diagnostic.format(), *(notes or [])])
    return None




@pytest.mark.parametrize(
    ("when", "needle"),
    [
        pytest.param(
            "(reserve[actor] is not empty) and (top_of(reserve[actor]).kind is king)",
            None, id="kind-is-king",
        ),
        pytest.param(
            "(reserve[actor] is not empty) and (top_of(reserve[actor]).side is red)",
            None, id="side-is-red",
        ),
        pytest.param(
            "(reserve[actor] is not empty) and (top_of(reserve[actor]).kind is red)",
            "comparing kind with side can never be equal",
            id="kind-is-red",
        ),
        pytest.param(
            "is_forward(along) and has_step(from, along, actor)",
            None, id="is-forward-in-a-guard",
        ),
    ],
)
def test_a_draughts_men_sentence_checks_or_is_refused(when: str, needle: str | None) -> None:
    rendered = _rendered(_game(when=when))
    if needle is None:
        assert rendered is None, rendered
    else:
        assert rendered is not None and needle in rendered, rendered


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        pytest.param(
            _game(extra="function f(p : Player) = any line in lines(3) where true\n"),
            "`lines` reads the board's lines, but `board: draughts(8, 8)` has none",
            id="lines on draughts",
        ),
        pytest.param(
            _game(board="draughts(8)"),
            "board family 'draughts' takes 2 argument(s), got 1",
            id="draughts with one argument",
        ),
        pytest.param(
            _game(board="draughts(8, 6)"),
            "board family 'draughts' takes a height in 7..16, got 6",
            id="draughts too short for two homes",
        ),
        pytest.param(
            _game(when="is_forward(along, actor)"),
            "is_forward() expects 1 argument(s), got 2",
            id="is_forward given the seat",
        ),
        pytest.param(
            _game(when="is_forward(from)"),
            "is_forward() expects Dir, got Cell",
            id="is_forward given a cell",
        ),
    ],
)
def test_a_plausible_wrong_draughts_sentence_is_refused(source: str, needle: str) -> None:
    rendered = _rendered(source)
    assert rendered is not None and needle in rendered, rendered


@pytest.mark.expects_shadow_guard
def test_is_forward_without_a_board_meets_the_runtime_shadow_guard() -> None:
    """Should `is_forward` reach play in a boardless game, the runtime refuses
    it naming the resolve check that should have, as every board verb does."""
    with pytest.raises(ShadowGuardError, match=r"declares no `board:`") as caught:
        native_call("is_forward", ["ahead_left"], _boardless_ctx())
    assert caught.value.leaked == "resolve._check_board_call"


# --- the witnesses ---------------------------------------------------------------

SKELETON = (
    "game DraughtsSkeleton {\n"
    "  players: 2\n"
    "  max_length: 400\n"
    "  board: draughts(8, 8)\n"
    "  pieces: draughts_men\n"
    "  zones {\n"
    "    box             : Deck\n"
    "    square[cell]    : Cell<cell>\n"
    "    reserve[player] : PlayerPile<player>\n"
    "    kings[player]   : PlayerPile<player>\n"
    "  }\n"
    "  state { result[player] : Integer = 0  done : Boolean = false }\n"
    "  phase setup {\n"
    "    move all pieces from box where (piece.side is red) and (piece.kind is king) to kings[0]\n"
    "    move all pieces from box where piece.side is red to reserve[0]\n"
    "    move all pieces from box where piece.kind is king to kings[1]\n"
    "    move all pieces from box to reserve[1]\n"
    "    for each cell c: if c in home(0) { move one piece from reserve[0] to square[c] }\n"
    "    for each cell c: if c in home(1) { move one piece from reserve[1] to square[c] }\n"
    "  }\n"
    "  phase play {\n"
    "    turns t from 0 over all players until done {\n"
    "      offer to t one of [step, pass, stop]\n"
    "    }\n"
    "  }\n"
    "  winner: highest result\n"
    "}\n"
    "function side_of(p : Player) = if p is 0 then red else white\n"
    "move_type step(from : cell, along : dir) {\n"
    "  when: (square[from] is not empty)\n"
    "        and (top_of(square[from]).side is side_of(actor))\n"
    "        and (is_forward(along) or (top_of(square[from]).kind is king))\n"
    "        and has_step(from, along, actor)\n"
    "        and (square[neighbor(from, along, actor)] is empty)\n"
    "  effect {\n"
    "    let dest = neighbor(from, along, actor)\n"
    "    move one piece from square[from] to square[dest]\n"
    "    if (dest in far_row(actor)) and (top_of(square[dest]).kind is man) {\n"
    "      move one piece from square[dest] to reserve[actor]\n"
    "      move one piece from kings[actor] to square[dest]\n"
    "    }\n"
    "  }\n"
    "}\n"
    "move_type pass { effect { } }\n"
    "move_type stop { effect { done := true } }\n"
)

# The oracle's draw point: it offers no move after forty plies without a
# capture (checkers.h, `kMaxMovesWithoutCapture`).
_ORACLE_QUIET_PLIES = 40


def _steps(candidates: list[Any]) -> set[tuple[str, str]]:
    return {(c[1][0], c[1][1]) for c in candidates if c[0] == "step"}


def _pick(candidates: list[Any], name: str, params: tuple[str, str] | None = None) -> list[Any]:
    return [
        next(
            c for c in candidates
            if c[0] == name and (params is None or tuple(c[1]) == params)
        )
    ]


@pytest.mark.parametrize("seed", range(12))
def test_the_skeletons_steps_are_the_oracles_moves_until_a_capture(seed: int) -> None:
    """At every decision before the oracle offers a capture or reaches its
    draw point, the steps the skeleton offers are, by their squares, exactly
    the oracle's legal moves, for both seats."""
    pyspiel = pytest.importorskip("pyspiel")
    spec = SPECS["draughts"]
    native = pyspiel.load_game("checkers").new_initial_state()
    rng = random.Random(seed)
    compared = [0, 0]

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        legal = native.legal_actions() if not native.is_terminal() else []
        plies = sum(compared)
        if (
            not legal
            or plies >= _ORACLE_QUIET_PLIES
            or any(_decode(a, 8, 8)[3] for a in legal)
        ):
            return _pick(candidates, "stop")
        assert native.current_player() == player
        moves = {native.action_to_string(player, a): a for a in legal}
        offered = {
            f"{frm}{spec.step(frm, along, player, 8, 8)}": (frm, along)
            for frm, along in _steps(candidates)
        }
        assert set(offered) == set(moves), (seed, plies, sorted(set(offered) ^ set(moves)))
        compared[player] += 1
        name = rng.choice(sorted(moves))
        native.apply_action(moves[name])
        return _pick(candidates, "step", offered[name])

    play_game(check_dsl(SKELETON, _FILE), random.Random(seed), chooser=chooser)
    assert compared[0] and compared[1], compared


@pytest.mark.parametrize("seed", range(6))
def test_one_side_alone_steps_crowns_and_steps_back(seed: int) -> None:
    """With only seat 0's men on the board, the steps offered are exactly
    those a hand-tracked board gives: a man along the two forward
    diagonals, a king along all four, onto an empty square; a man reaching
    the far rank is a king from the next move on."""
    spec = SPECS["draughts"]
    source = SKELETON.replace(
        "    for each cell c: if c in home(1) { move one piece from reserve[1] to square[c] }\n", ""
    )
    pieces = {c: "man" for c in spec.home(0, 8, 8)}
    rng = random.Random(seed)
    seen = {"crowned": 0, "back": 0, "moves": 0}

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        if seen["moves"] >= 150:
            return _pick(candidates, "stop")
        if player == 1:
            assert not _steps(candidates)
            return _pick(candidates, "pass")
        expected = set()
        for frm, kind in pieces.items():
            for d in spec.offsets:
                land = spec.step(frm, d, 0, 8, 8)
                if (d in spec.forward or kind == "king") and land is not None and land not in pieces:
                    expected.add((frm, d))
        offered = _steps(candidates)
        assert offered == expected, (seed, sorted(offered ^ expected))
        if not offered:
            return _pick(candidates, "stop")
        frm, along = rng.choice(sorted(offered))
        to = spec.step(frm, along, 0, 8, 8)
        assert to is not None
        kind = pieces.pop(frm)
        if kind == "man" and int(to[1:]) == 8:
            kind = "king"
            seen["crowned"] += 1
        if along not in spec.forward:
            seen["back"] += 1
        pieces[to] = kind
        seen["moves"] += 1
        return _pick(candidates, "step", (frm, along))

    play_game(check_dsl(source, _FILE), random.Random(seed), chooser=chooser)
    assert seen["crowned"] and seen["back"], seen


def test_both_seats_see_the_king_a_crowning_places(tmp_path: Any) -> None:
    """A man stepping onto the king-row, taken off and replaced by a king
    from the supply, is three public movements every seat observes, and the
    piece each names says man or king: a king is told from a man in what a
    seat knows.

    red under: `Card.__str__` (cardlang/runtime/values.py) rendering a
    `king` as a `man` -- the supply's piece then reads as a man to both
    seats."""
    from cardlang.openspiel.replay import DecisionNode, load, run

    path = tmp_path / "solo.cardlang"
    path.write_text(
        SKELETON.replace(
            "    for each cell c: if c in home(1) { move one piece from reserve[1] to square[c] }\n",
            "",
        )
    )
    _, space = load(str(path))
    history: list[int] = []
    for frm in ("a3", "b4", "c5", "d6", "e7"):
        for wanted in (("step", (frm, "ahead_right")), "pass"):
            node = run(str(path), 0, tuple(history))
            assert isinstance(node, DecisionNode)
            history.append(next(a for a in node.legal if space.decode(a) == wanted))
    node = run(str(path), 0, tuple(history))
    assert isinstance(node, DecisionNode)
    crowning = [
        ("move", "square[e7]", ("man:red",), "square[f8]", ("man:red",)),
        ("move", "square[f8]", ("man:red",), "reserve[0]", ("man:red",)),
        ("move", "kings[0]", ("king:red",), "square[f8]", ("king:red",)),
    ]
    for seat in (0, 1):
        log = node.obs_logs[seat]
        at = log.index(crowning[0])
        assert log[at : at + 3] == crowning, log[at : at + 3]
        steps = [e for e in log[:at] if e[0] == "move" and e[1].startswith("square[")]
        assert steps and all(e[2] == ("man:red",) for e in steps), steps
