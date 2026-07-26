import random

import pytest

from cardlang.openspiel.encoding import ActionSpace
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, deck_suits

GAME = """
game G {
  players: 4
  max_length: 50
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { hand[player] : Hand<player> }
  state { done : Integer = 0 }
  phase play { offer to 0 one of [ask] done := 1 }
  winner: highest done
}
move_type ask(target : Player, rank : Rank) { when: target is not actor effect { done := 1 } }
"""


def test_cross_product_vocab_ids_round_trip() -> None:
    game = parse_text(GAME, "g.cardlang")
    space = ActionSpace.for_game(game)
    # 4 targets x 13 ranks = 52 ask candidates; every (t, r) encodes distinctly
    ids = {space.encode(("ask", (t, r))) for t in range(4) for r in
           ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]}
    assert len(ids) == 52
    for t in range(4):
        aid = space.encode(("ask", (t, "K")))
        assert space.decode(aid) == ("ask", (t, "K"))


CARD_OFFER_GAME = """
game G2 {
  players: 4
  max_length: 50
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { hand[player] : Hand<player> }
  state { done : Integer = 0 }
  phase play { offer to 0 one of [play_card] done := 1 }
  winner: highest done
}
move_type play_card(c : Card) { effect { done := 1 } }
"""


def test_single_card_param_via_plain_offer_encodes_to_the_card_block() -> None:
    """The accept+encode happy path for a single-`Card`-param move under a
    PLAIN `offer` (its rejection cases live in
    test_resolve_param_domains.py's `test_offer_of_a_card_param_without_a_hand_zone_rejected`
    and `test_offer_of_two_card_parameterized_moves_rejected`, and the
    accept+encode path is otherwise exercised only via a `round offering`
    vocabulary, Schnapsen's `play_card` in test_openspiel_encoding.py).
    `check_dsl` (not
    bare `parse_text`) proves the game is actually ACCEPTED — a `hand[player]`
    zone is declared, so `_check_card_vocabulary` (resolve.py) has nothing to
    reject. `ActionSpace` mints no vocab id for `play_card`: its candidates
    ARE the card block, exactly like a bare card play (Option B, the module
    docstring in cardlang/openspiel/encoding.py)."""
    game = check_dsl(CARD_OFFER_GAME, "g2.cardlang")
    space = ActionSpace.for_game(game)
    assert space.num_distinct_actions == 52  # no extra vocab id for play_card
    card = Card("A", "hearts")
    aid = space.encode(("play_card", card))
    assert aid == space.encode(card) < 52
    assert space.decode(aid) == card


SUBSET_RANKING_GAME = """
game G3 {
  players: 4
  max_length: 50
  cards: standard52
  ranking: A K Q
  zones { hand[player] : Hand<player> }
  state { done : Integer = 0 }
  phase play { offer to 0 one of [ask] done := 1 }
  winner: highest done
}
move_type ask(target : Player, rank : Rank) { when: target is not actor effect { done := 1 } }
"""


def test_rank_domain_sourced_from_game_ranking_not_deck() -> None:
    """Regression test for a param-domain sourcing divergence: `ActionSpace.for_game`
    must source the `Rank` parameter domain from `game.ranking` — the SAME
    origin `mechanics.param_domain` reads at runtime (`ctx.rs.rank_index`,
    which `driver.py` builds from `game.ranking`) — never from the deck's own
    ranks. Sourced separately the two would coincide only by accident
    (`ranking is a subset of deck ranks`, unenforced); a game whose
    `ranking:` is a strict
    SUBSET of its deck's ranks exposes the divergence directly: `ranking: A K
    Q` under `cards: standard52` (13 ranks) resolves cleanly via `check_dsl`
    — nothing requires a `ranking:` to cover every deck rank — so this is a
    legal game, not a hypothetical.
    """
    game = check_dsl(SUBSET_RANKING_GAME, "g3.cardlang")
    assert game.ranking == ("A", "K", "Q")
    space = ActionSpace.for_game(game)

    # Exactly 4 players x 3 ranks = 12 vocab entries (52 card block + 12).
    # Deck-sourced (the pre-fix bug), this would instead be 52 + 4*13 = 104:
    # the deck's full 13 ranks, not the 3 the game actually declared.
    assert space.num_distinct_actions == 52 + 12

    # Every (target, rank) combination over the DECLARED ranking round-trips.
    for target in range(4):
        for rank in ("A", "K", "Q"):
            aid = space.encode(("ask", (target, rank)))
            assert space.decode(aid) == ("ask", (target, rank))

    # "J" is a deck rank absent from the declared ranking. Sourced correctly
    # (from `game.ranking`), it was never enumerated into the vocab, so
    # encoding it must raise. Deck-sourced (the pre-fix bug), it would
    # silently succeed with a dead/wrong action id instead.
    with pytest.raises(KeyError):
        space.encode(("ask", (0, "J")))


TICHU_SUIT_GAME = """
game GTichu {
  players: 4
  max_length: 50
  cards: tichu56
  zones { deck : Deck  hand[player] : Hand<player> }
  state { done[player] : Integer = 0 }
  phase play { offer to 0 one of [declare_suit] }
  winner: highest done
}
move_type declare_suit(s : Suit) { effect { done[actor] := 1 } }
"""


def test_suit_domain_sourced_from_deck_cards_not_declared_deck_suits() -> None:
    """Regression test for a param-domain sourcing divergence: the Suit parameter domain
    must be sourced identically at compile time (`ActionSpace.for_game`) and at
    runtime (`driver.play_game`'s `rs.suits`, read by `mechanics.param_domain`)
    — both from `runtime.values.deck_suits` (the deck's ACTUAL card suits),
    never from the declared `Deck.suits` field. `tichu56` exposes the
    divergence directly: its declared `Deck.suits` is the French four, but its
    real deck (standard 52 plus the four specials) carries a fifth suit,
    "special", that only shows up in the card block. No `ranking:` is needed
    for this game — a Suit-parameterized move never touches `game.ranking`/
    `rs.rank_index`.
    """
    assert deck_suits("tichu56") == ("clubs", "diamonds", "hearts", "spades", "special")

    game = check_dsl(TICHU_SUIT_GAME, "gtichu.cardlang")
    space = ActionSpace.for_game(game)
    # The compile-time action space already advertises "special" (it derives
    # its Suit domain from the deck's card block, never the declared field).
    aid = space.encode(("declare_suit", "special"))
    assert space.decode(aid) == ("declare_suit", "special")

    captured: dict[str, tuple[str, ...]] = {}

    def hook(rs: RuntimeState) -> None:
        captured["suits"] = rs.suits

    play_game(game, random.Random(0), on_first_decision=hook)
    # The runtime domain (driver.py's `rs.suits`) must be the SAME set the
    # compile-time action space advertises — were `rs.suits` the deck's
    # declared French-4 `Deck.suits`, "special" would be missing entirely, so
    # a legal `declare_suit(special)` decision would never be enumerated as a
    # live candidate even though `ActionSpace` has already minted it an
    # action id.
    assert captured["suits"] == deck_suits("tichu56")
