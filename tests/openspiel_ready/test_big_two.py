"""Big Two — OpenSpiel readiness.

Depth 6: Big Two sheds cards fast, so a deeper pause leaves too few
swappable hidden cards in opponents' hands. The harness's swap pool
additionally pins the 3♦ in place (`GameSpec.swap_pairs`) because this
game's opening filter keys on that exact card.

Bounded conformance walk: Big Two plays multiple hands to a target score,
hundreds of actions each with a large combo action space, and one full
`pyspiel.random_sim_test` is past the whole-sim budget (`harness.py`,
`conformance_steps`; 30s, measured 2026-10-18). `tests/test_openspiel_replay.py`'s `KERNEL_GAMES` plays one reference game
to TerminalNode through the replay engine and checks its returns.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_big_two",
        "big-two.cardlang",
        depth=6,
        conformance_steps=120,
        adapter_terminal_steps=200,  # greedy line measured at 147 steps
    )
