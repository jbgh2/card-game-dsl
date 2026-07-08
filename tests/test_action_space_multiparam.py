import pytest

from cardlang.parse import parse_text
from cardlang.openspiel.encoding import ActionSpace

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
