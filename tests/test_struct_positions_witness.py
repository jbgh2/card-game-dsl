"""The corpus's missing witness: a user `type`, and a position domain as a
parameter, in a game that actually runs.

No game in `docs/games/` declares a `type`, and none uses a declared position
domain as a function or move parameter — so both construct families were
exercised only by unit tests written alongside the code they check. Every
defect behind the struct/function fixpoint was found by review or adversarial
probe and none by the suite, for exactly that reason (issue #122). This fixture closes the
integration half of that hole: the struct registry, a derived field whose body
calls a function, a struct literal read through that derived field, and a
position domain in both parameter positions all execute in a played game.

It is a test FIXTURE rather than a corpus entry deliberately: corpus-first
governs which games exist, and no real card game motivates these constructs
today — but that governs admission, not how completely a mechanism is covered
(decisions.md, "Closed-domain completeness").
"""

from __future__ import annotations

import random
from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

FIXTURE = Path(__file__).parent / "fixtures" / "struct_positions_witness.cardlang"

# claim(s) pays `slot_bonus(s) + weight_of(s).doubled` = (s > 2 ? 2 : 1) + 2*s.
SLOT_VALUE = {1: 3, 2: 5, 3: 8, 4: 10}


def test_the_witness_checks_and_plays() -> None:
    """The struct and position-domain paths reach a running game.

    red under: delete the `derived` block from `type Weight`, or give
    `slot_bonus` a parameter type that is not the declared position domain —
    the fixture stops checking and this fails at `check_source`.
    """
    game = check_source(FIXTURE)
    assert game.name == "StructPositionsWitness"
    for seed in range(20):
        play_game(game, random.Random(seed))


def test_the_derived_field_reaches_the_score_it_computes() -> None:
    """The fixpoint's result is OBSERVED, not just typed.

    Four slots are claimed once each over the two rounds, so the players'
    scores partition `SLOT_VALUE` exactly. A derived field that failed to
    resolve — the defect class this branch closes — would not merely type as
    the permissive top, it would pay the wrong score here.

    red under: change `doubled = twice(base)` to `doubled = base` in the
    fixture; the total drops and this fails.
    """
    game = check_source(FIXTURE)
    total = sum(SLOT_VALUE.values())
    for seed in range(20):
        result = play_game(game, random.Random(seed))
        assert sum(result.scores.values()) == total, (
            f"seed {seed}: every slot is claimed exactly once, so the scores "
            f"must partition {SLOT_VALUE}"
        )
        for score in result.scores.values():
            assert _is_a_subset_sum(score), (
                f"seed {seed}: {score} is not a sum of distinct slot values"
            )


def _is_a_subset_sum(target: int) -> bool:
    sums = {0}
    for value in SLOT_VALUE.values():
        sums |= {s + value for s in sums}
    return target in sums
