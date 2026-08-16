"""Playtest statistics over random rollouts of a registered cardlang game —
the designer-feedback seed (SP1 spec, "Design-tool alignment"): run N games,
report length, branching, returns spread, and a best-finish count per [[seat]] —
one credit per rollout, so a tie credits the lowest-numbered tied seat alone and
a game whose seats can share a top return reads as more seat-biased than it is
(issue #353)."""

from __future__ import annotations

import random
from typing import Any

import pyspiel


def playtest_report(short_name: str, num_games: int, seed: int = 0) -> dict[str, Any]:
    game = pyspiel.load_game(short_name)
    rng = random.Random(seed)
    lengths: list[int] = []
    branchings: list[int] = []
    all_returns: list[list[float]] = []
    for _ in range(num_games):
        state = game.new_initial_state()
        steps = 0
        while not state.is_terminal():
            if state.is_chance_node():
                state.apply_action(rng.choice([o for o, _ in state.chance_outcomes()]))
                continue
            legal = state.legal_actions()
            branchings.append(len(legal))
            state.apply_action(rng.choice(legal))
            steps += 1
        lengths.append(steps)
        all_returns.append(state.returns())
    n = game.num_players()
    best_seat = [0] * n
    for rets in all_returns:
        best_seat[max(range(n), key=lambda p: rets[p])] += 1
    return {
        "game": short_name,
        "num_games": num_games,
        "mean_length": sum(lengths) / len(lengths),
        "mean_branching": sum(branchings) / len(branchings),
        "mean_returns": [
            sum(r[p] for r in all_returns) / num_games for p in range(n)
        ],
        "best_seat_counts": best_seat,
    }
