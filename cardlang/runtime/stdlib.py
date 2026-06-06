"""Runtime implementations of the stdlib functions Hearts names.

These are the deferred runtime-primitives the front end only signatured
(library.md "Stdlib functions" / "Outcome functions"). Zone-query methods
(`where`, `cards_of_suit`) live in the evaluator; this module holds the bare
`f(...)` calls and the value-callbacks.
"""

from __future__ import annotations

from typing import Any, Callable

from cardlang.runtime.state import Ctx, IllegalMove
from cardlang.runtime.values import Card, Player


def call(name: str, args: list[Any], ctx: Ctx) -> Any:
    match name:
        case "player_holding":
            return _player_holding(args[0], ctx)
        case "team_of":
            return ctx.rs.team_of[args[0]]
        case "suit_of":
            return _suit_of(args[0])
        case "error":
            raise IllegalMove(args[0] if args else "illegal move")
        case _:
            raise AssertionError(f"unknown stdlib function '{name}'")


def _suit_of(value: Any) -> str:
    """The suit of a card, or of the single card in a zone (a face-up trump
    indicator)."""
    from cardlang.runtime.state import Zone

    if isinstance(value, Zone):
        return value.cards[0].suit
    assert isinstance(value, Card)
    return value.suit


def _player_holding(card: Card, ctx: Ctx) -> Player | None:
    """The player whose hand contains `card`, or None."""
    for player, zone in ctx.rs.zones.families["hand"].items():
        if card in zone.cards:
            return player
    return None


# --- value-callbacks (mechanic functions passed by name) ---

# An outcome function picks the trick winner from the plays, the led suit, and
# the trump suit (None when the game declares no trump).
OutcomeFn = Callable[[list[tuple[Player, Card]], str, "str | None"], Player]
# An early-termination predicate: does this play end the trick? (card, led_suit)
EarlyTermFn = Callable[[Card, str], bool]


def value_function(name: str) -> Callable[..., Any]:
    match name:
        case "highest_of_led_suit":
            return highest_of_led_suit
        case "highest_trump_or_led_suit":
            return highest_trump_or_led_suit
        case "on_play_of_tochoo":
            return on_play_of_tochoo
        case _:
            raise AssertionError(f"unknown stdlib value '{name}'")


def highest_of_led_suit(
    played: list[tuple[Player, Card]], led_suit: str, trump: str | None = None
) -> Player:
    """The player who played the highest-ranked card of the led suit."""
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return max(of_suit, key=lambda pc: pc[1].rank_order)[0]


def highest_trump_or_led_suit(
    played: list[tuple[Player, Card]], led_suit: str, trump: str | None = None
) -> Player:
    """The highest trump if any trump was played, else the highest card of the
    led suit (the standard trick winner for a trump game)."""
    trumps = [(p, c) for (p, c) in played if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: pc[1].rank_order)[0]
    return highest_of_led_suit(played, led_suit)


def on_play_of_tochoo(card: Card, led_suit: str) -> bool:
    """A tochoo is a card that fails to follow the led suit; playing one (only
    possible when void) ends the trick early (Getaway: the highest led-suit
    card then picks up the pile)."""
    return card.suit != led_suit
