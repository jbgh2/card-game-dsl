"""Unit tests for type-checker internals (cardlang/typecheck.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.functions import BUILTIN_CALL_FUNCS, PRIMITIVE_CALL_FUNCS
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.pipeline import check_source
from cardlang.runtime.errors import ShadowGuardError
from cardlang.typecheck import TypeEnv, infer, type_from_name, value_enum_map
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


# --- the `Call` arm's two no-signature refusals ------------------------------
#
# The arm is reached only when no table states a signature, which resolve
# refuses for every sentence a designer can write — so both cells are
# FUNCTION-GRAIN by necessity: they say the arm discriminates the two cases,
# never that a game description meets either. The pipeline-grain witness for
# the Primitive case is the Owner Guard's own,
# tests/test_primitives_block.py::test_the_regime_product_lands_where_the_table_says,
# with the rendered message at
# tests/rejections/primitives_declared_only_no_block.


@pytest.mark.expects_shadow_guard
def test_an_undeclared_primitive_meets_the_shadow_guard_naming_resolve() -> None:
    """A blockless game's table is `CALL_SIGS` entire, so a Primitive has no
    row in it — and that absence is the REGIME speaking, not a table that lost
    one. The refusal names resolve's arms rather than diagnosing registry
    drift, which for this case would be false.

    red under: drop the `PRIMITIVE_CALL_FUNCS` branch from the `Call` arm — the
    call falls to the drift assert and this cell fails on the type."""
    name = min(PRIMITIVE_CALL_FUNCS)
    with pytest.raises(ShadowGuardError) as excinfo:
        infer(n.Call(name, ()), TypeEnv())
    message = str(excinfo.value)
    assert "resolve._validate_refs" in message, message
    assert "declared-only" in message, message
    assert name in message, message


def test_a_builtin_with_no_signature_row_meets_the_drift_assert() -> None:
    """The other case the arm can reach, and the one whose drift diagnosis is
    true: a Builtin whose `CALL_SIGS` row is gone. Planted here, because
    `set(CALL_SIGS) == set(BUILTIN_CALL_FUNCS)` holds in tree
    (tests/test_signatures.py) and the assert is born green behind it."""
    name = min(BUILTIN_CALL_FUNCS)
    thinned = {k: v for k, v in CALL_SIGS.items() if k != name}
    with pytest.raises(AssertionError, match="registry has drifted"):
        infer(n.Call(name, ()), TypeEnv(call_sigs=thinned))
