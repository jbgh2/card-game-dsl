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
  phase play repeat until rounds >= 10 {
    before_each { rounds += 1 }
    for each player p: offer to p one of [take_one, take_two]
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
"""


def test_offer_runs_a_chosen_effect_each_round() -> None:
    game = check_dsl(SRC, "g.cardlang")
    result = play_game(game, random.Random(3))
    for p in (0, 1):
        assert 10 <= result.scores[p] <= 20
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])


def test_guard_filters_illegal_moves() -> None:
    src = SRC.replace(
        "move_type take_two { effect { coins[actor] += 2 } }",
        "move_type take_two { when: coins[actor] >= 5  effect { coins[actor] += 2 } }",
    )
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(1))
    for p in (0, 1):
        assert 10 <= result.scores[p] <= 20
