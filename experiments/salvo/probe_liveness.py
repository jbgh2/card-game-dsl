"""Per-location liveness probe (DESIGN.md evaluation question 3, deferred
from round 1): do locations play the way the proximity design intends —
edge targets as precision knife fights, mid targets as volume wars — and
does competent play degenerate into scripted abandonment of any class of
location (the Blotto watch)?

Method: mirror playouts (both seats the same policy, no seating asymmetry)
on the adopted base game at tuned knobs, for sighted / blind / random.
Every game contributes three location records: the location's target
extremity (distance of its target rank from the mid rank 7 on the A..K
line, 0..6), and per player the cards committed there, their distances to
the target, affinity matches, and the final values.

Binning: mid (extremity 0-1: targets 6-8), near (2-3: 4-5 and 9-10),
edge (4-6: A-3 and J-K). Reported per bin per policy:

- volume:      mean cards committed per location (both players)
- tightness:   mean |rank - target| over committed cards (knife-fight
               locations should be LOW at edges if the design works)
- affinity:    fraction of committed cards matching the location suit
- margin:      mean final |value difference|; unclaimed-tie rate
- abandonment: how often this bin's location was the game's
               least-contested (fewest total cards), normalized by how
               often the bin appears at all — a share consistently and
               heavily above its appearance share = a concede script

Run:  PYTHONHASHSEED=0 python experiments/salvo/probe_liveness.py [--seeds N]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import triage
from cardlang.openspiel import replay

HERE = Path(__file__).resolve().parent

MID_IDX = 6  # rank 7 on the aces-low A..K line
BINS = (("mid", 0, 1), ("near", 2, 3), ("edge", 4, 6))


def bin_of(extremity: int) -> str:
    for name, lo, hi in BINS:
        if lo <= extremity <= hi:
            return name
    raise AssertionError(extremity)


def drive(space: Any, policy: str, seed: int, lv: Any, ridx: dict[str, int]) -> list[dict[str, Any]]:
    """One mirror playout; returns three location records."""
    rng = random.Random(seed * 7919 + 13)
    history: list[int] = []
    ctx = triage.Ctx()
    while True:
        r = replay.run(triage.GAME_PATH, seed, tuple(history))
        if isinstance(r, replay.Terminal):
            break
        kind = "offer" if all(aid >= space._name_base for aid in r.legal) else "pick"
        pol = triage.POLICIES[policy]
        aid = pol(kind, r, space, ctx, lv, ridx, rng)
        if kind == "offer":
            lab = space._names[aid - space._name_base]
            if lab.startswith("commit_"):
                ctx.pending_loc = lab.removeprefix("commit_")
        history.append(aid)

    # Inspect the final world at the last pause (plus the pending pick).
    rp = replay.run(triage.GAME_PATH, seed, tuple(history[:-1]))
    assert isinstance(rp, replay.Pause)
    pend = None
    if history and history[-1] < space._name_base:
        pend = space.decode(history[-1])
    pend_loc = None
    if pend is not None:
        for a in reversed(history[:-1]):
            if a >= space._name_base:
                lab = space._names[a - space._name_base]
                if lab.startswith("commit_"):
                    pend_loc = lab.removeprefix("commit_")
                break

    records = []
    for l in triage.LOCS:
        target = triage.zone_cards(rp.rs, f"location_{l}")[0]
        t_idx = ridx[target.rank]
        cards_by_p: list[list[Any]] = []
        vals = []
        for p in (0, 1):
            cs = triage.zone_cards(rp.rs, f"army_{l}", p) + triage.zone_cards(rp.rs, f"staged_{l}", p)
            if pend is not None and pend_loc == l and p == rp.player:
                cs = cs + [pend]
            cards_by_p.append(cs)
            vals.append(sum(lv(c, target) for c in cs))
        records.append(
            {
                "extremity": abs(t_idx - MID_IDX),
                "n_cards": len(cards_by_p[0]) + len(cards_by_p[1]),
                "distances": [abs(ridx[c.rank] - t_idx) for cs in cards_by_p for c in cs],
                "affinity": sum(1 for cs in cards_by_p for c in cs if c.suit == target.suit),
                "margin": abs(vals[0] - vals[1]),
                "tied": vals[0] == vals[1],
            }
        )
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1000)
    args = ap.parse_args()

    triage.TUN = dict(triage.CURVES["base"])
    triage.GAME_PATH = str(HERE / triage.CURVES["base"]["game"])
    game_ast, space = replay.load(triage.GAME_PATH)
    ridx = triage.rank_index_map(game_ast)
    lv = triage.make_loc_value(ridx, triage.CURVES["base"]["base"])

    out: dict[str, Any] = {"seeds": args.seeds, "policies": {}}
    for policy in ("sighted", "blind", "random"):
        per_bin: dict[str, dict[str, Any]] = {
            name: {"n": 0, "cards": [], "dists": [], "aff_cards": 0, "tot_cards": 0, "margins": [], "ties": 0, "least": 0}
            for name, _, _ in BINS
        }
        for seed in range(args.seeds):
            recs = drive(space, policy, seed, lv, ridx)
            least_n = min(r["n_cards"] for r in recs)
            for r in recs:
                b = per_bin[bin_of(r["extremity"])]
                b["n"] += 1
                b["cards"].append(r["n_cards"])
                b["dists"].extend(r["distances"])
                b["aff_cards"] += r["affinity"]
                b["tot_cards"] += r["n_cards"]
                b["margins"].append(r["margin"])
                b["ties"] += int(r["tied"])
                # ties in least-contested split the credit evenly
                if r["n_cards"] == least_n:
                    b["least"] += 1 / sum(1 for x in recs if x["n_cards"] == least_n)
        total_locs = 3 * args.seeds
        summary = {}
        for name, _, _ in BINS:
            b = per_bin[name]
            if not b["n"]:
                continue
            summary[name] = {
                "appearance_share": round(b["n"] / total_locs, 4),
                "mean_cards": round(statistics.mean(b["cards"]), 2),
                "mean_distance": round(statistics.mean(b["dists"]), 2) if b["dists"] else None,
                "affinity_rate": round(b["aff_cards"] / b["tot_cards"], 4) if b["tot_cards"] else None,
                "margin_mean": round(statistics.mean(b["margins"]), 2),
                "unclaimed_rate": round(b["ties"] / b["n"], 4),
                "least_contested_share": round(b["least"] / args.seeds, 4),
            }
        out["policies"][policy] = summary
        print(json.dumps({policy: summary}))
        sys.stdout.flush()

    (HERE / "results_liveness.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {HERE / 'results_liveness.json'}")


if __name__ == "__main__":
    main()
