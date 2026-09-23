"""Wrapping a statement in `as` the acting seat never changes a Hidden Read
verdict; wrapping it in `as` another seat changes it exactly as the
cross-seat rule says.

A second derivation of the Hidden Read check's seat tracking, independent of
the grid's expected columns: every statement of every grid cell that sits in
a statement sequence is re-run inside an `as` block, mechanically, from the
parsed cell and its spans.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        as-invariance: `as <E> { S }`, where E is proven to name the
                 acting seat at S -- the `actor` pronoun, the enclosing seat
                 loop's binder, the name an enclosing `as` binds, its literal
                 seat, its State Variable -- has S's verdict. And `as <a seat
                 not proven to be the acting one> { S }` is refused exactly
                 where S accepted a read of a value bound outside S by a
                 proof that the acting seat owns it: a value bound under
                 another acting seat carries none of that seat's proofs.
domain:          every cell of the Hidden Read grids that
                 tests/test_hidden_reads_let_invariance.py derives its cells
                 from, every statement of it that sits in a statement
                 sequence and is a movement, an assignment, an `if`, an `as`,
                 a seat loop or an offer (a `let` is not wrapped: an `as`
                 would scope its name). The same-seat wraps take every
                 expression the enclosing constructs prove; the other-seat
                 wrap takes the statements whose own reads are public, so the
                 cross-seat rule alone decides the prediction, and whose cell
                 checks clean, so its verdicts can be read.
registry:        the cells: tests/test_hidden_reads_let_invariance.py's
                 `_cell_sources`; the verdicts read:
                 `cardlang.resolve.hidden_read_verdicts`.
does not prove:  the other-seat direction for a statement whose own reads
                 are proven by the acting seat -- a read written inside S
                 re-binds to the new seat, and predicting it would restate
                 the check.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

import pytest

from cardlang import resolve as R
from cardlang.ast import nodes as n
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from tests.test_hidden_reads_let_invariance import _cell_sources, _verdict

_WRAPPED = (n.Transfer, n.AssignStmt, n.IfStmt, n.AsBlock, n.ForEach, n.Offer)


def _statements(node: object, seats: tuple[str, ...]) -> Iterator[tuple[n.Stmt, tuple[str, ...]]]:
    """Every statement that sits in a statement sequence, with the
    expressions proven to name the acting seat at it."""
    if not dataclasses.is_dataclass(node) or isinstance(node, type):
        return
    inner = seats
    match node:
        case n.MoveTypeDef():
            inner = ("actor",)
        case n.ForEach() if node.role == "player":
            inner = ("actor", node.binder)
        case n.Turns():
            inner = ("actor", node.binder)
        case n.AsBlock() if isinstance(node.player, (n.NameRef, n.IntLit)) and not _may_rename(
            node
        ):
            spelled = (
                node.player.name if isinstance(node.player, n.NameRef) else str(node.player.value)
            )
            inner = ("actor", spelled)
        case n.AsBlock():
            inner = ("actor",)
    for f in dataclasses.fields(node):
        value = getattr(node, f.name)
        items = value if isinstance(value, tuple) else (value,)
        in_sequence = isinstance(value, tuple)
        for item in items:
            if in_sequence and isinstance(item, _WRAPPED) and inner:
                yield item, inner
            yield from _statements(item, inner)


def _may_rename(block: n.AsBlock) -> bool:
    """Whether the name an `as` binds may name another seat later in its body:
    a write to it, or an offer or round whose move may write it. The `as`
    entry's seat stays the acting one, so `actor` is still proven there."""
    if not isinstance(block.player, n.NameRef):
        return False
    for node in _nodes(block.body):
        if isinstance(node, (n.Offer, n.AuctionRound, n.TrickRound, n.ClimbRound, n.RunStmt)):
            return True
        if isinstance(node, (n.AssignStmt, n.RotateStmt)) and node.target.name == block.player.name:
            return True
    return False


def _nodes(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, tuple):
        for item in node:
            yield from _nodes(item)
    elif dataclasses.is_dataclass(node) and not isinstance(node, type):
        for f in dataclasses.fields(node):
            yield from _nodes(getattr(node, f.name))


def _wrap(source: str, stmt: n.Stmt, seat: str) -> str:
    assert stmt.span is not None
    start, end = stmt.span.start, stmt.span.end
    return source[:start] + f"as {seat} {{ " + source[start:end] + " }" + source[end:]


def _inside(span: object, stmt: n.Stmt) -> bool:
    assert stmt.span is not None
    return (
        span is not None
        and stmt.span.start <= span.start  # type: ignore[attr-defined]
        and span.end <= stmt.span.end  # type: ignore[attr-defined]
    )


_RED_REASON = "an `as` naming the acting seat takes a fresh seat and drops the proofs"
_RED: frozenset[str] = frozenset({
    'as-binder@as actor@move chosen 1 card from hand[p] to pile',
    'as-literal-seat@as actor@move chosen 1 card from hand[0] to pile',
    'as-state-variable-written-after@as actor@move chosen 1 card from hand[leader] to',
    'as-state-variable-written-in-sibling-branch@as actor@if flag { leader := 1 } else { move chos',
    'as-state-variable-written-in-sibling-branch@as actor@move chosen 1 card from hand[leader] to',
    'as-state-variable@as actor@move chosen 1 card from hand[leader] to',
    'function-argument-read-at-the-call@as actor@move chosen (cnt(p)) cards from hand[p]',
    'indexed-let-consumed-in-a-nested-seat@as actor@move chosen (k[p]) cards from hand[0] to',
    'let-alias@as actor@move chosen 1 card from hand[me] to pile',
    'let-consumed-by-the-same-seat-moving-a-public-pile@as actor@move chosen (k) cards from pile to won[p',
    'let-consumed-by-the-same-seat-moving-a-public-pile@as p@move chosen (k) cards from pile to won[p',
    'let-consumed-by-the-same-seat@as actor@move chosen (k) cards from hand[p] to pi',
    'let-consumed-by-the-same-seat@as p@move chosen (k) cards from hand[p] to pi',
    'let-consumed-in-a-nested-seat@as actor@move chosen (k) cards from hand[0] to pi',
    'let-names-the-binder-seat@as actor@move chosen 1 card from hand[who] to pil',
    'let-names-the-binder-seat@as p@move chosen 1 card from hand[who] to pil',
    'let-names-the-deciders-team@as actor@move chosen 1 card from secret[t] to pil',
    'let-names-the-literal-seat@as 0@move chosen 1 card from hand[s] to pile',
    'let-names-the-literal-seat@as actor@move chosen 1 card from hand[s] to pile',
    'let-names-the-state-variable-seat@as actor@move chosen 1 card from hand[who] to pil',
    'let-names-the-state-variable-seat@as leader@move chosen 1 card from hand[who] to pil',
    'procedure-argument-consumed-in-a-nested-seat@as actor@move chosen (k) cards from hand[0] to pi',
    'turns-binder@as actor@move chosen 1 card from hand[t] to pile',
    'when-let-own@as actor@move chosen 1 card from hand where held',
})


def _variants() -> tuple[list[object], list[object]]:
    same: list[object] = []
    other: list[object] = []
    for cell_id, source in _cell_sources():
        game = parse_text(source, "cell.cardlang")
        statements = list(_statements(game, ()))
        for stmt, seats in statements:
            text = source[stmt.span.start:stmt.span.end]  # type: ignore[union-attr]
            for seat in dict.fromkeys(seats):
                variant_id = f"{cell_id}@as {seat}@{text[:40].rstrip()}"
                marks = (
                    [pytest.mark.xfail(strict=True, raises=AssertionError, reason=_RED_REASON)]
                    if variant_id in _RED
                    else []
                )
                same.append(
                    pytest.param(source, _wrap(source, stmt, seat), id=variant_id, marks=marks)
                )
        accepted, _, _ = _verdict(source)
        if not accepted:
            continue
        verdicts = R.hidden_read_verdicts(check_dsl(source, "cell.cardlang"))
        for stmt, seats in statements:
            here = [v for v in verdicts if _inside(v.site, stmt)]
            own_reads = [v for v in here if _inside(v.read.span, stmt)]
            if any(v.reason != "public" for v in own_reads):
                continue
            outside_proofs = [
                v for v in here if not _inside(v.read.span, stmt) and v.reason != "public"
            ]
            another = "2" if "2" not in seats else "1"
            text = source[stmt.span.start:stmt.span.end]  # type: ignore[union-attr]
            other.append(
                pytest.param(
                    _wrap(source, stmt, another),
                    not outside_proofs,
                    id=f"{cell_id}@as {another}@{text[:40]}",
                )
            )
    return same, other


_SAME, _OTHER = _variants()


@pytest.mark.parametrize("source,variant", _SAME)
def test_as_the_acting_seat_keeps_the_verdict(source: str, variant: str) -> None:
    """`as` an expression proven to name the acting seat changes nothing."""
    assert _verdict(variant) == _verdict(source)


@pytest.mark.parametrize("variant,accepted", _OTHER)
def test_as_another_seat_strips_the_proofs_of_values_bound_outside(
    variant: str, accepted: bool
) -> None:
    """`as` another seat accepts exactly where no value bound outside the
    statement was accepted by the acting seat's ownership."""
    assert _verdict(variant)[0] is accepted


def test_both_directions_are_exercised() -> None:
    """The wraps reach every proven spelling, and the other-seat direction
    predicts both outcomes.

    red under: yield only the `actor` wrap from `_statements`."""
    spellings = " ".join(p.values[1] for p in _SAME)  # type: ignore[attr-defined]
    for spelling in ("as actor {", "as p {", "as 0 {", "as leader {"):
        assert spelling in spellings, spelling
    assert {p.values[1] for p in _OTHER} == {True, False}  # type: ignore[attr-defined]
