"""The corpus's missing witness: a position domain as a parameter, in a game
that actually runs.

No game in `docs/games/` uses a declared position domain as a function or
move parameter, so the construct would otherwise be exercised only by unit
tests written alongside the code they check. This fixture is the integration
half: a position domain in both parameter positions executes in a played
game.

It is a test FIXTURE rather than a corpus entry deliberately: corpus-first
governs which games exist, and no real card game motivates the construct
today — but that governs admission, not how completely a mechanism is covered
(decisions.md, "Closed-domain completeness").
"""

from __future__ import annotations

import random
from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

FIXTURE = Path(__file__).parent / "fixtures" / "position_parameters_witness.cardlang"

# claim(s) pays `slot_bonus(s) + twice(s)` = (s > 2 ? 2 : 1) + 2*s.
SLOT_VALUE = {1: 3, 2: 5, 3: 8, 4: 10}


def test_the_witness_checks_and_plays() -> None:
    """The position-domain parameter paths reach a running game.

    red under: give `slot_bonus` a parameter type that is not a declared
    type (`s : slott`) — the fixture stops checking and this fails at
    `check_source`.
    """
    game = check_source(FIXTURE)
    assert game.name == "PositionParametersWitness"
    for seed in range(20):
        play_game(game, random.Random(seed))


def test_the_parameter_reaches_the_score_it_computes() -> None:
    """The parameter's value is OBSERVED, not just typed.

    Four slots are claimed once each over the two rounds, so the players'
    scores partition `SLOT_VALUE` exactly.

    red under: change `twice(s)` to `s` in the fixture; the total drops and
    this fails.
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
