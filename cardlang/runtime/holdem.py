"""Texas Hold'em's runtime support (fixed-limit, 3 players).

The corpus's second side-pot game. Chips are integer state (a `stack` per
player), not a resource-zone subsystem. The whole hand — blinds, the burn-and-
deal sequence, the four betting streets on the kernel [[round]] in priority
order, and the showdown (reveal, per-entrant pot collection, muck) — runs in
the DSL (holdem.cardlang), and the seat-ring skip that resolves the button and
the blinds past busted seats is the language's own ring search
(`the first player from ... offset_by left where in_hand[player]`). This
module holds only the one pure function not expressible there:

- `holdem_pot_share` — the showdown side-pot query (argmax over poker-rank
  tuples per commitment layer), the Primitive the showdown's settle
  statement calls.

The hand evaluator is family-wide and lives in `cardlang/runtime/poker.py`,
shared with Stud. What is NOT shared is the settlement: Stud ranks
`hole + upcards`, Hold'em ranks `hole + board`, so the two read different
zones and each keeps its own `_payouts`.

Total chips are invariant — the falsifiable invariant for the betting and pot
logic (tests/test_playout_holdem.py).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.poker import side_pot_payouts
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/holdem.py", "holdem.cardlang")

# The blinds (2/5), street limits (5/5/10/10) and raise cap (4) live in
# holdem.cardlang; this module keeps only the pot-share query.


def showdown_hands(
    in_hand: list[Player],
    hole: Mapping[Player, Sequence[Card]],
    shown: Mapping[Player, Sequence[Card]],
    board: Sequence[Card],
) -> dict[Player, list[Card]]:
    """Each entrant's showdown holding: their two private cards plus the shared
    community board.

    This is the whole of what Hold'em contributes to the settlement — the
    layering itself is family-wide (`poker.side_pot_payouts`). Two game facts
    live here. A contender's private cards sit in whichever of `hole`/`shown`
    the DSL's reveal has moved them to, so both are concatenated and the result
    is insensitive to that move (as Stud's is). And the SAME board goes into
    every contender's hand, which is the structural difference from Stud, where
    every card in a ranking belongs to one player."""
    return {p: list(hole[p]) + list(shown[p]) + list(board) for p in in_hand}


def holdem_pot_share(facts: EngineFacts, gr: reads.GameReads, player: Player) -> int:
    """The chips `player` collects at showdown: a pure read of `in_hand` /
    `committed` / `folded` state plus the live `hole`/`shown` zones and the
    `board`. No RNG, no mutation; the DSL statement
    `stack[p] := stack[p] + holdem_pot_share(p)` is what moves the chips."""
    players = list(facts.seating.players)
    committed = gr.state["committed"]
    folded = gr.state["folded"]
    in_hand_flags = gr.state["in_hand"]
    in_hand = [p for p in players if in_hand_flags[p]]
    hands = showdown_hands(
        in_hand, gr.families["hole"], gr.families["shown"], gr.singles["board"]
    )
    return side_pot_payouts(in_hand, committed, folded, hands).get(player, 0)
