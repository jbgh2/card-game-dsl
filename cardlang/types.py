"""The type model for the static type checker.

A closed union of frozen-dataclass `Type`s, dispatched with structural `match` +
`typing.assert_never` (the same discipline as the AST in `ast/nodes.py`). The
checker (`typecheck.py`) infers a `Type` for every expression and validates the
type-checkable constructs.

Scope today is pragmatic: enough to type the corpus and catch real type errors.
Collections and zone contents are typed loosely (`TCollection`, often of
`TCard`); `TAny` is the permissive top that propagates through every operation
without error, used for the deferred parts of the typed object model (the full
`ZoneContents` query API, `Resource` generics, card attributes/facing). `TStruct`
and `TVariant` are declared as seams for later stages (user-defined `type`
declarations; tagged-union / phase outcomes) but are not yet constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TypeAlias


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
class TEnum:
    """A deck/stdlib value enum: ``Suit``, ``Rank``, ``Direction``."""

    name: str


@dataclass(frozen=True, slots=True)
class TOptional:
    """``T?`` — a ``T`` or the absence value ``none``."""

    inner: "Type"


@dataclass(frozen=True, slots=True)
class TCollection:
    """An ordered/keyed collection of ``element`` (a zone's contents, a query
    result, a player set). Structural distinctions (set/ordered/stack) and the
    full query API are deferred.

    ``key`` is the subscript's domain when the collection is a KEYED map — a
    per-player/per-team state variable, an indexed `let` — and ``None`` for
    positional collections and untracked shapes. It participates in the
    subscript/indexed-assignment key checks only, never in assignability or
    unification (`_bare_collection` strips it there): the value space of
    `score[player]` IS `Collection<Integer>`; the key is a fact about how you
    may ADDRESS it, not about what it holds."""

    element: "Type"
    key: "Type | None" = None


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
    fields: Mapping[str, "Type"]
    derived: frozenset[str]


@dataclass(frozen=True, slots=True)
class TVariant:
    """A tagged-union / phase-outcome type (Stage 2/3: `{ a(T) | b }`)."""

    name: str
    cases: Mapping[str, tuple["Type", ...]]


Type: TypeAlias = (
    TInteger
    | TBoolean
    | TString
    | TPlayer
    | TTeam
    | TCard
    | TEnum
    | TOptional
    | TCollection
    | TNull
    | TAny
    | TStruct
    | TVariant
)


def unify(a: Type, b: Type) -> Type | None:
    """The common type of ``a`` and ``b``, or ``None`` if incompatible.

    Equal types unify to themselves; ``TAny`` absorbs anything, at ANY depth; a
    bare ``T`` and ``T?`` unify to ``T?``. Anything else is a mismatch.

    The depth matters. `TAny` used to absorb only at the top level, so two
    collections were compared by plain equality — and a deliberately-unrefined
    element type (a chip stack is `Collection<Any>` precisely because that part of
    the object model is unrefined) was judged disjoint from `Collection<Card>`. Every
    caller that asks "are these compatible?" inherited that: the equality wall would
    MANUFACTURE a `can never be equal` diagnostic for a comparison whose only
    uncertainty was in the element. Gradual typing has to be gradual all the way
    down, or it is just a top-level special case.
    """
    if isinstance(a, TAny) or isinstance(b, TAny):
        return TAny()
    if isinstance(a, TCollection) and isinstance(b, TCollection):
        element = unify(a.element, b.element)
        return TCollection(element) if element is not None else None
    if isinstance(a, TNull):
        return b if isinstance(b, TOptional) else TOptional(b)
    if isinstance(b, TNull):
        return a if isinstance(a, TOptional) else TOptional(a)
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
        # strip it and compare elements exactly as the old whole-type equality
        # did for keyless collections.
        return src.element == dst.element
    return False
