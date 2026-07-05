"""Grammar/AST/IR for the rule `exempts:` clause. Runtime semantics are in
test_rule_exempts.py; this pins the frontend only, including the load-bearing
property that the IR key is emitted ONLY when a rule declares `exempts:` — an
ordinary rule (no `exempts`) must not gain an `"exempts"` key at all, which is
what keeps every pre-existing rule's golden byte-identical.
"""

from __future__ import annotations

from typing import Any

from cardlang.ast import nodes as n
from cardlang.ir import emit
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

SRC = """
game Mini {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase p {
    active_rules: [MustFollowSuit, JokerIsExempt]
    legal_moves:  [play_to_trick]
  }
  winner: highest score
}

rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
  if_impossible: hand
}

rule JokerIsExempt {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  exempts: hand.where(c => c.rank == "2")
}
"""


def _rule(game: n.Game, name: str) -> n.RuleDef:
    return next(r for r in game.rules if r.name == name)


def test_exempts_parses_as_an_expr() -> None:
    game = parse_text(SRC, "mini.cardlang")
    exempt_rule = _rule(game, "JokerIsExempt")
    plain_rule = _rule(game, "MustFollowSuit")
    assert isinstance(exempt_rule.exempts, n.MethodCall)
    assert exempt_rule.exempts.method == "where"
    assert plain_rule.exempts is None


def test_exempts_ir_key_emitted_only_when_present() -> None:
    ir: Any = emit(check_dsl(SRC, "mini.cardlang"))
    exempt_rule_ir = next(r for r in ir["rules"] if r["name"] == "JokerIsExempt")
    plain_rule_ir = next(r for r in ir["rules"] if r["name"] == "MustFollowSuit")

    assert "exempts" in exempt_rule_ir
    assert exempt_rule_ir["exempts"]["kind"] == "method_call"
    assert exempt_rule_ir["exempts"]["method"] == "where"

    # The whole point: a rule without `exempts:` carries NO such key at all
    # (not `"exempts": null`) — this is what keeps every pre-existing rule
    # golden byte-identical after this change.
    assert "exempts" not in plain_rule_ir
