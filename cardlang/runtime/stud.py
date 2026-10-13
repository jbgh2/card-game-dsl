"""The Stud family's runtime support (fixed-limit).

Chips are integer state (a `stack` per player), not a resource-zone subsystem.
The whole hand — antes, deal, bring-in post, the betting streets on the kernel
[[round]]'s ring, the seats each street opens on, and the showdown (reveal,
per-entrant pot collection, muck) — runs in the DSL (five-card-stud.cardlang,
seven-card-stud.cardlang, and the family libraries they use); this module holds
only the settlement:

- `pot_share` — the showdown side-pot query (argmax over poker-rank tuples per
  layer), the Primitive the showdown's settle statement calls.

The hand evaluator itself is family-wide and lives in `cardlang/runtime/poker.py`,
shared with Hold'em: which cards a player has available is a property of the
game, how five of them compare is not.

Random players bet/call/raise/fold uniformly among the legal actions. Total chips
are invariant — the falsifiable invariant for the betting and pot logic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cardlang.runtime import reads
from cardlang.runtime.poker import side_pot_payouts
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player


def showdown_hands(
    in_hand: list[Player],
    hole: Mapping[Player, Sequence[Card]],
    upcards: Mapping[Player, Sequence[Card]],
) -> dict[Player, list[Card]]:
    """Each entrant's showdown holding: their private and upcard cards
    together, however many of each the declaring game deals.

    Assembling the holding is the whole of what a game contributes to the
    settlement — the layering itself is family-wide
    (`poker.side_pot_payouts`). The one game fact here is that a DSL reveal
    move only changes WHICH of `hole`/`upcards` holds a contender's cards, not
    the concatenation, so both are concatenated and the result is insensitive
    to that move. Any game whose contenders show exactly the union of those
    two zones assembles its holding this way; the count is not read."""
    return {p: list(hole[p]) + list(upcards[p]) for p in in_hand}


def pot_share(facts: EngineFacts, gr: reads.GameReads, player: Player) -> int:
    """The chips `player` collects at showdown: a pure read of `in_hand` /
    `committed` / `folded` state plus the live `hole`/`upcards` zones. No RNG, no
    mutation; the DSL statement `stack[p] := stack[p] + pot_share(p)` is what
    actually moves the chips."""
    players = list(facts.seating.players)
    committed = gr.state["committed"]
    folded = gr.state["folded"]
    in_hand_flags = gr.state["in_hand"]
    in_hand = [p for p in players if in_hand_flags[p]]
    hands = showdown_hands(in_hand, gr.families["hole"], gr.families["upcards"])
    return side_pot_payouts(in_hand, committed, folded, hands).get(player, 0)
