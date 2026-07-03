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


from pathlib import Path

from cardlang.openspiel.encoding import ActionSpace, ComboAction
from cardlang.pipeline import check_source

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _space(path: str) -> ActionSpace:
    return ActionSpace.for_game(check_source(GAMES / path))


def test_hearts_space_is_cards_only() -> None:
    assert _space("hearts.cardlang").num_distinct_actions == 52


def test_spades_space_adds_the_integer_block() -> None:
    space = _space("spades.cardlang")
    assert space.num_distinct_actions == 52 + 53
    assert space.decode(space.encode(7)) == 7
    assert space.to_string(space.encode(7)) == "7"


def test_bridge_space_adds_the_auction_vocabulary() -> None:
    space = _space("bridge.cardlang")
    # pass, submit_bid over Suit? (clubs, diamonds, hearts, spades, none), double, redouble
    assert space.num_distinct_actions == 52 + 8
    aid = space.encode(("submit_bid", "hearts"))
    assert space.decode(aid) == ("submit_bid", "hearts")
    assert space.to_string(aid) == "submit_bid(hearts)"
    assert space.decode(space.encode(("pass", None))) == ("pass", None)


def test_bigtwo_space_adds_pass_and_the_combo_universe() -> None:
    space = _space("big-two.cardlang")
    assert space.num_distinct_actions == 52 + 1 + 19898
    aid = space.encode("pass")
    assert space.decode(aid) == "pass"


def test_stud_space_adds_the_betting_vocabulary() -> None:
    space = _space("seven-card-stud.cardlang")
    # 52 cards + the nullary betting vocabulary in offering order at 52..56;
    # no bare names, no integer block, no combos.
    assert space.num_distinct_actions == 57
    assert [space.to_string(a) for a in range(52, 57)] == [
        "check",
        "bet",
        "call",
        "fold",
        "raise",
    ]


def test_combo_round_trip_and_match() -> None:
    from cardlang.runtime.bigtwo import bigtwo_universe

    space = _space("big-two.cardlang")
    play = next(p for p in bigtwo_universe() if p.kind == "fullhouse")
    aid = space.encode(play)
    decoded = space.decode(aid)
    assert isinstance(decoded, ComboAction)
    assert decoded.cards == frozenset(play.cards)
    assert space.match(aid, [play, "pass"]) is play
    assert space.to_string(aid).startswith("fullhouse[")


def test_encode_rejects_out_of_space_values() -> None:
    import pytest

    space = _space("hearts.cardlang")
    with pytest.raises((KeyError, AssertionError, ValueError)):
        space.encode(("submit_bid", "hearts"))  # hearts has no vocabulary
