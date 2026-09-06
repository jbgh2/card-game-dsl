"""Heads-up fixed-limit Texas Hold'em's runtime support (2 players, one hand).

This module holds ONE function, and it holds no arithmetic of its own. The
showdown maths is family-wide (`poker.side_pot_payouts`) and the "which cards
does a contender show" fact is Hold'em-wide (`holdem.showdown_hands`, the two
hole cards plus the shared board); both are imported. What is left is the
delegation itself.

This name is a second BINDING of `holdem_pot_share`'s query, not a second
query, and nothing in the engine keeps the two apart: a `primitives { }`
entry binds its Python by name through `PRIMITIVE_IMPLEMENTATIONS`, its
[[reads-clause]] is the entry's own, and two games may declare one name —
the heads-up game may declare `holdem_pot_share` itself. Retiring this
module and the name's registry rows is issue #232. What a declared game
cannot do is CALL a name its own block does not declare
(`primitives_block.call_namespace`, the call-position namespace). The slots
the block does not cover (`primitives_block.WALLED_NAMESPACES`, issue #142)
still take any game's Primitive, and that no pin notices a game reaching
another game's Primitive that way is issue #238.

The duplication that would matter — two copies of side-pot arithmetic, which
drift while both still conserve chips — does not occur: there is one copy, in
`cardlang/runtime/poker.py`, and this module calls it.

Total chips are invariant, and no seat can go all-in: the game's four street
caps sum to 48 against a 100-chip stack. Both are falsifiable invariants
(tests/test_playout_holdem_heads_up.py).
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.holdem import showdown_hands
from cardlang.runtime.poker import side_pot_payouts
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Player


def holdem_heads_up_pot_share(
    facts: EngineFacts, gr: reads.GameReads, player: Player
) -> int:
    """The chips `player` collects at showdown: a pure read of `in_hand` /
    `committed` / `folded` state plus the live `hole`/`shown` zones and the
    `board`. No RNG, no mutation; the DSL statement
    `stack[p] := stack[p] + holdem_heads_up_pot_share(p)` is what moves the
    chips.

    `side_pot_payouts` layers by commitment, which is more than this game can
    ever need — with no all-in reachable there is exactly one layer. It is used
    anyway rather than a two-way comparison written here, because the general
    routine is the tested one and a hand-rolled two-way settle would be a second
    copy of the payout rule."""
    players = list(facts.seating.players)
    committed = gr.state["committed"]
    folded = gr.state["folded"]
    in_hand_flags = gr.state["in_hand"]
    in_hand = [p for p in players if in_hand_flags[p]]
    hands = showdown_hands(
        in_hand, gr.families["hole"], gr.families["shown"], gr.singles["board"]
    )
    return side_pot_payouts(in_hand, committed, folded, hands).get(player, 0)
