"""Random-playout harness for breakthrough — the board-topology movement rung.

The corpus's first game in which pieces MOVE (tic-tac-toe only places), so the
invariants are about the step itself. Perfect information, no shuffle, so a
fixed seed is fully deterministic. Checked at EVERY decision point of a
playout, and once more against the terminal board:

- strict alternation — seats fire 0, 1, 0, 1, ... until the game ends;
- every offered `step(from, along)` starts on a man of the ACTOR's side (the
  guard's `top_of(square[from]).side is side_of(actor)`, read off the offer)
  and stays on the board — a step off either edge is never offered, which is
  `has_step` masking the total `neighbor`;
- every applied step lands one rank FORWARD in the actor's frame (up for seat
  0, down for seat 1) and at most one file sideways;
- `ahead` moves straight (no file change) and never captures; `ahead_left` and
  `ahead_right` move exactly one file, in OPPOSITE directions, and are the only
  steps that may capture;
- a capture displaces an ENEMY man (never a friendly one) into `captured[foe]`,
  one man per capture, and nothing else moves;
- conservation — the 32 men are always split across the squares and the two
  captured piles;
- the terminal `result` is (+1,-1) or (-1,+1) and NEVER a draw, and the winner
  either stands on their far row or has taken the loser's last man — the two
  termini the `until` predicate encodes, each driven non-vacuously below.

Plus two length facts. `max_length: 500` is a non-termination backstop, not a
rule: a game that HIT it would be silently truncated and would diverge from the
oracle, which has no move limit. The measured maximum is 108 plies (2026-07-22;
the same over these 100 seeds and over a 400-seed sweep), so the declared cap is
asserted to stay a large multiple of what play produces.

And determinism: a shuffle-free game replays byte-identically from a seed, so
the same seed yields the same final board across two in-process runs — the
candidate list orders by the board's declared cell and direction order, not by
set iteration order (a hash-seed dependence would break this).

Not covered here, and recorded rather than machined: a player who still holds
men but has no legal step. OpenSpiel's breakthrough leaves such a state
non-terminal with an empty action list; the DSL would raise instead. It did not
arise in 400 random games (the smallest offer ever made was 9 steps), so no
machinery is built for it — see roadmap.md, "Board topology — later-rung
surface walled at rung 1".
"""

from __future__ import annotations

import random
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

BREAKTHROUGH = Path(__file__).parent.parent / "docs" / "games" / "breakthrough.cardlang"

FILES = "abcdefgh"
# The sixty-four squares in the board's declared member order (row-major from a1).
CELLS = tuple(f"{f}{r}" for r in range(1, 9) for f in FILES)

SIDE = ("light", "dark")  # seat -> the side it plays (`side_of` in the game)
FORWARD = (1, -1)  # seat -> the rank step "forward" means in that seat's frame
FAR_RANK = (8, 1)  # seat -> the rank it must reach to win
TOTAL_MEN = 32

LEGAL_OUTCOMES = {(1, -1), (-1, 1)}  # never (0, 0): breakthrough has no draw

# The file each direction leans along, per seat — steering data for the
# capture-seeking policy below, never an assertion. The convention itself is
# derived from observation by `test_the_two_directions_lean_opposite_ways`, and
# the wipe-out test cross-checks this copy against what it observed, so a
# changed frame makes that test fail loudly rather than pass vacuously.
LEAN = {
    (0, "ahead_left"): -1, (0, "ahead"): 0, (0, "ahead_right"): 1,
    (1, "ahead_left"): 1, (1, "ahead"): 0, (1, "ahead_right"): -1,
}

RANDOM_SEEDS = 100
GRIND_SEEDS = 24

Board = dict[str, "str | None"]
Policy = Callable[[int, list[Any], Board], Any]


def _game() -> n.Game:
    return check_source(BREAKTHROUGH)


def test_breakthrough_checks_clean() -> None:
    _game()  # parse -> resolve -> typecheck -> capacity; must not raise


def _coords(cell: str) -> tuple[int, int]:
    return FILES.index(cell[0]), int(cell[1:])


def _board(rs: RuntimeState) -> Board:
    return {
        c: (cards[0].suit if (cards := rs.zones.instance("square", c).cards) else None)
        for c in CELLS
    }


def _piles(rs: RuntimeState) -> tuple[int, int]:
    return (
        len(rs.zones.instance("captured", 0).cards),
        len(rs.zones.instance("captured", 1).cards),
    )


def _men_total(board: Board, piles: tuple[int, int]) -> int:
    return sum(1 for v in board.values() if v is not None) + sum(piles)


def _check_step(
    player: int,
    step: tuple[str, str],
    before: Board,
    after: Board,
    piles_before: tuple[int, int],
    piles_after: tuple[int, int],
) -> int:
    """Verify one applied step against the rules and return the file offset it
    moved along (so the caller can pin left/right consistency)."""
    frm, along = step
    side, foe = SIDE[player], 1 - player
    changed = sorted(c for c in CELLS if before[c] != after[c])
    assert changed and frm in changed, f"step({frm},{along}) did not vacate {frm}"
    assert len(changed) == 2, f"step({frm},{along}) disturbed {changed}, not two cells"
    assert after[frm] is None, f"step({frm},{along}) left a man on {frm}"
    dest = changed[0] if changed[1] == frm else changed[1]
    assert after[dest] == side, (
        f"step({frm},{along}) put {after[dest]!r} on {dest}, not the actor's {side}"
    )

    f0, r0 = _coords(frm)
    f1, r1 = _coords(dest)
    assert r1 - r0 == FORWARD[player], (
        f"seat {player}'s step({frm},{along}) went to {dest} — not one rank forward"
    )
    dfile = f1 - f0
    if along == "ahead":
        assert dfile == 0, f"the straight step({frm},{along}) changed file to {dest}"
    else:
        assert abs(dfile) == 1, f"the diagonal step({frm},{along}) reached {dest}"

    victim = before[dest]
    if victim is None:
        assert piles_after == piles_before, (
            f"step({frm},{along}) onto the empty {dest} changed the captured piles"
        )
    else:
        assert victim != side, f"step({frm},{along}) captured a friendly man on {dest}"
        assert along != "ahead", f"the straight step({frm},{along}) captured on {dest}"
        assert piles_after[foe] == piles_before[foe] + 1, (
            f"step({frm},{along}) took a man from {dest} but captured[{foe}] did not grow"
        )
        assert piles_after[player] == piles_before[player], (
            f"step({frm},{along}) grew the actor's own captured pile"
        )
    return dfile


def _terminus(scores: dict[int, int], board: Board) -> str:
    """The game stopped for one of the two reasons the `until` encodes."""
    winner = next(p for p in (0, 1) if scores[p] == 1)
    loser = 1 - winner
    if not any(v == SIDE[loser] for v in board.values()):
        return "wipe_out"
    reached = [
        c for c in CELLS if board[c] == SIDE[winner] and _coords(c)[1] == FAR_RANK[winner]
    ]
    assert reached, (
        f"seat {winner} won with the loser still on the board and no man on "
        f"rank {FAR_RANK[winner]} — neither terminus fired"
    )
    return "reach"


def _random_policy(rng: random.Random) -> Policy:
    def pick(player: int, candidates: list[Any], board: Board) -> Any:
        return rng.choice(candidates)

    return pick


def _capture_seeking_policy(rng: random.Random) -> Policy:
    """Take whenever a take exists, and otherwise stay off the far row. Random
    play essentially always ends by reaching the far row (100/100 seeds), so
    the wipe-out terminus needs a policy that trades men and declines to win by
    arriving. Steering only — every invariant is checked exactly as under
    random play."""

    def destination(player: int, frm: str, along: str) -> str:
        f, r = _coords(frm)
        return f"{FILES[f + LEAN[(player, along)]]}{r + FORWARD[player]}"

    def pick(player: int, candidates: list[Any], board: Board) -> Any:
        takes = [c for c in candidates if board[destination(player, *c[1])] is not None]
        if takes:
            return rng.choice(takes)
        quiet = [
            c
            for c in candidates
            if _coords(c[1][0])[1] + FORWARD[player] != FAR_RANK[player]
        ]
        return rng.choice(quiet or candidates)

    return pick


class Playout:
    """One finished playout's evidence: the terminal result and board, its
    length, which terminus fired, and the file offset each (seat, direction)
    was observed to move along."""

    def __init__(
        self,
        result: Any,
        board: Board,
        plies: int,
        terminus: str,
        offsets: dict[tuple[int, str], int],
    ) -> None:
        self.result = result
        self.board = board
        self.plies = plies
        self.terminus = terminus
        self.offsets = offsets


def _playout(seed: int, policy_for: Callable[[random.Random], Policy] = _random_policy) -> Playout:
    """Drive one playout under `policy_for`, asserting the per-decision
    invariants as it goes."""
    game = _game()
    assert game.max_length is not None
    cap = game.max_length
    rng = random.Random(seed)
    policy = policy_for(rng)
    rs_ref: dict[str, RuntimeState] = {}
    offsets: dict[tuple[int, str], int] = {}
    plies = [0]
    prev: list[Any] = [None]

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        rs = rs_ref["rs"]
        board, piles = _board(rs), _piles(rs)
        plies[0] += 1
        assert plies[0] <= cap, "the playout ran past the declared max_length"
        assert k == 1, f"breakthrough offers one move; got k={k}"
        assert _men_total(board, piles) == TOTAL_MEN, "the 32 men were not conserved"
        if prev[0] is not None:
            who, step, before, piles_before = prev[0]
            assert player == 1 - who, f"turn order broke: seat {player} after {who}"
            dfile = _check_step(who, step, before, board, piles_before, piles)
            assert offsets.setdefault((who, step[1]), dfile) == dfile, (
                f"seat {who}'s {step[1]} changed which way it leans"
            )
        # every offer starts on one of the actor's own men and stays on the board
        for kind, (frm, along) in candidates:
            assert kind == "step"
            assert board[frm] == SIDE[player], (
                f"step({frm},{along}) offered to seat {player} on {board[frm]!r}"
            )
            file_, rank = _coords(frm)
            assert 1 <= rank + FORWARD[player] <= 8, (
                f"step({frm},{along}) offered off the far edge to seat {player}"
            )
            lean = offsets.get((player, along))
            if lean is not None:
                assert 0 <= file_ + lean < 8, (
                    f"step({frm},{along}) offered off the side edge to seat {player}"
                )
        choice = policy(player, candidates, board)
        prev[0] = (player, choice[1], board, piles)
        return [choice]

    result = play_game(
        game,
        rng,
        chooser=chooser,
        on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
    )
    rs = rs_ref["rs"]
    final, piles = _board(rs), _piles(rs)
    who, step, before, piles_before = prev[0]
    offsets.setdefault((who, step[1]), _check_step(who, step, before, final, piles_before, piles))
    assert _men_total(final, piles) == TOTAL_MEN, "conservation broken at the terminal"
    outcome = (result.scores[0], result.scores[1])
    assert outcome in LEGAL_OUTCOMES, f"illegal terminal result {outcome}"
    assert result.loser is None
    return Playout(result, final, plies[0], _terminus(result.scores, final), offsets)


@lru_cache(maxsize=None)
def _random_run(seed: int) -> Playout:
    return _playout(seed)


@lru_cache(maxsize=None)
def _grind_run(seed: int) -> Playout:
    return _playout(seed, _capture_seeking_policy)


@pytest.mark.parametrize("seed", range(RANDOM_SEEDS))
def test_breakthrough_playout_invariants(seed: int) -> None:
    _random_run(seed)


def test_both_outcomes_arise_under_random_play() -> None:
    """Not vacuous: random play produces seat-0 wins AND seat-1 wins, and never
    a draw — so the invariant suite exercises both branches of the zero-sum
    result encoding."""
    tally = Counter(_random_run(seed).result.scores[0] for seed in range(RANDOM_SEEDS))
    assert tally[1] > 0 and tally[-1] > 0, f"random play covered one side only: {dict(tally)}"
    assert tally[0] == 0, "a draw appeared — breakthrough is monotone and has none"


def test_the_two_directions_lean_opposite_ways() -> None:
    """`ahead_left` and `ahead_right` are distinct steps for each seat: each is
    consistently one file offset across every playout, and the two are
    opposite. WHICH one is which is the frame's internal convention (Task 6's
    to_native pins it against the oracle); that they differ is a rule."""
    seen: dict[tuple[int, str], int] = {}
    for seed in range(RANDOM_SEEDS):
        for key, dfile in _random_run(seed).offsets.items():
            assert seen.setdefault(key, dfile) == dfile, f"{key} leaned both ways"
    for player in (0, 1):
        left, right = seen.get((player, "ahead_left")), seen.get((player, "ahead_right"))
        assert left is not None and right is not None, (
            f"seat {player} never played both diagonals in {RANDOM_SEEDS} playouts"
        )
        assert left == -right, f"seat {player}'s diagonals both lean {left}"
        assert seen[(player, "ahead")] == 0


def test_the_reach_terminus_fires_under_random_play() -> None:
    """The first of the two termini the `until` predicate encodes: a man
    arriving on the actor's far row ends the game at once."""
    tally = Counter(_random_run(seed).terminus for seed in range(RANDOM_SEEDS))
    assert tally["reach"] > 0, f"no game ended by reaching the far row: {dict(tally)}"


def test_the_wipe_out_terminus_fires_under_capture_seeking_play() -> None:
    """The second terminus: taking the opponent's last man ends the game even
    with the far row untouched. Random play never gets there (it wins by
    arriving first), so this drives the capture-seeking policy — the branch
    that decrements `pieces_left` to zero would otherwise be dead code. The
    policy's steering table is cross-checked against what the playouts actually
    observed, so a changed frame convention cannot make this pass vacuously."""
    runs = [_grind_run(seed) for seed in range(GRIND_SEEDS)]
    tally = Counter(r.terminus for r in runs)
    assert tally["wipe_out"] > 0, (
        f"capture-seeking play never emptied a side in {GRIND_SEEDS} seeds: {dict(tally)}"
    )
    for run in runs:
        for key, dfile in run.offsets.items():
            assert LEAN[key] == dfile, f"the policy steered by a stale frame at {key}"
    wiped = next(r for r in runs if r.terminus == "wipe_out")
    winner = 0 if wiped.result.scores[0] == 1 else 1
    assert not any(v == SIDE[1 - winner] for v in wiped.board.values())
    assert sum(1 for v in wiped.board.values() if v == SIDE[winner]) > 0


def test_random_play_never_approaches_the_declared_max_length() -> None:
    """`max_length` is a non-termination backstop, not a rule. A game that hit
    it would be silently truncated — and would diverge from the oracle, which
    has no move limit — so the declared cap must stay far above what real lines
    produce. Measured 2026-07-22: 108 plies, over these 100 seeds and over 400."""
    game = _game()
    assert game.max_length is not None
    longest = max(
        max(_random_run(seed).plies for seed in range(RANDOM_SEEDS)),
        max(_grind_run(seed).plies for seed in range(GRIND_SEEDS)),
    )
    assert longest < game.max_length, "a playout reached the declared max_length"
    assert longest * 4 < game.max_length, (
        f"the longest observed game ({longest} plies) is within 4x of the declared "
        f"max_length ({game.max_length}) — raise the cap before a real line is cut"
    )


def test_a_fixed_seed_is_deterministic_across_runs() -> None:
    """Perfect information + no shuffle: the same seed yields the same final
    board twice. The candidate list is ordered by the board's declared cell and
    direction order (not set iteration order), so this holds independent of
    PYTHONHASHSEED — a set-ordering dependence would make the two runs diverge."""
    first, second = _playout(7), _playout(7)
    assert (first.board, first.plies) == (second.board, second.plies)
