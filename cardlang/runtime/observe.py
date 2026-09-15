"""Per-observer [[observation-event]] emission — the [[projection]] substrate.

Every event is a plain, deterministic, human-readable tuple. The kinds, and the
shape of every field each kind carries, are `EVENT_PAYLOADS` below — the closed
set and the authority, with `PAYLOAD_SHAPES` saying what each field shape
admits. This is what each carries:

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
                                          projection: a sorted tuple of card
                                          strings (identity), a count
                                          (count_only), or None (trivial)
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

from collections.abc import Callable
from typing import Any

from cardlang.domains import zone_observer_key
from cardlang.runtime.state import Ctx, RuntimeState
from cardlang.runtime.values import Card, Player
from cardlang.stdlib.zones import zone_projection


def _is_integer(value: object) -> bool:
    # `isinstance(True, int)` holds, and neither a seat nor a count is a flag.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_card_renderings(value: object) -> bool:
    return isinstance(value, tuple) and all(isinstance(item, str) for item in value)


# What each payload field shape admits: the alternatives its emitters produce,
# and nothing else.
PAYLOAD_SHAPES: dict[str, Callable[[object], bool]] = {
    # a seat index — the actor of an announcement
    "seat": _is_integer,
    # a zone's label: its name, or `name[key]` for a family instance
    "label": lambda value: isinstance(value, str),
    # one card, rendered
    "card": lambda value: isinstance(value, str),
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


def view_of(
    rs: RuntimeState,
    zone_name: str,
    key: Player | str | None,
    observer: Player,
    cards: Any,
) -> tuple[str, ...] | int | None:
    """What `observer` sees of `cards` at this zone, per its declared projection."""
    proj = zone_projection(
        rs.zones.zone_type[zone_name], _is_owner(rs, zone_name, key, observer)
    )
    if proj == "identity":
        return tuple(sorted(str(c) for c in cards))
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
        ctx.observe(p, ("move", _label(*src), src_view, _label(*dst), dst_view))
