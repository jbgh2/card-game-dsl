"""Enumerable values a game's deck and the stdlib types define.

Suits and ranks come from the deck; Direction is a stdlib enum. The name
resolver classifies a bare name as an enum value when it appears here, so the
IR can distinguish `left` / `hearts` (values) from `leader` (a variable).
Seeded for the formalized corpus; extended corpus-first.
"""

from __future__ import annotations

# deck name -> its suits
_FRENCH = frozenset({"clubs", "diamonds", "hearts", "spades"})
_SUITS_BY_DECK: dict[str, frozenset[str]] = {
    "standard52": _FRENCH,
    "schnapsen20": _FRENCH,  # 20-card Ace-Ten deck, same four suits
    "pinochle48": _FRENCH,   # 48-card Pinochle pack, same four suits
    "skat32": _FRENCH,       # 32-card Skat pack, same four suits
    # Tarot adds the 21-card trump suit (atouts) and the singleton Excuse.
    "tarot78": _FRENCH | frozenset({"atouts", "excuse"}),
    # Tichu adds the four special cards under a "special" suit.
    "tichu56": _FRENCH | frozenset({"special"}),
}

# The stdlib Direction enum (used for passing/seating offsets). `hold` is the
# no-pass / keep value; `none` is NOT a direction — it is the universal null
# literal (see resolve._classify).
DIRECTION_VALUES: frozenset[str] = frozenset({"left", "right", "across", "hold"})


def deck_suits(deck: str) -> frozenset[str]:
    return _SUITS_BY_DECK.get(deck, frozenset())


def enum_values(deck: str) -> frozenset[str]:
    """All bare-name enum values visible in a game with the given deck."""
    return deck_suits(deck) | DIRECTION_VALUES
