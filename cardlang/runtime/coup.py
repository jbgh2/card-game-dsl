"""Coup's game-local runtime primitives — all pure reads and trace emitters.

The game runs fully on the kernel at real interactive scope (coup.cardlang):
the turn's action pick, every challenge, every block (and WHICH character it
claims), and every action target are player decisions — `offer`s and declared
Player move parameters — and a proven challenge `reveal`s the shown card
publicly before returning it to the deck. Nothing here draws randomness: what
stays game-local is the in-game/seat scans and the character lookup (pure
reads) plus two trace primitives that keep the `coup_reveal` / `coup_game`
events the characterization golden and the playout invariants consume.
"""

from __future__ import annotations

from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Player


def _in_game(ctx: Ctx, p: Player) -> bool:
    return bool(
        ctx.rs.get("alive")[p] == 1 and ctx.rs.zones.families["influence"][p].cards
    )


def coup_players_in(ctx: Ctx) -> int:
    """How many players still hold influence (the game ends at 1)."""
    return sum(1 for p in ctx.rs.seating.players if _in_game(ctx, p))


def coup_next_in_game(ctx: Ctx, p: Player) -> Player:
    """The next in-game player clockwise after `p` (p itself when alone)."""
    npl = len(ctx.rs.seating.players)
    return next(
        (q % npl for q in (p + 1 + i for i in range(npl)) if _in_game(ctx, q % npl)),
        p,
    )


def coup_has_char(ctx: Ctx, p: Player, rank: str) -> bool:
    """Does `p` hold the claimed character face-down (a challenge's proof)?"""
    return any(c.rank == rank for c in ctx.rs.zones.families["influence"][p].cards)


def coup_note_reveal(ctx: Ctx, p: Player) -> int:
    """Trace the influence flip that just happened (the last card into
    `revealed[p]`) — the per-seed reveal-sequence golden's anchor."""
    card = ctx.rs.zones.families["revealed"][p].cards[-1]
    ctx.trace("coup_reveal", (p, card.rank))
    return 0


def coup_game_summary(ctx: Ctx) -> int:
    """Emit the end-of-game `coup_game` trace: the two conservation totals
    (50 coins, 15 cards — the playout invariants) plus final coins and the
    alive vector (the characterization golden)."""
    players = list(ctx.rs.seating.players)
    coins = ctx.rs.get("coins")
    alive = ctx.rs.get("alive")
    treasury = ctx.rs.get("treasury")
    total_coins = int(treasury) + sum(int(coins[p]) for p in players)
    deck = ctx.rs.zones.single("court_deck")
    influence = ctx.rs.zones.families["influence"]
    revealed = ctx.rs.zones.families["revealed"]
    total_cards = len(deck.cards) + sum(
        len(influence[p].cards) + len(revealed[p].cards) for p in players
    )
    ctx.trace(
        "coup_game",
        {
            "total_coins": total_coins,
            "total_cards": total_cards,
            "coins": {p: coins[p] for p in players},
            "alive": {p: alive[p] for p in players},
        },
    )
    return total_coins
