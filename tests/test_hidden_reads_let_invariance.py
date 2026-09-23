"""Hoisting a subexpression into a `let` never changes a Hidden Read verdict.

A second derivation of the Hidden Read check's verdicts, independent of the
grid's expected columns: every cell of tests/test_hidden_reads.py whose
judged expression sits in a statement is re-run with one of its
subexpressions bound by a `let` immediately before that statement, in the
same scope, and the verdict must not move.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        let-abstraction invariance: replacing a subexpression of a
                 judged position with a name bound to it by a `let` in the
                 same acting-seat scope, immediately before the use, leaves
                 the verdict unchanged -- accepted stays accepted, and a
                 refusal names the same zones.
domain:          every cell of the Hidden Read grids (the verdict, relation,
                 route, indirection and misuse-probe cells) whose judged
                 expression is part of a statement that sits in a statement
                 sequence: a chosen movement's amount, source, `where` and
                 destination, and a `choose` in an assignment. Each such
                 statement yields one variant per hoistable subexpression --
                 the whole amount, source and destination, every zone
                 reference inside the four, and every zone reference's index
                 -- mechanically, from the parsed cell and its spans. A
                 subexpression naming a binder the statement introduces
                 (`card`, `cards`) is not hoistable: the `let` would read it
                 outside its scope. A value bound under another acting seat
                 is the designed exception to invariance and never arises
                 here: the `let` is bound in the use's own scope.
registry:        the cells: tests/test_hidden_reads.py's grids; the
                 positions judged: `cardlang.resolve.HIDDEN_READ_POSITIONS`.
does not prove:  invariance at a position no statement holds -- a move type's
                 `when:`, a rule's clauses, a phase qualifier, a transition
                 trigger -- where no `let` can be written before the use; nor
                 for a route cell that needs a library, which runs under a
                 monkeypatch this module does not repeat.
"""

from __future__ import annotations

import dataclasses
import re
import typing
from collections.abc import Iterator
from typing import cast

import pytest

import tests.test_hidden_reads as G
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

_NAME = "hoisted_value"


def _cell_sources() -> Iterator[tuple[str, str]]:
    """(cell id, game source) for every unmarked grid cell."""
    for param in G._VERDICT_CELLS:
        if param.marks:  # type: ignore[attr-defined]
            continue
        label, need, zone_type, relation, _ = param.values  # type: ignore[attr-defined]
        _, _, build = G._POSITIONS[label]
        body, defs = build(need, G._zone_ref(zone_type, relation))
        decl, teams = G._zone_decl(zone_type)
        yield param.id, G._game(body, defs, zone=decl, teams=teams)  # type: ignore[attr-defined]
    for cells in (G._destination_cells(), G._relation_cells(), G._indirection_cells()):
        for param in cells:
            if param.marks:  # type: ignore[attr-defined]
                continue
            body, defs, zone, teams, _ = param.values  # type: ignore[attr-defined]
            yield param.id, G._game(body, defs, zone=zone, teams=teams)  # type: ignore[attr-defined]
    for param in G._route_cells():
        body, defs, primitives, library, _ = param.values  # type: ignore[attr-defined]
        if not library:
            yield param.id, G._game(body, defs, primitives=primitives)  # type: ignore[attr-defined]
    for param in G._probe_cells():
        body, defs, zone, _, _ = param.values  # type: ignore[attr-defined]
        yield param.id, G._game(body, defs, zone=zone)  # type: ignore[attr-defined]


def _in_sequences(node: object) -> Iterator[n.Stmt]:
    """Every statement that sits in a statement sequence, where a `let` may
    be written before it."""
    if not dataclasses.is_dataclass(node) or isinstance(node, type):
        return
    for f in dataclasses.fields(node):
        value = getattr(node, f.name)
        items = value if isinstance(value, tuple) else (value,)
        stmt_tuple = isinstance(value, tuple) and any(
            isinstance(v, typing_stmts()) for v in value
        )
        for item in items:
            if stmt_tuple and isinstance(item, typing_stmts()):
                yield cast(n.Stmt, item)
            yield from _in_sequences(item)


def typing_stmts() -> tuple[type, ...]:
    return typing.get_args(n.Stmt)


def _zone_refs(expr: object, zones: set[str]) -> Iterator[n.Expr]:
    """Every zone reference inside `expr`, and every such reference's index."""
    if isinstance(expr, n.Subscript) and isinstance(expr.obj, n.NameRef) and expr.obj.name in zones:
        yield expr
        yield expr.index
        yield from _zone_refs(expr.index, zones)
        return
    if isinstance(expr, n.NameRef) and expr.name in zones:
        yield expr
        return
    if dataclasses.is_dataclass(expr) and not isinstance(expr, type):
        for f in dataclasses.fields(expr):
            value = getattr(expr, f.name)
            for item in value if isinstance(value, tuple) else (value,):
                yield from _zone_refs(item, zones)


def _names(expr: object) -> set[str]:
    out: set[str] = set()
    if isinstance(expr, n.NameRef):
        out.add(expr.name)
    if dataclasses.is_dataclass(expr) and not isinstance(expr, type):
        for f in dataclasses.fields(expr):
            value = getattr(expr, f.name)
            for item in value if isinstance(value, tuple) else (value,):
                out |= _names(item)
    return out


def _hoistable(stmt: n.Stmt, zones: set[str]) -> Iterator[n.Expr]:
    positions: list[object] = []
    whole: list[object] = []
    if isinstance(stmt, n.Transfer) and stmt.selection_mode == "chosen":
        # A `to each` destination is a bare family name by its own guard.
        dest = () if stmt.dest_each else (stmt.dest,)
        whole = [p for p in (stmt.amount, stmt.source, *dest) if not isinstance(p, str)]
        positions = whole + [stmt.where]
    elif isinstance(stmt, n.AssignStmt) and any(
        isinstance(x, n.Choose) for x in _walk(stmt.value)
    ):
        positions = [stmt.value]
    seen: set[tuple[int, int]] = set()
    for expr in [*whole, *(r for p in positions for r in _zone_refs(p, zones))]:
        assert isinstance(expr, (n.NameRef, n.Subscript, n.IntLit, n.Call, n.BinOp,
                                 n.CardQuery, n.IfExpr, n.Member, n.Comprehension,
                                 n.IsCheck, n.Not, n.Quantifier, n.PlayerQuery,
                                 n.DomainQuery, n.SubsetQuery, n.Choose, n.ListLit,
                                 n.StrLit, n.CardLiteral, n.AllPlayers))
        span = expr.span
        if span is None or (span.start, span.end) in seen:
            continue
        if _names(expr) & {"card", "cards", "piece", "pieces"}:
            continue
        seen.add((span.start, span.end))
        yield expr


def _walk(node: object) -> Iterator[object]:
    yield node
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        for f in dataclasses.fields(node):
            value = getattr(node, f.name)
            for item in value if isinstance(value, tuple) else (value,):
                yield from _walk(item)


def _variants() -> list[object]:
    out: list[object] = []
    for cell_id, source in _cell_sources():
        game = parse_text(source, "cell.cardlang")
        zones = {z.name for z in game.zones}
        for stmt in _in_sequences(game):
            if stmt.span is None:
                continue
            for expr in _hoistable(stmt, zones):
                assert expr.span is not None
                start, end = expr.span.start, expr.span.end
                at = stmt.span.start
                text = source[start:end]
                variant = (
                    source[:at] + f"let {_NAME} = {text}  " + source[at:start]
                    + _NAME + source[end:]
                )
                variant_id = f"{cell_id}@{text}"
                marks = (
                    [pytest.mark.xfail(strict=True, raises=AssertionError, reason=_RED[variant_id])]
                    if variant_id in _RED
                    else []
                )
                out.append(pytest.param(source, variant, id=variant_id, marks=marks))
    return out


# variant -> why it moves the verdict: a destination bound by a `let` is read
# at the `let`'s need, not named as the destination position names it.
_DESTINATION = "a destination hoisted into a `let` counts its contents as read"
_RED: dict[str, str] = {
    f"destination-{zone_type}@{ref}": _DESTINATION
    for zone_type, ref in (
        ("ChipStack", "probe[actor offset_by left]"),
        ("FaceDownPile", "probe"),
        ("Deck", "probe"),
        ("HiddenPile", "probe[actor offset_by left]"),
        ("Burn", "probe"),
        ("Muck", "probe"),
        ("Hand", "probe[actor offset_by left]"),
        ("HiddenStack", "probe[1]"),
    )
}



_ZONE = re.compile(
    r"reads (?:whether |how many cards |the cards in |the order of the cards in )?"
    r"(?:every )?`(\w+)"
)


def _verdict(source: str) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """Accepted or not, the zones each Hidden Read refusal names, and every
    other refusal's text -- location stripped."""
    try:
        check_dsl(source, "cell.cardlang")
    except DiagnosticError as err:
        lines = [str(err).split(": error: ", 1)[-1]]
        for note in getattr(err, "__notes__", []):
            lines = [line.split(": error: ", 1)[-1] for line in note.splitlines()]
        zones = sorted(m.group(1) for line in lines if (m := _ZONE.search(line)))
        others = sorted(line for line in lines if not _ZONE.search(line))
        return False, tuple(zones), tuple(others)
    return True, (), ()


_VARIANTS = _variants()


@pytest.mark.parametrize("source,variant", _VARIANTS)
def test_hoisting_into_a_let_keeps_the_verdict(source: str, variant: str) -> None:
    """The variant binds one subexpression by a `let` just before its
    statement; the verdict is the original's."""
    assert _verdict(variant) == _verdict(source)


def test_the_hoists_reach_every_statement_position() -> None:
    """The variants hoist from every statement position the Hidden Read check
    judges, so a green here is not a green over a narrower set.

    red under: return no subexpression for a `Transfer` from `_hoistable`."""
    variants = [v.values[1] for v in _VARIANTS]  # type: ignore[attr-defined]
    hoisted = " ".join(variants)
    for spelling in ("to hoisted_value", "from hoisted_value", "chosen (hoisted_value)"):
        assert spelling in hoisted, spelling
    assert any(
        "choose integer" in v and f"let {_NAME} = " in v.split("choose integer")[0]
        for v in variants
    )
