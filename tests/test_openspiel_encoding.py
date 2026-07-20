"""Card ⇄ action-id round-trips over the full 52-card space."""

from __future__ import annotations

import random

import pytest

from cardlang.openspiel.encoding import (
    NUM_DISTINCT_ACTIONS,
    action_to_card,
    card_to_action,
)
from cardlang.runtime import reads, sidecar
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.tichu import ROW as TICHU_ROW
from cardlang.runtime.values import RANKS, SUITS, Card, Seating


def _tichu_bundles() -> tuple[sidecar.EngineFacts, reads.GameReads]:
    """The bundles a tichu climb query receives. The lead query ignores them
    (Tichu leads depend only on the hand), but they are built for real rather
    than faked: a None would only typecheck behind an ignore, and the next
    query to actually read them would fail at runtime instead of here."""
    from cardlang.ast import nodes as n

    decls = (n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),)
    rs = RuntimeState(Seating(4), ZoneStore(decls, (0, 1, 2, 3)), random.Random(0))
    rs.push_frame()
    rs.declare("out_first", False, None)
    rs.declare("out_second", False, None)
    return sidecar.bind(rs, None, TICHU_ROW)


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
    # `choose integer in 0 .. 13`: a literal upper bound is its own static
    # ceiling, so the integer block reserves ids 0..13 (14), not a deck-sized
    # constant — decisions.md "The integer `choose` domain".
    assert space.num_distinct_actions == 52 + 14
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


def test_skat_offer_move_encodes_the_same_as_its_runtime_tuple_shape() -> None:
    """The runtime represents EVERY nullary candidate — whether offered via a
    plain `offer` (`pick_up_skat`) or a round vocabulary (`pass`) — as a
    `(name, None)` tuple (mechanics.concrete_moves's empty-product case). This
    game's action space still names offer moves as bare strings (they were
    never round-vocabulary members, so no `(name, None)` vocab id was minted
    for them) — `encode`/`match` must treat the two shapes as the same action,
    or the OpenSpiel adapter can't encode what `execute._offer` actually
    offers (this exact gap broke `test_openspiel_replay.py`'s Skat replay and
    every Coup/Skat `openspiel_ready` proof until `encode`/`match` learned it)."""
    space = _space("skat.cardlang")
    aid = space.encode("pick_up_skat")
    assert space.encode(("pick_up_skat", None)) == aid
    assert space.match(aid, [("pick_up_skat", None), "throw_in"]) == ("pick_up_skat", None)


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


def test_tichu_space_derives_its_own_56_block_and_the_combo_codec() -> None:
    space = _space("tichu.cardlang")
    # tichu56 is not standard-52-expressible (Mahjong/Dog/Phoenix/Dragon fall
    # outside SUITS x RANKS), so the space derives its own 56-card block (deck
    # order), plus the climb "pass" name, plus the ARITHMETIC combo codec:
    # 211,204,694 plays, computed rather than enumerated (straights of length
    # 5-14 under free suit assignment are 208.8M of it — an enumerated,
    # golden-pinned universe like Big Two's 19,898 is physically infeasible).
    # Every combo id is a pure function of the card-set, so ids stay stable
    # across determinized worlds without a table.
    # ... plus the six named call/Dragon moves of the WS5 windows
    # (call_grand_tichu, decline_grand, call_tichu, no_call, dragon_to_left,
    # dragon_to_right).
    assert space.num_distinct_actions == 56 + 1 + 6 + 211_204_694
    # The named-move block follows the cards (declaration order interleaves
    # the WS5 vocabulary around the climb pass).
    assert space.to_string(60) == "pass"
    assert space.to_string(56) == "call_grand_tichu"
    # Spot ids: the combo block opens at 63 with the Dog (its own trick-ending
    # kind), and the engine's Phoenix+Mahjong pair (the by_rank quirk) sits at
    # a pinned slot inside the pair sub-block.
    from cardlang.runtime.combinations import Play
    from cardlang.runtime.values import build_deck

    deck = build_deck("tichu56")
    dog = next(c for c in deck if c.rank == "Dog")
    mahjong = next(c for c in deck if c.rank == "Mahjong")
    phoenix = next(c for c in deck if c.rank == "Phoenix")
    dog_aid = space.encode(Play("dog", 1, 0, (dog,)))
    assert dog_aid == 63
    assert space.to_string(dog_aid) == f"dog[{dog}]"
    pair_aid = space.encode(Play("pair", 2, 1, (mahjong, phoenix)))
    assert pair_aid == 63 + 56 + 78  # combo base + pair block + the 78 naturals
    assert space.to_string(pair_aid).startswith("pair[")


def test_tichu_card_block_round_trips_all_56() -> None:
    from cardlang.runtime.values import build_deck

    space = _space("tichu.cardlang")
    seen = set()
    for card in build_deck("tichu56"):
        aid = space.encode(card)
        assert 0 <= aid < 56
        assert aid not in seen
        seen.add(aid)
        assert space.decode(aid) == card
    assert len(seen) == 56


def test_tichu_combo_codec_round_trips_engine_emissions() -> None:
    # Every play the engine can emit from a hand must encode into the combo
    # block and decode back to the same card-set — including the engine's
    # Mahjong quirks (the Phoenix+Mahjong pair and the Mahjong-filled phoenix
    # fullhouse, which a naive closed-form universe misses).
    import random

    from cardlang.runtime.tichu import tichu_lead_options
    from cardlang.runtime.values import build_deck

    space = _space("tichu.cardlang")
    deck = build_deck("tichu56")
    rng = random.Random(11)
    checked = 0
    for _ in range(50):
        hand = rng.sample(deck, 14)
        for play in tichu_lead_options(*_tichu_bundles(), list(hand)):
            aid = space.encode(play)
            assert 57 <= aid < space.num_distinct_actions
            decoded = space.decode(aid)
            assert isinstance(decoded, ComboAction)
            assert decoded.cards == frozenset(play.cards), play
            assert space.match(aid, [play, "pass"]) is play
            checked += 1
    assert checked > 1000  # a real sweep, not a vacuous loop


def test_tichu_combo_codec_index_round_trips_every_block() -> None:
    # encode(decode(i)) == i at both edges of every block plus random interior
    # samples — the bijection holds across the full 211M-index range without
    # enumerating it.
    import random

    from cardlang.runtime.tichu import TICHU_COMBO_CODEC as codec

    rng = random.Random(23)
    edges = [0, codec.size - 1]
    samples = edges + [rng.randrange(codec.size) for _ in range(2000)]
    for i in samples:
        cards = codec.decode(i)
        assert codec.encode_cards(cards) == i
        assert codec.kind_of(i) in {
            "dog", "single", "pair", "triple", "bomb",
            "fullhouse", "straight", "pairseq",
        }


def test_coup_space_derives_its_own_5_card_block_and_the_action_names() -> None:
    from cardlang.runtime.values import build_deck

    space = _space("coup.cardlang")
    # coup15 is not standard-52-expressible (five character ranks of a "court"
    # suit), so the space derives its own block: 5 DISTINCT cards (the three
    # copies of each character share one id — identical cards are
    # interchangeable, so one id is exactly right for determinized replay).
    # Then the ten nullary names sorted (the four un-targeted actions plus the
    # six window responses — challenge/block/claim decisions are real moves at
    # the interactive scope), then the three Player-targeted actions flattened
    # over their declared domain in declaration order: 5 + 10 + 3*4 = 27.
    assert space.num_distinct_actions == 5 + 10 + 12
    assert [space.to_string(a) for a in range(5, 15)] == [
        "allow",
        "block_claiming_ambassador",
        "block_claiming_captain",
        "block_claiming_contessa",
        "block_claiming_duke",
        "challenge",
        "exchange",
        "foreign_aid",
        "income",
        "tax",
    ]
    assert [space.to_string(a) for a in range(15, 27)] == [
        f"{name}({t})" for name in ("steal", "coup", "assassinate") for t in range(4)
    ]
    seen = set()
    for card in build_deck("coup15"):
        aid = space.encode(card)
        assert 0 <= aid < 5
        seen.add(aid)
        assert space.decode(aid) == card
    assert len(seen) == 5
