"""Seven-Card Stud's runtime support (fixed-limit).

The corpus's first betting game. Chips are integer state (a `stack` per player),
not a resource-zone subsystem. The whole hand — antes, deal, bring-in post, the
five betting streets (3rd–7th) on the kernel [[round]] in priority order, and the
showdown (reveal, per-entrant pot collection, muck) — runs in the DSL
(seven-card-stud.cardlang); this module holds only the pure functions not
expressible there:

- `bring_in_seat` / `first_to_act_seat` — the door-card [[seat]] selectors (argmin /
  argmax over players), Primitives the betting phase calls;
- `pot_share` — the showdown side-pot query (argmax over poker-rank tuples per
  layer), the Primitive the showdown's settle statement calls.

The hand evaluator itself is family-wide and lives in `cardlang/runtime/poker.py`,
shared with Hold'em: which cards a player has available is a property of the
game, how five of them compare is not.

Random players bet/call/raise/fold uniformly among the legal actions. Total chips
are invariant — the falsifiable invariant for the betting and pot logic.

Simplifications (see docs/games/seven-card-stud.md): the 4th-street open-pair
limit doubling is
omitted (lower limit on 3rd/4th, upper on 5th–7th).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cardlang.runtime import reads
from cardlang.runtime.poker import RANK_VALUE, side_pot_payouts
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/stud.py", "seven-card-stud.cardlang")

# The ante (1), bring-in (2), street limits (5/10), and raise cap (3) live in
# seven-card-stud.cardlang; this module keeps only the seat selectors and the
# pot-share query. The hand evaluator is family-wide, so it lives in
# cardlang/runtime/poker.py (shared with Hold'em).
_SUIT_ORDER = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3}


# --- seat selectors (Stud-local Primitives, called from the DSL) -------
#
# The bring-in (lowest door card) and the first-to-act on 4th-7th street (highest
# visible upcards) are argmin/argmax over players keyed on card ranks/suits —
# neither expressible in the DSL today (no single-card zone read, no argmin/argmax).
# They are pure functions of the dealt cards (no RNG), so they reproduce the
# monolith's bringer/leader exactly and the betting ring order follows.


def _lowest_door(seats: list[Player], door: dict[Player, Card]) -> Player:
    """The bring-in seat: the lowest door card (the single upcard), ties broken by
    suit (clubs < diamonds < hearts < spades)."""
    return min(seats, key=lambda p: (RANK_VALUE[door[p].rank], _SUIT_ORDER[door[p].suit]))


def _highest_upcards(seats: list[Player], up: dict[Player, list[Card]]) -> Player:
    """The first-to-act seat (4th-7th street): the highest visible upcards, ranked
    by descending card values. A partial board may be fewer than five cards, so a
    lexicographic compare of the sorted ranks, not the full poker evaluator."""
    return max(seats, key=lambda p: sorted((RANK_VALUE[c.rank] for c in up[p]), reverse=True))


def bring_in_seat(facts: EngineFacts, gr: reads.GameReads) -> Player:
    """The player who must post the bring-in: the lowest door card among players
    still holding chips (no one has folded at bring-in time)."""
    stack = gr.state["stack"]
    up = gr.families["upcards"]
    able = [p for p in facts.seating.players if stack[p] > 0]
    door = {p: up[p][0] for p in able}
    return _lowest_door(able, door)


def first_to_act_seat(facts: EngineFacts, gr: reads.GameReads) -> Player:
    """The first player to act on a later street: the highest visible upcards among
    players still live (holding chips and not folded)."""
    stack = gr.state["stack"]
    folded = gr.state["folded"]
    players = list(facts.seating.players)
    up = gr.families["upcards"]
    live = [p for p in players if stack[p] > 0 and not folded[p]]
    if not live:  # unreachable in a real hand (a street runs only with >= 2 live)
        return players[0]
    cards = {p: list(up[p]) for p in live}
    return _highest_upcards(live, cards)


def showdown_hands(
    in_hand: list[Player],
    hole: Mapping[Player, Sequence[Card]],
    upcards: Mapping[Player, Sequence[Card]],
) -> dict[Player, list[Card]]:
    """Each entrant's showdown holding: their seven private-and-upcard cards.

    This is the whole of what Stud contributes to the settlement — the layering
    itself is family-wide (`poker.side_pot_payouts`). The one game fact here is
    that the DSL's reveal move only changes WHICH of `hole`/`upcards` holds a
    contender's cards, not the concatenated seven, so both are concatenated and
    the result is insensitive to that move."""
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
