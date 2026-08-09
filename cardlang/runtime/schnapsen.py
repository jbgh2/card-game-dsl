"""Schnapsen's game-local runtime primitive.

The hand runs fully on the kernel (schnapsen.cardlang): the leader's mixed lead
decision is the auction form of `round` over a single-participant ring, the
follower's strict-endgame answer a filtered movement, and the trick/claim/draw
bookkeeping plain statements. What stays game-local is the two-card trick
resolution — who won, given that `trick_pile` holds the leader's led card and
then the follower's answer. It returns the play/trick_end/trick trace events
alongside the winner, and the dispatch layer emits them; the
playout-invariant harness checks winners against those
(tests/test_playout_schnapsen.py).
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.primitives import highest_trump_or_led_suit
from cardlang.runtime.narrowing import EngineFacts, TraceEvent
from cardlang.runtime.values import Player

ROW = reads.row("cardlang/runtime/schnapsen.py", "schnapsen.cardlang")


def schnapsen_trick_winner(
    facts: EngineFacts, gr: reads.GameReads, leader: Player, trump: str | None
) -> tuple[Player, tuple[TraceEvent, ...]]:
    """The completed trick's winner: the highest trump if any was played, else
    the highest card of the led suit (no over-trump obligation). Returns the
    winner with the trace events the dispatch layer emits on its behalf."""
    cards = gr.singles["trick_pile"]
    if len(cards) != 2:
        # The pile's live size is the hosting game's runtime data, so a wrong
        # call site is the description's error, so this raise is its Owner Guard.
        raise OwnerGuardError(
            f"schnapsen_trick_winner: trick pile holds {len(cards)} cards, "
            f"expected a completed 2-card trick"
        )
    led, fcard = cards
    players = list(facts.seating.players)
    follower = players[1] if leader == players[0] else players[0]
    winner = highest_trump_or_led_suit(
        [(leader, led), (follower, fcard)], led.suit, trump, dict(facts.rank_index)
    )
    return winner, (
        ("play", (leader, led)),
        ("play", (follower, fcard)),
        ("trick_end", {"trump": trump}),
        ("trick", (winner, [led, fcard])),
    )
