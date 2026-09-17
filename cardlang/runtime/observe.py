"""Per-observer [[observation-event]] emission — the [[projection]] substrate.

Every event is a plain, deterministic, human-readable tuple. The kinds, and the
shape of every field each kind carries, are `EVENT_PAYLOADS` below — the closed
set and the authority, with `PAYLOAD_SHAPES` saying what each field shape
admits. This is what each carries:

  ("asked", phase, construct, count, destination)
                                          delivered to the DECIDER alone,
                                          before the Chooser is consulted: the
                                          phase it is asked in, the construct
                                          asking, how many picks it wants, and
                                          the zone they land in — None where
                                          the site cannot know that zone before
                                          the choice is made
  ("chose", <rendered value>)             delivered to the actor only, at the
                                          moment of the chooser draw (perfect
                                          recall of one's own decisions)
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

Which observer learns what is otherwise driven by the zone declarations alone
(decisions.md "Knowledge, visibility, and the projection model") — no game names
its observers.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, TypeGuard

from cardlang.domains import zone_observer_key
from cardlang.runtime.delegation import CONSTRUCTS
from cardlang.runtime.state import Ctx, RuntimeState
from cardlang.runtime.values import COMPONENT_SETS, Card, Player, build_deck
from cardlang.stdlib.zones import zone_projection


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
    # nothing, or a multi-card selection
    "value": lambda value: (
        value is None or isinstance(value, (str, int)) or _is_card_renderings(value)
    ),
    # the phase a decision is asked in, by the name the designer wrote. Never
    # None: a decision asked outside every phase names no stretch of play, and
    # the ask is refused at its choke point rather than sentinelled here.
    "phase": lambda value: isinstance(value, str) and _NAME.fullmatch(value) is not None,
    # the construct asking, one of the closed set the language spells
    "construct": lambda value: value in CONSTRUCTS,
    # how many picks the decision wants: a count, never a flag and never zero
    "count": lambda value: _is_integer(value) and value > 0,
    # the zone the picks land in, or nothing where the site cannot know it
    # before the choice is made
    "destination": lambda value: (
        value is None or (isinstance(value, str) and _LABEL.fullmatch(value) is not None)
    ),
}

# The closed set of observation-event kinds, each with the shape of every field
# it carries after its tag (closed-domain completeness, decisions.md). Emission
# sites: `choice`/`announce`/`movement` below, `chooser.sequential_decisions`'
# per-pick `chose`, and `execute._reveal`. A new kind, or a new field on one, is
# declared here first. Pinned by tests/test_observation_payloads.py, which plays
# every registered game with an observer installed and holds every delivered
# event to its row.
#
# The rung, recorded: the log stays tagged tuples and a consumer refuses what
# the table does not describe (`payload_refusal`), rather than a typed event
# union every site constructs — each tuple's `repr` is the information state's
# own substrate, so typing the log is a change of its own under the goldens'
# full width. Emission is therefore unfenced: `Ctx.observe` delivers whatever
# a site hands it.
EVENT_PAYLOADS: dict[str, tuple[str, ...]] = {
    "asked": ("phase", "construct", "count", "destination"),
    "chose": ("value",),
    "announce": ("seat", "value"),
    "move": ("label", "view", "label", "view"),
    "reveal": ("label", "card"),
}


def payload_refusal(event: object) -> str | None:
    """Why `event` is not an observation event `EVENT_PAYLOADS` describes, or
    None when it is one.

    For the consumers that must not read an event the table does not describe —
    a rendering, a proof that perturbs events field by field — because nothing
    downstream has a declared reading for one.
    """
    if not isinstance(event, tuple) or not event or not isinstance(event[0], str):
        return (
            f"{event!r} is not an observation event: an event is a tuple whose "
            "first item names its kind"
        )
    kind, fields = event[0], event[1:]
    row = EVENT_PAYLOADS.get(kind)
    if row is None:
        return (
            f"observation event kind {kind!r} is not declared; the kinds are "
            f"{', '.join(sorted(EVENT_PAYLOADS))}"
        )
    if len(fields) != len(row):
        return (
            f"a {kind!r} event carries {len(row)} field(s) ({', '.join(row)}), "
            f"not {len(fields)}: {event!r}"
        )
    for position, (shape, value) in enumerate(zip(row, fields), start=1):
        if not PAYLOAD_SHAPES[shape](value):
            return f"field {position} of a {kind!r} event is a {shape}, not {value!r}"
    return None


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


def render(value: Any) -> Any:
    """A deterministic, readable rendering of a decision value."""
    if isinstance(value, Card):
        return str(value)
    if isinstance(value, (list,)):  # a multi-card selection (simultaneous pass)
        return tuple(sorted(str(c) for c in value))
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        name, param = value  # a (move_type, param) auction/betting candidate
        return render_candidate(name, param)
    cards = getattr(value, "cards", None)
    if cards is not None:  # a combination play (climb engines)
        kind = getattr(value, "kind", "combo")
        return f"{kind}[" + ",".join(sorted(str(c) for c in cards)) + "]"
    if isinstance(value, (int, str)) or value is None:
        return value  # int/bool (a choose, a flag), str (a move name / "pass")
    # Closed-domain completeness: a decision value outside the declared
    # shapes has no deterministic rendering — fail loudly rather than pass
    # an unstable repr into every observer's information state.
    raise AssertionError(
        f"decision value of type {type(value).__name__} has no declared "
        f"rendering in observe.render — add it deliberately"
    )


def choice(ctx: Ctx, actor: Player, value: Any) -> None:
    """The actor observes their own decision at the draw."""
    ctx.observe(actor, ("chose", render(value)))


def announce(ctx: Ctx, actor: Player, value: Any) -> None:
    """A public decision: every player hears (actor, what)."""
    if ctx.observer is None:
        return
    for p in ctx.rs.seating.players:
        ctx.observe(p, ("announce", actor, render(value)))


def _is_owner(
    rs: RuntimeState, zone_name: str, key: Player | str | None, observer: Player
) -> bool:
    index = rs.zones.zone_index[zone_name]
    if key is None or index is None:
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
    proj = zone_projection(
        rs.zones.zone_type[zone_name], _is_owner(rs, zone_name, key, observer)
    )
    if proj == "identity":
        return tuple(sorted(cards, key=str))
    if proj == "count_only":
        return len(cards)
    if proj == "trivial":
        return None
    # Exhaustive over the projection names ZONE_PROJECTIONS can emit — a new
    # projection must be implemented here deliberately, never rendered ad hoc.
    raise AssertionError(f"projection '{proj}' has no declared emission rule")


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
    if ctx.observer is None or not cards:
        return
    for p in ctx.rs.seating.players:
        src_view = view_of(ctx.rs, src[0], src[1], p, cards)
        dst_view = view_of(ctx.rs, dst[0], dst[1], p, cards)
        if src_view is None and dst_view is None:
            continue
        ctx.observe(
            p,
            ("move", _label(*src), _rendered(src_view), _label(*dst), _rendered(dst_view)),
        )


def _rendered(view: ZoneView) -> tuple[str, ...] | int | None:
    """A view as an event carries it: the seen cards by their renderings.

    The information state spells the observation log as each event's `repr`,
    so a card in a payload would change the string OpenSpiel keys on. A payload
    therefore stays strings and counts, and carrying the cards themselves is a
    change of its own under the goldens' full width (issue #666). A reader of
    the log meets a card's rendering, never the card, and derives no fact by
    parsing one.
    """
    return tuple(str(card) for card in view) if isinstance(view, tuple) else view
