"""Per-observer [[observation-event]] emission — the [[projection]] substrate.

Every event is a member of the closed union `ObservationEvent` below: one
frozen kind per tag, whose fields each carry a `PAYLOAD_SHAPES` row saying
what they admit, and which spells itself as a plain, deterministic,
human-readable tuple (`spelled()`). This is each kind's spelling:

  ("asked", phase, construct, count, destination)
                                          delivered to the DECIDER alone,
                                          before the Chooser is consulted: the
                                          phase it is asked in, the construct
                                          asking, how many picks it wants, and
                                          the zone they land in — None where
                                          the site cannot know that zone before
                                          the choice is made
  ("chose", <rendered value>)             one per pick, delivered to the
                                          decider alone as the pick is made
                                          (`chooser.decide`): perfect recall
                                          of one's own decisions, one record
                                          per pick on every route
  ("announce", actor, <rendered value>)   a decision whose chosen value is
                                          public — a bid, bet, pass, offer
                                          pick, or `choose` result (state
                                          variables are public, so their
                                          decisions are announcements)
  ("move", src_label, src_view, dst_label, dst_view)
                                          what THIS observer learned of a card
                                          transfer through each side's declared
                                          projection: the seen cards' renderings
                                          in `view_of`'s order (identity), a
                                          count (count_only), or None (trivial)
  ("reveal", zone_label, <card>)          a `reveal` names one card in place
                                          (`execute._reveal`). The one event
                                          that is public by construction:
                                          delivered to every player whatever
                                          the zone's declared visibility says
  ("was", variable, slot, <rendering>)   a [[state-delta]]: one State Variable
                                          slot whose rendering changed since
                                          the previous decision node, with the
                                          rendering it had there — None for a
                                          slot not in scope there. The slot is
                                          an indexed variable's key, rendered,
                                          or None for an unindexed one.
                                          Delivered to every player at every
                                          decision node (`state_delta`), before
                                          the `asked`, so a seat's log fixes
                                          the public state it was shown at
                                          every earlier node

Which observer learns what is otherwise driven by the zone declarations alone
(decisions.md "Knowledge, visibility, and the projection model") — no game names
its observers.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
- Assumes: `ZONE_PROJECTIONS` (`stdlib/zones.py`) is the one statement of
  what each zone type shows its owner and every other seat.
- Establishes: each seat's [[observation-log]] is kept by the run, on the
  world (`RuntimeState.observations`): made by `play_game` when the run is
  observed, appended to by `Ctx.observe` alone, and read as a frozen
  snapshot through `logs_of` alone, so every reader of a seat's knowledge
  reads the one log the run kept. An unobserved run keeps none and its
  emitters build no event (`Ctx.observing`). Held by: Unrepresentable to
  the reader for a snapshot's immutability -- `ObservationLog` is a
  bounded, read-only prefix -- resting on the record behind it only
  growing; Derived and Pinned for that, and for who makes, writes and reads
  the aggregate and who calls `logs_of` -- the scrapes of
  tests/test_observation_logs.py, each red under its planted second site.
  Why not higher: `append` is a public method, and which code calls it is
  a fact about the text.
- Establishes: every [[observation-event]] is a member of
  `ObservationEvent`, with its kind's fields; each field holds a value its
  `PAYLOAD_SHAPES` row admits, refused in words when the event is made; and
  a held event cannot change. Held by: Unrepresentable for the kind, the
  arity and the immutability -- the union, each kind's signature, `frozen`
  and `slots` -- and every consumer dispatches over the union; Derived and
  Pinned for the content -- one check, `_Admitted.__post_init__`, run by
  every constructor, and tests/test_observation_payloads.py, whose refusal
  cells redden on deleting it. Why not higher, for the content: a shape is
  a predicate over spellings (a label's form, a card's rendering, a sorted
  group), which no type states.
- Establishes: each kind spells itself as its tag followed by its fields in
  declaration order (`spelled()`), and that spelling, by its `repr`, is
  what the information state embeds (`infostate.render_information_state`).
  Held by: Born-Green Pin, tests/test_observation_spelling.py, the
  spelling of every event a seat is delivered along the whole line of
  every corpus game, red under respelling one kind. That the renderer
  embeds the spelling rather than the dataclass's own `repr` is
  `infostate`'s Contract. Why not higher: a spelling is a format the string
  OpenSpiel keys on carries, not a type.
- Establishes: a decider is told what it is asked, and recalls each of its
  own picks, through one route: `chooser.decide`, the only caller of the
  Chooser, delivers the node's `was` events to every seat, then the
  `asked` to the decider, then one `chose` per pick to the decider alone.
  Held by: Derived and Pinned for the route -- the AST scrape of
  tests/test_asked_event.py::test_the_choke_point_is_the_only_caller_of_the_chooser
  holds the Chooser's callers to `chooser.decide`, and
  tests/test_asked_event.py::test_the_ask_is_derived_in_one_place holds the
  modules naming the `asked` kind; Derived and Pinned for the events --
  tests/test_asked_event.py::test_only_the_route_makes_an_ask_or_a_pick
  holds every construction of an `AskedEvent` or a `ChoseEvent` under
  `cardlang/` to `chooser.decide`. Why not higher: which code reaches the
  Chooser, and which code constructs a kind, are facts about the text,
  which no type holds.
- Establishes: a card transfer reaches each seat through both sides'
  declared projections (`movement`, through `view_of`), and a seat for whom
  both sides are trivial receives no event; every card that lands in a zone
  during play is such a transfer, delivered by the site that lands it,
  `execute.deposit`. Held by: Derived and Pinned for what a seat receives --
  `view_of` is the one reading of a zone's projection, read by `movement`
  and by `infostate`'s zone facts alike, and the per-observer proofs under
  tests/openspiel_ready/ measure it; Derived and Pinned for whether a
  transfer is observed -- `execute.deposit` is the one door a card lands by
  during play and calls `movement` itself, and tests/test_deposit_door.py
  holds the callers of `Zone.add_all` and of `movement` to it, with the
  driver's deck seeding the one other write, which transfers nothing. Why
  not higher: a `Zone` is a public class, so which code writes one is a
  fact about the text.
- Establishes: `view_of` answers the cards, a count, or nothing, one arm
  for each level the engine builds (`ProjectionLevel`), and a zone type can
  declare no other level. Held by: Unrepresentable -- `ZoneVisibility`'s
  columns are `ProjectionLevel`s, and `_projected` is an exhaustive match
  over it ending in `assert_never`, so a level added to the type without an
  arm fails the type check.
- Establishes: a decision value and a State Variable's content each have
  one deterministic spelling (`render`, `render_state_variable`), shared by
  every log and every rendering of a Seat View, and a value outside the
  declared shapes is refused. Held by: Born-Green Pin,
  tests/test_openspiel_infostate.py::test_render_covers_the_declared_value_shapes_and_refuses_the_rest.
  Why not higher: a decision value arrives as `Any` from the Chooser and a
  State Variable as `Any` from its frame, so the dispatch is over runtime
  types.
- Establishes: at every decision node after a run's first, every seat
  receives one `was` per public State Variable slot whose rendering changed
  since the previous node, so its log fixes the public state it was shown
  at every earlier node (ADR-0021). Held by: Unrepresentable for the write
  doors -- `state_delta` diffs the one rendering `public_state` gives, so
  no door that writes a State Variable bypasses it; Derived and Pinned for
  the nodes -- `chooser.decide` calls it before every ask, and the
  choke-point scrape above holds every decision to `chooser.decide`. The
  executed witnesses are tests/test_state_recall.py, one row per write
  door, and
  tests/openspiel_ready/test_ismcts.py::test_a_constructed_world_keeps_the_public_state_a_seat_was_shown,
  red under dropping `state_delta(ctx)` from `chooser.decide`.
- Illegal after: a caller keeping a seat's log of its own, or wrapping one
  in an `ObservationLog`; interpreter code reading a seat's log off the
  world; an event that is not a member of
  `ObservationEvent`, or a field outside its kind's shape; an event spelled other than by
  `spelled()`; a projection spelled beside `view_of`; a card, rather than
  its rendering, in a payload (`_rendered`; issue #666).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, fields
from itertools import islice
from types import MappingProxyType
from typing import Any, ClassVar, Literal, TypeGuard, assert_never, get_args, overload

from cardlang.domains import zone_observer_key
from cardlang.runtime.delegation import CONSTRUCTS
from cardlang.runtime.state import Ctx, RuntimeState
from cardlang.runtime.values import COMPONENT_SETS, Card, Player, build_deck
from cardlang.stdlib.zones import ProjectionLevel, zone_projection


def _is_integer(value: object) -> TypeGuard[int]:
    # `isinstance(True, int)` holds, and neither a seat nor a count is a flag.
    return isinstance(value, int) and not isinstance(value, bool)


# A zone's label as `_label` spells it: the zone's name (the grammar's `NAME`),
# alone or with a family instance's key — a seat, a team, a position index or
# a board cell.
_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[A-Za-z0-9_]+\])?")

# A declared name as the grammar's NAME terminal spells it — a phase's own.
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# The rendering of every card and piece a component set holds.
_CARD_RENDERINGS = frozenset(
    str(card) for name in COMPONENT_SETS for card in build_deck(name)
)


def _is_card_rendering(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and value in _CARD_RENDERINGS


def _is_card_renderings(value: object) -> bool:
    # In the one order `view_of` and `render` sort them into: an identity
    # projection reveals which cards moved, never the order they sat in.
    if not isinstance(value, tuple):
        return False
    renderings = [item for item in value if _is_card_rendering(item)]
    return len(renderings) == len(value) and renderings == sorted(renderings)


# What each payload field shape admits: the alternatives its emitters produce,
# and nothing else. No string is both a label and a card, so a site that hands
# over one in the other's place is refused rather than read.
PAYLOAD_SHAPES: dict[str, Callable[[object], bool]] = {
    # a seat index — the actor of an announcement
    "seat": _is_integer,
    # a zone's label: its name, or `name[key]` for a family instance
    "label": lambda value: isinstance(value, str) and _LABEL.fullmatch(value) is not None,
    # one card, rendered
    "card": _is_card_rendering,
    # what one observer sees of moved cards through a projection (`view_of`):
    # the cards rendered, a count, or nothing
    "view": lambda value: (
        value is None or _is_integer(value) or _is_card_renderings(value)
    ),
    # a decision value as `render` spells it: a string, an integer or flag,
    # or nothing. A decision is one pick, so no value is a group of cards.
    "value": lambda value: value is None or isinstance(value, (str, int)),
    # the phase a decision is asked in, by the name the designer wrote. Never
    # None: a decision asked outside every phase names no stretch of play, and
    # the ask is refused at its choke point rather than sentinelled here.
    "phase": lambda value: isinstance(value, str) and _NAME.fullmatch(value) is not None,
    # the construct asking, one of the closed set the language spells. The
    # type test is load-bearing, not decoration: emission is unfenced, so a
    # site may hand over an unhashable value, and a bare `in` would raise
    # where this table's whole job is to ANSWER.
    "construct": lambda value: isinstance(value, str) and value in CONSTRUCTS,
    # how many picks the decision wants: a count, never a flag and never zero
    "count": lambda value: _is_integer(value) and value > 0,
    # the zone the picks land in, or nothing where the site cannot know it
    # before the choice is made
    "destination": lambda value: (
        value is None or (isinstance(value, str) and _LABEL.fullmatch(value) is not None)
    ),
    # a declared State Variable's name, as the grammar's NAME terminal spells it
    "variable": lambda value: isinstance(value, str) and _NAME.fullmatch(value) is not None,
    # what `render_state_variable` spells — a slot's key, or a slot's content
    # — or nothing: an unindexed variable's slot, or a slot not in scope
    "rendering": lambda value: value is None or isinstance(value, str),
}

# A view as an event carries it: the seen cards' renderings, a count, or nothing.
RenderedView = tuple[str, ...] | int | None


def _shaped(shape: str) -> Any:
    """A field of an Observation Event, carrying the `PAYLOAD_SHAPES` row
    that says what it admits."""
    return field(metadata={"shape": shape})


class _Admitted:
    """What every [[observation-event]] kind shares: its tag, the shape of each
    field, and the check that refuses an event outside them when it is made.

    `KIND` is the tag `spelled()` leads with; `SHAPES` pairs each field, in
    declaration order, with its `PAYLOAD_SHAPES` row.
    """

    __slots__ = ()
    KIND: ClassVar[str]
    SHAPES: ClassVar[tuple[tuple[str, str], ...]]

    def __post_init__(self) -> None:
        for position, (name, shape) in enumerate(self.SHAPES, start=1):
            value = getattr(self, name)
            if not PAYLOAD_SHAPES[shape](value):
                # Unreachable from a game description: every value an emission
                # site hands over is rendered by this module first, and the
                # payload registry (`PAYLOAD_SHAPES`) is what each field admits.
                raise AssertionError(
                    f"field {position} of a {self.KIND!r} event is a {shape}, "
                    f"not {value!r}: an emission site builds only the events "
                    f"the payload registry admits"
                )


@dataclass(frozen=True, slots=True)
class AskedEvent(_Admitted):
    """The decision a seat is asked, delivered to the [[decider]] alone before
    the Chooser is consulted; `destination` is None where the site cannot know
    the zone the picks land in before the choice is made."""

    KIND: ClassVar[str] = "asked"
    phase: str = _shaped("phase")
    construct: str = _shaped("construct")
    count: int = _shaped("count")
    destination: str | None = _shaped("destination")

    def spelled(self) -> tuple[str, str, str, int, str | None]:
        return ("asked", self.phase, self.construct, self.count, self.destination)


@dataclass(frozen=True, slots=True)
class ChoseEvent(_Admitted):
    """One pick, delivered to the decider alone as it is made."""

    KIND: ClassVar[str] = "chose"
    value: str | int | None = _shaped("value")

    def spelled(self) -> tuple[str, str | int | None]:
        return ("chose", self.value)


@dataclass(frozen=True, slots=True)
class AnnounceEvent(_Admitted):
    """A decision whose chosen value is public, delivered to every seat."""

    KIND: ClassVar[str] = "announce"
    seat: int = _shaped("seat")
    value: str | int | None = _shaped("value")

    def spelled(self) -> tuple[str, int, str | int | None]:
        return ("announce", self.seat, self.value)


@dataclass(frozen=True, slots=True)
class MovementEvent(_Admitted):
    """What one seat learned of a card transfer through each side's declared
    projection."""

    KIND: ClassVar[str] = "move"
    source: str = _shaped("label")
    source_view: RenderedView = _shaped("view")
    destination: str = _shaped("label")
    destination_view: RenderedView = _shaped("view")

    def spelled(self) -> tuple[str, str, RenderedView, str, RenderedView]:
        return ("move", self.source, self.source_view, self.destination, self.destination_view)


@dataclass(frozen=True, slots=True)
class RevealEvent(_Admitted):
    """One card named in place, delivered to every seat whatever the zone's
    declared visibility."""

    KIND: ClassVar[str] = "reveal"
    zone: str = _shaped("label")
    card: str = _shaped("card")

    def spelled(self) -> tuple[str, str, str]:
        return ("reveal", self.zone, self.card)


@dataclass(frozen=True, slots=True)
class WasEvent(_Admitted):
    """One slot of a [[state-delta]]: the rendering a State Variable slot had at
    the previous decision node, None for a slot not then in scope."""

    KIND: ClassVar[str] = "was"
    variable: str = _shaped("variable")
    slot: str | None = _shaped("rendering")
    shown: str | None = _shaped("rendering")

    def spelled(self) -> tuple[str, str, str | None, str | None]:
        return ("was", self.variable, self.slot, self.shown)


# The closed set of [[observation-event]] kinds (closed-domain completeness,
# decisions.md): a consumer dispatches over it exhaustively, ending in
# `assert_never`. A new kind is a member here first. Each kind spells itself as
# the tuple the information state embeds (`spelled`), so the string OpenSpiel
# keys on never meets a dataclass's own `repr`.
ObservationEvent = AskedEvent | ChoseEvent | AnnounceEvent | MovementEvent | RevealEvent | WasEvent

EVENT_KINDS: dict[str, type[ObservationEvent]] = {
    kind.KIND: kind for kind in get_args(ObservationEvent)
}

for _kind in EVENT_KINDS.values():
    _kind.SHAPES = tuple((f.name, f.metadata["shape"]) for f in fields(_kind))

# Each kind's field shapes after its tag, in `spelled()` order: derived from
# the kinds, never stated beside them.
EVENT_PAYLOADS: dict[str, tuple[str, ...]] = {
    kind: tuple(shape for _name, shape in cls.SHAPES) for kind, cls in EVENT_KINDS.items()
}


class ObservationLog(Sequence[ObservationEvent]):
    """One seat's [[observation-log]] as it stood when it was taken: the events
    delivered to the seat, in delivery order. A bounded prefix of the seat's
    record in `ObservationLogs`, which is only ever appended to, so taking one
    copies nothing and no later delivery is part of it."""

    __slots__ = ("_events", "_length")

    def __init__(self, events: list[ObservationEvent], length: int) -> None:
        self._events = events
        self._length = length

    def __len__(self) -> int:
        return self._length

    @overload
    def __getitem__(self, index: int) -> ObservationEvent: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[ObservationEvent, ...]: ...

    def __getitem__(self, index: int | slice) -> ObservationEvent | tuple[ObservationEvent, ...]:
        if isinstance(index, slice):
            return tuple(self._events[: self._length][index])
        position = index + self._length if index < 0 else index
        if not 0 <= position < self._length:
            raise IndexError(f"event {index} of a log of {self._length}")
        return self._events[position]

    def __iter__(self) -> Iterator[ObservationEvent]:
        return islice(self._events, self._length)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (ObservationLog, tuple)):
            return NotImplemented
        return len(other) == self._length and all(a == b for a, b in zip(self, other))

    def __hash__(self) -> int:
        return hash(tuple(self))

    def __repr__(self) -> str:
        return f"ObservationLog({tuple(self)!r})"


class ObservationLogs:
    """The table's [[observation-log]]s, one per seat: what `Ctx.observe`
    delivers, appended in delivery order, read as frozen `snapshot`s.

    `play_game` makes it when the run is observed and keeps it on the
    [[world]] (`RuntimeState.observations`); `listener`, when given, hears each
    event as it is appended, which is the one record of the order across
    seats."""

    __slots__ = ("_events", "_listener")

    def __init__(
        self,
        seats: Iterable[Player],
        listener: Callable[[Player, ObservationEvent], None] | None = None,
    ) -> None:
        self._events: dict[Player, list[ObservationEvent]] = {seat: [] for seat in seats}
        self._listener = listener

    def append(self, player: Player, event: ObservationEvent) -> None:
        self._events[player].append(event)
        if self._listener is not None:
            self._listener(player, event)

    def snapshot(self) -> Mapping[Player, ObservationLog]:
        """Every seat's log as it stands now."""
        return MappingProxyType(
            {seat: ObservationLog(events, len(events)) for seat, events in self._events.items()}
        )


def logs_of(rs: RuntimeState) -> Mapping[Player, ObservationLog]:
    """Every seat's log as it stands, off the world of an observed run."""
    # Shadow Guard behind `play_game`, which keeps the logs on the world of
    # every run it is asked to observe: a reader here asked for them.
    assert rs.observations is not None, "the logs of a run that was not observed"
    return rs.observations.snapshot()


# What the seats other than the deciding seat hear of a pick, by the construct
# asking (`delegation.CONSTRUCTS`, the word an `asked` event carries):
# "announced", every seat hears every pick (`announce`); "moved", no seat hears
# any, and the others learn of a pick only through the movement it makes, as
# the zones' projections show it; None where neither holds of every pick (a
# climbing round announces a pass, a decline, an announcement and a wildcard's
# rank, and shows a play through its movement), so a reader says it is settled
# in play. The deciding seat itself is always asked and remembers each pick
# (`chooser.decide`). Read by a Checker Query (`cardlang.query`). The rung,
# recorded: no emission site reads this table (the announcing sites are
# `execute._offer`, `evaluate._choose` and the climbing form's), so it is a
# Pin, held row by row to every pick every registered game makes by
# tests/test_query_seats.py; making it the emitters' own is issue #1111.
PICK_SHOWN: dict[str, Literal["announced", "moved"] | None] = {
    "transfer": "moved",
    "joint": "moved",
    "simultaneous": "moved",
    "offer": "announced",
    "choose": "announced",
    "trick": "moved",
    "climb": None,
}


def render_candidate(name: str, param: Any) -> str:
    """Render a `(move_type, param)` candidate: the bare name (nullary), a
    comma-joined tuple (a multi-parameter move — one rendering per value), or
    `name(param)` (a single parameter). Shared by `render` (below) and
    `cardlang.openspiel.encoding.ActionSpace.to_string`, which decode the same
    `(name, param)` shape from two different value spaces (a live candidate vs.
    a resolved action id) but render it identically."""
    if param is None:
        return name
    if isinstance(param, tuple):  # a multi-parameter move: render each value
        return f"{name}(" + ",".join(str(v) for v in param) + ")"
    return f"{name}({param})"


def render_play(kind: str, cards: Any, wild: int | None) -> str:
    """Render a combination play: its kind, its cards, and — when a wildcard
    among them stands for a rank — that rank's value after `@`. Shared by
    `render` (a live play) and `ActionSpace.to_string` (a decoded id), which
    must spell the same play identically."""
    text = f"{kind}[" + ",".join(sorted(str(c) for c in cards)) + "]"
    return text if wild is None else f"{text}@{wild}"


def render(value: Any) -> Any:
    """A deterministic, readable rendering of a decision value."""
    if isinstance(value, Card):
        return str(value)
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        name, param = value  # a (move_type, param) offering candidate
        return render_candidate(name, param)
    cards = getattr(value, "cards", None)
    if cards is not None:  # a combination play (climb engines)
        return render_play(getattr(value, "kind", "combo"), cards, getattr(value, "wild", None))
    if isinstance(value, (int, str)) or value is None:
        return value  # int/bool (a choose, a flag), str (a move name / "pass")
    # Closed-domain completeness: a decision value outside the declared
    # shapes has no deterministic rendering — fail loudly rather than pass
    # an unstable repr into every observer's information state.
    raise AssertionError(
        f"decision value of type {type(value).__name__} has no declared "
        f"rendering in observe.render — add it deliberately"
    )


def announce(ctx: Ctx, actor: Player, value: Any) -> None:
    """A public decision: every player hears (actor, what)."""
    if not ctx.observing:
        return
    for p in ctx.rs.seating.players:
        ctx.observe(p, AnnounceEvent(actor, render(value)))


def render_state_variable(value: Any) -> str:
    """A State Variable's content, spelled canonically: the one spelling every
    rendering of a Seat View, and every State Delta, gives it."""
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda kv: repr(kv[0]))
        return "{" + ",".join(f"{k}:{render_state_variable(v)}" for k, v in items) + "}"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "[" + ",".join(sorted(render_state_variable(v) for v in value)) + "]"
    if isinstance(value, (int, str, Card)) or value is None:
        return str(value)
    # Closed-domain completeness: a state value outside the declared shapes
    # has no deterministic rendering — fail loudly rather than embed an
    # unstable repr in the information state (determinism is a certified
    # property; see open-questions/structural-infoset-proofs.md).
    raise AssertionError(
        f"state value of type {type(value).__name__} has no declared "
        f"rendering in information_state — add it deliberately"
    )


def public_state(rs: RuntimeState) -> dict[str, Any]:
    """The State Variables in scope, as every seat is shown them: each scope
    frame merged, later frames shadowing earlier (phase-local over game).

    The one reading of the public state. The information state renders it
    and `state_delta` diffs it, so what a seat is shown and what its log
    records of a change are one definition. The values are the frames' own
    objects: a caller copies before keeping one.
    """
    merged: dict[str, Any] = {}
    for frame in rs.frames:
        merged.update(frame)
    return merged


# One State Variable slot: the variable's name, and an indexed variable's key
# as `render_state_variable` spells it (None for an unindexed variable).
Slot = tuple[str, str | None]


def shown_slots(rs: RuntimeState) -> dict[Slot, str]:
    """Every slot of the public state, rendered. An indexed variable is one
    slot per key, so a write to one key is one change, whichever door wrote it
    — an indexed assignment changes its slot in place."""
    slots: dict[Slot, str] = {}
    for name, value in public_state(rs).items():
        if isinstance(value, Mapping):
            for key, item in value.items():
                slots[(name, render_state_variable(key))] = render_state_variable(item)
        else:
            slots[(name, None)] = render_state_variable(value)
    return slots


def state_delta(ctx: Ctx) -> None:
    """Deliver the [[state-delta]] of this decision node to every seat: one
    `was` event per slot whose rendering differs from the previous decision
    node's, carrying the rendering it had there.

    A seat is shown the public state at every decision node, so this is what
    makes its log fix every earlier node's public state from the current one,
    whichever write door changed a slot between them, and whatever chose the
    write (decisions.md "Hidden information lives only in zones; state is
    public"). A slot written and overwritten between two nodes was shown at
    neither, and no event names it. The first decision node of a run has no
    earlier one and delivers nothing.

    Called by `chooser.decide` alone, before the `asked`; the snapshot it
    keeps (`RuntimeState.shown_slots`) is the previous node's.
    """
    if not ctx.observing:
        return
    rs = ctx.rs
    now = shown_slots(rs)
    before, rs.shown_slots = rs.shown_slots, now
    if before is None:
        return
    changed = sorted(
        (slot for slot in before.keys() | now.keys() if before.get(slot) != now.get(slot)),
        key=lambda slot: (slot[0], slot[1] is not None, slot[1] or ""),
    )
    for name, key in changed:
        event = WasEvent(name, key, before.get((name, key)))
        for p in rs.seating.players:
            ctx.observe(p, event)


def held(index: str | None, position_domains: Mapping[str, Any]) -> TypeGuard[str]:
    """Whether a zone indexed by `index` has a holder among the observers: a
    seat or a team family does, a single zone or a family over a Position
    Domain does not (no observer IS a column), so every observer sees it
    through its type's `others` column."""
    return index is not None and index not in position_domains


def _is_owner(
    rs: RuntimeState, zone_name: str, key: Player | str | None, observer: Player
) -> bool:
    index = rs.zones.zone_index[zone_name]
    if key is None or not held(index, rs.position_domains):
        return False
    # The observer owns the family instance whose key is their own member in
    # the index domain — their seat, their team — read from the domain table's
    # `zone_key_of` column rather than an `== "team"` re-spelling (which
    # treated every other role as player-keyed, silently). Ownership drives
    # per-observer projection, so this cell is info-set load-bearing.
    return zone_observer_key(index, rs, observer) == key


# What one zone projects to one observer: the cards themselves, a bare count, or
# nothing at all — the whole domain a reader of a projection has to carry.
ZoneView = tuple[Card, ...] | int | None


def view_of(
    rs: RuntimeState,
    zone_name: str,
    key: Player | str | None,
    observer: Player,
    cards: Any,
) -> ZoneView:
    """What `observer` sees of `cards` at this zone, per its declared projection.

    Seen cards come in one canonical order, by their rendering. An identity
    projection reveals which cards a zone holds and never the order they sit in
    (decisions.md "Projections: what visibility controls"), so no reader of a
    view meets the storage order.
    """
    return _projected(projection_for(rs, zone_name, key, observer), cards)


def projection_for(
    rs: RuntimeState, zone_name: str, key: Player | str | None, observer: Player
) -> ProjectionLevel:
    """The projection `observer` sees this zone instance through: its type's
    owner column for the instance's holder, its others column for every other
    observer."""
    return zone_projection(rs.zones.zone_type[zone_name], _is_owner(rs, zone_name, key, observer))


def _projected(proj: ProjectionLevel, cards: Any) -> ZoneView:
    match proj:
        case "identity":
            return tuple(sorted(cards, key=str))
        case "count_only":
            return len(cards)
        case "trivial":
            return None
        case _ as unbuilt:
            assert_never(unbuilt)


def _label(zone_name: str, key: Player | str | None) -> str:
    return zone_name if key is None else f"{zone_name}[{key}]"


def movement(
    ctx: Ctx,
    src: tuple[str, Player | str | None],
    dst: tuple[str, Player | str | None],
    cards: Any,
) -> None:
    """Emit a card transfer to every observer through both sides' projections
    (decisions.md "Observation events"). Observers for whom both sides are
    trivial learn nothing and get no event."""
    if not ctx.observing or not cards:
        return
    for p in ctx.rs.seating.players:
        src_proj = projection_for(ctx.rs, src[0], src[1], p)
        dst_proj = projection_for(ctx.rs, dst[0], dst[1], p)
        if not movement_seen(src_proj, dst_proj):
            continue
        src_view = _projected(src_proj, cards)
        dst_view = _projected(dst_proj, cards)
        ctx.observe(
            p,
            MovementEvent(_label(*src), _rendered(src_view), _label(*dst), _rendered(dst_view)),
        )


def movement_seen(source_projection: str, destination_projection: str) -> bool:
    """Whether an observer seeing a movement's source and destination through
    these projections learns of the movement at all: not when both are
    `trivial`, which shows nothing. The one rule `movement` emits by, and the
    one a Checker Query reads (`cardlang.query`)."""
    return not (source_projection == "trivial" and destination_projection == "trivial")


def _rendered(view: ZoneView) -> tuple[str, ...] | int | None:
    """A view as an event carries it: the seen cards by their renderings.

    The information state spells the observation log by each event's
    spelling (`spelled()`), so a card in a payload would change the string OpenSpiel keys on. A payload
    therefore stays strings and counts, and carrying the cards themselves is a
    change of its own under the goldens' full width (issue #666). A reader of
    the log meets a card's rendering, never the card, and derives no fact by
    parsing one.
    """
    return tuple(str(card) for card in view) if isinstance(view, tuple) else view
