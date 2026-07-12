"""Enumerable values a game's deck and the stdlib types define.

Suits and ranks come from the deck; Direction is a stdlib enum. The name
resolver classifies a bare name as an enum value when it appears here, so the
IR can distinguish `left` / `hearts` (values) from `leader` (a variable).
Seeded for the formalized corpus; extended corpus-first.
"""

from __future__ import annotations

from cardlang.runtime.values import deck_suits as _runtime_deck_suits

# The stdlib Direction enum (used for passing/seating offsets). `hold` is the
# no-pass / keep value; `none` is NOT a direction — it is the universal null
# literal (see resolve._classify).
DIRECTION_VALUES: frozenset[str] = frozenset({"left", "right", "across", "hold"})


# deck name -> total card count. Irregular decks (copies in pinochle48/coup15,
# explicit lists in tarot78/tichu56) make a suits×ranks formula wrong, so the size
# is an explicit table — pinned to `len(runtime.build_deck(name))` by a drift test.
_DECK_SIZE: dict[str, int] = {
    "standard52": 52,
    "schnapsen20": 20,
    "pinochle48": 48,
    "doppelkopf48": 48,
    "skat32": 32,
    "tarot78": 78,
    "tichu56": 56,
    "coup15": 15,
}


def deck_suits(deck: str) -> frozenset[str]:
    """A deck's suits, derived from the runtime deck registry — one source of
    truth (closed-domain completeness): a deck registered in `DECKS` can
    never be silently absent here, and an unknown deck name fails loudly in
    `build_deck` rather than resolving every suit literal to an empty
    namespace."""
    return frozenset(_runtime_deck_suits(deck))


def deck_size(deck: str) -> int | None:
    """The deck's card count, or None for an unknown deck (rejected earlier; the
    capacity check treats None as 'cannot bound' and skips the game)."""
    return _DECK_SIZE.get(deck)


def enum_values(deck: str) -> frozenset[str]:
    """All bare-name enum values visible in a game with the given deck."""
    return deck_suits(deck) | DIRECTION_VALUES
