"""BOARDS registry: board families as closed static data, in the DECKS style
(cardlang/runtime/values.py). A game selects a board by family name and
integer arguments (docs/design-notes/board-topology.md S2.1); this module
turns that selection into a BoardEntry -- cells and their lines -- never by
hand-enumerating cells per game. Only the grid family is registered at rung
1; relations, regions, frames, and jump triples are later rungs' additions
(docs/roadmap.md), not fields of BoardEntry today.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

_FILES = "abcdefghijklmnop"  # grid's declared arg ceiling is 16


def _cell_name(column: int, row: int) -> str:
    # column, row are 0-based. File (column) runs a..p left to right; rank
    # (row) runs 1..16 bottom to top. lines() re-derives coordinates from
    # this same pairing, so the two stay in sync by construction.
    return f"{_FILES[column]}{row + 1}"


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

    def lines(self, k: int) -> tuple[tuple[str, ...], ...]:
        if self.family == "grid":
            width, height = self.args
            return _grid_lines(width, height, k)
        raise ValueError(
            f"unknown board family {self.family!r} (registry only mints: {sorted(BOARD_FAMILIES)})"
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
