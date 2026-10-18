"""Big Two — OpenSpiel readiness.

Depth 6: Big Two sheds cards fast, so a deeper pause leaves too few
swappable hidden cards in opponents' hands. The harness's swap pool
additionally pins the 3♦ in place (`GameSpec.swap_pairs`) because this
game's opening filter keys on that exact card.

Conformance: `conformance_steps` is unset, so this game plays the full
`pyspiel.random_sim_test`, one whole game through the adapter, inside the
whole-sim budget (`harness.py`, `conformance_steps`).
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_big_two",
        "big-two.cardlang",
        depth=6,
        adapter_terminal_steps=200,  # greedy line measured at 147 steps
    )
