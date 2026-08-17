"""The engine-core trick-[[winner]] comparisons.

The two standard winner functions — highest of the led suit, and highest
trump else highest of the led suit — are the language's, not any one game's:
the trick form's `winner` clause names them (Bridge, Hearts, Spades, Oh
Hell), and the call form `highest_trump_or_led_suit(zone, trump)` computes
the same winner over a public pile's [[arrival-record]] (issue #256; the
schnapsen retirement). They live in this neutral module because the two
dispatch halves may not import each other (`runtime/builtins.py` and
`runtime/primitives.py`, each docstring's contract) and BOTH consume these.

Contract
--------
Assumes: `played` is non-empty, in play order, with the led card first.
Establishes: the winning seat, by pure comparison over the arguments.
Illegal after: nothing — pure functions, no state.
"""

from __future__ import annotations

from collections.abc import Mapping

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import Card, Player, rank_strength

# An outcome function picks the trick winner from the plays, the led suit,
# the trump suit (None when no trump), and the game's rank-strength map.
RankIndex = Mapping[str, int]


def recorded_plays(
    pairs: tuple[tuple[Player | None, Card], ...], caller: str, expected: int
) -> list[tuple[Player, Card]]:
    """A completed trick's plays, read off the pile's [[arrival-record]]
    pairs (issue #256) — the shared guard of every hand-rolled trick winner.

    Two Owner Guards, both the hosting description's errors: the pile must
    hold exactly the completed trick (`expected` plays — a wrong call site
    used to be caught by the same count over zipped cards), and every entry
    must carry a deciding actor (a card an engine deal placed has no player
    to attribute the play to)."""
    if len(pairs) != expected:
        raise OwnerGuardError(
            f"{caller}: trick pile holds {len(pairs)} cards, expected "
            f"a completed {expected}-card trick"
        )
    played: list[tuple[Player, Card]] = []
    for actor, card in pairs:
        if actor is None:
            raise OwnerGuardError(
                f"{caller}: {card} arrived with no deciding actor (an engine "
                f"deal, not a play) — every trick card must have been played "
                f"by a seat"
            )
        played.append((actor, card))
    return played


def _strongest(
    candidates: list[tuple[Player, Card]], rank_index: RankIndex, reader: str
) -> Player:
    """The first-played candidate of greatest declared strength (`max` keeps
    the first maximal element, so equals resolve to the earlier play).
    Strength reads go through `rank_strength`, the runtime Owner Guard for a
    rank outside a partial `ranking:` — naming `reader`, the DSL-visible
    winner, so the message says which read failed."""
    return max(
        candidates, key=lambda pc: rank_strength(rank_index, pc[1].rank, reader)
    )[0]


def highest_of_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The player who played the highest-ranked card of the led suit. Reads no
    trump: the argument is the winner contract's, accepted and unused — which
    is why resolve refuses a `trump` clause on this winner
    (`TRUMP_READING_WINNERS`, cardlang/builtins/functions.py)."""
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return _strongest(of_suit, rank_index, "highest_of_led_suit")


def highest_trump_or_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The highest trump if any trump was played, else the highest card of the
    led suit (the standard trick winner for a trump game)."""
    trumps = [(p, c) for (p, c) in played if c.suit == trump]
    if trumps:
        return _strongest(trumps, rank_index, "highest_trump_or_led_suit")
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return _strongest(of_suit, rank_index, "highest_trump_or_led_suit")
