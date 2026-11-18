"""Every observation event's payload, declared once and probed field by field.

property:        Every [[observation-event]] is a member of the closed union
                 `cardlang.runtime.observe.ObservationEvent`, one frozen,
                 slotted kind per tag, and its constructor refuses, in words, a
                 field outside the shape `PAYLOAD_SHAPES` names for it, so no
                 event outside the vocabulary can be made, and a held event
                 cannot change. Each kind spells itself (`spelled()`) as its
                 tag followed by its fields, in declaration order. Every event
                 an emission site delivers, over every registered game, is a
                 member of the union. The shapes tell their fields apart: no
                 string is both a label and a card, a card is the rendering of
                 a card some component set holds, and a group of cards travels
                 in the one sorted order, so a site that hands over a label in
                 a card's place, a card no set holds, or cards in the order
                 they sat is refused. Every shape a kind's fields name has one
                 perturbation in the soundness matrix's payload probe table
                 that keeps a value inside its shape and changes it, and one
                 synthetic member the matrix builds an appended event from.
domain:          The kinds are `EVENT_KINDS`, derived from the union; each
                 kind's fields and their shapes are its `SHAPES`, read off its
                 dataclass fields, and `EVENT_PAYLOADS` is derived from them.
                 The shapes are `PAYLOAD_SHAPES`. A shape's members are the
                 alternatives its predicate admits, cells per alternative
                 below, each beside the nearest values an emission site could
                 plausibly hand over instead, and every one of those is crossed
                 with every field that carries the shape. The card and label
                 shapes are also crossed with the rendering of every card and
                 piece the component sets hold. The emission axis is every
                 registered game played along a bounded seeded line with an
                 observer installed, and the sweep must meet every kind at
                 least once, so no kind is certified by a line that never
                 emitted it.
registry:        the union and its kinds,
                 `cardlang.runtime.observe.ObservationEvent` and `EVENT_KINDS`;
                 the field shapes, `cardlang.runtime.observe.PAYLOAD_SHAPES`;
                 the cards, every set in `cardlang.runtime.values.COMPONENT_SETS`
                 as `build_deck` builds it; the probes and the synthetic
                 members, `tests.openspiel_ready.partition`'s `PAYLOAD_PROBES`
                 and `SYNTHETIC_PAYLOAD`; the games,
                 `cardlang.openspiel.registry.GAMES`.
held by:         Unrepresentable for kind and arity (the union, a dataclass's
                 signature); Derived and Pinned for content (the one
                 constructor check, `_Admitted.__post_init__`, red under
                 deleting it: every `test_a_field_outside_its_shape_is_refused`
                 cell); Unrepresentable for change once made (`frozen` and
                 `slots`).
does not prove:  That a site emits the RIGHT value. A `move` whose view is a
                 well-formed count of the wrong cards passes every cell here;
                 which observer learns what is the per-observer proofs' claim
                 (tests/openspiel_ready/). A card is held to every component
                 set rather than the game's own, so another deck's card passes;
                 a label is held to its spelling rather than the game's zones,
                 so a well-formed label naming no zone passes, and a decision
                 value is any string, so a label or a card handed over as one
                 passes. The sweep is bounded and seeded, so a shape
                 alternative only a later position or another line emits is
                 unwitnessed by it -- a `move` out of a trivial zone into an
                 identity one among them, which the member cells cover and no
                 swept line reaches. That `spelled()` is today's spelling: the
                 whole-line capture (tests/test_observation_spelling.py) holds
                 that.
"""

from __future__ import annotations

import random
import dataclasses
from functools import cache
from pathlib import Path
from typing import Any, get_args

import pytest

from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import load
from cardlang.runtime import observe
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.delegation import CONSTRUCTS
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
# a string, an integer or flag, or nothing.
SHAPE_MEMBERS: dict[str, tuple[Any, ...]] = {
    "seat": (0, 3),
    "label": ("deck", "hand[2]", "square[a1]"),
    "card": ("Q♠", "10♥", "Joker:joker", "mark:x"),
    "view": (("2♣", "9♥"), ("Joker:joker", "Joker:joker"), (), 2, 0, None),
    "value": ("pass", "bid(3)", 7, True, None),
    "phase": ("play", "passing", "hand_sequence", "_setup"),
    # The whole closed set, derived rather than listed: a word minted without
    # a phrase or a table row arrives here as an uncovered cell.
    "construct": tuple(sorted(CONSTRUCTS)),
    "count": (1, 3, 52),
    "destination": ("trick_pile", "hand[2]", "square[a1]", None),
    "variable": ("flag", "guess", "went_again"),
    # A slot's key or content as `render_state_variable` spells it, an empty
    # String's own spelling, and nothing (an unindexed slot, a slot not in scope).
    "rendering": ("1", "True", "{0:0,1:0}", "Q♠", "None", "", None),
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
    # A decision is one pick: a group of cards, in either order, is the
    # aggregate record no site emits.
    "value": (("2♣", "A♠"), ("A♠", "2♣"), ("pass",), object(), 1.5, ["pass"], (Card("2", "clubs"),)),
    # A phase names one declaration, so a zone label, a qualified path, the
    # sentinel a site would reach for outside every phase, and a seat are all
    # refused where a phase belongs.
    "phase": ("hand[2]", "play.passing", "", None, 3, "two words"),
    # The verb a designer wrote, the Title Case the prose uses, a zone, and
    # the neighbouring fields — none of them is the construct's own word.
    "construct": ("move", "Transfer", "trick_pile", "", None, 1),
    "count": (0, -1, True, None, "1", 1.5),
    # A card handed over as a zone, a perturbed label, and the neighbouring
    # shapes; None is a MEMBER here, not a refusal.
    "destination": ("Q♠", "hand[2]«perturbed»", 3, ("hand", 1), True),
    # A variable is named as declared: an indexed slot's label, a zone's
    # label, a card, and the neighbouring fields are not a name.
    "variable": ("guess[0]", "hand[2]", "Q♠", "", None, 3, "two words"),
    # Content handed over unrendered — an integer, a flag, a card, a
    # collection — is the value, not its spelling.
    "rendering": (1, True, Card("Q", "spades"), ("1",), {"0": "1"}, 1.5),
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


# Values no emitter should produce, but which an unfenced `Ctx.observe` can
# carry: a predicate that RAISES on one answers nothing, and the consumer that
# called it to get a refusal crashes instead of refusing.
_HOSTILE: tuple[Any, ...] = (["a"], {"a": 1}, {"a"}, bytearray(b"a"), object(), 1.5, None)


@pytest.mark.parametrize("shape", sorted(observe.PAYLOAD_SHAPES))
@pytest.mark.parametrize("value", _HOSTILE, ids=lambda v: type(v).__name__)
def test_every_shape_answers_rather_than_raises(shape: str, value: Any) -> None:
    """Every shape predicate is TOTAL: it answers True or False for any object,
    because its callers call it to be told, and one that raises turns a
    declared refusal into a crash.

    Quantified over the whole shape registry, not the shapes that happen to
    look risky — a bare `in` against a frozenset is the shape of the fault and
    any shape could grow one.

    red under: drop the `isinstance` from the `construct` predicate in
    `observe.PAYLOAD_SHAPES` — an unhashable value then raises `TypeError`
    here, and an event's constructor crashes on it rather than refusing."""
    assert observe.PAYLOAD_SHAPES[shape](value) in (True, False)


@pytest.mark.parametrize("rendering", _RENDERINGS)
def test_every_card_a_component_set_holds_is_a_card_and_never_a_label(
    rendering: str,
) -> None:
    """A `reveal` carries a label and a card side by side, so the two shapes
    must not share a string anywhere in the card domain, or a site that swaps
    them is read as well-formed."""
    assert observe.PAYLOAD_SHAPES["card"](rendering)
    assert not observe.PAYLOAD_SHAPES["label"](rendering)


def _members(kind: str) -> tuple[Any, ...]:
    return tuple(SHAPE_MEMBERS[shape][0] for shape in observe.EVENT_PAYLOADS[kind])


def _well_formed(kind: str) -> observe.ObservationEvent:
    return observe.EVENT_KINDS[kind](*_members(kind))


def test_every_kind_is_one_member_of_the_union() -> None:
    """The kinds a consumer dispatches over are the union's members, each with
    its own tag.

    red under: add a kind to `ObservationEvent` that reuses another's `KIND`
    -- the tags no longer key one member each."""
    members = get_args(observe.ObservationEvent)
    assert len({kind.KIND for kind in members}) == len(members)
    assert set(observe.EVENT_KINDS.values()) == set(members)
    assert set(observe.EVENT_PAYLOADS) == set(observe.EVENT_KINDS)


@pytest.mark.parametrize("kind", sorted(observe.EVENT_KINDS))
def test_a_well_formed_event_of_each_kind_spells_its_tag_then_its_fields(kind: str) -> None:
    """red under: reorder two fields in one kind's `spelled()` -- that kind's
    cell parts from the declaration order."""
    assert _well_formed(kind).spelled() == (kind, *_members(kind))


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
    fields = list(_members(kind))
    fields[index] = _REFUSALS[shape][wrong]
    with pytest.raises(AssertionError) as refused:
        observe.EVENT_KINDS[kind](*fields)
    assert repr(kind) in str(refused.value) and shape in str(refused.value)


@pytest.mark.parametrize("kind", sorted(observe.EVENT_KINDS))
@pytest.mark.parametrize("change", ["one field short", "one field over"])
def test_an_event_of_the_wrong_length_is_refused(kind: str, change: str) -> None:
    fields = _members(kind)
    fields = fields[:-1] if change == "one field short" else (*fields, "extra")
    with pytest.raises(TypeError):
        observe.EVENT_KINDS[kind](*fields)


@pytest.mark.parametrize("kind", sorted(observe.EVENT_KINDS))
def test_an_event_cannot_change_once_made(kind: str) -> None:
    """A held event reads as it did when it was delivered.

    red under: drop `frozen=True` from one kind -- its field assignment
    succeeds; drop `slots=True` -- a new attribute lands in its `__dict__`."""
    event = _well_formed(kind)
    name = event.SHAPES[0][0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(event, name, getattr(event, name))
    assert not hasattr(event, "__dict__")


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
def _swept(file_name: str) -> tuple[observe.ObservationEvent, ...]:
    """Every event one bounded, seeded line of `file_name` delivers, to every
    observer, in delivery order."""
    game, _ = load(str(GAMES_DIR / file_name))
    rng = random.Random(_SWEEP_SEED)
    uniform = random_chooser(rng)
    events: list[observe.ObservationEvent] = []
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
def test_every_emitted_event_is_a_member_of_the_union(short_name: str) -> None:
    """An emission site in code the type checker reads as `Any` could still
    hand `Ctx.observe` something else; executing every game says none does."""
    members = get_args(observe.ObservationEvent)
    for event in _swept(GAMES[short_name]):
        assert isinstance(event, members), f"{short_name}: {event!r}"


def test_the_sweep_meets_every_declared_kind() -> None:
    """The per-game cells are only as good as the kinds the lines reached."""
    seen = {event.KIND for file_name in GAMES.values() for event in _swept(file_name)}
    assert seen == set(observe.EVENT_KINDS), (
        f"the sweep reached only {sorted(seen)}; lengthen the line or add a "
        f"seed rather than letting a kind go uncertified"
    )
