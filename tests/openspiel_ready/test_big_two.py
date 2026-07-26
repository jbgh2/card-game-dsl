"""Big Two — OpenSpiel readiness.

Depth 6: Big Two sheds cards fast, so a deeper pause leaves too few
swappable hidden cards in opponents' hands. The harness's swap pool
additionally pins the 3♦ in place (`GameSpec.swap_pairs`) because this
game's opening filter keys on that exact card.

Bounded conformance walk: the full `pyspiel.random_sim_test` measured 122s
locally — by far the slowest single test in this suite (Big Two plays
multiple hands to a target score, hundreds of actions each with a large
combo action space, the same O(n^2) re-simulation cost as Stud/French
Tarot/Tichu, compounded by a bigger per-decision branching factor). This
game's full-game-to-Terminal coverage through the actual pyspiel `State`
wrapper lives in `test_openspiel_replay.py`'s KERNEL_GAMES list, so
bounding this walk drops no real coverage.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_big_two",
        "big-two.cardlang",
        depth=6,
        conformance_steps=120,
        adapter_terminal_steps=200,  # greedy line measured at 147 steps
        conformance_verbs_unreached=(
            (
                "<card>",
                "STRUCTURAL, not a depth shortfall: every Big Two play is a "
                "combination — a singleton is a size-1 combo — so plays encode "
                "through the combo block and the reserved card block is dead "
                "(measured unapplied over 600 steps on three rngs). Issue #157 "
                "owns deriving the block away",
            ),
        ),
    )
