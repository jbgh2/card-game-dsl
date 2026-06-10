from __future__ import annotations

import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# A define whose body deterministically produces one variant; the produces:
# consumer dispatches to the matching arm and binds the payload.
SRC = """
define settle -> { won(Integer) | lost } {
  produce won(7)
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""


def test_produces_dispatches_to_the_produced_arm_and_binds_payload() -> None:
    game = check_dsl(SRC, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 7 and result.scores[1] == 7
