"""Random-playout harness for Hearts.

The runtime net's acceptance test: play Hearts to completion with random legal
moves and assert the invariants implementation.md names — it terminates, the
legal-move set is never empty before terminal (else the chooser would raise),
scores reconcile, and a winner emerges.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def _hearts() -> n.Game:
    return check_source(HEARTS)


def test_200_random_games_satisfy_invariants() -> None:
    game = _hearts()
    for seed in range(200):
        hand_totals: list[int] = []

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                hand_totals.append(sum(data.values()))

        result = play_game(game, random.Random(seed), tracer)

        # Terminates (returned), and someone crossed the 100-point threshold.
        assert max(result.scores.values()) >= 100
        # Winner is the lowest cumulative score.
        assert result.winner == min(result.scores, key=lambda p: result.scores[p])
        # Each hand contributes 26 points (13 hearts + Q♠), or 78 on a
        # shoot-the-moon (shooter 0, the other three 26 each).
        deltas = [b - a for a, b in zip([0, *hand_totals], hand_totals)]
        assert all(d in (26, 78) for d in deltas), f"seed {seed}: hand deltas {deltas}"
        assert len(hand_totals) == result.hands_played


def test_one_game_trace_is_coherent() -> None:
    game = _hearts()
    plays: list[tuple[int, Any]] = []
    tricks: list[tuple[int, list[Any]]] = []

    def tracer(event: str, data: Any) -> None:
        if event == "play":
            plays.append(data)
        elif event == "trick":
            tricks.append(data)

    result = play_game(game, random.Random(7), tracer)

    # Thirteen tricks per hand, four plays per trick.
    assert len(tricks) == 13 * result.hands_played
    assert len(plays) == 4 * len(tricks)

    for i, (winner, cards) in enumerate(tricks):
        group = plays[i * 4 : (i + 1) * 4]
        players_in_trick = {p for p, _ in group}
        assert len(players_in_trick) == 4  # all four play once
        assert winner in players_in_trick  # the winner is one of them
        assert len(cards) == 4
