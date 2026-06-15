"""Standard-library functions, value-callbacks, and zone-query methods.

The name resolver checks bare-name function references (e.g. a `round`'s
`outcome` / `early` function), `f(...)` calls, and `zone.method(...)` queries
against these sets, so the IR can mark them as functions and unknown calls are
caught. Seeded for the formalized corpus; extended corpus-first.
"""

from __future__ import annotations

# Stdlib values referenced by bare name (a `round`'s `outcome` callback).
# A trick outcome has signature (played, led_suit, trump, rank_index) -> Player; an
# auction outcome (the auction form of `round`) has (history, ctx) -> (tag, payloads)
# and produces the phase's typed variant. Both live in this namespace; the runtime
# dispatches by the round form it is driving.
STDLIB_VALUE_NAMES: frozenset[str] = frozenset(
    {
        "highest_of_led_suit",
        "highest_trump_or_led_suit",  # trick winner with a trump suit in play
        "bridge_auction_outcome",  # Bridge auction -> contract_finalized | all_pass
    }
)

# Early-termination predicates a `round`'s `early` clause may name. Distinct from
# outcome callbacks above — a different signature, (card, led_suit) -> Boolean —
# so they validate against their own set, not the outcome-function namespace.
STDLIB_EARLY_PREDICATES: frozenset[str] = frozenset(
    {
        "on_play_of_tochoo",  # Getaway: a tochoo (off-suit play when void) ends the trick
    }
)

# Stdlib functions invoked with arguments: `f(...)`.
STDLIB_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "player_holding",
        "team_of",  # the partnership a player belongs to
        "suit_of",  # the suit of a card, or of a single-card zone (trump indicator)
        "strain_index",  # bidding rank of a strain: C<D<H<S<NT (none = no-trump, highest)
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
