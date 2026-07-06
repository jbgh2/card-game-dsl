"""Hearts — OpenSpiel readiness (harness defaults throughout)."""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_hearts", "hearts.cardlang")
