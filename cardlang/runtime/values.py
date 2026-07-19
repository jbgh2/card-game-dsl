"""Runtime value types: cards, players, and the seating ring.

These are the concrete objects the interpreter manipulates — the live
counterparts to the DSL's `Card`, `Player`, and `Seating` stdlib types.
Hearts only needs a standard 52-card deck and a four-player ring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
    game's `ranking:`), the suits, an optional card-point value table for
    point-trick games (Schnapsen, Pinochle), and how many copies of each card
    the deck holds (Pinochle doubles a 24-card pack into 48). A non-uniform deck
    (Tarot: suits of 14, a 21-card atout suit, the singleton Excuse) supplies an
    explicit ``cards`` list instead of the suits×ranks cross product."""

    suits: tuple[str, ...]
    ranks: tuple[str, ...]
    values: dict[str, int]  # rank -> card points; empty when the game scores otherwise
    copies: int = 1
    cards: tuple[tuple[str, str], ...] = ()  # explicit (rank, suit) list for non-uniform decks

    def __post_init__(self) -> None:
        # Exactly one representation: the suits×ranks cross product (`ranks`) or
        # an explicit non-uniform `cards` list. Setting both silently ignores
        # `ranks` (build_deck prefers `cards`), so reject it at construction.
        if bool(self.ranks) == bool(self.cards):
            raise ValueError(
                "Deck must set exactly one of `ranks` (suits×ranks cross product) "
                "or `cards` (explicit non-uniform list)"
            )


@dataclass(frozen=True, slots=True)
class ComponentSet:
    """One `cards:`/`pieces:` registry entry. `axes` bind positionally to the
    `Deck` item slots: axes[0] is the suit slot, axes[1] the rank slot."""

    flavor: Literal["card", "piece"]
    axes: tuple[str, str]
    deck: Deck

    def __post_init__(self) -> None:
        a0, a1 = self.axes
        if a0 == a1:
            raise ValueError(f"ComponentSet axes must be distinct, got {self.axes!r}")
        if not a0.isidentifier() or not a1.isidentifier():
            raise ValueError(f"ComponentSet axes must both be identifiers, got {self.axes!r}")
        if self.flavor == "piece" and self.axes == ("suit", "rank"):
            raise ValueError(
                "piece-flavored ComponentSet may not spell axes as "
                "('suit', 'rank') -- reserved for the card flavor"
            )


def _tarot78() -> tuple[tuple[str, str], ...]:
    """The 78-card Tarot pack: four 14-card suits, 21 atouts, and the Excuse."""
    suit_ranks = ("K", "Q", "C", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "1")
    cards = [(r, s) for s in SUITS for r in suit_ranks]
    cards += [(str(n), "atouts") for n in range(1, 22)]
    cards.append(("Excuse", "excuse"))
    return tuple(cards)


def _tichu56() -> tuple[tuple[str, str], ...]:
    """The 56-card Tichu pack: the standard 52 plus four special cards."""
    cards = [(r, s) for s in SUITS for r in RANKS]
    cards += [(name, "special") for name in ("Mahjong", "Dog", "Phoenix", "Dragon")]
    return tuple(cards)


def _five_hundred43() -> tuple[tuple[str, str], ...]:
    """The 43-card Australian 500 pack: the black suits keep A..5 (10 cards),
    the red suits A..4 (11), plus the single joker — its own suit and rank,
    like Tarot's Excuse."""
    black = ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5")
    red = black + ("4",)
    cards = [(r, s) for s in SUITS for r in (red if s in ("diamonds", "hearts") else black)]
    cards.append(("Joker", "joker"))
    return tuple(cards)


def _canasta108() -> tuple[tuple[str, str], ...]:
    """The 108-card Canasta pack: two standard 52-card packs plus four jokers.
    An explicit list rather than `copies=2` because the jokers sit outside the
    suits×ranks cross product (their own `joker` suit, like Tichu's
    `special`); the two standard copies are spelled by repetition, so the
    deck genuinely holds duplicate identical Card values (the pinochle48
    precedent — zones are multisets)."""
    cards = [(r, s) for _ in range(2) for s in SUITS for r in RANKS]
    cards += [("Joker", "joker")] * 4
    return tuple(cards)


COMPONENT_SETS: dict[str, ComponentSet] = {
    "standard52": ComponentSet("card", ("suit", "rank"), Deck(suits=SUITS, ranks=RANKS, values={})),
    # 20-card Ace-Ten deck: J Q K 10 A in four suits, A 10 K Q J high to low.
    "schnapsen20": ComponentSet(
        "card",
        ("suit", "rank"),
        Deck(
            suits=SUITS,
            ranks=("J", "Q", "K", "10", "A"),
            values={"J": 2, "Q": 3, "K": 4, "10": 10, "A": 11},
        ),
    ),
    # 48-card Pinochle pack: two copies of A 10 K Q J 9 per suit. Counters
    # (A, 10, K) are worth 10 trick points each; the rest score 0.
    "pinochle48": ComponentSet(
        "card",
        ("suit", "rank"),
        Deck(
            suits=SUITS,
            ranks=("A", "10", "K", "Q", "J", "9"),
            values={"A": 10, "10": 10, "K": 10, "Q": 0, "J": 0, "9": 0},
            copies=2,
        ),
    ),
    # 48-card Doppelkopf pack: the Pinochle composition (two copies of
    # A 10 K Q J 9 per suit) under Ace-Ten values (240 card points total).
    "doppelkopf48": ComponentSet(
        "card",
        ("suit", "rank"),
        Deck(
            suits=SUITS,
            ranks=("A", "10", "K", "Q", "J", "9"),
            values={"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0},
            copies=2,
        ),
    ),
    # 32-card Skat pack: A 10 K Q J 9 8 7 per suit (Ace-Ten values, 120 total).
    "skat32": ComponentSet(
        "card",
        ("suit", "rank"),
        Deck(
            suits=SUITS,
            ranks=("A", "10", "K", "Q", "J", "9", "8", "7"),
            values={"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0},
        ),
    ),
    # 78-card Tarot pack (non-uniform). Card values vary by rank AND suit, so the
    # value table is left empty and the Tarot mechanic computes points itself.
    "tarot78": ComponentSet("card", ("suit", "rank"), Deck(suits=SUITS, ranks=(), values={}, cards=_tarot78())),
    # 56-card Tichu pack: standard 52 plus Mahjong, Dog, Phoenix, Dragon.
    "tichu56": ComponentSet("card", ("suit", "rank"), Deck(suits=SUITS, ranks=(), values={}, cards=_tichu56())),
    # 43-card Australian 500 pack (non-uniform): A..5 black, A..4 red, one joker.
    "five_hundred43": ComponentSet(
        "card", ("suit", "rank"), Deck(suits=SUITS, ranks=(), values={}, cards=_five_hundred43())
    ),
    # 108-card Canasta pack: two standard 52s plus four jokers. No `values`
    # table: Canasta's card points are a scoring fact of the game, held in
    # its game-local primitive (cardlang/runtime/canasta.py), not a deck
    # property — the deck is also used with other point tables in principle.
    "canasta108": ComponentSet(
        "card", ("suit", "rank"), Deck(suits=SUITS, ranks=(), values={}, cards=_canasta108())
    ),
    # 15-card Coup deck: five characters (the "rank") under one suit, three each.
    "coup15": ComponentSet(
        "card",
        ("suit", "rank"),
        Deck(
            suits=("court",),
            ranks=("Duke", "Assassin", "Captain", "Ambassador", "Contessa"),
            values={},
            copies=3,
        ),
    ),
    "xo_marks": ComponentSet(
        "piece",
        ("side", "kind"),
        Deck(suits=(), ranks=(), values={}, cards=(("mark", "x"),) * 5 + (("mark", "o"),) * 4),
    ),
}

# The card-flavored projection every pre-existing deck consumer reads;
# a piece set never appears here.
DECKS: dict[str, Deck] = {
    name: cs.deck for name, cs in COMPONENT_SETS.items() if cs.flavor == "card"
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
        sym = {
            "clubs": "♣",
            "diamonds": "♦",
            "hearts": "♥",
            "spades": "♠",
            "atouts": "★",
            "excuse": "☆",
        }.get(self.suit, f":{self.suit}")
        return f"{self.rank}{sym}"


@dataclass(frozen=True, slots=True)
class CardSet:
    """A joint-selection candidate: one subset of a movement's source pool
    (`where jointly` — decisions.md "Joint-predicate selection"). Exposes
    `.cards` because that is the runtime's convention for set-valued
    decision candidates (a climb `Play` does the same), which is what the
    OpenSpiel encoder's combo block and `match()` key on."""

    cards: tuple[Card, ...]

    def __str__(self) -> str:
        return "{" + ",".join(str(c) for c in self.cards) + "}"


def component_set(name: str) -> ComponentSet | None:
    """The named component set (a card deck or a piece set), or None if the
    registry has no entry under that name."""
    return COMPONENT_SETS.get(name)


def build_deck(deck_name: str) -> list[Card]:
    """Construct the ordered list of `Card`-shaped items a named component
    set contains -- a deck's cards, or a piece set's pieces (represented the
    same way; see `ComponentSet`)."""
    cs = component_set(deck_name)
    if cs is None:
        raise NotImplementedError(
            f"component set '{deck_name}' not supported by the runtime yet — "
            f"known component sets: {', '.join(sorted(COMPONENT_SETS))}"
        )
    deck = cs.deck
    if deck.cards:  # explicit-list form
        return [Card(rank, suit) for rank, suit in deck.cards]
    return [
        Card(rank, suit)
        for _ in range(deck.copies)
        for suit in deck.suits
        for rank in deck.ranks
    ]


def deck_suits(deck_name: str) -> tuple[str, ...]:
    """A deck's DISTINCT card suits, in first-appearance order — read from the
    actual card block (`build_deck`), never the declared `Deck.suits` field.
    `Deck.suits` alone is wrong for a non-uniform deck: tarot78 and tichu56
    both declare the French `suits=SUITS`, but their real `cards` carry extra
    suits `build_deck` iterates too (tarot78's "atouts"/"excuse", tichu56's
    "special") that `Deck.suits` never lists. This is the ONE source both
    `driver.py`'s `rs.suits` (the runtime move-parameter domain) and
    `cardlang.openspiel.encoding.ActionSpace.for_game` (the advertised action
    space) derive from, so the two can never diverge (mirrors how the Rank
    domain is unified on `game.ranking`)."""
    return tuple(dict.fromkeys(c.suit for c in build_deck(deck_name)))


def deck_ranks(deck_name: str) -> tuple[str, ...]:
    """A deck's DISTINCT card ranks, in first-appearance order — read from the
    actual card block like `deck_suits` (the declared `Deck.ranks` field is
    empty for the explicit-card decks, tarot78/tichu56). This is the rank
    namespace for games with no `ranking:` (Coup's characters, Tarot's
    atouts); a declared `ranking:` refines the *order*, never the membership."""
    return tuple(dict.fromkeys(c.rank for c in build_deck(deck_name)))


def _reranked(*top: str, bottom: str | None = None) -> tuple[str, ...]:
    """The French ranks strongest-first with the named ranks moved: `top` in
    the given order at the head, `bottom` at the tail, everything else in
    aces-high order between. Every template derives from the ONE `RANKS`
    tuple above — a convention is never a second spelling of the rank set."""
    moved = set(top) | ({bottom} if bottom is not None else set())
    rest = [r for r in reversed(RANKS) if r not in moved]
    return top + tuple(rest) + ((bottom,) if bottom is not None else ())


# The named ranking conventions `ranking:` accepts in place of an enumeration
# (decisions.md, "The `ranking:` declaration: enumeration or convention"). Keys are the
# exact surface spellings (single-spaced); values are the full French order,
# strongest first. A game's operative ranking is the template FILTERED to its
# deck's ranks (`expand_ranking_convention`), so one convention serves every
# French-ranked deck: `aces high` means A K Q J 10 … on standard52 and
# A K Q J 10 9 8 7 on skat32. `ace-ten` (the Ace-Ten family: Skat, Schnapsen,
# Pinochle, Doppelkopf, Belote non-trump) promotes the 10 between A and K;
# `twos high` is the climbing-game order (President). The grammar's RANK_CONV
# terminal and this registry are reconciled by
# tests/test_ranking_conventions.py — a key the grammar cannot parse, or a
# parseable spelling with no key here, fails statically.
RANKING_CONVENTIONS: dict[str, tuple[str, ...]] = {
    "aces high": _reranked(),
    "aces low": _reranked(bottom="A"),
    "ace-ten": _reranked("A", "10"),
    "twos high": _reranked("2"),
}


def expand_ranking_convention(convention: str, deck_name: str) -> tuple[str, ...]:
    """A convention's operative ranking for a deck: the template filtered to
    the deck's real ranks, order preserved. Total for every deck whose ranks
    are all French — the resolver walls the rest (`resolve.py::
    _expand_ranking`) before this runs, so filtering can never silently drop
    a deck rank."""
    members = set(deck_ranks(deck_name))
    return tuple(r for r in RANKING_CONVENTIONS[convention] if r in members)


# A player is just an identity; the runtime uses small ints P0..P(n-1).
Player = int

# The closed value set of the game-level `direction:` clause (grammatically a
# bare NAME). resolve's `_resolve_direction` walls membership; `driver.py`
# maps the value onto `Seating.clockwise`. An omitted clause means clockwise.
GAME_DIRECTIONS: tuple[str, ...] = ("clockwise", "counterclockwise")


@dataclass(frozen=True, slots=True)
class Seating:
    """A ring of players with directional navigation.

    `direction: clockwise` means increasing index is clockwise, so the turn-order
    ring advances by +1; `counterclockwise` advances by -1. `offset_by left`/
    `right` are absolute (+1 / -1) in either ring; for four players `across` is
    the opposite seat.
    """

    count: int
    clockwise: bool = True

    @property
    def players(self) -> tuple[Player, ...]:
        return tuple(range(self.count))

    def offset_by(self, player: Player, direction: str) -> Player:
        delta = {
            "hold": 0,
            "left": 1,
            "right": -1,
            "across": self.count // 2,
        }[direction]
        return (player + delta) % self.count

    def left_of(self, player: Player) -> Player:
        return self.offset_by(player, "left")

    def turn_order_from(self, leader: Player) -> list[Player]:
        """Players in turn order from `leader`, following the game's direction:
        +1 per seat clockwise, -1 counterclockwise."""
        step = 1 if self.clockwise else -1
        return [(leader + i * step) % self.count for i in range(self.count)]
