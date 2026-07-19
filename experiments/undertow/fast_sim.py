"""Fast Undertow simulator — the speed twin of undertow.cardlang.

The MCCFR lesson (REPORT §4) was that search/training at this game's size
needs engine throughput the re-simulation adapter deliberately doesn't
offer. This module is the pipeline plan's answer: a hand-written fast
engine whose ONLY authority is the DSL runtime — every semantic (follow
legality, trick winner, tide selection incl. the earliest-played tie rule,
returns) is pinned by differential fixtures exported from the adapter
(`export_fixtures.py` + `test_against_fixtures`). PIMC thinks against this
engine; the artifact's JS engine is a line-by-line port of it.

Cards are ints 0..51: rank_value = c % 13 (2→0 … A→12), suit = c // 13
(0=♣ 1=♦ 2=♥ 3=♠ — matching the label glyphs the adapter renders).
"""

from __future__ import annotations

import random

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♣", "♦", "♥", "♠"]
TWO_OF_CLUBS = 0  # rank_value 0, suit 0


def label(c: int) -> str:
    return RANKS[c % 13] + SUITS[c // 13]


def parse_label(s: str) -> int:
    suit = SUITS.index(s[-1])
    return suit * 13 + RANKS.index(s[:-1])


class Sim:
    """One hand of Undertow. Mutable; copy() before speculative play."""

    __slots__ = (
        "hands", "trump", "leader", "to_play", "trick", "tricks_won", "played", "history",
    )

    def __init__(self, hands: list[list[int]], leader: int | None = None) -> None:
        self.hands = [sorted(h) for h in hands]
        self.trump: int | None = None            # suit index, None = no trump
        self.leader = (
            leader
            if leader is not None
            else next(p for p in range(4) if TWO_OF_CLUBS in self.hands[p])
        )
        self.to_play = self.leader
        self.trick: list[tuple[int, int]] = []   # (player, card) in play order
        self.tricks_won = [0, 0, 0, 0]
        self.played: list[int] = []              # all cards played, in order
        self.history: list[list[tuple[int, int]]] = []  # completed tricks

    def copy(self) -> "Sim":
        s = Sim.__new__(Sim)
        s.hands = [list(h) for h in self.hands]
        s.trump = self.trump
        s.leader = self.leader
        s.to_play = self.to_play
        s.trick = list(self.trick)
        s.tricks_won = list(self.tricks_won)
        s.played = list(self.played)
        s.history = [list(t) for t in self.history]
        return s

    def terminal(self) -> bool:
        return all(not h for h in self.hands)

    def legal(self) -> list[int]:
        hand = self.hands[self.to_play]
        if not self.trick:
            return list(hand)
        led = self.trick[0][1] // 13
        follow = [c for c in hand if c // 13 == led]
        return follow if follow else list(hand)

    def apply(self, card: int) -> None:
        p = self.to_play
        self.hands[p].remove(card)
        self.trick.append((p, card))
        self.played.append(card)
        if len(self.trick) < 4:
            self.to_play = (p + 1) % 4
            return
        # resolve: winner = highest trump if any, else highest of led suit
        led = self.trick[0][1] // 13
        if self.trump is not None and any(c // 13 == self.trump for _, c in self.trick):
            winner, _ = max(
                ((q, c) for q, c in self.trick if c // 13 == self.trump),
                key=lambda qc: qc[1] % 13,
            )
        else:
            winner, _ = max(
                ((q, c) for q, c in self.trick if c // 13 == led),
                key=lambda qc: qc[1] % 13,
            )
        # the undertow: lowest rank, EARLIEST PLAYED breaks ties, names trump
        low = min(c % 13 for _, c in self.trick)
        tide_card = next(c for _, c in self.trick if c % 13 == low)
        self.trump = tide_card // 13
        self.tricks_won[winner] += 1
        self.leader = winner
        self.to_play = winner
        self.history.append(self.trick)
        self.trick = []

    def rollout_random(self, rng: random.Random) -> list[int]:
        while not self.terminal():
            self.apply(rng.choice(self.legal()))
        return self.tricks_won


def voids_from_history(history: list[list[tuple[int, int]]]) -> list[set[int]]:
    """Suits each player has shown void in (played off-suit on that lead)."""
    voids: list[set[int]] = [set(), set(), set(), set()]
    for trick in history:
        if not trick:
            continue
        led = trick[0][1] // 13
        for q, c in trick[1:]:
            if c // 13 != led:
                voids[q].add(led)
    return voids
