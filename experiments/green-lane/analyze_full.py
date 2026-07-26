"""Green Lane FULL game: outcome-sampling MCCFR at scale, skill gradient by
head-to-head play, and mixture evidence from the learned average policy.
The full tree (~1e8 histories) is far past exact solving, so this is the
sampled counterpart of analyze_mini.py's ground truth.

Run:  python experiments/green-lane/analyze_full.py [iterations]
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import defaultdict

import glcommon
import pyspiel
from open_spiel.python.algorithms import outcome_sampling_mccfr

SHORT_NAME = "greenlane"
DEFAULT_ITERATIONS = 120_000
WEAK_ITERATIONS_FRACTION = 10  # weak snapshot trains 1/10th as long
EVAL_GAMES = 2000


def sample_action(
    state: pyspiel.State, pol: object | None, rng: random.Random
) -> int:
    if pol is None:
        return rng.choice(state.legal_actions())
    probs = pol.action_probabilities(state)  # type: ignore[attr-defined]
    actions = list(probs.keys())
    weights = [probs[a] for a in actions]
    return rng.choices(actions, weights=weights, k=1)[0]


def head_to_head(
    game: pyspiel.Game,
    pol_a: object | None,
    pol_b: object | None,
    n_games: int,
    rng: random.Random,
) -> tuple[float, float]:
    """Mean return (and standard error) for policy A, seats alternating."""
    total = 0.0
    totsq = 0.0
    for g in range(n_games):
        seats = (pol_a, pol_b) if g % 2 == 0 else (pol_b, pol_a)
        state = game.new_initial_state()
        while not state.is_terminal():
            if state.is_chance_node():
                state.apply_action(0)
                continue
            pol = seats[state.current_player()]
            state.apply_action(sample_action(state, pol, rng))
        r = state.returns()[0 if g % 2 == 0 else 1]
        total += r
        totsq += r * r
    mean = total / n_games
    var = max(0.0, totsq / n_games - mean * mean)
    return mean, math.sqrt(var / n_games)


def entropy(probs: list[float]) -> float:
    return -sum(p * math.log2(p) for p in probs if p > 0)


def mixture_evidence(
    game: pyspiel.Game, pol: object, rng: random.Random, n_games: int = 1500
) -> dict[str, object]:
    """Self-play under the average policy; per visited infoset, record visit
    counts and the strategy, then summarize how mixed play actually is at the
    decisions the game reaches."""
    visits: dict[str, int] = defaultdict(int)
    strategy: dict[str, dict[str, float]] = {}
    owner: dict[str, int] = {}
    ply_of: dict[str, int] = {}

    for _ in range(n_games):
        state = game.new_initial_state()
        ply = 0
        while not state.is_terminal():
            if state.is_chance_node():
                state.apply_action(0)
                continue
            player = state.current_player()
            key = state.information_state_string(player)
            if key not in strategy:
                probs = pol.action_probabilities(state)  # type: ignore[attr-defined]
                strategy[key] = {
                    state.action_to_string(player, a): p for a, p in probs.items()
                }
                owner[key] = player
                ply_of[key] = ply
            visits[key] += 1
            state.apply_action(sample_action(state, pol, rng))
            ply += 1

    rows = sorted(visits, key=lambda k: -visits[k])
    total_visits = sum(visits.values())
    mixed_visits = sum(
        visits[k]
        for k in rows
        if sum(1 for p in strategy[k].values() if p > 0.05) > 1
    )
    top = [
        {
            "visits": visits[k],
            "player": owner[k],
            "ply": ply_of[k],
            "strategy": strategy[k],
        }
        for k in rows[:16]
    ]
    ent = [
        entropy(list(strategy[k].values()))
        for k in rows
        if len(strategy[k]) > 1
    ]
    return {
        "infosets_visited": len(rows),
        "share_of_decisions_at_mixed_infosets": mixed_visits / total_visits,
        "mean_entropy_bits": sum(ent) / len(ent) if ent else 0.0,
        "top_decisions": top,
    }


def describe(row: dict[str, object]) -> str:
    strat = ", ".join(
        f"{a}:{p:.3f}"
        for a, p in sorted(row["strategy"].items(), key=lambda kv: -kv[1])  # type: ignore[union-attr]
        if p > 0.005
    )
    return f"visits={row['visits']:5d} P{row['player']} ply={row['ply']:2d}  [{strat}]"


def main() -> None:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ITERATIONS
    glcommon.register_all(num_seeds=1)
    game = pyspiel.load_game(SHORT_NAME)
    rng = random.Random(17)

    weak_iters = iterations // WEAK_ITERATIONS_FRACTION
    solvers = {
        "weak": (outcome_sampling_mccfr.OutcomeSamplingSolver(game), weak_iters),
        "strong": (outcome_sampling_mccfr.OutcomeSamplingSolver(game), iterations),
    }
    for name, (solver, iters) in solvers.items():
        t0 = time.perf_counter()
        for it in range(iters):
            solver.iteration()
            if (it + 1) % 20_000 == 0:
                print(
                    f"  {name}: {it + 1}/{iters} iterations "
                    f"({time.perf_counter() - t0:.0f}s)"
                )
        print(
            f"{name}: trained {iters} MCCFR iterations in "
            f"{time.perf_counter() - t0:.0f}s"
        )

    weak = solvers["weak"][0].average_policy()
    strong = solvers["strong"][0].average_policy()

    print("\nhead-to-head (mean return for A ± stderr, seats alternating):")
    results: dict[str, tuple[float, float]] = {}
    for label, a, b in (
        ("strong vs random", strong, None),
        ("weak   vs random", weak, None),
        ("strong vs weak", strong, weak),
    ):
        mean, se = head_to_head(game, a, b, EVAL_GAMES, rng)
        results[label] = (mean, se)
        print(f"  {label}: {mean:+.2f} ± {se:.2f}")

    print("\nmixture evidence (self-play with the strong policy):")
    evidence = mixture_evidence(game, strong, rng)
    print(f"  infosets visited: {evidence['infosets_visited']}")
    print(
        "  share of in-game decisions taken at mixed infosets: "
        f"{evidence['share_of_decisions_at_mixed_infosets']:.1%}"
    )
    print(f"  mean strategy entropy: {evidence['mean_entropy_bits']:.2f} bits")
    print("  most visited decisions:")
    for row in evidence["top_decisions"]:  # type: ignore[union-attr]
        print("    " + describe(row))

    out = {
        "iterations": iterations,
        "head_to_head": {k: {"mean": v[0], "stderr": v[1]} for k, v in results.items()},
        "mixture": {
            k: evidence[k]
            for k in (
                "infosets_visited",
                "share_of_decisions_at_mixed_infosets",
                "mean_entropy_bits",
            )
        },
        "top_decisions": evidence["top_decisions"],
    }
    with open(glcommon.HERE / "results_full.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nwrote results_full.json")


if __name__ == "__main__":
    main()
