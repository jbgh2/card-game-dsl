"""Per-observer observation emission — the projection substrate.

Every event is a plain, deterministic, human-readable tuple. The vocabulary:

  ("chose", <rendered value>)             delivered to the actor only, at the
                                          moment of the chooser draw (perfect
                                          recall of one's own decisions)
  ("announce", actor, <rendered value>)   a public vocabulary decision — a bid,
                                          bet, pass, offer pick, or `choose`
                                          result (state variables are public,
                                          so their decisions are announcements)
  ("move", src_label, src_view, dst_label, dst_view)
                                          what THIS observer learned of a card
                                          transfer through each side's declared
                                          projection: a sorted tuple of card
                                          strings (identity), a count
                                          (count_only), or None (trivial)

Emission is driven by the zone declarations alone (decisions.md "Knowledge,
visibility, and the projection model") — no game names its observers.
"""

from __future__ import annotations

from typing import Any

from cardlang.runtime.state import Ctx, RuntimeState
from cardlang.runtime.values import Card, Player
from cardlang.stdlib.zones import zone_projection


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


def _is_owner(rs: RuntimeState, zone_name: str, key: Player | None, observer: Player) -> bool:
    index = rs.zones.zone_index[zone_name]
    if key is None or index is None:
        return False
    if index == "team":
        return rs.team_of.get(observer) == key
    return observer == key


def view_of(
    rs: RuntimeState,
    zone_name: str,
    key: Player | None,
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
    raise AssertionError(f"projection '{proj}' has no emission rule yet")


def _label(zone_name: str, key: Player | None) -> str:
    return zone_name if key is None else f"{zone_name}[{key}]"


def movement(
    ctx: Ctx,
    src: tuple[str, Player | None],
    dst: tuple[str, Player | None],
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
