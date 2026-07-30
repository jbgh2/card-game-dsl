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
        "submit_bid",  # a player names a number (Spades/Oh Hell bidding)
        # Schnapsen's lead moves (play_card / declare_marriage / exchange_trump_jack /
        # close_talon) are game-defined `move_type`s in schnapsen.cardlang, not
        # library moves — like Seven-Card Stud's betting moves below.
        # Auction moves (handled by the auction mechanics).
        "pass",
        "declare_trump_suit",
        "double",
        "redouble",
        # Skat's Reizen/declaration moves (bid / yes / pass / play_at_eighteen /
        # throw_in / pick_up_skat / declare_hand / choose_suit_game /
        # declare_grand / declare_null / declare_suit) are game-defined
        # `move_type`s in skat.cardlang, not library moves.
        # Seven-Card Stud's betting moves (check/bet/call/raise/fold) are
        # game-defined `move_type`s in seven-card-stud.cardlang, not library moves.
        # The climbing games' shared play (Big Two, Tichu): one combination per
        # `round climb` step. Tichu's push is a chosen movement and its calls
        # are rng-gated primitives, so neither carries a move type.
        "play_combination",
        # Coup's seven actions (income / foreign_aid / coup / tax / assassinate /
        # steal / exchange) are game-defined `move_type`s in coup.cardlang, not
        # library moves; challenging and blocking are rng-gated windows at the
        # migrated scope, not moves.
    }
)

# The ONE move type rule enforcement runs for. `rules.legal_cards` has a single
# caller (the trick form's card decision), which passes this; every other
# decision site computes its candidates without consulting rules at all. Named
# here, and read by BOTH the caller and the resolver's reachability wall, so
# the wall cannot drift from the consumer it describes: widening enforcement to
# another decision site is one edit here plus the site, and the wall follows.
# Which sites should eventually enforce rules is
# docs/open-questions/rule-scope-beyond-trick-play.md.
RULE_ENFORCED_MOVE_TYPE: str = "play_to_trick"
