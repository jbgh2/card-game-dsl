"""Pinochle's ascending auction on the kernel `round`, both outcome arms pinned
independently of RNG luck.

The byte-identical characterization golden exercises both arms (the all-pass
fallback fires for ~9 of 50 random hands), but that coverage rests on the seed
set. These drive the two arms deterministically with an injected chooser so the
contract `pinochle_auction_outcome` settles is fixed by construction:

- every seat passes -> the opener takes the contract at the minimum 50;
- every seat bids -> the bid escalates 50, 60, ... to the 16-bid cap (200) and
  the standing high bidder wins.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

PINOCHLE = (
    Path(__file__).parent.parent / "docs" / "games" / "pinochle.cardlang"
).read_text()

# Dealer starts at 0; `before_each` advances it to 1 before the first hand, so the
# opener (`dealer offset_by left`) is seat 2.
FIRST_OPENER = 2


def _move(candidates: list[Any], name: str) -> Any | None:
    """The auction move named `name` from a candidate list, or None when the list
    is not auction moves (trump suits, trick cards)."""
    for c in candidates:
        if isinstance(c, tuple) and c[0] == name:
            return c
    return None


def test_all_pass_gives_the_opener_the_minimum_contract() -> None:
    game = check_dsl(PINOCHLE, "pinochle.cardlang")
    contracts: list[dict[str, Any]] = []

    def always_pass(player: int, candidates: list[Any], n: int) -> list[Any]:
        passit = _move(candidates, "pass")
        return [passit] if passit is not None else [candidates[0]]

    def tr(event: str, data: Any) -> None:
        if event == "pinochle_contract":
            contracts.append(data)

    play_game(game, random.Random(0), tr, chooser=always_pass)

    assert contracts, "no auction ran"
    first = contracts[0]
    assert first == {"all_pass": True, "declarer": FIRST_OPENER, "bid": 50}


def test_full_bidding_settles_on_the_high_bidder_at_the_cap() -> None:
    game = check_dsl(PINOCHLE, "pinochle.cardlang")
    contracts: list[dict[str, Any]] = []

    def always_bid(player: int, candidates: list[Any], n: int) -> list[Any]:
        bid = _move(candidates, "submit_bid")
        return [bid] if bid is not None else [candidates[0]]

    def tr(event: str, data: Any) -> None:
        if event == "pinochle_contract":
            contracts.append(data)

    play_game(game, random.Random(0), tr, chooser=always_bid)

    assert contracts, "no auction ran"
    first = contracts[0]
    # Sixteen bids at +10 from the opening 50 reach the cap of 200; the normal arm
    # threads the standing high bid (not the opener fallback's flat 50).
    assert first["all_pass"] is False
    assert first["bid"] == 200
    assert first["declarer"] in range(4)
