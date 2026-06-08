"""Action encoding for the Hearts OpenSpiel adapter.

Hearts decisions are all single-card selections (the 3-card pass decomposes into
three sequential single-card actions), so the action space is exactly the 52
cards: ``action_id = suit_index * 13 + rank_index``.
"""

from __future__ import annotations

from cardlang.runtime.values import RANKS, SUITS, Card

NUM_DISTINCT_ACTIONS = len(SUITS) * len(RANKS)  # 52


def card_to_action(card: Card) -> int:
    return SUITS.index(card.suit) * len(RANKS) + RANKS.index(card.rank)


def action_to_card(action: int) -> Card:
    if not 0 <= action < NUM_DISTINCT_ACTIONS:
        raise ValueError(f"action {action} out of range 0..{NUM_DISTINCT_ACTIONS - 1}")
    return Card(RANKS[action % len(RANKS)], SUITS[action // len(RANKS)])
