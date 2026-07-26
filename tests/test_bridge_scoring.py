"""Independent recompute of Bridge scoring, driving the real bridge.cardlang.

Bridge's scoring lives in the DSL, so this drives actual games and recomputes
every hand's score from the traced contract (a `bridge_contract` event) and the
trick winners, mirroring the scoring rules in Python, then asserts the recomputed
running totals match the traced `hand_end` totals after every hand. This pins the
whole scoring system — in particular the just-fixed redoubled-undertrick tier
(×4 → 400/200), which random play exercises heavily — so a regression in any
branch makes the recompute diverge and the test fail.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"
TEAM = {0: 0, 2: 0, 1: 1, 3: 1}  # partnerships [[0, 2], [1, 3]]


def _per_trick(strain: str | None) -> int:
    if strain is None:
        return 30  # no-trump
    return 20 if strain in ("clubs", "diamonds") else 30


def test_bridge_scoring_matches_independent_recompute() -> None:
    game = check_source(BRIDGE)
    redoubled_down = 0
    for seed in range(25):
        events: list[tuple[str, Any]] = []

        def tracer(event: str, data: Any) -> None:
            if event in ("bridge_contract", "trick", "hand_end"):
                events.append((event, data))  # noqa: B023 -- consumed before the loop advances

        play_game(game, random.Random(seed), tracer)

        games_won = {0: 0, 1: 0}
        below = {0: 0, 1: 0}
        total = {0: 0, 1: 0}
        contract: dict[str, Any] | None = None
        tricks = {0: 0, 1: 0}

        for kind, data in events:
            if kind == "bridge_contract":
                contract = data
                tricks = {0: 0, 1: 0}
            elif kind == "trick":
                tricks[TEAM[data[0]]] += 1
            elif kind == "hand_end":
                assert contract is not None
                if not contract["all_pass"]:
                    dt = contract["declarer_team"]
                    ot = 1 - dt
                    level, dm, strain = contract["level"], contract["doubled_mult"], contract["strain"]
                    required = 6 + level
                    actual = tricks[dt]
                    vuln = games_won[dt] >= 1
                    pt = _per_trick(strain)
                    if actual >= required:
                        nt_bonus = 10 if strain is None else 0
                        b = (pt * level + nt_bonus) * dm
                        total[dt] += b
                        below[dt] += b
                        over = actual - required
                        ov = pt if dm == 1 else (200 if vuln else 100) if dm == 2 else (400 if vuln else 200)
                        total[dt] += ov * over
                        if level == 6:
                            total[dt] += 750 if vuln else 500
                        if level == 7:
                            total[dt] += 1500 if vuln else 1000
                        if below[dt] >= 100:
                            total[dt] += 500 if vuln else 300
                            games_won[dt] += 1
                            below[dt] = 0
                            below[ot] = 0
                            if games_won[dt] >= 2:
                                total[dt] += 700 if games_won[ot] == 0 else 500
                    else:
                        under = required - actual
                        pu = (100 if vuln else 50) if dm == 1 else (200 if vuln else 100) if dm == 2 else (400 if vuln else 200)
                        total[ot] += pu * under
                        if dm == 4:
                            redoubled_down += 1
                # The traced hand_end carries the runtime's total_score per team.
                assert data == total, f"seed {seed}: recompute {total} != runtime {data}"
                contract = None

    # The redoubled-undertrick tier is genuinely exercised (not a vacuous pass).
    assert redoubled_down > 0
