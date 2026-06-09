"""Unit tests for the Type model (cardlang/types.py)."""

from __future__ import annotations

from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TOptional,
    subscriptable,
    unify,
)


def test_type_equality_is_structural() -> None:
    assert TInteger() == TInteger()
    assert TEnum("Suit") == TEnum("Suit")
    assert TEnum("Suit") != TEnum("Rank")
    assert TCollection(TCard()) == TCollection(TCard())
    assert TInteger() != TBoolean()


def test_unify_equal_returns_that_type() -> None:
    assert unify(TInteger(), TInteger()) == TInteger()
    assert unify(TEnum("Suit"), TEnum("Suit")) == TEnum("Suit")


def test_unify_any_propagates() -> None:
    assert unify(TAny(), TInteger()) == TAny()
    assert unify(TInteger(), TAny()) == TAny()


def test_unify_optional_absorbs_bare() -> None:
    assert unify(TInteger(), TOptional(TInteger())) == TOptional(TInteger())
    assert unify(TOptional(TInteger()), TInteger()) == TOptional(TInteger())


def test_unify_mismatch_is_none() -> None:
    assert unify(TInteger(), TBoolean()) is None
    assert unify(TEnum("Suit"), TEnum("Rank")) is None


def test_subscriptable() -> None:
    assert subscriptable(TCollection(TCard()))
    assert subscriptable(TAny())
    assert not subscriptable(TInteger())
    assert not subscriptable(TBoolean())
