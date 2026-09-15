"""Every observation event's payload, declared once and probed field by field.

property:        Every event an emission site delivers to an observer carries a
                 kind `cardlang.runtime.observe.EVENT_PAYLOADS` declares and,
                 field by field, a value inside the shape that kind's row names
                 — checked by execution over every registered game — and
                 `observe.payload_refusal` refuses, in words, a kind, an arity
                 or a field outside the table. The shapes tell their fields
                 apart: no string is both a label and a card, a card is the
                 rendering of a card some component set holds, and a group of
                 cards travels in the one sorted order, so a site that hands
                 over a label in a card's place, a card no set holds, or cards
                 in the order they sat is refused. Every shape a row names has
                 one perturbation in the soundness matrix's payload probe table
                 that keeps a value inside its shape and changes it, and one
                 synthetic member the matrix builds an appended event from, so
                 the matrix probes an event's content field by field for any
                 rendering rather than by the spelling of one.
domain:          The kinds and each kind's fields are the rows of
                 `EVENT_PAYLOADS`; the shapes are `PAYLOAD_SHAPES`. A shape's
                 members are the alternatives its predicate admits, cells per
                 alternative below, each beside the nearest values an emission
                 site could plausibly hand over instead, and every one of those
                 is crossed with every field that carries the shape. The card
                 and label shapes are also crossed with the rendering of every
                 card and piece the component sets hold. The emission axis is
                 every registered game played along a bounded seeded line with
                 an observer installed, and the sweep must meet every kind at
                 least once, so no kind is certified by a line that never
                 emitted it.
registry:        kinds and fields: `cardlang.runtime.observe.EVENT_PAYLOADS`;
                 shapes: `cardlang.runtime.observe.PAYLOAD_SHAPES`; the refusal:
                 `cardlang.runtime.observe.payload_refusal`; cards:
                 `cardlang.runtime.values.COMPONENT_SETS`, each set's cards as
                 `build_deck` builds them; the probes and the synthetic
                 members: `tests.openspiel_ready.partition`'s `PAYLOAD_PROBES`
                 and `SYNTHETIC_PAYLOAD`; games:
                 `cardlang.openspiel.registry.GAMES`.
does not prove:  That a site emits the RIGHT value. A `move` whose view is a
                 well-formed count of the wrong cards passes every cell here;
                 which observer learns what is the per-observer proofs' claim
                 (tests/openspiel_ready/). A card is held to every component
                 set rather than the game's own, so another deck's card passes;
                 a label is held to its spelling rather than the game's zones,
                 so a well-formed label naming no zone passes, and a decision
                 value is any string, so a label or a card handed over as one
                 passes. The sweep is bounded and seeded, so
                 a shape alternative only a later position or another line
                 emits is unwitnessed by it — a `move` out of a trivial zone
                 into an identity one among them, which the member cells cover
                 and no swept line reaches. Emission itself is unfenced:
                 `Ctx.observe` delivers whatever tuple a site hands it, and a
                 malformed event is refused where it is consumed — by the
                 matrix at probe time, by a rendering that asks
                 `payload_refusal` — never where it is made; the rung is
                 recorded at `EVENT_PAYLOADS`.
"""

from __future__ import annotations

import random
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import load
from cardlang.runtime import observe
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.state import IllegalMove
from cardlang.runtime.values import COMPONENT_SETS, Card, build_deck
from tests.openspiel_ready import partition

GAMES_DIR = Path(__file__).parent.parent / "docs" / "games"

# The members of each alternative each shape admits. The alternatives are the
# emitters' own: a seat is a seat index; a label names a zone, or a family
# instance keyed by a seat, a team, a position or a board cell; a card is the
# rendering of a card or piece a component set holds; a view is what one
# observer sees of moved cards through a projection — card renderings in
# sorted order with repeats kept (none, when nothing moved), a count, or
# nothing at all; a value is a decision value as `observe.render` spells it —
# a string, an integer or flag, nothing, or a multi-card selection.
SHAPE_MEMBERS: dict[str, tuple[Any, ...]] = {
    "seat": (0, 3),
    "label": ("deck", "hand[2]", "square[a1]"),
    "card": ("Q♠", "10♥", "Joker:joker", "mark:x"),
    "view": (("2♣", "9♥"), ("Joker:joker", "Joker:joker"), (), 2, 0, None),
    "value": ("pass", "bid(3)", 7, True, None, ("2♣", "A♠")),
}

# The nearest wrong values per shape: what a site that forgot to render,
# rendered through the wrong function, handed over a neighbouring field, or
# kept the order the cards sat in would hand the observer instead.
_REFUSALS: dict[str, tuple[Any, ...]] = {
    "seat": ("1", True, None),
    "label": ("Q♠", "hand[2]«perturbed»", 3, None, ("hand", 1)),
    "card": ("hand[2]", str(partition.SYNTHETIC), Card("Q", "spades"), None, 12),
    "view": (
        ("9♥", "2♣"),
        ("hand[2]",),
        {"2♣"},
        ["2♣"],
        True,
        1.0,
        (Card("2", "clubs"),),
    ),
    "value": (("A♠", "2♣"), ("pass",), object(), 1.5, ["pass"], (Card("2", "clubs"),)),
}

# Every card and piece rendering the component sets hold.
_RENDERINGS = sorted({str(card) for name in COMPONENT_SETS for card in build_deck(name)})


def test_the_shape_cells_name_every_declared_shape() -> None:
    """The member and refusal columns cover the shape axis the table declares,
    so a shape added to `PAYLOAD_SHAPES` arrives as cells to decide."""
    assert set(SHAPE_MEMBERS) == set(observe.PAYLOAD_SHAPES)
    assert set(_REFUSALS) == set(observe.PAYLOAD_SHAPES)


def test_every_shape_a_row_names_is_declared_and_every_declared_shape_is_named() -> None:
    """A row naming a shape nothing can check, or a shape no row carries, is
    caught here rather than at the first consumer to dispatch on it. Born
    green; reddens when a row names a misspelt shape."""
    named = {shape for row in observe.EVENT_PAYLOADS.values() for shape in row}
    assert named == set(observe.PAYLOAD_SHAPES)


@pytest.mark.parametrize(
    ("shape", "member"),
    [(shape, member) for shape, members in SHAPE_MEMBERS.items() for member in members],
)
def test_a_shape_admits_each_of_its_alternatives(shape: str, member: Any) -> None:
    assert observe.PAYLOAD_SHAPES[shape](member)


@pytest.mark.parametrize(
    ("shape", "value"),
    [(shape, value) for shape, values in _REFUSALS.items() for value in values],
)
def test_a_shape_refuses_the_nearest_wrong_value(shape: str, value: Any) -> None:
    assert not observe.PAYLOAD_SHAPES[shape](value)


@pytest.mark.parametrize("rendering", _RENDERINGS)
def test_every_card_a_component_set_holds_is_a_card_and_never_a_label(
    rendering: str,
) -> None:
    """A `reveal` carries a label and a card side by side, so the two shapes
    must not share a string anywhere in the card domain, or a site that swaps
    them is read as well-formed."""
    assert observe.PAYLOAD_SHAPES["card"](rendering)
    assert not observe.PAYLOAD_SHAPES["label"](rendering)


def _well_formed(kind: str) -> tuple[Any, ...]:
    return (kind, *(SHAPE_MEMBERS[shape][0] for shape in observe.EVENT_PAYLOADS[kind]))


@pytest.mark.parametrize("kind", sorted(observe.EVENT_PAYLOADS))
def test_a_well_formed_event_of_each_kind_is_accepted(kind: str) -> None:
    assert observe.payload_refusal(_well_formed(kind)) is None


@pytest.mark.parametrize(
    ("kind", "index", "wrong"),
    [
        (kind, index, wrong)
        for kind, row in sorted(observe.EVENT_PAYLOADS.items())
        for index, shape in enumerate(row)
        for wrong in range(len(_REFUSALS[shape]))
    ],
)
def test_a_field_outside_its_shape_is_refused(kind: str, index: int, wrong: int) -> None:
    shape = observe.EVENT_PAYLOADS[kind][index]
    fields = list(_well_formed(kind))
    fields[index + 1] = _REFUSALS[shape][wrong]
    refusal = observe.payload_refusal(tuple(fields))
    assert refusal is not None
    assert kind in refusal and shape in refusal


@pytest.mark.parametrize("kind", sorted(observe.EVENT_PAYLOADS))
@pytest.mark.parametrize("change", ["one field short", "one field over"])
def test_an_event_of_the_wrong_length_is_refused(kind: str, change: str) -> None:
    event = _well_formed(kind)
    event = event[:-1] if change == "one field short" else (*event, "extra")
    refusal = observe.payload_refusal(event)
    assert refusal is not None and kind in refusal


@pytest.mark.parametrize(
    "event",
    [("nonesuch", 42), (), ["announce", 0, "bid"], "chose", (7, "Q♠")],
    ids=["undeclared kind", "empty", "a list", "a bare string", "an untagged tuple"],
)
def test_an_event_outside_the_vocabulary_is_refused(event: Any) -> None:
    refusal = observe.payload_refusal(event)
    assert refusal is not None


def test_every_shape_has_one_probe_and_one_synthetic_member() -> None:
    """The matrix's payload probe table covers the shape axis, so a shape the
    emitter gains cannot reach an observer log unprobed."""
    assert set(partition.PAYLOAD_PROBES) == set(observe.PAYLOAD_SHAPES)
    assert set(partition.SYNTHETIC_PAYLOAD) == set(observe.PAYLOAD_SHAPES)


@pytest.mark.parametrize(
    ("shape", "member"),
    [(shape, member) for shape, members in SHAPE_MEMBERS.items() for member in members],
)
def test_a_probe_keeps_a_member_inside_its_shape_and_changes_it(
    shape: str, member: Any
) -> None:
    perturbed = partition.PAYLOAD_PROBES[shape](member)
    assert observe.PAYLOAD_SHAPES[shape](perturbed)
    assert perturbed != member


@pytest.mark.parametrize("shape", sorted(observe.PAYLOAD_SHAPES))
def test_a_synthetic_member_is_inside_its_shape(shape: str) -> None:
    assert observe.PAYLOAD_SHAPES[shape](partition.SYNTHETIC_PAYLOAD[shape])


# How far each game's line runs. Far enough for a challenge window or a
# showdown to open in the games that have them, near enough to keep the sweep
# a unit test; a game that ends or refuses sooner is swept to where it stopped.
_SWEEP_DECISIONS = 80
_SWEEP_SEED = 5


class _Enough(Exception):
    """The line has run as far as the sweep reads."""


@cache
def _swept(file_name: str) -> tuple[tuple[Any, ...], ...]:
    """Every event one bounded, seeded line of `file_name` delivers, to every
    observer, in delivery order."""
    game, _ = load(str(GAMES_DIR / file_name))
    rng = random.Random(_SWEEP_SEED)
    uniform = random_chooser(rng)
    events: list[tuple[Any, ...]] = []
    made = [0]

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        if made[0] >= _SWEEP_DECISIONS:
            raise _Enough
        made[0] += 1
        return uniform(player, candidates, count)

    try:
        play_game(
            game,
            rng,
            None,
            chooser=choose,
            observer=lambda _player, event: events.append(event),
        )
    except (_Enough, GameDescriptionError, IllegalMove):
        # A refusal ends the line where a uniform-random policy took it; the
        # events delivered before it are still events the sites emitted.
        pass
    return tuple(events)


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_every_emitted_event_matches_its_declared_payload(short_name: str) -> None:
    for event in _swept(GAMES[short_name]):
        refusal = observe.payload_refusal(event)
        assert refusal is None, f"{short_name}: {refusal}"


def test_the_sweep_meets_every_declared_kind() -> None:
    """The per-game cells are only as good as the kinds the lines reached."""
    seen = {event[0] for file_name in GAMES.values() for event in _swept(file_name)}
    assert seen == set(observe.EVENT_PAYLOADS), (
        f"the sweep reached only {sorted(seen)}; lengthen the line or add a "
        f"seed rather than letting a kind go uncertified"
    )
