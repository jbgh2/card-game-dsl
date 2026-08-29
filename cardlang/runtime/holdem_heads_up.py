"""Heads-up fixed-limit Texas Hold'em's runtime support (2 players, one hand).

This module holds ONE function, and it holds no arithmetic of its own. The
showdown maths is family-wide (`poker.side_pot_payouts`) and the "which cards
does a contender show" fact is Hold'em-wide (`holdem.showdown_hands`, the two
hole cards plus the shared board); both are imported. What is left is the
delegation itself.

Why the delegation exists at all, rather than `holdem-heads-up.cardlang`
calling `holdem_pot_share` directly: `holdem.cardlang` writes no
`primitives { }` block, so its reads are a `PRIMITIVE_READS` row keyed on
(module, game_file) and `holdem.py` binds that ONE row at import
(`ROW = reads.row(...)`) — it serves `holdem.cardlang` and only that.
Reusing its primitive here would run this game's showdown against a row
that does not name it, and `tests/test_primitive_reads.py` pins each row
against its own game's declarations — so a later edit to `holdem.cardlang`'s
zone names would silently break a game no pin was watching. This game
declares instead, and a declaration carries its own reads per call, which is
what a module constant cannot do (issue #232). That a LEGACY game can call
another legacy game's primitive with no pin is issue #238; a declared game
cannot, because its `f(...)` calls resolve against its own namespace alone.

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
