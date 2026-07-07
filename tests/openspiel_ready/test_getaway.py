"""Getaway — OpenSpiel readiness.

Depth 8: Getaway sheds cards fast, so a deeper pause leaves too few
swappable hidden cards in opponents' hands.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_getaway", "getaway.cardlang", depth=8)
