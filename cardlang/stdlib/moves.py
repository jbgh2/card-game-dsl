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
        # Skat moves (handled by the SkatHand mechanic).
        "bid",
        "yes",
        "pick_up_skat",
        "declare_hand",
        "declare_suit_diamonds",
        "declare_suit_hearts",
        "declare_suit_spades",
        "declare_suit_clubs",
        "declare_grand",
        "declare_null",
        "play_at_eighteen",
        "throw_in",
        # Seven-Card Stud's betting moves (check/bet/call/raise/fold) are
        # game-defined `move_type`s in seven-card-stud.cardlang, not library moves.
        # Tichu moves (handled by the TichuHand mechanic).
        "play_combination",
        "push_card",
        "call_tichu",
        "call_grand_tichu",
        # Coup moves (handled by the CoupGame mechanic).
        "income",
        "foreign_aid",
        "coup",
        "tax",
        "assassinate",
        "steal",
        "exchange",
        "challenge",
        "block",
    }
)
