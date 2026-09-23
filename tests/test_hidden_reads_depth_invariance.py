"""How many by-value bindings a value passes through never changes a Hidden
Read verdict.

A second derivation of the Hidden Read check's following of names, beside
tests/test_hidden_reads_let_invariance.py (one `let`): every hoist that
module derives is re-run through a chain of `let`s, each bound to the one
before, and every grid cell whose value reaches its decision as a phase
outcome's payload is re-run with the payload forwarded through further
outcome phases.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        binding-depth invariance: a value reaching a judged position
                 through a chain of `let`s of any length keeps the verdict it
                 has through one; a payload forwarded through k phase
                 outcomes keeps the verdict it has at k = 0, where the
                 language can write the forwarding at all.
domain:          the `let` chains: every variant of the one-`let` hoists, at
                 chain lengths that cross any bound a follower could carry
                 (`_DEPTHS`). The outcome chains: every grid cell whose
                 judged value is an outcome payload, forwarded through k = 1
                 to 4 phases, each consuming the previous outcome in a
                 `produces:` arm and producing its own, placed before the
                 consumer and, for the `after_each` consumer, after it. The
                 language refuses every such forwarding -- a `produce` may
                 not stand in a `produces:` arm, and a procedure may not
                 produce -- so a chain whose depth-0 cell is accepted must be
                 refused by that rule, and a chain whose depth-0 cell the
                 Hidden Read check refuses must be refused by that check,
                 naming the same zones, at every depth: the check runs before
                 the arm rule, so it is what a designer reads.
registry:        the cells and the hoists: tests/test_hidden_reads_let_invariance.py
                 (`_cell_sources`, `_variants`); the outcome cells:
                 tests/test_hidden_reads.py's `_INDIRECTIONS`.
does not prove:  invariance for a chain mixing binding kinds (a `let` of a
                 payload of a parameter): each kind's chain is run alone.
"""

from __future__ import annotations

import re

import pytest

import tests.test_hidden_reads as G
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from tests.test_hidden_reads_let_invariance import _NAME, _VARIANTS, _verdict

# Chain lengths: short, and past any small bound a follower might carry.
_DEPTHS = (2, 12, 40)


_FIXED_WALKS = "outcomes are collected in a fixed count of walks"
_FIXED_DEPTH = "a binding chain is followed to a fixed depth"
# variant -> why it moves the verdict.
_RED: dict[str, str] = {
    'after-each-consumes-a-later-outcome@forward2': _FIXED_WALKS,
    'after-each-consumes-a-later-outcome@forward3': _FIXED_WALKS,
    'after-each-consumes-a-later-outcome@forward4': _FIXED_WALKS,
    'as-literal-seat@0@depth40': _FIXED_DEPTH,
    'as-state-variable-written-after@leader@depth40': _FIXED_DEPTH,
    'as-state-variable-written-in-sibling-branch@leader@depth40': _FIXED_DEPTH,
    'as-state-variable@leader@depth40': _FIXED_DEPTH,
    'indexed-let-consumed-in-a-nested-seat@0@depth40': _FIXED_DEPTH,
    'let-consumed-in-a-nested-seat@0@depth40': _FIXED_DEPTH,
    'let-names-the-deciders-team@t@depth40': _FIXED_DEPTH,
    'let-names-the-literal-seat@s@depth40': _FIXED_DEPTH,
    'let-names-the-state-variable-seat@who@depth40': _FIXED_DEPTH,
    'outcome-payload-consumed-by-another-seat@forward2': _FIXED_WALKS,
    'outcome-payload-consumed-by-another-seat@forward3': _FIXED_WALKS,
    'outcome-payload-consumed-by-another-seat@forward4': _FIXED_WALKS,
    'procedure-argument-consumed-in-a-nested-seat@0@depth40': _FIXED_DEPTH,
    'procedure-argument@x@depth40': _FIXED_DEPTH,
    'team-of-decider@team_of(actor)@depth40': _FIXED_DEPTH,
}


def _mark(variant_id: str) -> list[pytest.MarkDecorator]:
    reason = _RED.get(variant_id)
    return (
        [pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)]
        if reason is not None
        else []
    )


def _chained(variant: str, depth: int) -> str:
    """`variant`'s one `let` followed by `depth - 1` more, each bound to the
    one before, and the use reading the last."""
    head, sep, tail = variant.partition(f"let {_NAME} = ")
    assert sep, "a hoist variant binds the hoisted name"
    init, _, rest = tail.partition("  ")
    chain = f"let {_NAME}0 = {init}  " + "".join(
        f"let {_NAME}{i} = {_NAME}{i - 1}  " for i in range(1, depth)
    )
    use = re.sub(rf"\b{_NAME}\b", f"{_NAME}{depth - 1}", rest)
    return head + chain + use


def _let_chain_cells() -> list[object]:
    out: list[object] = []
    for param in _VARIANTS:
        source, variant = param.values  # type: ignore[attr-defined]
        for depth in _DEPTHS:
            variant_id = f"{param.id}@depth{depth}"  # type: ignore[attr-defined]
            out.append(
                pytest.param(
                    source, _chained(variant, depth), id=variant_id, marks=_mark(variant_id)
                )
            )
    return out


@pytest.mark.parametrize("source,variant", _let_chain_cells())
def test_a_let_chain_keeps_the_verdict(source: str, variant: str) -> None:
    """A value bound through a chain of `let`s is judged as written in place."""
    assert _verdict(variant) == _verdict(source)


_OUTCOME = re.compile(
    r"phase (?P<phase>\w+) -> outcome \{ (?P<tag>\w+)\((?P<type>\w+)\) \}"
)


def _forwarded(source: str, depth: int) -> str:
    """The cell with its payload forwarded through `depth` more outcome
    phases, declared immediately before the phase whose `produces:` arm
    consumes it (or after it, for a consumer in an `after_each`)."""
    m = _OUTCOME.search(source)
    assert m is not None
    phase, tag, type_ = m.group("phase"), m.group("tag"), m.group("type")
    forwards = ""
    for i in range(1, depth + 1):
        prev_phase, prev_tag = (phase, tag) if i == 1 else (f"fwd{i - 1}", f"t{i - 1}")
        forwards += (
            f"phase fwd{i} -> outcome {{ t{i}({type_}) }} "
            f"{{ {prev_phase} produces: {prev_tag}(v) {{ produce t{i}(v) }} }} "
        )
    last_phase, last_tag = f"fwd{depth}", f"t{depth}"
    consumer = f"{phase} produces: {tag}("
    assert consumer in source
    forwarded = source.replace(consumer, f"{last_phase} produces: {last_tag}(")
    if "after_each" in forwarded.split(consumer.split(" ")[0])[0]:
        at = forwarded.index(m.group(0))
        return forwarded[:at] + forwards + forwarded[at:]
    at = forwarded.index(f"{last_phase} produces:")
    enclosing = forwarded.rindex("phase ", 0, at)
    return forwarded[:enclosing] + forwards + forwarded[enclosing:]


def _outcome_cells() -> list[object]:
    out: list[object] = []
    for cell_id, (body, defs, zone, teams, _) in G._INDIRECTIONS.items():
        if "-> outcome" not in body:
            continue
        source = G._game(body, defs, zone=zone, teams=teams)
        for depth in range(1, 5):
            variant_id = f"{cell_id}@forward{depth}"
            out.append(
                pytest.param(
                    source, _forwarded(source, depth), id=variant_id, marks=_mark(variant_id)
                )
            )
    return out


_ARM_RULE = "'produce' may not appear in a produces: arm"


@pytest.mark.parametrize("source,variant", _outcome_cells())
def test_a_forwarded_payload_keeps_the_verdict(source: str, variant: str) -> None:
    """A payload forwarded through k outcome phases: refused by the Hidden
    Read check naming the depth-0 zones where depth 0 is refused, and by the
    language's forwarding rule where depth 0 is accepted."""
    accepted, zones, _ = _verdict(source)
    if accepted:
        with pytest.raises(DiagnosticError) as exc:
            check_dsl(variant, "forward.cardlang")
        text = "\n".join([str(exc.value), *getattr(exc.value, "__notes__", [])])
        assert _ARM_RULE in text, text
        return
    forwarded, forwarded_zones, _ = _verdict(variant)
    assert (forwarded, forwarded_zones) == (False, zones)


def test_the_outcome_chains_reach_every_outcome_cell() -> None:
    """Every outcome cell is forwarded, the `after_each` consumer among them.

    red under: return no cell from `_outcome_cells`."""
    ids = " ".join(p.id for p in _outcome_cells())  # type: ignore[attr-defined]
    for cell_id, (body, _, _, _, _) in G._INDIRECTIONS.items():
        if "-> outcome" in body:
            assert f"{cell_id}@forward4" in ids
    assert "after-each" in ids
