"""BOARDS registry: board families as closed static data, in the DECKS style
(cardlang/runtime/values.py). A game selects a board by family name and
integer arguments (docs/design-notes/board-topology.md S2.1); this module
turns that selection into a BoardEntry -- cells and their lines -- never by
hand-enumerating cells per game. Only the grid family is registered at rung
1; relations, regions, frames, and jump triples are later rungs' additions
(issue #124), not fields of BoardEntry today.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

_FILES = "abcdefghijklmnop"  # grid's declared arg ceiling is 16

# The seat-relative forward directions a grid mints, in fixed order (decisions.md
# "Boards and cells", rung-2 movement). One member per forward direction a piece
# may step. `directions()` returns these NAMES; the offsets/diagonal flag below
# carry the geometry behind them. Kept as an independently-authored tuple (not
# derived from _GRID_DIRECTION_OFFSETS) so the integrity pin that the two agree
# is a real cross-check, not a tautology.
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
    span = max(width, height)
    if not (1 <= k <= span):
        raise ValueError(f"lines(k) requires k in 1..{span} for grid({width}, {height}), got {k}")
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


@dataclass(frozen=True)
class BoardEntry:
    """One instantiated board: closed static data, integrity-pinned from
    birth (docs/decisions.md, "Closed-domain completeness")."""

    family: str
    args: tuple[int, ...]
    cells: tuple[str, ...]

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
        if self.family == "grid":
            self._check_movement_integrity()

    def lines(self, k: int) -> tuple[tuple[str, ...], ...]:
        if self.family == "grid":
            width, height = self.args
            return _grid_lines(width, height, k)
        raise ValueError(
            f"unknown board family {self.family!r} (registry only mints: {sorted(BOARD_FAMILIES)})"
        )

    def directions(self) -> tuple[str, ...]:
        """The seat-relative forward directions this board mints, in fixed
        order -- the members of the `dir` move-parameter domain (decisions.md
        "Boards and cells", rung-2 movement). The per-player offsets and the
        diagonal flag behind these names are `_offset`/`is_diagonal`."""
        if self.family == "grid":
            return _GRID_DIRECTIONS
        raise ValueError(
            f"unknown board family {self.family!r} (registry only mints: {sorted(BOARD_FAMILIES)})"
        )

    def is_diagonal(self, direction: str) -> bool:
        """True iff a step along `direction` changes file (dcol != 0) -- the
        capturing directions, matching the oracle's straight-never-captures
        rule. Player-independent: the 180-degree flip preserves |dcol|."""
        self._grid_args()
        return self._base_offset(direction)[1] != 0

    def neighbor(self, cell: str, direction: str, player: int) -> str | None:
        """The cell one step along `direction` in `player`'s frame, or None off
        the board's edge -- the registry-internal PARTIAL lookup (a later task's
        stdlib verb wraps it total-with-backstop; a guard's `has_step` gates
        it). Generated from cell coords + the actor-resolved offset, never a
        literal per-cell table."""
        width, height = self._grid_args()
        col, row = self._require_cell(cell, width, height)
        drow, dcol = self._offset(direction, player)
        nc, nr = col + dcol, row + drow
        if 0 <= nc < width and 0 <= nr < height:
            return _cell_name(nc, nr)
        return None

    def has_step(self, cell: str, direction: str, player: int) -> bool:
        """Whether the step along `direction` stays on the board -- the guard
        predicate that gates the total stdlib `neighbor`. Delegates to
        `neighbor`, so the two agree by construction."""
        return self.neighbor(cell, direction, player) is not None

    def home(self, player: int) -> tuple[str, ...]:
        """The player's back two ranks -- breakthrough's 16-piece setup region.
        Player 0 advances toward higher ranks, so its back is the low ranks;
        player 1's is the high ranks (the mirror). Generated from the grid,
        clamped on boards too short for two ranks."""
        width, height = self._grid_args()
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
        width, height = self._grid_args()
        self._require_player(player)
        r = height - 1 if player == 0 else 0
        return tuple(_cell_name(c, r) for c in range(width))

    def _grid_args(self) -> tuple[int, int]:
        if self.family != "grid":
            raise ValueError(
                f"unknown board family {self.family!r} (registry only mints: {sorted(BOARD_FAMILIES)})"
            )
        width, height = self.args
        return width, height

    @staticmethod
    def _base_offset(direction: str) -> tuple[int, int]:
        offset = _GRID_DIRECTION_OFFSETS.get(direction)
        if offset is None:
            raise ValueError(
                f"BoardEntry has no offset for direction {direction!r} "
                f"(registry bug: not one of {sorted(_GRID_DIRECTION_OFFSETS)})"
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

    def _check_movement_integrity(self) -> None:
        """Registry-bug refusal for the grid family's directions, frames, and
        regions -- the runtime half of the closed-domain pins (the static half
        is tests/test_boards_registry.py). Universal pins hold for every grid;
        the adequacy pins (no dead direction, home disjoint, home size) hold
        only where the board is a real face-off -- width >= 2 and height >= 4,
        the conjunction of the per-pin thresholds (disjoint needs height >= 4,
        |home| == 2*width needs height >= 2, a live diagonal needs width >= 2).
        Degenerate grids like tic-tac-toe's 3x3 skip them: their homes
        legitimately overlap, which is not a registry bug."""
        width, height = self.args
        dirs = self.directions()

        if set(_GRID_DIRECTION_OFFSETS) != set(dirs):
            raise ValueError(
                "BoardEntry direction offsets must cover exactly directions() "
                f"(registry bug: {sorted(_GRID_DIRECTION_OFFSETS)} vs {sorted(dirs)})"
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
    return BoardEntry(family="grid", args=args, cells=cells)


@dataclass(frozen=True)
class BoardFamily:
    """One BOARD_FAMILIES row: declared argument arity and per-argument
    bounds, plus the builder that turns validated args into a BoardEntry."""

    arity: int
    lo: int
    hi: int
    build: Callable[[tuple[int, ...]], BoardEntry]


BOARD_FAMILIES: dict[str, BoardFamily] = {
    "grid": BoardFamily(arity=2, lo=1, hi=16, build=_grid),
}


def board_entry(family: str, args: tuple[int, ...]) -> BoardEntry:
    """Instantiate a board by family name and arguments. Raises ValueError
    naming the violated bound on any misuse; resolve turns these into
    diagnostics at the `board:` clause."""
    declared = BOARD_FAMILIES.get(family)
    if declared is None:
        raise ValueError(
            f"unknown board family {family!r} (registered families: {sorted(BOARD_FAMILIES)})"
        )
    if len(args) != declared.arity:
        raise ValueError(
            f"board family {family!r} takes {declared.arity} argument(s), got {len(args)}"
        )
    for value in args:
        if not (declared.lo <= value <= declared.hi):
            raise ValueError(
                f"board family {family!r} arguments must be in "
                f"{declared.lo}..{declared.hi}, got {value}"
            )
    return declared.build(args)
