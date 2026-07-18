"""The legal-move engine: which cards a player may play.

For the move type in play, the legal set is the intersection of every active
rule's card-set `demands` whose `applies_when` holds (decisions.md "Rule demand
forms"). An empty intersection falls back via `if_impossible` (default: the
whole hand). Move-shape demands (`actions where …`) don't filter card plays;
they constrain the choose-count at the call site instead. A rule's `exempts`
(when its `applies_when` holds) removes cards from the cascade entirely and
appends them after every other candidate, in hand order (Tarot's Excuse:
always playable, never bound by an obligation, offered last).
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, elements
from cardlang.runtime.values import Card, Player


def legal_cards(player: Player, move_type: str, ctx: Ctx) -> list[Card]:
    pctx = ctx.acting_as(player)
    hand = pctx.rs.zones.instance("hand", player).cards

    # A pre-pass: cards any APPLICABLE rule `exempts` sit outside the demand
    # cascade entirely — never narrowed by it, never needed to satisfy it —
    # and are appended LAST, in hand order, after every other legal card
    # (Tarot's Excuse: always playable, offered after the constrained
    # candidates, regardless of hand position — the `base + excuse` order the
    # RNG stream depends on). A game with no `exempts` rule leaves this set
    # empty, making the rest of this function list-identical to before.
    exempt: set[Card] = set()
    for rule in ctx.active_rules:
        if rule.constrains != move_type or rule.exempts is None:
            continue
        if not _applies(rule, pctx):
            continue
        exempt |= set(evaluate(rule.exempts, pctx))
    working = [c for c in hand if c not in exempt]

    # Narrow the legal set one rule at a time. When a rule's card-set demand
    # would empty the running set, it cannot be satisfied — its `if_impossible`
    # decides what happens: an explicit `error(...)` rejects the move (raises
    # IllegalMove), and a card-set fallback (e.g. `hand`) replaces the empty set.
    # A card-set demand with no `if_impossible` is a malformed game — rejected at
    # resolve time, so reaching it here is a backstop error, never a silent drop.
    result = set(working)
    for rule in ctx.active_rules:
        if rule.constrains != move_type or not _applies(rule, pctx):
            continue
        if rule.demands is None or rule.demands.kind != "cards":
            continue
        narrowed = result & set(evaluate(rule.demands.expr, pctx))
        if narrowed:
            result = narrowed
        elif rule.if_impossible is None:
            raise RuntimeError(
                f"rule '{rule.name}' filtered out every legal card for "
                f"'{move_type}' and declares no `if_impossible` fallback"
            )
        else:
            # error(...) raises here; `elements` is the same Zone -> .cards
            # coercion state.py centralizes for every Zone-or-collection
            # site (e.g. `if_impossible: hand` — play any card).
            fallback = elements(evaluate(rule.if_impossible, pctx))
            if isinstance(fallback, (list, set, tuple)):
                result &= set(fallback)
    return [c for c in working if c in result] + [c for c in hand if c in exempt]


def _applies(rule: n.RuleDef, ctx: Ctx) -> bool:
    aw = rule.applies_when
    if aw is None or aw.always:
        return True
    assert aw.pred is not None  # parse builds `applies_when` as `always` or a predicate
    return bool(evaluate(aw.pred, ctx))
