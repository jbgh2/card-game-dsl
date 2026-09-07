"""The Stud family's runtime support (fixed-limit).

Chips are integer state (a `stack` per player), not a resource-zone subsystem.
The whole hand — antes, deal, bring-in post, the betting streets on the kernel
[[round]]'s ring, and the showdown (reveal, per-entrant pot collection, muck) —
runs in the DSL (five-card-stud.cardlang, seven-card-stud.cardlang); this module
holds only the pure functions not expressible there:

- `bring_in_seat` — the lowest door card, the [[seat]] that posts the bring-in;
- `best_showing_seat` — the best POKER hand showing, the seat that opens each
  later street: multiplicities ahead of card values, straights and flushes not
  counted, ties broken on the suit of the highest card;
- `first_to_act_seat` — card values compared one at a time, which is a DIFFERENT
  order: an unpaired board beats any pair below its high card.
  `seven-card-stud.cardlang` is its only caller, and issue #636 owns moving that
  game onto `best_showing_seat` and deleting this selector. The two stand
  together because the move changes which seat Seven-Card Stud asks on every
  street from 4th on, and that regeneration is a change of its own;
- `pot_share` — the showdown side-pot query (argmax over poker-rank tuples per
  layer), the Primitive the showdown's settle statement calls.

The hand evaluator itself is family-wide and lives in `cardlang/runtime/poker.py`,
shared with Hold'em: which cards a player has available is a property of the
game, how five of them compare is not.

Random players bet/call/raise/fold uniformly among the legal actions. Total chips
are invariant — the falsifiable invariant for the betting and pot logic.

Simplifications (see docs/games/seven-card-stud.md): Seven-Card Stud's 4th-street
open-pair limit doubling is omitted (lower limit on 3rd/4th, upper on 5th–7th).
Five-Card Stud carries its own open-pair conditional in the language.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from cardlang.runtime import reads
from cardlang.runtime.poker import RANK_VALUE, side_pot_payouts
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player

# Each game's ante, bring-in, street limits and raise cap live in its own
# .cardlang file; this module keeps only the seat selectors and the pot-share
# query. The hand evaluator is family-wide, so it lives in
# cardlang/runtime/poker.py (shared with Hold'em).
_SUIT_ORDER = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3}


# --- seat selectors (Stud-local Primitives, called from the DSL) -------
#
# The bring-in (lowest door card) and the seat that opens a later street (best
# cards showing) are argmin/argmax over players keyed on card ranks/suits —
# neither expressible in the DSL today (no single-card zone read, no argmin/argmax).
# They are pure functions of the dealt cards (no RNG), so the betting ring order
# follows from the deal alone.


def _lowest_door(seats: list[Player], door: dict[Player, Card]) -> Player:
    """The bring-in seat: the lowest door card (the single upcard), ties broken by
    suit (clubs < diamonds < hearts < spades)."""
    return min(seats, key=lambda p: (RANK_VALUE[door[p].rank], _SUIT_ORDER[door[p].suit]))


def _highest_upcards(seats: list[Player], up: dict[Player, list[Card]]) -> Player:
    """The first-to-act seat (4th-7th street): the highest visible upcards, ranked
    by descending card values. A partial board may be fewer than five cards, so a
    lexicographic compare of the sorted ranks, not the full poker evaluator."""
    return max(seats, key=lambda p: sorted((RANK_VALUE[c.rank] for c in up[p]), reverse=True))


def _showing_key(cards: list[Card]) -> tuple[list[int], list[int], tuple[int, int]]:
    """Stud's "best hand showing" order over however many cards a seat has face up.

    Pagat, Five Card Stud (https://www.pagat.com/poker/variants/5stud.html): "pairs,
    triplets, two pairs and quads count in their normal poker order - so for example
    with three cards showing 3-3-3 is higher than 7-7-8, which is higher than A-K-Q.
    Incomplete straights and flushes do not count. If there is a tie it is resolved
    by comparing the suits of the highest cards in the tied hands using the ranking
    order clubs (low), diamonds, hearts, spades (high)."

    The key is three parts, in the order poker compares them. First the SHAPE
    alone — the rank multiplicities, descending — because the class outranks every
    card value inside it: two pair of sixes and fives is [2, 2] and beats a pair of
    sevens at [2, 1, 1] on the second entry, which no comparison that read the
    values alongside the counts would get right. Both boards on a street hold the
    same number of cards, so the two shapes sum alike and neither can be a prefix
    of the other. Then the card values, ordered by multiplicity first so the pair
    is read before its kickers. That is normal poker order over exactly the hand
    classes multiplicity can express, and it is why the family five-card evaluator
    is the wrong instrument here — it would rank the straights and flushes this
    order does not count, and it takes five cards where a street may show as few
    as two.

    Two hands sharing shape and values hold the same ranks, so the tie-break
    compares the highest card itself: equal rank, and the suit decides.
    """
    counts = Counter(RANK_VALUE[c.rank] for c in cards)
    by_weight = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [n for _, n in by_weight]
    values = [value for value, _ in by_weight]
    top = max((RANK_VALUE[c.rank], _SUIT_ORDER[c.suit]) for c in cards)
    return (shape, values, top)


def _best_showing(seats: list[Player], up: dict[Player, list[Card]]) -> Player:
    """The seat with the best hand showing (`_showing_key`'s order)."""
    return max(seats, key=lambda p: _showing_key(up[p]))


def bring_in_seat(facts: EngineFacts, gr: reads.GameReads) -> Player:
    """The player who must post the bring-in: the lowest door card among players
    still holding chips (no one has folded at bring-in time)."""
    stack = gr.state["stack"]
    up = gr.families["upcards"]
    able = [p for p in facts.seating.players if stack[p] > 0]
    door = {p: up[p][0] for p in able}
    return _lowest_door(able, door)


def best_showing_seat(facts: EngineFacts, gr: reads.GameReads) -> Player:
    """The seat that opens a street: the best hand showing among the players still
    live (holding chips and not folded). A folder's up cards are in the muck, so
    they are out of the comparison by having left the zone as well as by the
    `folded` read."""
    stack = gr.state["stack"]
    folded = gr.state["folded"]
    players = list(facts.seating.players)
    up = gr.families["upcards"]
    live = [p for p in players if stack[p] > 0 and not folded[p]]
    if not live:  # unreachable in a real hand (a street runs only with >= 2 live)
        return players[0]
    return _best_showing(live, {p: list(up[p]) for p in live})


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
