"""Coup's game-local runtime primitives — all pure reads and trace emitters.

The game runs fully on the kernel at real interactive scope (coup.cardlang):
the turn's action pick, every challenge, every block (and WHICH character it
claims), and every action target are player decisions — `offer`s and declared
Player move parameters — and a proven challenge `reveal`s the shown card
publicly before returning it to the deck. Nothing here draws randomness: what
stays game-local is the in-game/seat scans and the character lookup (pure
reads) plus the `coup_game` trace primitive the characterization golden and
the playout invariants consume; the reveal sequence itself derives at the
harness layer from observation events (tests/playout_trace.py).
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts, TraceEvent
from cardlang.runtime.values import Player

ROW = reads.row("cardlang/runtime/coup.py", "coup.cardlang")


def _in_game(gr: reads.GameReads, p: Player) -> bool:
    return bool(
        gr.state["alive"][p]
        and gr.families["influence"][p]
    )


def coup_players_in(facts: EngineFacts, gr: reads.GameReads) -> int:
    """How many players still hold influence (the game ends at 1)."""
    return sum(1 for p in facts.seating.players if _in_game(gr, p))


def coup_next_in_game(
    facts: EngineFacts, gr: reads.GameReads, p: Player
) -> Player:
    """The next in-game player clockwise after `p` (p itself when alone)."""
    npl = len(facts.seating.players)
    return next(
        (q % npl for q in (p + 1 + i for i in range(npl)) if _in_game(gr, q % npl)),
        p,
    )


def coup_has_char(
    facts: EngineFacts, gr: reads.GameReads, p: Player, rank: str | None
) -> bool:
    """Does `p` hold the claimed character face-down (a challenge's proof)?
    `rank` is `Rank?` in CALL_SIGS and Coup passes `block_claim : Rank? = none`,
    so `None` genuinely arrives here — and matches no card, which is the
    declared semantics of proving an unset claim. The annotation (`str | None`)
    and the interface (`Rank?`) agree on exactly the value the body handles."""
    return any(c.rank == rank for c in gr.families["influence"][p])


def coup_game_summary(
    facts: EngineFacts, gr: reads.GameReads
) -> tuple[int, tuple[TraceEvent, ...]]:
    """The end-of-game `coup_game` trace: the two conservation totals
    (50 coins, 15 cards — the playout invariants) plus final coins and the
    alive vector (the characterization golden)."""
    players = list(facts.seating.players)
    coins = gr.state["coins"]
    alive = gr.state["alive"]
    treasury = gr.state["treasury"]
    total_coins = int(treasury) + sum(int(coins[p]) for p in players)
    deck = gr.singles["court_deck"]
    influence = gr.families["influence"]
    revealed = gr.families["revealed"]
    total_cards = len(deck) + sum(
        len(influence[p]) + len(revealed[p]) for p in players
    )
    event: TraceEvent = (
        "coup_game",
        {
            "total_coins": total_coins,
            "total_cards": total_cards,
            "coins": {p: coins[p] for p in players},
            "alive": {p: alive[p] for p in players},
        },
    )
    return total_coins, (event,)
