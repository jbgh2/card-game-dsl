"""The general information state (perfect recall, per player) — derived, not
hand-authored.

A player's information state is a pure function of (a) their view of every zone
through the [[projection]] its declared library type gives them, (b) the declared
[[state-variable]]s — public by convention: hidden information lives only in
zones (SP1 spec, "State variables are public"), and (c) their accumulated
per-observer [[observation-log]] (perfect recall; a `Muck`'s contents are trivial
going forward while prior observations persist in the log). The string is
deterministic and human-readable.

The derivation and the rendering are separate, and the separation is the
point. `derive` answers what a seat knows; `render_information_state` turns
that answer into the string OpenSpiel keys on. A renderer takes the derived
[[seat-view]] and never the live [[world]], so a second rendering — a frame a
person reads, a policy's input — consumes the same facts by construction
rather than deriving them again beside this one. Two derivations of a seat's
knowledge would be two implementations of the property this project is built
to guarantee, kept equal by review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cardlang.runtime.observe import view_of
from cardlang.runtime.state import RuntimeState, StructValue
from cardlang.runtime.values import Card


def _render(value: Any) -> str:
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: repr(kv[0]))
        return "{" + ",".join(f"{k}:{_render(v)}" for k, v in items) + "}"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "[" + ",".join(sorted(_render(v) for v in value)) + "]"
    if isinstance(value, StructValue):  # canonical: sorted declared fields
        fields = ",".join(f"{k}:{_render(v)}" for k, v in sorted(value.fields.items()))
        return f"{value.type_name}{{{fields}}}"
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


# What one zone projects to one observer: `view_of`'s three answers, which are
# the whole domain a renderer has to carry — card identities, a bare count, or
# nothing at all.
ZoneView = tuple[str, ...] | int | None


@dataclass(frozen=True)
class SeatView:
    """Everything one seat knows at one position, and nothing else.

    The value has no hidden fields, so "this cannot leak" is a property of the
    type rather than a claim about the code that builds it: a renderer holding
    a SeatView has no route to another seat's zones, because the route is not
    in its hands.

    Every field is ordered as it is rendered, so the ordering decisions live at
    the one site that makes them.
    """

    player: int
    zones: tuple[tuple[str, ZoneView], ...]
    state: tuple[tuple[str, Any], ...]
    obs_log: tuple[tuple[Any, ...], ...]


def _zone_facts(rs: RuntimeState, player: int) -> tuple[tuple[str, ZoneView], ...]:
    def fact(name: str, key: Any) -> tuple[str, ZoneView]:
        zone = rs.zones.single(name) if key is None else rs.zones.instance(name, key)
        label = name if key is None else f"{name}[{key}]"
        return label, view_of(rs, name, key, player, zone.cards)

    return tuple(
        [fact(name, None) for name in sorted(rs.zones.singles)]
        + [
            fact(name, key)
            for name in sorted(rs.zones.families)
            for key in sorted(rs.zones.families[name])
        ]
    )


def derive(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> SeatView:
    """What `player` knows at this position: zones through their projections,
    the public state variables, and their own observation log."""
    merged: dict[str, Any] = {}
    for frame in rs.frames:  # later frames shadow earlier (phase-local over game)
        merged.update(frame)
    return SeatView(
        player=player,
        zones=_zone_facts(rs, player),
        state=tuple(sorted(merged.items())),
        obs_log=tuple(obs_log),
    )


def _zone_line(label: str, view: ZoneView) -> str:
    if view is None:
        return f"{label}=?"
    if isinstance(view, int):
        return f"{label}=#{view}"
    return f"{label}=[" + ",".join(view) + "]"


def render_information_state(view: SeatView) -> str:
    """The seat's knowledge as the string OpenSpiel keys on."""
    zones = ";".join(_zone_line(label, zone) for label, zone in view.zones)
    state_vars = ";".join(f"{k}={_render(v)}" for k, v in view.state)
    obs = ";".join(repr(e) for e in view.obs_log)
    return f"P{view.player}|" + zones + f"|state:{state_vars}|obs:{obs}"


def information_state(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> str:
    return render_information_state(derive(player, rs, obs_log))
