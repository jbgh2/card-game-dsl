"""BOARDS registry: the grid family's cells and lines, integrity-pinned.

property:   every BOARD_FAMILIES row builds a BoardEntry whose cells are
            unique, nonempty, and within the 256-member position-domain cap;
            board_entry() raises ValueError naming the violated bound for
            every unknown-family, wrong-arity, or out-of-bounds misuse;
            lines(k) returns exactly the k-in-a-row alignments (rows,
            columns, both diagonal directions), deduplicated, for every k in
            1..max(width, height), and raises ValueError outside that range.
domain:     BOARD_FAMILIES rows (currently: grid) x argument space (arity,
            per-argument bounds, and the misuse shapes: unknown family,
            wrong arity, out-of-bounds argument) x entry-integrity
            properties (cell uniqueness, cell count, and, per k in
            1..max(width, height), line length/distinctness/subset-of-cells
            and the line count).
registry:   cardlang.stdlib.boards.BOARD_FAMILIES, .board_entry, .BoardEntry
covered:    the bad-args rejection grid (unknown family, arity 1, arity 3,
            arg 0, arg 17, negative arg), each pinned to a ValueError naming
            the violated bound; grid(3,3)'s exact 9-cell name order; lines(3)
            on grid(3,3) against the 8 known tic-tac-toe lines (set
            equality) plus a determinism check (repeat calls, and separate
            instances, agree); an integrity sweep over five grids (1x1,
            2x5, 5x2, 16x16, 3x3) crossed with every k in
            1..max(width, height): cell uniqueness, cell count ==
            width*height, every line k-long with distinct in-bounds cells,
            and the line count against an independently-derived closed-form
            formula; a full brute-force reconstruction (colinearity over
            every k-combination of cells, not a sliding window)
            cross-checked against lines(k) for the four small grids (1x1,
            2x5, 5x2, 3x3); the k-boundary cases (k=0 and k=17 on grid(3,3)
            raise; k=1 on grid(1,1) returns the single cell; k=5 on
            grid(2,5) returns the 2 vertical-only lines); and `lines()` is
            total over BOARD_FAMILIES — every registered family produces
            `lines(1)` without raising, args derived per row, pinning the
            second family-set enumeration in `BoardEntry.lines` to the registry.
sampled:    16x16 relies on the closed-form count only (brute force over
            every k-combination of 256 cells is infeasible); the closed-form
            itself is cross-checked against true brute force on the four
            small grids, so it is not trusted un-derived at the size it
            matters most.
residual:   relations, regions, frames, and jump triples are absent from
            BoardEntry until a witness game needs them (docs/roadmap.md) --
            not a gap in this registry's own domain, which is cells and
            lines only; non-grid families (hex, track, enumerated graphs)
            are a later rung's registry rows, not a residual of this one.

red under (naming): transposing the file/rank order in _cell_name --
swapping `f"{_FILES[column]}{row + 1}"` for `f"{row + 1}{_FILES[column]}"`
-- fails 8 of 26: test_grid_3x3_cell_order,
test_lines_3_on_grid_3x3_matches_tic_tac_toe_lines,
test_brute_force_matches_generator_on_small_grids[1x1/2x5/5x2/3x3] (all
four), test_lines_k_1_on_1x1_returns_the_single_cell, and
test_lines_k_5_on_2x5_returns_the_two_vertical_only_lines (demonstrated via
`PYTHONPATH="$PWD" .venv/bin/python -m pytest tests/test_boards_registry.py
-q`, which reported "8 failed, 18 passed"; reverted, back to 26 passed).

red under (generator, the born-green integrity sweep specifically):
deleting the down-diagonal `found.add(...)` line in _grid_lines (keeping
only the up-diagonal) -- fails 8 of 27, including
test_integrity_sweep[3x3/2x5/5x2/16x16] (four of five grids; 1x1 has no k>1
to lose a diagonal from) on the closed-form count assertion alone, plus
test_lines_3_on_grid_3x3_matches_tic_tac_toe_lines and
test_brute_force_matches_generator_on_small_grids[2x5/5x2/3x3]
(demonstrated the same way; "8 failed, 19 passed"; reverted, back to 27
passed). This is the witness that _expected_line_count and _grid_lines are
independent: the closed-form formula catches a generator bug at 16x16,
sizes the brute-force cross-check (O(C(w*h, k)) in width*height) cannot
reach.
"""

from __future__ import annotations

import itertools

import pytest

from cardlang.stdlib.boards import BOARD_FAMILIES, BoardEntry, board_entry

GRIDS: list[tuple[int, int]] = [(1, 1), (2, 5), (5, 2), (16, 16), (3, 3)]
SMALL_GRIDS: list[tuple[int, int]] = [(1, 1), (2, 5), (5, 2), (3, 3)]

EXPECTED_TTT_LINES: set[tuple[str, ...]] = {
    ("a1", "b1", "c1"),
    ("a2", "b2", "c2"),
    ("a3", "b3", "c3"),
    ("a1", "a2", "a3"),
    ("b1", "b2", "b3"),
    ("c1", "c2", "c3"),
    ("a1", "b2", "c3"),
    ("a3", "b2", "c1"),
}


def _name(column: int, row: int) -> str:
    """Independent re-derivation of cell naming, for the brute-force check
    below -- deliberately not calling boards.py's _cell_name."""
    return f"{chr(ord('a') + column)}{row + 1}"


def _expected_line_count(width: int, height: int, k: int) -> int:
    """Closed-form line count, independent of boards.py's sliding-window
    generator. k=1 is special: a length-1 window carries no direction, so
    all four alignments produce the same w*h singleton windows and collapse
    under dedup to exactly w*h, not 4*w*h."""
    if k == 1:
        return width * height
    horizontal = height * max(0, width - k + 1)
    vertical = width * max(0, height - k + 1)
    diagonal = max(0, width - k + 1) * max(0, height - k + 1)
    return horizontal + vertical + 2 * diagonal


def _is_aligned(sorted_coords: tuple[tuple[int, int], ...]) -> bool:
    """True iff the given cells (sorted ascending by (column, row)) form one
    contiguous run along a row, a column, or either diagonal direction.
    A colinearity check over the combination, not a window-sliding
    reconstruction -- the second, independent algorithm _brute_force_lines
    needs to be a genuine cross-check rather than a relabeling."""
    k = len(sorted_coords)
    columns = [c for c, _ in sorted_coords]
    rows = [r for _, r in sorted_coords]
    if len(set(columns)) == 1:
        return rows == list(range(rows[0], rows[0] + k))
    if columns != list(range(columns[0], columns[0] + k)):
        return False
    if len(set(rows)) == 1:
        return True
    if rows == list(range(rows[0], rows[0] + k)):
        return True
    return rows == list(range(rows[0], rows[0] - k, -1))


def _brute_force_lines(width: int, height: int, k: int) -> set[tuple[str, ...]]:
    """Every k-combination of cells, kept iff colinear -- O(C(w*h, k)), so
    callers restrict this to small grids."""
    coords = [(c, r) for r in range(height) for c in range(width)]
    found: set[tuple[str, ...]] = set()
    for combo in itertools.combinations(coords, k):
        ordered = tuple(sorted(combo))
        if _is_aligned(ordered):
            found.add(tuple(_name(c, r) for c, r in ordered))
    return found


# ---------------------------------------------------------------------------
# board_entry(): bad-args rejection grid
# ---------------------------------------------------------------------------

BAD_ARGS_CASES: list[tuple[str, tuple[int, ...], str]] = [
    ("hexagon", (3, 3), "unknown board family"),
    ("grid", (3,), "takes 2 argument"),
    ("grid", (3, 3, 3), "takes 2 argument"),
    ("grid", (0, 3), "1..16"),
    ("grid", (3, 17), "1..16"),
    ("grid", (-1, 3), "1..16"),
]


@pytest.mark.parametrize(
    "family, args, expected_substring",
    BAD_ARGS_CASES,
    ids=["unknown_family", "arity_1", "arity_3", "arg_zero", "arg_17", "arg_negative"],
)
def test_board_entry_rejects_bad_args(
    family: str, args: tuple[int, ...], expected_substring: str
) -> None:
    with pytest.raises(ValueError, match=expected_substring):
        board_entry(family, args)


def test_board_families_has_exactly_grid() -> None:
    assert set(BOARD_FAMILIES) == {"grid"}
    assert BOARD_FAMILIES["grid"].arity == 2
    assert BOARD_FAMILIES["grid"].lo == 1
    assert BOARD_FAMILIES["grid"].hi == 16


def test_lines_is_total_over_the_family_registry() -> None:
    # `BoardEntry.lines()` dispatches on `self.family` with a hardcoded
    # `if self.family == "grid": … else: raise` — a SECOND enumeration of the
    # family set beside BOARD_FAMILIES, unlike cell generation which is
    # registry-driven (`spec.build`). A family added to the registry but not to
    # `lines()` would mint cells yet raise "unknown board family" the first time
    # a game asks for its win-lines. This pins `lines()` total over the
    # registry: every family produces `lines(1)` without raising. The args are
    # the minimal valid ones, derived per row (`lo` repeated `arity` times), so
    # a new family is covered without hand-listing.
    # red under: narrowing `BoardEntry.lines`'s `if self.family == "grid"` to a
    # name no family uses reddens this — grid's `lines(1)` then hits the raise.
    for family, spec in BOARD_FAMILIES.items():
        board_entry(family, (spec.lo,) * spec.arity).lines(1)


# ---------------------------------------------------------------------------
# grid(3,3): cell order and the 8 tic-tac-toe lines (the explicit fixture)
# ---------------------------------------------------------------------------


def test_grid_3x3_cell_order() -> None:
    entry = board_entry("grid", (3, 3))
    assert entry.cells == ("a1", "b1", "c1", "a2", "b2", "c2", "a3", "b3", "c3")


def test_lines_3_on_grid_3x3_matches_tic_tac_toe_lines() -> None:
    entry = board_entry("grid", (3, 3))
    lines = entry.lines(3)
    assert set(lines) == EXPECTED_TTT_LINES
    assert len(lines) == 8


def test_lines_is_deterministic_across_calls_and_instances() -> None:
    entry = board_entry("grid", (3, 3))
    assert entry.lines(3) == entry.lines(3)
    other = board_entry("grid", (3, 3))
    assert entry.lines(3) == other.lines(3)


# ---------------------------------------------------------------------------
# Integrity sweep: several grids x every valid k
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width, height", GRIDS, ids=[f"{w}x{h}" for w, h in GRIDS])
def test_integrity_sweep(width: int, height: int) -> None:
    entry = board_entry("grid", (width, height))

    assert len(entry.cells) == width * height
    assert len(set(entry.cells)) == len(entry.cells)

    for k in range(1, max(width, height) + 1):
        lines = entry.lines(k)
        for line in lines:
            assert len(line) == k
            assert len(set(line)) == k
            assert all(cell in entry.cells for cell in line)
        assert len(lines) == _expected_line_count(width, height, k)


@pytest.mark.parametrize("width, height", SMALL_GRIDS, ids=[f"{w}x{h}" for w, h in SMALL_GRIDS])
def test_brute_force_matches_generator_on_small_grids(width: int, height: int) -> None:
    entry = board_entry("grid", (width, height))
    for k in range(1, max(width, height) + 1):
        assert set(entry.lines(k)) == _brute_force_lines(width, height, k)


# ---------------------------------------------------------------------------
# lines(k) bounds
# ---------------------------------------------------------------------------


def test_lines_k_zero_raises() -> None:
    entry = board_entry("grid", (3, 3))
    with pytest.raises(ValueError, match="1..3"):
        entry.lines(0)


def test_lines_k_too_large_raises() -> None:
    entry = board_entry("grid", (3, 3))
    with pytest.raises(ValueError, match="1..3"):
        entry.lines(17)


def test_lines_k_1_on_1x1_returns_the_single_cell() -> None:
    entry = board_entry("grid", (1, 1))
    assert entry.lines(1) == (("a1",),)


def test_lines_k_5_on_2x5_returns_the_two_vertical_only_lines() -> None:
    entry = board_entry("grid", (2, 5))
    lines = entry.lines(5)
    assert set(lines) == {
        ("a1", "a2", "a3", "a4", "a5"),
        ("b1", "b2", "b3", "b4", "b5"),
    }
    assert len(lines) == 2


def test_lines_rejects_a_family_outside_the_registry() -> None:
    # Unreachable through board_entry() today (BOARD_FAMILIES has only
    # "grid"); pins the loud refusal for direct BoardEntry construction.
    entry = BoardEntry(family="hex", args=(1,), cells=("a1",))
    with pytest.raises(ValueError, match="unknown board family"):
        entry.lines(1)


# ---------------------------------------------------------------------------
# BoardEntry construction backstop
# ---------------------------------------------------------------------------


def test_board_entry_rejects_duplicate_cells() -> None:
    with pytest.raises(ValueError, match="unique"):
        BoardEntry(family="grid", args=(1, 2), cells=("a1", "a1"))


def test_board_entry_rejects_empty_cells() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        BoardEntry(family="grid", args=(1, 1), cells=())


def test_board_entry_rejects_over_256_cells() -> None:
    with pytest.raises(ValueError, match="256"):
        BoardEntry(family="grid", args=(16, 16), cells=tuple(f"c{i}" for i in range(257)))
