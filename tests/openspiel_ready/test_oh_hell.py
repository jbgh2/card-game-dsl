"""Oh Hell — OpenSpiel readiness.

Bounded conformance walk: the full `pyspiel.random_sim_test` measured 8.7s
locally (multiple hands of shrinking/growing trick length — the same O(n^2)
re-simulation cost as Stud/French Tarot/Tichu, just a shorter game). This
game's full-game-to-TerminalNode coverage through the actual pyspiel `State`
wrapper lives in `test_openspiel_replay.py`'s KERNEL_GAMES list, so
bounding this walk drops no real coverage.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_oh_hell", "oh-hell.cardlang", conformance_steps=120)
