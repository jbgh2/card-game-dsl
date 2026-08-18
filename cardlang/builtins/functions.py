"""Native function and value-callback names, by the home that implements each.

The name resolver checks bare-name references (a [[round]]'s [[winner]] /
`outcome` / `early` function, a climbing round's `combinations` / `follows`
query) and `f(...)` calls against these sets, so the IR can mark them as
functions and unknown names are caught. There is no zone-method namespace here:
the expression layer has no method register (decisions.md "The expression
register"). Seeded for the formalized corpus; extended corpus-first.

`BUILTIN_*` names a generic function the language ships ([[builtins]]);
`PRIMITIVE_*` names sanctioned game-local Python ([[primitive]]; issue #200).
Nothing here is the **[[stdlib]]**, which is the layer written in the language
(`cardlang/stdlib/`).
"""

from __future__ import annotations

# Value callbacks referenced by bare name (a `round`'s `winner` or `outcome`
# callback). The two round forms yield different things and are validated
# against separate namespaces (a trick winner function named on an auction round, or
# vice versa, is rejected at resolve time, not left to crash the dispatcher at
# runtime):
#
# - a *trick* winner function, under one of TWO contracts keyed by
#   `TRICK_ORDER_GATED_WINNERS` below and dispatched by the one
#   `runtime/primitives.py::value_function`:
#     * the uniform contract, (played, led_suit, trump, rank_index) -> Player,
#       which every winner that reads the ROUND's configuration answers (which
#       members READ `trump` is `TRUMP_READING_WINNERS` below, and which read
#       `rank_index` is typecheck's `RANKING_GATED_WINNERS`);
#     * the Trick Order contract, (played, ctx) -> Player, which the gated
#       winner answers because its led suit, its trumps and its strengths are
#       the GAME's `trick_order { }` rows, materialized once at load, not the
#       round's arguments (`runtime/trick_order.py::TrickOrderWinner`).
#   Two contracts rather than a fifth argument on one: handing a live Ctx to
#   every game-local winner would widen what a Primitive may read, against the
#   narrowing contract (issue #200).
# - an *auction* outcome function: (history, ctx) -> (tag, payloads), producing the
#   phase's typed outcome.
#
# A name has ONE home, and the home is its CLASSIFICATION — generic
# (Builtin) or game-local (Primitive) — never its syntactic position: the
# registry's own first line draws the Builtin/Primitive split by genericity,
# and the two standard trick comparisons are the language's, not any game's
# (Bridge, Hearts, Spades, Oh Hell, and the Getaway/Schnapsen forms all name
# them). They were filed under PRIMITIVE_TRICK_WINNERS from before the split
# was drawn; the `highest_trump_or_led_suit` CALL form (issue #256) is what
# forced the finer cut, because one name would otherwise have sat in both
# halves. Both sets validate the winner slot through their union below.
BUILTIN_TRICK_WINNERS: frozenset[str] = frozenset(
    {
        "highest_of_led_suit",  # the standard no-trump trick winner
        "highest_trump_or_led_suit",  # trick winner with a trump suit in play
        "highest_by_trick_order",  # the winner of a game's declared Trick Order
    }
)
PRIMITIVE_TRICK_WINNERS: frozenset[str] = frozenset(
    {
        "tarot_trick_winner",  # French Tarot: highest atout else led suit; Excuse never wins
        "belote_trick_winner",  # Belote: highest trump under the J-9 trump order, else led suit
    }
)
# The winner slot's namespace: what a `round … winner <name>` may name.
TRICK_WINNER_NAMES: frozenset[str] = BUILTIN_TRICK_WINNERS | PRIMITIVE_TRICK_WINNERS
# The winners whose BODY reads the `trump` argument of the winner contract
# above. The other half accepts the argument and ignores it (a no-trump
# winner, and Tarot's, whose atouts are its own suit), so a `trump` clause
# on one of those -- the round's own, or the game-level `trump:` it would
# inherit -- would be accepted and silently dropped: resolve refuses both
# shapes against this set (the winner-slot arm of `_validate_refs`, and
# `_resolve_trump`'s dead-clause guard). Classification by body, not name:
# tests/test_trump_slot_class.py executes every registered winner on one
# pile with and without a trump and reconciles this set against the answer,
# so a winner filed on the wrong side fails there. A new winner not listed
# here is treated as trump-blind -- its trump clause is REFUSED, loudly,
# rather than admitted on trust.
# `highest_by_trick_order` is deliberately NOT a member: its trumps are the
# game's `trick_order { trump: ... }` row, not the round's `trump` argument,
# which it never receives (the other contract). A round `trump` clause beside
# it is refused by the presence partition (`_check_trick_order_partition`, R2),
# whose message names the block -- so the two guards divide the case rather
# than co-reporting on it.
TRUMP_READING_WINNERS: frozenset[str] = frozenset(
    {"highest_trump_or_led_suit", "belote_trick_winner"}
)

PRIMITIVE_AUCTION_OUTCOMES: frozenset[str] = frozenset(
    {
        "bridge_auction_outcome",  # Bridge auction -> contract_finalized | all_pass
        "pinochle_auction_outcome",  # Pinochle ascending auction -> bid_won
        "tarot_auction_outcome",  # French Tarot four-level bid -> taken | thrown_in
    }
)
# The union is the bare-name function namespace (for NameRef classification)
# and the surface the signature tables must cover — every slot callback of
# EITHER home, which is why it carries neither home's prefix (it was
# `PRIMITIVE_VALUE_NAMES` while every member was a Primitive; a Builtin
# member under that prefix would mislabel by name — the CALL_FUNCS pattern,
# the neutral union of the two homes' call sets, is the precedent).
VALUE_NAMES: frozenset[str] = TRICK_WINNER_NAMES | PRIMITIVE_AUCTION_OUTCOMES

# Early-termination predicates a `round`'s `early` clause may name. Distinct from
# the callbacks above — a different signature, (card, led_suit) -> Boolean —
# so they validate against their own set, not the winner/outcome namespaces.
# Slot-only, deliberately outside VALUE_NAMES: an early predicate is
# unreachable as a bare NameRef and rejected in a `winner` slot, even though
# the runtime dispatches both through `value_function`. Sharing the dispatcher
# is an implementation detail of the runtime, not a shared namespace.
PRIMITIVE_EARLY_PREDICATES: frozenset[str] = frozenset(
    {
        "on_play_off_led_suit",  # an off-led-suit play ends the trick (Getaway's tochoo)
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
PRIMITIVE_CLIMB_LEADS: frozenset[str] = frozenset(
    {
        "bigtwo_lead_options",  # Big Two: every combination (3♦-filtered on the opening lead)
        "tichu_lead_options",  # Tichu: every combination + the special-card lead singles
        "president_lead_options",  # President: every equal-rank set of 1-4 cards
    }
)
PRIMITIVE_CLIMB_FOLLOWS: frozenset[str] = frozenset(
    {
        "bigtwo_follows",  # Big Two: combinations that beat the standing play (same size)
        "tichu_follows",  # Tichu: same kind/length and higher, any bomb, Dragon/Phoenix answers
        "president_follows",  # President: same-size higher-rank sets + transparent threes
    }
)

# Native functions invoked with arguments: `f(...)`, declared in two sets by
# the home that implements each (issue #200's ruling; the implementation split
# is `runtime/builtins.py` vs `runtime/primitives.py`). Stated as two sets
# rather than one union plus a hand-listed half, so the declaration side can
# SAY which home a name belongs to: the arm-home grid
# (tests/test_native_dispatch_split.py) reads its expected column from here
# rather than restating it, and a new call landing in neither set is a name
# resolve refuses rather than a name that quietly defaults to game-local.

# BUILTINS — generic: the meaning is the language's, not one game's.
BUILTIN_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "lines",  # the board's length-k lines (cell-name tuples); reads the `board:`
        "neighbor",  # rung-2 movement: the cell one step along a dir in a player's frame
        "has_step",  # rung-2 movement: whether that step stays on the board (gates neighbor)
        "is_diagonal",  # rung-2 movement: whether a dir captures (changes file)
        "home",  # rung-2 movement: a player's back-two-ranks setup region (Collection<Cell>)
        "far_row",  # rung-2 movement: the opponent's back row, the reach-to-win goal
        "player_holding",
        "team_of",  # the team a player belongs to
        "suit_of",  # the suit of a card, or of a single-card zone (trump indicator)
        "strain_index",  # bidding rank of a strain: C<D<H<S<NT (none = no-trump, highest)
        "error",  # the if_impossible fallback that rejects the move
        "rank_value",  # a card's rank strength under the game's `ranking:` (higher = stronger)
        "card_points",  # a card's points under the game's `card_points { }` table
        "top_of",  # the top card of an ordered zone/collection (the sequence end)
        "bottom_of",  # the bottom card of an ordered zone/collection (the sequence front)
        # The standard trump-game trick winner, callable over a fully public
        # pile's Arrival Record (issue #256) — the SAME Builtin winner the
        # trick form's `winner` clause names bare (BUILTIN_TRICK_WINNERS
        # above), in its second position: one name, one home, two syntactic
        # positions, each resolved against its own namespace.
        "highest_trump_or_led_suit",
        # The Trick Order's surface (decisions.md "Trick Order"; issue #250).
        # The three READERS the language mints from the block's rows -- one per
        # row, each a fact of the card alone; and the two Builtins over the
        # whole declaration: the winner (also in BUILTIN_TRICK_WINNERS above,
        # the same two-position shape as `highest_trump_or_led_suit`) and the
        # candidate test the winner uses, made callable so a follow filter can
        # ask it. All five are gated on the block's presence in BOTH directions
        # (`TRICK_ORDER_GATED_FUNCS`).
        "is_trump",
        "follow_class",
        "card_strength",
        "highest_by_trick_order",
        "follows_lead",
    }
)

# PRIMITIVES — game-local: sanctioned Python whose meaning belongs to one game.
# This set is the elimination metric's declaration side; it shrinks as
# `design-notes/primitive-inventory.md`'s constructs land in the language.
PRIMITIVE_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "bring_in_seat",  # Stud: the lowest-door seat that posts the bring-in
        "first_to_act_seat",  # Stud: the highest-upcards seat that acts first on a street
        "pot_share",  # Stud: the chips a player collects at showdown (side-pot layering)
        "holdem_pot_share",  # Hold'em: the chips a player collects at showdown (side-pot layering)
        "holdem_heads_up_pot_share",  # Heads-up Hold'em: the same query, against its own declared-reads row
        "pinochle_meld_value",  # Pinochle: a player's hand's meld points under the declared trump
        "tarot_led_suit",  # French Tarot: the effective led suit (first non-Excuse card) in play
        "tarot_trump_height",  # French Tarot: an atout's rank strength (0 for a non-atout)
        "tarot_excuse_player",  # French Tarot: who played the Excuse in the trick just completed
        "tarot_per_opp",  # French Tarot: the zero-sum per-opponent settlement amount
        "skat_next_bid",  # Skat: the next Reizen ladder value (0 = exhausted)
        "skat_follow_ok",  # Skat: follow-class legality (jacks + trump suit are one class)
        "skat_trick_winner",  # Skat: the three-card trick's winner under the contract
        "skat_matadors",  # Skat: the with/without matador count (hand + skat)
        "doko_trick_winner",  # Doppelkopf: the four-card trick's winner (first of equals)
        "tichu_dragon_won",  # Tichu: did the Dragon capture the trick just completed?
        "coup_game_summary",  # Coup: emit the conservation/finals trace at game end
        "peg_pair_points",  # Cribbage: pairs points at the tail of the live pegging count
        "peg_run_points",  # Cribbage: run points at the tail of the live pegging count
        "peg_origin_of",  # Cribbage: which player played a live pegging-pile card
        "cribbage_show_value",  # Cribbage: a player's pegged hand's show score
        "cribbage_crib_value",  # Cribbage: the dealer's crib show score
        "gin_deadwood",  # Gin: optimal-partition deadwood of a hand
        "gin_can_knock",  # Gin: some discard leaves a <= 10 arrangement
        "gin_knock_ok",  # Gin: knock legality after a specific discard
        "gin_valid_meld",  # Gin: joint meld validity (set / ace-low run)
        "gin_arrange_ok",  # Gin: valid meld AND the rest still arranges to <= 10
        "gin_can_declare",  # Gin: some declarable meld exists (knocker)
        "gin_can_declare_free",  # Gin: some valid meld exists (defender)
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
        "canasta_can_take_pile",  # Canasta: a complete legal pile take exists
        "canasta_must_take_pile",  # Canasta: the no-stock forced take applies
        "canasta_can_start",  # Canasta: a new meld of the rank is completable from hand
        "canasta_stage_ok",  # Canasta: card joins the open attempt, close stays reachable
        "canasta_close_ok",  # Canasta: the open attempt closes legally as it stands
        "canasta_canasta_bonus",  # Canasta: 500 per natural / 300 per mixed canasta
    }
)

# The whole call namespace: what resolve accepts as a known `f(...)` name, and
# the surface CALL_SIGS must cover. DERIVED from the two homes, so a name can
# never be in the namespace without a home having claimed it.
CALL_FUNCS: frozenset[str] = BUILTIN_CALL_FUNCS | PRIMITIVE_CALL_FUNCS


# --- The Trick Order (decisions.md "Trick Order"; issue #250) ----------------
#
# The game-level `trick_order { }` block declares three per-card facts -- is
# the card a trump, what class does it follow as, how strong is it within its
# class -- and the language mints one reader per row plus two Builtins over
# the declaration. These tables are the ONE source for: which rows exist
# (parse, resolve, typecheck, IR and the diagnostics all render from it),
# which names the block gates, and which names it excludes.

# row key -> the reader the language mints from it. The tuple ORDER is the
# language's reference order: a row may read the readers of the rows BEFORE
# it and no others, whatever order the rows are written in (resolve, R8).
# A row's required body type is `CALL_SIGS[reader].ret` -- stated once there.
TRICK_ORDER_ROWS: tuple[tuple[str, str], ...] = (
    ("trump", "is_trump"),
    ("follow_class", "follow_class"),
    ("card_strength", "card_strength"),
)
TRICK_ORDER_ROW_KEYS: tuple[str, ...] = tuple(k for k, _ in TRICK_ORDER_ROWS)
TRICK_ORDER_READERS: tuple[str, ...] = tuple(r for _, r in TRICK_ORDER_ROWS)

# The winner that reads the block, and the whole surface the block gates. Both
# directions of the presence partition key on these: with a block, everything
# OUTSIDE them is refused; without one, everything INSIDE them is.
TRICK_ORDER_GATED_WINNERS: frozenset[str] = frozenset({"highest_by_trick_order"})
TRICK_ORDER_GATED_FUNCS: frozenset[str] = frozenset(
    {"highest_by_trick_order", "follows_lead"}
) | frozenset(TRICK_ORDER_READERS)
# The complements, BY SUBTRACTION: a winner or call added to the language later
# lands on the excluded side automatically rather than being silently admitted
# beside a block by an out-of-date hand-listing.
TRICK_ORDER_EXCLUDED_WINNERS: frozenset[str] = TRICK_WINNER_NAMES - TRICK_ORDER_GATED_WINNERS
TRICK_ORDER_EXCLUDED_FUNCS: frozenset[str] = (
    BUILTIN_TRICK_WINNERS & BUILTIN_CALL_FUNCS
) - TRICK_ORDER_GATED_FUNCS

# What a Trick Order row may call. A row is HERMETIC -- a pure function of the
# card and public state, asked from the legality filter, the winner slot and a
# hand-rolled body under different live frames -- so the callable surface is an
# ALLOW-LIST, and its complement is listed explicitly rather than derived, so a
# newly registered Builtin lands unclassified and the partition test names it
# (tests/test_trick_order.py::test_row_callable_partition_is_total) instead of
# being absorbed silently into either side. Every `PRIMITIVE_CALL_FUNCS` member
# is uncallable by construction (a row calls no game-local Python), which is
# why only the Builtin half is partitioned here.
TRICK_ORDER_ROW_CALLS: frozenset[str] = frozenset(
    {
        "rank_value",  # the declared `ranking:` order -- what strength defaults to
        "card_points",  # the declared `card_points { }` table
        "suit_of",  # the suit of its card argument
        "strain_index",  # a strain's bidding rank (pure over the argument)
        "team_of",  # the seating's team map (public, fixed)
        "top_of",  # a position read of the collection its argument names
        "bottom_of",
    }
)
TRICK_ORDER_ROW_UNCALLABLE: frozenset[str] = frozenset(
    {
        "player_holding",  # walks every hand -- a concealed read the argument does not name
        "error",  # not a value: a row is a fact, and may not refuse a move
        "lines",  # the board verbs: a Trick Order orders a deck, not a board
        "neighbor",
        "has_step",
        "is_diagonal",
        "home",
        "far_row",
        "highest_trump_or_led_suit",  # the standard winner, excluded beside a block anyway
        "highest_by_trick_order",  # a consumer: reads every row of the order it would define
        "follows_lead",  # a consumer, likewise
    }
)

# The calls that read a pile's [[arrival-record]], name -> the index of the
# PILE argument. One registry beneath three consumers: resolve's static
# pile-argument guard (`_check_arrival_record_pile_args`), the identity hoist
# that guard performs, and the proof harness's provenance derivation
# (tests/openspiel_ready/harness.py), which walks the checked AST for these
# calls rather than reading a hand-listed zone name off each game's row.
# Every member is in `BUILTIN_CALL_FUNCS` with a `TAny` parameter at its index
# (the runtime needs the Zone handle, not coerced elements) -- pinned by
# tests/test_native_call_boundary.py.
ARRIVAL_RECORD_CALLS: dict[str, int] = {
    "highest_by_trick_order": 0,
    "follows_lead": 1,
    "highest_trump_or_led_suit": 0,
}

# The `early` predicates admitted beside a Trick Order winner: none. An early
# predicate reads the LITERAL led suit, and a Trick Order's follow class may
# differ from it (a class-remapped trump, a class-less Excuse), so the two
# would disagree about when a trick ends. Empty rather than absent so the
# refusal is a subtraction from `PRIMITIVE_EARLY_PREDICATES` -- a predicate
# added later is refused beside the block until someone puts it here with a
# witness (issue #250 PR 1, ruled point 6).
TRICK_ORDER_EARLY_PREDICATES: frozenset[str] = frozenset()



# The classification of every CALL_FUNCS member by the game feature its
# semantics READ. A call that reads a card's suit or rank, the ranking order,
# card-point values, or follow/trump/lead machinery cannot mean anything in a
# piece game (no suit/rank/points), so it is a resolve-time FLAVOR Owner Guard
# (DECK_ONLY_CALL_FUNCS); a call that reads the `board:` entry cannot mean
# anything in a boardless game, so it is a resolve-time BOARD Owner Guard
# (BOARD_ONLY_CALL_FUNCS -- the deck-only classification's board twin, keyed on
# `game.board is None` rather than the flavor); ANY_FLAVOR_CALL_FUNCS -- functions
# This partition is ORTHOGONAL to the Builtin/Primitive split above and does not
# refine it: it asks which game FLAVORS a call can mean anything in, not whose
# meaning it carries. Most of ANY_FLAVOR_CALL_FUNCS is game-named but
# content-blind (`skat_next_bid` reads only the standing bid, never a card),
# so it is a Primitive that is nonetheless legal in a piece game.
# that touch only players/teams/seats/zone counts or ordered-collection POSITION
# (top_of/bottom_of), never a card's content or a board -- stay legal
# everywhere. The three sets partition the registry, pinned by
# tests/test_piece_content_guards.py so a newly registered call cannot land
# unclassified (the "vacuously green" guard) and tests/test_signatures.py.
# Derived by an audit that read every implementation; membership IS the
# classification rationale (decisions.md "Closed-domain completeness"). The
# organizing rule for the boundary: locating an OPAQUE caller-supplied token is
# generic (`player_holding` matches a card by identity); privileging a
# SPECIFIC rank/suit -- by `.rank`/
# `.suit`, `rs.rank_index`, `rs.card_points`, a point table, or an internal
# card literal -- is deck-only.
ANY_FLAVOR_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "bottom_of",
        "coup_game_summary",
        "error",
        "five_hundred_bid_level",
        "peg_origin_of",
        "player_holding",
        "skat_next_bid",
        "team_of",
        "top_of",
    }
)

# The complement, listed explicitly (not `CALL_FUNCS - GENERIC...`) so
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
        "bring_in_seat",
        "canasta_can_start",
        "canasta_can_take_pile",
        "canasta_canasta_bonus",
        "canasta_close_ok",
        "canasta_must_take_pile",
        "canasta_stage_ok",
        "card_points",
        "card_strength",
        "cribbage_crib_value",
        "cribbage_show_value",
        "doko_trick_winner",
        "first_to_act_seat",
        "five_hundred_bid_value",
        "five_hundred_follow_ok",
        "five_hundred_lead_ok",
        "five_hundred_next_bid",
        "five_hundred_trick_winner",
        "follow_class",
        "follows_lead",
        "gin_arrange_ok",
        "gin_can_declare",
        "gin_can_declare_free",
        "gin_can_knock",
        "gin_deadwood",
        "gin_knock_ok",
        "gin_lay_ok_a",
        "gin_lay_ok_b",
        "gin_lay_ok_c",
        "gin_valid_meld",
        "highest_by_trick_order",
        "highest_trump_or_led_suit",
        "holdem_heads_up_pot_share",
        "holdem_pot_share",
        "is_trump",
        "peg_pair_points",
        "peg_run_points",
        "pinochle_meld_value",
        "pot_share",
        "rank_value",
        "skat_follow_ok",
        "skat_matadors",
        "skat_trick_winner",
        "strain_index",
        "suit_of",
        "tarot_excuse_player",
        "tarot_led_suit",
        "tarot_per_opp",
        "tarot_trump_height",
        "tichu_dragon_won",
    }
)

# Board-reading calls: rejected in a boardless game (no `board:` to read), the
# board twin of DECK_ONLY above. Listed explicitly (not derived by subtraction)
# so the partition test can name a newly registered board call that nobody
# classified, rather than silently absorbing it here.
BOARD_ONLY_CALL_FUNCS: frozenset[str] = frozenset(
    {
        "lines",  # the board's length-k lines -- reads ctx.rs.board
        "neighbor",  # the destination cell one step along a dir -- reads ctx.rs.board
        "has_step",  # whether a step stays on the board -- reads ctx.rs.board
        "is_diagonal",  # whether a dir captures -- reads the board's direction data
        "home",  # a player's home region -- reads ctx.rs.board
        "far_row",  # the far rank (reach goal) -- reads ctx.rs.board
    }
)
