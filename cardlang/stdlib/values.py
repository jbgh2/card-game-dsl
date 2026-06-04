"""Enumerable values a game's deck and the stdlib types define.

Suits and ranks come from the deck; Direction is a stdlib enum. The name
resolver classifies a bare name as an enum value when it appears here, so the
IR can distinguish `left` / `hearts` (values) from `leader` (a variable).
Seeded for the formalized corpus; extended corpus-first.
"""

from __future__ import annotations

# deck name -> its suits
_SUITS_BY_DECK: dict[str, frozenset[str]] = {
    "standard52": frozenset({"clubs", "diamonds", "hearts", "spades"}),
}

# The stdlib Direction enum (used for passing/seating offsets).
DIRECTION_VALUES: frozenset[str] = frozenset({"left", "right", "across", "none"})


def deck_suits(deck: str) -> frozenset[str]:
    return _SUITS_BY_DECK.get(deck, frozenset())


def enum_values(deck: str) -> frozenset[str]:
    """All bare-name enum values visible in a game with the given deck."""
    return deck_suits(deck) | DIRECTION_VALUES
