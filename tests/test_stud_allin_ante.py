"""Regression: a Stud hand where everyone goes all-in on the ante must not crash.

Two players each enter with exactly one chip (= the ante), so after antes every
entrant is all-in and nobody can bring in or bet. Before the fix, the bring-in's
`min(able, ...)` over an empty list raised ValueError. The hand should instead be
dealt out and settled at showdown.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

FIXTURE = Path(__file__).parent / "fixtures" / "stud_allin.cardlang"


def test_ante_all_in_hand_settles_without_crashing() -> None:
    game = check_source(FIXTURE)
    for seed in range(30):
        census: dict[str, Any] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()
                census.update(data)

        result = play_game(game, random.Random(seed))  # must not raise
        # Two chips total, always; the game ends with one player holding them.
        assert sum(result.scores.values()) == 2, f"seed {seed}: {result.scores}"
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1 and result.winner == with_chips[0]
