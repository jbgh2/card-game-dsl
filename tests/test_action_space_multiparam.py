from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.openspiel.encoding import ActionSpace
from cardlang.runtime.values import Card

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
move_type ask(target : Player, rank : Rank) { when: target != actor effect { done := 1 } }
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
    PLAIN `offer` (previously only its rejection cases were tested —
    test_resolve_param_domains.py's `test_offer_of_a_card_param_without_a_hand_zone_rejected`
    and `test_offer_of_two_card_parameterized_moves_rejected` — and the
    accept+encode path was only exercised via a `round offering` vocabulary,
    Schnapsen's `play_card` in test_openspiel_encoding.py). `check_dsl` (not
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
