"""Spades — OpenSpiel readiness (harness defaults throughout)."""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_spades",
        "spades.cardlang",
        adapter_terminal_steps=150,  # greedy line 56-112 steps over the manifest
    )
