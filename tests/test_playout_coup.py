"""Random-playout harness for Coup.

Coup is the corpus's furthest-from-cards game (influence, coins, bluff, challenge,
block, elimination). Its falsifiable invariants are conservation and termination:
total coins stay at 50 (treasury + players), influence cards stay at 15 (deck +
hands + revealed), and every game ends with exactly one player still holding
influence — the winner.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

COUP = Path(__file__).parent.parent / "docs" / "games" / "coup.cardlang"


def test_40_random_games_satisfy_invariants() -> None:
    game = check_source(COUP)
    for seed in range(40):
        info: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "coup_game":
                info.update(data)

        result = play_game(game, random.Random(seed), tracer)

        # Exactly one survivor, who is the winner.
        survivors = [p for p, a in result.scores.items() if a == 1]
        assert len(survivors) == 1, f"seed {seed}: alive = {result.scores}"
        assert result.winner == survivors[0]
        assert result.winner == max(result.scores, key=lambda p: result.scores[p])

        # Conservation: 50 coins and 15 influence cards, always.
        assert info["total_coins"] == 50, f"seed {seed}: {info}"
        assert info["total_cards"] == 15, f"seed {seed}: {info}"
