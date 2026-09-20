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

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from cardlang.runtime.observe import ZoneView, view_of
from cardlang.runtime.reads import deep_freeze
from cardlang.runtime.state import RuntimeState, StructValue
from cardlang.runtime.values import Card


def render_state_variable(value: Any) -> str:
    """A State Variable's content, spelled canonically: the one spelling every
    rendering of a Seat View gives it."""
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda kv: repr(kv[0]))
        return "{" + ",".join(f"{k}:{render_state_variable(v)}" for k, v in items) + "}"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "[" + ",".join(sorted(render_state_variable(v) for v in value)) + "]"
    if isinstance(value, StructValue):  # canonical: sorted declared fields
        fields = ",".join(
            f"{k}:{render_state_variable(v)}" for k, v in sorted(value.fields.items())
        )
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


@dataclass(frozen=True)
class SeatView:
    """Everything one seat knows at one position, and nothing else.

    The value has no hidden fields, so "this cannot leak" is a property of the
    type rather than a claim about the code that builds it: a holder has no
    route to another seat's zones, because the route is not in its hands.

    Not leaking and not aliasing are different guarantees, and only the first
    is the type's. A view built straight off the world would hold the frames'
    live dicts and the zones' own cards; `derive` is the constructor that
    snapshots, and the one whose result is safe to keep.

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


def _facts(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> SeatView:
    """The derivation, over the live world.

    Private, and the privacy is the invariant: the state values here are the
    frames' own objects, so this view is safe only while it cannot outlive the
    call that made it. The one caller that renders immediately uses it; the one
    that hands a view out takes a snapshot first. Nothing else may.
    """
    if isinstance(player, bool) or player not in rs.seating.players:
        # The projection would answer for any integer — every zone through a
        # non-owner's view — and the result would read as some seat's view. A
        # flag passes the membership test, since `True == 1`, and would show
        # that seat's private zones under a name no seat has.
        raise AssertionError(
            f"no seat {player!r} at this table: a seat view is derived for one "
            f"of seats 0..{len(rs.seating.players) - 1}"
        )
    merged: dict[str, Any] = {}
    for frame in rs.frames:  # later frames shadow earlier (phase-local over game)
        merged.update(frame)
    return SeatView(
        player=player,
        zones=_zone_facts(rs, player),
        state=tuple(sorted(merged.items())),
        obs_log=tuple(obs_log),
    )


def derive(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> SeatView:
    """What `player` knows at this position, as a value safe to keep.

    A snapshot, not a window. An indexed state variable is a live
    `{player: value}` dict on the frame, and a seen zone's cards are the
    engine's own card values, so a view over either would keep reading the
    world as the world moved on, and its holder could write through into
    engine state — through a frozen card too, whose fields `object.__setattr__`
    still reaches. `frozen=True` guards the view's fields, never what they point
    at; `deep_freeze` owns that class (`runtime/reads.py`) and rebuilds every
    level.

    What it guarantees is immutability, not renderability: it admits shapes
    `render_state_variable` has no spelling for, so a view holding one derives
    here and is refused where it is rendered.

    The observation log is not copied: every field shape `EVENT_PAYLOADS`
    declares is immutable, and emission is not fenced against a payload outside
    them (issue #638).

    Copying is why this is separate from `_facts`: the rendering path consumes
    its view before it returns, and has no use for a snapshot.
    """
    live = _facts(player, rs, obs_log)
    return replace(
        live,
        zones=tuple((label, deep_freeze(zone)) for label, zone in live.zones),
        state=tuple((k, deep_freeze(v)) for k, v in live.state),
    )


@dataclass(frozen=True)
class Ask:
    """The last question put to a seat: the phase it was asked in, the
    construct asking, how many picks it wants, and the zone they land in where
    the site knew it before the choice.

    How far THROUGH the call the seat is, is deliberately not a field. One
    Chooser call is `count` decisions of the game tree, but the `chose` events
    that would count them are route-dependent — a native playout emits one
    aggregate for the whole call while a replayed one emits a per-pick event
    too — so a progress count read off the log answers differently on the two
    routes for the same completed decision. A seat's position within a call is
    the caller's to track until the log says it unambiguously (issue #592).
    """

    phase: str
    construct: str
    count: int
    destination: str | None


def current_ask(view: SeatView) -> Ask | None:
    """The last question put to `view`'s seat, or None before it has been asked
    anything.

    At a decision point — where a [[seat-policy]] is asked, which is every
    position one is handed a view — the last question IS the live one, because
    the ask is emitted before the Chooser is consulted. Away from one, on a
    stored or terminal view, it is the last question the seat was put and not a
    claim that the seat is still answering it: the log carries no completion
    marker, so this reports what was asked rather than whether it is over.

    The ONE reading of the ask. A consumer wanting to know which decision it is
    answering — a Seat Policy, a person's frame, a listing of a game's
    decisions — reads it here rather than scanning the log beside this, because
    a second reading of a seat's knowledge is a second implementation of the
    property the language exists to guarantee (this module's own contract).
    """
    for event in reversed(view.obs_log):
        if event and event[0] == "asked":
            _kind, phase, construct, count, destination = event
            return Ask(phase, construct, count, destination)
    return None


def _zone_line(label: str, view: ZoneView) -> str:
    if view is None:
        return f"{label}=?"
    if isinstance(view, int) and not isinstance(view, bool):
        return f"{label}=#{view}"
    if isinstance(view, tuple) and all(isinstance(card, Card) for card in view):
        return f"{label}=[" + ",".join(str(card) for card in view) + "]"
    # Closed-domain completeness: `view_of` answers cards, a count, or nothing,
    # and another shape spelled as one of those would read as a projection
    # that never happened.
    raise AssertionError(
        f"zone {label}: a view of type {type(view).__name__} has no declared "
        f"rendering in information_state — `view_of` answers cards, a count, "
        f"or nothing"
    )


def render_information_state(view: SeatView) -> str:
    """The seat's knowledge as the string OpenSpiel keys on."""
    zones = ";".join(_zone_line(label, zone) for label, zone in view.zones)
    state_vars = ";".join(f"{k}={render_state_variable(v)}" for k, v in view.state)
    obs = ";".join(repr(e) for e in view.obs_log)
    return f"P{view.player}|" + zones + f"|state:{state_vars}|obs:{obs}"


def information_state(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> str:
    """The seat's knowledge, derived and rendered in one step.

    Renders `_facts` rather than `derive`: the view is consumed before this
    returns and never reaches a caller, so it has nothing to gain from a
    snapshot and would pay for one on the engine's most-called derivation.
    """
    return render_information_state(_facts(player, rs, obs_log))
