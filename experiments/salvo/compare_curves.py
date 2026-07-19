"""Side-by-side of Salvo arena configs (results_triage*.json files).

Default: every canonical config file present, in design-history order
(full, zc, cap, recon). Pass filenames to compare a custom set, e.g. the
hold-threshold sweep:

  python compare_curves.py results_triage_recon.json \
      results_triage_recon_hb9.json results_triage_recon_hb11.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

CANONICAL = [
    "results_triage.json",        # round 1: no cap, all-positive curve
    "results_triage_zc.json",     # round 2: zero-centered curve (refuted)
    "results_triage_cap.json",    # round 3 baseline: capacity 4
    "results_triage_recon.json",  # round 3: capacity + recon draw
    "results_triage_base.json",   # round 4: adopted base, tuned knobs
]


def label_of(name: str, data: dict) -> str:
    base = data.get("curve", "full")
    hb = data.get("tuning", {}).get("hold_below")
    stem = name.removeprefix("results_triage").removesuffix(".json").strip("_") or "full"
    if "hb" in stem.rsplit("_", 1)[-1]:
        return f"{base} hb={hb:g}"
    return {"full": "round1", "zc": "zero-centered", "cap": "capacity", "recon": "cap+recon", "base": "base (tuned)"}.get(base, base)


def fmt_cell(p: dict | None) -> str:
    if p is None:
        return f"{'—':>21}"
    a, b = p["pairing"].split(" vs ")
    wr = p["win_rate"]
    if a == b:
        return f"{'draws ' + format(wr.get('draw', 0.0), '.1%'):>21}"
    return f"{wr.get(a, 0.0):>7.1%} /{wr.get(b, 0.0):>7.1%}"


def main() -> None:
    names = sys.argv[1:] or [n for n in CANONICAL if (HERE / n).exists()]
    tables: list[tuple[str, dict[str, dict]]] = []
    for n in names:
        data = json.loads((HERE / n).read_text())
        tables.append((label_of(n, data), {p["pairing"]: p for p in data["pairings"]}))

    all_pairings: list[str] = []
    for _, t in tables:
        for p in t:
            if p not in all_pairings:
                all_pairings.append(p)

    header = f"{'pairing':<28}" + "".join(f" {lab:>21}" for lab, _ in tables)
    print(header)
    for pairing in all_pairings:
        print(f"{pairing:<28}" + "".join(f" {fmt_cell(t.get(pairing))}" for _, t in tables))

    print("\nmean commits/holds per game and margins (mean/median, unclaimed):")
    for lab, t in tables:
        for pairing, p in t.items():
            mc, mh = p["mean_commits"], p["mean_holds"]
            usage = "  ".join(f"{k} {mc[k]:.2f}c/{mh[k]:.2f}h" for k in mc)
            print(
                f"  [{lab}] {pairing:<26} {usage}"
                f"   margins {p['margin_mean']:.1f}/{p['margin_median']}"
                f"  uncl {p['unclaimed_rate_per_loc']:.1%}"
            )
        div = [
            f"{pairing}: {p['sighted_divergence_rate']:.1%}"
            for pairing, p in t.items()
            if "sighted_divergence_rate" in p
        ]
        if div:
            print(f"  [{lab}] divergence  " + "  ".join(div))


if __name__ == "__main__":
    main()
