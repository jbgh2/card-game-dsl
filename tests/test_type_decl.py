from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.parse import parse_text

TYPES = """
type Contract = {
  level : Integer
  suit  : Suit
}
type HandResult = {
  contract        : Contract
  tricks_required : Integer
  tricks_actual   : Integer
} derived {
  made = tricks_actual >= tricks_required
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  winner: highest score
  state { score[player] : Integer = 0 }
}
"""


def test_type_decls_parse_into_game() -> None:
    game = parse_text(TYPES, "g.cardlang")
    assert [t.name for t in game.types] == ["Contract", "HandResult"]
    contract = game.types[0]
    assert [(f.name, f.type_name, f.optional) for f in contract.fields] == [
        ("level", "Integer", False),
        ("suit", "Suit", False),
    ]
    hand_result = game.types[1]
    assert [d.name for d in hand_result.derived] == ["made"]
    assert isinstance(hand_result.derived[0].value, n.BinOp)
