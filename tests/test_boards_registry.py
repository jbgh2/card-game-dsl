"""BOARDS registry: the grid family's cells, lines, directions, frames, and
regions, integrity-pinned.

property:   every BOARD_FAMILIES row builds a BoardEntry whose cells are
            unique, nonempty, and within the 256-member position-domain cap;
            board_entry() raises ValueError naming the violated bound for
            every unknown-family, wrong-arity, or out-of-bounds misuse;
            lines(k) returns exactly the k-in-a-row alignments (rows,
            columns, both diagonal directions), deduplicated, for every k in
            1..max(width, height), and raises ValueError outside that range;
            and the grid family's movement data is self-consistent -- the
            direction offsets cover exactly directions(), player 1's frame is
            the 180-degree rotation of player 0's, neighbor() lands on a board
            cell or None, is_diagonal() flags exactly the file-changing
            directions, and home()/far_row() are the back-two-ranks / far-rank
            regions -- refused as a ValueError naming "registry bug" in
            __post_init__, with the adequacy pins (no dead direction, disjoint
            2*width homes) enforced only where width >= 2 and height >= 4.
domain:     BOARD_FAMILIES rows (currently: grid) x argument space (arity,
            per-argument bounds, and the misuse shapes: unknown family,
            wrong arity, out-of-bounds argument) x entry-integrity
            properties: (a) cell/line -- cell uniqueness, cell count, and, per
            k in 1..max(width, height), line length/distinctness/subset-of-
            cells and the line count; (b) movement -- directions() names,
            is_diagonal per direction, neighbor()/has_step() over cells x
            directions x the two seats (edge cells -> None), and
            home()/far_row() over the two seats; crossed with the integrity
            pins (offsets-cover-directions, frames-are-180-rotations,
            neighbor-in-cells-or-None, regions subset/sized/edged, and the
            adequacy pins) over a grid sweep spanning degenerate,
            breakthrough-shaped, and non-square boards.
registry:   cardlang.stdlib.boards.BOARD_FAMILIES, .board_entry, .BoardEntry
            (.lines, .directions, .is_diagonal, .neighbor, .has_step, .home,
            .far_row), and the _GRID_DIRECTION_OFFSETS table.
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
            For movement: directions() == the three forward names; is_diagonal
            == the straight-vs-diagonal split (the oracle's straight-never-
            captures rule); grid(8,8) and grid(3,3) neighbor tables hand-
            computed over both seats and every direction (interior, both
            corners, and edge steps -> None), with has_step agreeing;
            home()/far_row() explicit rank sets on 8x8 and 3x3, and
            far_row(actor) == the opponent's back rank (the outer rank of the
            opponent's home); a universal-pin sweep over MOVEMENT_GRIDS (3x3,
            6x6, 8x8, 8x3, and degenerate 1x1/5x2/2x5) cross-checking
            neighbor() against an independent re-derivation (its own offset
            literals) over every cell x direction x seat, plus frames-180,
            region subset, |far_row| == width, and the top/bottom far-row
            edges; an adequacy sweep over ADEQUATE_GRIDS (2x5, 6x6, 8x8, 8x4):
            no dead direction, disjoint homes, |home| == 2*width; disjointness
            pinned explicitly on the 8x8 corpus board; the grid(3,3) positive
            case that documents the adequacy skip (constructs, homes overlap
            on the middle rank); each born-green movement pin's reddening
            witness as a focused negative test (see "red under (movement)");
            and the method input walls -- unknown direction, seat other than
            0/1, off-grid cell, and a non-grid family -- each refused loudly.
sampled:    16x16 relies on the closed-form count only (brute force over
            every k-combination of 256 cells is infeasible); the closed-form
            itself is cross-checked against true brute force on the four
            small grids, so it is not trusted un-derived at the size it
            matters most. The movement pins are refused at construction on
            every board the runtime instantiates, so the static sweep samples
            grid shapes rather than re-proving the pin on every reachable board.
residual:   relations (adjacency graphs), jump triples (draughts), track
            frames (backgammon), crownhead / arbitrary-depth home regions, and
            frames for more than two seats are absent from BoardEntry until a
            witness game needs them (issue #124) -- not a gap in this
            registry's own domain. The two-seat 180 frame, the seat-relative
            forward directions, and the back-two-ranks / far-rank regions are
            present because breakthrough witnesses them; non-grid families
            (hex, track, enumerated graphs) are a later rung's registry rows,
            not a residual of this one.

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

red under (movement): each born-green movement pin has a focused negative
test that mutates exactly its source and asserts its OWN named refusal on
grid(8,8), not a neighbouring pin's. The five, with their sources:
- test_offsets_cover_directions_pin_reddens: delitem "ahead_left" from
  _GRID_DIRECTION_OFFSETS -> "cover exactly directions()".
- test_frames_180_pin_reddens: force _offset to skip the seat flip ->
  "180-degree rotation".
- test_neighbor_membership_pin_reddens: force neighbor() to return an off-grid
  cell -> "land on a board cell or None".
- test_no_dead_direction_pin_reddens: widen the "ahead" offset to (99, 0) ->
  "is dead".
- test_home_disjoint_pin_reddens: force home() to ignore the seat ->
  "disjoint".
Additionally, corrupting any player-0 offset VALUE (e.g. ahead_left ->
(1, 0)) is caught by the hand tables (test_neighbor_table_grid_8x8/3x3) and
the sweep's independent _expected_neighbor cross-check, not by a structural
__post_init__ pin -- those pin structure (consistency, totality, subset),
while the tables pin the exact geometry. Each reddening was run and observed
to fail its named assertion before landing.
"""

from __future__ import annotations

import itertools

import pytest

from cardlang.stdlib import boards
from cardlang.stdlib.boards import BOARD_FAMILIES, BoardEntry, board_entry

GRIDS: list[tuple[int, int]] = [(1, 1), (2, 5), (5, 2), (16, 16), (3, 3)]
SMALL_GRIDS: list[tuple[int, int]] = [(1, 1), (2, 5), (5, 2), (3, 3)]

DIRECTIONS: tuple[str, ...] = ("ahead", "ahead_left", "ahead_right")

# The movement sweep spans degenerate (1x1, 5x2, 2x5), breakthrough-shaped
# (6x6, 8x8), and non-square (8x3) boards. The adequacy sweep is the subset
# where the frame/region adequacy pins hold -- width >= 2 and height >= 4.
MOVEMENT_GRIDS: list[tuple[int, int]] = [(3, 3), (6, 6), (8, 8), (8, 3), (1, 1), (5, 2), (2, 5)]
ADEQUATE_GRIDS: list[tuple[int, int]] = [(2, 5), (6, 6), (8, 8), (8, 4)]

# Independent copy of the player-0 base offsets, deliberately NOT read from
# boards._GRID_DIRECTION_OFFSETS, so a corruption of that table diverges from
# _expected_neighbor below (the brute-force-vs-generator idiom, for movement).
_BASE_OFFSETS_INDEP: dict[str, tuple[int, int]] = {
    "ahead": (1, 0),
    "ahead_left": (1, -1),
    "ahead_right": (1, 1),
}

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


def _expected_neighbor(width: int, height: int, cell: str, direction: str, player: int) -> str | None:
    """Independent re-derivation of BoardEntry.neighbor -- its own offset
    literals and coordinate math (not boards.py's), so a corrupted offset
    table or a broken seat flip diverges from neighbor() here. Player 1 is the
    180-degree rotation of player 0."""
    drow, dcol = _BASE_OFFSETS_INDEP[direction]
    if player == 1:
        drow, dcol = -drow, -dcol
    col = ord(cell[0]) - ord("a")
    row = int(cell[1:]) - 1
    nc, nr = col + dcol, row + drow
    if 0 <= nc < width and 0 <= nr < height:
        return f"{chr(ord('a') + nc)}{nr + 1}"
    return None


def _rank(rank: int, width: int) -> tuple[str, ...]:
    """The cells of one rank, left to right -- independent of home()/far_row()."""
    return tuple(f"{chr(ord('a') + c)}{rank}" for c in range(width))


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


# ---------------------------------------------------------------------------
# Movement: directions, is_diagonal, neighbor / has_step (explicit tables)
# ---------------------------------------------------------------------------


def test_directions_are_the_three_forward_names() -> None:
    assert board_entry("grid", (8, 8)).directions() == DIRECTIONS
    assert board_entry("grid", (3, 3)).directions() == DIRECTIONS


def test_is_diagonal_matches_straight_vs_diagonal() -> None:
    # The oracle rule (breakthrough.cc): a straight step (dcol 0) never
    # captures; the two file-changing diagonals do. is_diagonal draws exactly
    # that line, and is player-independent.
    entry = board_entry("grid", (8, 8))
    assert entry.is_diagonal("ahead") is False
    assert entry.is_diagonal("ahead_left") is True
    assert entry.is_diagonal("ahead_right") is True


# (cell, direction, player) -> expected neighbour, hand-computed. Player 0
# advances toward higher ranks; player 1 is the 180-degree face-off (its
# ahead_left is file+1, its ahead_right file-1). Edge steps -> None.
NEIGHBOR_8x8: list[tuple[str, str, int, str | None]] = [
    ("a1", "ahead", 0, "a2"),
    ("a1", "ahead_left", 0, None),
    ("a1", "ahead_right", 0, "b2"),
    ("h1", "ahead", 0, "h2"),
    ("h1", "ahead_left", 0, "g2"),
    ("h1", "ahead_right", 0, None),
    ("d4", "ahead", 0, "d5"),
    ("d4", "ahead_left", 0, "c5"),
    ("d4", "ahead_right", 0, "e5"),
    ("a8", "ahead", 0, None),
    ("d8", "ahead_left", 0, None),
    ("h8", "ahead_right", 0, None),
    ("a8", "ahead", 1, "a7"),
    ("a8", "ahead_left", 1, "b7"),
    ("a8", "ahead_right", 1, None),
    ("h8", "ahead", 1, "h7"),
    ("h8", "ahead_left", 1, None),
    ("h8", "ahead_right", 1, "g7"),
    ("d4", "ahead", 1, "d3"),
    ("d4", "ahead_left", 1, "e3"),
    ("d4", "ahead_right", 1, "c3"),
    ("a1", "ahead", 1, None),
    ("h1", "ahead_left", 1, None),
]

NEIGHBOR_3x3: list[tuple[str, str, int, str | None]] = [
    ("a1", "ahead", 0, "a2"),
    ("a1", "ahead_left", 0, None),
    ("a1", "ahead_right", 0, "b2"),
    ("b2", "ahead", 0, "b3"),
    ("b2", "ahead_left", 0, "a3"),
    ("b2", "ahead_right", 0, "c3"),
    ("c3", "ahead", 0, None),
    ("a3", "ahead", 1, "a2"),
    ("a3", "ahead_left", 1, "b2"),
    ("a3", "ahead_right", 1, None),
    ("b2", "ahead", 1, "b1"),
    ("b2", "ahead_left", 1, "c1"),
    ("b2", "ahead_right", 1, "a1"),
    ("a1", "ahead", 1, None),
]


@pytest.mark.parametrize(
    "cell, direction, player, expected",
    NEIGHBOR_8x8,
    ids=[f"{c}-{d}-p{p}" for c, d, p, _ in NEIGHBOR_8x8],
)
def test_neighbor_table_grid_8x8(
    cell: str, direction: str, player: int, expected: str | None
) -> None:
    entry = board_entry("grid", (8, 8))
    assert entry.neighbor(cell, direction, player) == expected
    assert entry.has_step(cell, direction, player) == (expected is not None)


@pytest.mark.parametrize(
    "cell, direction, player, expected",
    NEIGHBOR_3x3,
    ids=[f"{c}-{d}-p{p}" for c, d, p, _ in NEIGHBOR_3x3],
)
def test_neighbor_table_grid_3x3(
    cell: str, direction: str, player: int, expected: str | None
) -> None:
    entry = board_entry("grid", (3, 3))
    assert entry.neighbor(cell, direction, player) == expected
    assert entry.has_step(cell, direction, player) == (expected is not None)


# ---------------------------------------------------------------------------
# Movement: home / far_row regions (explicit)
# ---------------------------------------------------------------------------


def test_home_and_far_row_grid_8x8() -> None:
    entry = board_entry("grid", (8, 8))
    assert entry.home(0) == _rank(1, 8) + _rank(2, 8)
    assert entry.home(1) == _rank(7, 8) + _rank(8, 8)
    assert entry.far_row(0) == _rank(8, 8)
    assert entry.far_row(1) == _rank(1, 8)


def test_home_and_far_row_grid_3x3() -> None:
    entry = board_entry("grid", (3, 3))
    assert entry.home(0) == _rank(1, 3) + _rank(2, 3)
    assert entry.home(1) == _rank(2, 3) + _rank(3, 3)
    assert entry.far_row(0) == _rank(3, 3)
    assert entry.far_row(1) == _rank(1, 3)


def test_far_row_is_the_opponents_back_rank() -> None:
    # far_row(actor) is the opponent's back rank -- the reach-to-win goal, and
    # the outermost rank of the opponent's home.
    entry = board_entry("grid", (8, 8))
    assert entry.far_row(0) == entry.home(1)[-8:]
    assert entry.far_row(1) == entry.home(0)[:8]


# ---------------------------------------------------------------------------
# Movement integrity sweep (universal pins over every grid; adequacy pins over
# adequate grids) -- the runtime __post_init__ pins, re-asserted statically.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "width, height", MOVEMENT_GRIDS, ids=[f"{w}x{h}" for w, h in MOVEMENT_GRIDS]
)
def test_movement_integrity_universal_sweep(width: int, height: int) -> None:
    entry = board_entry("grid", (width, height))
    cellset = set(entry.cells)

    assert entry.directions() == DIRECTIONS
    assert set(boards._GRID_DIRECTION_OFFSETS) == set(entry.directions())

    for cell in entry.cells:
        for d in DIRECTIONS:
            for p in (0, 1):
                nb = entry.neighbor(cell, d, p)
                assert nb == _expected_neighbor(width, height, cell, d, p)
                assert nb is None or nb in cellset
                assert entry.has_step(cell, d, p) == (nb is not None)

    for d in DIRECTIONS:
        o0 = entry._offset(d, 0)
        assert entry._offset(d, 1) == (-o0[0], -o0[1])

    for p in (0, 1):
        assert set(entry.home(p)) <= cellset
        assert set(entry.far_row(p)) <= cellset
        assert len(entry.far_row(p)) == width
    assert all(int(c[1:]) == height for c in entry.far_row(0))
    assert all(int(c[1:]) == 1 for c in entry.far_row(1))


@pytest.mark.parametrize(
    "width, height", ADEQUATE_GRIDS, ids=[f"{w}x{h}" for w, h in ADEQUATE_GRIDS]
)
def test_movement_adequacy_sweep(width: int, height: int) -> None:
    entry = board_entry("grid", (width, height))
    for d in DIRECTIONS:
        for p in (0, 1):
            assert any(entry.has_step(cell, d, p) for cell in entry.cells)
    assert set(entry.home(0)).isdisjoint(entry.home(1))
    for p in (0, 1):
        assert len(entry.home(p)) == 2 * width


def test_home_is_disjoint_on_the_8x8_corpus_board() -> None:
    # The corpus pin (breakthrough is 8x8): the two 16-piece setup regions do
    # not overlap, asserted explicitly rather than only via the sweep.
    entry = board_entry("grid", (8, 8))
    assert set(entry.home(0)).isdisjoint(entry.home(1))
    assert len(entry.home(0)) == 16
    assert len(entry.home(1)) == 16


def test_grid_3x3_constructs_and_homes_overlap() -> None:
    # Tic-tac-toe's board is height 3 -- too short for two disjoint 2-rank
    # homes -- so the adequacy pins are skipped: it constructs, and the homes
    # legitimately overlap on the middle rank. Documents why the __post_init__
    # guard is conditional (grid(3,3) is loaded on every tic-tac-toe run).
    entry = board_entry("grid", (3, 3))
    assert set(entry.home(0)) & set(entry.home(1)) == {"a2", "b2", "c2"}


# ---------------------------------------------------------------------------
# Reddening witnesses: each born-green integrity pin, mutated to fire its own
# named refusal (not a neighbour's) on the 8x8 corpus board.
# ---------------------------------------------------------------------------


def _offset_no_seat_flip(self: BoardEntry, direction: str, player: int) -> tuple[int, int]:
    return boards._GRID_DIRECTION_OFFSETS[direction]  # ignores the seat -- no 180 flip


def _neighbor_off_grid(self: BoardEntry, cell: str, direction: str, player: int) -> str | None:
    return "z9"  # never a board cell


def _home_ignoring_seat(self: BoardEntry, player: int) -> tuple[str, ...]:
    width, _height = self.args
    return tuple(boards._cell_name(c, r) for r in (0, 1) for c in range(width))


def test_offsets_cover_directions_pin_reddens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(boards._GRID_DIRECTION_OFFSETS, "ahead_left")
    with pytest.raises(ValueError, match="cover exactly directions"):
        board_entry("grid", (8, 8))


def test_frames_180_pin_reddens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BoardEntry, "_offset", _offset_no_seat_flip)
    with pytest.raises(ValueError, match="180-degree rotation"):
        board_entry("grid", (8, 8))


def test_neighbor_membership_pin_reddens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BoardEntry, "neighbor", _neighbor_off_grid)
    with pytest.raises(ValueError, match="land on a board cell"):
        board_entry("grid", (8, 8))


def test_no_dead_direction_pin_reddens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(boards._GRID_DIRECTION_OFFSETS, "ahead", (99, 0))
    with pytest.raises(ValueError, match="is dead"):
        board_entry("grid", (8, 8))


def test_home_disjoint_pin_reddens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BoardEntry, "home", _home_ignoring_seat)
    with pytest.raises(ValueError, match="disjoint"):
        board_entry("grid", (8, 8))


# ---------------------------------------------------------------------------
# Movement: method input walls (registry-internal refusals -- the stdlib verbs
# that wrap these only ever pass a valid cell / direction / seat)
# ---------------------------------------------------------------------------


def test_is_diagonal_rejects_unknown_direction() -> None:
    with pytest.raises(ValueError, match="no offset for direction"):
        board_entry("grid", (8, 8)).is_diagonal("sideways")


def test_neighbor_rejects_unknown_direction() -> None:
    with pytest.raises(ValueError, match="no offset for direction"):
        board_entry("grid", (8, 8)).neighbor("a1", "sideways", 0)


def test_neighbor_rejects_bad_player() -> None:
    with pytest.raises(ValueError, match="players 0 and 1"):
        board_entry("grid", (8, 8)).neighbor("a1", "ahead", 2)


def test_neighbor_rejects_off_grid_cell() -> None:
    with pytest.raises(ValueError, match="off grid"):
        board_entry("grid", (3, 3)).neighbor("a9", "ahead", 0)


def test_home_rejects_bad_player() -> None:
    with pytest.raises(ValueError, match="players 0 and 1"):
        board_entry("grid", (8, 8)).home(2)


def test_far_row_rejects_bad_player() -> None:
    with pytest.raises(ValueError, match="players 0 and 1"):
        board_entry("grid", (8, 8)).far_row(2)


def test_movement_methods_reject_a_family_outside_the_registry() -> None:
    # The geometry methods dispatch on family like lines()/directions(); a
    # non-grid BoardEntry refuses them loudly (the lines() twin). Unreachable
    # through board_entry() today (only "grid" is registered).
    entry = BoardEntry(family="hex", args=(1,), cells=("a1",))
    with pytest.raises(ValueError, match="unknown board family"):
        entry.is_diagonal("ahead")
    with pytest.raises(ValueError, match="unknown board family"):
        entry.neighbor("a1", "ahead", 0)
    with pytest.raises(ValueError, match="unknown board family"):
        entry.home(0)
    with pytest.raises(ValueError, match="unknown board family"):
        entry.far_row(0)
