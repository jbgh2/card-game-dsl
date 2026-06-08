"""Card ⇄ action-id round-trips over the full 52-card space."""

from __future__ import annotations

import pytest

from cardlang.openspiel.encoding import (
    NUM_DISTINCT_ACTIONS,
    action_to_card,
    card_to_action,
)
from cardlang.runtime.values import RANKS, SUITS, Card


def test_round_trip_all_52() -> None:
    assert NUM_DISTINCT_ACTIONS == 52
    seen = set()
    for suit in SUITS:
        for rank in RANKS:
            card = Card(rank, suit)
            aid = card_to_action(card)
            assert 0 <= aid < 52
            assert aid not in seen  # bijective
            seen.add(aid)
            assert action_to_card(aid) == card
    assert len(seen) == 52


def test_out_of_range_raises() -> None:
    for bad in (-1, 52, 999):
        with pytest.raises(ValueError):
            action_to_card(bad)
