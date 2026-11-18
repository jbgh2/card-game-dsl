"""One line of text per observation event: what a seat's view shows of its log.

`event_line` has a line for every kind of `observe.ObservationEvent`, matched
exhaustively, and each line spells every field its kind carries, so a seat
shown its log is shown all of it.

A designed constraint: an event carries zone labels and card renderings, never
the zones or the cards (`observe._rendered`, issue #666), and a line shows them
as the event spells them. It derives no fact by parsing one — no seat out of
`hand[2]`, no suit out of `Q♠` — so a line says who acted only where the event
names the seat, and a group of cards keeps the event's own order.
"""

from __future__ import annotations

from typing import assert_never

from cardlang.runtime.observe import (
    AnnounceEvent,
    AskedEvent,
    ChoseEvent,
    MovementEvent,
    ObservationEvent,
    RevealEvent,
    WasEvent,
)
from cardlang.types import Flavor


def counted(count: int, noun: Flavor) -> str:
    """A number of cards or pieces, as a person says it."""
    return f"1 {noun}" if count == 1 else f"{count} {noun}s"


def _grouped(renderings: tuple[str, ...], noun: Flavor) -> str:
    return " ".join(renderings) if renderings else f"no {noun}s"


def _seen(view: tuple[str, ...] | int | None, noun: Flavor) -> str:
    if view is None:
        return "unseen"
    if isinstance(view, tuple):
        return _grouped(view, noun)
    return counted(view, noun)


def _decided(choice: str | int | None) -> str:
    # No two alternatives may read alike, or two logs would show as one: a
    # flag or nothing is spelled as the language writes it, which no
    # declaration may be named (`resolve.RESERVED_VALUE_NAMES`).
    if choice is None:
        return "none"
    if isinstance(choice, bool):
        return "true" if choice else "false"
    return str(choice)


# What each construct asks for: the verb a person reads, and the unit its count
# is counted in — a card for a movement, a number for a `choose`, a move for an
# offer. An empty unit means the content noun (card or piece). Every construct
# spells its count, because a field a line does not show is a field the
# soundness matrix cannot certify (tests/test_play_view.py). Total over
# `delegation.CONSTRUCTS`, reconciled by tests/test_asked_event.py.
_ASK_PHRASES: dict[str, tuple[str, str, str]] = {
    "transfer": ("move", "", ""),
    # "commit", not "move": a seat choosing simultaneously is committing
    # before any other seat's pick is shown, which is the whole of what the
    # construct means to a designer — and a plain "move" would read alike to
    # a `transfer` into the same zone, showing two decisions as one.
    "simultaneous": ("commit", "", ""),
    "trick": ("play", "", ""),
    "joint": ("pick", "set that goes together", "sets that go together"),
    "offer": ("take", "of the moves offered", "of the moves offered"),
    "choose": ("choose", "number", "numbers"),
    "climb": ("play", "combination (or pass)", "combinations (or pass)"),
}


def _asking(construct: str, count: int, noun: Flavor) -> str:
    """What the seat is invited to do, counted."""
    verb, singular, plural = _ASK_PHRASES[construct]
    if not singular:
        return f"{verb} {counted(count, noun)}"
    return f"{verb} {count} {singular if count == 1 else plural}"


def _landing(construct: str, destination: str | None) -> str:
    """Where the picks go. A named zone is said; a simultaneous pass says the
    zone is settled once everyone has chosen, which is what its absence MEANS —
    a seat told "nowhere" would read its own pass as going nowhere."""
    if destination is not None:
        return f" to `{destination}`"
    if construct == "simultaneous":
        return ", landing where every seat's choice settles"
    return ""


def event_line(event: ObservationEvent, noun: Flavor = "card") -> str:
    """The line a seat's view shows for one event of its observation log."""
    match event:
        case AskedEvent(phase, construct, count, destination):
            return (
                f"asked in `{phase}` to {_asking(construct, count, noun)}"
                f"{_landing(construct, destination)}"
            )
        case ChoseEvent(choice):
            return f"you chose {_decided(choice)}"
        case AnnounceEvent(seat, choice):
            return f"P{seat} announced {_decided(choice)}"
        case MovementEvent(source, source_view, destination, destination_view):
            return (
                f"moved from {source} ({_seen(source_view, noun)}) "
                f"to {destination} ({_seen(destination_view, noun)})"
            )
        case RevealEvent(label, card):
            return f"revealed {card} in {label}"
        case WasEvent(variable, slot, shown):
            return (
                f"`{variable if slot is None else f'{variable}[{slot}]'}` "
                + ("was not in scope" if shown is None else f"was `{shown}`")
                + " at the decision before"
            )
        case _:
            assert_never(event)
