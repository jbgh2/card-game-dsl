"""Salvo's runtime support: the combo bonus one army scores at one location.

Salvo (`experiments/salvo/`) prices a committed card by its distance to the
location's target rank and its affinity suit — both in the DSL — and adds a
bonus for the army's internal structure. That bonus is `experiments/salvo/
DESIGN.md`'s combo table: three independent families (of-a-kind, run, flush),
each scoring at most once and on its largest instance only, summed, with one
card free to serve several. It is a combination count the language has no
combinator for, so the game declares it as the [[primitive]] `salvo_combos` in
its own `primitives { }` block; it migrates into the DSL when the
`combinations` construct lands (docs/design-notes/combination-scoring.md).

The run family's adjacency is the game's declared `ranking:`, which arrives as
`EngineFacts.rank_index` — this module holds no private copy of the rank order.

Contract
--------
Assumes: `cards` are one player's army at one location, and `rank_index` ranks
every rank they carry.
Establishes: DESIGN.md's table over those cards, with jokers excluded from
every family.
Illegal after: reading a joker as a member of any combination.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player, rank_strength

# The joker as this deck spells it: `standard54` gives both jokers their own
# suit and rank, outside the suits x ranks cross product
# (`runtime/values.py`, `_standard54`).
JOKER_SUIT = "joker"
JOKER_RANK = "Joker"

# The three locations, in the order the Integer argument numbers them. The
# argument is an Integer because the declared surface has no spelling for a
# zone family, so the mapping from 0/1/2 to a/b/c lives here and the game
# file's own comment states it.
LOCATIONS: tuple[str, ...] = ("a", "b", "c")


def naturals(cards: list[Card]) -> list[Card]:
    """The cards that can join a combination — everything but the jokers.

    The ONE exclusion site, and it runs before every family: two jokers share
    a rank, so an unfiltered of-a-kind scan pairs them, and a joker sits at
    one end of the declared ranking, so an unfiltered run scan reads it as
    adjacent to the rank next to it."""
    return [c for c in cards if c.suit != JOKER_SUIT]


def of_a_kind_bonus(cards: list[Card]) -> int:
    """Pair 4, three of a kind 12, four of a kind 20 — the largest instance
    only, so two pairs score one pair and a triplet does not also score the
    pair inside it. The top rung is a floor because `standard54` holds four
    cards of a natural rank and no more."""
    most = max(Counter(c.rank for c in naturals(cards)).values(), default=0)
    if most >= 4:
        return 20
    return {3: 12, 2: 4}.get(most, 0)


def run_bonus(cards: list[Card], rank_index: Mapping[str, int]) -> int:
    """A run of three 6, of four 10, of five or longer 15 — the longest run
    only.

    Adjacency is consecutive positions on the game's declared scale with the
    joker rank taken out of it, so the scale stays the linear ace-low ladder
    DESIGN.md describes however the ranking places the joker. The ladder does
    not wrap: A-2-3 is a run and Q-K-A is not, which is the reason Salvo's
    extreme location targets price the deck unevenly at all. Duplicate ranks
    collapse — a run is a set of ranks, not of cards.

    The per-card strength goes through `rank_strength`, the ONE lookup every
    `rank_index` consumer routes through: a `ranking:` may be a partial
    permutation of the deck, and an army holding a card it does not rank is
    the game author's to fix, in the runtime's own typed channel."""
    scale = sorted({v for r, v in rank_index.items() if r != JOKER_RANK})
    position = {v: i for i, v in enumerate(scale)}
    held = sorted(
        {
            position[rank_strength(rank_index, c.rank, "salvo_combos")]
            for c in naturals(cards)
        }
    )
    longest = run = 0
    for i, p in enumerate(held):
        run = run + 1 if i and p == held[i - 1] + 1 else 1
        longest = max(longest, run)
    if longest >= 5:
        return 15
    return {4: 10, 3: 6}.get(longest, 0)


def flush_bonus(cards: list[Card]) -> int:
    """A flush of three 5, of four 9, of five or longer 14 — the longest flush
    only. A joker has no suit to match, so it joins none."""
    most = max(Counter(c.suit for c in naturals(cards)).values(), default=0)
    if most >= 5:
        return 14
    return {4: 9, 3: 5}.get(most, 0)


def combo_score(cards: list[Card], rank_index: Mapping[str, int]) -> int:
    """One army's combo bonus: the three families summed.

    They are independent, so one card may serve several — DESIGN.md's worked
    example, 7 of spades + 7 of hearts + 8 of spades + 9 of spades, scores a
    pair, a run of three and a flush of three."""
    return of_a_kind_bonus(cards) + run_bonus(cards, rank_index) + flush_bonus(cards)


def salvo_combos(
    facts: EngineFacts, gr: reads.GameReads, p: Player, loc: int
) -> int:
    """`p`'s combo bonus at location `loc` (0/1/2 for a/b/c).

    All three armies are read because all three are declared: the block's
    clause is per-entry, and the location is an argument, so the bundle
    materializes the set and the argument selects within it."""
    armies = (
        gr.families["army_a"][p],
        gr.families["army_b"][p],
        gr.families["army_c"][p],
    )
    if not 0 <= loc < len(LOCATIONS):
        raise OwnerGuardError(
            f"salvo_combos: location {loc} is outside 0..2 — the three "
            f"locations are {', '.join(LOCATIONS)}"
        )
    return combo_score(list(armies[loc]), facts.rank_index)
