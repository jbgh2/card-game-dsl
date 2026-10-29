"""The Declared Engine: a climbing round over the game's own Combination
Catalogue (decisions.md "Combination Catalogues").

A catalogue's rows name card multisets; this module is the one home of what
they name. `universe` derives a catalogue's every play over the game's deck,
which the catalogue pass judges at check time (counts, qualifiers, overlaps,
the enumeration bound) and the action space numbers; `DeclaredClimbEngine`
offers a seat the multisets of its hand that a row names and the game's
follows function admits, in action-id order, each moving its cards in deck
order.

Contract:
  assumes:      resolve stamped the round's engine a `DeclaredEngine`, and the
                catalogue pass accepted the catalogue (every row admissible,
                no two rows naming one multiset, the universe within
                `catalogue.ENUMERATED_UNIVERSE_BOUND`); typecheck accepted the
                follows function at `(Combination, Combination?) -> Boolean`.
  establishes:  a play's identity is its card multiset (copies of one card
                stay distinct plays' cards, never one card twice); the
                universe is a pure function of the catalogue, the deck and the
                Rank Sequence; a seat's candidates are a pure function of its
                hand, the standing play and the follows function's reads
                (`DeclaredEngine.state_reads` / `zone_reads`, stamped by
                resolve), so its answers are cached on exactly those.
  illegal after: an offered play outside the universe; a candidate list in
                any order but action-id order; a cached follows answer whose
                key omits a read the function makes.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.values import Card, Combination, build_deck

# The follows function's answers are cached by play identity and the values
# of what it reads; a test turns the cache off to hold the cached run against
# the uncached one (tests/test_declared_engine.py).
CACHE = True

Identity = tuple[Card, ...]


@cache
def card_order(deck: str) -> dict[Card, int]:
    """Each card of `deck` at its first place in the deck's own order: the
    order a play's cards move in, and the order identities sort by."""
    order: dict[Card, int] = {}
    for i, card in enumerate(build_deck(deck)):
        order.setdefault(card, i)
    return order


def _windows(sequence: tuple[str, ...], size: int) -> list[Counter[str]]:
    return [Counter(sequence[i : i + size]) for i in range(len(sequence) - size + 1)]


def _in_sequence(cards: Sequence[Card], sequence: tuple[str, ...]) -> bool:
    if len(cards) < 2:
        return False
    ranks = Counter(c.rank for c in cards)
    return any(w == ranks for w in _windows(sequence, len(cards)))


def _part(
    part: n.ShapePart,
    pool: Sequence[Card],
    free: Sequence[int],
    sequence: tuple[str, ...],
    one_suit: bool = False,
) -> Iterator[tuple[int, ...]]:
    """The index tuples of `pool` (drawn from `free`) that `part` names. With
    `one_suit` (the row's `all one suit`), any-cards picks are drawn suit by
    suit, so a flush row walks a suit's cards rather than the whole deck's."""
    size = part.count
    match part.kind:
        case "shape_card" | "shape_cards":
            if not one_suit:
                yield from itertools.combinations(free, size)
                return
            by_suit: dict[str, list[int]] = {}
            for i in free:
                by_suit.setdefault(pool[i].suit, []).append(i)
            for group in by_suit.values():
                yield from itertools.combinations(group, size)
        case "shape_of_a_kind":
            by_rank: dict[str, list[int]] = {}
            for i in free:
                by_rank.setdefault(pool[i].rank, []).append(i)
            for group in by_rank.values():
                yield from itertools.combinations(group, size)
        case "shape_in_sequence":
            by_rank = {}
            for i in free:
                by_rank.setdefault(pool[i].rank, []).append(i)
            for start in range(len(sequence) - size + 1):
                window = sequence[start : start + size]
                for pick in itertools.product(*(by_rank.get(r, []) for r in window)):
                    if len(set(pick)) == size:
                        yield tuple(sorted(pick))


def _qualified(cards: Sequence[Card], row: n.ShapeRow, sequence: tuple[str, ...]) -> bool:
    one_suit = len({c.suit for c in cards}) == 1
    for q in row.qualifiers:
        match q:
            case "q_all_one_suit":
                if not one_suit:
                    return False
            case "q_not_all_one_suit":
                if one_suit:
                    return False
            case "q_not_in_sequence":
                if _in_sequence(cards, sequence):
                    return False
    return True


def row_multisets(
    row: n.ShapeRow, pool: Sequence[Card], sequence: tuple[str, ...], order: dict[Card, int]
) -> Iterator[Identity]:
    """Every card multiset of `pool` that `row` names, once each, its cards in
    deck order. A pool may hold copies of one card; two picks of equal cards
    are one multiset."""
    seen: set[Identity] = set()
    everything = range(len(pool))
    first, *rest = row.parts
    one_suit = not rest and "q_all_one_suit" in row.qualifiers
    for a in _part(first, pool, everything, sequence, one_suit):
        picks: Iterator[tuple[int, ...]]
        if rest:
            (second,) = rest
            taken = {pool[i].rank for i in a}
            free = [i for i in everything if i not in a and pool[i].rank not in taken]
            picks = (tuple(sorted(a + b)) for b in _part(second, pool, free, sequence))
        else:
            picks = iter((a,))
        for pick in picks:
            cards = tuple(sorted((pool[i] for i in pick), key=order.__getitem__))
            if cards in seen or not _qualified(cards, row, sequence):
                continue
            seen.add(cards)
            yield cards


@dataclass(frozen=True)
class Universe:
    """A catalogue's every play over its deck, in action-id order: card count,
    then the cards' deck places (`primitives.action_order`'s order, over the
    deck's own numbering). `rank` is each identity's place."""

    plays: tuple[Combination, ...]
    rank: dict[Identity, int]


@cache
def universe(catalogue: n.CombinationCatalogue, deck: str, sequence: tuple[str, ...], bound: int) -> Universe | None:
    """The catalogue's universe, or None when it holds more than `bound`
    plays (the enumeration stops one past it). Each play carries the label of
    the one row that names it; two rows naming one multiset is the catalogue
    pass's refusal, which runs before anything numbers the universe."""
    pool = build_deck(deck)
    order = card_order(deck)
    found: dict[Identity, str] = {}
    for row in catalogue.rows:
        for cards in row_multisets(row, pool, sequence, order):
            found.setdefault(cards, row.label)
            if len(found) > bound:
                return None
    keyed = sorted(found, key=lambda cards: (len(cards), [order[c] for c in cards]))
    plays = tuple(Combination(found[cards], cards) for cards in keyed)
    return Universe(plays, {cards: i for i, cards in enumerate(keyed)})


class DeclaredClimbEngine:
    """A climbing round's Declared Engine: the catalogue's plays a hand holds,
    admitted by the game's follows function against the standing play (None at
    a lead), in action-id order."""

    def __init__(self, engine: n.DeclaredEngine, ctx: Any) -> None:
        from cardlang.catalogue import ENUMERATED_UNIVERSE_BOUND
        from cardlang.runtime.errors import ShadowGuardError

        rs = ctx.rs
        self.catalogue: n.CombinationCatalogue = rs.catalogues[engine.catalogue]
        self.follows_fn: n.FunctionDef = rs.function_index[engine.follows]
        self.sequence: tuple[str, ...] = rs.rank_sequence
        self.order = card_order(rs.deck_name)
        found = universe(self.catalogue, rs.deck_name, self.sequence, ENUMERATED_UNIVERSE_BOUND)
        if found is None:
            raise ShadowGuardError(
                "the catalogue pass (resolve), which refuses a catalogue past the "
                "enumeration bound",
                f"catalogue `{self.catalogue.name}` numbers more than "
                f"{ENUMERATED_UNIVERSE_BOUND} plays",
            )
        self.universe = found
        self.engine = engine
        self._memo: dict[tuple[object, ...], bool] = {}

    def _admits(self, play: Combination, standing: Combination | None, ctx: Any) -> bool:
        from cardlang.runtime.evaluate import call_user_function

        if not (CACHE and self.engine.cacheable):
            return bool(call_user_function(self.follows_fn, [play, standing], ctx))
        rs = ctx.rs
        key = (
            play.cards,
            None if standing is None else standing.cards,
            tuple(rs.get(v) for v in self.engine.state_reads),
            tuple(_zone_contents(rs, z) for z in self.engine.zone_reads),
        )
        hit = self._memo.get(key)
        if hit is None:
            hit = bool(call_user_function(self.follows_fn, [play, standing], ctx))
            self._memo[key] = hit
        return hit

    def candidates(self, hand: Sequence[Card], standing: Combination | None, ctx: Any) -> list[Combination]:
        offered = [
            play
            for row in self.catalogue.rows
            for cards in row_multisets(row, hand, self.sequence, self.order)
            if self._admits(play := Combination(row.label, cards), standing, ctx)
        ]
        offered.sort(key=lambda p: self.universe.rank[p.cards])
        return offered


def _zone_contents(rs: Any, zone: str) -> object:
    if rs.zones.is_family(zone):
        return tuple(tuple(z.cards) for z in rs.zones.families[zone].values())
    return tuple(rs.zones.single(zone).cards)
