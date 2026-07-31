"""Poker's family-wide showdown maths — shared by the corpus's poker games.

Two pieces of poker knowledge are genuinely family-wide rather than game-local,
and they are the same shape of claim:

- **`hand_rank`** — "the best five-card hand from the cards available". Stud
  picks its five from seven private-and-upcard cards; Hold'em from two hole
  cards plus a five-card community board. WHICH cards are available is a
  property of the game; how five of them compare is not.
- **`side_pot_payouts`** — "who collects what when players are all-in for
  different amounts". WHICH cards a contender shows is a property of the game;
  how commitment layers into side pots is not.

Both are parameterized on exactly that boundary: the caller supplies the
per-contender showdown holding, this module supplies the comparison and the
layering. That split matters more than tidiness — two copies of side-pot
arithmetic drift, and a drifted settlement still CONSERVES CHIPS, so the
playout invariant every poker game leans on cannot see it (decisions.md
"Closed-domain completeness", sweep the class).

What stays with each game is what reads its zones: Stud's door-card seat
selectors, Hold'em's busted-seat ring skip, and each game's `pot_share`
primitive, which knows which of its own zones the contenders' cards sit in.

Pure functions of card values, so no declared-reads row and no bundle: nothing
here touches runtime state. (design-notes/primitive-sidecars.md §2 promotes
the poker-*family* names to the stdlib once a second poker game lands; that
promotion is about the DSL-visible selectors, not these, which no game names.)
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations

from cardlang.runtime.values import Card, Player

RANK_VALUE = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
              "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
"""Poker rank strengths, ace high. Deliberately NOT the game's `ranking:`
order: poker's hand categories are defined against this fixed scale (and the
wheel A-2-3-4-5 treats the ace as low *within a straight*, handled below), so
reading `rs.rank_index` here would let a game's ranking declaration silently
change what beats what."""


def _rank5(five: tuple[Card, ...]) -> tuple[int, ...]:
    ranks = sorted((RANK_VALUE[c.rank] for c in five), reverse=True)
    counts = Counter(ranks)
    is_flush = len({c.suit for c in five}) == 1
    distinct = sorted(set(ranks), reverse=True)
    straight_high = 0
    if len(distinct) == 5 and distinct[0] - distinct[4] == 4:
        straight_high = distinct[0]
    elif set(ranks) == {14, 2, 3, 4, 5}:  # the wheel: A-2-3-4-5
        straight_high = 5
    is_straight = straight_high > 0
    by_count = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    shape = sorted(counts.values(), reverse=True)
    if is_straight and is_flush:
        return (8, straight_high)
    if shape == [4, 1]:
        return (7, by_count[0][0], by_count[1][0])
    if shape == [3, 2]:
        return (6, by_count[0][0], by_count[1][0])
    if is_flush:
        return (5,) + tuple(ranks)
    if is_straight:
        return (4, straight_high)
    if shape == [3, 1, 1]:
        kick = sorted((r for r in ranks if r != by_count[0][0]), reverse=True)
        return (3, by_count[0][0]) + tuple(kick)
    if shape == [2, 2, 1]:
        pairs = sorted((k for k, v in counts.items() if v == 2), reverse=True)
        odd_kicker = next(k for k, v in counts.items() if v == 1)
        return (2, pairs[0], pairs[1], odd_kicker)
    if shape == [2, 1, 1, 1]:
        kick = sorted((r for r in ranks if r != by_count[0][0]), reverse=True)
        return (1, by_count[0][0]) + tuple(kick)
    return (0,) + tuple(ranks)


def hand_rank(cards: list[Card]) -> tuple[int, ...]:
    """The best five-card poker rank from any number of cards (a comparable
    tuple: category, then descending tiebreakers)."""
    return max(_rank5(combo) for combo in combinations(cards, 5))


def side_pot_payouts(
    in_hand: list[Player],
    committed: Mapping[Player, int],
    folded: Mapping[Player, bool],
    showdown_hands: Mapping[Player, Sequence[Card]],
) -> dict[Player, int]:
    """The side-pot settlement, by amount committed: layers on the distinct
    commitment levels, each layer split among its eligible contenders holding
    the best hand (ties split evenly, odd chip to the first winner in seat
    order); a lone contender (all others folded) takes the whole pot with no
    reveal needed. Pure — returns the chip delta per entrant rather than
    mutating a stack, so each game's `pot_share` primitive reads one settlement
    computation and the known-value tests pin it directly.

    `showdown_hands` is the per-contender holding ALREADY assembled by the
    calling game: Stud concatenates hole and upcards, Hold'em concatenates the
    hole with the shared community board. That is the whole game-specific part
    — entries for folded entrants are never ranked, so a game may supply them
    empty or partial."""
    payouts: dict[Player, int] = {p: 0 for p in in_hand}
    pot = sum(committed.values())
    distributed = 0
    contenders = [p for p in in_hand if not folded[p]]
    if len(contenders) == 1:
        payouts[contenders[0]] += pot
        return payouts
    best: dict[Player, tuple[int, ...]] = {
        p: hand_rank(list(showdown_hands[p])) for p in contenders
    }
    levels = sorted({committed[p] for p in in_hand if committed[p] > 0})
    prev = 0
    for lvl in levels:
        contributors = [p for p in in_hand if committed[p] >= lvl]
        amount = (lvl - prev) * len(contributors)
        eligible = [p for p in contributors if not folded[p]]
        if eligible and amount > 0:
            top = max(best[p] for p in eligible)
            winners = [p for p in eligible if best[p] == top]
            share, odd = divmod(amount, len(winners))
            for w in winners:
                payouts[w] += share
            payouts[winners[0]] += odd
            distributed += amount
        prev = lvl
    leftover = pot - distributed  # uncalled/odd remainder → best contender (conservation)
    if leftover:
        top = max(best[p] for p in contenders)
        payouts[next(p for p in contenders if best[p] == top)] += leftover
    return payouts
