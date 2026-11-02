"""Random-playout harness for Hex — the board-topology connection rung.

The corpus's first game won by a chain rather than a line or a row, and its
first whose `max_length` is a fact of its board: one stone per pick, 121
cells. Perfect information, no shuffle, so a fixed seed is fully
deterministic. Checked at EVERY decision point of a playout, and once more
against the terminal board:

- strict alternation — seats fire 0, 1, 0, 1, ... from black, seat 0;
- the offer is exactly the empty cells, in the board's cell order, one
  `place(at)` per empty cell (the `when: tile[at] is empty` guard, read off
  the offer);
- conservation — the 121 stones are always split across the two reserves and
  the tiles, each side's count its own;
- at most 121 decisions, one stone per decision;
- no side has joined its edges while the game still offers a decision: a
  chain completed and not detected would let play run on past the win;
- the terminal `result` is (+1,-1) or (-1,+1) and never (0,0), the line ended
  by its rules and not by its length, and the winner's stones join the
  winner's two edges while the loser's do not.

"Joined" is decided here by an INDEPENDENT flood fill (`_joined`) over this
module's own six offsets, written from the rules, never read from the board
registry: the in-test oracle for the `connected` Builtin at game level.

Plus the length facts. `max_length: 121` is the board's bound, so the
declaration is asserted EQUAL to the cell count `hex_rhombus(11)` declares;
and a line that fills the board ends by its rules at the 121st placement,
witnessed by the manifest's full-board seeds. Measured 2026-11-01 under the
uniform policy over seeds 0-299: lines of 70 to 121 plies (median 108), 14 of
them filling the board, 160 black wins to 140 white.

And determinism: a shuffle-free game replays byte-identically from a seed, so
the same seed yields the same final board across two in-process runs, and one
seed's board is pinned.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   every decision of every manifest line offers exactly the empty
            cells to the seat whose turn it is, conserves the 121 stones,
            and comes before either side has joined its edges; every line
            ends by its rules within 121 decisions with a winner whose
            stones join its edges and a loser whose stones do not.
domain:     the uniform-random lines of seeds `range(SEEDS)`, which hold the
            full-board lines `FULL_BOARD`; the declared `max_length`.
registry:   board: cardlang/stdlib/boards.py::BOARD_FAMILIES `hex_rhombus`;
            pieces: cardlang/runtime/values.py::COMPONENT_SETS `hex_stones`.
held by:    `max_length` is the board's bound, Derived and Pinned: the bound
            is derived here from `board_entry("hex_rhombus", (11,)).cells`
            and the declaration asserted equal to it; not higher, because
            `max_length` is a designer-written literal with no derived
            spelling. The playout invariants are Born-Green Pins, each red
            under the plant named below; not higher, because they are
            execution evidence over a line, which no type holds.
does not prove:  that the adjacency is OpenSpiel's: the flood fill reads this
            module's offsets, and tests/test_differential_hex.py compares the
            game against the oracle's own.

red under (guard): delete `when: tile[at] is empty` from hex.cardlang; the
offer stops being the empty cells at the second decision.
red under (win): delete the `if connected(...)` block from hex.cardlang; a
joined side is still offered a decision, and a full board leaves an offer
with no legal placement.
red under (adjacency): `(1, 1)` in place of `(1, -1)` in
`boards._HEX_FORWARD_OFFSETS`; the game declares a win the flood fill does
not see, or misses one it does.
red under (bound): declare `max_length: 120`; the full-board seeds stop by
length at the 120th placement.
"""

from __future__ import annotations

import random
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.stdlib.boards import board_entry

HEX = Path(__file__).parent.parent / "docs" / "games" / "hex.cardlang"

SIZE = 11
FILES = "abcdefghijk"
# The 121 cells in the board's declared member order (row-major from a1).
CELLS = tuple(f"{f}{r}" for r in range(1, SIZE + 1) for f in FILES)

SIDE = ("black", "white")  # seat -> the side it plays (`side_of` in the game)
STONES = (61, 60)  # seat -> the stones it holds before the first placement

# The six neighbours of a hexagon as (file, rank) offsets: along its rank,
# along its file, and the diagonal running up to the left and down to the right.
NEIGHBOUR_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1), (-1, 1), (1, -1))

LEGAL_OUTCOMES = {(1, -1), (-1, 1)}  # never (0, 0): Hex has no draw

SEEDS = 40
# The manifest's lines that fill the board (measured 2026-11-01).
FULL_BOARD = (4, 34)

Board = dict[str, "str | None"]


def _game() -> n.Game:
    return check_source(HEX)


def test_hex_checks_clean() -> None:
    _game()  # parse -> resolve -> typecheck -> capacity; must not raise


def _coords(cell: str) -> tuple[int, int]:
    return FILES.index(cell[0]), int(cell[1:])


def _name(file_: int, rank: int) -> str:
    return f"{FILES[file_]}{rank}"


def _on_near_edge(seat: int, cell: str) -> bool:
    file_, rank = _coords(cell)
    return rank == 1 if seat == 0 else file_ == 0


def _on_far_edge(seat: int, cell: str) -> bool:
    file_, rank = _coords(cell)
    return rank == SIZE if seat == 0 else file_ == SIZE - 1


def _joined(board: Board, seat: int) -> bool:
    """Whether `seat`'s stones join its two edges: a flood fill from its near
    edge through its own stones, over this module's six offsets."""
    side = SIDE[seat]
    frontier = [c for c in CELLS if board[c] == side and _on_near_edge(seat, c)]
    seen = set(frontier)
    while frontier:
        cell = frontier.pop()
        if _on_far_edge(seat, cell):
            return True
        file_, rank = _coords(cell)
        for df, dr in NEIGHBOUR_OFFSETS:
            f2, r2 = file_ + df, rank + dr
            if 0 <= f2 < SIZE and 1 <= r2 <= SIZE:
                nb = _name(f2, r2)
                if nb not in seen and board[nb] == side:
                    seen.add(nb)
                    frontier.append(nb)
    return False


def _board(rs: RuntimeState) -> Board:
    return {
        c: (cards[0].suit if (cards := rs.zones.instance("tile", c).cards) else None)
        for c in CELLS
    }


def _reserves(rs: RuntimeState) -> tuple[int, int]:
    return (
        len(rs.zones.instance("reserve", 0).cards),
        len(rs.zones.instance("reserve", 1).cards),
    )


def _check_counts(board: Board, reserves: tuple[int, int]) -> None:
    for seat in (0, 1):
        placed = sum(1 for v in board.values() if v == SIDE[seat])
        assert placed + reserves[seat] == STONES[seat], (
            f"seat {seat}: {placed} on the board + {reserves[seat]} in reserve "
            f"is not its {STONES[seat]} stones"
        )


class Playout:
    """One finished playout's evidence: the terminal result and board, and its
    length."""

    def __init__(self, result: Any, board: Board, plies: int) -> None:
        self.result = result
        self.board = board
        self.plies = plies

    @property
    def winner(self) -> int:
        return 0 if self.result.scores[0] == 1 else 1


def _playout(seed: int) -> Playout:
    """Drive one uniform-random playout, asserting the per-decision invariants
    as it goes."""
    game = _game()
    rng = random.Random(seed)
    rs_ref: dict[str, RuntimeState] = {}
    seats: list[int] = []

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        rs = rs_ref["rs"]
        board, reserves = _board(rs), _reserves(rs)
        assert k == 1, f"Hex offers one move; got k={k}"
        assert len(seats) < len(CELLS), "a decision past the 121st placement"
        expected_seat = 0 if not seats else 1 - seats[-1]
        assert player == expected_seat, f"turn order broke: seat {player} after {seats[-1:]}"
        seats.append(player)
        _check_counts(board, reserves)
        offer = [("place", c) for c in CELLS if board[c] is None]
        assert list(candidates) == offer, (
            f"seat {player} was offered {len(candidates)} placements, not the "
            f"{len(offer)} empty cells in board order"
        )
        for seat in (0, 1):
            assert not _joined(board, seat), (
                f"seat {seat} has joined its edges, and decision {len(seats)} "
                f"is still offered"
            )
        return [rng.choice(candidates)]

    result = play_game(
        game,
        rng,
        chooser=chooser,
        on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
    )
    rs = rs_ref["rs"]
    final = _board(rs)
    _check_counts(final, _reserves(rs))
    assert sum(1 for v in final.values() if v is not None) == len(seats)
    assert result.ended_by.value == "rules", f"seed {seed}: the line ended by {result.ended_by}"
    outcome = (result.scores.get(0), result.scores.get(1))
    assert outcome in LEGAL_OUTCOMES, f"illegal terminal result {outcome}"
    assert result.loser is None
    playout = Playout(result, final, len(seats))
    assert _joined(final, playout.winner), (
        f"seed {seed}: seat {playout.winner} won without joining its edges"
    )
    assert not _joined(final, 1 - playout.winner), (
        f"seed {seed}: seat {1 - playout.winner} lost with its edges joined"
    )
    return playout


@cache
def _run(seed: int) -> Playout:
    return _playout(seed)


def test_max_length_is_the_board_cell_count() -> None:
    """`max_length: 121` is the board's own bound: one stone per pick and one
    cell per stone. The bound is read off the board the game declares, and the
    declaration must EQUAL it — neither a headroom multiple nor a cut."""
    game = _game()
    cells = board_entry("hex_rhombus", (SIZE,)).cells
    assert cells == CELLS, "this module's cell names are not the board's"
    assert game.max_length == len(cells) == 121


@pytest.mark.parametrize("seed", range(SEEDS))
def test_hex_playout_invariants(seed: int) -> None:
    _run(seed)


def test_both_winners_arise_under_random_play() -> None:
    """Not vacuous: random play produces black wins AND white wins, so the
    invariant suite exercises both branches of the zero-sum result."""
    tally = Counter(_run(seed).winner for seed in range(SEEDS))
    assert tally[0] > 0 and tally[1] > 0, f"random play covered one side only: {dict(tally)}"


def test_a_full_board_line_ends_by_its_rules_at_the_121st_placement() -> None:
    """The hex theorem at game level: a line that fills the board is decided
    by its last stone, and it ends by its rules rather than by its length,
    though its length equals `max_length`."""
    for seed in FULL_BOARD:
        run = _run(seed)
        assert run.plies == len(CELLS), f"seed {seed} no longer fills the board ({run.plies})"
        assert all(v is not None for v in run.board.values())
        assert run.result.ended_by.value == "rules"


def test_a_fixed_seed_is_deterministic_across_runs() -> None:
    """Perfect information + no shuffle: the same seed yields the same final
    board twice. The candidate list is ordered by the board's declared cell
    order, so this holds independent of PYTHONHASHSEED."""
    first, second = _playout(7), _playout(7)
    assert (first.board, first.plies) == (second.board, second.plies)


def _render(board: Board) -> tuple[str, ...]:
    """The board rank by rank from rank 11 down: `b` black, `w` white, `.`
    empty, file `a` first."""
    mark = {None: ".", "black": "b", "white": "w"}
    return tuple(
        "".join(mark[board[_name(f, r)]] for f in range(SIZE)) for r in range(SIZE, 0, -1)
    )


def test_a_fixed_seed_pins_a_known_board() -> None:
    """Characterization: seed 7's terminal board. Pinning the exact layout
    catches an accidental change to the candidate ordering or the rng stream."""
    run = _run(7)
    assert (run.result.scores[0], run.result.scores[1], run.plies) == KNOWN_SEED_7[0]
    assert _render(run.board) == KNOWN_SEED_7[1]


KNOWN_SEED_7: tuple[tuple[int, int, int], tuple[str, ...]] = (
    (1, -1, 115),
    (
        "bbbbw.bbwbb",
        "bwwwbwwwbbw",
        "bwwwbwbbwww",
        "wbwbbbbbbww",
        "b.bwbwbwbbb",
        "bbwbwwbwwww",
        "wwwbwwbwbbw",
        ".wwwb.wwbbw",
        "w.bwwb.wbbw",
        "wbbbbwbbwwb",
        "bwbwbwbbwbw",
    ),
)
