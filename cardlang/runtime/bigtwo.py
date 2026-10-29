"""The Big Two combination engine and its climbing-form Primitive queries.

The corpus's second climbing game (after Tichu) and the partner instance that —
together with Tichu — shapes the kernel `climb` construct. Big Two's whole hand
runs on the climb [[form]] of [[round]] (`docs/games/big-two.cardlang`); this
module is the RNG-free combination engine plus the game-local queries the
climb round names:
`bigtwo_lead_options` (lead candidates) and `bigtwo_follows` (legal follows).

The engine has two parts only Big Two has but Tichu does not: suit *always* breaks
ties (a single 52-card deck, so 7♠ > 7♥), and the five-card group includes flushes
and quads-plus-kicker. Two rank orders coexist: 2 is the highest rank for
singles/pairs/triples/quads/full-houses (and a flush's top card), while straights
and straight flushes run in *natural* order (A high in 10-J-Q-K-A, low in the
A-2-3-4-5 wheel; no wrap-around). It is kept game-local beside Tichu's
`tichu_combinations.py` (the engines differ) until a third instance justifies
merging.

The queries offer every combination a hand holds — each suit choice of a pair,
triple, straight, full house, and quads kicker, and each five-card subset of a
suit for a flush — since which cards a seat keeps back is a decision of the game.
tests/test_bigtwo_combinations.py holds them to an independent oracle written
from the rules source over every subset of sampled hands.
"""

from __future__ import annotations

import functools
import itertools
from dataclasses import dataclass, replace
from typing import Any

from cardlang.runtime import primitives, reads
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card

ROW = reads.row("cardlang/runtime/bigtwo.py", "big-two.cardlang")

# Big Two rank order for singles / pairs / triples / quads / full houses and a
# flush's top card: the 2 is the highest rank, the 3 the lowest.
_RANK = {"3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
         "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15}
# Natural order for straights / straight flushes: the ace is high in 10-J-Q-K-A
# and low in the A-2-3-4-5 wheel; the 2 is an ordinary low card here, never high.
_NAT = {"3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
        "J": 11, "Q": 12, "K": 13, "A": 14, "2": 2}
# Suit order, high to low: spades > hearts > clubs > diamonds (breaks every tie).
_SUIT = {"diamonds": 0, "clubs": 1, "hearts": 2, "spades": 3}

# Five-card type ranks: a higher type beats every lower one regardless of cards.
_STRAIGHT, _FLUSH, _FULLHOUSE, _QUADS, _STRAIGHTFLUSH = 0, 1, 2, 3, 4

# The ten straight rank-windows, each ordered low-to-high so the last element is
# the top card. The wheel (A-2-3-4-5) is lowest; 10-J-Q-K-A is highest.
_STRAIGHTS: tuple[tuple[str, ...], ...] = (
    ("A", "2", "3", "4", "5"),
    ("2", "3", "4", "5", "6"),
    ("3", "4", "5", "6", "7"),
    ("4", "5", "6", "7", "8"),
    ("5", "6", "7", "8", "9"),
    ("6", "7", "8", "9", "10"),
    ("7", "8", "9", "10", "J"),
    ("8", "9", "10", "J", "Q"),
    ("9", "10", "J", "Q", "K"),
    ("10", "J", "Q", "K", "A"),
)


@dataclass(frozen=True, slots=True)
class Play:
    """A playable combination. `key` is a tuple comparing plays *of the same
    size*; for five-card plays its first element is the type rank, so a stronger
    type sorts above a weaker one before the within-type strength is consulted."""

    kind: str            # single|pair|triple|straight|flush|fullhouse|quads|straightflush
    size: int            # 1 | 2 | 3 | 5
    key: tuple[Any, ...]
    cards: tuple[Card, ...]
    # The `primitives.ClimbPlay` behaviours, none of which Big Two has: no
    # play ends the trick, stands a wildcard, compels, announces, or
    # interrupts.
    ends_trick: bool = False
    wild: int | None = None
    compelled: bool = False
    announce: tuple[str, ...] = ()
    interrupt: bool = False


def _by_rank(hand: list[Card]) -> dict[str, list[Card]]:
    """Group a hand by rank, each rank's cards sorted highest suit first."""
    groups: dict[str, list[Card]] = {}
    for c in hand:
        groups.setdefault(c.rank, []).append(c)
    for cs in groups.values():
        cs.sort(key=lambda c: _SUIT[c.suit], reverse=True)
    return groups


def _is_straight_ranks(ranks: frozenset[str]) -> bool:
    return any(ranks == frozenset(seq) for seq in _STRAIGHTS)


def _five_card_combos(hand: list[Card], by_rank: dict[str, list[Card]]) -> list[Play]:
    out: list[Play] = []
    suit_cards: dict[str, list[Card]] = {}
    for c in hand:
        suit_cards.setdefault(c.suit, []).append(c)

    # Straights and straight flushes, window by window: every suit assignment
    # over the window's five ranks. A monochrome assignment is a straight flush.
    for seq in _STRAIGHTS:
        if not all(r in by_rank for r in seq):
            continue
        top_nat = _NAT[seq[-1]]
        for cards in itertools.product(*(by_rank[r] for r in seq)):
            top = cards[-1]
            if len({c.suit for c in cards}) == 1:
                out.append(Play("straightflush", 5, (_STRAIGHTFLUSH, top_nat, _SUIT[top.suit]), cards))
            else:
                out.append(Play("straight", 5, (_STRAIGHT, top_nat, _SUIT[top.suit]), cards))

    # Flushes: every five cards of a suit, unless their ranks are consecutive —
    # that card-set is a straight flush, already emitted.
    for suit, cs in suit_cards.items():
        ordered = sorted(cs, key=lambda c: _RANK[c.rank], reverse=True)
        for five in itertools.combinations(ordered, 5):
            if not _is_straight_ranks(frozenset(c.rank for c in five)):
                out.append(Play("flush", 5, (_FLUSH, _SUIT[suit], _RANK[five[0].rank]), five))

    # Full houses: every triple of a rank with every pair of another rank (the
    # triple's rank ranks it).
    for tr, tcs in by_rank.items():
        for triple in itertools.combinations(tcs, 3):
            for pr, pcs in by_rank.items():
                if pr == tr:
                    continue
                for pair in itertools.combinations(pcs, 2):
                    out.append(Play("fullhouse", 5, (_FULLHOUSE, _RANK[tr]), triple + pair))

    # Quads: four of a rank plus any other card of the hand as the fifth.
    for r, cs in by_rank.items():
        if len(cs) == 4:
            for kicker in hand:
                if kicker.rank != r:
                    out.append(Play("quads", 5, (_QUADS, _RANK[r]), tuple(cs) + (kicker,)))
    return out


def _combos(hand: list[Card]) -> list[Play]:
    """Every combination a hand can play. Sizes 1, 2, 3, and 5 — Big Two has
    no four-card play, and quads are a five-card group (four plus a kicker)."""
    by_rank = _by_rank(hand)
    out: list[Play] = [
        Play("single", 1, (_RANK[c.rank], _SUIT[c.suit]), (c,)) for c in hand
    ]
    for r, cs in by_rank.items():
        # `cs` is highest suit first, so each pair's first card is its highest.
        for pair in itertools.combinations(cs, 2):
            out.append(Play("pair", 2, (_RANK[r], _SUIT[pair[0].suit]), pair))
        for triple in itertools.combinations(cs, 3):
            out.append(Play("triple", 3, (_RANK[r],), triple))
    out.extend(_five_card_combos(hand, by_rank))
    return out


def _legal_follows(hand: list[Card], led: Play) -> list[Play]:
    """Plays that legally beat `led`: the same number of cards and a higher key.
    Big Two has no cross-size beating and no bombs — a single follows a single, a
    five-card group a five-card group (where a stronger type already sorts above a
    weaker one inside the key)."""
    return [p for p in _combos(hand) if p.size == led.size and p.key > led.key]


# ---------------------------------------------------------------------------
# The climbing-form Primitive queries (named on `round climb` in big-two.cardlang)
# ---------------------------------------------------------------------------


def bigtwo_lead_options(
    facts: EngineFacts, gr: reads.GameReads, hand: list[Card]
) -> list[Play]:
    """The combinations a leader may lead. On a hand's opening lead (game state
    `opened` still false) only those containing the 3♦ are offered — its holder
    leads and must play it, alone or in any combination holding it."""
    combos = _combos(hand)
    if not gr.state["opened"]:
        three = Card("3", "diamonds")
        combos = [p for p in combos if three in p.cards]
    return _in_action_order(combos)


def bigtwo_follows(
    facts: EngineFacts, gr: reads.GameReads, hand: list[Card], current: Play
) -> list[Play]:
    """The combinations that legally beat the standing play (same size, higher
    key). The bundles are unused — Big Two follows depend only on the hand and
    the led play — but the climb round passes them uniformly with the lead
    query."""
    return _in_action_order(_legal_follows(hand, current))


@functools.cache
def _action_rank() -> dict[primitives.Identity, int]:
    return primitives.action_rank(bigtwo_universe())


def _in_action_order(plays: list[Play]) -> list[Play]:
    """`plays` in their action-id order, the order both queries offer, each
    moving its cards in card-id order (`primitives.in_card_order`)."""
    rank = _action_rank()
    return [
        replace(p, cards=primitives.in_card_order(p.cards))
        for p in sorted(plays, key=lambda p: rank[primitives.play_identity(p)])
    ]


def bigtwo_universe() -> list[Play]:
    """Every play this engine can ever produce over any hand — the combination
    action universe for the OpenSpiel adapter (the union of `_combos` over
    every hand; each card-set appears at most once, since a collision would
    give two plays one action id).

    Enumerates by shape, mirroring `_combos` / `_five_card_combos`: pairs are
    all C(4,2) per rank, triples all C(4,3), a straight is any non-monochrome
    suit assignment over its window (monochrome is a straight flush), a flush
    any 5-of-a-suit whose ranks are not a straight window, a quad takes any of
    the 48 spare cards as kicker.
    """
    suits_desc = sorted(_SUIT, key=lambda s: _SUIT[s], reverse=True)
    out: list[Play] = []

    for r in _RANK:
        for s in suits_desc:
            out.append(Play("single", 1, (_RANK[r], _SUIT[s]), (Card(r, s),)))
    for r in _RANK:
        for s1, s2 in itertools.combinations(suits_desc, 2):
            out.append(Play("pair", 2, (_RANK[r], _SUIT[s1]), (Card(r, s1), Card(r, s2))))
        for suits3 in itertools.combinations(suits_desc, 3):
            out.append(Play("triple", 3, (_RANK[r],), tuple(Card(r, s) for s in suits3)))

    for seq in _STRAIGHTS:
        top_nat = _NAT[seq[-1]]
        for suit in suits_desc:  # monochrome: the straight flushes
            cards = tuple(Card(r, suit) for r in seq)
            out.append(Play("straightflush", 5, (_STRAIGHTFLUSH, top_nat, _SUIT[suit]), cards))
        for assignment in itertools.product(suits_desc, repeat=5):
            if len(set(assignment)) == 1:
                continue  # monochrome emitted above as a straight flush
            cards = tuple(Card(r, s) for r, s in zip(seq, assignment))
            out.append(Play("straight", 5, (_STRAIGHT, top_nat, _SUIT[assignment[-1]]), cards))

    for suit in suits_desc:
        for ranks in itertools.combinations(_RANK, 5):
            if _is_straight_ranks(frozenset(ranks)):
                continue  # that card-set is a straight flush
            ordered = sorted(ranks, key=lambda r: _RANK[r], reverse=True)
            cards = tuple(Card(r, suit) for r in ordered)
            out.append(Play("flush", 5, (_FLUSH, _SUIT[suit], _RANK[ordered[0]]), cards))

    for tr in _RANK:
        for pr in _RANK:
            if pr == tr:
                continue
            for ts in itertools.combinations(suits_desc, 3):
                for ps in itertools.combinations(suits_desc, 2):
                    cards = tuple(
                        [Card(tr, s) for s in ts] + [Card(pr, s) for s in ps]
                    )
                    out.append(Play("fullhouse", 5, (_FULLHOUSE, _RANK[tr]), cards))

    for r in _RANK:
        four = tuple(Card(r, s) for s in suits_desc)
        for kr in _RANK:
            if kr == r:
                continue
            for ks in suits_desc:
                out.append(Play("quads", 5, (_QUADS, _RANK[r]), four + (Card(kr, ks),)))
    return out
