"""Random-playout harness for tic-tac-toe — the board-topology walking skeleton.

The first board game in the corpus, and a perfect-information one: no shuffle,
no hidden zone, so a fixed seed is fully deterministic. Its falsifiable
invariants, checked at EVERY decision point of a random playout:

- strict alternation — seats fire 0, 1, 0, 1, ... until the game ends (`turns
  t from 0 over all players`);
- every placement lands on a previously-EMPTY cell (the `when: square[at] is
  empty` guard, observed from the offered candidates);
- at most nine decisions — one mark per placement, nine cells;
- conservation — the five X plus four O marks are always split across the two
  reserves and the nine squares, nine in total;
- the terminal `result` is one of the three legal outcomes (X win, O win,
  draw), encoded (+1,-1) / (-1,+1) / (0,0).

Plus determinism: a shuffle-free game replays byte-identically from a seed, so
the same seed yields the same final board across two in-process runs — the
candidate list orders by the board's declared member order, not by set
iteration order (a hash-seed dependence would break this).
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

TTT = Path(__file__).parent.parent / "docs" / "games" / "tic-tac-toe.cardlang"

# The nine squares in the board's declared member order (row-major from a1).
NINE_CELLS = ("a1", "b1", "c1", "a2", "b2", "c2", "a3", "b3", "c3")

LEGAL_OUTCOMES = {(1, -1), (-1, 1), (0, 0)}


def _ttt() -> n.Game:
    return check_source(TTT)


def test_tic_tac_toe_checks_clean() -> None:
    _ttt()  # parse -> resolve -> typecheck -> capacity; must not raise


def _filled(rs: RuntimeState) -> dict[str, str | None]:
    return {
        c: (cards[0].suit if (cards := rs.zones.instance("square", c).cards) else None)
        for c in NINE_CELLS
    }


def _marks_total(rs: RuntimeState) -> int:
    on_board = sum(len(rs.zones.instance("square", c).cards) for c in NINE_CELLS)
    in_reserve = len(rs.zones.instance("reserve", 0).cards) + len(
        rs.zones.instance("reserve", 1).cards
    )
    return on_board + in_reserve


def _playout(seed: int) -> tuple[Any, dict[str, str | None]]:
    """Drive one random playout, asserting the per-decision invariants; return
    (result, final board)."""
    game = _ttt()
    rng = random.Random(seed)
    rs_ref: dict[str, RuntimeState] = {}
    seats: list[int] = []
    decisions = [0]

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        rs = rs_ref["rs"]
        decisions[0] += 1
        assert decisions[0] <= 9, "more than nine placements on a 3x3 board"
        assert k == 1, f"tic-tac-toe offers one move; got k={k}"
        # strict alternation: seat p fires, then 1 - p, ...
        if seats:
            assert player == 1 - seats[-1], (
                f"turn order broke: seat {player} after {seats[-1]}"
            )
        seats.append(player)
        # nine marks always conserved across reserves + board
        assert _marks_total(rs) == 9, "the nine marks were not conserved"
        # every offered placement targets an empty cell
        board = _filled(rs)
        for kind, cell in candidates:
            assert kind == "place"
            assert board[cell] is None, f"place({cell}) offered on an occupied cell"
        choice = rng.choice(candidates)
        return [choice]

    result = play_game(
        game,
        rng,
        chooser=chooser,
        on_first_decision=lambda rs: rs_ref.__setitem__("rs", rs),
    )
    final = _filled(rs_ref["rs"])
    assert _marks_total(rs_ref["rs"]) == 9, "conservation broken at the terminal"
    outcome = (result.scores[0], result.scores[1])
    assert outcome in LEGAL_OUTCOMES, f"illegal terminal result {outcome}"
    assert result.loser is None
    return result, final


@pytest.mark.parametrize("seed", range(100))
def test_tic_tac_toe_playout_invariants(seed: int) -> None:
    _playout(seed)


def test_all_three_outcomes_arise_under_random_play() -> None:
    """Not vacuous: random play produces X wins, O wins, AND draws, so the
    invariant suite exercises every terminal branch of the result encoding."""
    tally = Counter(_playout(seed)[0].scores[0] for seed in range(100))
    assert tally[1] > 0 and tally[-1] > 0 and tally[0] > 0, (
        f"random play did not cover all three outcomes: {dict(tally)}"
    )


def test_a_fixed_seed_is_deterministic_across_runs() -> None:
    """Perfect information + no shuffle: the same seed yields the same final
    board twice. The candidate list is ordered by the board's declared member
    order (not set iteration order), so this holds independent of PYTHONHASHSEED
    — a set-ordering dependence would make the two runs diverge."""
    _, board_a = _playout(7)
    _, board_b = _playout(7)
    assert board_a == board_b


def test_a_fixed_seed_pins_a_known_board() -> None:
    """Characterization: seed 7 draws (a full board). Pinning the exact layout
    catches an accidental change to the candidate ordering or the rng stream."""
    result, board = _playout(7)
    assert (result.scores[0], result.scores[1]) == (0, 0)
    assert board == {
        "a1": "x", "b1": "o", "c1": "o",
        "a2": "o", "b2": "x", "c2": "x",
        "a3": "x", "b3": "x", "c3": "o",
    }
