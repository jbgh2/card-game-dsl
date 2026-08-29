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

# Versioned the way `triage.CURVES[...]["results"]` is: each round's committed
# output is a dated artifact the report cites, so the name moves with the round
# rather than a re-run overwriting the round the report still quotes.
RESULTS = "results_liveness_r5.json"

BINS = (("mid", 0, 1), ("near", 2, 3), ("edge", 4, 6))


def mid_index(ridx: dict[str, int]) -> int:
    """The middle rung of the natural A..K line — rank 7 — as the game's own
    rank index spells it. Derived rather than written down because the joker
    takes a slot in the declared ranking and shifts every natural rank past
    it; extremity is a distance along the natural scale either way, and a
    location is never a joker (the deal filters them out)."""
    natural = sorted((v for r, v in ridx.items() if r != "Joker"))
    return natural[len(natural) // 2]


def bin_of(extremity: int) -> str:
    for name, lo, hi in BINS:
        if lo <= extremity <= hi:
            return name
    raise AssertionError(extremity)


def drive(
    space: Any, policy: str, seed: int, lv: Any, ridx: dict[str, int], mid_idx: int,
    ladder: dict[str, int],
) -> list[dict[str, Any]]:
    """One mirror playout; returns three location records.

    This rig scores locations itself rather than through `triage.playout`, so
    it carries its own mirror pin at the foot: the per-location values it
    reports must reproduce the DSL's terminal returns exactly. Without it a
    scoring rule the game does not use would publish as `margin` and
    `unclaimed` — and a tie, which is what leaves a location unclaimed, is
    exactly what a missing bonus moves."""
    rng = random.Random(seed * 7919 + 13)
    history: list[int] = []
    ctx = triage.Ctx()
    while True:
        r = replay.run(triage.GAME_PATH, seed, tuple(history))
        if isinstance(r, replay.TerminalNode):
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
    assert isinstance(rp, replay.DecisionNode)
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
    all_vals: list[list[int]] = []
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
            vals.append(sum(lv(c, target) for c in cs) + triage.combo_bonus(cs, ladder))
        all_vals.append(vals)
        records.append(
            {
                "extremity": abs(t_idx - mid_idx),
                "n_cards": len(cards_by_p[0]) + len(cards_by_p[1]),
                # Jokers are outside the rank scale — they score a flat
                # perfect hit — so they carry no distance to average.
                "distances": [
                    abs(ridx[c.rank] - t_idx)
                    for cs in cards_by_p
                    for c in cs
                    if c.suit != "joker"
                ],
                "affinity": sum(1 for cs in cards_by_p for c in cs if c.suit == target.suit),
                "margin": abs(vals[0] - vals[1]),
                "tied": vals[0] == vals[1],
            }
        )
    # Mirror pin: locations won and grand totals recomputed above must equal
    # the terminal returns' encoding (final = locations * 1000 + total).
    locs_won = [round(x / 1000) for x in r.returns]
    totals = [int(x) - 1000 * lw for x, lw in zip(r.returns, locs_won)]
    for p in (0, 1):
        won = sum(1 for v in all_vals if v[p] > v[1 - p])
        assert won == locs_won[p], f"mirror drift: locs_won {won} != {locs_won[p]}"
        assert sum(v[p] for v in all_vals) == totals[p], (
            f"mirror drift: totals {sum(v[p] for v in all_vals)} != {totals[p]}"
        )
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1000)
    ap.add_argument(
        "--seed-start", type=int, default=0,
        help="first deal; the sighted policy here carries the tuned knobs, so a "
             "headline run starts past the tuning sweep's range",
    )
    args = ap.parse_args()

    triage.TUN = dict(triage.CURVES["base"])
    triage.GAME_PATH = str(HERE / triage.CURVES["base"]["game"])
    game_ast, space = replay.load(triage.GAME_PATH)
    ridx = triage.rank_index_map(game_ast)
    lv = triage.make_loc_value(ridx, triage.CURVES["base"]["base"])
    mid_idx = mid_index(ridx)
    ladder = triage.natural_ladder(tuple(game_ast.ranking))

    out: dict[str, Any] = {"seeds": args.seeds, "seed_start": args.seed_start, "policies": {}}
    for policy in ("sighted", "blind", "random"):
        per_bin: dict[str, dict[str, Any]] = {
            name: {"n": 0, "cards": [], "dists": [], "aff_cards": 0, "tot_cards": 0, "margins": [], "ties": 0, "least": 0}
            for name, _, _ in BINS
        }
        for seed in range(args.seed_start, args.seed_start + args.seeds):
            recs = drive(space, policy, seed, lv, ridx, mid_idx, ladder)
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

    (HERE / RESULTS).write_text(json.dumps(out, indent=2))
    print(f"wrote {HERE / RESULTS}")


if __name__ == "__main__":
    main()
