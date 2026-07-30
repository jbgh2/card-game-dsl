"""One-stop exact evaluation for any SMALL Green Lane variant: census, CFR+
solve with exploitability trend, game value, mixedness, top reach-weighted
equilibrium decisions, and a naive-rule gap (best {ship rule} x {inspect
rule} combo against the equilibrium). Everything a design iteration needs to
compare a variant against the baseline, in one JSON.

Run:  python experiments/green-lane/solve.py <file.cardlang> [iterations] [out.json]

The variant must be a 2-player zero-sum cardlang game with no chance (the
registration uses one seed) whose response vocabulary is {inspect, wave} —
i.e. any Green Lane rules variant. Keep it mini-sized: the tree is walked
exhaustively (census + exact heuristic evaluation), so a few thousand nodes
is the practical ceiling.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import glcommon
import pyspiel
from analyze_exploit import exploitation
from analyze_heuristics import RulePolicy, joint_value
from analyze_mini import census, expected_value, reach_weighted_strategies
from open_spiel.python.algorithms import cfr, exploitability

EXPL_EVERY = 100


def solve(path: Path, iterations: int) -> dict[str, object]:
    short_name = "gl_" + path.stem.replace("-", "_")
    glcommon.register(short_name, path.name, num_seeds=1, base_dir=path.parent)
    game = pyspiel.load_game(short_name)

    t0 = time.perf_counter()
    stats = census(game)
    print(f"census ({time.perf_counter() - t0:.0f}s): {stats}")

    solver = cfr.CFRPlusSolver(game)
    trend: list[tuple[int, float]] = []
    t0 = time.perf_counter()
    for it in range(1, iterations + 1):
        solver.evaluate_and_update_policy()
        if it % EXPL_EVERY == 0 or it == iterations:
            expl = exploitability.exploitability(game, solver.average_policy())
            trend.append((it, expl))
            print(f"iter {it:4d} exploitability {expl:.4f} ({time.perf_counter() - t0:.0f}s)")

    avg = solver.average_policy()
    value = expected_value(game, avg)
    rows = reach_weighted_strategies(game, avg)
    mixed = [
        r
        for r in rows
        if sum(1 for p in r["strategy"].values() if p > 0.02) > 1  # type: ignore[union-attr]
    ]

    grid = []
    for s in ("ace_first", "ace_last", "uniform"):
        for i in ("always", "never", "coin_flip"):
            rule = RulePolicy(f"{s}/{i}", s, i)
            as_p0 = joint_value(game, rule, avg)
            as_p1 = -joint_value(game, avg, rule)
            br_p0, br_p1 = exploitation(game, rule)
            grid.append(
                {
                    "rule": rule.name,
                    "mean_vs_equilibrium": (as_p0 + as_p1) / 2,
                    "mean_vs_best_response": (br_p0 + br_p1) / 2,
                }
            )
    # The depth headline: how much even the SAFEST naive rule bleeds once the
    # opponent adapts (closer to 0 = shallower game).
    best_naive = max(grid, key=lambda r: r["mean_vs_best_response"])  # type: ignore[arg-type,return-value]

    return {
        "file": path.name,
        "iterations": iterations,
        "census": stats,
        "exploitability_final": trend[-1][1],
        "exploitability_trend": trend,
        "game_value_p0": value,
        "infosets_reached": len(rows),
        "infosets_mixed": len(mixed),
        "mixed_share": len(mixed) / len(rows),
        "best_naive_rule": best_naive,
        "naive_grid": grid,
        "top_decisions": [
            {k: row[k] for k in ("reach", "player", "depth", "strategy")}
            for row in rows[:14]
        ],
    }


def main() -> None:
    path = Path(sys.argv[1]).resolve()
    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else path.with_suffix(".results.json")
    glcommon.install_replay_memo()
    glcommon.install_infostate_memo()
    result = solve(path, iterations)
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"value {result['game_value_p0']:+.3f}  mixed {result['infosets_mixed']}/"
          f"{result['infosets_reached']}  best naive {result['best_naive_rule']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
