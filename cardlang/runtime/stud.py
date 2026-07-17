"""Seven-Card Stud's runtime support (fixed-limit).

The corpus's first betting game. Chips are integer state (a `stack` per player),
not a resource-zone subsystem. The whole hand — antes, deal, bring-in post, the
five betting streets (3rd–7th) on the kernel `round` in priority order, and the
showdown (reveal, per-entrant pot collection, muck) — runs in the DSL
(seven-card-stud.cardlang); this module holds only the pure functions not
expressible there:

- `hand_rank` — the best-five-of-seven poker evaluator (module-level, unit-tested);
- `bring_in_seat` / `first_to_act_seat` — the door-card seat selectors (argmin /
  argmax over players), stdlib primitives the betting phase calls;
- `pot_share` — the showdown side-pot query (argmax over poker-rank tuples per
  layer), the stdlib primitive the showdown's settle statement calls.

Random players bet/call/raise/fold uniformly among the legal actions. Total chips
are invariant — the falsifiable invariant for the betting and pot logic.

Simplifications (see docs/roadmap.md): the 4th-street open-pair limit doubling is
omitted (lower limit on 3rd/4th, upper on 5th–7th).
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from cardlang.runtime import reads
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

_R = reads.row("cardlang/runtime/stud.py", "seven-card-stud.cardlang")

# The ante (1), bring-in (2), street limits (5/10), and raise cap (3) live in
# seven-card-stud.cardlang; this module keeps only the poker evaluator, the seat
# selectors, and the pot-share query.
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
    stack = reads.state(ctx.rs, _R, "stack")
    up = reads.family(ctx.rs, _R, "upcards")
    able = [p for p in ctx.rs.seating.players if stack[p] > 0]
    door = {p: up[p].cards[0] for p in able}
    return _lowest_door(able, door)


def first_to_act_seat(ctx: Ctx) -> Player:
    """The first player to act on a later street: the highest visible upcards among
    players still live (holding chips and not folded)."""
    stack = reads.state(ctx.rs, _R, "stack")
    folded = reads.state(ctx.rs, _R, "folded")
    players = list(ctx.rs.seating.players)
    up = reads.family(ctx.rs, _R, "upcards")
    live = [p for p in players if stack[p] > 0 and not folded[p]]
    if not live:  # unreachable in a real hand (a street runs only with >= 2 live)
        return players[0]
    cards = {p: list(up[p].cards) for p in live}
    return _highest_upcards(live, cards)


def _payouts(
    in_hand: list[Player],
    committed: dict[Player, int],
    folded: dict[Player, bool],
    hole: Any,
    upcards: Any,
) -> dict[Player, int]:
    """The side-pot settlement, by amount committed: layers on the distinct
    commitment levels, each layer split among its eligible contenders holding the
    best hand (ties split evenly, odd chip to the first winner in seat order); a
    lone contender (all others folded) takes the whole pot with no reveal needed.
    Pure — returns the chip delta per entrant rather than mutating a stack, so
    `pot_share` reads one settlement computation and the known-value side-pot
    tests pin it directly."""
    payouts: dict[Player, int] = {p: 0 for p in in_hand}
    pot = sum(committed.values())
    distributed = 0
    contenders = [p for p in in_hand if not folded[p]]
    if len(contenders) == 1:
        payouts[contenders[0]] += pot
        return payouts
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
                payouts[w] += share
            payouts[winners[0]] += odd
            distributed += amount
        prev = lvl
    leftover = pot - distributed  # uncalled/odd remainder → best contender (conservation)
    if leftover:
        top = max(best[p] for p in contenders)
        payouts[next(p for p in contenders if best[p] == top)] += leftover
    return payouts


def pot_share(ctx: Ctx, player: Player) -> int:
    """The chips `player` collects at showdown: a pure read of `in_hand` /
    `committed` / `folded` state plus the live `hole`/`upcards` zones (whichever
    of the two the cards currently sit in — the DSL's reveal move only changes
    which zone holds them, not the concatenated 7-card hand `_payouts` ranks). No
    RNG, no mutation; the DSL statement `stack[p] := stack[p] + pot_share(p)`
    is what actually moves the chips."""
    rs = ctx.rs
    players = list(rs.seating.players)
    committed = reads.state(rs, _R, "committed")
    folded = reads.state(rs, _R, "folded")
    in_hand_flags = reads.state(rs, _R, "in_hand")
    in_hand = [p for p in players if in_hand_flags[p]]
    hole = reads.family(rs, _R, "hole")
    upcards = reads.family(rs, _R, "upcards")
    return _payouts(in_hand, committed, folded, hole, upcards).get(player, 0)
