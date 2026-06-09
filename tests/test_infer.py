"""Unit tests for expression type inference (cardlang/typecheck.py infer)."""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    TPlayer,
    TString,
)
from cardlang.typecheck import TypeEnv, infer


def test_infer_literals() -> None:
    env = TypeEnv()
    assert infer(n.IntLit(5), env) == TInteger()
    assert infer(n.StrLit("x"), env) == TString()
    assert infer(n.CardLiteral("A", "spades"), env) == TCard()
    assert infer(n.AllPlayers(), env) == TCollection(TPlayer())


def test_infer_nameref_by_refkind() -> None:
    env = TypeEnv(
        state_vars={"score": TInteger()},
        zones={"hand": TCollection(TCard())},
        value_enums={"hearts": TEnum("Suit")},
    )
    assert infer(n.NameRef("score", ref_kind="state_var"), env) == TInteger()
    assert infer(n.NameRef("hand", ref_kind="zone"), env) == TCollection(TCard())
    assert infer(n.NameRef("hearts", ref_kind="enum_value"), env) == TEnum("Suit")
    assert infer(n.NameRef("true", ref_kind="bool"), env) == TBoolean()


def test_infer_local_binding() -> None:
    env = TypeEnv().with_local("p", TPlayer())
    assert infer(n.NameRef("p", ref_kind="local"), env) == TPlayer()


def test_infer_refined_and_unrefined_nodes() -> None:
    env = TypeEnv()
    assert infer(n.Not(n.IntLit(1)), env) == TBoolean()  # refined: a predicate
    # Member access (pronoun fields / sugar) is deferred — permissive.
    assert infer(n.Member(n.NameRef("card", ref_kind="local"), "suit"), env) == TAny()
