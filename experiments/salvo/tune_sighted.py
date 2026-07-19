"""Re-tune the sighted policy's knobs for the adopted base rules
(capacity 4 + recon draw). The round-3 lesson: sighted's race weights
were calibrated to uncapped margins (~22 mean) and rarely fire at the
capped scale (~9 mean), so arena skill-gap numbers were a stale floor.

Method — coordinate sweep against FIXED-knob references (per-seat tuns
via triage.arena's `tuns`), 200 seeds per seating per cell:

  Stage A: hold_below x won/lost margin grid, candidate sighted vs the
           fixed reference blind_hold (hold_below 10) and vs blind;
           cell score = mean of the two win rates.
  Stage B: refine the stage-A winner over urgency_w x opp_staged_est.
  Stage C: headline measurement at 500 seeds: tuned sighted vs blind,
           vs blind_hold(10), vs OLD-knob sighted (via the sighted_old
           registration below), and the tuned mirror.

Output: results_tune.json (every cell + the winner). The winner's knobs
become the "base" config defaults in triage.py — update them in the
same change that commits this file's results.

Run:  PYTHONHASHSEED=0 python experiments/salvo/tune_sighted.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import triage
from cardlang.openspiel import replay

HERE = Path(__file__).resolve().parent

# Old knobs (rounds 1-3), kept for the stage-C comparison.
OLD = dict(triage.CURVES["base"], won_margin=25.0, lost_margin=25.0, hold_below=7.0)

# Fixed reference: the strongest simple opponent from the round-3 sweep.
REF_BLIND_HOLD = dict(OLD, hold_below=10.0)

SWEEP_SEEDS = 200
FINAL_SEEDS = 500


def cell(tun: dict[str, Any], space: Any, lv: Any, ridx: Any, seeds: int) -> dict[str, Any]:
    vs_bh = triage.arena(
        space, "sighted", "blind_hold", seeds, lv, ridx,
        tuns={"sighted": tun, "blind_hold": REF_BLIND_HOLD},
    )
    vs_b = triage.arena(
        space, "sighted", "blind", seeds, lv, ridx, tuns={"sighted": tun},
    )
    w_bh = vs_bh["win_rate"]["sighted"]
    w_b = vs_b["win_rate"]["sighted"]
    return {
        "knobs": {k: tun[k] for k in ("hold_below", "won_margin", "lost_margin", "urgency_w", "opp_staged_est")},
        "vs_blind_hold": w_bh,
        "vs_blind": w_b,
        "score": (w_bh + w_b) / 2,
    }


def main() -> None:
    triage.TUN = dict(triage.CURVES["base"])
    triage.GAME_PATH = str(HERE / triage.CURVES["base"]["game"])
    game_ast, space = replay.load(triage.GAME_PATH)
    ridx = triage.rank_index_map(game_ast)
    lv = triage.make_loc_value(ridx, triage.CURVES["base"]["base"])

    results: dict[str, Any] = {"sweep_seeds": SWEEP_SEEDS, "final_seeds": FINAL_SEEDS, "stage_a": [], "stage_b": []}

    # --- Stage A: hold_below x won/lost margin (tied) -----------------------
    best: dict[str, Any] | None = None
    for hb in (7.0, 9.0, 10.0, 11.0, 12.0):
        for wm in (8.0, 10.0, 12.0, 16.0, 25.0):
            tun = dict(OLD, hold_below=hb, won_margin=wm, lost_margin=wm)
            c = cell(tun, space, lv, ridx, SWEEP_SEEDS)
            results["stage_a"].append(c)
            print(json.dumps(c))
            sys.stdout.flush()
            if best is None or c["score"] > best["score"]:
                best = c

    assert best is not None
    print(f"# stage A winner: {best['knobs']} score {best['score']:.3f}")

    # --- Stage B: urgency x opponent-staged estimate around the winner ------
    a_knobs = best["knobs"]
    for uw in (1.0, 1.3, 1.6):
        for est in (8.0, 9.5, 11.0):
            tun = dict(OLD)
            tun.update(a_knobs)
            tun.update(urgency_w=uw, opp_staged_est=est)
            c = cell(tun, space, lv, ridx, SWEEP_SEEDS)
            results["stage_b"].append(c)
            print(json.dumps(c))
            sys.stdout.flush()
            if c["score"] > best["score"]:
                best = c

    tuned = dict(OLD, **best["knobs"])
    results["winner"] = best
    print(f"# overall winner: {best['knobs']} score {best['score']:.3f}")

    # --- Stage C: headline at 500 seeds ------------------------------------
    # Old-knob sighted seats under a distinct name so both sides can be
    # sighted with different tuns (name-keyed).
    triage.POLICIES["sighted_old"] = lambda kind, pause, space_, ctx, lv_, ridx_, rng, tun=None: (
        triage.sighted_policy(kind, pause, space_, ctx, lv_, ridx_, rng, tun=OLD)
    )
    final = {
        "tuned_vs_blind": triage.arena(space, "sighted", "blind", FINAL_SEEDS, lv, ridx, tuns={"sighted": tuned}),
        "tuned_vs_blind_hold10": triage.arena(
            space, "sighted", "blind_hold", FINAL_SEEDS, lv, ridx,
            tuns={"sighted": tuned, "blind_hold": REF_BLIND_HOLD},
        ),
        "tuned_vs_old": triage.arena(
            space, "sighted", "sighted_old", FINAL_SEEDS, lv, ridx, tuns={"sighted": tuned},
        ),
        "tuned_mirror": triage.arena(space, "sighted", "sighted", FINAL_SEEDS, lv, ridx, tuns={"sighted": tuned}),
    }
    results["final"] = final
    for k, v in final.items():
        print(json.dumps({k: {"win_rate": v["win_rate"], "margins": v["margin_mean"], "commits": v["mean_commits"], "holds": v["mean_holds"]}}))

    out = HERE / "results_tune.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
