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

    # Narrow the legal set one rule at a time. When a rule's card-set demand
    # would empty the running set, it cannot be satisfied — consult *that*
    # rule's `if_impossible`: an explicit `error(...)` rejects the move (raises
    # IllegalMove), an explicit card-set is the fallback, and the default (no
    # clause) drops the rule so the move stays legal under the others.
    result = set(hand)
    for rule in ctx.active_rules:
        if rule.constrains != move_type or not _applies(rule, pctx):
            continue
        if rule.demands is None or rule.demands.kind != "cards":
            continue
        narrowed = result & set(evaluate(rule.demands.expr, pctx))
        if narrowed:
            result = narrowed
        elif rule.if_impossible is not None:
            fallback = evaluate(rule.if_impossible, pctx)  # error(...) raises here
            if isinstance(fallback, (list, set, tuple)):
                result &= set(fallback)
    return [card for card in hand if card in result]


def _applies(rule: n.RuleDef, ctx: Ctx) -> bool:
    aw = rule.applies_when
    if aw is None or aw.always:
        return True
    assert aw.pred is not None
    return bool(evaluate(aw.pred, ctx))
