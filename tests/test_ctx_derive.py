"""Every derivation of a [[context]] carries every field it does not set.

`Ctx.derive` copies the field list `_CTX_FIELDS`, taken from
`dataclasses.fields(Ctx)` at import, so a field added to `Ctx` is carried by
construction. A derivation that dropped one would hand the next body a
context missing its observer, its tracer or its acting player — no refusal,
just a different game.

Completeness: the domain is the set of `Ctx` methods annotated to return a
`Ctx`, derived by introspection, plus the two derivations outside the class
(`_hermetic_ctx`'s two modes). `test_every_derivation_is_in_the_table` pins
the table to the introspected set, so a new derivation method fails until it
joins. Each row states which fields the derivation sets; every other field
must come back as the same object. A green does not prove the values a
derivation sets are right — those are its callers' tests.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest

from cardlang.ast import nodes as n
from cardlang.runtime import state as state_mod
from cardlang.runtime.evaluate import _hermetic_ctx
from cardlang.runtime.state import Ctx, Move, RuntimeState
from cardlang.runtime.values import Card, Seating


def _full_ctx() -> Ctx:
    """A context with every field set to a distinct, non-default object."""
    rs = cast(RuntimeState, SimpleNamespace(seating=Seating(4)))

    def chooser(p: int, c: list[Any], k: int) -> list[Any]:
        return c[:k]

    def tracer(event: str, data: Any) -> None:
        return None

    def observer(p: int, event: tuple[Any, ...]) -> None:
        return None

    return Ctx(
        rs=rs,
        chooser=chooser,
        tracer=tracer,
        locals={"x": 1},
        current_player=1,
        current_phase=cast(n.Phase, object()),
        winner=2,
        action=Move(Card("A", "spades"), 3),
        active_rules=(cast(n.RuleDef, object()),),
        observer=observer,
        round_source=("hand", cast(state_mod.Zone, object())),
    )


# Derivation -> (how to take it from a context, the fields it sets).
DERIVATIONS: dict[str, tuple[Callable[[Ctx], Ctx], frozenset[str]]] = {
    "derive": (lambda c: c.derive(winner=0), frozenset({"winner"})),
    "with_local": (lambda c: c.with_local("y", 2), frozenset({"locals"})),
    "acting_as": (lambda c: c.acting_as(0), frozenset({"current_player"})),
    "in_phase": (
        lambda c: c.in_phase(cast(n.Phase, object())),
        frozenset({"current_phase"}),
    ),
    "with_winner": (lambda c: c.with_winner(0), frozenset({"winner"})),
    "with_action": (
        lambda c: c.with_action(Move(Card("K", "hearts"), 0)),
        frozenset({"action"}),
    ),
    "with_rules": (lambda c: c.with_rules(()), frozenset({"active_rules"})),
    "_hermetic_ctx(keep_actor=True)": (
        lambda c: _hermetic_ctx(c, {"p": 0}, keep_actor=True),
        frozenset({"locals", "winner", "action", "round_source"}),
    ),
    "_hermetic_ctx(keep_actor=False)": (
        lambda c: _hermetic_ctx(c, {"card": 0}, keep_actor=False),
        frozenset({"locals", "winner", "action", "round_source", "current_player"}),
    ),
}

_OUTSIDE_THE_CLASS = frozenset(
    {"_hermetic_ctx(keep_actor=True)", "_hermetic_ctx(keep_actor=False)"}
)


def _ctx_returning_methods() -> set[str]:
    return {
        name
        for name, fn in inspect.getmembers(Ctx, inspect.isfunction)
        if inspect.signature(fn).return_annotation in ("Ctx", Ctx)
    }


def test_every_derivation_is_in_the_table() -> None:
    assert _ctx_returning_methods() == set(DERIVATIONS) - _OUTSIDE_THE_CLASS


def test_the_field_list_is_the_dataclass_fields() -> None:
    assert state_mod._CTX_FIELDS == tuple(f.name for f in dataclasses.fields(Ctx))


@pytest.mark.parametrize("name", sorted(DERIVATIONS))
def test_a_derivation_carries_every_field_it_does_not_set(name: str) -> None:
    """Reddens if `Ctx.derive` copies a hand list that misses a field, or a
    derivation clears a field its row does not name."""
    take, sets = DERIVATIONS[name]
    source = _full_ctx()
    derived = take(source)
    assert derived is not source
    for f in dataclasses.fields(Ctx):
        if f.name in sets:
            continue
        assert getattr(derived, f.name) is getattr(source, f.name), (
            f"{name} did not carry {f.name}"
        )
    for field_name in sets:
        assert getattr(derived, field_name) is not getattr(source, field_name), (
            f"{name}'s row says it sets {field_name}, and it came back unchanged"
        )


def test_derive_refuses_a_name_that_is_not_a_field() -> None:
    with pytest.raises(AttributeError):
        _full_ctx().derive(not_a_field=1)
