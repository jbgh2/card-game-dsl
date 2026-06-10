from __future__ import annotations

import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# Both halves together: a define produces a struct-carrying variant; the
# consumer matches exhaustively and reads a derived field off the bound struct
# payload.
SRC = """
type Contract = {
  level : Integer
  made  : Integer
} derived {
  surplus = made - level
}
define resolve_hand -> { contract_made(Contract) | passed_out } {
  produce contract_made(Contract { level: 4, made: 6 })
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      resolve_hand produces:
        contract_made(c) { points[p] += c.surplus }
        passed_out       { points[p] += 0 }
  }
  winner: highest points
}
"""


def test_struct_carrying_variant_runs_end_to_end() -> None:
    game = check_dsl(SRC, "g.cardlang")  # parse + resolve + typecheck all clean
    result = play_game(game, random.Random(0))
    # surplus = made(6) - level(4) = 2, for each player.
    assert result.scores[0] == 2 and result.scores[1] == 2
