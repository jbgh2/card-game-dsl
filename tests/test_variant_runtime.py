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


def test_arm_binder_does_not_leak_into_outer_scope() -> None:
    # The arm binder `carry` shares a name with the state var `carry`. The binder
    # must be scoped to its arm only: outside the arm, `carry` reads the state var
    # (9), not the binder — otherwise the outer read misclassifies as a local and
    # KeyErrors at runtime.
    src = """
define pick -> { chose(Integer) | nope } { produce chose(5) }
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0  carry : Integer = 9 }
  phase play {
    for each player p:
      pick produces:
        chose(carry) { points[p] += carry }
        nope         { points[p] += 0 }
    for each player q: points[q] += carry
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    # arm binds carry=5 (per player), then the outer read uses state carry=9 => 14.
    assert result.scores[0] == 14 and result.scores[1] == 14
