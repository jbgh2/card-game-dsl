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
        # Schnapsen lead moves (handled by the SchnapsenHand mechanic).
        "declare_marriage",
        "exchange_trump_jack",
        "close_talon",
        "claim_66",
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
        # French Tarot moves (handled by the TarotHand mechanic).
        "discard_to_chien",
        "call_poignee",
        # Cribbage moves (handled by the CribbageHand mechanic).
        "discard_to_crib",
        "play_card",
        "declare_go",
        # Seven-Card Stud moves (handled by the StudHand mechanic).
        "bring_in",
        "check",
        "call",
        "bet",
        "raise",
        "fold",
        # Tichu moves (handled by the TichuHand mechanic).
        "play_combination",
        "push_card",
        "call_tichu",
        "call_grand_tichu",
    }
)
