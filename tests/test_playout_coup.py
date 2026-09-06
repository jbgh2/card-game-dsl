"""Random-playout harness for Coup.

Coup is the corpus's furthest-from-cards game (influence, coins, bluff, challenge,
block, elimination). Its falsifiable invariants are conservation and termination:
total coins stay at 50 (treasury + players), influence cards stay at 15 (deck +
hands + revealed), and every game ends with exactly one player still holding
influence — the winner.

The two totals are the harness's own arithmetic over the terminal world and the
driver's terminal card census (tests/playout_trace.py, `TerminalState` and
`coup_totals`), so the 50 and the 15 are this test's numbers rather than a
number the game text reports about itself.
"""

from __future__ import annotations

import random
from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from tests.playout_trace import TerminalState, coup_totals

COUP = Path(__file__).parent.parent / "docs" / "games" / "coup.cardlang"


def test_40_random_games_satisfy_invariants() -> None:
    game = check_source(COUP)
    for seed in range(40):
        terminal = TerminalState(("coins", "treasury"))
        result = play_game(
            game,
            random.Random(seed),
            terminal.tracer,
            on_first_decision=terminal.hold,
        )

        # Exactly one survivor, who is the winner.
        survivors = [p for p, a in result.scores.items() if a == 1]
        assert len(survivors) == 1, f"seed {seed}: alive = {result.scores}"
        assert result.winner == survivors[0]
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])

        # Conservation: 50 coins and 15 influence cards, always.
        totals = coup_totals(terminal)
        assert totals["total_coins"] == 50, f"seed {seed}: {totals}"
        assert totals["total_cards"] == 15, f"seed {seed}: {totals}"
