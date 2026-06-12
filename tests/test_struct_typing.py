from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.parse import parse_text
from cardlang.resolve import resolve
from cardlang.typecheck import TypeEnv, env_from_game, infer
from cardlang.types import TAny, TBoolean, TEnum, TInteger, TStruct

SRC = """
type Contract = {
  level : Integer
  suit  : Suit
}
type HandResult = {
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
  state {
    deal : Contract = none
    result : HandResult = none
    score[player] : Integer = 0
  }
  winner: highest score
}
"""


def _env() -> tuple[n.Game, TypeEnv]:
    game = resolve(parse_text(SRC, "g.cardlang"))
    return game, env_from_game(game)


def test_struct_state_var_field_access_is_typed() -> None:
    _game, env = _env()
    deal = n.NameRef("deal", ref_kind="state_var")
    assert isinstance(infer(deal, env), TStruct)
    assert infer(n.Member(deal, "level"), env) == TInteger()
    assert infer(n.Member(deal, "suit"), env) == TEnum("Suit")


def test_derived_field_is_typed_from_its_expression() -> None:
    _game, env = _env()
    result = n.NameRef("result", ref_kind="state_var")
    # `made = tricks_actual >= tricks_required` infers Boolean.
    assert infer(n.Member(result, "made"), env) == TBoolean()


def test_unknown_field_infers_permissively_but_known_fields_win() -> None:
    _game, env = _env()
    deal = n.NameRef("deal", ref_kind="state_var")
    # A field not on the struct stays permissive (the error is raised in _check_expr).
    assert infer(n.Member(deal, "nonesuch"), env) == TAny()
