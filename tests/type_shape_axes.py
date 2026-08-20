"""Axis derivation for the nominal-comparison grid (`test_permissive_top.py`).

Every axis here reads a DEFINITION SITE — the checker's `Type` union and the
signatures of the relations over it — and returns the member list. Nothing
hand-lists a domain: a new union member, a new position at which a `Type`
nests inside another, or a third compatibility relation shows up as grid rows
nobody wrote, which is the point (decisions.md, "Closed-domain completeness").

Separate from the grid module so the derivation can be replayed against the
merge base: the review reads the HEAD-derived cell list and runs it on the
base tree, where the cells that fail (plus the cells that cannot exist there)
are the change's behavioral delta. A base tree re-deriving its own cell list
would lose exactly the rows the change adds.

The shape axis in particular has to be derived rather than read: `types.py`
carries `from __future__ import annotations`, so a field's raw
`__annotations__` entry is the STRING an author wrote — `"Type"`,
`"Type | None"`, `"Mapping[str, Type]"`, `"Mapping[str, tuple[Type, ...]]"`.
A matcher keyed on `"Type"` finds one position of the four and drops three,
which is this repo's named recurring defect (a matcher written against the
examples while the prose states the class). `typing.get_type_hints` resolves
the strings to objects, and `_nests_a_type` walks `get_args` to the leaves, so
a position is found by what its annotation MEANS rather than by how it is
spelled.

Contract
--------
Assumes: `cardlang.types` imports, and every annotation in it resolves
(`get_type_hints` raises otherwise, which is the loud form of a union member
whose field type nobody can name).
Establishes: every public axis is a NON-EMPTY tuple, or raises
`AxisDerivationError`; every `Type` union member is classified as either a
leaf or the declarer of at least one nested-`Type` position, and the two sets
partition the union.
Illegal after this module: parametrizing a grid over an axis that came back
empty, and hand-listing any of these three axes at a consumer. An empty axis
yields zero cells and a passing grid — the vacuously-green class
(decisions.md, "Closed-domain completeness"), which is why the emptiness
check lives here at the producer rather than in each consumer.
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import typing
from dataclasses import dataclass

from cardlang import types as type_model
from cardlang.types import Type


class AxisDerivationError(AssertionError):
    """An axis came back empty, or its defining site changed shape.

    `AssertionError` so a grid cell awaiting an unlanded rule reddens under
    the same exception a wrong expected outcome does, keeping
    `xfail(raises=...)` marks constrained to one failure shape.
    """


def _nonempty(values: tuple[object, ...], what: str) -> None:
    if not values:
        raise AxisDerivationError(
            f"the {what} axis derived to nothing — the definition site in "
            f"cardlang/types.py changed shape, and a grid crossed over an "
            f"empty axis runs zero cells and passes"
        )


# --- the union itself --------------------------------------------------------

UNION_MEMBERS: tuple[type, ...] = typing.get_args(Type)
_nonempty(UNION_MEMBERS, "Type union")


def _nests_a_type(annotation: object) -> bool:
    """Whether `annotation` reaches a `Type` union member anywhere inside it.

    Recursive over `get_args`, so `Type`, `Type | None`, `Mapping[str, Type]`
    and `Mapping[str, tuple[Type, ...]]` all answer true while `str`,
    `bool` and `frozenset[str]` answer false. `Ellipsis` (from
    `tuple[Type, ...]`) and `None` reach the membership test and answer
    false there rather than needing an arm.
    """
    if annotation in UNION_MEMBERS:
        return True
    return any(_nests_a_type(arg) for arg in typing.get_args(annotation))


@dataclass(frozen=True)
class ShapePosition:
    """One position at which a `Type` nests inside another `Type`.

    `label` is the grid's cell id — `"TCollection.key"` — and `bare` is the
    synthetic identity position (no enclosing constructor), which the grid
    needs because "no wrapper at all" is a cell of the shape axis and no
    dataclass field declares it.
    """

    label: str
    ctor: type | None  # None for the identity position
    field: str | None


BARE = ShapePosition(label="bare", ctor=None, field=None)


def _derive_positions() -> tuple[ShapePosition, ...]:
    found: list[ShapePosition] = []
    for member in UNION_MEMBERS:
        hints = typing.get_type_hints(member)
        for field in dataclasses.fields(member):
            if _nests_a_type(hints[field.name]):
                found.append(
                    ShapePosition(
                        label=f"{member.__name__}.{field.name}",
                        ctor=member,
                        field=field.name,
                    )
                )
    return tuple(found)


NESTED_POSITIONS: tuple[ShapePosition, ...] = _derive_positions()
_nonempty(NESTED_POSITIONS, "nested-Type position")

#: The shape axis: the identity position plus every position at which a
#: `Type` nests inside another. This is what the nominal rule must reach
#: through, or fail to reach through for a stated reason.
SHAPE_POSITIONS: tuple[ShapePosition, ...] = (BARE, *NESTED_POSITIONS)

#: The union members that nest no `Type` at all. Not a grid axis — recorded
#: so the partition below is visible rather than implied, and so a reviewer
#: can see which members the shape axis is silent about BECAUSE they have
#: nothing inside them.
LEAF_MEMBERS: tuple[type, ...] = tuple(
    m for m in UNION_MEMBERS if not any(p.ctor is m for p in NESTED_POSITIONS)
)

if len(LEAF_MEMBERS) + len({p.ctor for p in NESTED_POSITIONS}) != len(UNION_MEMBERS):
    raise AxisDerivationError(
        "the Type union's members do not partition into leaves and declarers "
        "of a nested position — the walk failed to classify one"
    )


# --- the nominal members -----------------------------------------------------


def _name_field_is_a_string(member: type) -> bool:
    return typing.get_type_hints(member).get("name") is str


def _derive_nominal_members() -> tuple[type, ...]:
    """Union members whose identity is a declared name AND which carry a
    structural payload beside it.

    These are the members for which "nominal" is a RULE rather than a
    consequence of dataclass equality: the payload can disagree while the
    name agrees, so equality answers "different type" for two snapshots of
    one declared type. A member carrying a name and nothing else
    (`NAME_ONLY_MEMBERS`) already compares by name and needs no arm — the
    grid pins that rather than assuming it.
    """
    return tuple(
        m
        for m in UNION_MEMBERS
        if _name_field_is_a_string(m) and len(dataclasses.fields(m)) > 1
    )


NOMINAL_MEMBERS: tuple[type, ...] = _derive_nominal_members()
_nonempty(NOMINAL_MEMBERS, "nominal member")

#: Union members whose ONLY field is the declared name. The classified
#: exclusion from `NOMINAL_MEMBERS`: dataclass equality over a single `name`
#: field IS nominal comparison, so these need no arm in either relation.
NAME_ONLY_MEMBERS: tuple[type, ...] = tuple(
    m
    for m in UNION_MEMBERS
    if _name_field_is_a_string(m) and len(dataclasses.fields(m)) == 1
)
_nonempty(NAME_ONLY_MEMBERS, "name-only member")


# --- the relations -----------------------------------------------------------


#: What "two-sided" means, and the arity `_derive_relations` demands.
RELATION_ARITY = 2


def _derive_relations() -> tuple[str, ...]:
    """The two-sided compatibility relations over `Type`, by SIGNATURE.

    Derived rather than listed so a third relation joins the grid on the day
    it is written. The predicate is "a public module-level function of
    `cardlang.types` taking exactly `RELATION_ARITY` `Type` operands" — which
    admits `join` and `coercible` and excludes `subscriptable` (one operand),
    without either function being named here.
    """
    found: list[str] = []
    for name, fn in vars(type_model).items():
        if name.startswith("_") or not inspect.isfunction(fn):
            continue
        if fn.__module__ != type_model.__name__:
            continue
        params = list(inspect.signature(fn).parameters)
        hints = typing.get_type_hints(fn)
        if len(params) == RELATION_ARITY and all(hints.get(p) == Type for p in params):
            found.append(name)
    return tuple(sorted(found))


RELATIONS: tuple[str, ...] = _derive_relations()
_nonempty(RELATIONS, "compatibility relation")

#: The operand-order axis: the orderings of a relation's operand slots.
#: Derived from the SAME arity the relation axis is derived from rather than
#: written as ("forward", "reversed") — a function is on the relation axis
#: exactly because it has two sides, and this is what having two sides means.
#: The axis is load-bearing because one relation is asymmetric by design
#: (`coercible` admits `Integer` where `Player` is expected and not the
#: reverse), so a rule that must hold BOTH ways has to be asked both ways.
ORDERINGS: tuple[tuple[int, ...], ...] = tuple(
    itertools.permutations(range(RELATION_ARITY))
)
_nonempty(ORDERINGS, "operand order")
