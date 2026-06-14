"""The Bridge auction's `all_pass` arm, forced.

Under random capped-level bidding a pass-out essentially never happens (0 of 684
auctions across the 50-seed sweep), so the byte-identical characterization leaves
the `all_pass` arm + `skip to next hand` unexercised. Force a pass-out on the
first hand with a scripted chooser and check the arm end-to-end.

If `skip to next hand` failed to bypass the play phase, the no-contract hand would
run `leader := declarer offset_by left` with `declarer = none` and crash — so a
clean completion is itself evidence the skip worked.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Player

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"


def test_pass_out_routes_through_skip_to_next_hand() -> None:
    rand = random_chooser(random.Random(0))
    forced = {"passes": 4}  # one full opening round of passes -> all_pass, hand 1

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if n == 1 and ("pass",) in candidates and forced["passes"] > 0:
            forced["passes"] -= 1
            return [("pass",)]
        return rand(player, candidates, n)

    contracts: list[dict[str, Any]] = []

    def tracer(event: str, payload: Any) -> None:
        if event == "bridge_contract":
            contracts.append(payload)

    game = check_dsl(BRIDGE.read_text(), "bridge.cardlang")
    result = play_game(game, random.Random(1), tracer=tracer, chooser=chooser)

    assert any(c.get("all_pass") for c in contracts)  # the pass-out arm fired
    assert result.winner in (0, 1)  # ...and the rubber still completed (no crash)
