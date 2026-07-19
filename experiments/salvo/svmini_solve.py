"""Exact-tier evaluation for salvo-mini: census, CFR+ with exploitability
trend, game value, and the staging-mixing analysis (does the first
committer randomize placements at equilibrium?).

Modes:

  --scan N                  classify seeds 0..N-1 by the dealt locations'
                            target extremity (curation for fixed-deal picks)
  --seeds 3,17,41           fixed-deal exact solves, one per seed
                            (single-seed chance root = Green Lane's shape)
  --sample N                ONE deal-sampled game with seeds 0..N-1 at the
                            chance root (the overnight run)

Long-run contract compliance: census prints before solving; a calibration
burst prints the measured per-iteration rate and the ETA for the requested
iterations before committing; checkpoints rewrite the output JSON
atomically every EXPL_EVERY iterations (interrupted runs keep every
finished stage, marked "partial"); a sampled census that would overrun the
replay memo refuses loudly with the measured numbers instead of thrashing.

Run:  PYTHONHASHSEED=0 python experiments/salvo/svmini_solve.py --seeds 0 --iters 800
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyspiel
from open_spiel.python.algorithms import cfr, exploitability

import svmini
from cardlang.openspiel import replay
from cardlang.openspiel.game import CardlangState

HERE = Path(__file__).resolve().parent
EXPL_EVERY = 50

# ---------------------------------------------------------------------------

_orig_infostate = CardlangState.information_state_string


def install_infostate_memo() -> None:
    cache: dict[tuple[str, int, tuple[int, ...], int], str] = {}

    def memoized(self: CardlangState, player: int | None = None) -> str:
        if self._seed is None:
            return _orig_infostate(self, player)
        p = self.current_player() if player is None else player
        key = (self._path, self._seed, tuple(self._history_ids), int(p))
        if key not in cache:
            cache[key] = _orig_infostate(self, player)
        return cache[key]

    CardlangState.information_state_string = memoized  # type: ignore[method-assign]


def census(game: pyspiel.Game, node_cap: int) -> dict[str, int]:
    """Full-tree walk (also warms the replay memo). Refuses past node_cap."""
    counts = {"chance": 0, "decision": 0, "terminal": 0, "max_depth": 0}

    def walk(state: Any, depth: int) -> None:
        total = counts["chance"] + counts["decision"] + counts["terminal"]
        if total > node_cap:
            raise RuntimeError(
                f"census exceeded node cap {node_cap} — the sampled tree is too "
                f"large for the replay memo; reduce --sample"
            )
        counts["max_depth"] = max(counts["max_depth"], depth)
        if state.is_terminal():
            counts["terminal"] += 1
            return
        if state.is_chance_node():
            counts["chance"] += 1
            for a, _ in state.chance_outcomes():
                walk(state.child(a), depth + 1)
            return
        counts["decision"] += 1
        for a in state.legal_actions():
            walk(state.child(a), depth + 1)

    walk(game.new_initial_state(), 0)
    return counts


def expected_value(game: pyspiel.Game, policy: Any) -> float:
    def walk(state: Any, prob: float) -> float:
        if state.is_terminal():
            return prob * state.returns()[0]
        if state.is_chance_node():
            return sum(walk(state.child(a), prob * p) for a, p in state.chance_outcomes())
        ap = policy.action_probabilities(state)
        return sum(walk(state.child(a), prob * p) for a, p in ap.items() if p > 0)

    return walk(game.new_initial_state(), 1.0)


def reach_weighted(game: pyspiel.Game, policy: Any) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}

    def walk(state: Any, prob: float, depth: int) -> None:
        if state.is_terminal():
            return
        if state.is_chance_node():
            for a, p in state.chance_outcomes():
                walk(state.child(a), prob * p, depth + 1)
            return
        player = state.current_player()
        info = state.information_state_string(player)
        ap = policy.action_probabilities(state)
        row = rows.setdefault(
            info,
            {
                "player": player,
                "depth": depth,
                "reach": 0.0,
                "strategy": {state.action_to_string(player, a): round(p, 4) for a, p in ap.items()},
            },
        )
        row["reach"] += prob
        for a, p in ap.items():
            if p > 0:
                walk(state.child(a), prob * p, depth + 1)

    walk(game.new_initial_state(), 1.0, 0)
    out = list(rows.values())
    out.sort(key=lambda r: -r["reach"])
    return out


def solve_one(short_name: str, seeds: list[int], iters: int, stop_expl: float, out_path: Path) -> dict[str, Any]:
    path = svmini.register(short_name, seeds)
    game = pyspiel.load_game(short_name)

    t0 = time.perf_counter()
    stats = census(game, node_cap=int(svmini.MEMO_MAX * 0.8))
    t_census = time.perf_counter() - t0
    print(f"[{short_name}] census {stats} ({t_census:.1f}s, memo {svmini.memo_info().currsize})")

    result: dict[str, Any] = {
        "game": svmini.FILENAME,
        "seeds": seeds,
        "iterations_requested": iters,
        "census": stats,
        "exploitability_trend": [],
        "partial": True,
    }

    def checkpoint() -> None:
        tmp = out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=2))
        os.replace(tmp, out_path)

    solver = cfr.CFRPlusSolver(game)
    # calibration burst -> ETA before committing (long-run contract)
    t0 = time.perf_counter()
    for _ in range(3):
        solver.evaluate_and_update_policy()
    per_it = (time.perf_counter() - t0) / 3
    print(f"[{short_name}] calibration {per_it * 1000:.0f} ms/iter -> ETA {per_it * iters / 60:.1f} min for {iters} iters")

    t0 = time.perf_counter()
    done = 3
    for it in range(4, iters + 1):
        solver.evaluate_and_update_policy()
        done = it
        if it % EXPL_EVERY == 0 or it == iters:
            expl = exploitability.exploitability(game, solver.average_policy())
            result["exploitability_trend"].append((it, expl))
            checkpoint()
            print(f"[{short_name}] iter {it:5d} exploitability {expl:.5f} ({time.perf_counter() - t0:.0f}s)")
            if expl < stop_expl:
                print(f"[{short_name}] stop: exploitability under {stop_expl}")
                break

    avg = solver.average_policy()
    rows = reach_weighted(game, avg)
    decision_rows = [r for r in rows if r["reach"] > 1e-6]
    mixed = [
        r for r in decision_rows
        if sum(1 for p in r["strategy"].values() if p >= 0.02) > 1
    ]
    # The headline infosets: the first committer's round-1 offer is the first
    # decision after the chance node (depth 1); its card pick sits at depth 2.
    first_offers = [r for r in decision_rows if r["depth"] == 1]
    result.update(
        {
            "iterations_done": done,
            "game_value_p0": expected_value(game, avg),
            "infosets_reached": len(decision_rows),
            "infosets_mixed": len(mixed),
            "mixed_share": round(len(mixed) / len(decision_rows), 4) if decision_rows else None,
            "first_committer_round1": first_offers,
            "top_decisions": rows[:20],
            "partial": False,
        }
    )
    checkpoint()
    print(
        f"[{short_name}] value {result['game_value_p0']:+.3f}  "
        f"mixed {len(mixed)}/{len(decision_rows)}  wrote {out_path}"
    )
    return result


def scan(n: int) -> None:
    """Classify seeds by dealt-location extremity for fixed-deal curation."""
    path = str(HERE / svmini.FILENAME)
    game_ast, space = replay.load(path)
    ridx = {r: i for i, r in enumerate(game_ast.ranking)}
    # game_ast.ranking lists ranks strongest-first; distances are orientation-
    # invariant, but the pool's CENTER must be derived, not assumed.
    pool_idx = sorted(ridx[r] for r in ("A", "2", "3", "4", "5", "6"))
    mid = (pool_idx[0] + pool_idx[-1]) / 2
    for seed in range(n):
        r = replay.run(path, seed, ())
        locs = []
        for l in ("a", "b"):
            zone = r.rs.zones.singles[f"location_{l}"]
            c = list(zone.cards)[0]
            locs.append((f"{c.rank}{c.suit[0]}", abs(ridx[c.rank] - mid)))
        e = sorted(x[1] for x in locs)
        # pool extremities run 0.5 (ranks 3/4) to 2.5 (A/6)
        klass = "edge" if e[0] >= 2 else ("mid" if e[1] <= 1 else "mixed")
        print(f"seed {seed:3d}  {locs[0][0]:>3} {locs[1][0]:>3}  extremity {e}  {klass}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", type=int, default=None)
    ap.add_argument("--seeds", type=str, default=None, help="comma list: one fixed-deal solve per seed")
    ap.add_argument("--sample", type=int, default=None, help="one game, seeds 0..N-1 sampled at the root")
    ap.add_argument("--iters", type=int, default=800)
    ap.add_argument("--stop-expl", type=float, default=0.05)
    args = ap.parse_args()

    if args.scan is not None:
        scan(args.scan)
        return

    install_infostate_memo()
    if args.seeds is not None:
        combined = []
        for s in [int(x) for x in args.seeds.split(",")]:
            out = HERE / f"results_mini_seed{s}.json"
            combined.append(solve_one(f"svmini_s{s}", [s], args.iters, args.stop_expl, out))
        summary = [
            {
                "seeds": r["seeds"],
                "value": r["game_value_p0"],
                "mixed_share": r["mixed_share"],
                "expl": r["exploitability_trend"][-1][1] if r["exploitability_trend"] else None,
            }
            for r in combined
        ]
        print(json.dumps(summary, indent=2))
    elif args.sample is not None:
        out = HERE / f"results_mini_sample{args.sample}.json"
        solve_one(f"svmini_n{args.sample}", list(range(args.sample)), args.iters, args.stop_expl, out)
    else:
        ap.error("one of --scan / --seeds / --sample is required")


if __name__ == "__main__":
    main()
