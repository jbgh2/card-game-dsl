from typing import Any

from cardlang.ir import emit
from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play { for each player p: offer to p one of [take_one, take_two] }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
"""


def test_ir_has_move_types_and_offer() -> None:
    ir: Any = emit(check_dsl(SRC, "g.cardlang"))
    assert [m["name"] for m in ir["move_types"]] == ["take_one", "take_two"]
    assert ir["move_types"][0]["kind"] == "move_type"
    phase = ir["phases"][0]
    foreach = next(i for i in phase["items"] if i["kind"] == "for_each")
    assert foreach["body"]["kind"] == "offer"
    assert foreach["body"]["move_types"] == ["take_one", "take_two"]
