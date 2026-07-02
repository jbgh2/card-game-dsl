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
