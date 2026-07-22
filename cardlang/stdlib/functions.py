"""Standard-library function and value-callback names.

The name resolver checks bare-name references (a `round`'s `outcome` / `early`
function, a climbing round's `combinations` / `follows` query) and `f(...)`
calls against these sets, so the IR can mark them as functions and unknown
names are caught. There is no zone-method namespace here: the expression layer
has no method register (decisions.md "The expression register"). Seeded for the
formalized corpus; extended corpus-first.
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
# Slot-only, deliberately outside STDLIB_VALUE_NAMES: an early predicate is
# unreachable as a bare NameRef and rejected in an `outcome` slot, even though
# the runtime dispatches both through `value_function`. Sharing the dispatcher
# is an implementation detail of the runtime, not a shared namespace.
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
        "lines",  # the board's length-k lines (cell-name tuples); reads the `board:`
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
        "president_next_holder",  # President: the arg if holding, else the next holder cw
        "president_is_top_rank",  # President: is the card the player's highest rank (2 high)?
        "coup_players_in",  # Coup: players still holding influence (game ends at 1)
        "coup_next_in_game",  # Coup: the next in-game player clockwise
        "coup_has_char",  # Coup: does a player hold the claimed character (a proof)?
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

# The classification of every STDLIB_CALL_FUNCS member by the game feature its
# semantics READ. A call that reads a card's suit or rank, the ranking order,
# card-point values, or follow/trump/lead machinery cannot mean anything in a
# piece game (no suit/rank/points), so it is a resolve-time FLAVOR wall
# (DECK_ONLY_CALL_FUNCS); a call that reads the `board:` entry cannot mean
# anything in a boardless game, so it is a resolve-time BOARD wall
# (BOARD_ONLY_CALL_FUNCS -- the deck-only classification's board twin, keyed on
# `game.board is None` rather than the flavor); GENERIC_CALL_FUNCS -- functions
# that touch only players/teams/seats/zone counts or ordered-collection POSITION
# (top_of/bottom_of), never a card's content or a board -- stay legal
# everywhere. The three sets partition the registry, pinned by
# tests/test_piece_content_walls.py so a newly registered call cannot land
# unclassified (the "vacuously green" guard) and tests/test_signatures.py.
# Derived by an audit that read every implementation; membership IS the
# classification rationale (decisions.md "Closed-domain completeness"). The
# organizing rule for the boundary: locating an OPAQUE caller-supplied token is
# generic (`player_holding` matches a card by identity; `canasta_discard_ok`'s
# card argument is unread); privileging a SPECIFIC rank/suit -- by `.rank`/
# `.suit`, `rs.rank_index`, `rs.card_values`, a point table, or an internal
# card literal (`bigtwo_first_leader` builds the 3 of diamonds) -- is deck-only.
GENERIC_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "bottom_of",
        "canasta_discard_ok",
        "canasta_red3_bonus",
        "coup_game_summary",
        "coup_next_in_game",
        "coup_players_in",
        "error",
        "five_hundred_bid_level",
        "peg_origin_of",
        "player_holding",
        "president_next_holder",
        "skat_effective_loss",
        "skat_next_bid",
        "team_of",
        "tichu_double_victory",
        "tichu_first_out",
        "tichu_next_holder",
        "tichu_opponent_team",
        "tichu_partner",
        "tichu_players_holding",
        "top_of",
    }
)

# The complement, listed explicitly (not `STDLIB_CALL_FUNCS - GENERIC...`) so
# the partition test can FAIL: a newly registered call absent from both sets is
# unclassified, and the test names it rather than silently defaulting it here.
DECK_ONLY_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "belote_best_is",
        "belote_decl_class",
        "belote_decl_height",
        "belote_decl_points",
        "belote_decl_size",
        "belote_decl_slot",
        "belote_decl_trump",
        "belote_opp_winning",
        "belote_royal_player",
        "belote_trump_height",
        "bigtwo_first_leader",
        "bring_in_seat",
        "canasta_add_ok",
        "canasta_black3_ok",
        "canasta_can_start",
        "canasta_can_take_pile",
        "canasta_canasta_bonus",
        "canasta_close_ok",
        "canasta_hand_points",
        "canasta_is_black3",
        "canasta_is_red3",
        "canasta_meld_points",
        "canasta_must_take_pile",
        "canasta_pile_rank",
        "canasta_stage_ok",
        "canasta_top_is_wild",
        "canasta_top_starts_pile",
        "card_value",
        "coup_has_char",
        "cribbage_crib_value",
        "cribbage_show_value",
        "doko_trick_winner",
        "first_to_act_seat",
        "five_hundred_bid_value",
        "five_hundred_follow_ok",
        "five_hundred_lead_ok",
        "five_hundred_next_bid",
        "five_hundred_trick_winner",
        "gin_arrange_ok",
        "gin_can_declare",
        "gin_can_declare_free",
        "gin_can_knock",
        "gin_card_points",
        "gin_deadwood",
        "gin_flat_points",
        "gin_knock_ok",
        "gin_lay_ok_a",
        "gin_lay_ok_b",
        "gin_lay_ok_c",
        "gin_shown_points",
        "gin_valid_meld",
        "peg_pair_points",
        "peg_run_points",
        "peg_value",
        "pinochle_meld_value",
        "pot_share",
        "president_is_top_rank",
        "rank_value",
        "schnapsen_trick_winner",
        "skat_follow_ok",
        "skat_matadors",
        "skat_trick_winner",
        "strain_index",
        "suit_of",
        "tarot_card_points",
        "tarot_excuse_player",
        "tarot_led_suit",
        "tarot_per_opp",
        "tarot_trump_height",
        "tichu_card_points",
        "tichu_dragon_won",
        "tichu_mahjong_holder",
    }
)

# Board-reading calls: rejected in a boardless game (no `board:` to read), the
# board twin of DECK_ONLY above. Listed explicitly (not derived by subtraction)
# so the partition test can name a newly registered board call that nobody
# classified, rather than silently absorbing it here.
BOARD_ONLY_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "lines",  # the board's length-k lines -- reads ctx.rs.board
    }
)
