"""Side-by-side of the curve A/B: round-1 all-positive (results_triage.json)
vs zero-centered (results_triage_zc.json). Prints the shared pairings with
win rates and commit/hold usage, then the zc-only commit-count probes.

Run:  python experiments/salvo/compare_curves.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str) -> dict[str, dict]:
    data = json.loads((HERE / name).read_text())
    return {p["pairing"]: p for p in data["pairings"]}


def fmt_row(p: dict | None) -> str:
    if p is None:
        return f"{'—':>24}"
    a, b = p["pairing"].split(" vs ")
    wr = p["win_rate"]
    wa, wb = wr.get(a, 0.0), wr.get(b, 0.0)
    if a == b:  # mirror rows pool both seats; only draws are meaningful
        return f"{'(mirror) draws ' + format(wr.get('draw', 0.0), '.1%'):>24}"
    return f"{wa:>7.1%} /{wb:>7.1%} ({wr.get('draw', 0.0):.1%} draw)"


def main() -> None:
    full = load("results_triage.json")
    zc = load("results_triage_zc.json")

    print(f"{'pairing':<28} {'all-positive':>24}   {'zero-centered':>24}")
    for pairing in list(full) + [p for p in zc if p not in full]:
        print(f"{pairing:<28} {fmt_row(full.get(pairing))}   {fmt_row(zc.get(pairing))}")

    print("\ncommit/hold usage (mean per game, non-mirror pairings):")
    for label, table in (("all-positive", full), ("zero-centered", zc)):
        for pairing, p in table.items():
            a, b = pairing.split(" vs ")
            if a == b:
                continue
            mc, mh = p["mean_commits"], p["mean_holds"]
            print(
                f"  [{label}] {pairing:<26}"
                + "  ".join(f"{k}: {mc[k]:.2f}c/{mh[k]:.2f}h" for k in mc)
            )

    print("\nmargins (mean/median) and unclaimed-tie rate per location:")
    for label, table in (("all-positive", full), ("zero-centered", zc)):
        for pairing, p in table.items():
            print(
                f"  [{label}] {pairing:<26} {p['margin_mean']:>6.1f}/{p['margin_median']:<4}"
                f"  unclaimed {p['unclaimed_rate_per_loc']:.1%}"
            )


if __name__ == "__main__":
    main()
