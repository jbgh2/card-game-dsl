"""Axis derivation for the round-form grid (`test_round_forms.py`).

Every function here reads a DEFINITION SITE — the grammar text, the parse
builder's return annotations, an AST registry — and returns the member list.
Nothing hand-lists a domain: a fourth `round` production, a third order mode,
or a new optional clause shows up as grid rows nobody wrote, which is the
point (decisions.md, "Closed-domain completeness").

The form axis is derived by RECONCILING two sources rather than reading
either alone. The grammar says how many `round` forms a designer can write;
the parse builders say how many nodes those forms become. Before the node
split those two disagreed — three productions, one node — and nothing in the
tree said so, because no artifact crossed them. `round_nodes` crosses them,
so the disagreement is now a failure rather than a fact you had to already
know (the audit's "second definition site" rule).

Contract
--------
Assumes: the grammar file parses as text, and `cardlang.parse` imports.
Establishes: every public axis function returns a NON-EMPTY tuple, or raises
`AxisDerivationError`.
Illegal after this module: parametrizing a grid over an axis that came back
empty. An empty axis yields zero cells and a passing grid — the
vacuously-green class (decisions.md, "Closed-domain completeness"), which is
why the emptiness check lives here at the producer rather than in each
consumer.
"""

from __future__ import annotations

import dataclasses
import re
import typing
from pathlib import Path

from cardlang import parse as parse_mod
from cardlang.ast import nodes as n
from cardlang.stdlib.moves import (
    CLIMB_DECISION_MOVE_TYPE,
    RULE_ENFORCED_MOVE_TYPE,
)

GRAMMAR = Path(__file__).resolve().parent.parent / "cardlang" / "grammar" / "cardlang.lark"

# The grammar keyword that opens every form of the construct. Naming it once
# here is what makes the form axis a scrape rather than a list: a fourth form
# is a fourth production opening with this terminal.
_ROUND_TERMINAL = "_ROUND_KW"


class AxisDerivationError(AssertionError):
    """An axis came back empty, or its defining site vanished.

    `AssertionError` so a grid cell awaiting an unlanded production reddens
    under the same exception a wrong expected outcome does, keeping
    `xfail(raises=...)` marks constrained to one failure shape.
    """


def _production_bodies() -> dict[str, str]:
    """Every `name: body` production in the grammar, comments stripped.

    Reads the grammar text rather than Lark's parsed table because the grid
    must be derivable against the MERGE BASE too (the review replays
    HEAD-derived cells there), and a production that does not exist yet
    cannot be imported.
    """
    text = re.sub(r"//[^\n]*", "", GRAMMAR.read_text())
    bodies = {}
    for match in re.finditer(r"^(\??\w+):([^\n]*)$", text, re.MULTILINE):
        bodies[match.group(1).lstrip("?")] = match.group(2)
    if not bodies:
        raise AxisDerivationError(
            f"no productions matched in {GRAMMAR.name} — the scrape's shape "
            f"assumption no longer holds, so every axis below covers nothing"
        )
    return bodies


def round_productions() -> tuple[str, ...]:
    """Every grammar production that opens with the `round` keyword.

    This is the form axis at the surface: what a designer can write. A form
    added to the grammar without a node to build it fails in `round_nodes`,
    not here — this function's job is only to say what the surface admits.
    """
    found = tuple(
        name
        for name, body in _production_bodies().items()
        if body.split() and body.split()[0] == _ROUND_TERMINAL
    )
    if not found:
        raise AxisDerivationError(
            f"no production opens with {_ROUND_TERMINAL} — either the keyword "
            f"terminal was renamed or the construct moved, and either way a "
            f"grid over this axis covers nothing"
        )
    return found


def round_node_by_production() -> dict[str, type]:
    """The AST node class each round production builds, keyed by production.

    Derived by reconciling the grammar against the parse builders: the
    builder method is looked up BY THE PRODUCTION'S NAME, which is also how
    Lark dispatches to it. That is deliberate — a renamed production silently
    detaches its builder (`mypy` cannot see the link, since nothing calls the
    method by name in Python), and this lookup turns that into a failure.

    The mapping, not a set: which form builds which node is the thing a
    consumer needs, and deduplicating first is what would hide two forms
    sharing one node.
    """
    mapping: dict[str, type] = {}
    for production in round_productions():
        builder = getattr(parse_mod._Builder, production, None)
        if builder is None:
            raise AxisDerivationError(
                f"the grammar has a `{production}` production but the parse "
                f"builder has no method of that name — Lark dispatches by "
                f"name, so nothing builds it"
            )
        returns = typing.get_type_hints(builder).get("return")
        if returns is None or not hasattr(returns, "__dataclass_fields__"):
            raise AxisDerivationError(
                f"`{production}`'s builder does not return an AST node "
                f"(got {returns!r})"
            )
        mapping[production] = returns
    return mapping


def round_nodes() -> tuple[type, ...]:
    """The DISTINCT node classes the round productions build.

    Fewer members than `round_productions` means some forms share a node and
    can only be told apart by sniffing a field.
    """
    return tuple(dict.fromkeys(round_node_by_production().values()))


def optional_clauses(production: str) -> tuple[str, ...]:
    """The optional clauses of one production, named by their keyword.

    Lark spells an optional clause `[_X_KW …]`; the clause's designer-facing
    name is `X` lowercased. These are the cells most likely to go uncovered:
    the corpus witnesses whichever combinations its games happen to use, and
    a field that defaults wrongly after a refactor hides in the rest.
    """
    body = _production_bodies().get(production)
    if body is None:
        raise AxisDerivationError(f"no `{production}` production in {GRAMMAR.name}")
    out = []
    for group in re.findall(r"\[([^\]]*)\]", body):
        head = group.split()
        if not head:
            continue
        keyword = re.fullmatch(r"_([A-Z0-9]+)_KW", head[0])
        if keyword is None:
            raise AxisDerivationError(
                f"`{production}` has an optional group not opened by a keyword "
                f"terminal ({group.strip()!r}) — the clause has no name to "
                f"cross, so the scrape cannot say what the cell would be"
            )
        out.append(keyword.group(1).lower())
    return tuple(out)


def order_modes() -> tuple[str, ...]:
    """The values the auction form's `order` clause may take.

    A closed value registry, so the clause is not binary: `absent` (the
    default) and each declared mode are distinct cells. Read from the AST
    registry rather than the grammar, which admits any NAME here and leaves
    the domain to resolve.
    """
    if not n.ROUND_ORDER_MODES:
        raise AxisDerivationError("`ROUND_ORDER_MODES` is empty")
    return tuple(sorted(n.ROUND_ORDER_MODES))


# Which optional clauses carry a closed value registry, and where that
# registry lives. AUTHORED, not derived, and one of two authored mappings in
# this module: the link from a grammar keyword to the AST field it fills is a
# naming correspondence, and no artifact states it. Recorded as a residual in
# the grid's ledger rather than passed off as derived. A clause absent from
# this mapping is treated as binary (absent/present).
_CLAUSE_VALUE_REGISTRIES = {"order": order_modes}


# The one move type each form's decision site actually runs. AUTHORED for the
# same reason — the runtime hardwires it, and nothing states the pairing — but
# note what IS derived: which forms need an entry. A form carrying a
# `move_type` field and missing from this table raises rather than dropping
# out of the axis, which is what makes the gap loud instead of invisible.
_RUNNABLE_MOVE_TYPE = {
    "TrickRound": RULE_ENFORCED_MOVE_TYPE,
    "ClimbRound": CLIMB_DECISION_MOVE_TYPE,
}


def move_type_forms() -> tuple[tuple[type, str], ...]:
    """Each round node carrying a `move_type`, with the name its site runs.

    The auction form is absent because it has no `move_type` at all — its
    moves come from the `offering` — and that absence is derived from the
    node's fields, not decided here.
    """
    out = []
    for node in round_nodes():
        if "move_type" not in {f.name for f in dataclasses.fields(node)}:
            continue
        runnable = _RUNNABLE_MOVE_TYPE.get(node.__name__)
        if runnable is None:
            raise AxisDerivationError(
                f"`{node.__name__}` carries a `move_type` but no entry says which "
                f"name its decision site runs — the axis cannot say what to accept, "
                f"and a form silently dropped here is a form whose move type "
                f"nothing checks"
            )
        out.append((node, runnable))
    if not out:
        raise AxisDerivationError("no round form carries a `move_type`")
    return tuple(out)


def clause_settings(production: str) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Every grammar-reachable setting of one production's optional clauses.

    A cell is a tuple of `(clause, setting)` pairs — the full cross, so a
    combination no corpus game writes is a row nobody had to think of. The
    empty tuple is the all-clauses-absent cell, which is a real program and
    not a degenerate one.
    """
    axes = []
    for clause in optional_clauses(production):
        registry = _CLAUSE_VALUE_REGISTRIES.get(clause)
        values = ("absent",) + (registry() if registry else ("present",))
        axes.append(tuple((clause, value) for value in values))
    combinations: list[tuple[tuple[str, str], ...]] = [()]
    for axis in axes:
        combinations = [existing + (choice,) for existing in combinations for choice in axis]
    return tuple(combinations)
