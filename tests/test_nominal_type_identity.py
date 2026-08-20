"""A declared type's identity is its NAME, at every position it can occupy.

`TStruct` and `TOutcome` carry a structural payload beside their declared name
(a field map, a case map), and both are frozen dataclasses, so equality is
structural: two SNAPSHOTS of one declared type taken at different points in
the registry fixpoint compare unequal. Left to equality that produced
`expects R, got R` — a diagnostic naming one type on both sides — and, worse,
a `join` returning `None` from an `IfExpr`, which falls to the permissive top
and exempts the whole subtree from every type Owner Guard
(tests/test_permissive_top.py). The nominal rule answers that: identity
belongs to the name, and the payload is what the name resolves TO.

A rule applied at the outer layer only is a top-level special case, so the
grid crosses the rule against every position at which a `Type` nests inside
another — derived from the union, not listed — against both relations, both
operand orders, and both nominal members.

Completeness ledger (decisions.md "Surface totality" / "Closed-domain
completeness")
----------------------------------------------------------------------
property:   two values of one declared type are compatible, and two values of
            differently-named declared types are not, under every
            compatibility relation over `Type`, in either operand order, at
            every position at which a `Type` nests inside another — never by
            structural comparison of the payload, which is a snapshot and can
            be stale.
domain:     (position at which a `Type` nests inside another, plus the
            identity position) x (compatibility relation over `Type`) x
            (operand order) x (union member whose identity is a declared
            name), with each position carrying a behaviour class that says
            whether the nested identity is OBSERVABLE through the relation;
            plus the cross-member cell (a struct and an outcome type sharing
            one name), and the classified exclusion (a union member carrying a
            name and no payload).
registry:   tests/type_shape_axes.py derives all four axes in code —
            `SHAPE_POSITIONS` from `dataclasses.fields` over
            `typing.get_args(Type)` resolved through `typing.get_type_hints`
            (the module carries `from __future__ import annotations`, so a
            matcher keyed on the annotation STRING finds one position of four);
            `RELATIONS` from the signatures of `cardlang.types`' public
            module-level functions taking two `Type` operands; `ORDERINGS`
            from that same arity; `NOMINAL_MEMBERS` from the union members
            carrying a `name: str` beside a structural payload.
covered:    `test_a_declared_types_identity_is_its_name_at_every_position`
            (position x relation x order x member), plus
            `test_a_struct_and_an_outcome_type_may_share_a_name_and_stay_
            distinct` (member x member x relation x order) and
            `test_a_name_only_member_is_already_nominal_under_equality`
            (the classified exclusion). The behaviour-class column is half
            derived (`_OPAQUE` is `position.ctor in NOMINAL_MEMBERS`) and half
            authored (`_AUTHORED_CLASSES`), and the authored half is pinned to
            cover exactly the derived positions it does not derive — so a new
            nested position fails collection rather than being guessed into a
            row. The keying domain's own rule, which is NOT this one, is
            covered by `test_the_keying_domain_admits_no_nominal_type` and
            `test_the_keying_domain_is_governed_by_the_sticky_key_rule`.
sampled:    one nested payload per nominal member (`TAny` vs `TInteger` for
            the stale/settled pair, one field or case tag). At the transparent
            and opaque positions the rule under test reads only the NAME, so
            the payload's shape is not a dimension of it — a second field or a
            second case tag would exercise the same branch. The stale/settled
            pair is the shape the registry fixpoint actually produces
            (`_provisional_structs` seeds every derived field at the permissive
            top and refines it).
            The keying position is the exception, and that argument does NOT
            cover it: `join` compares keys with raw `==`, so the payload is
            exactly what its cells turn on. What makes one payload enough there
            is the closed inhabitant set — no nominal type can reach the slot
            at all (`test_the_keying_domain_admits_no_nominal_type`) — and the
            rule that does govern it is run over agreeing, disagreeing and
            absent keys rather than sampled.
residual:   (1) A `TOutcome` cannot reach either relation from a well-formed
            program: no `infer` arm returns one — it is a registry entry
            consulted when checking `produce` / `produces:`
            (cardlang/types.py's module docstring) — and no declared field,
            parameter or payload type can name one (`type_from_name` resolves
            against the STRUCT registry). The grid therefore exercises the
            outcome rows by calling the relations directly. R4 — reaching
            them from source needs a new `infer` arm, i.e. editing the
            machinery. Recorded here; the guarantee is the type checker's, so
            it is rigor-critical, and the closure is the rule itself rather
            than a wall: the arms below answer for an outcome type whether or
            not one ever arrives.
            (2) NOT the nominal rule, and deliberately outside this grid: the
            relations' behaviour over the union's non-nominal members
            (`TAny` absorption at depth, optional widening, `Integer` standing
            for `Player`), the relations' algebraic laws (reflexivity —
            `coercible(TNull(), TNull())` is False, since the `TNull` arm
            precedes the equality arm — symmetry, transitivity, and the
            order-independence of the left fold in `_ifexpr_type`), and the
            nesting DEPTH the relations can manufacture but no construction
            site builds (`join(TNull(), X)` yields `TOptional(X)`). Each is a
            property of a different rule over the same union; guarded today
            only by the per-arm behaviour tests in tests/test_types.py and
            tests/test_permissive_top.py. R4 — an auditor calling the
            relations directly meets them; no DSL sentence infers a `TNull`
            or an outcome into either side. Recorded as issue #113's
            follow-on scope in this row rather than filed, since no cell of it
            is known wrong.
            (3) `TypeEnv.zone_families`' index type is the OTHER index-like
            slot the relations consume (`TPlayer`/`TTeam`/`TInteger`/`TCell`,
            checked through `coercible` at the subscript). It is not a
            `TCollection.key`, so it is not a position of this grid's axis;
            its own coverage is tests/test_positions.py and
            tests/test_zone_index_roles.py. R4 — recorded so the two
            index-like slots are not read as one.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable

import pytest

from cardlang.domains import DOMAINS, ZONE_INDEX_ROLES
from cardlang.types import (
    TAny,
    TCard,
    TCollection,
    TInteger,
    TOptional,
    TOutcome,
    TPlayer,
    TStruct,
    Type,
    coercible,
    join,
)
from tests.type_shape_axes import (
    NAME_ONLY_MEMBERS,
    NOMINAL_MEMBERS,
    ORDERINGS,
    RELATIONS,
    SHAPE_POSITIONS,
    ShapePosition,
)

# --- the behaviour classes ---------------------------------------------------

#: The relation descends into the position, so the nested type's identity
#: decides the verdict.
TRANSPARENT = "transparent"
#: The enclosing constructor is itself nominal, so its own name decides and
#: the nested identity is erased before either relation looks at it.
OPAQUE = "opaque"
#: Neither relation consults the slot: it is how a collection is ADDRESSED,
#: not part of its value space (`cardlang/types.py`, `TCollection.key`). Its
#: own rule is the sticky-key merge, covered separately below.
IGNORED = "ignored"

#: The behaviour class of every shape position whose declaring constructor is
#: not itself nominal. `OPAQUE` is DERIVED (`position.ctor in
#: NOMINAL_MEMBERS`); these are the positions where the answer is a design
#: decision rather than a consequence, so they are authored — and pinned below
#: to cover exactly the positions the derivation leaves. A new nested position
#: therefore fails collection instead of being guessed into a passing row.
_AUTHORED_CLASSES: dict[str, str] = {
    "bare": TRANSPARENT,
    "TOptional.inner": TRANSPARENT,
    "TCollection.element": TRANSPARENT,
    "TCollection.key": IGNORED,
}

#: How to build a value with the probe type at each shape position. The
#: enclosing names ("W", "d") are fixed across a cell's two operands, so the
#: only thing that varies between them is the NESTED type — which is what the
#: cell is asking about.
_WRAPPERS: dict[str, Callable[[Type], Type]] = {
    "bare": lambda t: t,
    "TOptional.inner": lambda t: TOptional(t),
    "TCollection.element": lambda t: TCollection(t),
    "TCollection.key": lambda t: TCollection(TCard(), key=t),
    "TStruct.fields": lambda t: TStruct(
        name="W", fields={"g": t}, derived=frozenset()
    ),
    "TOutcome.cases": lambda t: TOutcome(name="W", cases={"d": (t,)}),
}

#: How to build a value of each nominal member under a given declared name,
#: carrying a given payload. `payload` is what makes the two operands of a
#: same-name cell structurally unequal — the stale/settled pair the registry
#: fixpoint produces.
_NOMINALS: dict[type, Callable[[str, Type], Type]] = {
    TStruct: lambda name, payload: TStruct(
        name=name, fields={"f": payload}, derived=frozenset()
    ),
    TOutcome: lambda name, payload: TOutcome(name=name, cases={"c": (payload,)}),
}

#: Each relation as a two-sided COMPATIBILITY predicate. `join` answers with a
#: type or `None`; `coercible` answers with a bool. The grid asks the one
#: question both can answer.
_COMPATIBLE: dict[str, Callable[[Type, Type], bool]] = {
    "join": lambda a, b: join(a, b) is not None,
    "coercible": coercible,
}


def _label(key: object) -> str:
    """A comparable id for an axis member — a union member is keyed by class in
    one table and by name in another, and `str(SomeClass)` is `<class '...'>`,
    which would make every comparison below fail for the wrong reason."""
    return key.__name__ if isinstance(key, type) else str(key)


def _covers(table: Iterable[object], axis: Iterable[object], what: str) -> None:
    """Every authored table covers exactly its derived axis, checked at import.

    This is what keeps the grid honest as the union grows: a new shape
    position, nominal member or relation arrives with no decided outcome, and
    the module fails to collect rather than running a smaller grid that
    passes.
    """
    have, want = {_label(k) for k in table}, {_label(k) for k in axis}
    assert have == want, (
        f"the authored {what} table no longer covers its derived axis: "
        f"missing {sorted(want - have)}, stale {sorted(have - want)}. Decide "
        f"the new member's outcome here rather than letting the grid run "
        f"without it (decisions.md, 'Closed-domain completeness')."
    )


_covers(_WRAPPERS, {p.label for p in SHAPE_POSITIONS}, "shape-position wrapper")
_covers(_NOMINALS, NOMINAL_MEMBERS, "nominal-member builder")
_covers(_COMPATIBLE, RELATIONS, "relation")
_covers(
    _AUTHORED_CLASSES,
    {p.label for p in SHAPE_POSITIONS if p.ctor not in NOMINAL_MEMBERS},
    "behaviour class",
)


def _behaviour(position: ShapePosition) -> str:
    """The class of a shape position: derived where it follows from the union,
    authored where it is a decision."""
    if position.ctor in NOMINAL_MEMBERS:
        return OPAQUE
    return _AUTHORED_CLASSES[position.label]


def _expected(behaviour: str, same_name: bool) -> bool:
    """The cell's decided outcome.

    Transparent: the nested identity decides, which IS the nominal rule.
    Opaque and ignored: the nested identity is not observable through the
    relation, so both probes are compatible — for opposite reasons, which is
    why the two classes stay distinct even though this column agrees.
    """
    return same_name if behaviour == TRANSPARENT else True


def _ordered(pair: tuple[Type, Type], order: tuple[int, ...]) -> tuple[Type, Type]:
    return (pair[order[0]], pair[order[1]])


# --- the grid ----------------------------------------------------------------


@pytest.mark.parametrize("member", NOMINAL_MEMBERS, ids=lambda m: m.__name__)
@pytest.mark.parametrize("order", ORDERINGS, ids=lambda o: f"operands{o[0]}{o[1]}")
@pytest.mark.parametrize("relation", RELATIONS)
@pytest.mark.parametrize("position", SHAPE_POSITIONS, ids=lambda p: p.label)
def test_a_declared_types_identity_is_its_name_at_every_position(
    position: ShapePosition, relation: str, order: tuple[int, ...], member: type
) -> None:
    """position x relation x operand order x nominal member.

    Two snapshots of one declared type must stay compatible, and two
    differently-named declared types must not — wherever the type sits, and
    whichever way round the relation is asked. `coercible` is asymmetric by
    design (`Integer` stands for `Player`, not the reverse), so a rule that
    must hold both ways is asked both ways rather than assumed symmetric.

    red under: in `cardlang.types`, delete the `TOutcome` half of the nominal
    arm in `join` (or in `coercible`) — the outcome-type rows of the
    transparent and opaque positions go red together, which is the point: one
    missing arm is not one missing cell.
    """
    build = _NOMINALS[member]
    wrap = _WRAPPERS[position.label]
    stale, settled = build("R", TAny()), build("R", TInteger())
    unrelated = build("S", TInteger())
    behaviour = _behaviour(position)
    compatible = _COMPATIBLE[relation]

    same = compatible(*_ordered((wrap(stale), wrap(settled)), order))
    assert same is _expected(behaviour, same_name=True), (
        f"{relation} at {position.label} ({behaviour}) answered {same} for two "
        f"snapshots of one {member.__name__} named R"
    )
    different = compatible(*_ordered((wrap(stale), wrap(unrelated)), order))
    assert different is _expected(behaviour, same_name=False), (
        f"{relation} at {position.label} ({behaviour}) answered {different} for "
        f"a {member.__name__} named R against one named S"
    )


@pytest.mark.parametrize("order", ORDERINGS, ids=lambda o: f"operands{o[0]}{o[1]}")
@pytest.mark.parametrize("relation", RELATIONS)
@pytest.mark.parametrize("outer", NOMINAL_MEMBERS, ids=lambda m: m.__name__)
@pytest.mark.parametrize("inner", NOMINAL_MEMBERS, ids=lambda m: m.__name__)
def test_a_struct_and_an_outcome_type_may_share_a_name_and_stay_distinct(
    inner: type, outer: type, relation: str, order: tuple[int, ...]
) -> None:
    """The nominal rule is same NAME AND same constructor, never the name alone.

    `type R` and `define R` occupy different namespaces, so one spelling can
    name both. A nominal arm that compared only `.name` would make them one
    type — the accepted-but-ignored shape, since a `produce` of the outcome
    type would then satisfy a position expecting the struct.

    The diagonal (`inner is outer`) is the same-type case and is compatible;
    the off-diagonal must not be. Both are rows, so the arm cannot be narrowed
    to the diagonal without a red cell.

    red under: in `cardlang.types`, drop `type(a) is type(b)` from `join`'s
    nominal arm (or `type(src) is type(dst)` from `coercible`'s).
    """
    left, right = _NOMINALS[inner]("R", TInteger()), _NOMINALS[outer]("R", TInteger())
    answer = _COMPATIBLE[relation](*_ordered((left, right), order))
    assert answer is (inner is outer), (
        f"{relation} answered {answer} for {inner.__name__}('R') against "
        f"{outer.__name__}('R')"
    )


@pytest.mark.parametrize("order", ORDERINGS, ids=lambda o: f"operands{o[0]}{o[1]}")
@pytest.mark.parametrize("relation", RELATIONS)
@pytest.mark.parametrize("member", NAME_ONLY_MEMBERS, ids=lambda m: m.__name__)
def test_a_name_only_member_is_already_nominal_under_equality(
    member: type, relation: str, order: tuple[int, ...]
) -> None:
    """The classified exclusion from `NOMINAL_MEMBERS`, pinned rather than assumed.

    A union member whose ONLY field is its declared name has nothing that can
    disagree while the name agrees, so frozen-dataclass equality already IS
    nominal comparison and neither relation needs an arm for it. That is why
    the nominal axis derives on "a name field BESIDE a payload" rather than on
    "a name field": the members it excludes are excluded for a reason this
    test states and runs.

    red under: give `TEnum` a second field in `cardlang/types.py` — the
    derivation moves it into `NOMINAL_MEMBERS`, `NAME_ONLY_MEMBERS` empties,
    and tests/type_shape_axes.py's `_nonempty` refuses at import (run: the
    module errors on "the name-only member axis derived to nothing"). The
    axis producer answers before the parametrization does, which is where an
    empty axis should be caught.
    """
    same_a, same_b = member(name="Suit"), member(name="Suit")
    other = member(name="Rank")
    assert same_a == same_b and same_a != other, (
        f"{member.__name__} equality is not its name — it no longer belongs to "
        f"the excluded class"
    )
    compatible = _COMPATIBLE[relation]
    assert compatible(*_ordered((same_a, same_b), order)) is True
    assert compatible(*_ordered((same_a, other), order)) is False


# --- the keying domain: a different rule, classified rather than assumed -----


def test_the_keying_domain_admits_no_nominal_type() -> None:
    """Why `TCollection.key` is `IGNORED` rather than an uncovered cell of the
    nominal rule.

    A nominal type cannot inhabit the slot at all. `key` is set at exactly
    three sites: a state variable's index (`role_type` of the declared index
    role), an indexed `let` (`TPlayer` outright), and `join`'s own
    key-disagreement branch (the permissive top). Resolve narrows the first to
    `ZONE_INDEX_ROLES`, so the reachable set is the zone-index rows' binder
    types plus `TPlayer` and the top — no member of which carries a declared
    name. The nominal rule has nothing to reach here, so the sticky-key rule
    below is not a hole in it but the rule that governs the slot.

    Derived from the domain registry rather than listed, so a widened
    `ZONE_INDEX_ROLES` — the one edit that could put a named type in a key —
    reddens this instead of silently reopening the question.

    red under: add `TStruct` to the reachable set below (a stand-in for
    widening `ZONE_INDEX_ROLES` to a role whose binder type is nominal).
    """
    reachable: set[Type] = {d.binder_type for d in DOMAINS if d.id in ZONE_INDEX_ROLES}
    reachable |= {TPlayer(), TAny()}
    assert reachable, "the zone-index rows derived to nothing"
    nominal_named = {m.__name__ for m in NOMINAL_MEMBERS}
    offenders = sorted(
        type(t).__name__ for t in reachable if type(t).__name__ in nominal_named
    )
    assert not offenders, (
        f"{offenders} can now key a collection, so the keying domain is no "
        f"longer outside the nominal rule — reclassify TCollection.key in "
        f"_AUTHORED_CLASSES and decide the cell"
    )


def test_the_keying_domain_is_governed_by_the_sticky_key_rule() -> None:
    """The rule that DOES govern the slot, asserted on `join`'s output.

    Neither relation lets the key decide the verdict, so a test reading only
    the verdict can never see this slot — it would be a row that cannot fail.
    The observable is the key `join` RETURNS: agreeing keys keep their domain;
    disagreeing keys stay keyed with the domain unknowable (the permissive
    top, which the subscript check accepts and the keyed-membership Owner
    Guard still fires on). Keyedness is sticky in the prohibiting direction
    because a maybe-map is still ambiguous at runtime.

    red under: in `cardlang.types.join`, replace the key merge with
    `key = a.key` (agreement kept, disagreement silently resolved to the left
    operand's domain).
    """
    agreeing = join(
        TCollection(TCard(), key=TPlayer()), TCollection(TCard(), key=TPlayer())
    )
    assert isinstance(agreeing, TCollection) and agreeing.key == TPlayer()

    disagreeing = join(
        TCollection(TCard(), key=TPlayer()), TCollection(TCard(), key=TInteger())
    )
    assert isinstance(disagreeing, TCollection) and disagreeing.key == TAny()

    unkeyed = join(TCollection(TCard(), key=TPlayer()), TCollection(TCard()))
    assert isinstance(unkeyed, TCollection) and unkeyed.key == TAny(), (
        "a map merged with a non-map must stay keyed — an unkeyed result sends "
        "the keyed-membership Owner Guard dark"
    )


def test_every_nominal_member_carries_a_payload_that_can_go_stale() -> None:
    """The premise the whole grid rests on, pinned against the union.

    The nominal rule is only a rule because a nominal member's payload can
    disagree while its name agrees. `_NOMINALS` builds each member with a
    payload for exactly that reason; this pin says the payload field is real
    and that dataclass equality does distinguish the two probes — otherwise
    the grid's same-name rows would be comparing equal values and could not
    fail.

    red under: freeze `_NOMINALS`' two builders to ignore their `payload`
    argument (both probes become equal, and every same-name row goes
    vacuously green).
    """
    for member in NOMINAL_MEMBERS:
        payload_fields = [f.name for f in dataclasses.fields(member) if f.name != "name"]
        assert payload_fields, f"{member.__name__} has no payload beside its name"
        build = _NOMINALS[member]
        assert build("R", TAny()) != build("R", TInteger()), (
            f"two {member.__name__} probes named R compare EQUAL, so the "
            f"same-name rows of the grid cannot fail"
        )
