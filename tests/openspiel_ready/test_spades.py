"""Spades — OpenSpiel readiness (harness defaults throughout)."""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_spades", "spades.cardlang")
