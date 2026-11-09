"""Executes the state-recall witness: two deals seat 0 cannot tell apart at
its second decision, which it could tell apart at its first.

Perfect recall (Kuhn) requires every history in one information set to carry
the same sequence of the seat's own earlier information states and actions.
This probe finds a pair of seeds that violates it in the real engine and
prints both seats' information-state strings at both decisions.
"""

from __future__ import annotations

from pathlib import Path

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, run

WITNESS = str(Path(__file__).resolve().parent / "witnesses" / "state_recall.cardlang")


def infostates(seed: int, history: tuple[int, ...]) -> tuple[str, list[int]]:
    node = run(WITNESS, seed, history)
    assert isinstance(node, DecisionNode) and node.player == 0
    return information_state(0, node.rs, node.obs_logs[0]), node.legal


def flag_at_first(seed: int) -> str:
    first, _ = infostates(seed, ())
    return first


def main() -> None:
    by_first: dict[str, int] = {}
    for seed in range(40):
        by_first.setdefault(flag_at_first(seed), seed)
        if len(by_first) == 2:
            break
    assert len(by_first) == 2, "no pair of deals separated seat 0 at its first decision"
    (first_a, seed_a), (first_b, seed_b) = by_first.items()
    _, legal = infostates(seed_a, ())
    pick = (legal[0],)
    second_a, _ = infostates(seed_a, pick)
    second_b, _ = infostates(seed_b, pick)
    print(f"seed {seed_a} first : {first_a}")
    print(f"seed {seed_b} first : {first_b}")
    print(f"seed {seed_a} second: {second_a}")
    print(f"seed {seed_b} second: {second_b}")
    print(f"first decisions distinguishable:  {first_a != first_b}")
    print(f"second decisions distinguishable: {second_a != second_b}")
    if first_a != first_b and second_a == second_b:
        print("PERFECT RECALL VIOLATED: one information set at the second decision,"
              " two at the first")


if __name__ == "__main__":
    main()
