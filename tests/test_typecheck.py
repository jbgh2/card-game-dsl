"""Unit tests for type-checker internals (cardlang/typecheck.py)."""

from __future__ import annotations

from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.typecheck import type_from_name, value_enum_map
from cardlang.types import (
    TAny,
    TBoolean,
    TEnum,
    TInteger,
    TOptional,
    TPlayer,
)

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def test_type_from_name_scalars_and_enums() -> None:
    assert type_from_name("Integer", optional=False) == TInteger()
    assert type_from_name("Boolean", optional=False) == TBoolean()
    assert type_from_name("Player", optional=False) == TPlayer()
    assert type_from_name("Suit", optional=False) == TEnum("Suit")
    assert type_from_name("SeatDirection", optional=False) == TEnum("SeatDirection")


def test_type_from_name_optional_wraps() -> None:
    assert type_from_name("Player", optional=True) == TOptional(TPlayer())
    assert type_from_name("Suit", optional=True) == TOptional(TEnum("Suit"))


def test_type_from_name_unknown_is_any() -> None:
    assert type_from_name("Contract", optional=False) == TAny()  # user types deferred


def test_value_enum_map_classifies_suits_ranks_directions() -> None:
    game = check_source(HEARTS)
    m = value_enum_map(game)
    assert m["hearts"] == TEnum("Suit")  # a standard52 suit
    assert m["A"] == TEnum("Rank")  # a rank from `ranking:`
    assert m["left"] == TEnum("SeatDirection")  # a SeatDirection enum value
