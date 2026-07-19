"""Green Lane MINI ground truth: enumerate the tree, solve with CFR+, report
exploitability trend and the equilibrium behaviour at the most-reached
information sets. Run:  python experiments/green-lane/analyze_mini.py
"""

from __future__ import annotations

import json
import time
from collections import defaultdict

import pyspiel
from open_spiel.python.algorithms import cfr, exploitability

import glcommon

SHORT_NAME = "greenlane_mini"
CFR_ITERATIONS = 400
EXPL_EVERY = 50


def census(game: pyspiel.Game) -> dict[str, int]:
    """Exhaustive tree walk: node/terminal/infoset counts and max depth."""
    decision_nodes = 0
    terminals = 0
    infosets: dict[int, set[str]] = {0: set(), 1: set()}
    max_depth = 0

    stack = [(game.new_initial_state(), 0)]
    while stack:
        state, depth = stack.pop()
        max_depth = max(max_depth, depth)
        if state.is_terminal():
            terminals += 1
            continue
        if state.is_chance_node():
            for action, _ in state.chance_outcomes():
                child = state.clone()
                child.apply_action(action)
                stack.append((child, depth + 1))
            continue
        decision_nodes += 1
        player = state.current_player()
        infosets[player].add(state.information_state_string(player))
        for action in state.legal_actions():
            child = state.clone()
            child.apply_action(action)
            stack.append((child, depth + 1))

    return {
        "decision_nodes": decision_nodes,
        "terminals": terminals,
        "infosets_p0": len(infosets[0]),
        "infosets_p1": len(infosets[1]),
        "max_depth": max_depth,
    }


def reach_weighted_strategies(
    game: pyspiel.Game, avg_policy: object
) -> list[dict[str, object]]:
    """Walk the tree under the average policy; per infoset, accumulate reach
    probability and record the mixed strategy with human-readable actions."""
    reach: dict[str, float] = defaultdict(float)
    strategy: dict[str, dict[str, float]] = {}
    owner: dict[str, int] = {}
    depth_of: dict[str, int] = {}

    def walk(state: pyspiel.State, prob: float, depth: int) -> None:
        if prob == 0 or state.is_terminal():
            return
        if state.is_chance_node():
            for action, p in state.chance_outcomes():
                child = state.clone()
                child.apply_action(action)
                walk(child, prob * p, depth)
            return
        player = state.current_player()
        key = state.information_state_string(player)
        probs = avg_policy.action_probabilities(state)  # type: ignore[attr-defined]
        if key not in strategy:
            strategy[key] = {
                state.action_to_string(player, a): p for a, p in probs.items()
            }
            owner[key] = player
            depth_of[key] = depth
        reach[key] += prob
        for action, p in probs.items():
            child = state.clone()
            child.apply_action(action)
            walk(child, prob * p, depth + 1)

    walk(game.new_initial_state(), 1.0, 0)
    rows = [
        {
            "reach": reach[key],
            "player": owner[key],
            "depth": depth_of[key],
            "strategy": strategy[key],
            "infoset": key,
        }
        for key in reach
    ]
    rows.sort(key=lambda r: -r["reach"])  # type: ignore[operator]
    return rows


def expected_value(game: pyspiel.Game, avg_policy: object) -> float:
    """P0's expected return under the average policy profile."""

    def walk(state: pyspiel.State, prob: float) -> float:
        if state.is_terminal():
            return prob * state.returns()[0]
        total = 0.0
        if state.is_chance_node():
            for action, p in state.chance_outcomes():
                child = state.clone()
                child.apply_action(action)
                total += walk(child, prob * p)
            return total
        probs = avg_policy.action_probabilities(state)  # type: ignore[attr-defined]
        for action, p in probs.items():
            if p == 0:
                continue
            child = state.clone()
            child.apply_action(action)
            total += walk(child, prob * p)
        return total

    return walk(game.new_initial_state(), 1.0)


def describe(row: dict[str, object]) -> str:
    strat = ", ".join(f"{a}:{p:.3f}" for a, p in row["strategy"].items())  # type: ignore[union-attr]
    return (
        f"reach={row['reach']:.3f} P{row['player']} depth={row['depth']}  "
        f"[{strat}]"
    )


def main() -> None:
    glcommon.register_all(num_seeds=1)
    game = pyspiel.load_game(SHORT_NAME)

    t0 = time.perf_counter()
    stats = census(game)
    print(f"tree census ({time.perf_counter() - t0:.1f}s): {stats}")

    solver = cfr.CFRPlusSolver(game)
    trend: list[tuple[int, float]] = []
    t0 = time.perf_counter()
    for it in range(1, CFR_ITERATIONS + 1):
        solver.evaluate_and_update_policy()
        if it % EXPL_EVERY == 0 or it == 1:
            expl = exploitability.exploitability(game, solver.average_policy())
            trend.append((it, expl))
            print(
                f"iter {it:4d}  exploitability {expl:.5f}  "
                f"({time.perf_counter() - t0:.0f}s)"
            )

    avg = solver.average_policy()
    value = expected_value(game, avg)
    print(f"\ngame value (P0 expected return at equilibrium): {value:+.4f}")

    rows = reach_weighted_strategies(game, avg)
    mixed = [
        r
        for r in rows
        if sum(1 for p in r["strategy"].values() if p > 0.02) > 1  # type: ignore[union-attr]
    ]
    print(f"\ninfosets reached: {len(rows)}; mixed (>1 action above 2%): {len(mixed)}")
    print("\ntop reach-weighted decisions (equilibrium strategies):")
    for row in rows[:14]:
        print("  " + describe(row))

    out = {
        "census": stats,
        "exploitability_trend": trend,
        "game_value_p0": value,
        "infosets_reached": len(rows),
        "infosets_mixed": len(mixed),
        "top_decisions": [
            {k: row[k] for k in ("reach", "player", "depth", "strategy")}
            for row in rows[:20]
        ],
    }
    with open(glcommon.HERE / "results_mini.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nwrote results_mini.json")


if __name__ == "__main__":
    main()
