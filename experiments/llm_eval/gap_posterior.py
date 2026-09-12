"""The literal posterior over a deterministic subsample of `gap_windows`'
population, per cell (matchup).

    python -m experiments.llm_eval.gap_posterior \\
        --windows windows.jsonl --out posterior.jsonl \\
        --per-cell 50 --subsample-seed 0 --ess-floor 200 \\
        --min-proposals 2000 --max-proposals 64000

Selection, per cell, is STRATIFIED: every R1-abstains window (the primary
analysis subset — `belief-calibration-spec.md` §3, "R1 abstains") is taken
before any R1-fires window is drawn, up to `--per-cell`. When abstains are the
scarcer class in a cell — the common shape, since most standing claims are not
provably false — this exhausts them first rather than spending budget
proportionally, so the primary subset is the one the budget targets; any
leftover budget draws from R1-fires. Both strata are sampled with
`random.Random(--subsample-seed)`, advanced once per matchup in sorted
matchup order, so the subsample is a pure function of the windows file and the
seed regardless of dict iteration order.

`gap_sampler.estimate` runs with an ADAPTIVE proposal budget per window:
start at `--min-proposals`, double while the effective sample size is under
`--ess-floor` and the budget is under `--max-proposals`. A window whose budget
is exhausted with zero accepted proposals (`gap_sampler.estimate` raises
`ValueError`) is DROPPED and logged — never silently absent, since a silent
cap here would read as "the sampler covered every selected window."

Contract
--------
Assumes: `--windows` is `gap_windows`' own JSONL output — in particular every
record's `infostate` is what the observer's view rendered at that window, and
`r1_widened` is `infostate.provably_false` already evaluated there.
Establishes: one JSONL record per window the adaptive budget converged (or
exhausted without dropping), carrying every field of its window record plus
the posterior estimate and enough of the sampler's own diagnostics
(`ess`, `n_accepted`, `split_half`, `rejects`) to judge whether to trust it.
Illegal after: reading `p_lie` as ground truth, or trusting a record whose
`converged` is `False` without reading `split_half` first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import gap_sampler
from .gap_replay import make_checker

DEFAULT_GAME_PATH = "docs/games/cheat.cardlang"


def _load_windows(path: Path) -> list[dict[str, Any]]:
    """`gap_windows`' own JSONL output. Plain text — this module's population
    is always this repo's own enumeration output, never the gzipped archive."""
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _derive_seed(subsample_seed: int, matchup: str, seed: int, step: int) -> int:
    """A posterior-sampling seed that is a pure function of the subsample seed
    and the window's own identity, so a rerun with the same inputs proposes
    the same worlds — independent of `gap_sampler`'s own per-index derivation,
    which starts from whatever this returns."""
    material = f"{subsample_seed}:{matchup}:{seed}:{step}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _select(
    windows: list[dict[str, Any]],
    per_cell: int,
    rng: random.Random,
    observer_agent: str | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The stratified subsample for one cell, plus what was available to draw
    from — the counts `main` logs so a short subsample is never silent."""
    eligible = [
        w for w in windows if observer_agent is None or w["observer_agent"] == observer_agent
    ]
    abstains = sorted(
        (w for w in eligible if not w["r1_widened"]), key=lambda w: (w["seed"], w["step"])
    )
    fires = sorted(
        (w for w in eligible if w["r1_widened"]), key=lambda w: (w["seed"], w["step"])
    )
    take_a = min(len(abstains), per_cell)
    chosen_a = rng.sample(abstains, take_a)
    take_f = min(len(fires), per_cell - take_a)
    chosen_f = rng.sample(fires, take_f)
    counts = {
        "eligible": len(eligible),
        "abstains_available": len(abstains),
        "fires_available": len(fires),
        "abstains_taken": take_a,
        "fires_taken": take_f,
    }
    return chosen_a + chosen_f, counts


@dataclass
class _Adaptive:
    estimate: gap_sampler.Estimate
    n_proposed_final: int
    converged: bool


def _adaptive_estimate(
    infostate: str,
    *,
    sampler_seed: int,
    min_proposals: int,
    max_proposals: int,
    ess_floor: float,
    check: Callable[[gap_sampler.World], None] | None,
    check_count: int,
) -> _Adaptive:
    """`gap_sampler.estimate`, doubling the proposal budget while the ESS is
    under floor and the budget is under the cap. Raises `ValueError` — the
    same exception `gap_sampler.estimate` raises on zero accepted proposals —
    when even the maximum budget accepts nothing; `main` is the one that
    decides that means "drop and log", not this function."""
    proposals = min_proposals
    while True:
        est = gap_sampler.estimate(
            infostate,
            seed=sampler_seed,
            samples=proposals,
            proposal=gap_sampler.SMART,
            check=check,
            check_count=check_count,
        )
        converged = est.ess >= ess_floor
        if converged or proposals >= max_proposals:
            return _Adaptive(estimate=est, n_proposed_final=proposals, converged=converged)
        proposals = min(proposals * 2, max_proposals)


def run(
    windows: list[dict[str, Any]],
    *,
    per_cell: int,
    subsample_seed: int,
    ess_floor: float,
    min_proposals: int,
    max_proposals: int,
    check_count: int,
    game_path: str,
    observer_agent: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """The whole pipeline over an already-loaded window population.

    Returns the posterior records and a log of every drop or non-convergence
    — `main` prints the log; tests can assert on it directly.
    """
    by_matchup: dict[str, list[dict[str, Any]]] = {}
    for w in windows:
        by_matchup.setdefault(w["matchup"], []).append(w)

    rng = random.Random(subsample_seed)
    out: list[dict[str, Any]] = []
    log: list[str] = []
    for matchup in sorted(by_matchup):
        chosen, counts = _select(by_matchup[matchup], per_cell, rng, observer_agent)
        log.append(
            f"{matchup}: eligible={counts['eligible']} "
            f"abstains={counts['abstains_taken']}/{counts['abstains_available']} "
            f"fires={counts['fires_taken']}/{counts['fires_available']} "
            f"selected={len(chosen)}/{per_cell}"
        )
        for w in sorted(chosen, key=lambda w: (w["seed"], w["step"])):
            sampler_seed = _derive_seed(subsample_seed, matchup, w["seed"], w["step"])
            check = (
                make_checker(w["infostate"], game_path, seed=w["seed"])
                if check_count
                else None
            )
            try:
                result = _adaptive_estimate(
                    w["infostate"],
                    sampler_seed=sampler_seed,
                    min_proposals=min_proposals,
                    max_proposals=max_proposals,
                    ess_floor=ess_floor,
                    check=check,
                    check_count=check_count,
                )
            except ValueError as e:
                log.append(
                    f"DROPPED {matchup} seed={w['seed']} step={w['step']}: {e}"
                )
                continue
            if not result.converged:
                log.append(
                    f"NOT CONVERGED {matchup} seed={w['seed']} step={w['step']}: "
                    f"ess={result.estimate.ess:.1f} < floor {ess_floor} at "
                    f"{result.n_proposed_final} proposals (max {max_proposals})"
                )
            est = result.estimate
            record = {
                k: v for k, v in w.items() if k != "infostate"
            }
            record.update(
                p_lie=est.p_lie,
                ess=est.ess,
                n_proposed=result.n_proposed_final,
                n_accepted=est.n_accepted,
                split_half=list(est.split_half),
                n_checked=est.n_checked,
                rejects=[list(r) for r in est.rejects],
                converged=result.converged,
                sampler_seed=sampler_seed,
            )
            out.append(record)
    return out, log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--windows", required=True, help="gap_windows' JSONL output")
    ap.add_argument("--out", required=True, help="output posterior JSONL path")
    ap.add_argument("--per-cell", type=int, required=True, help="subsample size per matchup")
    ap.add_argument("--subsample-seed", type=int, required=True)
    ap.add_argument("--ess-floor", type=float, required=True)
    ap.add_argument("--min-proposals", type=int, required=True)
    ap.add_argument("--max-proposals", type=int, required=True)
    ap.add_argument(
        "--check-count", type=int, default=0,
        help="replay this many accepted worlds per window against the engine",
    )
    ap.add_argument("--game-path", default=DEFAULT_GAME_PATH)
    ap.add_argument(
        "--observer-agent", default=None,
        help="restrict eligible windows to this observer_agent (default: every seat)",
    )
    args = ap.parse_args(argv)

    windows = _load_windows(Path(args.windows))
    records, log = run(
        windows,
        per_cell=args.per_cell,
        subsample_seed=args.subsample_seed,
        ess_floor=args.ess_floor,
        min_proposals=args.min_proposals,
        max_proposals=args.max_proposals,
        check_count=args.check_count,
        game_path=args.game_path,
        observer_agent=args.observer_agent,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    for line in log:
        print(line)
    converged = sum(1 for r in records if r["converged"])
    print(
        f"\nwrote {len(records)} posterior record(s) to {out_path} "
        f"({converged}/{len(records)} converged at ess-floor {args.ess_floor})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
