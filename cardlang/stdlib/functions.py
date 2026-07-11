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
        "tarot_trick_winner",  # French Tarot: highest atout else led suit; Excuse never wins
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
        "tichu_lead_options",  # Tichu: every combination + the special-card lead singles
    }
)
STDLIB_CLIMB_FOLLOWS: frozenset[str] = frozenset(
    {
        "bigtwo_follows",  # Big Two: combinations that beat the standing play (same size)
        "tichu_follows",  # Tichu: same kind/length and higher, any bomb, Dragon/Phoenix answers
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
        "rank_value",  # a card's rank strength under the game's `ranking:` (higher = stronger)
        "card_value",  # a card's deck-declared card-point value (point-trick counters)
        "pinochle_meld_value",  # Pinochle: a player's hand's meld points under the declared trump
        "tarot_led_suit",  # French Tarot: the effective led suit (first non-Excuse card) in play
        "tarot_trump_height",  # French Tarot: an atout's rank strength (0 for a non-atout)
        "tarot_excuse_player",  # French Tarot: who played the Excuse in the trick just completed
        "tarot_per_opp",  # French Tarot: the zero-sum per-opponent settlement amount
        "tarot_card_points",  # French Tarot: a card's doubled card-point value
        "schnapsen_trick_winner",  # Schnapsen: the two-card trick's winner (leader led first)
        "skat_next_bid",  # Skat: the next Reizen ladder value (0 = exhausted)
        "skat_follow_ok",  # Skat: follow-class legality (jacks + trump suit are one class)
        "skat_trick_winner",  # Skat: the three-card trick's winner under the contract
        "skat_matadors",  # Skat: the with/without matador count (hand + skat)
        "skat_effective_loss",  # Skat: the overbid-aware loss base (needs a ceiling)
        "tichu_call_roll",  # Tichu: one player's Tichu/Grand-Tichu gate (0/100/200, rng)
        "tichu_mahjong_holder",  # Tichu: who holds the Mahjong (leads the first trick)
        "tichu_players_holding",  # Tichu: how many players still hold cards
        "tichu_double_victory",  # Tichu: are the first two finishers teammates?
        "tichu_partner",  # Tichu: the teammate (partners sit across)
        "tichu_next_holder",  # Tichu: the arg if holding, else the next holder ccw
        "tichu_dragon_won",  # Tichu: did the Dragon capture the trick just completed?
        "tichu_dragon_recipient",  # Tichu: the opponent given the Dragon's trick (rng)
        "tichu_opponent_team",  # Tichu: the team a player does not belong to
        "tichu_first_out",  # Tichu: the first finisher (defaults to player 0)
        "tichu_card_points",  # Tichu: the card-point table (K/10 = 10, 5 = 5, Dragon +25, Phoenix -25)
        "tichu_hand_summary",  # Tichu: emit the tichu_hand trace; the captured card points
        "coup_players_in",  # Coup: players still holding influence (game ends at 1)
        "coup_next_in_game",  # Coup: the next in-game player clockwise
        "coup_has_char",  # Coup: does a player hold the claimed character (a proof)?
        "coup_note_reveal",  # Coup: trace the influence flip that just happened
        "coup_game_summary",  # Coup: emit the conservation/finals trace at game end
        "peg_value",  # Cribbage: pegging/fifteens value of a card (A=1, faces 10)
        "peg_pair_points",  # Cribbage: pairs points at the tail of the live pegging count
        "peg_run_points",  # Cribbage: run points at the tail of the live pegging count
        "peg_origin_of",  # Cribbage: which player played a live pegging-pile card
        "cribbage_show_value",  # Cribbage: a player's pegged hand's show score
        "cribbage_crib_value",  # Cribbage: the dealer's crib show score
    }
)

# Zone-query methods: `zone.method(...)` (library.md "Types", ZoneContents).
ZONE_METHODS: frozenset[str] = frozenset(
    {
        "where",
        "cards_of_suit",
    }
)
