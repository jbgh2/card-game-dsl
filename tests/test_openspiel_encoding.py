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


def test_pinochle_space_adds_the_bid_and_trump_vocabulary() -> None:
    space = _space("pinochle.cardlang")
    # 52 cards + the auction's nullary [submit_bid, pass] + declare_trump_suit
    # over its four-suit domain, in the order the game file's rounds are
    # walked (auction first, then the play phase): 52=submit_bid, 53=pass,
    # 54..57=declare_trump_suit(clubs/diamonds/hearts/spades). No bare names,
    # no integer block, no combos.
    assert space.num_distinct_actions == 58
    assert [space.to_string(a) for a in range(52, 58)] == [
        "submit_bid",
        "pass",
        "declare_trump_suit(clubs)",
        "declare_trump_suit(diamonds)",
        "declare_trump_suit(hearts)",
        "declare_trump_suit(spades)",
    ]


def test_french_tarot_space_derives_its_own_78_card_block() -> None:
    space = _space("french-tarot.cardlang")
    # The tarot78 deck is not standard-52-expressible (the atouts' rank "1"/
    # the Cavalier's "C", and the Excuse, all fall outside SUITS x RANKS), so
    # the space derives its OWN 78-card block (deck-declaration order: clubs
    # K..1, diamonds K..1, hearts K..1, spades K..1, atouts 1..21, Excuse) —
    # rather than the module's standard 52-card mapping — plus the auction's
    # five nullary bid-level moves in game-file declaration order.
    assert space.num_distinct_actions == 78 + 5
    assert space.encode(Card("K", "clubs")) == 0
    assert space.encode(Card("1", "atouts")) == 56
    assert space.encode(Card("21", "atouts")) == 76
    assert space.encode(Card("Excuse", "excuse")) == 77
    assert [space.to_string(a) for a in range(78, 83)] == [
        "pass",
        "bid_petite",
        "bid_garde",
        "bid_garde_sans",
        "bid_garde_contre",
    ]


def test_french_tarot_card_block_round_trips_all_78() -> None:
    from cardlang.runtime.values import build_deck

    space = _space("french-tarot.cardlang")
    seen = set()
    for card in build_deck("tarot78"):
        aid = space.encode(card)
        assert 0 <= aid < 78
        assert aid not in seen
        seen.add(aid)
        assert space.decode(aid) == card
    assert len(seen) == 78


def test_french_tarot_to_string_uses_the_card_glyph_rendering() -> None:
    space = _space("french-tarot.cardlang")
    assert space.to_string(space.encode(Card("K", "clubs"))) == "K♣"
    assert space.to_string(space.encode(Card("1", "atouts"))) == "1★"
    assert space.to_string(space.encode(Card("Excuse", "excuse"))) == "Excuse☆"


def test_schnapsen_space_folds_play_card_into_the_card_block() -> None:
    space = _space("schnapsen.cardlang")
    # 52 cards (schnapsen20 is a standard-catalogue subset, so the standard
    # block applies with unused slots) + the lead vocabulary WITHOUT play_card:
    # a Card-parameterized move's actions ARE the card block (Option B), so it
    # mints no vocab ids — declare_marriage over the four suits, then the
    # nullary exchange/close, in vocabulary order.
    assert space.num_distinct_actions == 58
    assert [space.to_string(a) for a in range(52, 58)] == [
        "declare_marriage(clubs)",
        "declare_marriage(diamonds)",
        "declare_marriage(hearts)",
        "declare_marriage(spades)",
        "exchange_trump_jack",
        "close_talon",
    ]
    # A leader's play_card candidate encodes as the card itself — the same id
    # as the follower playing that card as a bare movement pick.
    card = Card("A", "hearts")
    aid = space.encode(("play_card", card))
    assert aid == space.encode(card) < 52
    # A card id matches either representation in a live candidate pool.
    assert space.match(aid, [("play_card", card), ("close_talon", None)]) == (
        "play_card",
        card,
    )
    assert space.match(aid, [Card("J", "clubs"), card]) == card


def test_skat_space_names_offers_and_reizen_vocabulary() -> None:
    space = _space("skat.cardlang")
    # 52 cards (skat32 is a standard-catalogue subset, unused slots) + the
    # seven offer names (sorted) + the auction vocabulary in walk order: the
    # Reizen's [bid, yes, pass], then declare_suit over the four suits.
    assert space.num_distinct_actions == 66
    assert [space.to_string(a) for a in range(52, 66)] == [
        "choose_suit_game",
        "declare_grand",
        "declare_hand",
        "declare_null",
        "pick_up_skat",
        "play_at_eighteen",
        "throw_in",
        "bid",
        "yes",
        "pass",
        "declare_suit(clubs)",
        "declare_suit(diamonds)",
        "declare_suit(hearts)",
        "declare_suit(spades)",
    ]


def test_cribbage_space_is_pure_cards() -> None:
    # No offers, no `choose`, no auction vocabulary, no climb engine — just the
    # standard 52-card block (the first 2-player registered game).
    space = _space("cribbage.cardlang")
    assert space.num_distinct_actions == 52
    assert space.encode(Card("A", "clubs")) == card_to_action(Card("A", "clubs"))
    assert space.decode(space.encode(Card("K", "hearts"))) == Card("K", "hearts")


def test_existing_games_keep_the_standard_52_card_block() -> None:
    # The derivation must be a no-op for every deck already expressible in the
    # standard scheme — a subset deck (pinochle48) leaves unused slots rather
    # than getting its own (smaller) from-scratch block.
    assert _space("hearts.cardlang").encode(Card("A", "clubs")) == card_to_action(
        Card("A", "clubs")
    )
    assert _space("pinochle.cardlang").num_distinct_actions == 58  # unchanged


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
