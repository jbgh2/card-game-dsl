import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0  rounds : Integer = 0 }
  phase play repeat until rounds >= 3 {
    before_each { rounds += 1 }
    for each player p: coins[p] += 1
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
"""


def test_driver_builds_move_type_index_and_game_runs() -> None:
    game = check_dsl(SRC, "g.cardlang")
    result = play_game(game, random.Random(0))
    # 2 players, 3 rounds, +1 each round -> 3 coins each; winner is player 0 or 1.
    assert result.scores[0] == 3 and result.scores[1] == 3
    assert result.winner in (0, 1)
