"""Unit tests for the Type model (cardlang/types.py)."""

from __future__ import annotations

from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TNull,
    TOptional,
    TPlayer,
    Type,
    coercible,
    subscriptable,
    join,
)


def test_assignable() -> None:
    assert coercible(TInteger(), TInteger())
    assert coercible(TInteger(), TPlayer())  # players are 0-based int identities
    assert coercible(TInteger(), TOptional(TPlayer()))  # bare fits its optional
    assert coercible(TOptional(TPlayer()), TPlayer())  # optional reads as its base
    assert coercible(TAny(), TEnum("Suit"))  # Any is compatible either way
    assert not coercible(TEnum("Suit"), TInteger())
    assert not coercible(TBoolean(), TInteger())
    assert coercible(TNull(), TOptional(TPlayer()))  # `none` fits an optional
    assert not coercible(TNull(), TPlayer())  # …but not a plain Player


def test_type_equality_is_structural() -> None:
    assert TInteger() == TInteger()
    assert TEnum("Suit") == TEnum("Suit")
    assert TEnum("Suit") != TEnum("Rank")
    assert TCollection(TCard()) == TCollection(TCard())
    a: Type = TInteger()
    b: Type = TBoolean()
    assert a != b  # distinct kinds are unequal


def test_unify_equal_returns_that_type() -> None:
    assert join(TInteger(), TInteger()) == TInteger()
    assert join(TEnum("Suit"), TEnum("Suit")) == TEnum("Suit")


def test_unify_any_propagates() -> None:
    assert join(TAny(), TInteger()) == TAny()
    assert join(TInteger(), TAny()) == TAny()


def test_unify_optional_absorbs_bare() -> None:
    assert join(TInteger(), TOptional(TInteger())) == TOptional(TInteger())
    assert join(TOptional(TInteger()), TInteger()) == TOptional(TInteger())


def test_unify_mismatch_is_none() -> None:
    assert join(TInteger(), TBoolean()) is None
    assert join(TEnum("Suit"), TEnum("Rank")) is None


def test_subscriptable() -> None:
    assert subscriptable(TCollection(TCard()))
    assert subscriptable(TAny())
    assert not subscriptable(TInteger())
    assert not subscriptable(TBoolean())
