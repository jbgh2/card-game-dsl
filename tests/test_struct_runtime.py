from __future__ import annotations

import random

from cardlang.ast import nodes as n
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


def test_struct_literal_parses_in_expression_position() -> None:
    src = """
    type Contract = { level : Integer  suit : Suit }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state { deal : Contract = Contract { level: 1, suit: hearts } }
      winner: highest score
    }
    """
    game = parse_text(src, "g.cardlang")
    assert game.state is not None
    default = game.state.decls[0].default
    assert isinstance(default, n.StructLit)
    assert default.type_name == "Contract"
    assert [fi.name for fi in default.fields] == ["level", "suit"]


def test_struct_value_field_is_readable_at_runtime() -> None:
    src = """
    type Contract = { level : Integer  suit : Suit }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state {
        deal : Contract = Contract { level: 7, suit: hearts }
        top[player] : Integer = 0
      }
      phase play { for each player p: top[p] := deal.level }
      winner: highest top
    }
    """
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 7 and result.scores[1] == 7
