"""Standard-library move types, as data.

The named card-movement patterns from library.md "Move types". The resolver
checks every `constrains:`, `legal_moves:`, and transition move-event
reference against this set. Seeded with what the formalized corpus uses;
extended corpus-first as games introduce new move types.
"""

from __future__ import annotations

LIBRARY_MOVE_TYPES: frozenset[str] = frozenset(
    {
        "play_to_trick",
        "transfer_between_hands",
    }
)
