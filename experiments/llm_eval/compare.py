"""Compare two matchups rate by rate — the arm-delta report.

Built on `verify.tally`, deliberately not on `metrics.aggregate`: the comparison
that decides whether an arm did anything is computed by the independent
recomputation path, not by the code being audited. Every number here is a ratio
of two raw counts read out of the transcripts, with the counts printed beside it.

Significance is Fisher's exact test on the 2x2 of the two arms' numerators and
denominators. Hand-rolled from `math.comb` rather than taken from scipy, which
the harness does not otherwise depend on: the arithmetic is exact, so a reader
can reproduce a p-value without installing anything.

    python -m experiments.llm_eval.compare \\
        --control llm_cheap_rendered_bluffer \\
        --arm llm_cheap_reason_first_bluffer

Contract
--------
Assumes: both matchups ran the same seeds, opponents and rendering, differing in
one variable — which is a property of `config.yaml`, not something this module
can check. It prints the seed sets so a mismatch is visible.
Establishes: a per-rate delta with its exact two-sided p-value.
Illegal after: quoting an arm delta without the denominators beside it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from math import comb, sqrt
from pathlib import Path
from typing import Any

from .verify import RATES, _load, _stem, _transcripts


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher's exact p for [[a, b], [c, d]].

    Sums the hypergeometric probability of every table with the same margins
    whose probability is no greater than the observed one. Exact, and with the
    counts this harness produces (hundreds, not millions) fast enough to be
    unremarkable.
    """
    n = a + b + c + d
    if n == 0 or (a + b) == 0 or (c + d) == 0 or (a + c) == 0 or (b + d) == 0:
        return 1.0
    row1, col1 = a + b, a + c

    def prob(x: int) -> float:
        return (
            comb(row1, x) * comb(n - row1, col1 - x) / comb(n, col1)
        )

    observed = prob(a)
    # A strictly-greater test would drop tables tying the observed probability,
    # which for symmetric margins is most of the mass. The epsilon absorbs the
    # float error in comparing two independently-computed products.
    total = sum(
        p
        for x in range(max(0, col1 - (n - row1)), min(row1, col1) + 1)
        if (p := prob(x)) <= observed * (1 + 1e-9)
    )
    return min(1.0, total)


def wald_ci(num: int, den: int) -> tuple[float, float]:
    """95% Wald interval. Reported because a rate over 20 windows and a rate over
    600 print identically otherwise."""
    if den == 0:
        return (0.0, 0.0)
    p = num / den
    half = 1.96 * sqrt(max(p * (1 - p), 0.0) / den)
    return (max(0.0, p - half), min(1.0, p + half))


# --- what counts as a result ------------------------------------------------
#
# PRE-REGISTERED, and the commit that introduced it precedes the reason-first
# N=10 data. `RATES` holds ten rates; testing all ten at alpha=0.05 gives a
# family-wise error rate near 40%, so "one of them came out significant" is the
# expected outcome of an arm that does nothing at all. Naming the endpoint after
# seeing the table is how a null result becomes a finding.
#
# The hypothesis is about over-accusation: the default arm makes the model commit
# to an action before writing a word of justification, and both models challenged
# roughly half of all opportunities at sub-50% precision. `challenge_rate` is
# therefore the endpoint — the direct measure of how often the model acts when
# given the choice. It is a one-line change to re-point this, and doing so after
# looking at data is exactly the move it exists to prevent.
PRIMARY_ENDPOINT = "challenge_rate"

# Every other rate is exploratory: reported with its p-value, flagged `~` rather
# than `*`, and not to be quoted as a result without a confirmatory run. The
# threshold is Bonferroni over the ten rates in `RATES`, which is conservative
# and deliberately so — these are hypothesis generators, not findings.
ALPHA_EXPL = 0.05 / 10


# Rates `verify.RATES` does not carry, because they are per-GAME counts rather
# than ratios of two counters. The wrong-accusation figure is the one that
# explained why models with better lie detection still lost every game: a wrong
# call costs the entire pile, so its per-game rate matters more than precision.
DERIVED: list[tuple[str, str]] = [
    ("wrong_accusations_per_game", "wrong_accusations"),
    ("challenges_per_game", "challenges_made"),
    ("provable_faced_per_game", "provable_faced"),
]


def enrich(c: Counter[str]) -> Counter[str]:
    """Counts derivable from `tally`'s output, added so both arms compute them
    the same way."""
    c["wrong_accusations"] = c["challenges_made"] - c["challenges_correct"]
    return c


def load(root: Path, name: str) -> list[dict[str, Any]]:
    for path in _transcripts(root):
        if _stem(path) == name:
            return _load(path)
    raise SystemExit(f"no transcript for matchup {name!r} under {root}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--dir", default="experiments/llm_eval/results/transcripts")
    ap.add_argument("--control", required=True, help="the baseline matchup name")
    ap.add_argument("--arm", required=True, help="the matchup under test")
    ap.add_argument(
        "--who",
        default=None,
        help="agent label to compare (default: the one common to both, "
        "refusing if that is ambiguous)",
    )
    ap.add_argument(
        "--common-seeds",
        action="store_true",
        help="restrict both arms to the seeds they BOTH played. For a run cut "
        "short by a budget cap this is the only defensible comparison: the "
        "alternative pits N games against M different deals.",
    )
    args = ap.parse_args(argv)

    root = Path(args.dir)
    from .verify import arm_audit, report_arm, tally

    left, right = load(root, args.control), load(root, args.arm)

    if args.who:
        who = args.who
    else:
        names = [
            {n for r in recs for n in r["seats"].values() if n.startswith("llm")}
            for recs in (left, right)
        ]
        common = names[0] & names[1]
        if len(common) != 1:
            raise SystemExit(
                f"cannot pick an agent automatically: control has {sorted(names[0])}, "
                f"arm has {sorted(names[1])} — pass --who"
            )
        who = common.pop()

    if args.common_seeds:
        shared = {r["seed"] for r in left} & {r["seed"] for r in right}
        if not shared:
            raise SystemExit("the two arms share no seeds — nothing to compare")
        dropped = (len(left) - len(shared)) + (len(right) - len(shared))
        left = [r for r in left if r["seed"] in shared]
        right = [r for r in right if r["seed"] in shared]
        # Loud, because silently discarding games is how a truncated run gets
        # reported as if it were the run that was planned.
        print(
            f"--common-seeds: restricted to the {len(shared)} seed(s) both arms "
            f"played; dropped {dropped} game(s)."
        )

    # Seeds first: the whole comparison rests on the two runs being the same
    # games, which this module cannot enforce and must therefore expose.
    seeds_l = sorted(r["seed"] for r in left)
    seeds_r = sorted(r["seed"] for r in right)
    print(f"agent      {who}")
    print(f"control    {args.control:38} N={len(left):<3} seeds={seeds_l}")
    print(f"arm        {args.arm:38} N={len(right):<3} seeds={seeds_r}")
    if seeds_l != seeds_r:
        print(
            "\n  ** SEED SETS DIFFER — the arms are not the same games, so every\n"
            "     delta below mixes the format change with a different deal. **"
        )

    a_counts, b_counts = enrich(tally(left, who)), enrich(tally(right, who))

    print(f"\n{'rate':30} {'control':>18} {'arm':>18}   {'delta':>8} {'p':>9}")
    print("-" * 90)
    marked = 0
    for name, num, den in RATES:
        an, ad, bn, bd = a_counts[num], a_counts[den], b_counts[num], b_counts[den]
        if not ad and not bd:
            continue
        ar = an / ad if ad else float("nan")
        br = bn / bd if bd else float("nan")
        p = fisher_exact(an, ad - an, bn, bd - bn)
        primary = name == PRIMARY_ENDPOINT
        # `*` is reserved for the ONE pre-registered endpoint; everything else is
        # exploratory and marked `~`, however small its p. See `PRIMARY_ENDPOINT`.
        flag = (" *" if p < 0.05 else "") if primary else (" ~" if p < ALPHA_EXPL else "")
        marked += bool(flag.strip() == "~")
        print(
            f"{name:30} {f'{an}/{ad}={ar:.3f}':>18} {f'{bn}/{bd}={br:.3f}':>18}   "
            f"{br - ar:>+8.3f} {p:>9.2}{flag}"
        )
        lo_a, hi_a = wald_ci(an, ad)
        lo_b, hi_b = wald_ci(bn, bd)
        print(
            f"{'':30} {f'[{lo_a:.3f},{hi_a:.3f}]':>18} {f'[{lo_b:.3f},{hi_b:.3f}]':>18}"
        )

    print(
        f"\n  * = the pre-registered endpoint ({PRIMARY_ENDPOINT}), p < 0.05\n"
        f"  ~ = exploratory, p < {ALPHA_EXPL:.3f} (Bonferroni over {len(RATES)} "
        f"rates) — a hypothesis, not a result"
    )
    if marked:
        print(
            f"    {marked} exploratory rate(s) flagged. Testing {len(RATES)} rates at "
            f"0.05 gives a ~40% chance of at least one false positive, which is why\n"
            f"    they are not marked `*`. Quote them only after a confirmatory run."
        )

    print(f"\n{'per game':30} {'control':>18} {'arm':>18}   {'delta':>8}")
    print("-" * 90)
    for name, key in DERIVED:
        ag, bg = a_counts["games"], b_counts["games"]
        ar = a_counts[key] / ag if ag else float("nan")
        br = b_counts[key] / bg if bg else float("nan")
        print(
            f"{name:30} {f'{a_counts[key]}/{ag}={ar:.2f}':>18} "
            f"{f'{b_counts[key]}/{bg}={br:.2f}':>18}   {br - ar:>+8.2f}"
        )

    # The arm audit last, because it is the thing that says whether any of the
    # above is attributable to the manipulation at all.
    for label, recs in ((args.control, left), (args.arm, right)):
        c = arm_audit(recs, who)
        if c["decisions"]:
            report_arm(f"{label} :: {who}  ARM AUDIT (N={len(recs)})", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
