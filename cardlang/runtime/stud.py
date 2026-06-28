"""Seven-Card Stud's runtime support (fixed-limit).

The corpus's first betting game. Chips are integer state (a `stack` per player),
not a resource-zone subsystem. The antes, deal, bring-in post, and the five
betting streets (3rd–7th) run in the DSL on the kernel `round` in priority order
(seven-card-stud.cardlang); this module holds only what is not expressible there:

- `run_stud_showdown` — the RNG-free showdown suffix (side-pot distribution by
  amount committed, then the muck), invoked by `instantiate StudShowdown()`;
- `hand_rank` — the best-five-of-seven poker evaluator (module-level, unit-tested);
- `bring_in_seat` / `first_to_act_seat` — the door-card seat selectors (argmin /
  argmax over players), stdlib primitives the betting phase calls.

Random players bet/call/raise/fold uniformly among the legal actions. Total chips
are invariant — the falsifiable invariant for the betting and pot logic.

Simplifications (see docs/roadmap.md): the 4th-street open-pair limit doubling is
omitted (lower limit on 3rd/4th, upper on 5th–7th); reveal order at showdown is
irrelevant to a random playout.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# The ante (1), bring-in (2), street limits (5/10), and raise cap (3) now live in
# seven-card-stud.cardlang; this module keeps only the RNG-free showdown, the
# poker evaluator, and the seat selectors.
_RV = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
       "J": 11, "Q": 12, "K": 13, "A": 14}
_SUIT_ORDER = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3}


def _rank5(five: tuple[Card, ...]) -> tuple[int, ...]:
    ranks = sorted((_RV[c.rank] for c in five), reverse=True)
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


# --- seat selectors (Stud-local stdlib primitives, called from the DSL) -------
#
# The bring-in (lowest door card) and the first-to-act on 4th-7th street (highest
# visible upcards) are argmin/argmax over players keyed on card ranks/suits —
# neither expressible in the DSL today (no single-card zone read, no argmin/argmax).
# They are pure functions of the dealt cards (no RNG), so they reproduce the
# monolith's bringer/leader exactly and the betting ring order follows.


def _lowest_door(seats: list[Player], door: dict[Player, Card]) -> Player:
    """The bring-in seat: the lowest door card (the single upcard), ties broken by
    suit (clubs < diamonds < hearts < spades)."""
    return min(seats, key=lambda p: (_RV[door[p].rank], _SUIT_ORDER[door[p].suit]))


def _highest_upcards(seats: list[Player], up: dict[Player, list[Card]]) -> Player:
    """The first-to-act seat (4th-7th street): the highest visible upcards, ranked
    by descending card values. A partial board may be fewer than five cards, so a
    lexicographic compare of the sorted ranks, not the full poker evaluator."""
    return max(seats, key=lambda p: sorted((_RV[c.rank] for c in up[p]), reverse=True))


def bring_in_seat(ctx: Ctx) -> Player:
    """The player who must post the bring-in: the lowest door card among players
    still holding chips (no one has folded at bring-in time)."""
    stack = ctx.rs.get("stack")
    up = ctx.rs.zones.families["upcards"]
    able = [p for p in ctx.rs.seating.players if stack[p] > 0]
    door = {p: up[p].cards[0] for p in able}
    return _lowest_door(able, door)


def first_to_act_seat(ctx: Ctx) -> Player:
    """The first player to act on a later street: the highest visible upcards among
    players still live (holding chips and not folded)."""
    stack = ctx.rs.get("stack")
    folded = ctx.rs.get("folded")
    players = list(ctx.rs.seating.players)
    up = ctx.rs.zones.families["upcards"]
    live = [p for p in players if stack[p] > 0 and not folded[p]]
    if not live:  # unreachable in a real hand (a street runs only with >= 2 live)
        return players[0]
    cards = {p: list(up[p].cards) for p in live}
    return _highest_upcards(live, cards)


def run_stud_showdown(stmt: n.Instantiate, ctx: Ctx) -> Player:
    """The Stud hand's showdown: side-pot settlement and the end-of-hand muck.

    The antes, deal, bring-in, and the five betting streets now run in the DSL
    (the kernel `round` in priority order); this RNG-free suffix reads the betting
    result from phase state — `in_hand`, `committed`, `folded`, `stack` — distributes
    the committed chips by side-pot layer, and mucks the hands. Because it draws no
    randomness, it cannot shift the chooser sequence: the per-hand stack golden
    pins its payouts.
    """
    rs = ctx.rs
    players = list(rs.seating.players)
    stack = rs.get("stack")
    committed = rs.get("committed")
    folded = rs.get("folded")
    in_hand_flags = rs.get("in_hand")
    in_hand = [p for p in players if in_hand_flags[p]]
    hole = rs.zones.families["hole"]
    upcards = rs.zones.families["upcards"]
    muck = rs.zones.single("muck")

    _settle(in_hand, committed, folded, stack, hole, upcards)
    for p in in_hand:  # cards leave play
        muck.add_all(hole[p].take_all())
        muck.add_all(upcards[p].take_all())
    ctx.trace(
        "stud_hand",
        {
            "total_chips": sum(stack[p] for p in players),
            # Per-seat stacks after the hand settles. The end-of-game scores are
            # degenerate (the winner holds all 400 chips), so this per-hand vector
            # is the sensitive signal a byte-identical migration must preserve.
            "stacks": {p: stack[p] for p in players},
        },
    )
    return players[0]


def _settle(
    in_hand: list[Player],
    committed: dict[Player, int],
    folded: dict[Player, bool],
    stack: dict[Player, int],
    hole: Any,
    upcards: Any,
) -> None:
    pot = sum(committed.values())
    distributed = 0
    contenders = [p for p in in_hand if not folded[p]]
    if len(contenders) == 1:
        stack[contenders[0]] += pot
        return
    best: dict[Player, tuple[int, ...]] = {
        p: hand_rank(list(hole[p].cards) + list(upcards[p].cards)) for p in contenders
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
                stack[w] += share
            stack[winners[0]] += odd
            distributed += amount
        prev = lvl
    leftover = pot - distributed  # uncalled/odd remainder → best contender (conservation)
    if leftover:
        top = max(best[p] for p in contenders)
        stack[next(p for p in contenders if best[p] == top)] += leftover
