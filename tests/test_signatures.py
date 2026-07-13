"""Stdlib type signatures stay in sync with the name sets, and known signatures
are correct (cardlang/stdlib/signatures.py)."""

from __future__ import annotations

from cardlang.stdlib.functions import (
    STDLIB_AUCTION_OUTCOMES,
    STDLIB_CALL_FUNCS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_TRICK_OUTCOMES,
    STDLIB_VALUE_NAMES,
)
from cardlang.stdlib.signatures import (
    CALL_SIGS,
    EARLY_SIGS,
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
    assert set(EARLY_SIGS) == set(STDLIB_EARLY_PREDICATES)
    assert set(ZONE_CONTENT) == set(LIBRARY_ZONE_TYPES)
    # The two outcome namespaces partition the value-name set (the resolver
    # validates each round form against its own; the union is the bare-name space).
    assert STDLIB_TRICK_OUTCOMES | STDLIB_AUCTION_OUTCOMES == STDLIB_VALUE_NAMES
    assert STDLIB_TRICK_OUTCOMES.isdisjoint(STDLIB_AUCTION_OUTCOMES)


def test_outcome_names_are_dispatchable() -> None:
    # Each declared outcome name must resolve to a runtime callback — guards the
    # resolve namespace from drifting out of sync with the runtime dispatchers
    # (else a name passes resolve and then Assertion-fails mid-playout).
    from cardlang.runtime.stdlib import auction_outcome_function, value_function

    for name in STDLIB_TRICK_OUTCOMES:
        assert callable(value_function(name))
    for name in STDLIB_AUCTION_OUTCOMES:
        assert callable(auction_outcome_function(name))


def test_climb_queries_are_dispatchable() -> None:
    # The climbing form's combination-engine query names must each resolve to a
    # runtime callable, like the outcome names above — guards the resolve namespace
    # (STDLIB_CLIMB_LEADS / STDLIB_CLIMB_FOLLOWS) from drifting out of sync with the
    # runtime dispatchers.
    from cardlang.runtime.stdlib import climb_follow_function, climb_lead_function
    from cardlang.stdlib.functions import STDLIB_CLIMB_FOLLOWS, STDLIB_CLIMB_LEADS

    for name in STDLIB_CLIMB_LEADS:
        assert callable(climb_lead_function(name))
    for name in STDLIB_CLIMB_FOLLOWS:
        assert callable(climb_follow_function(name))


def test_call_funcs_are_dispatchable() -> None:
    # Each name registered in STDLIB_CALL_FUNCS must reach a real arm of
    # call()'s match — not fall through to its loud `case _` default. Unlike
    # value_function/climb_lead_function (which just return a callable
    # reference), call() dispatches AND executes in the same statement, so
    # there is no args-free way to "just look up" an arm: invoke each name
    # with no args and a minimal-but-real Ctx, and treat any exception other
    # than the default arm's AssertionError as proof the name was dispatched
    # (wrong arg count, missing runtime state, etc. all reach real code past
    # the match).
    import random

    from cardlang.ast import nodes as n
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.stdlib import call
    from cardlang.runtime.values import Seating

    decls = (n.ZoneDecl(name="probe", index=None, type_ref=n.TypeRef(name="Hand")),)
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))

    for name in STDLIB_CALL_FUNCS:
        try:
            call(name, [], ctx)
        except AssertionError as e:
            assert "unknown stdlib function" not in str(e), (
                f"{name!r} falls through call()'s default arm: {e}"
            )
        except Exception:
            pass  # dispatched: failed downstream for some other reason



def test_known_call_signatures() -> None:
    assert CALL_SIGS["player_holding"] == Sig((TCard(),), TPlayer())
    assert CALL_SIGS["team_of"] == Sig((TPlayer(),), TTeam())
    # suit_of is polymorphic (card OR single-card zone) -> loose arg, optional ret.
    assert CALL_SIGS["suit_of"].ret == TOptional(TEnum("Suit"))


def test_zone_contents() -> None:
    assert ZONE_CONTENT["Hand"] == TCollection(TCard())
    assert ZONE_CONTENT["TeamPile"] == TCollection(TCard())
    assert ZONE_CONTENT["ChipStack"] == TCollection(TAny())  # resource zone, loose
