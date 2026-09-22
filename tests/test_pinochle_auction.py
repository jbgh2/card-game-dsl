"""Pinochle's ascending auction on the kernel `round`, both outcome arms and the
ladder's two ends pinned independently of RNG luck.

The byte-identical characterization golden exercises both outcome arms, but that
coverage rests on the seed set. These drive the arms deterministically with an
injected chooser so the contract `pinochle_auction_outcome` settles is fixed by
construction:

- every seat leaves the auction -> the dealer is under and takes the contract at
  the minimum opening, which is the rules' seat and the rules' number;
- every seat bids the smallest legal raise -> the bid climbs the ladder in tens
  to the declared ceiling and the standing high bidder wins;
- `pass_with_help` is a third option that leaves the auction exactly as `pass`
  does, so a table that plays it settles the same contract as one that does not;
- at the top rung `submit_bid` is not offered at all, because there is no legal
  number left to name.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from tests.playout_policy import is_length_guard

PINOCHLE = (
    Path(__file__).parent.parent / "docs" / "games" / "pinochle.cardlang"
).read_text()

# Dealer starts at 0; `before_each` advances it to 1 before the first hand, so
# the dealer is seat 1 and the opener (`dealer offset_by left`) is seat 2.
FIRST_DEALER = 1

# The ladder's own numbers, read off the game rather than restated: the minimum
# opening and the ceiling `submit_bid` stops at.
MINIMUM_OPENING = 250
CEILING = 1500


def _move(candidates: list[Any], name: str) -> Any | None:
    """The auction move named `name` from a candidate list, or None when the list
    is not auction moves (bid amounts, trump suits, trick cards)."""
    for c in candidates:
        if isinstance(c, tuple) and c[0] == name:
            return c
    return None


def _capture_contracts(game: Any, chooser: Any) -> list[dict[str, Any]]:
    """Play one game with `chooser` and return every contract the auction's
    `pinochle_auction_outcome` traced (`pinochle_contract` events, in order).

    A chooser this degenerate is not a way anyone plays, and at the game's own
    1500 target it runs past the declared length before a side gets there. That
    refusal is tolerated — and ONLY that one, by the same predicate the playout
    policy uses, so a planted fault in the auction cannot be filed as "this game
    ran long" — because what these tests assert is the FIRST contract, which is
    settled long before the bound is anywhere near.
    """
    contracts: list[dict[str, Any]] = []

    def tr(event: str, data: Any) -> None:
        if event == "pinochle_contract":
            contracts.append(data)

    try:
        play_game(game, random.Random(0), tr, chooser=chooser)
    except OwnerGuardError as exc:
        if not is_length_guard(exc):
            raise
    return contracts


def _picking(name: str) -> Any:
    """A chooser that takes the named move wherever it is offered, and the first
    candidate everywhere else — which at a bid amount is the smallest legal
    raise, the ladder's own bottom rung."""

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        move = _move(candidates, name)
        return [move] if move is not None else [candidates[0]]

    return chooser


@pytest.mark.parametrize("leaving", ["pass", "pass_with_help"])
def test_every_seat_leaving_gives_the_dealer_the_minimum_contract(leaving: str) -> None:
    """The dealer is under: when the other three seats leave, the round ends
    before he is asked anything and the contract is his at the minimum opening.

    Both ways of leaving the auction are driven, because `pass_with_help` is a
    signalling action that no rule reads — a table that plays it must reach the
    same contract as one that does not, and that is a claim, not a restatement
    of the effect block."""
    game = check_dsl(PINOCHLE, "pinochle.cardlang")
    contracts = _capture_contracts(game, _picking(leaving))

    assert contracts, "no auction ran"
    assert contracts[0] == {
        "all_pass": True,
        "declarer": FIRST_DEALER,
        "bid": MINIMUM_OPENING,
    }


def test_full_bidding_climbs_the_ladder_to_the_ceiling() -> None:
    """Every seat taking the smallest legal raise walks the ladder from the
    minimum opening to the declared ceiling in tens, and the standing high
    bidder wins — not the seat the all-pass arm would have named.

    Pinning the declarer guards the high-bidder-vs-under selection and the ring
    rotation against off-by-one; pinning the bid at the ceiling guards the
    `when:` that stops `submit_bid` at the top rung, since without it the last
    raise would ask for a number out of an empty range."""
    game = check_dsl(PINOCHLE, "pinochle.cardlang")
    contracts = _capture_contracts(game, _picking("submit_bid"))

    assert contracts, "no auction ran"
    assert contracts[0] == {"all_pass": False, "declarer": 3, "bid": CEILING}


def test_the_top_rung_offers_no_bid_at_all() -> None:
    """The ceiling's own misuse probe: at the top rung the seat is offered the
    two ways out and nothing else.

    A ceiling enforced only by the range would ask for a number in an empty
    interval, which the chooser refuses with a message about candidate counts —
    a refusal naming the instrument where the game's own rule is what ran out.
    """
    game = check_dsl(PINOCHLE, "pinochle.cardlang")
    at_ceiling: list[frozenset[str]] = []

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        names = frozenset(c[0] for c in candidates if isinstance(c, tuple) and c)
        if names and names <= {"submit_bid", "pass", "pass_with_help"}:
            at_ceiling.append(names)
        move = _move(candidates, "submit_bid")
        return [move] if move is not None else [candidates[0]]

    _capture_contracts(game, chooser)

    assert at_ceiling, "no auction decision was offered"
    assert frozenset({"pass", "pass_with_help"}) in at_ceiling, (
        "the ladder never reached a rung where `submit_bid` was withheld, so "
        "the ceiling's `when:` guard is unexercised"
    )
