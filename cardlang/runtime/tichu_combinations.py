"""The Tichu combination engine (shared, RNG-free).

The enumeration of every combination a hand can form, the legal follows over
a standing play, and the rank table. `KINDS` is the registry of combination
kinds and their structure; `_combos` is complete against it, which
tests/test_tichu_combinations.py holds it to with an independent validator
(the oracle never calls the code it judges) over every subset of sampled
hands.

The rules the engine implements (Fata Morgana English edition):

- Singles, pairs, triples, full houses (a triple with a pair), straights of at
  least five consecutive ranks, and consecutive pairs of at least two ranks.
- The Mahjong ranks as a one: a lead single, or the low end of a straight,
  and nothing else. The Dog is led alone and ends the trick. The Dragon is
  the highest single and joins no combination. The Phoenix is a single half a
  rank above the standing play (`1.5` led), and in every other kind a
  wildcard for any one card between 2 and Ace — never in a bomb.
- Bombs are four of a rank, or at least five consecutive cards of one suit.
  A bomb beats everything but a higher bomb; bombs rank first by number of
  cards, then by rank, so any straight flush beats any four of a kind.

A play's identity for the action space is its card-set PLUS `wild`: a
card-set holding the Phoenix can be two plays ({Phoenix,3,4,5,6} is 2-6 or
3-7; {8,8,K,K,Phoenix} is eights full or kings full), and the two differ in
what they beat. Every suit choice is enumerated — with straight-flush bombs
live, which card of a rank a player parts with is a real choice.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations, product
from typing import Final

from cardlang.runtime.values import Card

# Rank values. The Mahjong is a one; the Dragon a fifteen; the Phoenix and the
# Dog carry no rank of their own (the Phoenix's single value is contextual).
_RANKVAL: Final[dict[str, int]] = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14, "Mahjong": 1, "Dragon": 15,
}
MAHJONG_VALUE: Final = 1
DRAGON_VALUE: Final = 15
PHOENIX_LEAD_VALUE: Final = 1.5
NORMAL_VALUES: Final[tuple[int, ...]] = tuple(range(2, 15))  # the wildcard's range
_RANK_NAMES: Final[dict[int, str]] = {v: r for r, v in _RANKVAL.items() if 2 <= v <= 14}

# The Mahjong's wish: whoever plays the Mahjong may wish for a rank, and the
# tokens are the announcement the climb form offers right after the play
# (`Play.announce`). `WISH_VALUES` reads a token back to the rank value it
# names; `no_wish` names none.
WISH_TOKENS: Final[tuple[str, ...]] = tuple(
    [f"wish_{_RANK_NAMES[v]}" for v in NORMAL_VALUES] + ["no_wish"]
)
WISH_VALUES: Final[dict[str, int]] = {f"wish_{_RANK_NAMES[v]}": v for v in NORMAL_VALUES}
# What a seat asked in the interrupt window says when it plays no bomb.
INTERRUPT_DECLINE: Final = "no_bomb"


def _rv(c: Card) -> int | None:
    return _RANKVAL.get(c.rank)  # None for Phoenix / Dog


@dataclass(frozen=True, slots=True)
class Kind:
    """One row of `KINDS`: a combination kind's structure.

    `phoenix` says whether the Phoenix may stand in for a card of the kind;
    `mahjong` whether the Mahjong may be part of it; `lengths` the `Play.length`
    values the kind takes (cards for most kinds, PAIRS for a pair sequence,
    cards again for a bomb, where 4 is four of a rank and 5..13 a straight
    flush)."""

    phoenix: bool
    mahjong: bool
    lengths: tuple[int, ...]


# The rows' order is the codec's block order (`tichu.py`, the combo codec).
KINDS: Final[dict[str, Kind]] = {
    "dog": Kind(phoenix=False, mahjong=False, lengths=(1,)),
    "single": Kind(phoenix=True, mahjong=True, lengths=(1,)),
    "pair": Kind(phoenix=True, mahjong=False, lengths=(2,)),
    "triple": Kind(phoenix=True, mahjong=False, lengths=(3,)),
    "bomb": Kind(phoenix=False, mahjong=False, lengths=(4, *range(5, 14))),
    "fullhouse": Kind(phoenix=True, mahjong=False, lengths=(5,)),
    "straight": Kind(phoenix=True, mahjong=True, lengths=tuple(range(5, 15))),
    "pairseq": Kind(phoenix=True, mahjong=False, lengths=tuple(range(2, 8))),
}


@dataclass(frozen=True, slots=True)
class Play:
    """One play, conforming to `primitives.ClimbPlay`."""

    kind: str       # a key of KINDS
    length: int     # see Kind.lengths
    key: float      # comparison key within (kind, length); bombs compare across
    cards: tuple[Card, ...]
    wild: int | None = None  # the rank value the Phoenix stands in for, else None
    compelled: bool = False  # the standing wish makes this play mandatory
    announce: tuple[str, ...] = ()  # the Mahjong's wish, opened by the play

    @property
    def is_bomb(self) -> bool:
        return self.kind == "bomb"

    @property
    def interrupt(self) -> bool:
        """A bomb may be played out of turn (the climb form's interrupt
        window offers it between plays)."""
        return self.kind == "bomb"

    @property
    def ends_trick(self) -> bool:
        """A Dog lead ends the trick at once — its followers get no chooser
        draw; the lead passes to the partner (the climb form reads this)."""
        return self.kind == "dog"

    @property
    def rank_values(self) -> frozenset[int]:
        """The rank values the play holds as NATURAL cards (the wildcard's
        value is not among them — the Phoenix never counts as a rank)."""
        return frozenset(v for v in (_rv(c) for c in self.cards) if v is not None)


def bomb_rank(p: Play) -> tuple[int, float]:
    """How bombs rank against each other: number of cards, then rank."""
    return (p.length, p.key)


def _split(hand: list[Card]) -> tuple[Card | None, Card | None, Card | None, dict[int, list[Card]]]:
    """(phoenix, mahjong, dragon, normal cards by rank value)."""
    phoenix = mahjong = dragon = None
    by_rank: dict[int, list[Card]] = {}
    for c in hand:
        if c.rank == "Phoenix":
            phoenix = c
        elif c.rank == "Mahjong":
            mahjong = c
        elif c.rank == "Dragon":
            dragon = c
        elif c.rank != "Dog":
            by_rank.setdefault(_RANKVAL[c.rank], []).append(c)
    return phoenix, mahjong, dragon, by_rank


def _combos(hand: list[Card]) -> list[Play]:
    """Every combination the hand can form, at every suit choice, except the
    two lead-site plays (the Dog, and the Phoenix as a single, whose value
    depends on the standing play). Order: singles, pairs, triples, bombs,
    full houses, straights, pair sequences — natural plays before the
    Phoenix's within each kind."""
    out: list[Play] = []
    phoenix, mahjong, dragon, by_rank = _split(hand)
    values = sorted(by_rank)

    # Singles: every ranked card (the Dog is a lead-only kind; the Phoenix is
    # contextual and added at the call sites).
    if mahjong is not None:
        out.append(Play("single", 1, MAHJONG_VALUE, (mahjong,), announce=WISH_TOKENS))
    for v in values:
        for c in by_rank[v]:
            out.append(Play("single", 1, v, (c,)))
    if dragon is not None:
        out.append(Play("single", 1, DRAGON_VALUE, (dragon,)))

    # Sets: pairs, triples, four-of-a-rank bombs; the Phoenix completes a
    # pair or a triple.
    for v in values:
        cs = by_rank[v]
        for pair in combinations(cs, 2):
            out.append(Play("pair", 2, v, pair))
        for triple in combinations(cs, 3):
            out.append(Play("triple", 3, v, triple))
        if len(cs) == 4:
            out.append(Play("bomb", 4, v, tuple(cs)))
    if phoenix is not None:
        for v in values:
            cs = by_rank[v]
            for c in cs:
                out.append(Play("pair", 2, v, (c, phoenix), wild=v))
            for pair in combinations(cs, 2):
                out.append(Play("triple", 3, v, (*pair, phoenix), wild=v))

    # Straight-flush bombs: at least five consecutive ranks in one suit.
    by_suit: dict[str, dict[int, Card]] = {}
    for v in values:
        for c in by_rank[v]:
            by_suit.setdefault(c.suit, {})[v] = c
    for suit in sorted(by_suit):
        held = by_suit[suit]
        for lo in NORMAL_VALUES:
            for hi in range(lo + 4, 15):
                if all(v in held for v in range(lo, hi + 1)):
                    cards = tuple(held[v] for v in range(lo, hi + 1))
                    out.append(Play("bomb", hi - lo + 1, hi, cards))
                else:
                    break

    # Full houses: a triple of one rank with a pair of another; the Phoenix
    # completes either the pair or the triple.
    for tr in values:
        for pr in values:
            if pr == tr:
                continue
            for triple in combinations(by_rank[tr], 3):
                for pair in combinations(by_rank[pr], 2):
                    out.append(Play("fullhouse", 5, tr, (*triple, *pair)))
    if phoenix is not None:
        for tr in values:
            for pr in values:
                if pr == tr:
                    continue
                for triple in combinations(by_rank[tr], 3):
                    for c in by_rank[pr]:
                        out.append(Play("fullhouse", 5, tr, (*triple, c, phoenix), wild=pr))
                for pair_t in combinations(by_rank[tr], 2):
                    for pair in combinations(by_rank[pr], 2):
                        out.append(Play("fullhouse", 5, tr, (*pair_t, phoenix, *pair), wild=tr))

    # Straights: one card per consecutive rank, the Mahjong as a one at the
    # low end; a suited run is a bomb (above), never a straight. The Phoenix
    # stands for any one rank from 2 up, held or not.
    ranked: dict[int, list[Card]] = dict(by_rank)
    if mahjong is not None:
        ranked[MAHJONG_VALUE] = [mahjong]
    for lo in range(1, 11):
        for hi in range(lo + 4, 15):
            window = range(lo, hi + 1)
            wish = WISH_TOKENS if lo == 1 else ()  # the Mahjong's straight opens the wish
            if all(v in ranked for v in window):
                for cards in product(*(ranked[v] for v in window)):
                    suited = [c for c in cards if c.rank != "Mahjong"]
                    if lo >= 2 and len({c.suit for c in suited}) == 1:
                        continue  # a straight flush: emitted as a bomb
                    out.append(Play("straight", hi - lo + 1, hi, cards, announce=wish))
            if phoenix is not None:
                for p in window:
                    if p < 2:
                        continue
                    others = [v for v in window if v != p]
                    if all(v in ranked for v in others):
                        for cards in product(*(ranked[v] for v in others)):
                            out.append(
                                Play("straight", hi - lo + 1, hi, (*cards, phoenix), wild=p, announce=wish)
                            )

    # Consecutive pairs: two cards of each of at least two consecutive ranks;
    # the Phoenix stands for one card of one rank.
    for lo in NORMAL_VALUES:
        for hi in range(lo + 1, 15):
            window = range(lo, hi + 1)
            if all(len(by_rank.get(v, ())) >= 2 for v in window):
                for pairs in product(*(list(combinations(by_rank[v], 2)) for v in window)):
                    cards = tuple(c for pair in pairs for c in pair)
                    out.append(Play("pairseq", hi - lo + 1, hi, cards))
            if phoenix is not None:
                for p in window:
                    others = [v for v in window if v != p]
                    if by_rank.get(p) and all(len(by_rank.get(v, ())) >= 2 for v in others):
                        for single in by_rank[p]:
                            for pairs in product(*(list(combinations(by_rank[v], 2)) for v in others)):
                                cards = tuple(c for pair in pairs for c in pair) + (single, phoenix)
                                out.append(Play("pairseq", hi - lo + 1, hi, cards, wild=p))
    return out


def compel(plays: list[Play], wish: int | None) -> list[Play]:
    """Mark the plays a standing wish compels: those holding a natural card
    of the wished rank (a bomb holding one counts; the Phoenix never does).
    With no wish, or no such play, every play comes back as it was."""
    if wish is None:
        return plays
    return [replace(p, compelled=True) if wish in p.rank_values else p for p in plays]


def phoenix_single(hand: list[Card], value: float) -> Play | None:
    """The Phoenix as a single at `value`, if the hand holds it."""
    phoenix = next((c for c in hand if c.rank == "Phoenix"), None)
    return None if phoenix is None else Play("single", 1, value, (phoenix,))


def _legal_follows(hand: list[Card], current: Play) -> list[Play]:
    """The plays that beat `current`: same kind and length with a higher key;
    a bomb over anything but a bomb it does not outrank; the Phoenix as a
    single half a rank above any single but the Dragon. Nothing follows the
    Dog."""
    if current.kind == "dog":
        return []
    follows: list[Play] = []
    for p in _combos(hand):
        if p.is_bomb:
            if not current.is_bomb or bomb_rank(p) > bomb_rank(current):
                follows.append(p)
        elif current.is_bomb:
            continue
        elif p.kind == current.kind and p.length == current.length and p.key > current.key:
            follows.append(p)
    if current.kind == "single" and current.key < DRAGON_VALUE:
        answer = phoenix_single(hand, current.key + 0.5)
        if answer is not None:
            follows.append(answer)
    return follows
