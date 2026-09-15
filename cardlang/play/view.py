"""A seat's view as text a person reads: the Seat View's second rendering.

`render_view` reads a Seat View and the game's own declarations and nothing
else, never the World, so what it can show is what the seat knows. The
information state (`cardlang.openspiel.infostate.render_information_state`)
renders the same view for OpenSpiel to key on; this text is laid out for a
person, and tests/test_play_view.py certifies that every fact the view carries
still shows in it.

The text shows whose view it is, with a turn line when the decision is the
seat's own; each zone as its projection answers, the cards in the game's order,
a count, or unseen; the public state variables; and the whole observation log,
one line per event (`cardlang.play.events`). Every fact of the position it
shows is one the soundness matrix probes, or, for the turn line, one the swap
proof holds. A caller shows the other facts of the decision beside it: which
decision it is, whose it is when it is another seat's, what can be chosen.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import cache

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import SeatView, render_state_variable
from cardlang.play.events import counted, event_line
from cardlang.runtime.observe import ZoneView
from cardlang.runtime.values import Card, deck_ranks, deck_suits
from cardlang.types import Flavor


@cache
def _positions(deck: str, ranking: tuple[str, ...]) -> tuple[dict[str, int], dict[str, int]]:
    suits = deck_suits(deck)
    ranks = ranking or deck_ranks(deck)
    return (
        {suit: place for place, suit in enumerate(suits)},
        {rank: place for place, rank in enumerate(ranks)},
    )


def card_order(game: n.Game) -> Callable[[Card], tuple[int, int, str]]:
    """The order a seat's cards show in: suit by suit in the deck's own order,
    and within a suit by the game's `ranking:` from the highest, or by the
    deck's order where the game declares none. A suit or rank the declarations
    do not name sorts after every one they do, and the rendering breaks a tie,
    so the order is defined for any card a seat can be shown."""
    suits, ranks = _positions(game.deck, game.ranking)

    def key(card: Card) -> tuple[int, int, str]:
        return (
            suits.get(card.suit, len(suits)),
            ranks.get(card.rank, len(ranks)),
            str(card),
        )

    return key


def _zone(
    zone: ZoneView, key: Callable[[Card], tuple[int, int, str]], noun: Flavor
) -> str:
    if zone is None:
        return "unseen"
    if isinstance(zone, int) and not isinstance(zone, bool):
        return counted(zone, noun)
    if isinstance(zone, tuple) and all(isinstance(card, Card) for card in zone):
        return " ".join(str(card) for card in sorted(zone, key=key)) or "empty"
    # Closed-domain completeness: `view_of` answers cards, a count, or nothing,
    # and another shape spelled as one of those would read as a projection that
    # never happened.
    raise AssertionError(
        f"a zone view of type {type(zone).__name__} has no declared rendering in "
        f"render_view — `view_of` answers cards, a count, or nothing"
    )


def _aligned(rows: Iterable[tuple[str, str]], empty: str) -> list[str]:
    listed = list(rows)
    if not listed:
        return [f"  {empty}"]
    width = max(len(name) for name, _ in listed)
    return [f"  {name:<{width}}  {text}" for name, text in listed]


def _numbered(lines: list[str], recent: int | None) -> list[str]:
    if not lines:
        return ["  nothing yet"]
    width = len(str(len(lines)))
    rows = [f"  {number:>{width}}  {line}" for number, line in enumerate(lines, start=1)]
    folded = 0 if recent is None else max(0, len(lines) - recent)
    if not folded:
        return rows
    earlier = "1 earlier event" if folded == 1 else f"{folded} earlier events"
    return [f"  {'':>{width}}  {earlier}", *rows[folded:]]


def render_view(
    game: n.Game, view: SeatView, *, your_turn: bool = False, recent: int | None = None
) -> str:
    """What `view.player` knows at this position, as text a person reads.

    `your_turn` says the decision at this position is the seat's own. It is the
    one fact of the position shown here that a Seat View does not carry, and
    the swap proof holds it: worlds the deciding seat cannot tell apart give
    that seat the decision in both.

    `recent` shows only that many of the log's latest events, under one line
    counting the events before them. The text with the whole log is the one
    certified; a window onto it is a presentation its caller chooses.
    """
    noun = game.content_flavor
    key = card_order(game)
    lines = [f"{game.name}, as P{view.player} sees it"]
    if your_turn:
        lines.append("your turn to choose")
    lines += ["", "zones"]
    lines += _aligned(((label, _zone(zone, key, noun)) for label, zone in view.zones), "none")
    lines += ["", "state variables"]
    lines += _aligned(
        ((name, render_state_variable(content)) for name, content in view.state), "none"
    )
    lines += ["", "observation log"]
    lines += _numbered([event_line(event, noun) for event in view.obs_log], recent)
    return "\n".join(lines)
