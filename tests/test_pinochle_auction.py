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


def _capture_contracts(game: Any, chooser: Any) -> list[dict[str, Any]]:
    """Play one game with `chooser` and return every contract the auction's
    `pinochle_auction_outcome` traced (`pinochle_contract` events, in order)."""
    contracts: list[dict[str, Any]] = []

    def tr(event: str, data: Any) -> None:
        if event == "pinochle_contract":
            contracts.append(data)

    play_game(game, random.Random(0), tr, chooser=chooser)
    return contracts


def test_all_pass_gives_the_opener_the_minimum_contract() -> None:
    game = check_dsl(PINOCHLE, "pinochle.cardlang")

    def always_pass(player: int, candidates: list[Any], n: int) -> list[Any]:
        passit = _move(candidates, "pass")
        return [passit] if passit is not None else [candidates[0]]

    contracts = _capture_contracts(game, always_pass)

    assert contracts, "no auction ran"
    assert contracts[0] == {"all_pass": True, "declarer": FIRST_OPENER, "bid": 50}


def test_full_bidding_settles_on_the_high_bidder_at_the_cap() -> None:
    game = check_dsl(PINOCHLE, "pinochle.cardlang")

    def always_bid(player: int, candidates: list[Any], n: int) -> list[Any]:
        bid = _move(candidates, "submit_bid")
        return [bid] if bid is not None else [candidates[0]]

    contracts = _capture_contracts(game, always_bid)

    assert contracts, "no auction ran"
    # Sixteen bids at +10 from the opening 50 reach the cap of 200, and the
    # standing high bidder wins — deterministically seat 1 (the bidding rotation
    # from opener 2 is 2,3,0,1,...; the 16th bid lands on seat 1), NOT the
    # opener-fallback seat 2 at the flat 50. Pinning the declarer guards the
    # high-bidder-vs-opener selection and the ring rotation against off-by-one.
    assert contracts[0] == {"all_pass": False, "declarer": 1, "bid": 200}
