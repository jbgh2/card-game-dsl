"""Independent recomputation of the `cheat_gap` study's headline numbers, from
`gap_windows`' and `gap_posterior`'s own JSONL output — no engine, no sampler,
stdlib only.

    python -m experiments.llm_eval.verify_cheat_gap \\
        --windows windows.jsonl --posterior posterior.jsonl [--out AUDIT.txt]

This module shares no code with either producer: it reads the two files as
plain JSON lines and does its own arithmetic, so a bug in `gap_sampler`'s
weighting or `gap_windows`' classification cannot hide behind a checker built
from the same code. It is the `verify.py` pattern — the audit re-derives and
never trusts — applied to this study, and its own
completeness argument is the same shape: it never imports `cardlang`,
`pyspiel`, `gap_sampler` or any sibling module of this package (pinned by
`tests/test_cheat_gap_verify.py`'s `ast` scrape), so the one thing it can be
wrong about is its own arithmetic, checked directly against a hand-computed
fixture.

The **reader's gap** of a seat class, over a subset of its windows, is
`(observed lie rate) - (mean R_literal)` on the windows it CHALLENGED; the
**deceiver's gap** is the same over the windows it ALLOWED
(`gap_sampler.estimate` is `R_literal`; `PREREGISTRATION_CHEAT_GAP.md` defines
both gaps and names which is the registered endpoint).
Both are computed here, per cell (matchup) x seat class (`observer_agent`) x
subset (all / R1-abstains / R1-fires) x action (challenged / allowed / any), as
percentage points. The **selection contrast** — the gap over the windows a
seat challenged minus the gap over every window it faced — is the statistic
that isolates reading beyond the literal channel (`contrast_stat` says why the
raw gap cannot), and the null control's expected zero is a statement about
the contrast, not the raw gap.

Contract
--------
Assumes: `--windows` is `gap_windows`' JSONL output and `--posterior` is
`gap_posterior`'s JSONL output over a (possibly strict) subsample of it — every
posterior record carries `p_lie`, `lie`, `r1_widened`, `observer_agent`,
`action`, `matchup` and `seed`.
Establishes: a plain-text AUDIT report — every rate as `n / d = value` (or
`null` over a zero denominator), a bootstrap 95% interval per bucket and per
selection contrast resampling GAMES, the exact two-sided sign test of the
per-game contrast against zero on the R1-abstains subset
(`contrast_sign_test`, the registered endpoint's test), the null-control noise
floor for all-rule cells on the contrast, and a paired-by-seed sign test
between two named cells.
Illegal after: quoting a GAP without its bootstrap interval, or a p-value from
`paired_seed_comparison` as anything but exploratory — that comparison is the
capability gradient, which `PREREGISTRATION_CHEAT_GAP.md` marks `~`.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import random
from pathlib import Path
from collections.abc import Callable
from typing import Any

#: Resamples for every bootstrap interval in this module, and the seed that
#: makes the reported interval reproducible from these two files alone.
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0

SUBSETS = ("all", "abstains", "fires")
ACTIONS = ("challenged", "allowed", "any")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSON lines, plain or gzipped by suffix — the archive commits derived
    records gzipped, the same way it commits transcripts."""
    out: list[dict[str, Any]] = []
    opener = gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")
    with opener as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _rate_str(num: int, den: int) -> str:
    if den == 0:
        return f"{num} / {den} = null"
    return f"{num} / {den} = {num / den:.4f}"


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def _action_bucket(action: str) -> str:
    if action == "call_cheat":
        return "challenged"
    if action == "allow":
        return "allowed"
    raise ValueError(f"a window action must be 'call_cheat' or 'allow', got {action!r}")


def _in_subset(record: dict[str, Any], subset: str) -> bool:
    if subset == "all":
        return True
    if subset == "abstains":
        return not record["r1_widened"]
    if subset == "fires":
        return bool(record["r1_widened"])
    raise ValueError(f"unknown subset {subset!r}")


def bucket(
    records: list[dict[str, Any]], matchup: str, seat_class: str, subset: str, action: str
) -> list[dict[str, Any]]:
    """Every posterior record in one (cell, seat class, subset, action) cell."""
    return [
        r
        for r in records
        if r["matchup"] == matchup
        and r["observer_agent"] == seat_class
        and _in_subset(r, subset)
        and (action == "any" or _action_bucket(r["action"]) == action)
    ]


def gap_stat(records: list[dict[str, Any]]) -> float | None:
    """`(observed lie rate) - (mean R_literal)`, in percentage points, or
    `None` with no windows to compute either half from."""
    n = len(records)
    if n == 0:
        return None
    rate = sum(1 for r in records if r["lie"]) / n
    mean_r = sum(float(r["p_lie"]) for r in records) / n
    return (rate - mean_r) * 100.0


def contrast_stat(records: list[dict[str, Any]]) -> float | None:
    """The SELECTION CONTRAST: `gap_stat` over the windows the observer
    challenged minus `gap_stat` over every window it faced, in percentage
    points — `None` unless both halves have windows.

    The raw gap carries the literal reference's own miscalibration: under
    uniform card choice a claim is a lie in most consistent worlds whoever
    made it, so a challenger that ignores the cards still measures a large
    negative gap. The contrast removes that, and the base lie rate with it:
    a challenge decision that is independent of the cards leaves the
    challenged windows a random draw from all of them, so the two gaps agree
    and the contrast is zero in expectation. What remains is the part of
    the challenged windows' excess lie rate that the literal information at
    those windows does not explain."""
    challenged = [r for r in records if _action_bucket(r["action"]) == "challenged"]
    a = gap_stat(challenged)
    b = gap_stat(records)
    if a is None or b is None:
        return None
    return a - b


def bootstrap_gap(
    records: list[dict[str, Any]],
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    stat: Callable[[list[dict[str, Any]]], float | None] = gap_stat,
) -> tuple[float, float] | None:
    """A 95% percentile interval for `stat` (`gap_stat` unless another is
    named, `contrast_stat` being the other), resampling GAMES (`(matchup,
    seed)` pairs) with replacement — not windows, since windows within one
    game share a hand and are not independent trials."""
    if not records:
        return None
    by_game: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for r in records:
        by_game.setdefault((r["matchup"], r["seed"]), []).append(r)
    games = sorted(by_game)
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(n_resamples):
        pooled = [row for g in (rng.choice(games) for _ in games) for row in by_game[g]]
        value = stat(pooled)
        if value is not None:
            stats.append(value)
    if not stats:
        return None
    stats.sort()
    lo = stats[max(0, min(len(stats) - 1, round(0.025 * (len(stats) - 1))))]
    hi = stats[max(0, min(len(stats) - 1, round(0.975 * (len(stats) - 1))))]
    return lo, hi


def residual_summary(records: list[dict[str, Any]]) -> tuple[float, float] | None:
    """Mean and population standard deviation of `lie - p_lie` per window —
    the per-window calibration residual, not the pooled gap."""
    if not records:
        return None
    residuals = [float(r["lie"]) - r["p_lie"] for r in records]
    mean = sum(residuals) / len(residuals)
    variance = sum((x - mean) ** 2 for x in residuals) / len(residuals)
    return mean, math.sqrt(variance)


def _per_seed_gap(records: list[dict[str, Any]]) -> dict[int, float]:
    by_seed: dict[int, list[dict[str, Any]]] = {}
    for r in records:
        by_seed.setdefault(r["seed"], []).append(r)
    out: dict[int, float] = {}
    for seed, rows in by_seed.items():
        stat = gap_stat(rows)
        if stat is not None:
            out[seed] = stat
    return out


def sign_test(pairs: list[tuple[float, float]]) -> tuple[int, int, int, float]:
    """Exact two-sided sign test on paired differences (`verify_kuhn.sign_test`'s
    arithmetic, reproduced here rather than imported — this module imports
    nothing of the harness)."""
    up = sum(1 for a, b in pairs if b > a)
    down = sum(1 for a, b in pairs if b < a)
    tied = len(pairs) - up - down
    n = up + down
    if n == 0:
        return up, down, tied, 1.0
    k = min(up, down)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return up, down, tied, min(1.0, 2 * tail)


def per_seed_contrast(records: list[dict[str, Any]]) -> dict[int, float]:
    """The selection contrast of each game (seed) separately, for the games
    that carry one.

    A game enters only if it offers the observer BOTH a challenged and an
    allowed window in this bucket. With challenges alone `gap_stat` over the
    challenged windows is `gap_stat` over all of them, so the contrast is
    identically zero — a degenerate value that a sign test would count as a
    tie and read as evidence of no effect. Such a game carries no contrast and
    is absent here rather than scored."""
    by_seed: dict[int, list[dict[str, Any]]] = {}
    for r in records:
        by_seed.setdefault(r["seed"], []).append(r)
    out: dict[int, float] = {}
    for seed, rows in by_seed.items():
        buckets = {_action_bucket(r["action"]) for r in rows}
        if not {"challenged", "allowed"} <= buckets:
            continue
        stat = contrast_stat(rows)
        if stat is not None:
            out[seed] = stat
    return out


def contrast_sign_test(records: list[dict[str, Any]]) -> tuple[int, int, int, float]:
    """`(n_games, n_positive, n_negative, p)` — the per-game selection
    contrast against zero, under the exact two-sided `sign_test`.

    The test the study's primary endpoint names: the bootstrap interval says
    how precisely the pooled contrast is measured, and this says how
    consistently the games agree on its sign. `n_games` is every game
    `per_seed_contrast` admits, so `n_games - n_positive - n_negative` is the
    count sitting exactly on zero."""
    contrasts = per_seed_contrast(records)
    pairs = [(0.0, value) for value in contrasts.values()]
    up, down, _tied, p = sign_test(pairs)
    return len(contrasts), up, down, p


def paired_seed_comparison(
    records_a: list[dict[str, Any]], records_b: list[dict[str, Any]]
) -> dict[str, Any]:
    """Per-seed gap differences between two already-bucketed record sets,
    paired by seed, scored with an exact two-sided sign test — the
    `compare.py` pattern for a quantity that is a gap rather than a rate."""
    ga, gb = _per_seed_gap(records_a), _per_seed_gap(records_b)
    shared = sorted(set(ga) & set(gb))
    pairs = [(ga[s], gb[s]) for s in shared]
    up, down, tied, p = sign_test(pairs)
    return {
        "shared_seeds": len(shared),
        "up": up,
        "down": down,
        "tied": tied,
        "p_two_sided": p,
        "pairs": pairs,
    }


def _cells(records: list[dict[str, Any]]) -> list[str]:
    return sorted({r["matchup"] for r in records})


def _seat_classes(records: list[dict[str, Any]], matchup: str) -> list[str]:
    return sorted({r["observer_agent"] for r in records if r["matchup"] == matchup})


def report(windows: list[dict[str, Any]], posterior: list[dict[str, Any]]) -> list[str]:
    """The whole AUDIT text, as lines — `main` prints them and optionally
    writes them to `--out`."""
    lines: list[str] = []
    total_windows: dict[str, int] = {}
    for w in windows:
        total_windows[w["matchup"]] = total_windows.get(w["matchup"], 0) + 1

    for matchup in _cells(posterior):
        lines.append(f"\n=== {matchup} ===")
        subsampled = sum(1 for r in posterior if r["matchup"] == matchup)
        lines.append(
            f"  windows enumerated: {total_windows.get(matchup, 0)}   "
            f"subsampled: {subsampled}"
        )
        for seat_class in _seat_classes(posterior, matchup):
            lines.append(f"\n  -- seat class: {seat_class} --")
            for subset in SUBSETS:
                for action in ACTIONS:
                    rows = bucket(posterior, matchup, seat_class, subset, action)
                    n = len(rows)
                    label = f"{subset:>8} / {action:<10}"
                    if n == 0:
                        lines.append(f"    {label}  n=0 (no windows)")
                        continue
                    lie_n = sum(1 for r in rows if r["lie"])
                    mean_r = sum(r["p_lie"] for r in rows) / n
                    gap = gap_stat(rows)
                    ci = bootstrap_gap(rows)
                    resid = residual_summary(rows)
                    lines.append(
                        f"    {label}  n={n:<4} lie_rate={_rate_str(lie_n, n)}  "
                        f"mean_R_literal={mean_r:.4f}  "
                        f"GAP={gap:+.2f}pp"
                        + (f"  95% CI=[{ci[0]:+.2f},{ci[1]:+.2f}]pp" if ci else "")
                    )
                    if resid is not None:
                        lines.append(
                            f"      residual (lie-p_lie): mean={resid[0]:+.4f} "
                            f"sd={resid[1]:.4f}"
                        )
                rows = bucket(posterior, matchup, seat_class, subset, "any")
                contrast = contrast_stat(rows)
                if contrast is None:
                    lines.append(f"    {subset:>8} / CONTRAST     n/a (no challenged windows)")
                    continue
                ci = bootstrap_gap(rows, stat=contrast_stat)
                lines.append(
                    f"    {subset:>8} / CONTRAST     "
                    f"GAP(challenged) - GAP(any) = {contrast:+.2f}pp"
                    + (f"  95% CI=[{ci[0]:+.2f},{ci[1]:+.2f}]pp" if ci else "")
                )
                if subset == "abstains":
                    n_games, pos, neg, p = contrast_sign_test(rows)
                    lines.append(
                        f"    {subset:>8} / SIGN TEST    per-game CONTRAST vs 0: "
                        f"n_games={n_games} pos={pos} neg={neg} "
                        f"p_two_sided={p:.5f}"
                    )

    lines.append("\n=== NULL CONTROL (noise floor) ===")
    lines.append(
        "  cells whose observers are ALL rule agents, on the R1-abstains "
        "subset, which a rule agent challenges by a coin flip independent of "
        "the cards: the SELECTION CONTRAST is zero in expectation and its "
        "interval is the instrument's noise floor. The raw GAP beside it is "
        "the literal reference's own miscalibration, a property of the "
        "reference and not of the reader."
    )
    for matchup in _cells(posterior):
        classes = _seat_classes(posterior, matchup)
        if not classes or any(not c.startswith("rule") for c in classes):
            continue
        rows = [r for r in posterior if r["matchup"] == matchup and not r["r1_widened"]]
        challenged = [r for r in rows if _action_bucket(r["action"]) == "challenged"]
        if not challenged:
            lines.append(f"  {matchup}: n=0 (no abstains-subset challenges)")
            continue
        contrast = contrast_stat(rows)
        c_ci = bootstrap_gap(rows, stat=contrast_stat)
        gap = gap_stat(challenged)
        g_ci = bootstrap_gap(challenged)
        assert contrast is not None and gap is not None
        lines.append(
            f"  {matchup}: n_challenged={len(challenged)} n_all={len(rows)} "
            f"CONTRAST={contrast:+.2f}pp"
            + (f"  95% CI=[{c_ci[0]:+.2f},{c_ci[1]:+.2f}]pp" if c_ci else "")
            + f"   raw GAP(challenged)={gap:+.2f}pp"
            + (f"  95% CI=[{g_ci[0]:+.2f},{g_ci[1]:+.2f}]pp" if g_ci else "")
        )

    lines.append(
        f"\n(bootstrap: {BOOTSTRAP_RESAMPLES} resamples over games, seed={BOOTSTRAP_SEED})"
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--windows", required=True)
    ap.add_argument("--posterior", required=True)
    ap.add_argument("--out", default=None, help="also write the report here")
    args = ap.parse_args(argv)

    windows = _load_jsonl(Path(args.windows))
    posterior = _load_jsonl(Path(args.posterior))
    lines = report(windows, posterior)
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
