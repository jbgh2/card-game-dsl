"""Differential validation: cardlang breakthrough against OpenSpiel's NATIVE
`breakthrough`. The board-topology movement rung's external cross-implementation
check, and the corpus's third differential after GOPS and tic-tac-toe.

The action mapping. Native encodes `cell*12 + dir*2 + capture` with
`cell = row*8 + col` and **row 0 the TOP rank**; our cells are `<file><rank>`
with rank 1 at the BOTTOM and player 0 advancing toward rank 8. A vertical
rank-flip absorbs the orientation: `os_row = rank - 1`, `os_col = file`, which
puts our player 0 (home ranks 1-2) exactly on native's player 0 (its two top
rows) — so the seats map identity, both move first, and no player relabel is
needed. Native's six absolute directions are recovered by MATCHING our
actor-resolved `(rank, file)` offset against `kDirRowOffsets`/`kDirColOffsets`:

    player 0:  ahead -> 1   ahead_left -> 0   ahead_right -> 2
    player 1:  ahead -> 4   ahead_left -> 5   ahead_right -> 3

Player 1's diagonals CROSS, because our frame is the 180-degree rotation
(`cardlang/stdlib/boards.py`) while native distinguishes its diagonals by the
sign of the column offset, which the rank-flip leaves untouched. Adding 3 to the
player-0 slot — the obvious guess — swaps them; `test_naive_player_one_diagonal_
mapping_is_a_tripwire` pins that wrong map as a real failure.
`test_mapping_anchors_against_native` grounds the whole mapping against
pyspiel's OWN move rendering rather than bare literals: our a2-a3 is native's
`a7a6` (98), our player-1 b7-c6 is `b2c3` (598) while the naive slot 594 names a
different move (`b2a3`), and our a4xb5 is `a5b4*` (293, capture bit set).

Why this module carries its own walker. `native_oracle.py::walk_paired_
alternating` types `to_native` as `Callable[[decoded], int]`, which suffices for
tic-tac-toe because a placement's id is a function of the placed cell alone.
Breakthrough's id is NOT: the direction group depends on WHO is moving and the
capture bit depends on whether the destination holds an enemy right now, and
neither fact is in `("step", ("a4", "ahead_right"))`. So the walks here keep an
independent MIRROR board (`Mirror` below — its own geometry, occupancy and
capture rules, authored from the rules rather than read out of the runtime) and
reuse `native_oracle.py`'s per-node heart, `assert_node_agrees`, exactly as its
docstring offers it to "any exhaustive/scripted paired walk built on it".
`native_oracle.py` is untouched.

Coverage — three layers, an extra contact layer, and two trip-wires:

(a) `test_exhaustive_prefix_walk_to_depth_2`: DFS over OUR legal actions from
    the opening array to depth 2, asserting the mapped legal SETS equal native's
    at every node (507 nodes). ~3s. Depth 3 is ~11000 nodes (branching 22) and
    would alone exceed the module budget — REDUCED to 2, and the enemy-occupancy
    half of the legality grid, which no depth-3 prefix reaches either (the
    armies start four ranks apart), is covered by (a2) instead.
(a2) `test_contact_position_covers_the_legality_grid`: an 8-ply scripted opening
    that locks two pairs of men into contact, a census asserting the node really
    witnesses 11 of the 12 `{ahead, ahead_left, ahead_right}` x `{empty, enemy,
    friendly, off-board}` grid cells, then an exhaustive walk of that node and
    every child. This is where straight-blocked-by-enemy, both diagonal
    captures, friendly blocking and edge masking are checked against the oracle
    on a real position. ~1s.
(b) `test_scripted_reach_termini` and `test_scripted_wipe_out_terminus`: a
    player-0 march to rank 8, the mirror-image player-1 march to rank 1, and a
    71-ply forced-capture line that takes player 1's LAST man — the second
    terminus the `until` predicate encodes and the one random play never
    reaches. The wipe-out asserts its own discriminator: 16 captures, and NO
    move ever landed on the mover's far row, so the reach terminus cannot be
    what fired. ~5s.
(c) `test_random_trajectories_agree_with_native`: seeded policies walked to
    terminal with exact `returns` equality, and an assertion that the sample
    contains both a player-0 and a player-1 win. REDUCED from 200 seeds to 8: a
    breakthrough trajectory is ~60 plies and the replay adapter re-runs the game
    per ply, so one trajectory costs ~3s against tic-tac-toe's ~5ms. Measured
    over seeds 0-19 the split is 16 player-0 wins to 4; seeds 0-7 contain one
    player-1 win (seed 7). ~24s.
(d) Two trip-wires, one per half of the mapping, proving the agreement above is
    not vacuous: `test_naive_player_one_diagonal_mapping_is_a_tripwire` feeds the
    naive +3 direction map, and `test_blind_capture_bit_is_a_tripwire` feeds a
    mapping that never sets the capture bit — the half that depends on the
    POSITION rather than the decoded action. Both must redden the legal-set
    comparison. <0.5s.

Whole module ~35s, inside the 60s budget.

Residuals. (1) The `ahead` x off-board grid cell is UNWITNESSABLE in real play
on either side: a straight step leaves the board only from a man already
standing on its own far row, and arriving there ends the game. The cell is
covered statically by the movement grid in `tests/test_movement_verbs.py`
(`has_step` false at the edge); the census here asserts the other 11 and names
this one. (2) The differential pins the GEOMETRY of our two diagonals but not
which one is named `left`: breakthrough is mirror-symmetric about the file axis,
so renaming `ahead_left` <-> `ahead_right` consistently in both the board
registry and this module's offset table would be unobservable here — the same
kind of intrinsic symmetry residual tic-tac-toe records for the square's
dihedral group. The concrete convention is pinned by `OUR_OFFSETS` below, which
is authored from the board registry's documented offsets, not derived from it.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.replay import Pause, Terminal, load, run  # noqa: E402
from tests.native_oracle import (  # noqa: E402
    assert_node_agrees,
    assert_outcomes_agree,
    classify,
)

PATH = str(Path(__file__).parent.parent / "docs" / "games" / "breakthrough.cardlang")
NATIVE = "breakthrough"

FILES = "abcdefgh"
SIZE = 8
DIRECTIONS = ("ahead", "ahead_left", "ahead_right")

# Our board's player-0 forward offsets as (rank, file) deltas; player 1's frame
# is the 180-degree rotation of them (cardlang/stdlib/boards.py).
OUR_OFFSETS: dict[str, tuple[int, int]] = {
    "ahead": (1, 0),
    "ahead_left": (1, -1),
    "ahead_right": (1, 1),
}
# breakthrough.cc's kDirRowOffsets/kDirColOffsets as (row, col) pairs indexed by
# native direction id. Our rank delta IS the native row delta under the flip
# `os_row = rank - 1`, and our file delta IS the native column delta.
ORACLE_OFFSETS: tuple[tuple[int, int], ...] = (
    (1, -1), (1, 0), (1, 1), (-1, -1), (-1, 0), (-1, 1),
)

Move = tuple[str, str]  # (from cell, along direction)


def frame_offset(along: str, player: int) -> tuple[int, int]:
    """The (rank, file) delta of one step `along` in `player`'s frame."""
    drank, dfile = OUR_OFFSETS[along]
    return (drank, dfile) if player == 0 else (-drank, -dfile)


def dest_cell(cell: str, along: str, player: int) -> str | None:
    """The cell one step `along` in `player`'s frame, or None off the edge."""
    drank, dfile = frame_offset(along, player)
    f = FILES.index(cell[0]) + dfile
    r = int(cell[1:]) + drank
    if 0 <= f < SIZE and 1 <= r <= SIZE:
        return f"{FILES[f]}{r}"
    return None


def oracle_dir(along: str, player: int) -> int:
    """The native direction id denoting the same absolute step, found by
    matching our actor-resolved offset against the oracle's own table."""
    offset = frame_offset(along, player)
    for idx, oracle in enumerate(ORACLE_OFFSETS):
        if oracle == offset:
            return idx
    raise AssertionError(f"no native direction has offset {offset}")


def naive_oracle_dir(along: str, player: int) -> int:
    """The plausible-but-WRONG map: take player 0's slot and add 3 for player 1.
    Kept only to drive the trip-wire; see the module docstring."""
    return oracle_dir(along, 0) + (3 if player == 1 else 0)


def to_os_cell(cell: str) -> int:
    """The native cell index of one of our cells: `os_row = rank - 1` (the
    vertical flip that lands our player 0 on native's), `os_col = file`."""
    return (int(cell[1:]) - 1) * SIZE + FILES.index(cell[0])


def initial_board() -> dict[str, int]:
    """The opening array: each side's 16 men on its two back ranks."""
    board: dict[str, int] = {}
    for f in FILES:
        for r in (1, 2):
            board[f"{f}{r}"] = 0
        for r in (SIZE - 1, SIZE):
            board[f"{f}{r}"] = 1
    return board


def far_rank(player: int) -> int:
    return SIZE if player == 0 else 1


@dataclass
class Mirror:
    """An independent model of the breakthrough position, authored from the
    rules: it supplies the two facts a decoded action does not carry — who is
    moving and whether the destination holds an enemy — so `to_native` can name
    the native action id. Its occupancy classification also drives the legality
    grid census."""

    board: dict[str, int] = field(default_factory=initial_board)
    player: int = 0
    captures: int = 0
    far_row_arrivals: int = 0
    dir_index: Callable[[str, int], int] = oracle_dir
    capture_bit: bool = True  # a seam the trip-wires blind

    def copy(self) -> Mirror:
        return Mirror(
            board=dict(self.board),
            player=self.player,
            captures=self.captures,
            far_row_arrivals=self.far_row_arrivals,
            dir_index=self.dir_index,
            capture_bit=self.capture_bit,
        )

    def to_native(self, decoded: Any) -> int:
        name, (cell, along) = decoded
        assert name == "step", f"breakthrough has one move type; got {name!r}"
        dest = dest_cell(cell, along, self.player)
        capture = dest is not None and self.board.get(dest) == 1 - self.player
        return (
            to_os_cell(cell) * 12
            + self.dir_index(along, self.player) * 2
            + (1 if capture and self.capture_bit else 0)
        )

    def apply(self, decoded: Any) -> None:
        _, (cell, along) = decoded
        dest = dest_cell(cell, along, self.player)
        assert dest is not None, (
            f"{cell} {along} steps off the board for P{self.player}"
        )
        assert self.board.get(cell) == self.player, (
            f"{cell} does not hold a P{self.player} man ({self.fen()})"
        )
        if dest in self.board:
            assert self.board[dest] != self.player, f"{dest} holds a friendly man"
            assert along != "ahead", "a straight step may not capture"
            self.captures += 1
            del self.board[dest]
        del self.board[cell]
        self.board[dest] = self.player
        if int(dest[1:]) == far_rank(self.player):
            self.far_row_arrivals += 1
        self.player = 1 - self.player

    def men(self, player: int) -> int:
        return sum(1 for owner in self.board.values() if owner == player)

    def occupancy(self, cell: str, along: str) -> str:
        """Which column of the movement-legality grid a step falls in."""
        dest = dest_cell(cell, along, self.player)
        if dest is None:
            return "off_board"
        if dest not in self.board:
            return "empty"
        return "friendly" if self.board[dest] == self.player else "enemy"

    def census(self) -> dict[tuple[str, str], list[Move]]:
        """Every (direction, occupancy) grid cell the mover witnesses here."""
        seen: dict[tuple[str, str], list[Move]] = {}
        for cell, owner in sorted(self.board.items()):
            if owner != self.player:
                continue
            for along in DIRECTIONS:
                seen.setdefault((along, self.occupancy(cell, along)), []).append(
                    (cell, along)
                )
        return seen

    def fen(self) -> str:
        """The position on one line, top rank first, for failure witnesses."""
        return "/".join(
            "".join(str(self.board.get(f"{f}{r}", ".")) for f in FILES)
            for r in range(SIZE, 0, -1)
        )


def _witness(mirror: Mirror, decoded: Sequence[Any]) -> list[Any]:
    return [mirror.fen(), *decoded]


def paired_walk(
    script: Sequence[Move],
    *,
    label: str,
    mirror: Mirror | None = None,
) -> tuple[Pause | Terminal, Any, Mirror]:
    """Drive our game, a fresh native game and the mirror along a FIXED move
    script, asserting mapped legal-set agreement at every ply. Returns our state
    after the script, the native state, and the mirror. `mirror` is the seam the
    trip-wires feed a deliberately wrong mapping through."""
    _, space = load(PATH)
    native = pyspiel.load_game(NATIVE).new_initial_state()
    mirror = mirror if mirror is not None else Mirror()
    history: list[int] = []
    decoded: list[Any] = []
    for i, move in enumerate(script):
        ours = run(PATH, 0, tuple(history))
        assert isinstance(ours, Pause), (
            f"scripted {label}: our game ended after {i} plies"
        )
        assert mirror.player == ours.player, (
            f"scripted {label} ply {i}: mirror expects P{mirror.player}, our game "
            f"offers P{ours.player}"
        )
        assert_node_agrees(
            native, ours, mirror.to_native, space,
            label=f"scripted {label}", step=i, history=_witness(mirror, decoded),
        )
        action = space.encode(("step", move))
        assert action in ours.legal, (
            f"scripted {label} ply {i}: {move} is not legal in our game"
        )
        nid = mirror.to_native(("step", move))
        assert nid in native.legal_actions(), (
            f"scripted {label} ply {i}: native id {nid} for {move} is not legal"
        )
        native.apply_action(nid)
        mirror.apply(("step", move))
        history.append(action)
        decoded.append(("step", move))
    return run(PATH, 0, tuple(history)), native, mirror


def assert_terminus(
    ours: Pause | Terminal,
    native: Any,
    expected: list[float],
    *,
    label: str,
    mirror: Mirror,
) -> None:
    """Both implementations ended, on the same returns."""
    assert isinstance(ours, Terminal), (
        f"scripted {label}: our game is not terminal — {mirror.fen()}"
    )
    assert native.is_terminal(), (
        f"scripted {label}: native is not terminal — {mirror.fen()}"
    )
    assert ours.returns == expected, f"scripted {label}: our returns {ours.returns}"
    assert list(native.returns()) == expected, (
        f"scripted {label}: native returns {list(native.returns())}"
    )
    assert_outcomes_agree(ours.returns, list(native.returns()))


def walk_trajectory(policy_seed: int) -> tuple[list[float], list[float]]:
    """The state-carrying analogue of `native_oracle.py::walk_paired_
    alternating`: one seeded uniform policy over the MAPPED action space,
    applied to our game, native and the mirror together, to a terminal both
    sides must reach."""
    _, space = load(PATH)
    native = pyspiel.load_game(NATIVE).new_initial_state()
    mirror = Mirror()
    policy = random.Random(policy_seed)
    label = f"policy {policy_seed}"
    history: list[int] = []
    decoded: list[Any] = []
    ours: Pause | Terminal = run(PATH, 0, ())
    while isinstance(ours, Pause):
        assert mirror.player == ours.player, (
            f"{label} step {len(history)}: mirror expects P{mirror.player}, our "
            f"game offers P{ours.player}"
        )
        assert_node_agrees(
            native, ours, mirror.to_native, space,
            label=label, step=len(history), history=_witness(mirror, decoded),
        )
        action = policy.choice(ours.legal)
        chosen = space.decode(action)
        native.apply_action(mirror.to_native(chosen))
        mirror.apply(chosen)
        history.append(action)
        decoded.append(chosen)
        ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, Terminal)
    assert native.is_terminal(), (
        f"{label} step {len(history)}: our game is terminal but native is not — "
        f"board={_witness(mirror, decoded)}"
    )
    return ours.returns, list(native.returns())


def _dfs(
    space: Any,
    native: Any,
    mirror: Mirror,
    history: list[int],
    decoded: list[Any],
    depth: int,
    max_depth: int,
    label: str,
) -> int:
    ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, Pause), f"{label}: unexpected terminal at depth {depth}"
    assert mirror.player == ours.player, (
        f"{label} depth {depth}: mirror expects P{mirror.player}, our game offers "
        f"P{ours.player}"
    )
    assert_node_agrees(
        native, ours, mirror.to_native, space,
        label=label, step=depth, history=_witness(mirror, decoded),
    )
    if depth == max_depth:
        return 1
    visited = 1
    for action in ours.legal:
        child_move = space.decode(action)
        child = mirror.copy()
        nid = mirror.to_native(child_move)
        child.apply(child_move)
        visited += _dfs(
            space, native.child(nid), child,
            history + [action], decoded + [child_move],
            depth + 1, max_depth, label,
        )
    return visited


# An 8-ply opening that walks two men of each side into mutual contact: after
# it, player 0's a4 and b4 are blocked straight ahead by enemies on a5 and b5,
# and each can capture the other file's man diagonally.
CONTACT_OPENING: tuple[Move, ...] = (
    ("a2", "ahead"), ("a7", "ahead"), ("a3", "ahead"), ("a6", "ahead"),
    ("b2", "ahead"), ("b7", "ahead"), ("b3", "ahead"), ("b6", "ahead"),
)

# Player 0 marches a man up the a-file to rank 8. Player 1 clears a7 and a8
# (b7 sidesteps first so a8 has somewhere to go) and then plays elsewhere.
P0_REACH: tuple[Move, ...] = (
    ("a2", "ahead"), ("b7", "ahead_left"), ("a3", "ahead"), ("a7", "ahead_left"),
    ("a4", "ahead"), ("a8", "ahead_left"), ("a5", "ahead"), ("h7", "ahead"),
    ("a6", "ahead"), ("g7", "ahead"), ("a7", "ahead"),
)

# The mirror image: player 1 marches down the a-file to rank 1 while player 0
# clears a1 and a2.
P1_REACH: tuple[Move, ...] = (
    ("b2", "ahead_right"), ("a7", "ahead"), ("a2", "ahead_right"), ("a6", "ahead"),
    ("a1", "ahead_right"), ("a5", "ahead"), ("h2", "ahead"), ("a4", "ahead"),
    ("g2", "ahead"), ("a3", "ahead"), ("f2", "ahead"), ("a2", "ahead"),
)

# A forced-capture line that takes player 1's sixteenth man. Constructed offline
# by a greedy driver over the mirror: player 0 captures whenever it can and
# never enters rank 8, player 1 never captures and never enters rank 1, so the
# only terminus available to either side is the wipe-out.
WIPE_OUT: tuple[Move, ...] = (
    ("a2", "ahead"), ("a7", "ahead"), ("a1", "ahead"), ("a8", "ahead"),
    ("b2", "ahead"), ("b7", "ahead"), ("b1", "ahead"), ("b8", "ahead"),
    ("c2", "ahead"), ("c7", "ahead"), ("c1", "ahead"), ("c8", "ahead"),
    ("d2", "ahead"), ("d7", "ahead"), ("d1", "ahead"), ("d8", "ahead"),
    ("e2", "ahead"), ("e7", "ahead"), ("e1", "ahead"), ("e8", "ahead"),
    ("f2", "ahead"), ("f7", "ahead"), ("f1", "ahead"), ("f8", "ahead"),
    ("g2", "ahead"), ("g7", "ahead"), ("g1", "ahead"), ("g8", "ahead"),
    ("h2", "ahead"), ("h7", "ahead"), ("h1", "ahead"), ("h8", "ahead"),
    ("a3", "ahead"), ("a6", "ahead_left"), ("a4", "ahead_right"),
    ("a7", "ahead"), ("b5", "ahead_left"), ("b6", "ahead"),
    ("a6", "ahead_right"), ("b5", "ahead_left"), ("b3", "ahead_right"),
    ("c6", "ahead_left"), ("c4", "ahead_right"), ("c7", "ahead"),
    ("d5", "ahead_left"), ("d6", "ahead"), ("c6", "ahead_right"),
    ("d5", "ahead"), ("c3", "ahead_right"), ("e6", "ahead"),
    ("d4", "ahead_right"), ("e7", "ahead_right"), ("e5", "ahead_left"),
    ("f7", "ahead_right"), ("a2", "ahead"), ("f6", "ahead"),
    ("d3", "ahead_right"), ("f5", "ahead"), ("e3", "ahead_right"),
    ("g6", "ahead"), ("f4", "ahead_right"), ("g7", "ahead_right"),
    ("g5", "ahead_left"), ("e6", "ahead_left"), ("e4", "ahead_right"),
    ("h7", "ahead_right"), ("f5", "ahead_right"), ("h6", "ahead"),
    ("f3", "ahead_right"), ("h5", "ahead"), ("g3", "ahead_right"),
)


def test_mapping_anchors_against_native() -> None:
    """The cell transform bijects onto native's 64 ids, the direction map is the
    offset-matched one (player 1's diagonals crossed), and three concrete action
    ids are grounded against pyspiel's OWN move rendering: a player-0 straight
    step, a player-1 diagonal, and a capture."""
    cells = [f"{f}{r}" for r in range(1, SIZE + 1) for f in FILES]
    assert sorted(to_os_cell(c) for c in cells) == list(range(SIZE * SIZE))
    assert to_os_cell("a1") == 0 and to_os_cell("h8") == 63

    assert {d: oracle_dir(d, 0) for d in DIRECTIONS} == {
        "ahead": 1, "ahead_left": 0, "ahead_right": 2,
    }
    assert {d: oracle_dir(d, 1) for d in DIRECTIONS} == {
        "ahead": 4, "ahead_left": 5, "ahead_right": 3,
    }
    for along in ("ahead_left", "ahead_right"):
        assert oracle_dir(along, 1) != naive_oracle_dir(along, 1), (
            "player 1's diagonals must cross the naive +3 slot"
        )

    mirror = Mirror()
    native = pyspiel.load_game(NATIVE).new_initial_state()
    # Player 0, straight, no capture: our a2->a3 is native's a7a6.
    nid = mirror.to_native(("step", ("a2", "ahead")))
    assert nid == 98 and native.action_to_string(0, nid) == "a7a6"
    assert nid in native.legal_actions()
    native.apply_action(nid)
    mirror.apply(("step", ("a2", "ahead")))
    # Player 1, diagonal: our b7->c6 is native's b2c3 (and NOT the naive slot).
    nid = mirror.to_native(("step", ("b7", "ahead_left")))
    assert nid == 598 and native.action_to_string(1, nid) == "b2c3"
    assert nid in native.legal_actions()
    naive = Mirror(board=dict(mirror.board), player=1, dir_index=naive_oracle_dir)
    assert naive.to_native(("step", ("b7", "ahead_left"))) == 594
    assert native.action_to_string(1, 594) == "b2a3", "the naive slot names b7->a6"

    # A capture, reached by the four-ply prefix that puts an enemy on b5.
    _, native, mirror = paired_walk(
        [("a2", "ahead"), ("b7", "ahead"), ("a3", "ahead"), ("b6", "ahead")],
        label="capture anchor",
    )
    nid = mirror.to_native(("step", ("a4", "ahead_right")))
    assert nid == 293, "our a4xb5 is native cell 24, direction 2, capture bit 1"
    assert nid % 2 == 1, "the capture bit is set"
    assert nid in native.legal_actions()
    assert native.action_to_string(0, nid) == "a5b4*", "native marks a capture"


def test_exhaustive_prefix_walk_to_depth_2() -> None:
    """Layer (a): every prefix of depth <= 2 poses the same mapped legal-action
    set in our game and native. No line ends this early, so every visited node
    is a live decision on both sides."""
    _, space = load(PATH)
    visited = _dfs(
        space, pyspiel.load_game(NATIVE).new_initial_state(), Mirror(),
        [], [], 0, 2, "exhaustive dfs",
    )
    assert visited == 507, (
        f"the opening tree to depth 2 has 507 nodes, walked {visited}"
    )


def test_contact_position_covers_the_legality_grid() -> None:
    """Layer (a2): the movement-legality grid, verified against the oracle on a
    real position. The scripted opening is asserted to WITNESS 11 of the 12
    direction x occupancy cells (the twelfth, a straight step off the board, is
    unreachable in play — see the module docstring), and the node plus every one
    of its children is then checked against native."""
    ours, native, mirror = paired_walk(CONTACT_OPENING, label="contact")
    assert isinstance(ours, Pause) and not native.is_terminal()
    assert mirror.player == 0

    seen = mirror.census()
    expected = {
        (along, occ)
        for along in DIRECTIONS
        for occ in ("empty", "enemy", "friendly", "off_board")
    } - {("ahead", "off_board")}
    assert set(seen) == expected, (
        f"contact node grid census {sorted(seen)} != {sorted(expected)}"
    )

    _, space = load(PATH)
    history = [space.encode(("step", m)) for m in CONTACT_OPENING]
    decoded: list[Any] = [("step", m) for m in CONTACT_OPENING]
    visited = _dfs(
        space, native, mirror.copy(), history, decoded, 0, 1, "contact dfs",
    )
    assert visited == 1 + len(ours.legal)


def test_scripted_reach_termini() -> None:
    """Layer (b), first terminus: a man reaching the opponent's back row ends
    the game on both sides, with the same returns, for either seat."""
    ours, native, mirror = paired_walk(P0_REACH, label="p0 reach")
    assert_terminus(ours, native, [1.0, -1.0], label="p0 reach", mirror=mirror)
    assert mirror.far_row_arrivals == 1 and mirror.captures == 0

    ours, native, mirror = paired_walk(P1_REACH, label="p1 reach")
    assert_terminus(ours, native, [-1.0, 1.0], label="p1 reach", mirror=mirror)
    assert mirror.far_row_arrivals == 1 and mirror.captures == 0


def test_scripted_wipe_out_terminus() -> None:
    """Layer (b), second terminus: player 0 takes player 1's LAST man. The
    discriminator is asserted — 16 captures, and no move ever landed on the
    mover's far row — so the reach terminus cannot be what ended this line."""
    ours, native, mirror = paired_walk(WIPE_OUT, label="wipe-out")
    assert mirror.captures == 16, f"expected 16 captures, saw {mirror.captures}"
    assert mirror.men(1) == 0 and mirror.men(0) == 16
    assert mirror.far_row_arrivals == 0, (
        "the wipe-out line must never reach a far row, or the reach terminus "
        "would be what fired"
    )
    assert_terminus(ours, native, [1.0, -1.0], label="wipe-out", mirror=mirror)


def test_random_trajectories_agree_with_native() -> None:
    """Layer (c): 8 seeded policies walked to terminal — exact returns equality
    against native at every game, and the sample covers a player-0 AND a
    player-1 win. Breakthrough is never a draw, so two outcomes is the whole
    space."""
    tally: Counter[str] = Counter()
    for policy_seed in range(8):
        ours, native = walk_trajectory(policy_seed)
        assert ours == native, (
            f"policy {policy_seed}: terminal returns diverge — ours {ours} "
            f"native {native}"
        )
        assert_outcomes_agree(ours, native)
        assert classify(ours) != "draw", "breakthrough has no draw"
        tally[classify(ours)] += 1
    assert tally["p0"] and tally["p1"], (
        f"8 policies did not cover both winners: {dict(tally)}"
    )


def test_naive_player_one_diagonal_mapping_is_a_tripwire() -> None:
    """The differential FAILS when the direction map is wrong. The naive
    player-1 map (player 0's slot plus 3) swaps that seat's two diagonals; the
    swap is invisible wherever both diagonals are legal, and surfaces at the
    first player-1 node because the a- and h-file men have only one. Pins the
    correction that `oracle_dir`'s offset matching encodes."""
    with pytest.raises(AssertionError, match="legal actions diverge"):
        paired_walk(
            [("a2", "ahead"), ("a7", "ahead_left")],
            label="naive p1 dirs",
            mirror=Mirror(dir_index=naive_oracle_dir),
        )


def test_blind_capture_bit_is_a_tripwire() -> None:
    """The differential FAILS when the capture bit is wrong — the half of the
    mapping that depends on the POSITION rather than the decoded action. A
    mapping that always sends capture=0 agrees with native through the
    captureless plies of the contact opening and diverges at the first node
    where a diagonal step has an enemy under it."""
    with pytest.raises(AssertionError, match="legal actions diverge"):
        paired_walk(
            CONTACT_OPENING,
            label="blind capture bit",
            mirror=Mirror(capture_bit=False),
        )
