"""The general info-state: projected zones + public state + the observation log
(derived; game-agnostic). Replaces the Hearts-specific encoding."""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import derive, information_state
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


def test_a_derived_view_does_not_follow_the_world_it_came_from() -> None:
    """A view describes one position, and keeps describing it.

    An indexed state variable is a live `{player: value}` dict on the frame, so
    a view that held it would report the CURRENT score at whatever later moment
    it was read — quietly, and only for the callers who keep a view rather than
    rendering it at once.

    red under: return the frames' own values from `infostate.derive` instead of
    snapshotting them.
    """
    from cardlang.openspiel.infostate import derive

    rs = _rs()
    view = derive(0, rs, [])
    # COPIED, or the comparison below aliases what it is measuring: an
    # unsnapshotted view hands back the frame's own dict, and a reference to it
    # would move with the mutation and read equal to itself.
    before = dict(dict(view.state)["score"])

    # IN PLACE, which is how an indexed assignment reaches a state variable.
    # Rebinding the name with `set` would swap the object and leave a
    # reference-holding view reading the old one — passing this cell while the
    # defect it names stands.
    rs.get("score")[0] = 999

    assert dict(view.state)["score"] == before
    assert dict(derive(0, rs, []).state)["score"] == {0: 999, 1: 20}


def test_a_view_cannot_be_written_through_into_the_world() -> None:
    """Holding a seat's view is not a licence to edit the game.

    `frozen=True` on the dataclass guards the FIELD, never what the field
    points at, so a live dict inside it would be a writable door into engine
    state for anything handed a view — a renderer, a policy, an LLM seat's
    prompt builder.

    red under: the same edit as above; the snapshot is what closes both.
    """
    import pytest

    from cardlang.openspiel.infostate import derive

    rs = _rs()
    scores = dict(derive(0, rs, []).state)["score"]
    with pytest.raises(TypeError):
        scores[0] = -1
    assert rs.get("score") == {0: 10, 1: 20}


def test_a_view_holds_the_cards_themselves_in_one_canonical_order() -> None:
    """A seat entitled to a zone's cards is handed the cards as values — what a
    reader needs to rank them, group them by suit or compare their strength —
    and in one canonical order, because an identity projection reveals which
    cards a zone holds and never the order they sit in it.

    red under: `view_of`'s identity arm answering the cards' renderings, or the
    cards in the order the zone stores them.
    """
    rs = _rs()
    hand = rs.zones.instance("hand", 0)
    hand.add(Card("10", "spades"))
    hand.add(Card("2", "hearts"))
    assert [str(card) for card in hand.cards] == ["Q♠", "10♠", "2♥"]

    held = dict(derive(0, rs, []).zones)["hand[0]"]
    assert held == (Card("10", "spades"), Card("2", "hearts"), Card("Q", "spades"))


def test_a_view_cannot_be_written_through_into_a_zone() -> None:
    """A card in a kept view is not the card in the zone.

    `frozen=True` stops `card.rank = ...` and not `object.__setattr__`, so a view
    handing out the engine's own card would hand out a way to change what a zone
    holds.

    red under: `infostate.derive` passing the zone views through without the
    snapshot.
    """
    rs = _rs()
    held = dict(derive(0, rs, []).zones)["hand[0]"]
    assert isinstance(held, tuple)
    object.__setattr__(held[0], "rank", "K")
    assert rs.zones.instance("hand", 0).cards == [Card("Q", "spades")]


def test_a_zone_view_spells_each_declared_shape() -> None:
    from cardlang.openspiel.infostate import _zone_line

    assert _zone_line("hand[0]", (Card("10", "spades"), Card("Q", "spades"))) == (
        "hand[0]=[10♠,Q♠]"
    )
    assert _zone_line("trick_pile", ()) == "trick_pile=[]"
    assert _zone_line("deck", 48) == "deck=#48"
    assert _zone_line("deck", 0) == "deck=#0"
    assert _zone_line("muck", None) == "muck=?"


@pytest.mark.parametrize(
    "wrong",
    [["Q♠"], {"Q♠"}, frozenset({"Q♠"}), {"Q♠": 1}, True, 1.0, ("Q♠",)],
    ids=["list", "set", "frozenset", "dict", "a flag", "a float", "card renderings"],
)
def test_a_zone_view_outside_the_declared_shapes_is_refused(wrong: Any) -> None:
    """`view_of` answers cards, a count, or nothing, and the information state
    spells exactly those — never an iterable's items as though they were cards,
    nor a flag as though it were a count.

    red under: `_zone_line` spelling any non-tuple as a count, or joining any
    tuple's items.
    """
    from cardlang.openspiel.infostate import _zone_line

    with pytest.raises(AssertionError, match="no declared rendering"):
        _zone_line("hand[0]", wrong)


@pytest.mark.parametrize("seat", [-1, 2, 7, True, False])
def test_a_view_is_derived_only_for_a_seat_at_the_table(seat: int) -> None:
    """Handed an integer that seats nobody, the projection would still answer —
    every zone through the view of a non-owner — and render a plausible view
    that belongs to no one. Handed a flag, it would answer as seat 1 or seat 0
    and render that seat's private cards under the name `PTrue` or `PFalse`.

    red under: drop the seat check from `infostate._facts` (every cell), or
    only its flag test (the two flag cells).
    """
    rs = _rs()
    with pytest.raises(AssertionError, match="no seat"):
        information_state(seat, rs, [])
    with pytest.raises(AssertionError, match="no seat"):
        derive(seat, rs, [])
