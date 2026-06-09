"""Stdlib type signatures stay in sync with the name sets, and known signatures
are correct (cardlang/stdlib/signatures.py)."""

from __future__ import annotations

from cardlang.stdlib.functions import (
    STDLIB_CALL_FUNCS,
    STDLIB_VALUE_NAMES,
    ZONE_METHODS,
)
from cardlang.stdlib.signatures import (
    CALL_SIGS,
    METHOD_SIGS,
    VALUE_SIGS,
    ZONE_CONTENT,
    Sig,
)
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.types import TAny, TCard, TCollection, TEnum, TOptional, TPlayer, TTeam


def test_tables_reconcile_with_name_sets() -> None:
    # "stdlib is data": the signature tables must cover exactly the name sets.
    assert set(CALL_SIGS) == set(STDLIB_CALL_FUNCS)
    assert set(VALUE_SIGS) == set(STDLIB_VALUE_NAMES)
    assert set(METHOD_SIGS) == set(ZONE_METHODS)
    assert set(ZONE_CONTENT) == set(LIBRARY_ZONE_TYPES)


def test_known_call_signatures() -> None:
    assert CALL_SIGS["player_holding"] == Sig((TCard(),), TPlayer())
    assert CALL_SIGS["team_of"] == Sig((TPlayer(),), TTeam())
    # suit_of is polymorphic (card OR single-card zone) -> loose arg, optional ret.
    assert CALL_SIGS["suit_of"].ret == TOptional(TEnum("Suit"))


def test_zone_contents() -> None:
    assert ZONE_CONTENT["Hand"] == TCollection(TCard())
    assert ZONE_CONTENT["TeamPile"] == TCollection(TCard())
    assert ZONE_CONTENT["ChipStack"] == TCollection(TAny())  # resource zone, loose
