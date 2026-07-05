"""Schnapsen's game-local runtime primitive.

The hand runs fully on the kernel (schnapsen.cardlang): the leader's mixed lead
decision is the auction form of `round` over a single-participant ring, the
follower's strict-endgame answer a filtered movement, and the trick/claim/draw
bookkeeping plain statements. What stays game-local is the two-card trick
resolution — who won, given that `trick_pile` holds the leader's led card and
then the follower's answer. It also emits the play/trick_end/trick trace
events the playout-invariant harness checks winners against
(tests/test_playout_schnapsen.py).
"""

from __future__ import annotations

from cardlang.runtime.state import Ctx
from cardlang.runtime.stdlib import highest_trump_or_led_suit
from cardlang.runtime.values import Player


def schnapsen_trick_winner(ctx: Ctx, leader: Player, trump: str | None) -> Player:
    """The completed trick's winner: the highest trump if any was played, else
    the highest card of the led suit (no over-trump obligation)."""
    cards = ctx.rs.zones.single("trick_pile").cards
    assert len(cards) == 2, f"schnapsen trick pile holds {len(cards)} cards, expected 2"
    led, fcard = cards
    players = list(ctx.rs.seating.players)
    follower = players[1] if leader == players[0] else players[0]
    ctx.trace("play", (leader, led))
    ctx.trace("play", (follower, fcard))
    winner = highest_trump_or_led_suit(
        [(leader, led), (follower, fcard)], led.suit, trump, ctx.rs.rank_index
    )
    ctx.trace("trick_end", {"trump": trump})
    ctx.trace("trick", (winner, [led, fcard]))
    return winner
