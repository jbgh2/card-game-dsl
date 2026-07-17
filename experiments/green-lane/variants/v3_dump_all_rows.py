"""V3-graded mini: CFR+ (300 iters, deterministic — identical profile to
solve.py's) then dump EVERY reach-weighted infoset row including the infoset
string, so the sequencing question (A-then-7 vs 7-then-A) can be answered
from infosets below solve.py's top-14 cut.

Run from experiments/green-lane:
  PYTHONPATH=... python -u variants/v3_dump_all_rows.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyspiel
from open_spiel.python.algorithms import cfr

import glcommon
from analyze_mini import expected_value, reach_weighted_strategies

ITERATIONS = 300
HERE = Path(__file__).resolve().parent


def main() -> None:
    glcommon.install_replay_memo()
    glcommon.install_infostate_memo()
    path = HERE / "v3-graded-mini.cardlang"
    glcommon.register("gl_v3_dump", path.name, num_seeds=1, base_dir=path.parent)
    game = pyspiel.load_game("gl_v3_dump")

    solver = cfr.CFRPlusSolver(game)
    t0 = time.perf_counter()
    for it in range(1, ITERATIONS + 1):
        solver.evaluate_and_update_policy()
        if it % 50 == 0:
            print(f"iter {it} ({time.perf_counter() - t0:.0f}s)", flush=True)

    avg = solver.average_policy()
    value = expected_value(game, avg)
    rows = reach_weighted_strategies(game, avg)
    out = {
        "iterations": ITERATIONS,
        "game_value_p0": value,
        "rows": rows,  # every reached infoset, with the infoset string
    }
    with open(HERE / "v3-graded-mini.allrows.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"value {value:+.4f}; {len(rows)} rows -> v3-graded-mini.allrows.json")


if __name__ == "__main__":
    main()
