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


def test_nested_facets_do_not_distinguish() -> None:
    """Facets are invisible to both relations at every depth, not just the top.

    The four measured outcomes, pinned so the docstring that states them
    cannot drift back: `cardlang/types.py`'s `TCollection` once claimed a
    facet mismatch one level down DID distinguish, which no test contradicted
    because none reached the nested case.

    red under: give `coercible`'s or `join`'s collection arm a facet
    comparison (`src.zone == dst.zone`) — the top-level cells redden first,
    the nested ones with them.
    """
    zone_c = TCollection(TCard(), zone=True)
    plain_c = TCollection(TCard(), zone=False)

    # top level: a facet mismatch does not decide compatibility
    assert coercible(zone_c, plain_c)
    assert join(zone_c, plain_c) is not None

    # one level down: both arms recurse, so the mismatch is equally invisible
    assert coercible(TCollection(zone_c), TCollection(plain_c))
    assert join(TCollection(zone_c), TCollection(plain_c)) is not None

    # what join DOES do with facets: preserve agreement, drop disagreement
    merged_same = join(zone_c, TCollection(TCard(), zone=True))
    merged_diff = join(zone_c, plain_c)
    assert isinstance(merged_same, TCollection) and merged_same.zone is True
    assert isinstance(merged_diff, TCollection) and merged_diff.zone is False


def test_a_flag_bearing_collection_does_nest() -> None:
    """The safety argument for the corrected docstring, executed.

    The old prose excused the nested case as unreachable ("no current value
    shape nests a flag-bearing collection"). A zone-family subscript keeps
    the flag, so wrapping one — which an indexed `let` does, per
    tests/test_let_typing.py::test_an_indexed_let_types_as_a_collection_of_its_element
    — nests it.

    red under: in `infer`'s family-subscript arm, replace `return zone_t`
    with `return TCollection(zone_t.element)` — the family's type is rebuilt
    without its facet and the flag assert below fails. (The flag survives
    today precisely because that arm returns the zone's type unrebuilt; there
    is no `zone=` to drop.)
    """
    from cardlang.typecheck import TypeEnv, infer
    import cardlang.ast.nodes as n

    env = TypeEnv(
        zones={"hand": TCollection(TCard(), zone=True)},
        zone_families={"hand": TPlayer()},
        locals={"p": TPlayer()},
    )
    element = infer(
        n.Subscript(n.NameRef("hand", ref_kind="zone"), n.NameRef("p", ref_kind="local")),
        env,
    )
    assert isinstance(element, TCollection) and element.zone is True

    nested = TCollection(element, key=TPlayer())
    inner = nested.element
    assert isinstance(inner, TCollection) and inner.zone is True


def test_the_type_modules_docstring_examples_run() -> None:
    """`testpaths = ["tests"]` keeps `cardlang/` out of the default collection,
    so the doctests in `cardlang/types.py` would be written and never run --
    enumerated-but-never-executed, which is the shape this repo calls
    vacuously green. This runs them inside the gate that does get collected.

    red under: change any expected output in a `types.py` docstring example.
    """
    import doctest

    import cardlang.types

    result = doctest.testmod(cardlang.types, verbose=False)
    assert result.attempted > 10, (
        f"only {result.attempted} doctest examples ran -- the sweep would be "
        "vacuous if the examples were removed or stopped being recognised"
    )
    assert result.failed == 0, f"{result.failed} of {result.attempted} failed"
