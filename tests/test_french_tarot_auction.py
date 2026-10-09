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
    contracts the auctions settled, re-derived from the announcements."""
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

    heard: list[tuple[int, str]] = []

    def observer(player: int, event: tuple[Any, ...]) -> None:
        if player == 0 and event[0] == "announce":
            heard.append((int(event[1]), str(event[2])))

    play_game(game, random.Random(0), chooser=chooser, observer=observer)
    # Each auction is a run of bid-vocabulary announcements; its contract is
    # the last bid heard, or a thrown-in hand when nobody bid.
    levels = {"bid_petite": 1, "bid_garde": 2, "bid_garde_sans": 3, "bid_garde_contre": 4}
    in_auction = False
    taker: tuple[int, int] | None = None
    for actor, text in heard:
        if text in levels or text == "pass":
            in_auction = True
            if text in levels:
                taker = (actor, levels[text])
        elif in_auction:
            contracts.append(
                {"thrown_in": True} if taker is None
                else {"thrown_in": False, "taker": taker[0], "level": taker[1]}
            )
            in_auction, taker = False, None
    if in_auction:
        contracts.append(
            {"thrown_in": True} if taker is None
            else {"thrown_in": False, "taker": taker[0], "level": taker[1]}
        )
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
