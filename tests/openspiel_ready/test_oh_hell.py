"""Oh Hell — OpenSpiel readiness.

Conformance: `conformance_steps` is unset, so this game plays the full
`pyspiel.random_sim_test`, one whole game through the adapter, inside the
whole-sim budget (`harness.py`, `conformance_steps`).
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_oh_hell", "oh-hell.cardlang")
