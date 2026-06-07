"""The Seven-Card Stud hand mechanic (fixed-limit; concrete).

The corpus's first betting game. Chips are modelled as integer state (a `stack`
per player) rather than a resource-zone subsystem; the mechanic runs the antes,
the bring-in, five betting streets (3rd–7th), and the showdown with proper
side-pot distribution by amount committed. The poker hand evaluator
(`hand_rank`, best five of seven) is module-level so it can be unit-tested.

Random players bet/call/raise/fold uniformly among the legal actions (a player
never folds when checking is free). Total chips are invariant — the falsifiable
invariant for the betting and pot logic.

Simplifications (logged in IMPLEMENTATION_LOG.md): the 4th-street open-pair limit
doubling is omitted (lower limit on 3rd/4th, upper on 5th–7th); reveal order at
showdown is irrelevant to a random playout.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

_RV = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
       "J": 11, "Q": 12, "K": 13, "A": 14}
_SUIT_ORDER = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3}

ANTE = 1
BRING_IN = 2
LOWER, UPPER = 5, 10
MAX_RAISES = 3


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


def run_stud_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    choose = ctx.chooser
    args = {a.name: a.value for a in stmt.args}
    dealer: Player = evaluate(args["dealer"], ctx)  # type: ignore[arg-type]
    players = list(rs.seating.players)
    deck = rs.zones.single("deck")
    hole = rs.zones.families["hole"]
    upcards = rs.zones.families["upcards"]
    muck = rs.zones.single("muck")
    burn = rs.zones.single("burn")
    stack = rs.get("stack")

    in_hand = [p for p in players if stack[p] > 0]
    if len(in_hand) < 2:
        return dealer

    committed = {p: 0 for p in in_hand}
    folded = {p: False for p in in_hand}
    allin = {p: False for p in in_hand}

    def put(p: Player, amount: int) -> int:
        amount = min(amount, stack[p])
        stack[p] -= amount
        committed[p] += amount
        if stack[p] == 0:
            allin[p] = True
        return amount

    # antes
    for p in in_hand:
        put(p, ANTE)
    # deal two hole + one upcard
    for p in in_hand:
        hole[p].add(deck.cards.pop(0))
        hole[p].add(deck.cards.pop(0))
        upcards[p].add(deck.cards.pop(0))

    # bring-in: lowest door (upcard), ties by suit. If fewer than two players
    # can act (everyone went all-in on the ante — e.g. each entered with exactly
    # one chip), there is no bring-in or betting: the hand is dealt out and goes
    # straight to showdown.
    able = [p for p in in_hand if not allin[p]]
    bet_by = {p: 0 for p in in_hand}
    bringer: Player | None = None
    if len(able) >= 2:
        bringer = min(able, key=lambda p: (_RV[upcards[p].cards[0].rank], _SUIT_ORDER[upcards[p].cards[0].suit]))
        bet_by[bringer] = put(bringer, BRING_IN)

    def order_from(start: Player) -> list[Player]:
        si = in_hand.index(start) if start in in_hand else 0
        return in_hand[si:] + in_hand[:si]

    def betting_round(first: Player, opening: int, limit: int, bet_by0: dict[Player, int]) -> None:
        order = order_from(first)
        bet_by = dict(bet_by0)
        bet_to_match = opening
        raises = 1 if opening > 0 else 0
        acted: set[Player] = set()
        guard = 0
        while True:
            guard += 1
            if guard > 2000:
                break
            pending = [
                p for p in order
                if not folded[p] and not allin[p]
                and (p not in acted or bet_by[p] < bet_to_match)
            ]
            if not pending:
                break
            p = pending[0]
            to_call = bet_to_match - bet_by[p]
            if to_call <= 0:
                opts = ["check"] + (["bet"] if bet_to_match == 0 else [])
            else:
                opts = ["call", "fold"] + (
                    ["raise"] if bet_to_match > 0 and raises < MAX_RAISES else []
                )
            a = choose(p, opts, 1)[0]
            if a == "check":
                acted.add(p)
            elif a == "call":
                bet_by[p] += put(p, to_call)
                acted.add(p)
            elif a == "bet":
                bet_by[p] += put(p, limit)
                bet_to_match = bet_by[p]
                raises = 1
                acted = {p}
            elif a == "raise":
                bet_by[p] += put(p, to_call + limit)
                bet_to_match = max(bet_to_match, bet_by[p])
                raises += 1
                acted = {p}
            else:  # fold
                folded[p] = True
                muck.add_all(upcards[p].take_all())
            live = [q for q in in_hand if not folded[q] and not allin[q]]
            if len(live) <= 1 and all(bet_by[q] >= bet_to_match for q in live):
                if not any(  # nobody still owes a call
                    q for q in in_hand
                    if not folded[q] and not allin[q] and bet_by[q] < bet_to_match
                ):
                    break

    def deal_street(face_up: bool) -> None:
        if deck.cards:
            burn.add(deck.cards.pop(0))
        for p in in_hand:
            if not folded[p] and deck.cards:
                (upcards[p] if face_up else hole[p]).add(deck.cards.pop(0))

    def first_to_act() -> Player:
        # Highest visible upcards act first; ranked by descending card values (a
        # partial hand may be fewer than five cards, so not the full evaluator).
        live = [p for p in in_hand if not folded[p] and not allin[p]]
        if not live:
            return in_hand[0]
        return max(live, key=lambda p: sorted((_RV[c.rank] for c in upcards[p].cards), reverse=True))

    def contenders() -> list[Player]:
        return [p for p in in_hand if not folded[p]]

    # 3rd street (bring-in standing as the opening bet), then 4th–7th
    if bringer is not None and len(contenders()) > 1:
        betting_round(order_from(bringer)[1], BRING_IN, LOWER, bet_by)
    for street, limit, face_up in [(4, LOWER, True), (5, UPPER, True), (6, UPPER, True), (7, UPPER, False)]:
        if len(contenders()) <= 1:
            break
        deal_street(face_up)
        if len([p for p in contenders() if not allin[p]]) >= 2:
            betting_round(first_to_act(), 0, limit, {p: 0 for p in in_hand})

    # showdown: distribute committed chips by side-pot layers
    _settle(in_hand, committed, folded, stack, hole, upcards)

    for p in in_hand:  # cards leave play
        muck.add_all(hole[p].take_all())
        muck.add_all(upcards[p].take_all())
    ctx.trace("stud_hand", {"total_chips": sum(stack[p] for p in players)})
    return dealer


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
