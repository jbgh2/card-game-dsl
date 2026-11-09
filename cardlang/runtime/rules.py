"""The legal-move engine: which cards a player may play.

For the [[move-type]] in play, the legal set is the intersection of every active
[[rule]]'s card-set `demands` whose `applies_when` holds (decisions.md "Rule
demand forms"). An empty intersection falls back via `if_impossible` (default:
the whole hand). A rule binds here and nowhere else: every other decision is
legal or not by the construct that makes it (a [[transfer]]'s `chosen N`, a
move type's When Clause). A rule's `exempts` (when its `applies_when` holds)
removes cards from the cascade entirely and appends them after every other
candidate, in hand order (Tarot's Excuse: always playable, never bound by an
obligation, offered last).

Contract
--------
Assumes: `ctx.round_source` bound by the trick form to the acting seat's Play
Source, and every active rule checked by resolve (its `constrains:` names the
move type asked about, a `demands` carries its `if_impossible`).
Establishes: the legal card list for that one decision, the trick round's
card decision. Illegal after this: a second caller -- the one-site law is
pinned by tests/test_rule_sites.py.
Held by: the one-site law is Derived and Pinned, the AST census of
tests/test_rule_sites.py; not higher, because which code may consult the
cascade is a fact about the call graph, which no type in the engine holds.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, elements
from cardlang.runtime.values import Card, Player


def legal_cards(player: Player, move_type: str, ctx: Ctx) -> list[Card]:
    pctx = ctx.acting_as(player)
    # The pool is the acting seat's Play Source, which the trick round binds
    # (`ctx.round_source` — the declared family's instance, or the routed zone
    # under Delegated Play). A rule clause's bare `hand` reads the same binding,
    # so the demands cascade and this pool cannot disagree.
    if pctx.round_source is None:
        raise ShadowGuardError(
            "runtime.mechanics trick form",
            f"legal cards for '{move_type}' were asked with no trick round's "
            f"Play Source bound",
        )
    hand = pctx.round_source[1].cards

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
    # resolve time, so reaching it here fires a Shadow Guard, never a silent drop.
    result = set(working)
    for rule in ctx.active_rules:
        if rule.constrains != move_type or not _applies(rule, pctx):
            continue
        if rule.demands is None:
            continue
        narrowed = result & set(evaluate(rule.demands.expr, pctx))
        if narrowed:
            result = narrowed
        elif rule.if_impossible is None:
            raise ShadowGuardError(
                "resolve._resolve_rule",
                f"rule '{rule.name}' filtered out every legal card for "
                f"'{move_type}' and declares no `if_impossible` fallback",
            )
        else:
            # error(...) raises here; `elements` is the same Zone -> .cards
            # coercion state.py centralizes for every Zone-or-collection
            # site (e.g. `if_impossible: hand` — play any card).
            fallback = elements(evaluate(rule.if_impossible, pctx))
            if not isinstance(fallback, (list, set, tuple)):
                # Skipping here would drop the fallback AND the refusal a
                # narrowing fallback would have raised, so a wrong value would
                # widen the legal set in silence. Typecheck refuses the shape a
                # designer can write (`_check_if_impossible`); this is the
                # Shadow Guard for a value that reaches here anyway.
                raise ShadowGuardError(
                    "typecheck._check_if_impossible",
                    f"rule '{rule.name}' `if_impossible` evaluated to "
                    f"{fallback!r}, which is not a set of cards",
                )
            result &= set(fallback)
    return [c for c in working if c in result] + [c for c in hand if c in exempt]


def _applies(rule: n.RuleDef, ctx: Ctx) -> bool:
    aw = rule.applies_when
    if aw is None:
        return True
    return bool(evaluate(aw.pred, ctx))
