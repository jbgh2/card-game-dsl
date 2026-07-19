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
        "belote_trick_winner",  # Belote: highest trump under the J-9 trump order, else led suit
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
        "president_lead_options",  # President: every equal-rank set of 1-4 cards
    }
)
STDLIB_CLIMB_FOLLOWS: frozenset[str] = frozenset(
    {
        "bigtwo_follows",  # Big Two: combinations that beat the standing play (same size)
        "tichu_follows",  # Tichu: same kind/length and higher, any bomb, Dragon/Phoenix answers
        "president_follows",  # President: same-size higher-rank sets + transparent threes
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
        "top_of",  # the top card of an ordered zone/collection (the sequence end)
        "bottom_of",  # the bottom card of an ordered zone/collection (the sequence front)
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
        "doko_trick_winner",  # Doppelkopf: the four-card trick's winner (first of equals)
        "tichu_mahjong_holder",  # Tichu: who holds the Mahjong (leads the first trick)
        "tichu_players_holding",  # Tichu: how many players still hold cards
        "tichu_double_victory",  # Tichu: are the first two finishers teammates?
        "tichu_partner",  # Tichu: the teammate (partners sit across)
        "tichu_next_holder",  # Tichu: the arg if holding, else the next holder ccw
        "tichu_dragon_won",  # Tichu: did the Dragon capture the trick just completed?
        "tichu_opponent_team",  # Tichu: the team a player does not belong to
        "tichu_first_out",  # Tichu: the first finisher (defaults to player 0)
        "tichu_card_points",  # Tichu: the card-point table (K/10 = 10, 5 = 5, Dragon +25, Phoenix -25)
        "tichu_hand_summary",  # Tichu: emit the tichu_hand trace; the captured card points
        "president_next_holder",  # President: the arg if holding, else the next holder cw
        "president_is_top_rank",  # President: is the card the player's highest rank (2 high)?
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
        "gin_card_points",  # Gin: deadwood value of a card (A=1, pips, faces 10)
        "gin_deadwood",  # Gin: optimal-partition deadwood of a hand
        "gin_can_knock",  # Gin: some discard leaves a <= 10 arrangement
        "gin_knock_ok",  # Gin: knock legality after a specific discard
        "gin_valid_meld",  # Gin: joint meld validity (set / ace-low run)
        "gin_arrange_ok",  # Gin: valid meld AND the rest still arranges to <= 10
        "gin_can_declare",  # Gin: some declarable meld exists (knocker)
        "gin_can_declare_free",  # Gin: some valid meld exists (defender)
        "gin_flat_points",  # Gin: a hand counted as all-deadwood
        "gin_shown_points",  # Gin: shown_deadwood[p]'s point count
        "gin_lay_ok_a",  # Gin: card extends the knocker's meld A
        "gin_lay_ok_b",  # Gin: card extends the knocker's meld B
        "gin_lay_ok_c",  # Gin: card extends the knocker's meld C
        "five_hundred_next_bid",  # 500: cheapest bid ordinal in a strain beating the standing bid
        "five_hundred_bid_value",  # 500: a contract ordinal's score value (misère 250, open 500)
        "five_hundred_bid_level",  # 500: a suit/NT contract ordinal's trick target (6..10)
        "five_hundred_follow_ok",  # 500: follow legality (joker + bowers are trump-suit members)
        "five_hundred_lead_ok",  # 500: lead legality (un-nominated joker lead restriction)
        "five_hundred_trick_winner",  # 500: the trick's winner (3 cards in misère, else 4)
        "belote_trump_height",  # Belote: a rank's strength within trump (J > 9 > A > 10 > K > Q > 8 > 7)
        "belote_opp_winning",  # Belote: is the live trick's current winner an opponent of the actor?
        "belote_royal_player",  # Belote: who played a trump K/Q in the trick just completed
        "belote_best_is",  # Belote: is the stated (class, rank, trump) the actor's best combination?
        "belote_decl_points",  # Belote: the best combination's points under trump
        "belote_decl_class",  # Belote: the best combination's class (carré > quinte > quarte > tierce)
        "belote_decl_height",  # Belote: the best combination's height (top card / carré rank)
        "belote_decl_trump",  # Belote: is the best combination a trump-suit sequence?
        "belote_decl_size",  # Belote: how many cards the declarations comprise (showing bound)
        "belote_decl_slot",  # Belote: is a card the k-th declared card (the showing's reveal predicate)?
        "canasta_is_red3",  # Canasta: is the card a red three (bonus card)?
        "canasta_is_black3",  # Canasta: is the card a black three (stop card)?
        "canasta_top_starts_pile",  # Canasta: may the turned card start the pile?
        "canasta_top_is_wild",  # Canasta: did the discard just freeze the pile?
        "canasta_pile_rank",  # Canasta: the pile's top rank (the meld a take feeds)
        "canasta_can_take_pile",  # Canasta: a complete legal pile take exists
        "canasta_must_take_pile",  # Canasta: the no-stock forced take applies
        "canasta_can_start",  # Canasta: a new meld of the rank is completable from hand
        "canasta_stage_ok",  # Canasta: card joins the open attempt, close stays reachable
        "canasta_close_ok",  # Canasta: the open attempt closes legally as it stands
        "canasta_add_ok",  # Canasta: card lays onto the side's standing meld of the rank
        "canasta_discard_ok",  # Canasta: the discard may end the turn (go-out rule)
        "canasta_black3_ok",  # Canasta: the go-out black-three meld is legal now
        "canasta_meld_points",  # Canasta: card points of everything the side melded
        "canasta_canasta_bonus",  # Canasta: 500 per natural / 300 per mixed canasta
        "canasta_red3_bonus",  # Canasta: the red-three bonus, sign by melded-or-not
        "canasta_hand_points",  # Canasta: card points left in both partners' hands
    }
)
