"""The type model for the static type checker.

A closed union of frozen-dataclass `Type`s, dispatched with structural `match` +
`typing.assert_never` (the same discipline as the AST in `ast/nodes.py`). The
checker (`typecheck.py`) infers a `Type` for every expression and validates the
type-checkable constructs.

Scope today is pragmatic: enough to type the corpus and catch real type errors.
Collections and zone contents are typed loosely (`TCollection`, often of
`TCard`); `TAny` is the permissive top that propagates through every operation
without error, used for the deferred parts of the typed object model (the full
`ZoneContents` query API, `Resource` generics, card attributes/facing).
`TStruct` types a declared `type`, and `TOutcome` a `define`'s or an outcome
phase's cases; both are constructed (`typecheck.py`), but only `TStruct` is
reachable as an expression's inferred type -- a outcome is a registry entry
consulted when checking `produce` / `produces:`, never returned by `infer`.

Adding a member here is not local: every consumer that dispatches over `Type`
must gain an arm. The dispatches are isinstance chains rather than
`match` + `assert_never`, so mypy does NOT force that sweep -- the
`Member`-arm classification pin in `tests/test_typecheck_errors.py` is what
fails loudly instead, by deriving its domain from `get_args(Type)`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

# The two content flavors a game declares (`cards:` vs `pieces:`) -- the value
# of `Game.content_flavor` and `ComponentSet.flavor`, and the dispatch key for
# the flavor-aware guards. Not a `Type` (it types no expression); it lives in
# this leaf module so the AST, the resolver, the checker, and the runtime
# registry all import it without any of them importing each other.
Flavor: TypeAlias = Literal["card", "piece"]


@dataclass(frozen=True, slots=True)
class TInteger:
    pass


@dataclass(frozen=True, slots=True)
class TBoolean:
    pass


@dataclass(frozen=True, slots=True)
class TString:
    pass


@dataclass(frozen=True, slots=True)
class TPlayer:
    pass


@dataclass(frozen=True, slots=True)
class TTeam:
    pass


@dataclass(frozen=True, slots=True)
class TCard:
    pass


@dataclass(frozen=True, slots=True)
class TCell:
    """A board cell — one member of the named-member position domain a `board:`
    clause mints (decisions.md "Boards and cells"). Distinct from ``TInteger``
    so a named-member domain's parameters, binders and subscript keys reject
    integer operands (`square[7]`, `at is 3`) and vice versa, while integer
    position domains keep ``TInteger`` exactly. Its runtime representation is
    the cell name string (`"a1"`)."""


@dataclass(frozen=True, slots=True)
class TDir:
    """A movement direction -- one member of the named-member `dir` domain a
    `board:` clause mints (decisions.md "Boards and cells", rung-2 movement).
    Distinct from ``TCell`` and from ``TEnum("SeatDirection")`` (the seat
    ring direction) so a direction move parameter, binder or comparison rejects
    a cell (`along is a1`), an integer (`along is 3`), an ordering
    (`along < along2`), a subscript, and an `offset_by` operand -- riding only
    the generic type chains, never a permissive fall-through. Its runtime
    representation is the direction name string (`"ahead"`)."""


@dataclass(frozen=True, slots=True)
class TLine:
    """A board line -- one member of the collection ``lines(k)`` returns
    (decisions.md "Boards and cells"), itself an ordered collection of
    ``TCell`` members. Distinct from ``TCollection(TCell())`` so the two
    collection quantifier forms stay type-directed: ``any line in <expr>``
    demands a collection of lines, ``all cells in <expr>`` demands a single
    line, and neither can be spelled with a bare card/zone collection. Its
    runtime representation is the cell-name tuple (`("a1", "b1", "c1")`)."""


@dataclass(frozen=True, slots=True)
class TEnum:
    """A deck/stdlib value enum: ``Suit``, ``Rank``, ``Direction``."""

    name: str


@dataclass(frozen=True, slots=True)
class TOptional:
    """``T?`` — a ``T`` or the absence value ``none``."""

    inner: Type


@dataclass(frozen=True, slots=True)
class TCollection:
    """An ordered/keyed collection of ``element`` (a zone's contents, a query
    result, a player set). Structural distinctions (set/ordered/stack) and the
    full query API are deferred.

    ``key`` is the subscript's domain when the collection is a KEYED map — a
    per-player/per-team state variable, an indexed `let` — and ``None`` for
    positional collections and untracked shapes. It drives the
    subscript/indexed-assignment key checks and the keyed-membership Owner Guard.
    Facets do not decide TOP-LEVEL compatibility: `assignable`'s collection
    arm compares elements only, and `unify` preserves facets the two sides
    agree on rather than judging by them. (Nested collections compare
    elements with full equality, so a facet mismatch one level down does
    distinguish — no current value shape nests a flag-bearing collection.)
    The value space of `score[player]` IS `Collection<Integer>`; the key is a
    fact about how you may ADDRESS it, not about what it holds.

    Facets are bookkeeping, and bookkeeping riding on a structural type must
    be PRESERVED by every site that rebuilds one — an obligation that already
    bit once (`unify` dropped both facets; see its docstring). The promotion
    path to real nominal kinds (`TZone`, `TMap`), and the three named
    triggers that would fire it, are recorded in issue #123."""

    element: Type
    key: Type | None = None
    # True for a value that IS a zone at runtime (`ZONE_CONTENT`'s types, a
    # zone-family subscript) — as opposed to a COMPUTED card collection (a
    # query result, a list literal), which types identically by element but
    # evaluates to a plain list. Transfer/epistemic zone positions require it;
    # like `key`, it never participates in assignability or unification.
    zone: bool = False


@dataclass(frozen=True, slots=True)
class TNull:
    """The type of the `none` literal: the absence value, assignable only to an
    optional (or `TAny`). Distinct from `TOptional`, which is a *set* optional
    value that reads as its base (`Player?` used where `Player` is expected)."""


@dataclass(frozen=True, slots=True)
class TAny:
    """The permissive top: propagates through every operation without error.
    Used for pronoun member access and the deferred parts of the object model."""


# --- seams for later stages (declared, not yet constructed) ---


@dataclass(frozen=True, slots=True)
class TStruct:
    """A user-defined struct type (Stage 2: `type Name = { … } derived { … }`)."""

    name: str
    fields: Mapping[str, Type]
    derived: frozenset[str]


@dataclass(frozen=True, slots=True)
class TOutcome:
    """A tagged-union / phase-outcome type (Stage 2/3: `{ a(T) | b }`)."""

    name: str
    cases: Mapping[str, tuple[Type, ...]]


Type: TypeAlias = (
    TInteger
    | TBoolean
    | TString
    | TPlayer
    | TTeam
    | TCard
    | TCell
    | TDir
    | TLine
    | TEnum
    | TOptional
    | TCollection
    | TNull
    | TAny
    | TStruct
    | TOutcome
)


def unify(a: Type, b: Type) -> Type | None:
    """The common type of ``a`` and ``b``, or ``None`` if incompatible.

    Equal types unify to themselves; ``TAny`` absorbs anything, at ANY depth; a
    bare ``T`` and ``T?`` unify to ``T?``. Anything else is a mismatch.

    The depth matters. Were `TAny` to absorb only at the top level, two
    collections would be compared by plain equality — and a deliberately-unrefined
    element type (a chip stack is `Collection<Any>` precisely because that part of
    the object model is unrefined) would be judged disjoint from `Collection<Card>`.
    Every caller that asks "are these compatible?" would inherit that: the equality
    Owner Guard would MANUFACTURE a `can never be equal` diagnostic for a comparison
    whose only uncertainty is in the element. Gradual typing has to be gradual all
    the way down, or it is just a top-level special case.
    """
    if isinstance(a, TAny) or isinstance(b, TAny):
        return TAny()
    if isinstance(a, TStruct) and isinstance(b, TStruct):
        # Nominal, for the reason `assignable` gives: same name, same type.
        return a if a.name == b.name else None
    if isinstance(a, TCollection) and isinstance(b, TCollection):
        element = unify(a.element, b.element)
        if element is None:
            return None
        # PRESERVE the facets. Rebuilding bare TCollection(element) here
        # would erase them: `if c then hand[0] else hand[1]` — two genuine
        # zones — would unify to a non-zone and be falsely rejected at every
        # endpoint, and two same-keyed maps would unify to an unkeyed one,
        # sending the keyed-map Owner Guard dark through any IfExpr. The two
        # facets merge in OPPOSITE directions because they feed opposite
        # guard polarities: `zone` PERMITS (an endpoint requires a definite
        # zone, so a maybe-zone must not qualify — AND), while `key`
        # PROHIBITS (membership on a maybe-map is still ambiguous at runtime,
        # so keyedness must be STICKY: agreeing keys keep their domain; a map
        # merged with a non-map, or a differently-keyed map, stays keyed with
        # the domain unknowable — TAny, which the subscript check accepts and
        # the membership Owner Guard still fires on).
        if a.key == b.key:
            key: Type | None = a.key
        else:
            key = TAny()
        return TCollection(element, key=key, zone=a.zone and b.zone)
    if isinstance(a, TNull):
        return b if isinstance(b, TOptional) else TOptional(b)
    if isinstance(b, TNull):
        return a if isinstance(a, TOptional) else TOptional(a)
    if isinstance(a, TOptional) and isinstance(b, TOptional):
        # Reach through the wrapper before falling back to structural
        # equality: two `R?` holding snapshots that disagree about a derived
        # field are the same nominal type, and returning None here would send
        # an `IfExpr` over them to the permissive top — turning a stale
        # snapshot into a silently unchecked subtree, which is the defect the
        # nominal rule exists to prevent.
        inner = unify(a.inner, b.inner)
        return TOptional(inner) if inner is not None else None
    if a == b:
        return a
    if isinstance(a, TOptional) and unify(a.inner, b) == a.inner:
        return a
    if isinstance(b, TOptional) and unify(b.inner, a) == b.inner:
        return b
    return None


def subscriptable(t: Type) -> bool:
    """Whether ``t[...]`` is legal: collections (and the permissive top)."""
    return isinstance(t, (TCollection, TAny))


def assignable(src: Type, dst: Type) -> bool:
    """Whether a value of type ``src`` may be assigned where ``dst`` is expected.

    `TAny` is compatible either way. A bare value fits its optional (`T` → `T?`).
    An `Integer` may stand for a `Player`/`Team` — both are 0-based int identities,
    so a player/team literal or default (`dealer : Player = 0`) is fine.
    """
    if isinstance(src, TAny) or isinstance(dst, TAny):
        return True
    if isinstance(src, TNull):
        return isinstance(dst, TOptional)  # `none` only fits an optional
    if isinstance(src, TStruct) and isinstance(dst, TStruct):
        # A declared `type` is NOMINAL: two `R`s are the same type because they
        # are both named R, not because their field mappings happen to match.
        # `TStruct` carries its fields, so dataclass equality is structural —
        # and any two registries that disagreed about one derived field's type
        # then produced two unequal `R`s, which surfaced as diagnostics reading
        # `expects R, got R` and made well-typed programs unwritable. Identity
        # belongs to the name; the fields are what the name resolves TO.
        return src.name == dst.name
    if src == dst:
        return True
    if isinstance(dst, TOptional):
        inner = src.inner if isinstance(src, TOptional) else src
        return assignable(inner, dst.inner)
    if isinstance(src, TOptional):
        # An optional used where its base is expected: the DSL has no flow
        # narrowing, so a `Player?` known to be set reads as a `Player`.
        return assignable(src.inner, dst)
    if isinstance(src, TInteger) and isinstance(dst, (TPlayer, TTeam)):
        return True
    if isinstance(src, TCollection) and isinstance(dst, TCollection):
        # The key is how a map is ADDRESSED, not part of its value space —
        # strip it and compare elements. RECURSE rather than compare with `==`:
        # dataclass equality is structural, so two collections of the same
        # nominal struct whose snapshots disagree about one derived field would
        # be judged disjoint, exactly as the bare case was before the nominal
        # rule. The rule has to reach through every wrapper, or it is a
        # top-level special case.
        return assignable(src.element, dst.element)
    return False
