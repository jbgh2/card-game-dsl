"""Hearts — OpenSpiel readiness.

Bounded conformance walk: the full `pyspiel.random_sim_test` measured 8.1s
locally (multiple hands to a target score — the same O(n^2) re-simulation
cost as Stud/French Tarot/Tichu, just a shorter game). This game's
full-game-to-Terminal coverage through the actual pyspiel `State` wrapper
lives in `test_openspiel_replay.py`'s KERNEL_GAMES list, so bounding this
walk drops no real coverage.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_hearts", "hearts.cardlang", conformance_steps=120)
