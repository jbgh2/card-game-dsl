"""How much do naive pure-ish strategies lose against the mini equilibrium?
Re-solves the mini game with CFR+ (deterministic), then exactly evaluates a
grid of {shipping rule} x {inspection rule} heuristics against the
equilibrium average policy, both seats. If simple rules survived, the mixing
wouldn't be load-bearing; the gap quantifies the game's strategic depth.

Run:  python experiments/green-lane/analyze_heuristics.py [iterations]
"""

from __future__ import annotations

import json
import sys

import pyspiel
from open_spiel.python.algorithms import cfr

import glcommon

SHORT_NAME = "greenlane_mini"
DEFAULT_ITERATIONS = 400
RESPONSE_LABELS = {"inspect", "wave"}


class RulePolicy:
    """A deterministic-by-label policy: ship_rule and inspect_rule pick from
    the human-readable action labels, so the rule reads like the strategy."""

    def __init__(self, name: str, ship_rule: str, inspect_rule: str) -> None:
        self.name = name
        self.ship_rule = ship_rule
        self.inspect_rule = inspect_rule

    def action_probabilities(self, state: pyspiel.State) -> dict[int, float]:
        player = state.current_player()
        labeled = [(a, state.action_to_string(player, a)) for a in state.legal_actions()]
        labels = {lab for _, lab in labeled}
        if labels & RESPONSE_LABELS:
            pick = self._pick_response(labeled)
        else:
            pick = self._pick_ship(labeled)
        if pick is None:  # rule expresses no preference: uniform
            return {a: 1.0 / len(labeled) for a, _ in labeled}
        return {a: (1.0 if a == pick else 0.0) for a, _ in labeled}

    # Every rank any Green Lane variant declares contraband (baseline/V1: K A;
    # V2/V2b: K A; V3/V4: 7 A) — and no variant's decoy (always 2..5) collides
    # with it, so prefix classification stays exact across the whole family.
    # Keep this set in sync with the variants' contraband predicates.
    CONTRABAND_PREFIXES = ("A", "K", "Q", "7")

    def _pick_ship(self, labeled: list[tuple[int, str]]) -> int | None:
        hot = [a for a, lab in labeled if lab.startswith(self.CONTRABAND_PREFIXES)]
        cold = [a for a, lab in labeled if not lab.startswith(self.CONTRABAND_PREFIXES)]
        if self.ship_rule == "ace_first":
            return hot[0] if hot else labeled[0][0]
        if self.ship_rule == "ace_last":
            return cold[0] if cold else labeled[0][0]
        return None  # "uniform"

    def _pick_response(self, labeled: list[tuple[int, str]]) -> int | None:
        by = {lab: a for a, lab in labeled}
        if self.inspect_rule == "always":
            return by.get("inspect", labeled[0][0])
        if self.inspect_rule == "never":
            return by.get("wave", labeled[0][0])
        return None  # "coin_flip"


def joint_value(
    game: pyspiel.Game, pol0: object, pol1: object
) -> float:
    """P0's exact expected return when P0 plays pol0 and P1 plays pol1."""

    def walk(state: pyspiel.State, prob: float) -> float:
        if state.is_terminal():
            return prob * state.returns()[0]
        total = 0.0
        if state.is_chance_node():
            for action, p in state.chance_outcomes():
                child = state.clone()
                child.apply_action(action)
                total += walk(child, prob * p)
            return total
        pol = pol0 if state.current_player() == 0 else pol1
        for action, p in pol.action_probabilities(state).items():  # type: ignore[attr-defined]
            if p == 0:
                continue
            child = state.clone()
            child.apply_action(action)
            total += walk(child, prob * p)
        return total

    return walk(game.new_initial_state(), 1.0)


def main() -> None:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ITERATIONS
    glcommon.register_all(num_seeds=1)
    glcommon.install_infostate_memo()
    game = pyspiel.load_game(SHORT_NAME)

    solver = cfr.CFRPlusSolver(game)
    for _ in range(iterations):
        solver.evaluate_and_update_policy()
    equilibrium = solver.average_policy()

    rules = [
        RulePolicy(f"{s}/{i}", s, i)
        for s in ("ace_first", "ace_last", "uniform")
        for i in ("always", "never", "coin_flip")
    ]
    rows = []
    print(f"naive rule vs equilibrium (mean of both seats; CFR+ {iterations} iters):")
    for rule in rules:
        as_p0 = joint_value(game, rule, equilibrium)
        as_p1 = -joint_value(game, equilibrium, rule)
        mean = (as_p0 + as_p1) / 2
        rows.append(
            {"rule": rule.name, "as_p0": as_p0, "as_p1": as_p1, "mean": mean}
        )
        print(f"  {rule.name:20s}  P0 {as_p0:+7.3f}   P1 {as_p1:+7.3f}   mean {mean:+7.3f}")

    best = max(rows, key=lambda r: r["mean"])  # type: ignore[arg-type,return-value]
    print(f"\nbest naive combo: {best['rule']} at {best['mean']:+.3f} per game")

    with open(glcommon.HERE / "results_heuristics.json", "w") as fh:
        json.dump(rows, fh, indent=2)
    print("wrote results_heuristics.json")


if __name__ == "__main__":
    main()
