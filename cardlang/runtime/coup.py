"""Coup's game-local runtime [[primitive]]s — all pure reads and trace emitters.

The game runs fully on the kernel at real interactive scope (coup.cardlang):
the turn's action pick, every challenge, every block (and WHICH character it
claims), and every action target are player decisions — `offer`s and declared
Player move parameters — and a proven challenge `reveal`s the shown card
publicly before returning it to the deck. Nothing here draws randomness: what
stays game-local is the `coup_game` trace primitive the characterization
golden and the playout invariants consume (the #142 residual); the
next-in-game seat scan is the language's own ring search
(`the first player from ... offset_by left where ...`), and the reveal
sequence derives at the harness layer from [[observation-event]]s
(tests/playout_trace.py).
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts, TraceEvent

ROW = reads.row("cardlang/runtime/coup.py", "coup.cardlang")


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
