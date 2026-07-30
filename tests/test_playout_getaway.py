"""Random-playout harness for Getaway (Bhabhi) — the second game on the runtime
net. Getaway's invariants are NOT Hearts': there is no score and no winner. The
game terminates by elimination, every card is conserved, the tochoo/pickup
mechanic actually fires, and the single survivor is the loser (or, in the rare
all-escape trick, the winner of that final trick).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GETAWAY = Path(__file__).parent.parent / "docs" / "games" / "getaway.cardlang"


def _getaway() -> n.Game:
    return check_source(GETAWAY)


def test_200_random_games_satisfy_invariants() -> None:
    game = _getaway()
    early_terminations = 0
    for seed in range(200):
        tricks = 0
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            nonlocal tricks, early_terminations, census
            if event == "trick_end":
                tricks += 1
                if data["early"]:
                    early_terminations += 1
                assert tricks < 5000, f"seed {seed}: did not terminate"  # noqa: B023 -- consumed before the loop advances
            elif event == "game_end":
                census = data

        result = play_game(game, random.Random(seed), tracer)

        # An elimination game has a loser, no winner, and no scores.
        assert result.loser is not None
        assert result.winner is None
        assert result.scores == {}
        assert result.loser in range(game.players.low)
        # Card conservation: all 52 cards are still somewhere (no loss/dup).
        assert census["total"] == 52, f"seed {seed}: {census['total']} cards"
        # The game ends with at most one player still holding cards.
        assert census["hands_with_cards"] <= 1, f"seed {seed}: {census}"

    # The tochoo early-termination + pickup is the heart of the game; prove it
    # actually fired (termination alone would hold even if it were broken).
    assert early_terminations > 0


def test_playout_is_deterministic_per_seed() -> None:
    game = _getaway()
    first = play_game(game, random.Random(42))
    second = play_game(game, random.Random(42))
    assert first.loser == second.loser
