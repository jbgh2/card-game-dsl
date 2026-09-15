"""One line of text per observation event: what a seat's view shows of its log.

`EVENT_LINES` holds a line for every kind `observe.EVENT_PAYLOADS` declares,
and each line spells every field its kind carries, so a seat shown its log is
shown all of it. An event the table does not describe has no reading, and
`event_line` refuses it in the table's own words rather than show part of it.

A designed constraint: an event carries zone labels and card renderings, never
the zones or the cards (`observe._rendered`, issue #666), and a line shows them
as the event spells them. It derives no fact by parsing one — no seat out of
`hand[2]`, no suit out of `Q♠` — so a line says who acted only where the event
names the seat, and a group of cards keeps the event's own order.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cardlang.runtime.observe import payload_refusal
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


def _decided(choice: str | int | tuple[str, ...] | None) -> str:
    # No two alternatives may read alike, or two logs would show as one: a
    # group of cards is bracketed, which no rendered name or card begins with,
    # and a flag or nothing is spelled as the language writes it, which no
    # declaration may be named (`resolve.RESERVED_VALUE_NAMES`).
    if choice is None:
        return "none"
    if isinstance(choice, bool):
        return "true" if choice else "false"
    if isinstance(choice, tuple):
        return "[" + " ".join(choice) + "]"
    return str(choice)


# Each line takes its kind's fields in `EVENT_PAYLOADS` order, then the noun a
# count is spelled with.
EVENT_LINES: dict[str, Callable[..., str]] = {
    "chose": lambda choice, noun: f"you chose {_decided(choice)}",
    "announce": lambda seat, choice, noun: f"P{seat} announced {_decided(choice)}",
    "move": lambda source, source_view, destination, destination_view, noun: (
        f"moved from {source} ({_seen(source_view, noun)}) "
        f"to {destination} ({_seen(destination_view, noun)})"
    ),
    "reveal": lambda label, card, noun: f"revealed {card} in {label}",
}


def event_line(event: tuple[Any, ...], noun: Flavor = "card") -> str:
    """The line a seat's view shows for one event of its observation log."""
    refusal = payload_refusal(event)
    if refusal is not None:
        raise AssertionError(
            f"{refusal} — a seat's view shows only the events the payload table "
            f"describes"
        )
    kind, *fields = event
    return EVENT_LINES[kind](*fields, noun=noun)
