"""Standard-library mechanics, as data.

The named, parameterized behavioral units from library.md "Mechanics". The
resolver checks every `instantiate` against this set. Seeded with what the
formalized corpus uses; extended corpus-first.
"""

from __future__ import annotations

LIBRARY_MECHANICS: frozenset[str] = frozenset(
    {
        "Trick",
        "SchnapsenHand",  # Schnapsen's trick-and-draw hand with heterogeneous lead moves
    }
)
