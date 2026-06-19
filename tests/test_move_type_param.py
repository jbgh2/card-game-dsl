"""A `move_type` may carry one typed parameter drawn from an enumerable domain.

This is the first WS1 (auction) primitive: an auction's move vocabulary is
parameterized moves (Bridge's `submit_bid(strain)`), whose legal instantiations a
later commit will flatten into one per-turn candidate list. Here we pin only the
frontend: the parameter parses, survives resolve/typecheck, and reaches the IR.
"""

from __future__ import annotations

from typing import Any

from cardlang.ir import emit
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0  picked[player] : Suit? = none }
  phase play { for each player p: coins[p] += 1 }
  winner: highest coins
}
move_type pick(s : Suit?) { effect { picked[actor] := s } }
"""


def test_parameterized_move_type_records_param() -> None:
    game = parse_text(SRC, "g.cardlang")
    pick = next(m for m in game.move_types if m.name == "pick")
    assert pick.param is not None
    assert pick.param.name == "s"
    assert pick.param.type_name == "Suit?"


def test_nullary_move_type_has_no_param() -> None:
    # A move_type without parentheses keeps param=None (the existing form).
    src = SRC.replace("move_type pick(s : Suit?)", "move_type pick").replace(
        "picked[actor] := s", "coins[actor] += 1"
    )
    game = parse_text(src, "g.cardlang")
    pick = next(m for m in game.move_types if m.name == "pick")
    assert pick.param is None


def test_parameterized_move_type_round_trips_to_ir() -> None:
    ir: Any = emit(check_dsl(SRC, "g.cardlang"))
    pick = next(m for m in ir["move_types"] if m["name"] == "pick")
    assert pick["param"] == {"name": "s", "type_name": "Suit?"}
