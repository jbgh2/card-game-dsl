"""Differential validation: the corpus game `docs/games/english-draughts.cardlang`
against OpenSpiel's NATIVE `checkers`.

At every node a walk reaches, the two implementations pose the same decision:
the same seat is to move, and the game's legal actions, mapped into the
oracle's action space, are exactly the oracle's legal set. A line the rules
end ends on both sides with the same outcome. The oracle also ends every line
after forty plies in a row without a capture (`kMaxMovesWithoutCapture` in
its source), counting every step and every hop, with returns [0, 0]. That
draw is not a rule of the game (the game's header says so): there the walk
stops comparing and counts the line as truncated (`oracle_forty`).

The mapping. The oracle numbers its squares row by row from the TOP rank,
`row = 8 - rank`, `col = file`, and its action id is
`((row * 8 + col) * 4 + direction) * 2 + move_type` (`RankActionMixedBase`
over rows, columns, `kNumDirections`, `kNumMoveType`), a capture's
move type 1. Its player 0 starts on ranks 1 to 3, as the game's Red does, so
the seats map identity. Its four absolute directions are recovered by
MATCHING the mover's frame offset against `kDirRowOffsets` /
`kDirColumnOffsets`, as breakthrough's differential does; the mover is the
one fact a decoded action does not carry, so the walks keep an independent
`Mirror` of the position, authored from the rules rather than read out of the
runtime, whose mover is the mapping's. The Mirror also states its own legal
set at every node (`Mirror.legal`), held equal to the game's, and the walks
assert the seat the walker reports against the Mirror's mover, so a chain the
Mirror misreads fails as a mover mismatch.
`test_mapping_anchors_against_native` grounds the table against pyspiel's
own move rendering, whose square names are the game's.

The walker. Every line is `tests/native_oracle.py::walk_paired_prefix`, one
live run each, `oracle_forty` its `truncate_when`; the prefix walk is the
paused adapter, `run` with a history, through `assert_node_agrees`. On the
branch where a win by the game's rules falls on the ply the oracle's forty
ends the line, the walker is strict, and fails the line; how the differential
treats that branch is the open question on issue #983
(https://github.com/jbgh2/card-game-dsl/issues/983#issuecomment-6571173557).

Coverage:

(a) `test_exhaustive_prefix_walk`: every prefix of the opening array to
    `PREFIX_DEPTH`, through the paused adapter.
(b) Scripted lines, each a prefix walked move by move and then continued by
    a seeded uniform policy to the line's end: a multiple jump of two and of
    three hops with another piece's jump open beside it, the chain offering
    the jumping piece alone; a man crowned by a jump with a further jump open
    to the new king, the move ending there on both sides; a king's backward
    step and backward capture; and a blockade, the loser holding pieces with
    no legal move.
(c) `test_random_trajectories_agree_with_native`: seeded uniform policies
    over `POLICY_SEEDS`, walked to a rules end or the truncation; the tally
    holds both winners and a truncation.
(d) The forty-move draw, on the game alone past the oracle's truncation: a
    king shuffle to seventy-nine quiet plies broken by a man's step, then
    eighty quiet plies to the tie, the count read at every ply.
(e) The tripwires: the mapping with seat 1's frame read as seat 0's, and the
    mapping blind to the move type. Each must redden the comparison.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   at every node a walk reaches, the game and the oracle agree on the
            seat to move and on the mapped legal-action set, and the Mirror's
            legal set is the game's; a line the rules end ends on both sides
            on the same outcome; where the oracle ends a line by its forty
            with returns [0, 0], the game still offers a decision.
domain:     the nodes of the prefix tree to `PREFIX_DEPTH`; the nodes of the
            scripted lines; the nodes of every line over `POLICY_SEEDS`.
            Outside it, by the ruling on issue #953, the tail of a line past
            the oracle's forty, which (d) plays on the game alone.
registry:   `tests/native_oracle.py::assert_node_agrees`;
            `tests/native_oracle.py::walk_paired_prefix`; `ORACLE_OFFSETS`
            and `MOVE_TYPES`, the oracle's own tables; `CELLS` and
            `OUR_OFFSETS`, held against `cardlang.stdlib.boards.
            board_entry("draughts", (8, 8))` by the anchor test.
held by:    the direction and square tables are a Born-Green Pin (the
            bijection, and pyspiel's rendering of the opening moves, a
            capture and a king's backward move); why not higher: the oracle's
            tables are external data with no source in the tree. The
            truncation is a Born-Green Pin: `oracle_forty` counts the
            capture-free tail of the oracle's own history against
            `ORACLE_FORTY`, and the walker asks it only of a terminal oracle;
            why not higher: the count's value is external data, and the
            policy lines that truncate are its witnesses, the walk failing
            under any other value.
does not prove:  that the game and the oracle agree past the oracle's forty,
            where the oracle has no game to compare (the draw lines of (d)
            are the game's alone, against the Mirror); nor at a node no walk
            reaches: the scripted lines show each rule's branch played, not
            every position.

red under (directions): `oracle_dir` reading every seat's offset in seat 0's
frame reddens the first tripwire's walk at White's first move, and every
walk; `MOVE_TYPES` with its two entries exchanged reddens every walk at the
root.
red under (truncation): `ORACLE_FORTY = 39` reddens the policy walk at the
first truncating seed, the oracle's end no longer named.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.replay import DecisionNode, load, run
from cardlang.runtime.driver import EndedBy
from cardlang.stdlib.boards import board_entry
from tests.native_oracle import (
    Choose,
    LineEnd,
    Rules,
    Truncated,
    assert_node_agrees,
    tally_line_ends,
    uniform,
    walk_paired_prefix,
)

PATH = str(Path(__file__).parent.parent / "docs" / "games" / "english-draughts.cardlang")
NATIVE = "checkers"

FILES = "abcdefgh"
SIZE = 8
# The thirty-two dark squares, row-major from rank 1: file (a = 1) plus rank even.
CELLS: tuple[str, ...] = tuple(
    f"{f}{r}" for r in range(1, SIZE + 1) for i, f in enumerate(FILES) if (i + 1 + r) % 2 == 0
)
DIRECTIONS = ("ahead_left", "ahead_right", "back_left", "back_right")
# Seat 0's frame as (rank, file) steps; seat 1's is the half turn of it.
OUR_OFFSETS: dict[str, tuple[int, int]] = {
    "ahead_left": (1, -1),
    "ahead_right": (1, 1),
    "back_left": (-1, -1),
    "back_right": (-1, 1),
}
# checkers.cc's kDirRowOffsets / kDirColumnOffsets as (row, col) pairs indexed
# by the oracle's direction id, row 0 the top rank.
ORACLE_OFFSETS: tuple[tuple[int, int], ...] = ((-1, -1), (-1, 1), (1, 1), (1, -1))
MOVE_TYPES: dict[str, int] = {"step": 0, "jump": 1}  # kNormal, kCapture
ORACLE_FORTY = 40  # `kMaxMovesWithoutCapture` in the oracle's source

# The game's forty-move rule: each player's own forty moves.
QUIET_DRAW = 80


def frame_offset(along: str, player: int) -> tuple[int, int]:
    """The (rank, file) step of one move `along` in `player`'s frame."""
    drank, dfile = OUR_OFFSETS[along]
    return (drank, dfile) if player == 0 else (-drank, -dfile)


def beyond(cell: str, along: str, player: int, hops: int = 1) -> str | None:
    """The square `hops` steps `along` from `cell`, or None off the board."""
    drank, dfile = frame_offset(along, player)
    f = FILES.index(cell[0]) + dfile * hops
    r = int(cell[1:]) + drank * hops
    if 0 <= f < SIZE and 1 <= r <= SIZE:
        return f"{FILES[f]}{r}"
    return None


def is_forward(along: str) -> bool:
    return OUR_OFFSETS[along][0] > 0


def far_rank(player: int) -> int:
    return SIZE if player == 0 else 1


def oracle_dir(along: str, player: int) -> int:
    """The oracle's direction id for the same absolute step, matched against
    its own offset table (rank up is row down)."""
    drank, dfile = frame_offset(along, player)
    return ORACLE_OFFSETS.index((-drank, dfile))


def seat_zero_dir(along: str, player: int) -> int:
    """The WRONG map: every seat's direction read in seat 0's frame. Kept only
    to drive the tripwire."""
    return oracle_dir(along, 0)


def oracle_square(cell: str) -> int:
    """The oracle's row-major square index, row 0 the top rank."""
    return (SIZE - int(cell[1:])) * SIZE + FILES.index(cell[0])


def initial_board() -> dict[str, tuple[int, bool]]:
    """Each side's twelve men on the dark squares of its back three ranks."""
    board: dict[str, tuple[int, bool]] = {}
    for cell in CELLS:
        rank = int(cell[1:])
        if rank <= 3:
            board[cell] = (0, False)
        elif rank >= SIZE - 2:
            board[cell] = (1, False)
    return board


Move = tuple[str, tuple[str, str]]  # (move type, (from, along))


@dataclass
class Ply:
    """One applied move, as the Mirror read it."""

    player: int
    name: str
    frm: str
    along: str
    dest: str
    king: bool  # the moving piece was a king before it moved
    taken: tuple[int, bool] | None  # the jumped piece
    crowned: bool
    continues: bool  # the same piece must jump again
    quiet: int  # the game's forty-move count after the move


@dataclass
class Mirror:
    """An independent model of the position, authored from the federation's
    rules: the piece on each square (its seat and whether it is a king), the
    seat to move, the square of a piece that must jump again, and the
    forty-move count. It supplies the mover the mapping needs and its own
    legal set."""

    board: dict[str, tuple[int, bool]] = field(default_factory=initial_board)
    player: int = 0
    chain: str | None = None
    quiet: int = 0
    winner: int | None = None
    plies: list[Ply] = field(default_factory=list)
    dir_index: Callable[[str, int], int] = oracle_dir  # a seam the tripwires mis-set
    move_types: dict[str, int] = field(default_factory=lambda: dict(MOVE_TYPES))

    def copy(self) -> Mirror:
        return Mirror(
            board=dict(self.board), player=self.player, chain=self.chain,
            quiet=self.quiet, winner=self.winner, plies=list(self.plies),
            dir_index=self.dir_index, move_types=self.move_types,
        )

    def _may_go(self, cell: str, along: str) -> bool:
        return is_forward(along) or self.board[cell][1]

    def _step(self, cell: str, along: str, player: int) -> bool:
        if self.board.get(cell, (None, False))[0] != player or not self._may_go(cell, along):
            return False
        dest = beyond(cell, along, player)
        return dest is not None and dest not in self.board

    def _jump(self, cell: str, along: str, player: int) -> bool:
        if self.board.get(cell, (None, False))[0] != player or not self._may_go(cell, along):
            return False
        over, dest = beyond(cell, along, player), beyond(cell, along, player, 2)
        return (
            over is not None and dest is not None
            and self.board.get(over, (player, False))[0] == 1 - player
            and dest not in self.board
        )

    def jumps(self, player: int, cells: Sequence[str] = CELLS) -> list[Move]:
        return [
            ("jump", (c, d)) for c in cells for d in DIRECTIONS if self._jump(c, d, player)
        ]

    def steps(self, player: int) -> list[Move]:
        return [
            ("step", (c, d)) for c in CELLS for d in DIRECTIONS if self._step(c, d, player)
        ]

    def legal(self) -> list[Move]:
        """The mover's legal moves: the chained piece's jumps mid-capture,
        else every jump, else every step."""
        if self.chain is not None:
            return self.jumps(self.player, (self.chain,))
        return self.jumps(self.player) or self.steps(self.player)

    def to_native(self, decoded: Any) -> int:
        name, (cell, along) = decoded
        row, col = divmod(oracle_square(cell), SIZE)
        return (
            ((row * SIZE + col) * len(DIRECTIONS) + self.dir_index(along, self.player)) * 2
            + self.move_types[name]
        )

    def apply(self, player: int, decoded: Any) -> Ply:
        assert self.winner is None, f"the game is over ({self.fen()})"
        assert player == self.player, (
            f"the walker reports P{player} moving; the Mirror expects P{self.player} "
            f"({self.fen()})"
        )
        name, (cell, along) = decoded
        assert (name, (cell, along)) in self.legal(), (
            f"{name}({cell}, {along}) is not legal for P{player} ({self.fen()})"
        )
        owner, king = self.board.pop(cell)
        taken: tuple[int, bool] | None = None
        if name == "jump":
            over, dest = beyond(cell, along, player), beyond(cell, along, player, 2)
            assert over is not None and dest is not None
            taken = self.board.pop(over)
        else:
            stepped = beyond(cell, along, player)
            assert stepped is not None
            dest = stepped
        crowned = not king and int(dest[1:]) == far_rank(player)
        self.board[dest] = (owner, king or crowned)
        self.quiet = 0 if (taken is not None or not king) else self.quiet + 1
        continues = taken is not None and not crowned and bool(self.jumps(player, (dest,)))
        self.chain = dest if continues else None
        if not continues:
            self.player = 1 - player
            if not self.legal():
                self.winner = player
        ply = Ply(player, name, cell, along, dest, king, taken, crowned, continues, self.quiet)
        self.plies.append(ply)
        return ply

    def pieces(self, player: int) -> int:
        return sum(1 for owner, _ in self.board.values() if owner == player)

    def fen(self) -> str:
        """The position on one line, rank 8 first: r/w a man, R/W a king."""
        def glyph(cell: str) -> str:
            if cell not in self.board:
                return "."
            owner, king = self.board[cell]
            return ("RW" if king else "rw")[owner]

        return "/".join(
            "".join(glyph(f"{f}{r}") for f in FILES) for r in range(SIZE, 0, -1)
        )


def oracle_forty(native: Any) -> bool:
    """The oracle's draw: forty plies in a row in its own history with no
    capture, a capture being the move type bit of an action id."""
    quiet = 0
    for action in reversed(native.history()):
        if action % 2 == MOVE_TYPES["jump"]:
            break
        quiet += 1
    return quiet >= ORACLE_FORTY


class _Stopped(Exception):
    """The chooser stopped the line at a live node."""


@dataclass
class Line:
    """How one paired line ended, and the Mirror that followed it."""

    label: str
    mirror: Mirror
    end: LineEnd | None = None  # None: the chooser stopped the line at a live node
    history: list[int] = field(default_factory=list)
    offers: list[list[Move]] = field(default_factory=list)
    nodes: list[Mirror] = field(default_factory=list)  # the position at each decision


Steer = Callable[[list[Move], Mirror], Move]


def paired_line(
    steer: Steer,
    *,
    label: str,
    mirror: Mirror | None = None,
    truncate_when: Callable[[Any], bool] = oracle_forty,
) -> Line:
    """One line of `walk_paired_prefix`, the oracle's forty its truncation,
    `steer` choosing among the decoded offer with the Mirror in hand. A line
    the rules end ends on both sides on the same outcome, the one the Mirror
    reached."""
    line = Line(label, mirror if mirror is not None else Mirror())

    def advance(player: int, decoded: Any) -> None:
        line.mirror.apply(player, decoded)

    def choose(legal: list[int], space: ActionSpace) -> int:
        offer = [space.decode(a) for a in legal]
        assert sorted(offer) == sorted(line.mirror.legal()), (
            f"{label} step {len(line.history)}: the game offers {sorted(offer)}, the "
            f"Mirror {sorted(line.mirror.legal())} ({line.mirror.fen()})"
        )
        line.offers.append(offer)
        line.nodes.append(line.mirror.copy())
        action = space.encode(steer(offer, line.mirror))
        line.history.append(action)
        return action

    try:
        line.end = walk_paired_prefix(
            PATH, NATIVE, line.mirror.to_native, truncate_when, 0, choose,
            label=label, advance=advance,
        )
    except _Stopped:
        return line
    if isinstance(line.end, Rules):
        assert line.mirror.winner is not None, f"{label}: the Mirror's game is not over"
        expected = (1.0, -1.0) if line.mirror.winner == 0 else (-1.0, 1.0)
        assert line.end.ours == line.end.native == expected, (
            f"{label} step {line.end.ply}: ours {list(line.end.ours)}, native "
            f"{list(line.end.native)}, the Mirror's winner P{line.mirror.winner}"
        )
    return line


def notation(move: Move, player: int) -> str:
    """A move in from-to notation: `c3-d4` a step, `c3xe5` one hop of a jump."""
    name, (cell, along) = move
    hops = 2 if name == "jump" else 1
    return f"{cell}{'x' if name == 'jump' else '-'}{beyond(cell, along, player, hops)}"


def scripted_then(script: Sequence[str], seed: int | None) -> Steer:
    """Play `script` move by move, then a seeded uniform policy, or stop the
    line at a live node when `seed` is None."""
    steps: Iterator[str] = iter(script)
    rng = random.Random(seed)

    def steer(offer: list[Move], mirror: Mirror) -> Move:
        want = next(steps, None)
        if want is None:
            if seed is None:
                raise _Stopped
            return rng.choice(offer)
        hits = [m for m in offer if notation(m, mirror.player) == want]
        assert len(hits) == 1, (
            f"scripted {want!r} matches {hits} in {sorted(offer)} ({mirror.fen()})"
        )
        return hits[0]

    return steer


def uniform_steer(seed: int) -> Steer:
    """The seeded uniform policy over the offer, the walker's `uniform` by
    another door: both draw `choice` over the same ordered list."""
    rng = random.Random(seed)
    return lambda offer, mirror: rng.choice(offer)


def _safe(mirror: Mirror, move: Move) -> bool:
    """After `move`, the opponent has no capture."""
    after = mirror.copy()
    after.apply(mirror.player, move)
    return after.player == mirror.player or not after.jumps(after.player)


def shuffle_steer(seed: int, reset_at: int = QUIET_DRAW - 1) -> Steer:
    """The king-shuffling steer: uniform play until both sides hold a king,
    then each side moves a king where it leaves the opponent no capture, so
    the forty-move count climbs; once, at `reset_at` quiet plies, a man's
    step leaving no capture is played instead, starting the count again.
    Steering only: every move it picks is one the walk compares."""
    rng = random.Random(seed)
    reset = [False]

    def steer(offer: list[Move], mirror: Mirror) -> Move:
        kings = {owner for owner, king in mirror.board.values() if king}
        if kings != {0, 1} or offer[0][0] == "jump":
            return rng.choice(offer)
        by_kind = {
            king: [m for m in offer if mirror.board[m[1][0]][1] is king and _safe(mirror, m)]
            for king in (False, True)
        }
        if mirror.quiet == reset_at and not reset[0] and by_kind[False]:
            reset[0] = True
            return rng.choice(by_kind[False])
        return rng.choice(by_kind[True] or by_kind[False] or offer)

    return steer


def _dfs(
    space: Any, native: Any, mirror: Mirror, history: list[int], depth: int, max_depth: int
) -> int:
    ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, DecisionNode), f"prefix walk: unexpected terminal at depth {depth}"
    assert ours.player == mirror.player
    assert sorted(space.decode(a) for a in ours.legal) == sorted(mirror.legal())
    assert_node_agrees(
        native, ours, mirror.to_native, space,
        label="prefix walk", step=depth, history=[mirror.fen()],
    )
    if depth == max_depth:
        return 1
    visited = 1
    for action in ours.legal:
        decoded = space.decode(action)
        child = mirror.copy()
        nid = mirror.to_native(decoded)
        child.apply(mirror.player, decoded)
        visited += _dfs(space, native.child(nid), child, history + [action], depth + 1, max_depth)
    return visited


# The lines below were found offline by uniform play over the Mirror, each the
# shortest prefix that reaches its rule's branch; the tests assert the branch.
PREFIX_DEPTH = 3
POLICY_SEEDS: tuple[int, ...] = tuple(range(12))
DRAW_SEED = 30  # `shuffle_steer`'s seed for the forty-move draw
TRUNCATING_SEED = 2  # a policy seed the oracle's forty ends

# White's b6 jumps c5 and then e3, Red's d4 open to another White jump.
DOUBLE_JUMP: tuple[str, ...] = ("e3-d4", "h6-g5", "f2-e3", "g5-h4", "d4-c5", "b6xd4", "d4xf2")

# White's king, crowned on c1, jumps three times, the first hop backward.
TRIPLE_JUMP: tuple[str, ...] = (
    "c3-d4", "f6-e5", "d4xf6", "g7xe5", "b2-c3", "h6-g5", "a3-b4", "b6-c5",
    "c1-b2", "c5xa3", "a3xc1", "c3-b4", "h8-g7", "e3-d4", "c1xe3", "e3xc5",
    "c5xa3",
)

# Red's man jumps onto f8 and is crowned there; the new king has a jump open
# at once, and the move ends instead.
CROWNING_JUMP: tuple[str, ...] = (
    "a3-b4", "h6-g5", "g3-f4", "d6-c5", "b4xd6", "e7xc5", "f4xh6", "f8-e7", "h6xf8",
)

# Red's man is crowned on h8 by a double jump, and the king steps back to g7.
KING_STEPS_BACK: tuple[str, ...] = (
    "g3-h4", "f6-g5", "h4xf6", "g7xe5", "e3-d4", "h8-g7", "d4xf6", "f6xh8",
    "b6-c5", "h8-g7",
)

# White's man is crowned on c1 by a jump, and the king jumps back over d2.
KING_JUMPS_BACK: tuple[str, ...] = (
    "e3-d4", "h6-g5", "d2-e3", "b6-a5", "e3-f4", "g5xe3", "c1-d2", "e3xc1",
    "e1-d2", "c1xe3",
)

# A step that leaves the other side, still holding pieces, with no legal move;
# each script with the seat that wins.
BLOCKADES: dict[str, tuple[tuple[str, ...], int]] = {
    "red wins": ((
        "a3-b4", "f6-e5", "g3-f4", "e5xg3", "h2xf4", "d6-c5", "b4xd6", "e7xc5",
        "e3-d4", "c5xe3", "f2xd4", "h6-g5", "f4xh6", "f8-e7", "h6xf8", "b6-c5",
        "d4xb6", "c7xa5", "f8xd6", "b8-c7", "d6xb8", "d8-e7", "b8-c7", "a7-b6",
        "c7-d8", "h8-g7", "d8xf6", "f6xh8", "b6-c5", "g1-h2", "a5-b4", "c3xa5",
        "c5-b4", "d2-e3", "b4-a3", "e1-d2",
    ), 0),
    "white wins": ((
        "e3-f4", "f6-e5", "f4-g5", "h6xf4", "c3-b4", "d6-c5", "b4xd6", "e7xc5",
        "d2-e3", "f4xd2", "c1xe3", "c7-d6", "g3-h4", "d8-c7", "a3-b4", "c5xa3",
        "a3xc1", "a1-b2", "c1xa3", "e3-d4", "e5xc3", "e1-d2", "c3xe1", "h4-g5",
        "e1xg3", "h2xf4", "b6-c5", "g1-f2", "a3-b2", "f4-e5", "d6xf4", "f2-e3",
        "f4xd2", "g5-h6", "d2-e1",
    ), 1),
}


def _chains(line: Line) -> list[list[int]]:
    """The node indices of each move of two or more hops: the node of its
    first hop, then one per continuation."""
    moves: list[list[int]] = []
    current: list[int] = []
    for i, node in enumerate(line.nodes):
        if node.chain is not None:
            current.append(i)
            continue
        if len(current) > 1:
            moves.append(current)
        current = [i]
    if len(current) > 1:
        moves.append(current)
    return moves


def _played(line: Line, script: Sequence[str]) -> list[Ply]:
    plies = line.mirror.plies
    assert len(plies) >= len(script), f"{line.label}: the line stopped inside its script"
    return plies[: len(script)]


def test_mapping_anchors_against_native() -> None:
    """The square and direction tables are the board's and the oracle's: the
    cells and every step are `draughts(8, 8)`'s, the squares biject onto the
    oracle's dark squares and its opening men, each seat's four directions
    are the offset-matched ones, and every ply of every scripted line, played
    into a fresh oracle alone, is a legal oracle id whose rendering is the
    ply's own squares."""
    entry = board_entry("draughts", (8, 8))
    assert tuple(entry.cells) == CELLS
    for cell in CELLS:
        for along in DIRECTIONS:
            for player in (0, 1):
                assert entry.neighbor(cell, along, player) == beyond(cell, along, player)
    assert {d for d in DIRECTIONS if is_forward(d)} == {
        d for d in DIRECTIONS if entry.is_forward(d)
    }

    game = pyspiel.load_game(NATIVE)
    rendering = str(game.new_initial_state()).splitlines()
    dark = {r * SIZE + c for r in range(SIZE) for c in range(SIZE) if (r + c) % 2 == 1}
    assert {oracle_square(c) for c in CELLS} == dark
    men = {
        f"{FILES[c]}{SIZE - r}": rendering[r][1 + c]
        for r in range(SIZE) for c in range(SIZE) if (r + c) % 2 == 1
    }
    for seat, glyph in ((0, "o"), (1, "+")):
        assert {c for c, g in men.items() if g == glyph} == {
            c for c, (owner, _) in initial_board().items() if owner == seat
        }

    assert {d: oracle_dir(d, 0) for d in DIRECTIONS} == {
        "ahead_left": 0, "ahead_right": 1, "back_left": 3, "back_right": 2,
    }
    assert {d: oracle_dir(d, 1) for d in DIRECTIONS} == {
        "ahead_left": 2, "ahead_right": 3, "back_left": 1, "back_right": 0,
    }

    scripts = [DOUBLE_JUMP, TRIPLE_JUMP, CROWNING_JUMP, KING_STEPS_BACK, KING_JUMPS_BACK]
    scripts += [script for script, _ in BLOCKADES.values()]
    kinds: set[tuple[str, bool, bool]] = set()
    for script in scripts:
        native = game.new_initial_state()
        mirror = Mirror()
        for want in script:
            move = next(m for m in mirror.legal() if notation(m, mirror.player) == want)
            nid = mirror.to_native(move)
            assert nid in native.legal_actions(), f"{want}: oracle id {nid} is not legal"
            rendered = native.action_to_string(mirror.player, nid)
            assert rendered == want.replace("-", "").replace("x", ""), (want, rendered)
            assert nid % 2 == MOVE_TYPES[move[0]]
            kinds.add((move[0], mirror.board[move[1][0]][1], is_forward(move[1][1])))
            native.apply_action(nid)
            mirror.apply(mirror.player, move)
    assert {("step", False, True), ("jump", False, True), ("step", True, False),
            ("jump", True, False)} <= kinds


def test_exhaustive_prefix_walk() -> None:
    """Layer (a): every prefix of the opening array to `PREFIX_DEPTH` poses the
    same mapped legal set in the paused adapter, natively and in the Mirror."""
    _, space = load(PATH)
    native = pyspiel.load_game(NATIVE).new_initial_state()
    visited = _dfs(space, native, Mirror(), [], 0, PREFIX_DEPTH)
    frontier = [native]
    expected = 0
    for _ in range(PREFIX_DEPTH + 1):
        expected += len(frontier)
        frontier = [s.child(a) for s in frontier for a in s.legal_actions()]
    assert visited == expected, f"the prefix tree has {expected} nodes, walked {visited}"


@pytest.mark.parametrize(
    ("script", "hops", "jumper"),
    [(DOUBLE_JUMP, 2, "b6"), (TRIPLE_JUMP, 3, "c1")],
    ids=["double", "triple"],
)
def test_scripted_multiple_jump_moves_the_jumping_piece_alone(
    script: tuple[str, ...], hops: int, jumper: str
) -> None:
    """A move of several hops: at every continuation the game and the oracle
    offer the jumping piece's jumps alone, at one of them while another piece
    of the same side has a jump open, the same seat moving until the chain
    ends."""
    line = paired_line(scripted_then(script, None), label=f"{hops} hops")
    plies = _played(line, script)
    chain = _chains(line)[-1]
    assert len(chain) == hops, f"the last chained move has {len(chain)} hops"
    assert plies[chain[0]].frm == jumper
    assert {plies[i].player for i in chain} == {plies[chain[0]].player}
    for i in chain[1:]:
        assert {m[1][0] for m in line.offers[i]} == {line.nodes[i].chain}
    assert any(
        j[1][0] != node.chain
        for node in (line.nodes[i] for i in chain[1:])
        for j in node.jumps(node.player)
    ), f"{line.label}: no other piece had a jump open at a continuation"
    assert not plies[chain[-1]].continues
    assert line.nodes[-1].player != plies[chain[-1]].player


def test_scripted_crowning_jump_ends_the_move() -> None:
    """A man crowned by a jump with a further jump open to the new king: the
    move ends there on both sides, and the other seat moves next."""
    line = paired_line(scripted_then(CROWNING_JUMP, None), label="crowning jump")
    crown = _played(line, CROWNING_JUMP)[-1]
    assert crown.name == "jump" and crown.crowned and not crown.continues
    after = line.mirror.copy()
    after.player, after.chain = crown.player, None
    assert after.jumps(crown.player, (crown.dest,)), "the new king has no jump open"
    assert line.nodes[-1].player == 1 - crown.player


@pytest.mark.parametrize(
    ("script", "kind"), [(KING_STEPS_BACK, "step"), (KING_JUMPS_BACK, "jump")], ids=["step", "jump"],
)
def test_scripted_king_moves_backward(script: tuple[str, ...], kind: str) -> None:
    """A king's backward step and backward capture agree on both sides."""
    line = paired_line(scripted_then(script, None), label=f"king {kind}s back")
    last = _played(line, script)[-1]
    assert last.name == kind and last.king and not is_forward(last.along)


@pytest.mark.parametrize("name", sorted(BLOCKADES))
def test_scripted_blockade(name: str) -> None:
    """A step leaves the other side with pieces on the board and no legal
    move, and the stepping side wins on both sides."""
    script, winner = BLOCKADES[name]
    line = paired_line(scripted_then(script, 0), label=f"blockade, {name}")
    assert isinstance(line.end, Rules) and line.end.ply == len(script)
    assert line.mirror.winner == winner
    assert line.mirror.plies[-1].name == "step"
    assert line.mirror.pieces(1 - winner) > 0


def test_random_trajectories_agree_with_native() -> None:
    """Layer (c): the seeded policies agree at every node, and the tally holds
    both winners and a truncation; no line the rules end is a draw, since the
    oracle's forty falls before the game's eighty."""
    ends: list[LineEnd] = []
    for seed in POLICY_SEEDS:
        line = paired_line(uniform_steer(seed), label=f"policy {seed}")
        assert line.end is not None
        ends.append(line.end)
    tally = tally_line_ends(ends)
    assert tally["p0"] and tally["p1"] and tally["truncated"], dict(tally)
    assert "draw" not in tally


def test_forty_move_draw_on_the_game_alone() -> None:
    """Layer (d): the king shuffle is compared until the oracle's forty ends
    it, and then plays on in the game alone, the count read off the live game
    at every ply and held equal to the Mirror's: it reaches seventy-nine, a
    man's step starts it again, and eighty quiet plies later the game is a
    tie by its rules."""
    paired = paired_line(shuffle_steer(DRAW_SEED), label="draw")
    assert isinstance(paired.end, Truncated)

    mirror = Mirror()
    steer = shuffle_steer(DRAW_SEED)
    _, space = load(PATH)
    world: list[Any] = []
    counts: list[int] = []

    def beyond_history(player: int, legal: list[int]) -> int:
        assert int(world[0].get("quiet")) == mirror.quiet, f"ply {len(counts)}"
        counts.append(mirror.quiet)
        offer = [space.decode(a) for a in legal]
        assert player == mirror.player and sorted(offer) == sorted(mirror.legal())
        move = steer(offer, mirror)
        mirror.apply(player, move)
        return space.encode(move)

    end = run(PATH, 0, (), on_first_decision=world.append, beyond=beyond_history)
    assert not isinstance(end, DecisionNode)
    assert end.returns == [0.0, 0.0] and end.ended_by is EndedBy.RULES, end
    counts.append(mirror.quiet)  # the last ply's count, which only a tie at eighty ends on
    assert counts[-1] == QUIET_DRAW and mirror.winner is None
    reset = counts.index(QUIET_DRAW - 1) + 1
    assert mirror.plies[reset - 1].name == "step" and not mirror.plies[reset - 1].king, (
        "the count starts again on a man's step"
    )
    assert counts[reset:] == list(range(QUIET_DRAW + 1))
    assert len(paired.history) < len(counts) - 1, "the oracle's forty fell before the tie"


def test_seat_zero_frame_is_a_tripwire() -> None:
    """The comparison FAILS when seat 1's directions are read in seat 0's
    frame: White's first offer maps onto moves the oracle does not offer."""
    with pytest.raises(AssertionError, match="step 1: legal actions diverge"):
        paired_line(
            scripted_then(DOUBLE_JUMP, None), label="seat 0 frame",
            mirror=Mirror(dir_index=seat_zero_dir),
        )


def test_exchanged_move_types_are_a_tripwire() -> None:
    """The comparison FAILS when a step is mapped as a capture."""
    with pytest.raises(AssertionError, match="step 0: legal actions diverge"):
        paired_line(
            scripted_then(DOUBLE_JUMP, None), label="move types",
            mirror=Mirror(move_types={"step": 1, "jump": 0}),
        )


def test_truncation_predicate_is_load_bearing() -> None:
    """The walk FAILS when nothing names the oracle's forty: the oracle ends a
    truncating policy line while the game still offers a decision.

    red under: the walker treating every terminal oracle at one of our
    decisions as a truncation, without asking `truncate_when`."""
    with pytest.raises(
        AssertionError, match="native is already terminal while our game still offers a decision"
    ):
        paired_line(uniform_steer(TRUNCATING_SEED), label="no forty", truncate_when=lambda native: False)
