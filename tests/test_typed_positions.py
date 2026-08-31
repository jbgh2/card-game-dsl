"""Every expression position the runtime requires a type of, and how it is guarded.

A position is a `(Node, field)` pair holding an `Expr` a designer writes freely.
Some are consumed by a runtime that requires a specific type; a wrong value there
is refused, crashed on, or -- the case this module exists for -- played, silently
and to completion, as a different game (issue #515).

The treatment each position gets is decided by what the runtime DOES with the
value, because that is what decides whether a wrong one is loud:

- `bool(...)` never raises and every non-empty value is truthy, so a wrong value
  in a Boolean position is ALWAYS silent. Those positions must be TOTAL: they
  refuse the permissive top as well as concrete wrong types.
- A value matched against a domain where "no match" is a legal answer is likewise
  silent -- a round's `trump` that matches no card plays the hand as no-trump
  while the rules still enforce trump obligations.
- A value whose consumption TESTS its type and skips on mismatch is silent for
  the same reason, even where its type looks like it would raise: a rule's
  `if_impossible` fallback is dropped, taking with it the refusal that the
  same clause correctly typed would have raised.
- A value coerced by `int(...)`, indexed, iterated, or compared RAISES. Those
  positions may stay GRADUAL: the permissive top is caught downstream, loudly.

`TAny` keeps its one meaning throughout -- the top (decisions.md, "`Any` means
the top, never a failed lookup"). This module changes which positions ADMIT it,
never what it means. `TrickOrderRow.body` was total before this module existed
and is the template the Boolean positions follow.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      `n.Node` is the closed union of AST node types, and a field whose
              annotation mentions `Expr` holds designer-written expression(s).
Establishes:  every such position carries a decided treatment; a position added
              to the AST with no entry here fails `test_every_position_is_classified`.
Illegal after: adding an `Expr`-typed field to a Node without deciding whether a
              wrong value there is loud or silent.

Ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------
property:        every `Expr`-typed field of every `n.Node` member carries a
                 treatment decided from what the runtime does with the value.
domain:          the `Expr`-bearing fields of `typing.get_args(n.Node)`, derived
                 by `derive_positions()`. Positions whose required type depends
                 on context rather than on the position (an operator's operands,
                 a call's arguments, an assignment's value) are classified
                 CONTEXTUAL and carry their checking site instead of a type --
                 they are inside the domain and named, not excluded from it.
registry:        population: `derive_positions()` over `typing.get_args(n.Node)`;
                 node union pinned by tests/test_node_registry.py;
                 type registry: `typing.get_args(cardlang.types.Type)`.
does not prove:  that a TOTAL position's guard is actually total -- this module
                 pins the CLASSIFICATION, not the guards. The executed evidence
                 that a treatment is implemented is the grid in
                 tests/test_typed_position_grid.py.
"""

from __future__ import annotations

import dataclasses
import typing

import cardlang.ast.nodes as n

# How a wrong value in this position behaves at runtime, which decides the
# treatment its guard must have.
TOTAL = "total"  # a wrong value is SILENT -- the guard must refuse TAny too
GRADUAL = "gradual"  # a wrong value RAISES downstream -- TAny may pass
CONTEXTUAL = "contextual"  # no single required type; checked against its context


def derive_positions() -> dict[tuple[str, str], str]:
    """Axis 1, derived: every `Expr`-bearing field of every `n.Node` member.

    Keyed `(node name, field name)`; the value is the annotation, so a field that
    changes from a single `Expr` to a sequence surfaces as a changed value rather
    than silently keeping its row.
    """
    out: dict[tuple[str, str], str] = {}
    for cls in typing.get_args(n.Node):
        if not (isinstance(cls, type) and dataclasses.is_dataclass(cls)):
            continue
        hints = typing.get_type_hints(cls)
        for f in dataclasses.fields(cls):
            annotation = str(hints.get(f.name, f.type)).replace("cardlang.ast.nodes.", "")
            if "Expr" in annotation:
                out[(cls.__name__, f.name)] = annotation
    return out


# The treatment table. Every derived position appears exactly once; the
# completeness test below is what makes that true rather than intended.
#
# Boolean positions are TOTAL by the rule in the module docstring: `bool()`
# cannot raise, so nothing downstream can catch a wrong value there.
TREATMENT: dict[tuple[str, str], tuple[str, str]] = {
    # -- Boolean: consumed by `bool(...)`, so a wrong value is silent ----------
    ("AppliesWhen", "pred"): (TOTAL, "Boolean"),
    ("AuctionRound", "until"): (TOTAL, "Boolean"),
    ("CardQuery", "where"): (TOTAL, "Boolean"),
    ("ClimbRound", "until"): (TOTAL, "Boolean"),
    ("Comprehension", "where"): (TOTAL, "Boolean"),
    ("DomainQuery", "where"): (TOTAL, "Boolean"),
    ("EpistemicOp", "where"): (TOTAL, "Boolean"),
    ("IfExpr", "cond"): (TOTAL, "Boolean"),
    ("IfStmt", "cond"): (TOTAL, "Boolean"),
    ("MoveEvent", "where"): (TOTAL, "Boolean"),
    ("MoveTypeDef", "when"): (TOTAL, "Boolean"),
    ("Not", "operand"): (TOTAL, "Boolean"),
    ("PlayerQuery", "where"): (TOTAL, "Boolean"),
    ("Quantifier", "body"): (TOTAL, "Boolean"),
    ("RepeatUntil", "until"): (TOTAL, "Boolean"),
    ("Transfer", "where"): (TOTAL, "Boolean"),
    ("TrickOrderRow", "body"): (TOTAL, "row-declared"),
    ("Turns", "until"): (TOTAL, "Boolean"),
    # -- matched against a domain where "no match" is legal: also silent -------
    ("TrickRound", "trump"): (TOTAL, "Suit?"),
    # A collection position, but its consumption TESTS the type and skips
    # (`runtime/rules.py`, the `isinstance(fallback, (list, set, tuple))` arm)
    # rather than coercing and raising, so a wrong value is dropped in silence
    # -- and drops the guard that would otherwise fire with it. Measured on
    # belote 2026-08-31: a narrowing fallback raises OwnerGuardError where the
    # same clause mistyped plays on, every seed differing. The sibling shape
    # done right is `evaluate.py`'s `divided by` arm, which raises.
    ("RuleDef", "if_impossible"): (TOTAL, "Collection<Card>"),
    # -- coerced / indexed / iterated / compared: raises, so gradual is loud ---
    ("Choose", "lo"): (GRADUAL, "Integer"),
    ("Choose", "hi"): (GRADUAL, "Integer"),
    ("Transfer", "amount"): (GRADUAL, "Integer"),
    ("Subscript", "index"): (GRADUAL, "key domain"),
    ("Subscript", "obj"): (GRADUAL, "Collection"),
    ("IsCheck", "operand"): (GRADUAL, "Collection"),
    ("Member", "obj"): (GRADUAL, "object"),
    ("AsBlock", "player"): (GRADUAL, "Player"),
    ("Offer", "player"): (GRADUAL, "Player"),
    ("Loser", "selection"): (GRADUAL, "Player"),
    ("Turns", "leader"): (GRADUAL, "Player"),
    ("TrickRound", "leader"): (GRADUAL, "Player"),
    ("AuctionRound", "leader"): (GRADUAL, "Player"),
    ("ClimbRound", "leader"): (GRADUAL, "Player"),
    ("PlayerQuery", "start"): (GRADUAL, "Player"),
    ("Turns", "participants"): (GRADUAL, "Collection<Player>"),
    ("TrickRound", "participants"): (GRADUAL, "Collection<Player>"),
    ("AuctionRound", "participants"): (GRADUAL, "Collection<Player>"),
    ("ClimbRound", "participants"): (GRADUAL, "Collection<Player>"),
    ("Demands", "expr"): (GRADUAL, "Collection<Card>"),
    ("RuleDef", "exempts"): (GRADUAL, "Collection<Card>"),
    ("CardQuery", "source"): (GRADUAL, "Collection<Card>"),
    ("Comprehension", "source"): (GRADUAL, "Collection"),
    ("DomainQuery", "source"): (GRADUAL, "Collection"),
    ("Transfer", "source"): (GRADUAL, "Zone"),
    ("Transfer", "dest"): (GRADUAL, "Zone"),
    ("EpistemicOp", "zone"): (GRADUAL, "Zone"),
    # -- no single required type: checked against the context it sits in ------
    ("AssignStmt", "index"): (CONTEXTUAL, "the variable's key domain"),
    ("AssignStmt", "value"): (CONTEXTUAL, "the target's declared type"),
    ("BinOp", "left"): (CONTEXTUAL, "the operator's operand rule"),
    ("BinOp", "right"): (CONTEXTUAL, "the operator's operand rule"),
    ("Call", "args"): (CONTEXTUAL, "the callee's signature"),
    ("Comprehension", "body"): (CONTEXTUAL, "the aggregation"),
    ("Comprehension", "default"): (CONTEXTUAL, "the aggregation"),
    ("DerivedField", "value"): (CONTEXTUAL, "the field's declared type"),
    ("FieldInit", "value"): (CONTEXTUAL, "the field's declared type"),
    ("FunctionDef", "body"): (CONTEXTUAL, "the call site"),
    ("IfExpr", "elifs"): (CONTEXTUAL, "branch join"),
    ("IfExpr", "otherwise"): (CONTEXTUAL, "branch join"),
    ("IfExpr", "then"): (CONTEXTUAL, "branch join"),
    ("LetStmt", "value"): (CONTEXTUAL, "the binding's uses"),
    ("ListLit", "elements"): (CONTEXTUAL, "element join"),
    ("NamedArg", "value"): (CONTEXTUAL, "rejected: named args unsupported"),
    ("PhaseQualifier", "expr"): (CONTEXTUAL, "the qualifier's phase"),
    ("Produce", "payloads"): (CONTEXTUAL, "the declared outcome payload types"),
    ("RuleRef", "args"): (CONTEXTUAL, "the rule's parameter domains"),
    ("RunStmt", "args"): (CONTEXTUAL, "the procedure's parameter domains"),
    ("StateDecl", "default"): (CONTEXTUAL, "the declared type"),
    ("Transfer", "visibility"): (CONTEXTUAL, "rejected: not honored by the runtime"),
}


def test_every_position_is_classified() -> None:
    """The completeness pin: the derived population and the treatment table are
    the same set. An `Expr`-typed field added to any node fails here until
    somebody decides whether a wrong value in it is loud or silent.

    red under: delete any entry from `TREATMENT` (or add an `Expr` field to a
    node without adding its row).
    """
    derived = set(derive_positions())
    classified = set(TREATMENT)
    assert derived == classified, (
        f"unclassified positions: {sorted(derived - classified)}\n"
        f"stale table entries:   {sorted(classified - derived)}"
    )


def test_treatments_come_from_the_closed_vocabulary() -> None:
    """Every treatment is one of the three the module docstring defines."""
    bad = {pos: t for pos, (t, _) in TREATMENT.items() if t not in (TOTAL, GRADUAL, CONTEXTUAL)}
    assert not bad, f"unknown treatments: {bad}"
