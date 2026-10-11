from cardlang.ast import nodes as n
from cardlang.parse import parse_text

SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play {
    for each player p: offer to p one of [take_one, take_two]
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { when: coins[actor] < 10  effect { coins[actor] += 2 } }
"""


def test_parses_move_types_and_offer() -> None:
    game = parse_text(SRC, "g.cardlang")
    assert {m.name for m in game.move_types} == {"take_one", "take_two"}
    one = next(m for m in game.move_types if m.name == "take_one")
    assert one.when is None and len(one.effect) == 1
    two = next(m for m in game.move_types if m.name == "take_two")
    assert two.when is not None
    phase = game.phases[0]
    foreach = next(i for i in phase.items if isinstance(i, n.ForEach))
    assert isinstance(foreach.body, n.Offer)
    assert foreach.body.offering == ("take_one", "take_two")
