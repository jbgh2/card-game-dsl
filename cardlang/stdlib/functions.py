"""Standard-library functions, value-callbacks, and zone-query methods.

The name resolver checks bare-name function references (e.g. an outcome
function passed to `Trick`), `f(...)` calls, and `zone.method(...)` queries
against these sets, so the IR can mark them as functions and unknown calls are
caught. Seeded for the formalized corpus; extended corpus-first.
"""

from __future__ import annotations

# Stdlib values referenced by bare name (outcome functions passed as callbacks).
STDLIB_VALUE_NAMES: frozenset[str] = frozenset(
    {
        "highest_of_led_suit",
        "highest_trump_or_led_suit",  # trick winner with a trump suit in play
        "on_play_of_tochoo",  # Getaway early-termination: ends the trick on a tochoo play
    }
)

# Stdlib functions invoked with arguments: `f(...)`.
STDLIB_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "player_holding",
        "team_of",  # the partnership a player belongs to
        "error",  # the if_impossible fallback that rejects the move
    }
)

# Zone-query methods: `zone.method(...)` (library.md "Types", ZoneContents).
ZONE_METHODS: frozenset[str] = frozenset(
    {
        "where",
        "cards_of_suit",
    }
)
