"""The Cribbage hand mechanic (two-player, six-card; concrete).

Cribbage is a counting game, not a trick game: discard two to the crib, cut a
starter, peg through alternating play to 31 (scoring fifteens, pairs, runs, 31s,
and the last card), then *show* — count fifteens, pairs, runs, flush, and his
nob in the non-dealer's hand, the dealer's hand, and the crib (each against the
shared starter, in that order). First to 121 wins, and the count stops the
instant someone crosses (the non-dealer shows first), so the winner is exactly
the first to reach 121.

The combination scorers are module-level so they can be unit-tested against known
cribbage hands — the strongest falsifiable check for a counting game.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

_VALUE = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
          "10": 10, "J": 10, "Q": 10, "K": 10}
_ORDER = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
          "10": 10, "J": 11, "Q": 12, "K": 13}


def value(c: Card) -> int:
    """Pegging / fifteens value: A=1, face cards 10, otherwise pips."""
    return _VALUE[c.rank]


# --- the show ---


def count_fifteens(cards: list[Card]) -> int:
    vals = [_VALUE[c.rank] for c in cards]
    subsets = sum(
        1
        for r in range(2, len(vals) + 1)
        for combo in combinations(vals, r)
        if sum(combo) == 15
    )
    return 2 * subsets


def count_pairs(cards: list[Card]) -> int:
    return 2 * sum(1 for a, b in combinations(cards, 2) if a.rank == b.rank)


def run_score(cards: list[Card]) -> int:
    """Length × multiplicity of the longest run (≥3) over the ranks."""
    counts: dict[int, int] = {}
    for c in cards:
        counts[_ORDER[c.rank]] = counts.get(_ORDER[c.rank], 0) + 1
    distinct = sorted(counts)
    i = 0
    while i < len(distinct):
        j = i
        while j + 1 < len(distinct) and distinct[j + 1] == distinct[j] + 1:
            j += 1
        length = j - i + 1
        if length >= 3:
            mult = 1
            for k in range(i, j + 1):
                mult *= counts[distinct[k]]
            return length * mult
        i = j + 1
    return 0


def flush_score(hand4: list[Card], starter: Card, is_crib: bool) -> int:
    if len({c.suit for c in hand4}) != 1:
        return 0
    if starter.suit == hand4[0].suit:
        return 5
    return 0 if is_crib else 4


def nob_score(hand4: list[Card], starter: Card) -> int:
    return 1 if any(c.rank == "J" and c.suit == starter.suit for c in hand4) else 0


def show_score(hand4: list[Card], starter: Card, is_crib: bool) -> int:
    five = [*hand4, starter]
    return (
        count_fifteens(five)
        + count_pairs(five)
        + run_score(five)
        + flush_score(hand4, starter, is_crib)
        + nob_score(hand4, starter)
    )


# --- pegging ---


def peg_pair_points(seq: list[Card]) -> int:
    if len(seq) < 2:
        return 0
    n_same = 1
    for c in reversed(seq[:-1]):
        if c.rank == seq[-1].rank:
            n_same += 1
        else:
            break
    return n_same * (n_same - 1) if n_same >= 2 else 0


def peg_run_points(seq: list[Card]) -> int:
    for k in range(len(seq), 2, -1):
        orders = [_ORDER[c.rank] for c in seq[-k:]]
        if len(set(orders)) == k and max(orders) - min(orders) == k - 1:
            return k
    return 0


def run_cribbage_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    choose = ctx.chooser
    args = {a.name: a.value for a in stmt.args}
    dealer: Player = evaluate(args["dealer"], ctx)  # type: ignore[arg-type]
    players = list(rs.seating.players)

    def other(p: Player) -> Player:
        return players[1] if p == players[0] else players[0]

    hands = rs.zones.families["hand"]
    crib = rs.zones.single("crib")
    starter_zone = rs.zones.single("starter")
    played = rs.zones.families["played"]
    play_pile = rs.zones.single("play_pile")
    deck = rs.zones.single("deck")
    score = rs.get("score")
    nondealer = other(dealer)
    over = {"done": False}

    def add(p: Player, pts: int) -> None:
        if over["done"] or pts == 0:
            return
        score[p] += pts
        if score[p] >= 121:
            over["done"] = True

    # discard two each to the crib
    for p in players:
        for c in choose(p, list(hands[p].cards), 2):
            hands[p].remove(c)
            crib.add(c)
    hand4 = {p: list(hands[p].cards) for p in players}  # the show hands (pre-pegging)

    # cut the starter
    starter = deck.cards.pop(0)
    starter_zone.add(starter)
    if starter.rank == "J":
        add(dealer, 2)  # his heels
    if over["done"]:
        return dealer

    # pegging
    total = 0
    seq: list[tuple[Player, Card]] = []
    gos = 0
    last_played: Player | None = None
    active = nondealer

    def close(scored31: bool) -> None:
        nonlocal total, seq, gos
        if not scored31 and last_played is not None:
            add(last_played, 1)  # last card / go
        for pl, c in seq:  # the round's cards live in play_pile until now
            play_pile.remove(c)
            played[pl].add(c)
        total, seq, gos = 0, [], 0

    while hands[players[0]].cards or hands[players[1]].cards:
        if not hands[active].cards:
            active = other(active)
            continue
        playable = [c for c in hands[active].cards if total + value(c) <= 31]
        if playable:
            c = choose(active, playable, 1)[0]
            hands[active].remove(c)
            play_pile.add(c)
            seq.append((active, c))
            total += value(c)
            last_played = active
            gos = 0
            round_cards = [card for _, card in seq]
            if total in (15, 31):
                add(active, 2)
            add(active, peg_pair_points(round_cards))
            add(active, peg_run_points(round_cards))
            if over["done"]:
                return dealer
            if total == 31:
                close(True)
                active = other(active)  # the player who reached 31 just played
                continue
            active = other(active)
        else:
            gos += 1
            if gos >= 2:
                next_leader = other(last_played) if last_played is not None else active
                close(False)
                if over["done"]:
                    return dealer
                active = next_leader
                continue
            active = other(active)
    if seq:  # final open round: last card
        close(total == 31)
        if over["done"]:
            return dealer

    # the show: non-dealer hand, dealer hand, crib — in that order, early-out
    batches = [
        (hand4[nondealer], nondealer, False),
        (hand4[dealer], dealer, False),
        (list(crib.cards), dealer, True),
    ]
    for cards, owner, is_crib in batches:
        pts = show_score(cards, starter, is_crib)
        add(owner, pts)
        ctx.trace(
            "cribbage_show",
            {"owner": owner, "points": pts, "is_crib": is_crib},
        )
        if over["done"]:
            break
    return dealer
