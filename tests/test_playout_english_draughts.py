"""Random-playout harness for English draughts -- the first corpus game whose
turn offers one move family or another by whether a capture exists anywhere,
and whose one move can take several jumps.

The rules are recomputed here by an independent model -- the dark squares
and the diagonal steps written as coordinates, never read from the board
registry -- and checked at EVERY decision point of a playout, and once more
against the terminal position:

- the offered set equals the model's EXACTLY: mid-capture, every jump of the
  piece on `chain_from` and nothing else; otherwise every jump of the actor's
  side if it has one, and every step if it has none -- so a man moves
  forward, a king either way, every move starts on one of the actor's pieces
  and lands on a dark square;
- strict alternation, except across a capture the same piece goes on with:
  the same seat moves again exactly when the model says the piece that just
  jumped has another jump and was not crowned, and then `chain_from` names
  its square;
- a jump moves exactly one enemy piece from the square it jumps into
  `captured[foe]`, and a step captures nothing;
- crowning: a man ending a move on its far rank is a king there, the man in
  `reserve[actor]` and one fewer king in `kings[actor]`, and the move ends;
- conservation -- the forty-eight pieces are always split across the squares,
  the reserves, the king supplies and the captured piles;
- `quiet` is 0 after a jump or a man's step, and one more after a king's
  step;
- the terminal result is (+1, -1) or (-1, +1), the loser with no legal move,
  or (0, 0) with `quiet` at 80, ended by the rules.

Both termini are driven non-vacuously: the win under uniform play, the loser
with pieces still on the board under a policy that leaves the opponent the
fewest replies; the draw under a policy that shuffles kings once both sides
hold one, playing a king's step that leaves the opponent no capture.

The length fact. `max_length` is the bound a game ends at, not a rule: every
line of this game ends by its rules, since a man's moves are finite, every
capture takes a piece, and between them the forty-move count ends the game.
The bound keeps four times the longest line uniform play makes over this
module's seeds, and stays above every policy line
(`test_random_play_never_approaches_the_declared_max_length`).

And determinism: a shuffle-free game replays identically from a seed.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import EndedBy, play_game
from cardlang.runtime.state import RuntimeState

DRAUGHTS = Path(__file__).parent.parent / "docs" / "games" / "english-draughts.cardlang"

FILES = "abcdefgh"
SIZE = 8
SIDE = ("red", "white")  # seat -> the side it plays (`side_of` in the game)
FORWARD = (1, -1)  # seat -> the rank step "forward" means for its men
FAR_RANK = (8, 1)  # seat -> the rank its men are crowned on
TOTAL_PIECES = 48  # twelve men and twelve kings a side
QUIET_DRAW = 80
LEGAL_OUTCOMES = {(1, -1), (-1, 1), (0, 0)}

# The dark squares: file (a = 1) plus rank even.
CELLS: tuple[str, ...] = tuple(
    f"{f}{r}" for r in range(1, SIZE + 1) for i, f in enumerate(FILES) if (i + 1 + r) % 2 == 0
)

RANDOM_SEEDS = 24
POLICY_SEEDS = 4

Piece = tuple[int, bool]  # (seat, is a king)
Board = dict[str, Piece]
Candidate = tuple[str, tuple[str, str]]


def _coords(cell: str) -> tuple[int, int]:
    return FILES.index(cell[0]), int(cell[1:])


def _cell(file: int, rank: int) -> str | None:
    if 0 <= file < SIZE and 1 <= rank <= SIZE:
        return f"{FILES[file]}{rank}"
    return None


def _diagonal(frm: str, to: str) -> tuple[int, int]:
    """The (file, rank) step from `frm` to `to`, which must be diagonal."""
    (f0, r0), (f1, r1) = _coords(frm), _coords(to)
    assert abs(f1 - f0) == abs(r1 - r0) > 0, f"{frm} -> {to} is not diagonal"
    return f1 - f0, r1 - r0


@dataclass(frozen=True)
class Move:
    """A move the model offers, by its squares."""

    kind: str  # "step" or "jump"
    frm: str
    to: str

    @property
    def over(self) -> str:
        (f0, r0), (f1, r1) = _coords(self.frm), _coords(self.to)
        cell = _cell((f0 + f1) // 2, (r0 + r1) // 2)
        assert cell is not None
        return cell


def legal(board: Board, player: int, chain: str | None) -> set[Move]:
    """The model's legal moves for `player`: the chained piece's jumps
    mid-capture, else every jump of its side, else every step."""
    jumps: set[Move] = set()
    steps: set[Move] = set()
    for cell, (owner, king) in board.items():
        if owner != player or (chain is not None and cell != chain):
            continue
        f, r = _coords(cell)
        for df in (-1, 1):
            for dr in ((-1, 1) if king else (FORWARD[player],)):
                one, two = _cell(f + df, r + dr), _cell(f + 2 * df, r + 2 * dr)
                if one is not None and one not in board:
                    steps.add(Move("step", cell, one))
                if (
                    one is not None and two is not None
                    and board.get(one, (player, False))[0] != player
                    and two not in board
                ):
                    jumps.add(Move("jump", cell, two))
    if chain is not None or jumps:
        return jumps
    return steps


@dataclass
class After:
    """A move applied to a board, by the model."""

    board: Board
    crowned: bool
    continues: bool


def apply(board: Board, player: int, move: Move) -> After:
    after = dict(board)
    owner, king = after.pop(move.frm)
    if move.kind == "jump":
        del after[move.over]
    crowned = not king and _coords(move.to)[1] == FAR_RANK[player]
    after[move.to] = (owner, king or crowned)
    continues = (
        move.kind == "jump" and not crowned and bool(legal(after, player, move.to))
    )
    return After(after, crowned, continues)


@dataclass(frozen=True)
class Snapshot:
    """What the harness reads off the runtime at one decision."""

    board: Board
    reserve: tuple[int, int]
    kings: tuple[int, int]
    captured: tuple[int, int]
    quiet: int | None  # None at the terminal, whose frame is gone
    chain: str | None

    def pieces(self) -> int:
        return len(self.board) + sum(self.reserve) + sum(self.kings) + sum(self.captured)


def _count(rs: RuntimeState, zone: str, player: int) -> int:
    return len(rs.zones.instance(zone, player).cards)


def _snapshot(rs: RuntimeState, *, live: bool = True) -> Snapshot:
    """The position; the state variables too while the game is live."""
    board: Board = {}
    for cell in CELLS:
        cards = rs.zones.instance("square", cell).cards
        assert len(cards) <= 1, f"{cell} holds {len(cards)} pieces"
        if cards:
            board[cell] = (SIDE.index(cards[0].suit), cards[0].rank == "king")
    chain = rs.get("chain_from") if live else None
    return Snapshot(
        board,
        (_count(rs, "reserve", 0), _count(rs, "reserve", 1)),
        (_count(rs, "kings", 0), _count(rs, "kings", 1)),
        (_count(rs, "captured", 0), _count(rs, "captured", 1)),
        int(rs.get("quiet")) if live else None,
        None if chain is None else str(chain),
    )


def _as_move(player: int, candidate: Candidate) -> Move:
    """The squares an offered candidate names, read through the model's own
    frame: seat 0's `ahead_*` up the ranks, seat 1's turned half round."""
    kind, (frm, along) = candidate
    df = -1 if along.endswith("left") else 1
    dr = 1 if along.startswith("ahead") else -1
    if player == 1:
        df, dr = -df, -dr
    hops = 2 if kind == "jump" else 1
    f, r = _coords(frm)
    to = _cell(f + df * hops, r + dr * hops)
    assert to is not None, f"{candidate} is offered off the board to seat {player}"
    return Move(kind, frm, to)


def _check_move(player: int, move: Move, before: Snapshot, after: Snapshot) -> tuple[After, int]:
    """Verify one applied move against the model and return what it did and
    the count it leaves."""
    expected = apply(before.board, player, move)
    assert after.board == expected.board, (
        f"seat {player}'s {move} left {sorted(after.board.items())}, the model "
        f"{sorted(expected.board.items())}"
    )
    foe = 1 - player
    taken = 1 if move.kind == "jump" else 0
    assert after.captured[foe] == before.captured[foe] + taken, (
        f"seat {player}'s {move} moved {after.captured[foe] - before.captured[foe]} "
        f"pieces into captured[{foe}]"
    )
    assert after.captured[player] == before.captured[player]
    crowned = 1 if expected.crowned else 0
    assert after.reserve[player] == before.reserve[player] + crowned
    assert after.kings[player] == before.kings[player] - crowned
    assert (after.reserve[foe], after.kings[foe]) == (before.reserve[foe], before.kings[foe])
    assert before.quiet is not None
    king = before.board[move.frm][1]
    quiet = before.quiet + 1 if (move.kind == "step" and king) else 0
    assert after.quiet in (quiet, None), (
        f"seat {player}'s {move}: quiet {after.quiet}, expected {quiet}"
    )
    return expected, quiet


Policy = Callable[[int, list[Candidate], Snapshot, random.Random], Candidate]


def uniform(player: int, candidates: list[Candidate], snap: Snapshot, rng: random.Random) -> Candidate:
    return candidates[rng.randrange(len(candidates))]


def _replies(board: Board, player: int, move: Move) -> int:
    """How many moves the opponent has after `move` ends the turn; the same
    seat going on counts as many."""
    after = apply(board, player, move)
    if after.continues:
        return TOTAL_PIECES
    return len(legal(after.board, 1 - player, None))


def fewest_replies(player: int, candidates: list[Candidate], snap: Snapshot, rng: random.Random) -> Candidate:
    """Leave the opponent the fewest moves: the policy that drives the loss
    with pieces still on the board."""
    scored = [(_replies(snap.board, player, _as_move(player, c)), c) for c in candidates]
    best = min(score for score, _ in scored)
    tied = [c for score, c in scored if score == best]
    return tied[rng.randrange(len(tied))]


def _opens_no_capture(board: Board, player: int, move: Move) -> bool:
    after = apply(board, player, move)
    return after.continues or not any(m.kind == "jump" for m in legal(after.board, 1 - player, None))


def king_shuffle(player: int, candidates: list[Candidate], snap: Snapshot, rng: random.Random) -> Candidate:
    """Uniform play until both sides hold a king; then a king's step that
    leaves the opponent no capture, where there is one: the policy that
    drives the forty-move draw."""
    if {owner for owner, king in snap.board.values() if king} == {0, 1}:
        quiet = [
            c for c in candidates
            if c[0] == "step"
            and snap.board[c[1][0]][1]
            and _opens_no_capture(snap.board, player, _as_move(player, c))
        ]
        if quiet:
            return quiet[rng.randrange(len(quiet))]
    return candidates[rng.randrange(len(candidates))]


@dataclass
class Playout:
    """One finished playout's evidence."""

    outcome: tuple[int, int]
    final: Snapshot
    plies: int
    terminus: str  # "no move" or "forty moves"
    events: Counter[str]


def _game() -> n.Game:
    return check_source(DRAUGHTS)


def test_english_draughts_checks_clean() -> None:
    _game()  # parse -> resolve -> typecheck -> capacity; must not raise


def _playout(seed: int, policy: Policy = uniform) -> Playout:
    """Drive one playout under `policy`, asserting the per-decision
    invariants as it goes."""
    game = _game()
    assert game.max_length is not None
    cap = game.max_length
    rng = random.Random(seed)
    rs_ref: dict[str, RuntimeState] = {}
    prev: list[Any] = [None]
    plies = [0]
    events: Counter[str] = Counter()

    def check_previous(snap: Snapshot) -> tuple[After, int] | None:
        if prev[0] is None:
            return None
        who, move, before = prev[0]
        done, quiet = _check_move(who, move, before, snap)
        events[move.kind] += 1
        events["crowned"] += done.crowned
        events["continued"] += done.continues
        king = before.board[move.frm][1]
        if king and _diagonal(move.frm, move.to)[1] * FORWARD[who] < 0:
            events[f"king {move.kind} back"] += 1
        return done, quiet

    def chooser(player: int, candidates: list[Candidate], k: int) -> list[Candidate]:
        snap = _snapshot(rs_ref["rs"])
        plies[0] += 1
        assert plies[0] <= cap, "the playout ran past the declared max_length"
        assert k == 1, f"draughts offers one move; got k={k}"
        assert snap.pieces() == TOTAL_PIECES, "the forty-eight pieces were not conserved"
        checked = check_previous(snap)
        if checked is not None:
            done, who = checked[0], prev[0][0]
            if done.continues:
                assert player == who and snap.chain == prev[0][1].to, (
                    f"seat {who}'s piece on {prev[0][1].to} must jump again; seat "
                    f"{player} moves with chain_from {snap.chain}"
                )
            else:
                assert player == 1 - who and snap.chain is None, (
                    f"turn order broke: seat {player} after {who}, chain_from {snap.chain}"
                )
        offered = {_as_move(player, c) for c in candidates}
        assert len(offered) == len(candidates)
        expected = legal(snap.board, player, snap.chain)
        assert offered == expected, (
            f"seat {player} is offered {sorted(map(str, offered - expected))} beyond "
            f"the model and lacks {sorted(map(str, expected - offered))}"
        )
        choice = policy(player, candidates, snap, rng)
        prev[0] = (player, _as_move(player, choice), snap)
        return [choice]

    result = play_game(
        game, rng, chooser=chooser,
        on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
    )
    final = _snapshot(rs_ref["rs"], live=False)
    checked = check_previous(final)
    assert checked is not None and not checked[0].continues
    quiet = checked[1]
    assert final.pieces() == TOTAL_PIECES, "conservation broken at the terminal"
    assert result.ended_by is EndedBy.RULES, f"seed {seed} ended by {result.ended_by}"
    outcome = (result.scores[0], result.scores[1])
    assert outcome in LEGAL_OUTCOMES, f"illegal terminal result {outcome}"
    if outcome == (0, 0):
        assert quiet == QUIET_DRAW, f"a tie with quiet at {quiet}"
        terminus = "forty moves"
    else:
        winner = 0 if outcome[0] == 1 else 1
        assert prev[0][0] == winner, "the last move was not the winner's"
        assert not legal(final.board, 1 - winner, None), (
            f"seat {1 - winner} lost with a legal move left"
        )
        terminus = "no move"
    return Playout(outcome, final, plies[0], terminus, events)


@cache
def _random_run(seed: int) -> Playout:
    return _playout(seed)


@cache
def _blockade_run(seed: int) -> Playout:
    return _playout(seed, fewest_replies)


@cache
def _shuffle_run(seed: int) -> Playout:
    return _playout(seed, king_shuffle)


@pytest.mark.parametrize("seed", range(RANDOM_SEEDS))
def test_english_draughts_playout_invariants(seed: int) -> None:
    """Every decision of a uniform line holds the module's invariants.

    red under: drop `quiet := 0` from `step`'s man arm in the game, and the
    count check fails at the first man's step after a king's."""
    _random_run(seed)


def test_both_winners_and_every_move_kind_arise_under_random_play() -> None:
    """Not vacuous: uniform play produces wins for each seat, and between them
    every branch of the move rules -- a step, a jump, a jump the same piece
    goes on with, a crowning, and a king's step and jump backward."""
    runs = [_random_run(seed) for seed in range(RANDOM_SEEDS)]
    winners = Counter(r.outcome for r in runs)
    assert winners[(1, -1)] and winners[(-1, 1)], dict(winners)
    events = sum((r.events for r in runs), Counter())
    for kind in ("step", "jump", "continued", "crowned", "king step back", "king jump back"):
        assert events[kind], f"no {kind} in {RANDOM_SEEDS} playouts: {dict(events)}"


def test_the_loss_with_pieces_on_the_board_fires_under_fewest_replies() -> None:
    """The loss of a player whose pieces are all blocked, with pieces still on
    the board, drives the `can_move(foe)` branch the way a capture of the last
    piece does not."""
    runs = [_blockade_run(seed) for seed in range(POLICY_SEEDS)]
    blocked = [
        r for r in runs
        if r.terminus == "no move"
        and any(owner == (1 if r.outcome[0] == 1 else 0) for owner, _ in r.final.board.values())
    ]
    assert blocked, f"no blockade in {POLICY_SEEDS} seeds: {[r.terminus for r in runs]}"


def test_the_forty_move_draw_fires_under_king_shuffle() -> None:
    """The draw: eighty quiet plies tie the game by its rules."""
    runs = [_shuffle_run(seed) for seed in range(POLICY_SEEDS)]
    tally = Counter(r.terminus for r in runs)
    assert tally["forty moves"], f"no forty-move draw in {POLICY_SEEDS} seeds: {dict(tally)}"


def test_random_play_never_approaches_the_declared_max_length() -> None:
    """`max_length` is the bound a game ends at, not a rule; a line that
    reached it would end there by its Length Stop, a line the differential
    refuses. So the declared cap keeps four times the longest line uniform
    play makes over this module's seeds, and stays above every policy line.

    red under: declare `max_length` at four times the longest uniform line
    or less in english-draughts.cardlang."""
    game = _game()
    assert game.max_length is not None
    longest = max(_random_run(seed).plies for seed in range(RANDOM_SEEDS))
    assert longest * 4 < game.max_length, (
        f"the longest uniform game ({longest} plies) is within 4x of the declared "
        f"max_length ({game.max_length}) -- raise the cap before a real line is cut"
    )
    policy = max(
        max(_blockade_run(seed).plies, _shuffle_run(seed).plies) for seed in range(POLICY_SEEDS)
    )
    assert policy < game.max_length, f"a policy line ({policy} plies) reached max_length"


def test_a_fixed_seed_is_deterministic_across_runs() -> None:
    """Perfect information and no shuffle: the same seed yields the same final
    position twice, the candidate list ordered by the board's declared cell
    and direction order rather than by set iteration order."""
    first, second = _playout(7), _playout(7)
    assert (first.final, first.plies) == (second.final, second.plies)
