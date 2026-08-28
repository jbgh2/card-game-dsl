"""The serialized-IR schema is pinned to the version that names it.

`IR_VERSION` is written by `ir.py` and read by nothing — no code path
validates or rejects a document by version, and the package is unpublished
(`cardlang/ir.py` records why it deliberately stays where it is). A version
nobody reads and nobody checks cannot fail, which makes it a guarantee in
name only. This pin is what makes it able to fail: the emitted schema is
frozen against the version currently declared, so changing one without
deciding about the other stops the suite and says so.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   the discriminators and field names `ir.py` emits are exactly the
            surface `IR_VERSION` currently stands for
domain:     every `"kind"` tag literal and every dict-key literal in
            `cardlang/ir.py` -- the whole vocabulary a consumer would
            dispatch on or read
registry:   `cardlang/ir.py`'s own AST, scraped below rather than
            hand-listed, so a construct added to the emitter arrives as a
            new member instead of silently widening the schema
covered:    `test_the_emitted_ir_schema_is_the_pinned_one` -- set equality
            both ways, so an ADDED tag and a REMOVED one both fail by name
sampled:    none
residual:   a field whose spelling is unchanged but whose MEANING or value
            SHAPE changes is not caught: the scrape reads names, not
            semantics. That is a real hole in the guarantee and this ledger
            owns the record -- closing it needs a typed schema, which is
            work nobody has asked for while the IR has no consumer. R4.

red under (both pins, each demonstrated and reverted):
- schema pin: rename an emitted tag in `cardlang/ir.py` -- `outcome_case` to
  `outcome_kase` fails naming both the vanished member and the new one.
- version pin: set `IR_VERSION = 2` alone -- fails naming both numbers. Its
  first attempted witness passed, which was the harness restoring the file
  before the run rather than a dead assertion; re-run in isolation it goes
  red, and it is recorded here because an unproven pin is the thing this
  module exists to stop.
"""

from __future__ import annotations

import ast
from pathlib import Path

import cardlang
from cardlang.ir import IR_VERSION

# The schema IR_VERSION currently stands for. Recorded explicitly, never
# derived by comparison against itself: the point is that a change to the
# emitter has to be typed out here by whoever makes it, which is the moment
# they decide whether the version moves with it.
PINNED_SCHEMA: frozenset[str] = frozenset(
    {
        'key:active_rules', 'key:again', 'key:agg', 'key:always', 'key:amount',
        'key:applies_when', 'key:args', 'key:arms', 'key:binder', 'key:binders',
        'key:body', 'key:card_points', 'key:cardlang_ir', 'key:cases',
        'key:ceiling', 'key:check',
        'key:combos_fn', 'key:cond', 'key:constrains', 'key:content_flavor',
        'key:deck', 'key:decls', 'key:default', 'key:define', 'key:defines',
        'key:delta', 'key:demands', 'key:derived', 'key:dest', 'key:dest_each',
        'key:direction', 'key:directions', 'key:distribution', 'key:domain',
        'key:early_termination', 'key:effect', 'key:elements', 'key:elifs',
        'key:else', 'key:else_value', 'key:entries', 'key:event', 'key:expr',
        'key:field', 'key:fields',
        'key:follows_fn', 'key:form', 'key:func', 'key:functions', 'key:hi',
        'key:high', 'key:if_impossible', 'key:index', 'key:index_expr', 'key:item',
        'key:items', 'key:key', 'key:kind', 'key:leader', 'key:left', 'key:lo',
        'key:loser',
        'key:low', 'key:max_length', 'key:members', 'key:mode', 'key:move_type',
        'key:move_types', 'key:name', 'key:obj', 'key:offering', 'key:op',
        'key:operand', 'key:optional', 'key:order_mode', 'key:otherwise',
        'key:outcome_cases', 'key:outcome_fn', 'key:params', 'key:participants',
        'key:payload_types', 'key:payloads', 'key:phase', 'key:phases',
        'key:play_zone', 'key:player', 'key:players', 'key:positions', 'key:pred',
        'key:qualifier', 'key:quant', 'key:query', 'key:rank', 'key:rank_dir',
        'key:ranking', 'key:ranking_convention', 'key:ref', 'key:refs', 'key:right',
        'key:role', 'key:rows', 'key:rules', 'key:selection', 'key:selection_mode',
        'key:source', 'key:source_zone', 'key:state', 'key:state_var', 'key:suit',
        'key:tag', 'key:target', 'key:teams', 'key:then', 'key:transitions',
        'key:primitives', 'key:reads', 'key:return_type',
        'key:trick_order', 'key:trump', 'key:type', 'key:type_name',
        'key:type_ref', 'key:types',
        'key:until', 'key:value', 'key:values', 'key:verb', 'key:visibility',
        'key:when', 'key:where', 'key:winner', 'key:winner_fn', 'key:zone',
        'key:zones', 'tag:active_rules', 'tag:after_each', 'tag:all_players',
        'tag:applies_when', 'tag:as', 'tag:assign', 'tag:auction_round',
        'tag:before_each', 'tag:binop', 'tag:block', 'tag:call', 'tag:card',
        'tag:card_points_entry', 'tag:card_points_table',
        'tag:card_query', 'tag:choose', 'tag:climb_round', 'tag:comprehension',
        'tag:continue_to', 'tag:define', 'tag:demands', 'tag:derived_field',
        'tag:direction', 'tag:domain_query', 'tag:each_simultaneous',
        'tag:epistemic_op', 'tag:field_init', 'tag:for_each', 'tag:function',
        'tag:game', 'tag:if', 'tag:if_expr', 'tag:int', 'tag:is_check',
        'tag:legal_moves', 'tag:let', 'tag:list', 'tag:loser', 'tag:member',
        'tag:mode', 'tag:move_event', 'tag:move_type', 'tag:name', 'tag:named_arg',
        'tag:not', 'tag:offer', 'tag:outcome_case', 'tag:phase',
        'tag:phase_qualifier', 'tag:player_query', 'tag:players', 'tag:position',
        'tag:produce', 'tag:produce_arm', 'tag:produces', 'tag:quantifier',
        'tag:repeat_until', 'tag:rotate', 'tag:rule', 'tag:rule_ref',
        'tag:skip_to_next_hand', 'tag:state', 'tag:state_decl', 'tag:str',
        'tag:struct_field', 'tag:struct_lit', 'tag:subscript', 'tag:transfer',
        'tag:primitive_decl', 'tag:primitive_param', 'tag:primitive_read',
        'tag:primitives',
        'tag:transition_to', 'tag:trick_order', 'tag:trick_order_row',
        'tag:trick_round', 'tag:turns', 'tag:type_def',
        'tag:type_ref', 'tag:winner', 'tag:zone'
    }
)

# The version the set above was recorded for. If IR_VERSION moves, this moves
# with it in the same change -- otherwise the pin would silently go on
# guarding a schema that is no longer the declared one.
PINNED_FOR_VERSION = 1


def emitted_schema() -> frozenset[str]:
    """Every `kind` tag and dict key `ir.py` emits, from its own AST."""
    source = (Path(cardlang.__file__).parent / "ir.py").read_text()
    keys: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            keys.add(f"key:{k.value}")
            if k.value == "kind" and isinstance(v, ast.Constant) and isinstance(v.value, str):
                keys.add(f"tag:{v.value}")
    return frozenset(keys)


def test_the_emitted_ir_schema_is_the_pinned_one() -> None:
    """A consumer dispatches on these spellings, so changing one is a schema
    change even when every test still passes."""
    emitted = emitted_schema()
    assert emitted == PINNED_SCHEMA, (
        f"the serialized-IR schema changed -- added "
        f"{sorted(emitted - PINNED_SCHEMA)}, removed "
        f"{sorted(PINNED_SCHEMA - emitted)}. Either revert, or record the new "
        f"surface in PINNED_SCHEMA and decide whether IR_VERSION moves with "
        f"it (cardlang/ir.py says why it currently does not)."
    )


def test_the_pin_names_the_declared_version() -> None:
    """The schema above is pinned FOR a version; if `IR_VERSION` moves and
    this does not, the pin guards a schema nobody declared."""
    assert PINNED_FOR_VERSION == IR_VERSION, (
        f"IR_VERSION is {IR_VERSION} but the pinned schema was recorded for "
        f"{PINNED_FOR_VERSION} -- re-record PINNED_SCHEMA against the new "
        f"version and update PINNED_FOR_VERSION in the same change."
    )
