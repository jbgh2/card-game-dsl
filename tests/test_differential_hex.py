"""Differential validation: cardlang Hex against OpenSpiel's NATIVE `hex` at
`board_size=11`, `swap=false`. The connection rung's external
cross-implementation check, on the alternating perfect-information walker
(`tests/native_oracle.py`) tic-tac-toe uses.

The action mapping. Native numbers its cells row-major from the corner its
`ActionToString` prints `a1` (id = row * 11 + column, its row the rank and its
column the file, as `hex.cc` renders them), so a decoded `("place", cell)`
maps to `(rank - 1) * 11 + "abcdefghijk".index(file)`: a bijection onto
0..120 whose image of every cell renders, in native's own strings, as the
cell's name (`test_mapping_names_every_cell_as_native_does`). Black is seat 0
on both sides and moves first; native's black joins its first row to its last
(ranks 1 and 11) and white its first column to its last (files `a` and `k`),
our `near_edge`/`far_edge`. The board-size-1 oracle is not terminal after its
only stone, so no comparison here leaves size 11.

Coverage — three layers, plus a trip-wire:

(a) `test_exhaustive_prefix_walk_to_depth_1`: the empty board and every
    one-stone board pose the same mapped legal SETS in our game and native
    (122 nodes). REDUCED to depth 1: depth 2 is 14,641 nodes, and the replay
    adapter re-runs the game per node at about 6 ms for a two-stone history
    (measured 2026-11-01), so it alone would take about 90 s of the module's
    60 s budget. Within any short prefix both trees are pre-terminal and any
    bijection keeps them isomorphic, so this layer catches only STRUCTURAL
    mapping errors; the layers below carry the adjacency.
(b) `test_scripted_lines_agree_with_native`: four lines driven through
    `to_native`, native agreeing on the terminal and the exact returns at the
    same ply — black's straight chain up file `a` (21 plies, [1, -1]), white's
    along rank 1 (22 plies, [-1, 1]), and a staircase for each side along the
    diagonal (`k1 j2 ... a11`), the one adjacency a grid does not have.
(c) `test_random_trajectories_agree_with_native`: seeded uniform policies
    walked to terminal, mapped legal-set equality at every decision and exact
    returns equality, and the sample holds a black win and a white win.
    REDUCED to `TRAJECTORIES` policies: a uniform line runs 70 to 121 plies
    and the replay adapter re-runs the game per ply, so one trajectory costs
    about 6 s, against tic-tac-toe's 5 ms (measured 2026-11-01; the whole
    module 34 s).
(d) `test_transposed_mapping_is_a_tripwire`: a mapping that preserves the
    adjacency but exchanges the two seats' goals (the transpose `a2` <-> `b1`)
    sends black's file-`a` chain to native's rank 1, which joins nothing for
    black; every legal-set check still passes, so the failure surfaces at
    `assert native.is_terminal()`.

Residual — the board's own symmetry. The rhombus has one automorphism that
keeps every seat's goal: the half-turn `(file, rank) -> (10 - file, 12 -
rank)`. A mapping composed with it agrees with native at every layer here, so
the orientation is pinned only by `test_mapping_names_every_cell_as_native_
does`, which reads native's own cell strings rather than a literal.

red under (adjacency): `(1, 1)` in place of `(1, -1)` in
`boards._HEX_FORWARD_OFFSETS` reddens both staircases (our game is not
terminal at the last stair) and the random trajectories (our game is
terminal where native is not); depth 1 and the two straight lines stay
green, as they must.
red under (orientation): `to_native` composed with the half-turn reddens
`test_mapping_names_every_cell_as_native_does` alone, the residual above.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.replay import DecisionNode, TerminalNode, load, run  # noqa: E402
from tests.native_oracle import (  # noqa: E402
    assert_node_agrees,
    assert_outcomes_agree,
    classify,
    walk_paired_alternating,
)

PATH = str(Path(__file__).parent.parent / "docs" / "games" / "hex.cardlang")
NATIVE = "hex(board_size=11,swap=false)"

SIZE = 11
FILES = "abcdefghijk"
# The 121 cells in the board's declared member order (row-major from a1).
CELLS = tuple(f"{f}{r}" for r in range(1, SIZE + 1) for f in FILES)

# The policy seeds walked by layer (c), sized to the module budget.
TRAJECTORIES = 5


def to_native(decoded: Any) -> int:
    """The native `hex` action id a decoded `("place", cell)` denotes."""
    _, cell = decoded
    return (int(cell[1:]) - 1) * SIZE + FILES.index(cell[0])


def _new_native() -> Any:
    return pyspiel.load_game(NATIVE).new_initial_state()


def walk_cells(
    cells: list[str],
    to_native_fn: Callable[[Any], int] = to_native,
) -> tuple[list[float], list[float]]:
    """Drive our game and a fresh native game along a FIXED placement order (our
    cells), applying each to native through `to_native_fn`; return both returns
    vectors. Asserts mapped legal-set agreement at every ply and that both reach
    a terminal together. `to_native_fn` is a seam for the trip-wire."""
    _, space = load(PATH)
    native = _new_native()
    history: list[int] = []
    decoded: list[Any] = []
    for i, cell in enumerate(cells):
        ours = run(PATH, 0, tuple(history))
        assert isinstance(ours, DecisionNode), (
            f"scripted walk: our game ended after {i} plies, before {cell}"
        )
        assert not native.is_terminal(), f"scripted walk: native ended after {i} plies"
        assert_node_agrees(
            native, ours, to_native_fn, space,
            label="scripted", step=i, history=decoded,
        )
        action = space.encode(("place", cell))
        assert action in ours.legal, f"scripted cell {cell} is not legal at ply {i}"
        native.apply_action(to_native_fn(("place", cell)))
        history.append(action)
        decoded.append(("place", cell))
    ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, TerminalNode), (
        f"scripted walk: our game is not terminal after {len(cells)} plies"
    )
    assert native.is_terminal(), (
        f"scripted walk: native not terminal after {len(cells)} plies "
        f"— the mapping breaks the chain"
    )
    return ours.returns, list(native.returns())


def _interleave(first: list[str], second: list[str]) -> list[str]:
    """Black's cells and white's, alternating from black."""
    line: list[str] = []
    for i in range(max(len(first), len(second))):
        line += first[i : i + 1] + second[i : i + 1]
    return line


# Black up file `a`, white idling on file `k` below rank 11.
BLACK_FILE_A = _interleave([f"a{r}" for r in range(1, 12)], [f"k{r}" for r in range(1, 11)])
# White along rank 1, black idling on rank 11.
WHITE_RANK_1 = _interleave([f"{f}11" for f in FILES], [f"{f}1" for f in FILES])
# The diagonal from `k1` up to `a11`: each step is file - 1, rank + 1.
STAIR = [f"{FILES[SIZE - 1 - i]}{i + 1}" for i in range(SIZE)]
# Black climbs the stair from rank 1, white idling on file `a` below the stair.
BLACK_STAIR = _interleave(STAIR, [f"a{r}" for r in range(1, 11)])
# White descends the stair from file `a`; black idles on file `a` below it and
# on `b1`, a set that reaches rank 10 and no further.
WHITE_STAIR = _interleave(
    [f"a{r}" for r in range(1, 11)] + ["b1"], list(reversed(STAIR))
)


def test_mapping_names_every_cell_as_native_does() -> None:
    """`to_native` bijects our 121 cells onto native ids 0..120, and native's
    own `ActionToString` renders each image as the cell's name — so the
    orientation is read off the oracle, not a literal."""
    images = [to_native(("place", c)) for c in CELLS]
    assert sorted(images) == list(range(SIZE * SIZE))
    state = _new_native()
    for cell, nid in zip(CELLS, images):
        assert state.action_to_string(0, nid) == cell


def _dfs(space: Any, native: Any, history: list[int], decoded: list[Any], depth: int) -> int:
    ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, DecisionNode), f"depth {depth}: unexpected terminal"
    assert_node_agrees(
        native, ours, to_native, space,
        label="exhaustive dfs", step=depth, history=decoded,
    )
    if depth == 1:
        return 1
    visited = 1
    for action in ours.legal:
        step = space.decode(action)
        visited += _dfs(
            space, native.child(to_native(step)), history + [action], decoded + [step], depth + 1
        )
    return visited


def test_exhaustive_prefix_walk_to_depth_1() -> None:
    """Layer (a): every prefix of depth <= 1 poses the same mapped legal-action
    set in our game and native (122 nodes)."""
    _, space = load(PATH)
    assert _dfs(space, _new_native(), [], [], 0) == 1 + SIZE * SIZE


@pytest.mark.parametrize(
    ("line", "plies", "returns"),
    [
        (BLACK_FILE_A, 21, [1.0, -1.0]),
        (WHITE_RANK_1, 22, [-1.0, 1.0]),
        (BLACK_STAIR, 21, [1.0, -1.0]),
        (WHITE_STAIR, 22, [-1.0, 1.0]),
    ],
    ids=["black-file-a", "white-rank-1", "black-stair", "white-stair"],
)
def test_scripted_lines_agree_with_native(line: list[str], plies: int, returns: list[float]) -> None:
    """Layer (b): each scripted line ends at its last stone on both sides, with
    the exact returns."""
    assert len(line) == plies
    ours, native = walk_cells(line)
    assert ours == returns, f"our returns {ours}"
    assert native == returns, f"native returns {native}"
    assert_outcomes_agree(ours, native)


def test_random_trajectories_agree_with_native() -> None:
    """Layer (c): seeded uniform policies walked to terminal — exact returns
    equality against native, and both winners arise."""
    tally: Counter[str] = Counter()
    for policy_seed in range(TRAJECTORIES):
        ours, native = walk_paired_alternating(
            PATH, NATIVE, to_native, seed=0, policy_seed=policy_seed
        )
        assert ours == native, (
            f"policy {policy_seed}: terminal returns diverge — ours {ours} native {native}"
        )
        assert_outcomes_agree(ours, native)
        tally[classify(ours)] += 1
    assert tally["p0"] and tally["p1"], (
        f"{TRAJECTORIES} policies did not cover both winners: {dict(tally)}"
    )
    assert not tally["draw"]


def test_transposed_mapping_is_a_tripwire() -> None:
    """Layer (d): the differential FAILS when the trees diverge. The transpose
    `(file, rank) -> (rank, file)` keeps the adjacency and exchanges the two
    seats' goals, so black's file-`a` chain lands on native's rank 1. Every
    legal-set check passes (the tree stays isomorphic under a bijection), and
    the failure surfaces exactly at `assert native.is_terminal()`."""

    def transposed(decoded: Any) -> int:
        _, cell = decoded
        file_, rank = FILES.index(cell[0]), int(cell[1:]) - 1
        return file_ * SIZE + rank

    with pytest.raises(AssertionError, match="native not terminal"):
        walk_cells(BLACK_FILE_A, to_native_fn=transposed)
