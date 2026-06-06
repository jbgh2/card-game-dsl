"""Standard-library zone types, as data.

The library zone aliases from library.md, recorded as a table the resolver
checks references against. ``takes_owner`` records whether the type is
parameterized by an owner/role (``Hand<Owner>``) or is a singleton
(``Deck``). Seeded with what the walking skeleton needs; extended
corpus-first as games require new aliases.
"""

from __future__ import annotations

# zone type name -> whether it takes a single owner/role type argument
LIBRARY_ZONE_TYPES: dict[str, bool] = {
    "Deck": False,
    "Hand": True,
    "PublicHand": True,
    "TrickPile": False,
    "Discard": False,
    "Muck": False,
    "ChipStack": True,
    "PlayerPile": True,
    "TeamPile": True,  # a capture pile owned by a partnership (Spades)
}
