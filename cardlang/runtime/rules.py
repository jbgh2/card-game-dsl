"""The legal-move engine: which cards a player may play.

For the move type in play, the legal set is the intersection of every active
rule's card-set `demands` whose `applies_when` holds (decisions.md "Rule demand
forms"). An empty intersection falls back via `if_impossible` (default: the
whole hand). Move-shape demands (`actions where …`) don't filter card plays;
they constrain the choose-count at the call site instead.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player


def legal_cards(player: Player, move_type: str, ctx: Ctx) -> list[Card]:
    pctx = ctx.acting_as(player)
    hand = pctx.rs.zones.instance("hand", player).cards

    constraints: list[set[Card]] = []
    for rule in ctx.active_rules:
        if rule.constrains != move_type or not _applies(rule, pctx):
            continue
        if rule.demands is not None and rule.demands.kind == "cards":
            constraints.append(set(evaluate(rule.demands.expr, pctx)))

    result = set(hand)
    for c in constraints:
        result &= c
    if not result:
        return list(hand)  # if_impossible default: any card in hand
    return [card for card in hand if card in result]


def _applies(rule: n.RuleDef, ctx: Ctx) -> bool:
    aw = rule.applies_when
    if aw is None or aw.always:
        return True
    assert aw.pred is not None
    return bool(evaluate(aw.pred, ctx))
