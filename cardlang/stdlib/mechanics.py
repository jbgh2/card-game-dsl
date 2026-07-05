"""Standard-library mechanics, as data.

The named, parameterized behavioral units from library.md "Mechanics". The
resolver checks every `instantiate` against this set. Seeded with what the
formalized corpus uses; extended corpus-first.
"""

from __future__ import annotations

LIBRARY_MECHANICS: frozenset[str] = frozenset(
    {
        "SkatHand",  # Skat's Reizen auction + contract + suit/grand/null tricks
        "TichuHand",  # Tichu's pushing + climbing trick + special cards + scoring
        "CoupGame",  # Coup's influence / coin / challenge-block / elimination engine
    }
)
