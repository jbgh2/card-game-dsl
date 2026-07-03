"""Standard-library functions, value-callbacks, and zone-query methods.

The name resolver checks bare-name function references (e.g. a `round`'s
`outcome` / `early` function), `f(...)` calls, and `zone.method(...)` queries
against these sets, so the IR can mark them as functions and unknown calls are
caught. Seeded for the formalized corpus; extended corpus-first.
"""

from __future__ import annotations

# Stdlib values referenced by bare name (a `round`'s `outcome` callback). The two
# round forms have different outcome signatures and are validated against separate
# namespaces (a trick outcome named on an auction round, or vice versa, is rejected
# at resolve time, not left to crash the dispatcher at runtime):
#
# - a *trick* outcome  : (played, led_suit, trump, rank_index) -> Player
# - an *auction* outcome (the auction form): (history, ctx) -> (tag, payloads),
#   producing the phase's typed variant.
STDLIB_TRICK_OUTCOMES: frozenset[str] = frozenset(
    {
        "highest_of_led_suit",
        "highest_trump_or_led_suit",  # trick winner with a trump suit in play
    }
)
STDLIB_AUCTION_OUTCOMES: frozenset[str] = frozenset(
    {
        "bridge_auction_outcome",  # Bridge auction -> contract_finalized | all_pass
        "pinochle_auction_outcome",  # Pinochle ascending auction -> bid_won
        "tarot_auction_outcome",  # French Tarot four-level bid -> taken | thrown_in
    }
)
# The union is the bare-name function namespace (for NameRef classification) and
# the surface the signature tables must cover.
STDLIB_VALUE_NAMES: frozenset[str] = STDLIB_TRICK_OUTCOMES | STDLIB_AUCTION_OUTCOMES

# Early-termination predicates a `round`'s `early` clause may name. Distinct from
# outcome callbacks above — a different signature, (card, led_suit) -> Boolean —
# so they validate against their own set, not the outcome-function namespace.
STDLIB_EARLY_PREDICATES: frozenset[str] = frozenset(
    {
        "on_play_of_tochoo",  # Getaway: a tochoo (off-suit play when void) ends the trick
    }
)

# Combination-engine queries the climbing form of `round` names. Two signatures,
# validated against separate sets so a follow query named as the lead query (or
# vice versa) is rejected at resolve time:
#
# - a *lead* query    (`combinations`): (hand, ctx) -> list[Play]
# - a *follows* query (`follows`)     : (hand, current, ctx) -> list[Play]
#
# The engines are game-local (Big Two's and Tichu's combination rules differ), so
# these grow corpus-first, one pair per climbing game.
STDLIB_CLIMB_LEADS: frozenset[str] = frozenset(
    {
        "bigtwo_lead_options",  # Big Two: every combination (3♦-filtered on the opening lead)
    }
)
STDLIB_CLIMB_FOLLOWS: frozenset[str] = frozenset(
    {
        "bigtwo_follows",  # Big Two: combinations that beat the standing play (same size)
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
        "bring_in_seat",  # Stud: the lowest-door seat that posts the bring-in
        "first_to_act_seat",  # Stud: the highest-upcards seat that acts first on a street
        "pot_share",  # Stud: the chips a player collects at showdown (side-pot layering)
        "bigtwo_first_leader",  # Big Two: the holder of the 3♦, who leads the first hand
    }
)

# Zone-query methods: `zone.method(...)` (library.md "Types", ZoneContents).
ZONE_METHODS: frozenset[str] = frozenset(
    {
        "where",
        "cards_of_suit",
    }
)
