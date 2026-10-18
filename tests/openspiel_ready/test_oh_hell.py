"""Oh Hell — OpenSpiel readiness.

Bounded conformance walk: multiple hands of shrinking/growing trick length
(issue #913 measures the whole sim against this bound). This
game's full-game-to-TerminalNode coverage through the actual pyspiel `State`
wrapper lives in `test_openspiel_replay.py`'s KERNEL_GAMES list, so
bounding this walk drops no real coverage.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_oh_hell", "oh-hell.cardlang", conformance_steps=120)
