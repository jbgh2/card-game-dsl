"""Spades — OpenSpiel readiness (harness defaults throughout)."""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_spades",
        "spades.cardlang",
        adapter_terminal_steps=90,  # greedy line measured at 56 steps
    )
