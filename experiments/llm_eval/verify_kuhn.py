"""Kuhn's arithmetic: the recomputation, the solver cross-check, and the A/B.

The RECOMPUTATION is reached through the harness's single audit entry point,
which identifies the game from the transcript and delegates here:

    python -m experiments.llm_eval.verify --dir experiments/llm_eval/results_kuhn/transcripts

This module keeps its own CLI for the part that has no counterpart in the other
games — the pre-registered paired sign test over two arms (`--control`/`--arm`),
whose Cheat analogue is `compare.py`:

    python -m experiments.llm_eval.verify_kuhn --dir experiments/llm_eval/results_kuhn/runs/<stamp>

This deliberately does **not** call `kuhn.aggregate`. It re-derives every rate
with its own arithmetic straight from the transcripts, so a bug in the metrics
layer cannot hide behind a checker that shares its code. It reuses exactly one
thing from `kuhn`: the solver — `payoff`, `best_response` and `nash_policy` —
because reimplementing a best response to check a best response would be
checking a coin against its own reflection. What it does instead is verify the
solver against the transcripts' own recorded `returns`, which come from the
engine and not from this package at all.

Standard library only, apart from the solver import. No API key, no network, no
`pyspiel`.

Contract
--------
Assumes: transcripts written by `referee.play_game` for `cardlang_kuhn_poker`.
Establishes: every rate, recomputed; the paired sign test on the pre-registered
endpoint; and an assertion that the recorded terminal returns match what the
solver says that line of that deal is worth.
Illegal after: quoting a Kuhn number that this file has not reproduced.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
from collections import Counter, defaultdict
from typing import Any

from .kuhn import (
    DEALS,
    exploitability,
    infoset,
    infoset_keys,
    noise_floor,
    offered,
    payoff,
)


def _load(path: str) -> list[dict[str, Any]]:
    import gzip

    opener = gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") else open(
        path, encoding="utf-8"
    )
    with opener as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _reconstruct(record: dict[str, Any]) -> tuple[tuple[str, str], tuple[str, ...]]:
    """The deal and the line, from the decisions alone.

    Independent of anything the metrics layer stored: the cards come from each
    seat's own recorded fact, and the line from the actions in order.
    """
    cards: dict[int, str] = {}
    line: list[str] = []
    for decision in record["decisions"]:
        facts = decision["facts"]
        cards.setdefault(int(facts["seat"]), str(facts["card"]))
        line.append(str(facts["action"]))
    return (cards.get(0, "?"), cards.get(1, "?")), tuple(line)


def verify_transcript(path: str) -> dict[str, Any]:
    """Recompute one matchup's numbers from its transcript on disk."""
    return verify_records(os.path.basename(path), _load(path))


def verify_records(name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """The fold itself, over records already in hand.

    Separate from the loading so `verify.py --game` — the one entry point for
    every game's recomputation — can pass records it has already read and
    identified, without this module re-reading the file or re-deciding which
    game it is.
    """
    per_agent: dict[str, Counter[str]] = defaultdict(Counter)
    visits: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    chips: dict[str, float] = defaultdict(float)
    deals: Counter[str] = Counter()
    payoff_mismatches: list[str] = []

    for record in records:
        seats = {int(k): v for k, v in record["seats"].items()}
        deal, line = _reconstruct(record)

        # THE CROSS-CHECK. The engine wrote `returns`; the solver says what that
        # line of that deal is worth. They are computed by entirely separate
        # code — one is the DSL runtime through the adapter, the other is this
        # package's own table — so agreement is real evidence.
        if record["terminal"] and "?" not in deal:
            expected = payoff(deal, line)
            actual = float(record["returns"][0])
            if abs(expected - actual) > 1e-9:
                payoff_mismatches.append(
                    f"seed {record['seed']}: deal {deal} line {line} -> engine "
                    f"{actual}, solver {expected}"
                )
            deals["".join(deal)] += 1

        for seat, name in seats.items():
            per_agent[name]["games"] += 1
            if record["terminal"]:
                per_agent[name]["games_scored"] += 1
                chips[name] += float(record["returns"][seat])
                if float(record["returns"][seat]) > 0:
                    per_agent[name]["wins"] += 1

        for decision in record["decisions"]:
            facts = decision["facts"]
            name = seats[int(decision["player"])]
            counter = per_agent[name]
            counter["decisions"] += 1
            if decision.get("llm", {}).get("fallback"):
                counter["fallbacks"] += 1

            card = str(facts["card"])
            action = str(facts["action"])
            history = str(facts["history"])
            seat = int(facts["seat"])

            # Domination re-derived HERE from the payoff table, not read from the
            # recorded flag — the flag is what is being checked.
            hist = () if history == "open" else tuple(history.split("-"))
            facing_bet = hist[-1:] == ("bet",)
            if facing_bet and card in ("J", "K"):
                counter["dominated_offered"] += 1
                alternative = "call" if action == "fold" else "fold"
                sign = 1.0 if seat == 0 else -1.0
                consistent = [d for d in DEALS if d[seat] == card]
                worse = all(
                    sign * payoff(d, hist + (action,))
                    < sign * payoff(d, hist + (alternative,))
                    for d in consistent
                )
                if worse:
                    counter["dominated_taken"] += 1
            # A bluff is BETTING the card that cannot win a showdown, and only
            # where betting is on offer. Calling a bet with a Jack belongs to
            # `dominated` above; counting it here too would report a blunder as
            # a bluff and make the rate move with how often the opponent bets.
            if card == "J" and not facing_bet:
                counter["bluff_offered"] += 1
                if action == "bet":
                    counter["bluffs"] += 1

            visits[name][infoset(seat, card, hist)][action] += 1

    out: dict[str, Any] = {
        "transcript": name,
        "games": len(records),
        "deals": dict(sorted(deals.items())),
        "payoff_mismatches": payoff_mismatches,
        "agents": {},
    }
    for name, counter in sorted(per_agent.items()):
        seats_played = sorted({int(k[1]) for k in visits[name]})
        counts = {k: dict(v) for k, v in visits[name].items()}
        expl: list[float] = []
        floors: list[tuple[float, float]] = []
        for seat in seats_played:
            policy = {}
            for key in infoset_keys(seat):
                seen = counts.get(key, {})
                total = sum(seen.values())
                policy[key] = (
                    {a: seen.get(a, 0) / total for a in offered(key)}
                    if total
                    else {a: 0.5 for a in offered(key)}
                )
            expl.append(exploitability(policy, seat))
            floors.append(noise_floor(counts, seat))
        possible = [k for seat in seats_played for k in infoset_keys(seat)]
        # Every count named explicitly, not folded in from the Counter's keys: a
        # counter never incremented has no key at all, so a rate whose numerator
        # stayed at zero would go MISSING from the report rather than reading
        # zero — and "0 dominated actions" is the most quotable result here.
        counted = {
            key: int(counter[key])
            for key in (
                "games",
                "games_scored",
                "wins",
                "decisions",
                "fallbacks",
                "dominated_offered",
                "dominated_taken",
                "bluff_offered",
                "bluffs",
            )
        }
        out["agents"][name] = {
            **counted,
            "chips_per_hand": (
                chips[name] / counter["games_scored"] if counter["games_scored"] else None
            ),
            "win_rate": _rate(counter["wins"], counter["games_scored"]),
            "fallback_rate": _rate(counter["fallbacks"], counter["decisions"]),
            "dominated_action_rate": _rate(
                counter["dominated_taken"], counter["dominated_offered"]
            ),
            "bluff_rate": _rate(counter["bluffs"], counter["bluff_offered"]),
            "exploitability": (sum(expl) / len(expl)) if expl else None,
            "exploitability_noise_floor": (
                sum(m for m, _ in floors) / len(floors) if floors else None
            ),
            "exploitability_noise_floor_p95": (
                sum(p for _, p in floors) / len(floors) if floors else None
            ),
            "infoset_coverage": (
                sum(1 for k in possible if counts.get(k)) / len(possible)
                if possible
                else None
            ),
            "policy": {
                k: {a: round(v / sum(counts[k].values()), 4) for a, v in sorted(counts[k].items())}
                for k in sorted(counts)
            },
        }
    return out


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


# --- the pre-registered A/B -------------------------------------------------


def sign_test(pairs: list[tuple[float, float]]) -> tuple[int, int, int, float]:
    """Exact two-sided sign test on paired differences.

    Returns `(n_up, n_down, n_tied, p)`. Two-sided because the registered
    prediction has a direction but the report must be able to state a result
    that went the other way at the same threshold — which is exactly what
    happened to the Cheat experiment.
    """
    up = sum(1 for a, b in pairs if b > a)
    down = sum(1 for a, b in pairs if b < a)
    tied = len(pairs) - up - down
    n = up + down
    if n == 0:
        return up, down, tied, 1.0
    k = min(up, down)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return up, down, tied, min(1.0, 2 * tail)


def compare_arms(
    control_path: str, arm_path: str, endpoint: str = "dominated_action_rate"
) -> dict[str, Any]:
    """The pre-registered comparison, paired by seed.

    `PREREGISTRATION_KUHN.md` fixes the endpoint and the stopping rule; this
    only executes it. Pairing is by SEED, so the same deal is compared across
    arms and the deal draw cannot explain a difference.
    """
    def _key(record: dict[str, Any]) -> tuple[int, str]:
        """The experimental unit: a deal PLUS which seat the model sat in.

        Not the seed alone. Under balanced seating each seed is played once per
        seating, so keying on the seed would keep whichever game came last and
        silently discard half the run — and not at random, since the survivor is
        always the same seating. Measured before this was keyed properly: 150 of
        300 games dropped, every one of the survivors with the model at seat 1.
        """
        seat = next(s for s, name in record["seats"].items() if name.startswith("llm"))
        return int(record["seed"]), str(seat)

    control_records = _load(control_path)
    arm_records = _load(arm_path)
    control = {_key(r): r for r in control_records}
    arm = {_key(r): r for r in arm_records}
    if len(control) != len(control_records) or len(arm) != len(arm_records):
        raise ValueError(
            f"transcripts hold repeated (seed, seat) units — control "
            f"{len(control_records)} games to {len(control)} units, arm "
            f"{len(arm_records)} to {len(arm)}. Pairing would drop games "
            f"silently, which is what this check exists to prevent."
        )
    shared = sorted(set(control) & set(arm))

    def rate(record: dict[str, Any], skip_fallbacks: bool = False) -> tuple[int, int]:
        """Dominated actions taken over dominated actions offered, for the model.

        `skip_fallbacks` drops decisions where the model failed to parse twice
        and the harness played uniformly at random. Those are not the model's
        decisions, and a random choice facing a bet holding a Jack or a King
        takes the dominated action half the time — so leaving them in lets the
        harness's own parse failures contribute to the endpoint. Reported
        alongside the as-registered figure rather than instead of it: the
        pre-registration did not exclude them, and silently changing the
        denominator after the fact is the thing pre-registration exists to stop.
        """
        seats = {int(k): v for k, v in record["seats"].items()}
        taken = offered_ = 0
        for decision in record["decisions"]:
            facts = decision["facts"]
            if not seats[int(decision["player"])].startswith("llm"):
                continue
            if skip_fallbacks and (decision.get("llm") or {}).get("fallback"):
                continue
            if facts.get("dominated_offered"):
                offered_ += 1
                taken += bool(facts.get("dominated"))
        return taken, offered_

    pairs: list[tuple[float, float]] = []
    ca = cd = aa = ad = 0
    cnf_t = cnf_o = anf_t = anf_o = 0          # the same, fallbacks excluded
    for unit in shared:
        ct, co = rate(control[unit])
        at, ao = rate(arm[unit])
        ca += ct
        cd += co
        aa += at
        ad += ao
        t, o = rate(control[unit], skip_fallbacks=True)
        cnf_t += t
        cnf_o += o
        t, o = rate(arm[unit], skip_fallbacks=True)
        anf_t += t
        anf_o += o
        if co and ao:
            pairs.append((ct / co, at / ao))
    up, down, tied, p = sign_test(pairs)
    return {
        "endpoint": endpoint,
        "units_shared": len(shared),
        "units_are": "(deal seed, seat the model sat in)",
        "games_control": len(control_records),
        "games_arm": len(arm_records),
        "units_with_an_opportunity_in_both": len(pairs),
        "control": {"taken": ca, "offered": cd, "rate": _rate(ca, cd)},
        "arm": {"taken": aa, "offered": ad, "rate": _rate(aa, ad)},
        # The sensitivity the report quotes. Computed here so it is reproducible
        # from a committed tool rather than by hand.
        "control_excluding_fallbacks": {
            "taken": cnf_t, "offered": cnf_o, "rate": _rate(cnf_t, cnf_o)
        },
        "arm_excluding_fallbacks": {
            "taken": anf_t, "offered": anf_o, "rate": _rate(anf_t, anf_o)
        },
        "paired_sign_test": {"up": up, "down": down, "tied": tied, "p_two_sided": p},
    }


def report_records(name: str, records: list[dict[str, Any]]) -> int:
    """Print one matchup's recomputation; return the payoff-mismatch count.

    The solver cross-check is the part no rate table can carry: the engine wrote
    `returns` and this package's own table says what that line of that deal is
    worth, so agreement is evidence from two entirely separate computations.
    """
    result = verify_records(name, records)
    print(f"\n== {result['transcript']}  ({result['games']} games)")
    print(f"   deals: {result['deals']}")
    if result["payoff_mismatches"]:
        for line in result["payoff_mismatches"][:5]:
            print(f"   !! PAYOFF MISMATCH {line}")
    else:
        print("   solver agrees with the engine's returns on every game")
    for agent_name, stats in result["agents"].items():

        def fmt(key: str, _s: dict[str, Any] = stats) -> str:
            value = _s.get(key)
            return f"{value:+.4f}" if isinstance(value, float) else "   n/a"

        print(
            f"   {agent_name:10s} chips/hand={fmt('chips_per_hand')} "
            f"expl={fmt('exploitability')} "
            f"floor={fmt('exploitability_noise_floor')} "
            f"cov={fmt('infoset_coverage')} "
            f"dominated={fmt('dominated_action_rate')}"
            f" ({stats['dominated_taken']}/{stats['dominated_offered']})"
            f" bluff={fmt('bluff_rate')}"
            f" fallback={fmt('fallback_rate')}"
        )
    return len(result["payoff_mismatches"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        default="",
        help="a run directory; defaults to the most recent under results_kuhn/runs",
    )
    parser.add_argument("--control", default="llm_cheap_control_nash")
    parser.add_argument("--arm", default="llm_cheap_reason_first_nash")
    args = parser.parse_args()

    # The committed ARCHIVE is the default, not the latest run directory: a
    # reviewer who has just cloned the repo has no run directories, and the
    # archive is the record a published number rests on. `--dir` overrides for
    # looking at a run in progress.
    archive = "experiments/llm_eval/results_kuhn"
    run_dir = args.dir or (
        archive
        if glob.glob(os.path.join(archive, "transcripts", "*.jsonl.gz"))
        else max(glob.glob(os.path.join(archive, "runs", "*")), default="")
    )
    if not run_dir:
        print("no transcripts found — run a matchup first, or pass --dir")
        return 1
    transcripts = sorted(glob.glob(os.path.join(run_dir, "transcripts", "*.jsonl*")))
    if not transcripts:
        print(f"no transcripts under {run_dir}")
        return 1

    print(f"# recomputed independently of kuhn.aggregate, from {run_dir}\n")
    mismatches = 0
    for path in transcripts:
        mismatches += report_records(os.path.basename(path), _load(path))

    def _find(matchup: str) -> str:
        """The transcript for a matchup, gzipped or not — the archive holds one
        and a live run directory the other."""
        for suffix in (".jsonl", ".jsonl.gz"):
            candidate = os.path.join(run_dir, "transcripts", matchup + suffix)
            if os.path.exists(candidate):
                return candidate
        return ""

    control_path = _find(args.control)
    arm_path = _find(args.arm)
    if control_path and arm_path:
        print("== the pre-registered A/B (PREREGISTRATION_KUHN.md)")
        print(json.dumps(compare_arms(control_path, arm_path), indent=2))
    else:
        print("== the A/B arms are not both present in this run; skipping")

    if mismatches:
        print(f"\nFAILED: {mismatches} payoff mismatch(es)")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
