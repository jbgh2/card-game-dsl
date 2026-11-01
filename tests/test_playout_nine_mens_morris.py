"""Random-playout harness for nine men's morris — the first corpus game on a
board that is not a grid, and the first whose turn holds two decisions.

The rules are recomputed here by an independent model — the board's geometry
written as coordinates, adjacency and the sixteen mills derived from it, never
read from the board registry — and checked at EVERY decision point of a
playout, and once more against the terminal position:

- the offered family is the phase's: `place` while the seat has a man in
  reserve, `slide` while it has more than three men, `fly` at three — and the
  offered set equals the model's set EXACTLY: every vacant point to place on,
  every (own man, adjacent vacant point) pair to slide, every (own man, vacant
  point) pair to fly;
- a removal is offered exactly when the move before it landed a man in a mill
  of its side, to the same seat, and its offered set equals the model's: the
  enemy men outside every mill, or every enemy man when all of them stand in
  one; every other decision alternates seats;
- `men_left[p]` equals `9 - |captured[p]|` at every decision — the
  Derived-and-Pinned holder of "the men a side has left", whose one writer is
  `remove`'s decrement beside its one movement to `captured` (a piece game
  has no count form over a zone to derive it from: issue #1017);
- conservation — the eighteen men are always split across the points, the
  reserves and the captured piles;
- the terminal result is (+1, -1) or (-1, +1), ended by the rules, and the
  terminus is one of the two: the loser reduced to two men, or the loser,
  on their turn, with men on the board and no legal move.

Both termini and all four move families are driven non-vacuously: reduction
and every family under uniform play, blockade under a policy that steers each
move toward leaving the opponent the fewest moves (uniform play reaches a
blockade in a few games in a thousand). The every-man-in-a-mill removal arm
and the two-mills-earn-one-removal rule are scripted placements, each asserting
the position it reaches before it asserts the rule.

The length fact. `max_length: 6000` is the bound a game ends at, not a rule:
morris has no move cap, and a line that cycles ends there by its Stop
Result, a tie. Measured 2026-11-01 under uniform play over seeds 0-299: every
game ended by its rules, median 161 decisions, longest 979; the faithful
Python model of the planning sitting (issue #977, 2026-10-25) measured 1270
at most over 2000 games. The bound keeps four times the longest line this
module plays (`test_random_play_never_approaches_the_declared_max_length`).

And determinism: a shuffle-free game replays identically from a seed.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

MORRIS = Path(__file__).parent.parent / "docs" / "games" / "nine-mens-morris.cardlang"

SIDE = ("white", "black")  # seat -> the side it plays (`side_of` in the game)
MEN = 9
TOTAL_MEN = 2 * MEN
LEGAL_OUTCOMES = {(1, -1), (-1, 1)}

# The board as geometry: each point at (file, rank) on the 7x7 lattice. Two
# points are adjacent when they share a file or a rank, no other point lies
# between them, and the segment does not cross the empty centre (d4).
_RINGS = {
    1: ("a1", "d1", "g1", "g4", "g7", "d7", "a7", "a4"),
    2: ("b2", "d2", "f2", "f4", "f6", "d6", "b6", "b4"),
    3: ("c3", "d3", "e3", "e4", "e5", "d5", "c5", "c4"),
}
POINTS: tuple[str, ...] = tuple(p for ring in _RINGS.values() for p in ring)


def _xy(point: str) -> tuple[int, int]:
    return "abcdefg".index(point[0]), int(point[1:]) - 1


def _adjacent(a: str, b: str) -> bool:
    (ax, ay), (bx, by) = _xy(a), _xy(b)
    if a == b or (ax != bx and ay != by):
        return False
    lo, hi = sorted((ay, by)) if ax == bx else sorted((ax, bx))
    between = [
        p
        for p in POINTS
        if (_xy(p)[0] == ax and lo < _xy(p)[1] < hi)
        if ax == bx
    ] + [
        p
        for p in POINTS
        if (_xy(p)[1] == ay and lo < _xy(p)[0] < hi)
        if ay == by
    ]
    crosses_centre = (ax == bx == 3 and lo < 3 < hi) or (ay == by == 3 and lo < 3 < hi)
    return not between and not crosses_centre


ADJ: dict[str, frozenset[str]] = {
    p: frozenset(q for q in POINTS if _adjacent(p, q)) for p in POINTS
}

# A mill: three points in a straight line, each joined to the next.
MILLS: frozenset[frozenset[str]] = frozenset(
    frozenset((a, b, c))
    for b in POINTS
    for a in ADJ[b]
    for c in ADJ[b]
    if a < c
    and (_xy(a)[0] == _xy(b)[0] == _xy(c)[0] or _xy(a)[1] == _xy(b)[1] == _xy(c)[1])
)

Board = dict[str, "str | None"]
Candidate = tuple[str, tuple[Any, ...]]


def test_the_model_board_is_the_mill_board() -> None:
    """The model's geometry yields the board the rules describe: twenty-four
    points, thirty-two lines between neighbours, sixteen mills, and every
    point of degree two, three or four."""
    assert len(POINTS) == 24
    assert sum(len(v) for v in ADJ.values()) == 2 * 32
    assert len(MILLS) == 16
    assert {len(v) for v in ADJ.values()} == {2, 3, 4}


# ---------------------------------------------------------------------------
# The rules model
# ---------------------------------------------------------------------------


def in_mill(board: Board, point: str) -> bool:
    side = board[point]
    return side is not None and any(
        point in mill and all(board[q] == side for q in mill) for mill in MILLS
    )


def removable(board: Board, actor: int) -> set[tuple[Any, ...]]:
    foe = SIDE[1 - actor]
    enemy = [p for p in POINTS if board[p] == foe]
    free = [p for p in enemy if not in_mill(board, p)]
    return {(p,) for p in (free or enemy)}


def moves(board: Board, player: int, reserve: int, men: int) -> tuple[str, set[tuple[Any, ...]]]:
    """The family the phase offers `player` and every move in it."""
    side = SIDE[player]
    empty = [p for p in POINTS if board[p] is None]
    if reserve:
        return "place", {(p,) for p in empty}
    own = [p for p in POINTS if board[p] == side]
    if men > 3:
        return "slide", {(f, t) for f in own for t in ADJ[f] if board[t] is None}
    return "fly", {(f, t) for f in own for t in empty}


def apply(board: Board, player: int, kind: str, args: tuple[Any, ...]) -> tuple[Board, str | None]:
    """The board after a move, and the point the man landed on."""
    after = dict(board)
    if kind == "place":
        after[args[0]] = SIDE[player]
        return after, args[0]
    if kind in ("slide", "fly"):
        after[args[0]], after[args[1]] = None, SIDE[player]
        return after, args[1]
    after[args[0]] = None
    return after, None


# ---------------------------------------------------------------------------
# Reading the runtime
# ---------------------------------------------------------------------------


def _game() -> n.Game:
    return check_source(MORRIS)


def test_nine_mens_morris_checks_clean() -> None:
    _game()  # parse -> resolve -> typecheck -> capacity; must not raise


def _board(rs: RuntimeState) -> Board:
    return {
        p: (cards[0].suit if (cards := rs.zones.instance("point", p).cards) else None)
        for p in POINTS
    }


def _args(candidate: Any) -> tuple[Any, ...]:
    """A candidate's arguments as a tuple: a one-parameter move's argument
    arrives bare."""
    args = candidate[1]
    return args if isinstance(args, tuple) else (args,)


def _count(rs: RuntimeState, zone: str, player: int) -> int:
    return len(rs.zones.instance(zone, player).cards)


@dataclass
class Position:
    board: Board
    reserve: tuple[int, int]
    captured: tuple[int, int]

    def men(self, player: int) -> int:
        return MEN - self.captured[player]

    def mobile(self, player: int) -> bool:
        return bool(moves(self.board, player, self.reserve[player], self.men(player))[1])


def _position(rs: RuntimeState) -> Position:
    return Position(
        _board(rs),
        (_count(rs, "reserve", 0), _count(rs, "reserve", 1)),
        (_count(rs, "captured", 0), _count(rs, "captured", 1)),
    )


def _men_left(rs: RuntimeState, player: int) -> int:
    value = rs.get("men_left")
    return int(value[player])


Policy = Callable[[int, list[Candidate], Position, random.Random], Candidate]


def uniform(player: int, candidates: list[Candidate], pos: Position, rng: random.Random) -> Candidate:
    return candidates[rng.randrange(len(candidates))]


def smothering(player: int, candidates: list[Candidate], pos: Position, rng: random.Random) -> Candidate:
    """Steer toward blockade: among the seat's moves, take one that leaves the
    opponent the fewest moves of their own; removals stay uniform. Steering
    only — every invariant is checked exactly as under uniform play."""
    if candidates[0][0] == "remove":
        return uniform(player, candidates, pos, rng)
    foe = 1 - player

    def foe_moves(c: Candidate) -> int:
        after, _ = apply(pos.board, player, c[0], c[1])
        return len(moves(after, foe, pos.reserve[foe], pos.men(foe))[1])

    scored = [(foe_moves(c), i) for i, c in enumerate(candidates)]
    least = min(s for s, _ in scored)
    return candidates[rng.choice([i for s, i in scored if s == least])]


@dataclass
class Playout:
    result: Any
    final: Position
    decisions: int
    terminus: str
    families: Counter[str] = field(default_factory=Counter)


def _playout(seed: int, policy: Policy = uniform) -> Playout:
    """Drive one playout under `policy`, asserting the per-decision invariants
    as it goes."""
    game = _game()
    assert game.max_length is not None
    cap = game.max_length
    rng = random.Random(seed)
    rs_ref: dict[str, RuntimeState] = {}
    families: Counter[str] = Counter()
    count = [0]
    # (seat, kind, landed-in-a-mill) of the decision before this one
    prev: list[tuple[int, str, bool] | None] = [None]

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        rs = rs_ref["rs"]
        pos = _position(rs)
        count[0] += 1
        assert count[0] <= cap, "the playout ran past the declared max_length"
        assert k == 1, f"morris offers one move at a time; got k={k}"
        on_board = sum(1 for v in pos.board.values() if v is not None)
        assert on_board + sum(pos.reserve) + sum(pos.captured) == TOTAL_MEN, (
            "the eighteen men were not conserved"
        )
        for p in (0, 1):
            assert _men_left(rs, p) == pos.men(p), (
                f"men_left[{p}] is {_men_left(rs, p)} with {pos.captured[p]} captured"
            )
        removal_due = prev[0] is not None and prev[0][2]
        if prev[0] is None:
            assert player == 0, "White does not move first"
        elif removal_due:
            assert player == prev[0][0], "the removal decision changed seat"
        else:
            assert player == 1 - prev[0][0], f"turn order broke: seat {player} after {prev[0][0]}"
        kinds = {c[0] for c in candidates}
        offered = {_args(c) for c in candidates}
        assert len(kinds) == 1, f"one decision offered several families: {kinds}"
        (kind,) = kinds
        if removal_due:
            assert kind == "remove", f"a closed mill was followed by {kind}, not a removal"
            expected = removable(pos.board, player)
        else:
            assert kind != "remove", "a removal was offered without a mill"
            want, expected = moves(pos.board, player, pos.reserve[player], pos.men(player))
            assert kind == want, (
                f"seat {player} with {pos.reserve[player]} in reserve and "
                f"{pos.men(player)} men was offered {kind}, not {want}"
            )
        assert offered == expected, (
            f"seat {player}'s {kind} offer differs from the rules\n"
            f"offered, not legal: {sorted(offered - expected)}\n"
            f"legal, not offered: {sorted(expected - offered)}"
        )
        choice = policy(player, [(c[0], _args(c)) for c in candidates], pos, rng)
        families[choice[0]] += 1
        after, landed = apply(pos.board, player, choice[0], choice[1])
        prev[0] = (player, choice[0], landed is not None and in_mill(after, landed))
        index = next(i for i, c in enumerate(candidates) if (c[0], _args(c)) == choice)
        return [candidates[index]]

    result = play_game(
        game,
        rng,
        chooser=chooser,
        on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
    )
    final = _position(rs_ref["rs"])
    outcome = (result.scores[0], result.scores[1])
    assert outcome in LEGAL_OUTCOMES, f"illegal terminal result {outcome}"
    assert getattr(result.ended_by, "value", None) == "rules", (
        f"seed {seed}: the line ended by {result.ended_by}, not by the rules"
    )
    winner = 0 if outcome == (1, -1) else 1
    loser = 1 - winner
    assert prev[0] is not None
    if final.men(loser) == 2:
        terminus = "reduction"
        assert prev[0][0] == winner and prev[0][1] == "remove", (
            "the loser fell to two men by something other than the winner's removal"
        )
    else:
        terminus = "blockade"
        assert final.men(loser) > 3 and not final.reserve[loser], (
            f"seat {loser} lost with {final.men(loser)} men and "
            f"{final.reserve[loser]} in reserve — neither terminus applies"
        )
        assert not final.mobile(loser), f"seat {loser} lost with a legal move left"
        assert prev[0][0] == winner and not (prev[0][1] != "remove" and prev[0][2]), (
            "the blocked seat lost on a turn that was not theirs"
        )
    return Playout(result, final, count[0], terminus, families)


RANDOM_SEEDS = 12
SMOTHER_SEEDS = 6


@cache
def _random_run(seed: int) -> Playout:
    return _playout(seed)


@cache
def _smother_run(seed: int) -> Playout:
    return _playout(seed, smothering)


@pytest.mark.parametrize("seed", range(RANDOM_SEEDS))
def test_nine_mens_morris_playout_invariants(seed: int) -> None:
    _random_run(seed)


@pytest.mark.parametrize("seed", range(SMOTHER_SEEDS))
def test_nine_mens_morris_smothering_playout_invariants(seed: int) -> None:
    _smother_run(seed)


def test_every_family_and_both_outcomes_arise_under_uniform_play() -> None:
    """Not vacuous: uniform play places, slides, flies and removes, and both
    seats win, so the invariants above have exercised every phase and both
    arms of the zero-sum result."""
    runs = [_random_run(seed) for seed in range(RANDOM_SEEDS)]
    families = sum((r.families for r in runs), Counter[str]())
    assert set(families) == {"place", "slide", "fly", "remove"}, dict(families)
    winners = Counter(r.result.scores[0] for r in runs)
    assert winners[1] and winners[-1], f"uniform play covered one side only: {dict(winners)}"


def test_the_reduction_terminus_fires_under_uniform_play() -> None:
    tally = Counter(_random_run(seed).terminus for seed in range(RANDOM_SEEDS))
    assert tally["reduction"], f"no game ended by reduction to two men: {dict(tally)}"


def test_the_blockade_terminus_fires_under_smothering_play() -> None:
    """The second terminus: a seat with men on the board and no legal move on
    its turn loses. Uniform play reaches it rarely, so this drives the
    smothering policy; the turn that ends the game decides nothing."""
    runs = [_smother_run(seed) for seed in range(SMOTHER_SEEDS)]
    tally = Counter(r.terminus for r in runs)
    assert tally["blockade"], f"smothering play never blocked a seat: {dict(tally)}"


def test_random_play_never_approaches_the_declared_max_length() -> None:
    """`max_length` is the bound a game ends at, not a rule; the declared cap
    stays four times above the longest line this module plays.

    red under: declare `max_length: 900` in nine-mens-morris.cardlang (the
    longest line here is under 900 decisions, so the playouts still end by the
    rules, and four times it is not)."""
    game = _game()
    assert game.max_length is not None
    longest = max(
        max(_random_run(seed).decisions for seed in range(RANDOM_SEEDS)),
        max(_smother_run(seed).decisions for seed in range(SMOTHER_SEEDS)),
    )
    assert longest * 4 < game.max_length, (
        f"the longest observed game ({longest} decisions) is within 4x of the "
        f"declared max_length ({game.max_length})"
    )


def test_a_fixed_seed_is_deterministic_across_runs() -> None:
    first, second = _playout(7), _playout(7)
    assert (first.final, first.decisions) == (second.final, second.decisions)


# ---------------------------------------------------------------------------
# Scripted placements: the rules uniform play reaches too rarely to rely on
# ---------------------------------------------------------------------------


@dataclass
class Scripted:
    offers: list[tuple[int, str, set[tuple[Any, ...]]]]
    boards: list[Board]


def _scripted(script: list[tuple[str, tuple[str, ...]]]) -> Scripted:
    """Play `script` move by move (each entry must be offered), recording
    every decision's seat, family and offered set; stop the game at the first
    decision past the script."""
    game = _game()
    rs_ref: dict[str, RuntimeState] = {}
    out = Scripted([], [])

    class Done(Exception):
        pass

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        offered = {(c[0], _args(c)) for c in candidates}
        kinds = {c[0] for c in candidates}
        out.offers.append((player, next(iter(kinds)), {a for _, a in offered}))
        out.boards.append(_board(rs_ref["rs"]))
        if len(out.offers) > len(script):
            raise Done
        want = script[len(out.offers) - 1]
        assert want in offered, f"scripted {want} not offered to seat {player}"
        return [next(c for c in candidates if (c[0], _args(c)) == want)]

    with pytest.raises(Done):
        play_game(
            game,
            random.Random(0),
            chooser=chooser,
            on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
        )
    return out


def test_every_enemy_man_in_a_mill_may_be_taken() -> None:
    """Black closes a mill and takes White's man outside it; White then closes
    a mill while every Black man stands in Black's — and the removal offers
    all three of them, the exception to the in-mill restriction."""
    run = _scripted(
        [
            ("place", ("a1",)), ("place", ("a7",)),
            ("place", ("d1",)), ("place", ("d7",)),
            ("place", ("b2",)), ("place", ("g7",)),  # Black closes a7 d7 g7
            ("remove", ("b2",)),
            ("place", ("g1",)),  # White closes a1 d1 g1
        ]
    )
    seat, kind, offered = run.offers[6]
    assert (seat, kind) == (1, "remove")
    assert offered == {("a1",), ("d1",), ("b2",)}, "Black's removal offered a man of a mill"
    seat, kind, offered = run.offers[8]
    board = run.boards[8]
    assert all(in_mill(board, p) for p in POINTS if board[p] == "black")
    assert (seat, kind) == (0, "remove")
    assert offered == {("a7",), ("d7",), ("g7",)}


def test_a_man_in_a_mill_is_safe_while_a_free_man_stands() -> None:
    """The restriction's other arm: White closes a mill while Black has one
    man outside Black's mill, and only that man is offered.

    red under: drop `remove`'s last conjunct (`(not in_mill(at)) or
    all_in_mill(...)`) in nine-mens-morris.cardlang; this offers the three
    men of Black's mill as well, and the uniform and smothering playouts
    fail on their removal offers."""
    run = _scripted(
        [
            ("place", ("a1",)), ("place", ("a7",)),
            ("place", ("d1",)), ("place", ("d7",)),
            ("place", ("b2",)), ("place", ("g7",)),  # Black closes a7 d7 g7
            ("remove", ("b2",)),
            ("place", ("b4",)), ("place", ("f6",)),
            ("place", ("g1",)),  # White closes a1 d1 g1
        ]
    )
    seat, kind, offered = run.offers[10]
    assert (seat, kind) == (0, "remove")
    assert offered == {("f6",)}


def test_a_move_closing_two_mills_earns_one_removal() -> None:
    """White's man on d1 closes a1 d1 g1 and d1 d2 d3 at once: one removal
    follows, and then it is Black's turn to place."""
    run = _scripted(
        [
            ("place", ("a1",)), ("place", ("a7",)),
            ("place", ("g1",)), ("place", ("g7",)),
            ("place", ("d2",)), ("place", ("b6",)),
            ("place", ("d3",)), ("place", ("f6",)),
            ("place", ("d1",)),  # two mills
            ("remove", ("a7",)),
        ]
    )
    board = run.boards[9]
    closed = [m for m in MILLS if "d1" in m and all(board[q] == "white" for q in m)]
    assert len(closed) == 2, f"the scripted move closed {len(closed)} mills"
    assert run.offers[9][:2] == (0, "remove")
    assert run.offers[10][:2] == (1, "place"), "a second removal followed two mills"
