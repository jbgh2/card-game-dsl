"""Differential validation: cardlang tic-tac-toe against OpenSpiel's NATIVE
`tic_tac_toe`. The first board game's external cross-implementation check,
built on the reusable alternating perfect-information walker
(`tests/native_oracle.py`); GOPS's simultaneous + chance-following walker stays
separate.

The action mapping. Native numbers its cells row-major from the TOP-left
(id = row*3 + col, row 0 = top); our cells are named `<col><rank>` with rank 1
at the BOTTOM. So a decoded `("place", cell)` maps to
`(3 - int(cell[1:])) * 3 + "abc".index(cell[0])`. This is a bijection onto
0..8, verified in `test_mapping_is_a_bijection`: our bottom-left a1 -> native 6,
our top-left a3 -> native 0.

Coverage — three layers, plus a trip-wire:

(a) `test_exhaustive_prefix_walk_to_depth_4`: DFS over OUR legal actions from
    the empty board to depth 4, asserting the mapped legal SETS equal native's
    at every node (3610 nodes; no game terminates before depth 5, so every node
    is a live decision). ~1.8s.
(b) `test_scripted_line_coverage`: each of the 8 winning lines completed by X
    (returns [1,-1]), one scripted O-win (returns [-1,1]), one scripted draw
    (full board, returns [0,0]) — asserting native agrees on the terminal and
    the exact returns. Drives native THROUGH `to_native`, so the mapping is
    load-bearing here. <0.1s.
(c) `test_random_trajectories_agree_with_native`: 200 seeded policies walked to
    terminal, exact returns equality, and an assertion that X-wins, O-wins, AND
    draws all arose (the sample is not one degenerate branch). ~1s.

Whole module runs well under the 60s budget (~3s locally); depth 4 is kept
(measured, not reduced).

What each layer catches — the trip-wire (`test_line_breaking_mapping_is_a_
tripwire`, deliverable 3). Layer (a)'s legal-set comparison catches only
STRUCTURAL mapping errors (an image that escapes 0..8, or a collision): within
depth 4 both trees are pre-terminal, and ANY bijection keeps them isomorphic,
so a well-formed relabeling passes (a1) untouched. A well-formed but
LINE-BREAKING mapping is caught instead by layers (b)/(c), at
`assert native.is_terminal()`: when an our-line maps to non-collinear native
cells, our game reports a win the native oracle does not. The trip-wire feeds
exactly such a bijection (center<->corner swap) to a scripted X-win and asserts
the terminal check reddens.

Residual — NO differential layer pins `to_native`'s orientation. A
line-preserving relabeling (any of the square's 8 dihedral automorphisms)
produces an isomorphic, line-agreeing tree that every layer (a/b/c) accepts
unchanged, because the win condition is symmetric under that group. The
concrete orientation is pinned ONLY by `test_mapping_is_a_bijection`'s two
anchor assertions (a1 -> 6, a3 -> 0), and those are grounded against pyspiel's
own board rendering there so they are not bare magic numbers. This is intrinsic
to a fully-symmetric board, not a coverage gap: any of the 8 orientations would
be an equally valid oracle mapping, and the anchors select the one our board
actually uses.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.replay import DecisionNode, TerminalNode, load, run
from tests.native_oracle import (
    assert_node_agrees,
    assert_outcomes_agree,
    classify,
    walk_paired_alternating,
)

PATH = str(Path(__file__).parent.parent / "docs" / "games" / "tic-tac-toe.cardlang")
NATIVE = "tic_tac_toe"

# The nine squares in the board's declared member order (row-major from a1).
NINE_CELLS = ("a1", "b1", "c1", "a2", "b2", "c2", "a3", "b3", "c3")

# Our board's 8 winning lines, in our cell names (col letter + rank, rank 1 at
# the bottom): three rows, three columns, two diagonals.
LINES = (
    ("a1", "b1", "c1"),
    ("a2", "b2", "c2"),
    ("a3", "b3", "c3"),
    ("a1", "a2", "a3"),
    ("b1", "b2", "b3"),
    ("c1", "c2", "c3"),
    ("a1", "b2", "c3"),
    ("a3", "b2", "c1"),
)


def to_native(decoded: Any) -> int:
    """The native `tic_tac_toe` action id a decoded `("place", cell)` denotes.
    Native rows count from the top; our ranks from the bottom, hence `3 -`."""
    _, cell = decoded
    return (3 - int(cell[1:])) * 3 + "abc".index(cell[0])


def from_native(nid: int) -> str:
    """The inverse of `to_native`: the our-board cell a native id denotes."""
    row, col = divmod(nid, 3)
    return f"{'abc'[col]}{3 - row}"


def walk_cells(
    cells: list[str],
    to_native_fn: Callable[[Any], int] = to_native,
    seed: int = 0,
) -> tuple[list[float], list[float]]:
    """Drive our game and a fresh native game along a FIXED placement order (our
    cells), applying each to native through `to_native_fn`; return both returns
    vectors. Asserts mapped legal-set agreement at every ply and that both reach
    a terminal together. `to_native_fn` is a seam for the trip-wire."""
    _, space = load(PATH)
    native = pyspiel.load_game(NATIVE).new_initial_state()
    history: list[int] = []
    decoded: list[Any] = []
    for i, cell in enumerate(cells):
        ours = run(PATH, seed, tuple(history))
        assert isinstance(ours, DecisionNode), (
            f"scripted walk {cells}: our game ended after {i} plies"
        )
        assert_node_agrees(
            native, ours, to_native_fn, space,
            label=f"scripted {cells}", step=i, history=decoded,
        )
        action = space.encode(("place", cell))
        assert action in ours.legal, (
            f"scripted cell {cell} is not legal for our game at ply {i}"
        )
        nid = to_native_fn(("place", cell))
        assert nid in native.legal_actions(), (
            f"scripted native id {nid} is not legal at ply {i}"
        )
        native.apply_action(nid)
        history.append(action)
        decoded.append(("place", cell))
    ours = run(PATH, seed, tuple(history))
    assert isinstance(ours, TerminalNode), (
        f"scripted walk {cells}: our game is not terminal after {len(cells)} plies"
    )
    assert native.is_terminal(), (
        f"scripted walk {cells}: native not terminal after {len(cells)} plies "
        f"— the mapping breaks the line"
    )
    return ours.returns, list(native.returns())


def _x_win_script(line: tuple[str, str, str]) -> list[str]:
    """A five-ply history in which X completes `line`: X takes the three line
    cells, O takes two other cells (which cannot form a line — O plays twice)."""
    fillers = [c for c in NINE_CELLS if c not in line]
    return [line[0], fillers[0], line[1], fillers[1], line[2]]


def test_mapping_is_a_bijection() -> None:
    """`to_native` bijects our nine cells onto native ids 0..8, and `from_native`
    inverts it. Pins the two orientation anchors: a1 (bottom-left) -> 6,
    a3 (top-left) -> 0."""
    images = sorted(to_native(("place", c)) for c in NINE_CELLS)
    assert images == list(range(9))
    assert to_native(("place", "a1")) == 6
    assert to_native(("place", "a3")) == 0
    for c in NINE_CELLS:
        assert from_native(to_native(("place", c))) == c

    # Ground the two anchors against native's own board geometry, so the
    # orientation is verified rather than a bare literal: a1 is bottom-left,
    # a3 is top-left, and native renders row 0 at the top.
    for cell, expected_row in (("a1", 2), ("a3", 0)):
        s = pyspiel.load_game(NATIVE).new_initial_state()
        s.apply_action(to_native(("place", cell)))
        rows = str(s).split("\n")
        assert rows[expected_row][0] == "x" and str(s).count("x") == 1, (
            f"{cell} should mark native row {expected_row} column 0; got:\n{s}"
        )


def _dfs(
    space: Any,
    native: Any,
    history: list[int],
    decoded: list[Any],
    depth: int,
    max_depth: int,
) -> None:
    ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, DecisionNode), (
        f"depth {depth}: unexpected terminal within depth {max_depth}"
    )
    assert_node_agrees(
        native, ours, to_native, space,
        label="exhaustive dfs", step=depth, history=decoded,
    )
    if depth == max_depth:
        return
    for action in ours.legal:
        decoded_action = space.decode(action)
        _dfs(
            space,
            native.child(to_native(decoded_action)),
            history + [action],
            decoded + [decoded_action],
            depth + 1,
            max_depth,
        )


def test_exhaustive_prefix_walk_to_depth_4() -> None:
    """Layer (a): every prefix of depth <= 4 poses the same mapped legal-action
    set in our game and native (3610 nodes). No game terminates before depth 5,
    so every visited node is a live decision on both sides."""
    _, space = load(PATH)
    _dfs(space, pyspiel.load_game(NATIVE).new_initial_state(), [], [], 0, 4)


def test_scripted_line_coverage() -> None:
    """Layer (b): each of the 8 lines completed by X (returns [1,-1]), one
    scripted O-win (returns [-1,1]), one scripted draw (returns [0,0]) — native
    agrees on the terminal and the exact returns, and on the classification."""
    for line in LINES:
        ours, native = walk_cells(_x_win_script(line))
        assert ours == [1.0, -1.0], f"X completing {line}: our returns {ours}"
        assert native == [1.0, -1.0], f"X completing {line}: native returns {native}"
        assert_outcomes_agree(ours, native)

    # O (player 1) completes the top row {a3,b3,c3}; X takes a2,b2,a1 (no line).
    ours, native = walk_cells(["a2", "a3", "b2", "b3", "a1", "c3"])
    assert ours == [-1.0, 1.0] and native == [-1.0, 1.0], (ours, native)
    assert_outcomes_agree(ours, native)

    # A full board with no line: draw, returns [0,0] on both sides.
    ours, native = walk_cells(
        ["a3", "b3", "c3", "b2", "a2", "c2", "b1", "a1", "c1"]
    )
    assert ours == [0.0, 0.0] and native == [0.0, 0.0], (ours, native)
    assert_outcomes_agree(ours, native)


def test_random_trajectories_agree_with_native() -> None:
    """Layer (c): 200 seeded policies walked to terminal — exact returns
    equality against native at every game, and the sample covers X-wins,
    O-wins, AND draws (not one degenerate branch)."""
    tally: Counter[str] = Counter()
    for policy_seed in range(200):
        ours, native = walk_paired_alternating(
            PATH, NATIVE, to_native, seed=0, policy_seed=policy_seed
        )
        assert ours == native, (
            f"policy {policy_seed}: terminal returns diverge — ours {ours} "
            f"native {native}"
        )
        assert_outcomes_agree(ours, native)
        tally[classify(ours)] += 1
    assert tally["p0"] and tally["p1"] and tally["draw"], (
        f"200 policies did not cover all three outcomes: {dict(tally)}"
    )


def test_line_breaking_mapping_is_a_tripwire() -> None:
    """Deliverable 3: the differential FAILS when the game tree diverges. A
    line-breaking bijection (swap the native images of center b2 and corner c3 —
    a center/corner swap is NOT a board automorphism) sends X's top-row line
    {a3,b3,c3} to non-collinear native cells {0,1,4}. Every legal-set check
    still passes (the tree stays isomorphic under a bijection), so the failure
    surfaces exactly at `assert native.is_terminal()`: our game reports X's win,
    native does not."""
    swap = {"c3": to_native(("place", "b2")), "b2": to_native(("place", "c3"))}

    def wrong(decoded: Any) -> int:
        _, cell = decoded
        return swap.get(cell, to_native(decoded))

    with pytest.raises(AssertionError, match="native not terminal"):
        walk_cells(_x_win_script(("a3", "b3", "c3")), to_native_fn=wrong)
