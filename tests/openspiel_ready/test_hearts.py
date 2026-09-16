"""Hearts — OpenSpiel readiness.

Bounded conformance walk: the full `pyspiel.random_sim_test` measured 8.1s
locally (multiple hands to a target score — the same O(n^2) re-simulation
cost as Stud/French Tarot/Tichu, just a shorter game). This game's
full-game-to-TerminalNode coverage through the actual pyspiel `State` wrapper
lives in `test_openspiel_replay.py`'s KERNEL_GAMES list, so bounding this
walk drops no real coverage.
"""

from .harness import GameSpec, ReadinessProofs


_MOON = (
    "a moon is one hand in a hundred under random play and its choice comes "
    "at that hand's scoring, far beyond a 120-step walk; both arms are "
    "exercised in tests/test_playout_hearts.py::"
    "test_a_moon_scores_the_way_its_shooter_chose"
)


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_hearts",
        "hearts.cardlang",
        conformance_steps=120,
        conformance_verbs_unreached=(
            ("charge_the_others", _MOON),
            ("credit_the_shooter", _MOON),
        ),
    )
