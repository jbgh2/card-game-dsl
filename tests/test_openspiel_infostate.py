"""The general info-state: projected zones + public state + the observation log
(derived; game-agnostic). Replaces the Hearts-specific encoding."""

from __future__ import annotations

import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import information_state
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating


def _rs() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, players=(0, 1)), random.Random(0))
    rs.zones.instance("hand", 0).add(Card("Q", "spades"))
    rs.zones.instance("hand", 1).add(Card("2", "clubs"))
    rs.zones.single("trick_pile").add(Card("7", "hearts"))
    rs.push_frame()
    rs.declare("score", indexed=False, value={0: 10, 1: 20})
    return rs


def test_own_hand_at_identity_other_hand_as_count() -> None:
    s = information_state(0, _rs(), [])
    assert str(Card("Q", "spades")) in s        # own hand: identity
    assert str(Card("2", "clubs")) not in s     # opponent's hand: hidden
    assert str(Card("7", "hearts")) in s        # public pile: identity


def test_state_variables_are_public() -> None:
    s0 = information_state(0, _rs(), [])
    s1 = information_state(1, _rs(), [])
    assert "score" in s0 and "10" in s0 and "20" in s0
    assert "score" in s1 and "10" in s1 and "20" in s1


def test_observation_log_is_included_and_ordered() -> None:
    log: list[tuple[Any, ...]] = [("announce", 1, "bid(3)"), ("chose", "7 of hearts")]
    s = information_state(0, _rs(), log)
    assert "bid(3)" in s
    assert s.index("bid(3)") < s.index("chose")  # log order preserved


def test_deterministic_across_dict_insertion_orders() -> None:
    a, b = _rs(), _rs()
    b.set("score", {1: 20, 0: 10})  # same mapping, different insertion order
    assert information_state(0, a, []) == information_state(0, b, [])


def test_render_covers_the_declared_value_shapes_and_refuses_the_rest() -> None:
    """Closed-domain completeness (decisions.md): the information state's
    value renderer covers exactly the shapes the language can put in state —
    scalars, None, Card, containers, StructValue (canonically, insertion-order
    independent) — and refuses anything else loudly rather than embedding an
    unstable repr in a certified-deterministic string."""
    import pytest

    from cardlang.openspiel.infostate import _render
    from cardlang.runtime.state import StructValue
    from cardlang.runtime.values import Card

    assert _render(3) == "3"
    assert _render(True) == "True"
    assert _render("hearts") == "hearts"
    assert _render(None) == "None"
    assert _render(Card("Q", "spades")) == "Q♠"
    a = StructValue("Contract", {"level": 1, "suit": "spades"})
    b = StructValue("Contract", {"suit": "spades", "level": 1})
    assert _render(a) == _render(b) == "Contract{level:1,suit:spades}"

    class Alien:
        pass

    with pytest.raises(AssertionError, match="no declared rendering"):
        _render(Alien())
