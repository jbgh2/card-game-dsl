"""Runtime value types: cards, players, and the seating ring.

These are the concrete objects the interpreter manipulates — the live
counterparts to the DSL's `Card`, `Player`, and `Seating` stdlib types.
Hearts only needs a standard 52-card deck and a four-player ring.
"""

from __future__ import annotations

from dataclasses import dataclass

# Suits shared by the French-suited decks. Rank ordering is no longer a global:
# it is read per game from the `ranking:` declaration (see runtime.state /
# driver, `rank_index`), so a deck like schnapsen20 (A 10 K Q J) ranks correctly
# without a second source of truth. `Card.rank_order` is kept only as a
# convenience for standard-deck *tests*; the runtime decision path uses
# `rs.rank_index` exclusively.
SUITS: tuple[str, ...] = ("clubs", "diamonds", "hearts", "spades")
RANKS: tuple[str, ...] = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
_RANK_INDEX = {r: i for i, r in enumerate(RANKS)}


@dataclass(frozen=True, slots=True)
class Deck:
    """A named deck: the ranks each suit carries (high to low is set by the
    game's `ranking:`), the suits, and an optional card-point value table for
    point-trick games (Schnapsen, Pinochle, Tarot)."""

    suits: tuple[str, ...]
    ranks: tuple[str, ...]
    values: dict[str, int]  # rank -> card points; empty when the game scores otherwise


DECKS: dict[str, Deck] = {
    "standard52": Deck(suits=SUITS, ranks=RANKS, values={}),
    # 20-card Ace-Ten deck: J Q K 10 A in four suits, A 10 K Q J high to low.
    "schnapsen20": Deck(
        suits=SUITS,
        ranks=("J", "Q", "K", "10", "A"),
        values={"J": 2, "Q": 3, "K": 4, "10": 10, "A": 11},
    ),
}


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str

    @property
    def rank_order(self) -> int:
        """Standard-deck rank order. Convenience for tests on standard52 games;
        the runtime ranks via `rs.rank_index` instead (deck-agnostic)."""
        return _RANK_INDEX[self.rank]

    def __str__(self) -> str:
        sym = {"clubs": "♣", "diamonds": "♦", "hearts": "♥", "spades": "♠"}[self.suit]
        return f"{self.rank}{sym}"


def build_deck(deck_name: str) -> list[Card]:
    """Construct the ordered list of cards a named deck contains."""
    deck = DECKS.get(deck_name)
    if deck is None:
        raise NotImplementedError(f"deck '{deck_name}' not supported by the runtime yet")
    return [Card(rank, suit) for suit in deck.suits for rank in deck.ranks]


# A player is just an identity; the runtime uses small ints P0..P(n-1).
Player = int


@dataclass(frozen=True, slots=True)
class Seating:
    """A ring of players with directional navigation.

    `direction: clockwise` means increasing index is clockwise. The Direction
    enum values map to ring offsets; for four players `across` is the opposite
    seat.
    """

    count: int

    @property
    def players(self) -> tuple[Player, ...]:
        return tuple(range(self.count))

    def offset_by(self, player: Player, direction: str) -> Player:
        delta = {
            "none": 0,
            "left": 1,
            "right": -1,
            "across": self.count // 2,
        }[direction]
        return (player + delta) % self.count

    def left_of(self, player: Player) -> Player:
        return self.offset_by(player, "left")

    def turn_order_from(self, leader: Player) -> list[Player]:
        """Players in clockwise turn order starting at `leader`."""
        return [(leader + i) % self.count for i in range(self.count)]
