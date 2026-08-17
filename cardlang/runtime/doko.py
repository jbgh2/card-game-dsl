"""Doppelkopf's game-local runtime [[primitive]].

The hand runs fully on the kernel (doppelkopf.cardlang): hand-rolled tricks
(four single-actor filtered [[transfer]]s, the Skat shape) with a quiescence-lap
announcement poll before each play, follow legality and the announcement
guards in in-DSL functions, and the scoring in plain statements. What stays
game-local is exactly one query the expression language cannot phrase: the
trick winner, which needs the pile's play order because the double pack
makes ties real — of two identical winning cards, the FIRST played wins.

The normal game's trump structure is fixed (no bid solos in the corpus
scope): both hearts 10s (the Dulle) on top, then the queens, the jacks
(clubs > spades > hearts > diamonds within each rank), then the plain
diamonds. The primitive emits the play/trick traces the playout harness
recomputes winners from (tests/test_playout_doppelkopf.py).
"""

from __future__ import annotations

from cardlang.runtime import reads, winners
from cardlang.runtime.narrowing import EngineFacts, TraceEvent
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/doko.py", "doppelkopf.cardlang")

# Plain-suit order (queens and jacks are never plain; the hearts 10 is a
# trump, so plain hearts run A K 9 — the rank map covers the union).
_PLAIN_RANK = {"A": 4, "10": 3, "K": 2, "9": 1}
# Within queens and jacks: clubs > spades > hearts > diamonds.
_SUIT_ORDER = {"clubs": 4, "spades": 3, "hearts": 2, "diamonds": 1}
# Plain-diamond trumps below the jacks: A > 10 > K > 9.
_DIAMOND_RANK = {"A": 4, "10": 3, "K": 2, "9": 1}


def _is_trump(c: Card) -> bool:
    return (
        c.rank in ("Q", "J")
        or c.suit == "diamonds"
        or (c.suit == "hearts" and c.rank == "10")
    )


def _trump_strength(c: Card) -> int:
    if c.suit == "hearts" and c.rank == "10":
        return 300
    if c.rank == "Q":
        return 200 + _SUIT_ORDER[c.suit]
    if c.rank == "J":
        return 100 + _SUIT_ORDER[c.suit]
    return _DIAMOND_RANK[c.rank]


def doko_trick_winner(
    facts: EngineFacts, gr: reads.GameReads
) -> tuple[Player, tuple[TraceEvent, ...]]:
    """The completed four-card trick's winner: the strongest trump if any
    was played, else the strongest card of the led suit — strictly-greater
    comparison, so of two identical cards the first played wins (the
    double-pack rule). Who played each card is the kernel's Arrival Record
    (`gr.arrivals`, issue #256), in play order — attribution is read, never
    re-derived from seat arithmetic.
    """
    played = winners.recorded_plays(gr.arrivals["trick_pile"], "doko_trick_winner", 4)
    cards = [c for _, c in played]
    events: list[TraceEvent] = [("play", (q, c)) for q, c in played]
    trumps = [(p, c) for p, c in played if _is_trump(c)]
    if trumps:
        best = trumps[0]
        for p, c in trumps[1:]:
            if _trump_strength(c) > _trump_strength(best[1]):
                best = (p, c)
    else:
        led_suit = cards[0].suit
        of_led = [(p, c) for p, c in played if c.suit == led_suit]
        best = of_led[0]
        for p, c in of_led[1:]:
            if _PLAIN_RANK[c.rank] > _PLAIN_RANK[best[1].rank]:
                best = (p, c)
    events.append(("trick", (best[0], list(cards))))
    return best[0], tuple(events)
