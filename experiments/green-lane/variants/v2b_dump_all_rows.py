"""Dump EVERY reach-weighted infoset row (including the infoset string) for a
Green Lane mini variant, after the same deterministic CFR+ solve as solve.py
(same iteration count -> identical average profile). Written for the V2b
bounty-conditioning question — the infoset strings carry the public
`tokens=`/`pending=` state, so inspect rates can be conditioned on the
responder's bounty state at matched decisions.

Run from experiments/green-lane:
  PYTHONPATH=... python -u variants/v2b_dump_all_rows.py <file.cardlang> [iters] [out.json]
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


def main() -> None:
    path = Path(sys.argv[1]).resolve()
    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else path.with_suffix(".allrows.json")
    glcommon.install_replay_memo()
    glcommon.install_infostate_memo()
    short = "gl_dump_" + path.stem.replace("-", "_")
    glcommon.register(short, path.name, num_seeds=1, base_dir=path.parent)
    game = pyspiel.load_game(short)

    solver = cfr.CFRPlusSolver(game)
    t0 = time.perf_counter()
    for it in range(1, iterations + 1):
        solver.evaluate_and_update_policy()
        if it % 100 == 0:
            print(f"iter {it} ({time.perf_counter() - t0:.0f}s)", flush=True)

    avg = solver.average_policy()
    value = expected_value(game, avg)
    rows = reach_weighted_strategies(game, avg)
    with open(out, "w") as fh:
        json.dump({"iterations": iterations, "game_value_p0": value, "rows": rows}, fh, indent=2)
    print(f"value {value:+.4f}; {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
