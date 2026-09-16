"""Who plays the seats a person does not take: the `--vs` items of `cardlang play`.

An item is `WHO=OPPONENT`. WHO is a seat number, written as the table numbers
its seats; `all`, every seat that is not the person's; or `rest`, the seats no
numbered item names. OPPONENT is the name of an [[opponent]] in
`seat_policy.OPPONENTS`. An item is read on its own, before any game is loaded.
The items are then seated at the table the person sits at, which gives every
other seat exactly one opponent. The order of the items does not matter. A
saved session records each seat's opponent by name, never by `all` or `rest`.

Contract
--------
Assumes: `seat_policy.OPPONENTS` names every opponent.
Establishes: an item names a seat number with no sign, space or leading zero,
or a selector, and an opponent the table has; a seated composition names every
seat but the person's, each once; a recorded composition names the same seats,
each by an opponent the table has.
Illegal after: an opponent a table seats that the table does not name; a seat
with two opponents, or a seat but the person's with none.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cardlang.openspiel.seat_policy import OPPONENTS

ALL = "all"
REST = "rest"

# The opponent a refusal's example seats.
EXAMPLE = OPPONENTS["random"].name


@dataclass(frozen=True)
class Item:
    """One `--vs` item: `who` is a seat number as it was written, `all` or `rest`."""

    who: str
    opponent: str

    def __str__(self) -> str:
        return f"{self.who}={self.opponent}"


@dataclass(frozen=True)
class Unnamed:
    """A composition that leaves `seats` with no opponent."""

    seats: tuple[int, ...]


def seats_named(seats: Sequence[int]) -> str:
    names = [f"P{seat}" for seat in seats]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def described(name: str) -> str:
    return f"{name} ({OPPONENTS[name].description})"


def listing() -> str:
    """Every opponent, each with what it does."""
    return ", ".join(described(name) for name in OPPONENTS)


def by_opponent(opponents: Mapping[int, str]) -> list[str]:
    """One line for each opponent at the table, naming the seats it plays, in
    the order of those seats."""
    seats: dict[str, list[int]] = {}
    for seat in sorted(opponents):
        seats.setdefault(opponents[seat], []).append(seat)
    return [f"{seats_named(at)}: {described(name)}" for name, at in seats.items()]


def as_flags(opponents: Mapping[int, str]) -> str:
    """The opponents as the `--vs` items that name each seat."""
    return " ".join(f"--vs {seat}={name}" for seat, name in sorted(opponents.items()))


def read_item(text: str) -> Item | str:
    """The item `text` spells, or why it spells none."""
    who, equals, opponent = text.partition("=")
    if not equals:
        if text in OPPONENTS:
            return f"{text} names no seat: write --vs all={text} to seat it at every other seat"
        return (
            f"{text!r} is not WHO=OPPONENT: WHO is a seat number, all or rest, as in "
            f"--vs all={EXAMPLE}"
        )
    if who not in (ALL, REST) and not re.fullmatch(r"0|[1-9][0-9]*", who):
        return f"{who!r} is not a seat number, all or rest"
    if opponent not in OPPONENTS:
        return f"there is no opponent {opponent!r}; the opponents: {listing()}"
    return Item(who, opponent)


def seated(items: Sequence[Item], seats: int, person: int, path: str) -> dict[int, str] | Unnamed | str:
    """The opponent at each seat but `person`'s at a table of `seats`, the seats
    the items leave unnamed, or why the items seat nobody."""
    others = [seat for seat in range(seats) if seat != person]
    if not items:
        return Unnamed(tuple(others)) if others else {}
    if not others:
        return f"{path} seats one player, so --vs has no seat to fill; leave --vs out"
    alls = [item for item in items if item.who == ALL]
    rests = [item for item in items if item.who == REST]
    if alls and len(items) > 1:
        return (
            f"--vs {alls[0]} fills every other seat, so it stands alone; to name some "
            f"seats and fill the others, write --vs rest={alls[0].opponent} beside them"
        )
    if len(rests) > 1:
        return f"--vs {rests[0]} and --vs {rests[1]} both fill the rest; give rest once"
    numbered = {str(seat): seat for seat in range(seats)}
    named: dict[str, Item] = {}
    for item in items:
        if item.who in (ALL, REST):
            continue
        if item.who not in numbered:
            return f"{path} seats 0..{seats - 1}; --vs {item} names no seat at this table"
        if numbered[item.who] == person:
            return f"--vs {item} names P{person}, your own seat; --vs names the other seats"
        if item.who in named:
            return (
                f"--vs {named[item.who]} and --vs {item} both name P{item.who}; name each "
                "seat once"
            )
        named[item.who] = item
    chosen = {numbered[who]: item.opponent for who, item in named.items()}
    unnamed = [seat for seat in others if seat not in chosen]
    if alls:
        return {seat: alls[0].opponent for seat in others}
    if rests:
        if not named:
            return (
                f"--vs {rests[0]} fills the seats no --vs names, and none is named; write "
                f"--vs all={rests[0].opponent}"
            )
        if not unnamed:
            return f"--vs {rests[0]} fills no seat: every other seat is named; leave it out"
        chosen.update({seat: rests[0].opponent for seat in unnamed})
        return dict(sorted(chosen.items()))
    if unnamed:
        return Unnamed(tuple(unnamed))
    return dict(sorted(chosen.items()))


def recorded(opponents: Mapping[str, Any], seats: int, person: int, path: str) -> dict[int, str] | str:
    """The opponents a saved session records for a person at `person`, at a
    table of `seats`, or why they seat nobody there."""
    others = [seat for seat in range(seats) if seat != person]
    if set(opponents) != {str(seat) for seat in others}:
        if not others:
            return f"it records an opponent, and {path} seats one player"
        return (
            f"played at seat {person}, it should record one opponent for each of "
            f"{seats_named(others)}, and for no other seat"
        )
    for seat in others:
        name = opponents[str(seat)]
        if not isinstance(name, str) or name not in OPPONENTS:
            return (
                f"there is no opponent {name!r}, which it records for P{seat}; the "
                f"opponents: {listing()}"
            )
    return {seat: opponents[str(seat)] for seat in others}
