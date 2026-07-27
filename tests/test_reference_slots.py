"""Pins the reference-slot registry — the one table saying what every `str`-typed
field of every `n.Node` holds — to the AST's actual fields.

Most name-carrying slots hold a `NameRef`, which `resolve._rewrite` classifies
once and every consumer then reads off `ref_kind`. A minority hold their name as
a plain string, and a pass built on `NameRef` is structurally blind to those.
The blindness is not a design boundary: it is whichever consumer forgot the slot
exists, which is how a family library could reach past its `requires` contract
through `turns … again <var>` while the wall next door reported the property
proven (issue #138).

Completeness ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------------------
property: every `str`-typed field of every AST node carries exactly one
          classification, and the classification set is exhaustive — no field
          can exist unclassified, and no classification can name a field that
          does not exist.
domain:   every (dataclass, field) pair in `cardlang.ast.nodes` whose annotation
          mentions `str` anywhere — bare `str`, `str | None`,
          `tuple[str, ...]`, or a union with `str` among its members
          (`Movement.amount`).
registry: the AST module itself, introspected. `tests/test_node_registry.py`
          owns the prior link in the chain — that `n.Node` is exactly the
          module's dataclasses — so this module derives its node axis from the
          union and inherits that pin rather than repeating it.
covered:  the full membership equation, both directions, plus pairwise
          disjointness of the seven kinds. The SHAPE column (which of the four
          annotation shapes a slot has) is derived here and checked against
          `resolve.slot_strings`, so the extraction is total by construction
          rather than by the reader believing the annotations were read.
sampled:  none.
residual: the SEMANTIC column is authored, not derived, and cannot be otherwise
          — `str` is `str`, and what a slot MEANS is not in its annotation. What
          is derived is the KEY set and the shape column. A slot classified into
          the wrong namespace is therefore reachable by this pin only when the
          namespace does not exist at all (`test_every_namespace_is_named`); a
          wrong-but-real namespace is caught by the consumer grids in
          `tests/test_family_libraries.py`, not here. Stated because "derived
          and pinned" would otherwise read as a claim the classification itself
          is derived.

The framing check (surface-totality-audit Step 1) ran against `nodes.py` and the
grammar as the definition sources, with the author's table as provisional input;
it did not run in a fresh context, so it is the weaker form of that check. Its
diff is what moved `NameRef.name`/`ref_kind` out of `reference` into kinds of
their own and what added `Movement.item` as a game-fed slot.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

import cardlang.ast.nodes as n
from cardlang.resolve import (
    STRING_SLOT_KINDS,
    _BINDER_SLOTS,
    _CLASSIFIED_SLOTS,
    _DECLARATION_SLOTS,
    _KEYWORD_SLOTS,
    _METADATA_SLOTS,
    _OPAQUE_SLOTS,
    _REFERENCE_SLOTS,
    slot_namespace,
    slot_strings,
)

Slot = tuple[type, str]

# The seven kinds, as (name, the membership the registry derives it from). The
# tuple IS the closed domain: `STRING_SLOT_KINDS` is built from exactly these
# tables, so a kind added there without an entry here fails `test_the_kind_axis_
# is_the_whole_registry` rather than silently escaping disjointness.
_KIND_TABLES: tuple[tuple[str, frozenset[Slot]], ...] = (
    ("declaration", frozenset(_DECLARATION_SLOTS)),
    ("binder", _BINDER_SLOTS),
    ("reference", frozenset(_REFERENCE_SLOTS)),
    ("keyword", _KEYWORD_SLOTS),
    ("opaque", _OPAQUE_SLOTS),
    ("classified", _CLASSIFIED_SLOTS),
    ("metadata", _METADATA_SLOTS),
)


def _mentions_str(annotation: object) -> bool:
    """Whether `str` appears anywhere in an annotation — the domain's defining
    predicate, applied to the four shapes the AST actually uses and to any
    nesting of them."""
    if annotation is str:
        return True
    return any(_mentions_str(arg) for arg in typing.get_args(annotation))


def _string_slots() -> dict[Slot, object]:
    """Every `str`-mentioning field of every node kind, mapped to its
    annotation. The node axis comes from the `Node` union, which
    tests/test_node_registry.py pins to the module's dataclasses."""
    slots: dict[Slot, object] = {}
    for cls in typing.get_args(n.Node):
        hints = typing.get_type_hints(cls)
        for field in dataclasses.fields(cls):
            annotation = hints[field.name]
            if _mentions_str(annotation):
                slots[(cls, field.name)] = annotation
    return slots


def _name(slot: Slot) -> str:
    return f"{slot[0].__name__}.{slot[1]}"


def test_the_registry_is_exactly_the_asts_string_fields() -> None:
    """The membership equation, both directions. A `str` field added to a node
    with no row here is the hole this registry exists to close; a row naming a
    field that no longer exists is a classification of nothing, which reads as
    coverage.

    red under: add a `str` field to any node in `nodes.py`, or delete a row from
    any of the seven tables."""
    derived = set(_string_slots())
    registered = set(STRING_SLOT_KINDS)
    missing = sorted(_name(s) for s in derived - registered)
    extra = sorted(_name(s) for s in registered - derived)
    assert not missing, (
        f"string-bearing AST fields with no classification: {missing} — a slot "
        f"nobody classified is a name channel no sweep can see (issue #138)"
    )
    assert not extra, (
        f"classified slots that do not exist on their node: {extra} — the row "
        f"classifies nothing, and reads as coverage"
    )


def test_the_kind_axis_is_the_whole_registry() -> None:
    """`STRING_SLOT_KINDS` is the union of the seven tables and nothing else, so
    a kind cannot be added to the registry without joining this module's axis
    (and therefore the disjointness check below).

    red under: add an eighth table to `STRING_SLOT_KINDS`'s construction without
    a `_KIND_TABLES` entry."""
    union: set[Slot] = set()
    for _, table in _KIND_TABLES:
        union |= table
    assert union == set(STRING_SLOT_KINDS)
    assert {kind for kind, _ in _KIND_TABLES} == set(STRING_SLOT_KINDS.values())


def test_no_slot_carries_two_kinds() -> None:
    """Each slot is classified once. Two kinds would make every consumer's
    verdict depend on which table it happened to consult — the ambiguity a
    single registry exists to remove.

    red under: add any existing slot to a second table."""
    for i, (kind_a, table_a) in enumerate(_KIND_TABLES):
        for kind_b, table_b in _KIND_TABLES[i + 1 :]:
            overlap = sorted(_name(s) for s in table_a & table_b)
            assert not overlap, f"{kind_a} and {kind_b} both claim {overlap}"


# Namespaces whose declarations live outside the AST: a stdlib registry, the
# domain table, or the deck. A reference into one of these is still a reference —
# it just cannot be answered by walking a game's nodes.
_EXTERNALLY_OWNED = frozenset(
    {
        "stdlib_move_type",
        "stdlib_query",
        "deck_rank",
        "deck_suit",
        "enum_value",
        "component_set",
        "board_family",
        "role",
        "index_domain",
        "zone_type",
        "zone_type_arg",
        "content_kind",
        "library",
    }
)


def test_every_namespace_is_named() -> None:
    """Both name-bearing kinds carry a non-empty namespace, and every namespace a
    REFERENCE slot draws from is one some DECLARATION slot fills or one the
    registry records as externally owned.

    The second half is the check with teeth: a reference into a namespace
    nothing declares is either a typo or a namespace whose owner lives outside
    the AST (the stdlib registries, the domain table, the component set). Those
    are listed, so the list is the statement — a new reference namespace must be
    classified as one or the other before it can land.

    red under: point a `_REFERENCE_SLOTS` row at a namespace spelled differently
    from its declaration, or drop one from `_EXTERNALLY_OWNED`."""
    assert all(ns for ns in _DECLARATION_SLOTS.values())
    assert all(ns for ns in _REFERENCE_SLOTS.values())
    declared = set(_DECLARATION_SLOTS.values())
    referenced = set(_REFERENCE_SLOTS.values())
    unowned = sorted(referenced - declared - _EXTERNALLY_OWNED)
    assert not unowned, (
        f"reference namespaces nothing declares and nothing owns: {unowned}"
    )




# --- the shape column, derived --------------------------------------------
#
# `slot_strings` is what every consumer uses to read a slot, so its totality is
# the extraction's completeness argument. The four shapes are derived from the
# annotations rather than listed, and each is exercised on a real node.


def _shape(annotation: object) -> str:
    """Which of the annotation shapes a slot has, read off the annotation."""
    if annotation is str:
        return "bare"
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) is tuple:
        return "tuple"
    if type(None) in args:
        return "optional"
    return "union"


def test_every_slot_shape_is_one_of_four() -> None:
    """The shape axis is closed. A fifth shape (a `dict[str, str]` field, a
    nested tuple) would mean `slot_strings` reads part of a slot and calls it
    the whole, which is the silent half-coverage this registry replaces.

    red under: annotate a node field as `list[str]` or `dict[str, str]`."""
    shapes = {_shape(a) for a in _string_slots().values()}
    assert shapes <= {"bare", "optional", "tuple", "union"}, shapes


def test_slot_strings_reads_every_shape_whole() -> None:
    """One real node per shape, so the reader is exercised rather than reasoned
    about. The `tuple` row is the one that matters: a consumer taking only the
    first element would see `Offer.move_types`' first move type and miss the
    rest, which is coverage that looks total and is not.

    red under: make `slot_strings` return `(value,)` for a tuple slot, or drop
    its `None` guard."""
    bare = n.Call("helper", ())
    assert slot_strings(bare, "func") == ("helper",)

    unset = n.Round(
        move_type=None,
        leader=n.NameRef("p"),
        participants=n.AllPlayers(),
        source_zone=None,
        play_zone=None,
        outcome_fn=None,
        trump=None,
    )
    assert slot_strings(unset, "source_zone") == ()
    set_optional = n.Turns(
        binder="p",
        leader=n.NameRef("l"),
        participants=n.AllPlayers(),
        termination=n.NameRef("t"),
        again="flag",
        body=(),
    )
    assert slot_strings(set_optional, "again") == ("flag",)

    many = n.Offer(player=n.NameRef("p"), move_types=("bid", "pass"))
    assert slot_strings(many, "move_types") == ("bid", "pass")

    union = n.Movement(
        verb="deal",
        mode=None,
        amount="all",
        item="cards",
        source=None,
        dest=None,
        dest_each=False,
    )
    assert slot_strings(union, "amount") == ("all",)


def test_slot_namespace_answers_only_for_references() -> None:
    """The accessor is the registry's public face, and it must distinguish "not
    a reference" from "a reference into a namespace I forgot" — the two the
    hand-list era could not tell apart.

    red under: make `slot_namespace` fall back to a default namespace."""
    assert slot_namespace(n.Call("f", ()), "func") == "function"
    assert slot_namespace(n.Call("f", ()), "args") is None
    assert slot_namespace(n.StrLit("x"), "value") is None
