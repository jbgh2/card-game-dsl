"""BOARDS registry: board families as closed static data, in the DECKS style
(cardlang/runtime/values.py). A game selects a board by family name and
integer arguments (docs/design-notes/board-topology.md S2.1); this module
turns that selection into a BoardEntry -- the cells of the `cell`
[[position-domain]] and the topology a family declares over them -- never by
hand-enumerating cells per game.

A family's topology is data on its entry -- the declared adjacency (`edges`),
the line lengths it answers (`line_lengths`), and the movement frame
(`frame`, a grid's seat-relative forward directions and its two seats'
regions, which the `dir` domain also reads) -- and each board verb reads one
part of it, as `builtins.functions.BOARD_VERB_NEEDS` maps them. A part a
family does not declare is absent (`None`, or no line lengths), and a verb
reading it is refused at resolve naming the family. Relations beyond one
adjacency set, jump triples, track frames and in-file boards are later
rungs' additions (issue #124).

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      nothing; every entry is built here from registry data.
Establishes:  every built entry's cells are nonempty, unique and within the
              position-domain ceiling; its edges join two distinct cells of
              the board and cover every cell; it answers `lines(k)` for
              exactly its declared lengths, each line a straight run along
              its frame's geometry or its edges; a frame's directions,
              offsets and regions are self-consistent. A registry-bug
              refusal is a `ValueError`; a game author's misuse of a board
              (`board_entry`'s arguments, an undeclared `k`) is an
              `OwnerGuardError`.
Now illegal:  a frameless entry answering a frame verb or minting a
              direction; an entry answering `neighbors` without edges; a
              line that is not a straight run of its family's topology.
Held by:      the frame and the edges are Unrepresentable as absent-but-read:
              `BoardEntry.frame` and `.edges` are optional and each verb reads
              its field through `_frame` / `_edges`, which refuse a missing
              one. The mills are Unrepresentable as a second list: an edge
              family's lines are derived from its edges and the cells' file
              and rank (`_straight_runs`), so a line off the edges cannot be
              written. The edge data itself is a Born-Green Pin: authored here
              with no source above it in the tree, pinned by the hand tables
              of tests/test_board_verb_availability.py (GRID E), with the
              native-oracle differential (issue #978) as its executed witness.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cardlang.builtins.functions import BoardNeed
from cardlang.runtime.errors import OwnerGuardError

_FILES = "abcdefghijklmnop"  # grid's declared arg ceiling is 16

# The seat-relative forward directions a grid mints, in fixed order (decisions.md
# "Boards and cells", rung-2 movement). One member per forward direction a piece
# may step. The grid builder packs these NAMES and the offsets below into its
# entry's frame. Kept as an independently-authored tuple (not derived from
# _GRID_DIRECTION_OFFSETS) so the integrity pin that the two agree is a real
# cross-check, not a tautology.
_GRID_DIRECTIONS = ("ahead", "ahead_left", "ahead_right")

# Player-0 base offset (drow, dcol) for each forward direction; player 0
# advances toward higher ranks. Player 1's frame is the 180-degree rotation --
# a two-player face-off -- resolved by _player_sign (negate both components),
# not a second authored table. dcol != 0 marks a diagonal: the only directions
# that may capture, matching the oracle's rule that a straight step never
# captures (open_spiel breakthrough.cc). The seat-relative left/right choice is
# internally-consistent-but-arbitrary; a later task pins it against the oracle's
# absolute direction indices.
_GRID_DIRECTION_OFFSETS: dict[str, tuple[int, int]] = {
    "ahead": (1, 0),
    "ahead_left": (1, -1),
    "ahead_right": (1, 1),
}

# The mill board's twenty-four points in board order, row-major from a1 in the
# WMD notation: the file letter counted from the left, the rank from the
# bottom (Rosenberger, Muehle-Lehrbuch v1.9, 2.1).
_MORRIS9_CELLS: tuple[str, ...] = tuple(
    "a1 d1 g1 b2 d2 f2 c3 d3 e3 a4 b4 c4 e4 f4 g4 c5 d5 e5 b6 d6 f6 a7 d7 g7".split()
)

# The mill board's adjacency: three concentric squares, each side joined at
# its midpoint to the next square's.
_MORRIS9_EDGES: tuple[tuple[str, str], ...] = (
    # the outer square
    ("a1", "d1"), ("d1", "g1"), ("g1", "g4"), ("g4", "g7"),
    ("g7", "d7"), ("d7", "a7"), ("a7", "a4"), ("a4", "a1"),
    # the middle square
    ("b2", "d2"), ("d2", "f2"), ("f2", "f4"), ("f4", "f6"),
    ("f6", "d6"), ("d6", "b6"), ("b6", "b4"), ("b4", "b2"),
    # the inner square
    ("c3", "d3"), ("d3", "e3"), ("e3", "e4"), ("e4", "e5"),
    ("e5", "d5"), ("d5", "c5"), ("c5", "c4"), ("c4", "c3"),
    # the spokes joining the squares' midpoints
    ("d1", "d2"), ("d2", "d3"), ("g4", "f4"), ("f4", "e4"),
    ("d7", "d6"), ("d6", "d5"), ("a4", "b4"), ("b4", "c4"),
)


def board_spelling(family: str, args: tuple[int, ...]) -> str:
    """A board as a designer writes it after `board:`: `grid(8, 8)`, or a
    zero-argument family's bare name, `morris9`."""
    if not args:
        return family
    return f"{family}({', '.join(map(str, args))})"


def _cell_name(column: int, row: int) -> str:
    # column, row are 0-based. File (column) runs a..p left to right; rank
    # (row) runs 1..16 bottom to top. lines() re-derives coordinates from
    # this same pairing, so the two stay in sync by construction.
    return f"{_FILES[column]}{row + 1}"


def _cell_coords(name: str) -> tuple[int, int]:
    # Inverse of _cell_name: 'a1' -> (column 0, row 0). Both key off _FILES and
    # the 1-based rank, so they stay in sync by construction.
    return (_FILES.index(name[0]), int(name[1:]) - 1)


def _grid_lines(width: int, height: int, k: int) -> tuple[tuple[str, ...], ...]:
    found: set[tuple[str, ...]] = set()
    if width >= k:
        for row in range(height):
            for c0 in range(width - k + 1):
                found.add(tuple(_cell_name(c0 + i, row) for i in range(k)))
    if height >= k:
        for column in range(width):
            for r0 in range(height - k + 1):
                found.add(tuple(_cell_name(column, r0 + i) for i in range(k)))
    if width >= k and height >= k:
        for c0 in range(width - k + 1):
            for r0 in range(height - k + 1):
                found.add(tuple(_cell_name(c0 + i, r0 + i) for i in range(k)))
                found.add(tuple(_cell_name(c0 + i, r0 + k - 1 - i) for i in range(k)))
    return tuple(sorted(found))


def _collinear(path: list[str]) -> bool:
    # One file (the letter) or one rank (the number) throughout.
    return len({c[0] for c in path}) == 1 or len({c[1:] for c in path}) == 1


def _straight_runs(
    cells: tuple[str, ...], edges: frozenset[frozenset[str]], k: int
) -> tuple[tuple[str, ...], ...]:
    """The lines of `k` cells an edge family answers: every run of `k`
    distinct cells, each consecutive pair joined by an edge, along one file
    or one rank, written in board order."""
    order = {c: i for i, c in enumerate(cells)}
    adjacent = {c: [x for x in cells if frozenset((c, x)) in edges] for c in cells}
    found: set[tuple[str, ...]] = set()

    def extend(path: list[str]) -> None:
        if len(path) == k:
            found.add(tuple(sorted(path, key=order.__getitem__)))
            return
        for nxt in adjacent[path[-1]]:
            if nxt not in path and _collinear([*path, nxt]):
                extend([*path, nxt])

    for cell in cells:
        extend([cell])
    return tuple(sorted(found))


def _lengths_phrase(lengths: tuple[int, ...]) -> str:
    # A run from 1 is a span (`k in 1..8`, a grid's every length up to its
    # longer side); one other length is named alone (`k = 3`).
    if lengths == tuple(range(1, lengths[-1] + 1)):
        return f"k in 1..{lengths[-1]}"
    if len(lengths) == 1:
        return f"k = {lengths[0]}"
    return "k in " + ", ".join(map(str, lengths))


@dataclass(frozen=True)
class GridFrame:
    """A grid's movement frame: its width and height, the seat-relative
    forward directions in fixed order -- the members of the `dir` domain --
    and each direction's player-0 offset (drow, dcol)."""

    width: int
    height: int
    directions: tuple[str, ...]
    offsets: tuple[tuple[str, tuple[int, int]], ...]


@dataclass(frozen=True)
class BoardEntry:
    """One instantiated board: closed static data, integrity-pinned from
    birth (docs/decisions.md, "Closed-domain completeness"). `edges` is the
    declared symmetric adjacency, each edge the pair of cells it joins;
    `line_lengths` the `k` for which `lines(k)` answers; `frame` the movement
    frame. A family declares the parts it has and leaves the rest absent."""

    family: str
    args: tuple[int, ...]
    cells: tuple[str, ...]
    edges: frozenset[frozenset[str]] | None = None
    line_lengths: tuple[int, ...] = ()
    frame: GridFrame | None = None

    def __post_init__(self) -> None:
        if not self.cells:
            raise ValueError(
                "BoardEntry.cells must be nonempty (registry bug: family builder produced no cells)"
            )
        if len(set(self.cells)) != len(self.cells):
            raise ValueError(
                "BoardEntry.cells must be unique "
                "(registry bug: family builder produced a duplicate cell name)"
            )
        if len(self.cells) > 256:
            raise ValueError(
                "BoardEntry.cells must not exceed 256 (registry bug: family builder produced "
                f"{len(self.cells)})"
            )
        if self.edges is not None:
            self._check_edge_integrity(self.edges)
        if self.line_lengths:
            if list(self.line_lengths) != sorted(set(self.line_lengths)) or self.line_lengths[0] < 1:
                raise ValueError(
                    "BoardEntry.line_lengths must be distinct positive lengths in "
                    f"increasing order (registry bug: {self.line_lengths})"
                )
            if (self.frame is None) == (self.edges is None):
                raise ValueError(
                    "BoardEntry lines are derived from exactly one topology, a frame "
                    f"or edges (registry bug: board family {self.family!r})"
                )
        if self.frame is not None:
            self._check_movement_integrity()

    @property
    def spelling(self) -> str:
        return board_spelling(self.family, self.args)

    def answers(self, need: BoardNeed) -> bool:
        """Whether this board declares what a verb with `need` reads."""
        match need:
            case "lines":
                return bool(self.line_lengths)
            case "edges":
                return self.edges is not None
            case "frame":
                return self.frame is not None

    def lines(self, k: int) -> tuple[tuple[str, ...], ...]:
        """The board's lines of `k` cells. A `k` the family does not declare is
        the game author's to fix, refused naming the lengths it does."""
        if not self.line_lengths:
            raise OwnerGuardError(f"lines(k) reads lines, but {self.spelling} declares none")
        if k not in self.line_lengths:
            raise OwnerGuardError(
                f"lines(k) requires {_lengths_phrase(self.line_lengths)} for "
                f"{self.spelling}, got {k}"
            )
        if self.frame is not None:
            return _grid_lines(self.frame.width, self.frame.height, k)
        return _straight_runs(self.cells, self._edges("lines"), k)

    def neighbors(self, cell: str) -> tuple[str, ...]:
        """The cells joined to `cell` by an edge, in board order -- the
        declared adjacency `neighbors(c)` reads."""
        edges = self._edges("neighbors")
        if cell not in self.cells:
            raise ValueError(
                f"BoardEntry cell {cell!r} is not on {self.spelling} "
                "(registry bug: cell not on this board)"
            )
        return tuple(c for c in self.cells if frozenset((cell, c)) in edges)

    def directions(self) -> tuple[str, ...]:
        """The seat-relative forward directions this board's frame mints, in
        fixed order -- the members of the `dir` move-parameter domain
        (decisions.md "Boards and cells", rung-2 movement). The per-player
        offsets and the diagonal flag behind these names are
        `_offset`/`is_diagonal`."""
        return self._frame("directions").directions

    def is_diagonal(self, direction: str) -> bool:
        """True iff a step along `direction` changes file (dcol != 0) -- the
        capturing directions, matching the oracle's straight-never-captures
        rule. Player-independent: the 180-degree flip preserves |dcol|."""
        return self._base_offset(direction)[1] != 0

    def neighbor(self, cell: str, direction: str, player: int) -> str | None:
        """The cell one step along `direction` in `player`'s frame, or None off
        the board's edge -- the registry-internal PARTIAL lookup (a later task's
        stdlib verb wraps it total-with-Shadow-Guard; a guard's `has_step` gates
        it). Generated from cell coords + the actor-resolved offset, never a
        literal per-cell table."""
        frame = self._frame("neighbor")
        width, height = frame.width, frame.height
        col, row = self._require_cell(cell, width, height)
        drow, dcol = self._offset(direction, player)
        nc, nr = col + dcol, row + drow
        if 0 <= nc < width and 0 <= nr < height:
            return _cell_name(nc, nr)
        return None

    def has_step(self, cell: str, direction: str, player: int) -> bool:
        """Whether the step along `direction` stays on the board -- the guard
        predicate that gates the total Builtin `neighbor`. Delegates to
        `neighbor`, so the two agree by construction."""
        return self.neighbor(cell, direction, player) is not None

    def home(self, player: int) -> tuple[str, ...]:
        """The player's back two ranks -- breakthrough's 16-piece setup region.
        Player 0 advances toward higher ranks, so its back is the low ranks;
        player 1's is the high ranks (the mirror). Generated from the grid,
        clamped on boards too short for two ranks."""
        frame = self._frame("home")
        width, height = frame.width, frame.height
        self._require_player(player)
        if player == 0:
            rows = [r for r in (0, 1) if r < height]
        else:
            rows = [r for r in (height - 2, height - 1) if r >= 0]
        return tuple(_cell_name(c, r) for r in sorted(rows) for c in range(width))

    def far_row(self, player: int) -> tuple[str, ...]:
        """The single rank at the far edge of `player`'s frame -- the
        opponent's back row, the reach-to-win goal. Player 0's is the top rank,
        player 1's the bottom (the mirror of `home`)."""
        frame = self._frame("far_row")
        self._require_player(player)
        r = frame.height - 1 if player == 0 else 0
        return tuple(_cell_name(c, r) for c in range(frame.width))

    def _frame(self, reader: str) -> GridFrame:
        # Resolve's availability row refuses a frame verb on a frameless
        # board, and the runtime's `_board_of` stands behind it; reaching here
        # without a frame is the registry's own caller's bug.
        if self.frame is None:
            raise ValueError(
                f"BoardEntry {reader} reads a movement frame, but board family "
                f"{self.family!r} has none (registry bug: unguarded frame read)"
            )
        return self.frame

    def _edges(self, reader: str) -> frozenset[frozenset[str]]:
        # The `_frame` twin for the declared adjacency.
        if self.edges is None:
            raise ValueError(
                f"BoardEntry {reader} reads declared edges, but board family "
                f"{self.family!r} has none (registry bug: unguarded edge read)"
            )
        return self.edges

    def _base_offset(self, direction: str) -> tuple[int, int]:
        offsets = dict(self._frame("a direction's offset").offsets)
        offset = offsets.get(direction)
        if offset is None:
            raise ValueError(
                f"BoardEntry has no offset for direction {direction!r} "
                f"(registry bug: not one of {sorted(offsets)})"
            )
        return offset

    @staticmethod
    def _player_sign(player: int) -> int:
        # The 180-degree face-off: player 0 keeps the base frame, player 1
        # negates it. Defined only for the two seats a frame faces off.
        if player == 0:
            return 1
        if player == 1:
            return -1
        raise ValueError(
            f"BoardEntry frame is defined only for players 0 and 1 "
            f"(registry bug: got player {player})"
        )

    @staticmethod
    def _require_player(player: int) -> None:
        BoardEntry._player_sign(player)  # raises for anything but seat 0 or 1

    @staticmethod
    def _require_cell(cell: str, width: int, height: int) -> tuple[int, int]:
        col, row = _cell_coords(cell)
        if not (0 <= col < width and 0 <= row < height):
            raise ValueError(
                f"BoardEntry cell {cell!r} is off grid({width}, {height}) "
                f"(registry bug: cell not on this board)"
            )
        return col, row

    def _offset(self, direction: str, player: int) -> tuple[int, int]:
        drow, dcol = self._base_offset(direction)
        sign = self._player_sign(player)
        return (sign * drow, sign * dcol)

    def _check_edge_integrity(self, edges: frozenset[frozenset[str]]) -> None:
        """Registry-bug refusal for a declared adjacency: every edge joins two
        distinct cells of this board, and every cell has at least one."""
        cellset = set(self.cells)
        for edge in edges:
            if len(edge) != 2 or not edge <= cellset:
                raise ValueError(
                    "BoardEntry edges must each join two distinct cells of the board "
                    f"(registry bug: {sorted(edge)})"
                )
        joined: set[str] = set().union(*edges)
        if joined != cellset:
            raise ValueError(
                "BoardEntry edges must reach every cell "
                f"(registry bug: {sorted(cellset - joined)} unjoined)"
            )

    def _check_movement_integrity(self) -> None:
        """Registry-bug refusal for a frame's directions, seat frames, and
        regions -- the runtime half of the closed-domain pins (the static half
        is tests/test_boards_registry.py). Universal pins hold for every frame;
        the adequacy pins (no dead direction, home disjoint, home size) hold
        only where the board is a real face-off -- width >= 2 and height >= 4,
        the conjunction of the per-pin thresholds (disjoint needs height >= 4,
        |home| == 2*width needs height >= 2, a live diagonal needs width >= 2).
        Degenerate grids like tic-tac-toe's 3x3 skip them: their homes
        legitimately overlap, which is not a registry bug."""
        frame = self._frame("integrity")
        width, height = frame.width, frame.height
        dirs = self.directions()

        if set(self.cells) != {_cell_name(c, r) for r in range(height) for c in range(width)}:
            raise ValueError(
                "BoardEntry frame must cover exactly the board's cells "
                f"(registry bug: frame {width}x{height} on {len(self.cells)} cells)"
            )
        if set(dict(frame.offsets)) != set(dirs):
            raise ValueError(
                "BoardEntry direction offsets must cover exactly directions() "
                f"(registry bug: {sorted(dict(frame.offsets))} vs {sorted(dirs)})"
            )
        for d in dirs:
            o0 = self._offset(d, 0)
            if self._offset(d, 1) != (-o0[0], -o0[1]):
                raise ValueError(
                    "BoardEntry player-1 frame must be the 180-degree rotation "
                    f"of player 0 (registry bug: direction {d!r})"
                )

        cellset = set(self.cells)
        for cell in self.cells:
            for d in dirs:
                for p in (0, 1):
                    nb = self.neighbor(cell, d, p)
                    if nb is not None and nb not in cellset:
                        raise ValueError(
                            "BoardEntry neighbor must land on a board cell or None "
                            f"(registry bug: {cell!r} {d!r} p{p} -> {nb!r})"
                        )

        for p in (0, 1):
            if not set(self.home(p)) <= cellset:
                raise ValueError(f"BoardEntry home({p}) must be a subset of cells (registry bug)")
            fr = self.far_row(p)
            if not set(fr) <= cellset:
                raise ValueError(f"BoardEntry far_row({p}) must be a subset of cells (registry bug)")
            if len(fr) != width:
                raise ValueError(
                    f"BoardEntry far_row({p}) must be one full rank "
                    f"(registry bug: |far_row({p})| = {len(fr)} != width {width})"
                )
        if any(_cell_coords(c)[1] != height - 1 for c in self.far_row(0)):
            raise ValueError("BoardEntry far_row(0) must be the top rank (registry bug)")
        if any(_cell_coords(c)[1] != 0 for c in self.far_row(1)):
            raise ValueError("BoardEntry far_row(1) must be the bottom rank (registry bug)")

        if width >= 2 and height >= 4:
            for d in dirs:
                for p in (0, 1):
                    if not any(self.has_step(cell, d, p) for cell in self.cells):
                        raise ValueError(
                            f"BoardEntry direction {d!r} is dead for player {p} "
                            "(registry bug: no in-bounds step on an adequate board)"
                        )
            if set(self.home(0)) & set(self.home(1)):
                raise ValueError(
                    "BoardEntry home(0) and home(1) must be disjoint on an adequate "
                    "board (registry bug)"
                )
            for p in (0, 1):
                if len(self.home(p)) != 2 * width:
                    raise ValueError(
                        f"BoardEntry home({p}) must be two full ranks "
                        f"(registry bug: |home({p})| = {len(self.home(p))} != {2 * width})"
                    )


def _grid(args: tuple[int, ...]) -> BoardEntry:
    width, height = args
    cells = tuple(_cell_name(c, r) for r in range(height) for c in range(width))
    frame = GridFrame(
        width=width,
        height=height,
        directions=_GRID_DIRECTIONS,
        offsets=tuple(_GRID_DIRECTION_OFFSETS.items()),
    )
    return BoardEntry(
        family="grid",
        args=args,
        cells=cells,
        line_lengths=tuple(range(1, max(width, height) + 1)),
        frame=frame,
    )


def _morris9(args: tuple[int, ...]) -> BoardEntry:
    return BoardEntry(
        family="morris9",
        args=args,
        cells=_MORRIS9_CELLS,
        edges=frozenset(frozenset(edge) for edge in _MORRIS9_EDGES),
        line_lengths=(3,),
    )


@dataclass(frozen=True)
class BoardFamily:
    """One BOARD_FAMILIES row: declared argument arity and per-argument
    bounds, plus the builder that turns validated args into a BoardEntry. A
    zero-arity family's bounds bound nothing."""

    arity: int
    lo: int
    hi: int
    build: Callable[[tuple[int, ...]], BoardEntry]


BOARD_FAMILIES: dict[str, BoardFamily] = {
    "grid": BoardFamily(arity=2, lo=1, hi=16, build=_grid),
    "morris9": BoardFamily(arity=0, lo=0, hi=0, build=_morris9),
}


def board_entry(family: str, args: tuple[int, ...]) -> BoardEntry:
    """Instantiate a board by family name and arguments. Refuses any misuse
    — an unknown family, a wrong arity, an out-of-bounds argument — with an
    `OwnerGuardError` naming the violated bound: the `board:` arguments are
    the game author's to fix, and resolve converts exactly that type into a
    diagnostic at the clause. `BoardEntry.__post_init__`'s registry
    invariants stay outside it, addressed to the registry's maintainer."""
    declared = BOARD_FAMILIES.get(family)
    if declared is None:
        raise OwnerGuardError(
            f"unknown board family {family!r} (registered families: {sorted(BOARD_FAMILIES)})"
        )
    if len(args) != declared.arity:
        raise OwnerGuardError(
            f"board family {family!r} takes {declared.arity} argument(s), got {len(args)}"
        )
    for value in args:
        if not (declared.lo <= value <= declared.hi):
            raise OwnerGuardError(
                f"board family {family!r} arguments must be in "
                f"{declared.lo}..{declared.hi}, got {value}"
            )
    return declared.build(args)
