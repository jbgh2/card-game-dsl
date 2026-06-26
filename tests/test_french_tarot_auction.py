"""French Tarot's four-level auction on the kernel round, both outcome arms
pinned independently of RNG luck.

The byte-identical characterization golden exercises both arms across its random
seeds, but that coverage rests on the seed set. These drive the two arms
deterministically with an injected chooser:

- every seat passes -> the hand is thrown in (re-dealt, no taker);
- the opener bids petite -> he is the taker at level 1.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

TAROT = (
    Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"
).read_text()

# dealer starts 0; before_each advances it counterclockwise (offset_by right) to
# 3, so the opener (dealer's right, the first bidder) is seat 2.
FIRST_OPENER = 2


def _auction_move(candidates: list[Any], name: str) -> Any | None:
    for c in candidates:
        if isinstance(c, tuple) and c[0] == name:
            return c
    return None


def _capture_contracts(game: Any, want_first_bid: str | None) -> list[dict[str, Any]]:
    """Play one game, choosing `want_first_bid` (a move name) at the very first
    auction turn and passing at every later auction turn; non-auction decisions
    (chien discard, trick cards) take the first `n` candidates. Returns the
    `tarot_contract` events the auction traced."""
    contracts: list[dict[str, Any]] = []
    bid_done = [False]

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        if candidates and isinstance(candidates[0], tuple):  # an auction turn
            if want_first_bid is not None and not bid_done[0]:
                pick = _auction_move(candidates, want_first_bid)
                if pick is not None:
                    bid_done[0] = True
                    return [pick]
            passit = _auction_move(candidates, "pass")
            return [passit if passit is not None else candidates[0]]
        return list(candidates[:n])

    def tr(event: str, data: Any) -> None:
        if event == "tarot_contract":
            contracts.append(data)

    play_game(game, random.Random(0), tr, chooser=chooser)
    return contracts


def test_all_pass_throws_the_hand_in() -> None:
    game = check_dsl(TAROT, "french-tarot.cardlang")
    contracts = _capture_contracts(game, want_first_bid=None)
    assert contracts, "no auction ran"
    assert contracts[0] == {"thrown_in": True}


def test_opening_petite_makes_the_opener_taker_at_level_one() -> None:
    game = check_dsl(TAROT, "french-tarot.cardlang")
    contracts = _capture_contracts(game, want_first_bid="bid_petite")
    assert contracts, "no auction ran"
    assert contracts[0] == {
        "thrown_in": False,
        "taker": FIRST_OPENER,
        "level": 1,
    }
