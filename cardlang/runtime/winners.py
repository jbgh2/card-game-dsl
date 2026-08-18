"""The engine-core trick-[[winner]] comparisons.

The two standard winner functions — highest of the led suit, and highest
trump else highest of the led suit — are the language's, not any one game's:
the trick form's `winner` clause names them (Bridge, Hearts, Spades, Oh
Hell), and the call form `highest_trump_or_led_suit(zone, trump)` computes
the same winner over a public pile's [[arrival-record]] (issue #256; the
schnapsen retirement). Beside them is the general comparison, over a game's
declared [[trick-order]]: `highest_by_trick_order` reads no suit and no
`ranking:` of its own, only the three per-card facts the block's rows
computed (`follows_lead` is the same candidate test, exposed). They live in
this neutral module because the two dispatch halves may not import each other
(`runtime/builtins.py` and `runtime/primitives.py`, each docstring's
contract) and BOTH consume these.

[[first-of-equals]] is the kernel rule for EVERY winner here, not an accident
of one implementation: when two plays compare equal, the winner is the one
played EARLIER. It matters wherever a deck can hold two identical cards
(Doppelkopf's and Pinochle's double packs) and is invisible in a single pack,
which is why it is stated rather than left to be read off `max`.
`_strongest` gets it from `max` keeping the first maximal element;
`highest_by_trick_order` gets it from a strict `>` scan in play order. A
rewrite that loses it in either place is caught by
tests/test_trick_order.py::test_first_of_equals_is_the_kernel_rule_for_every_winner.

Contract
--------
Assumes: `played` is non-empty, in play order, with the led card first. For
the Trick Order winner, each `Arrival` carries the per-card facts the game's
rows already computed — this module never evaluates a row.
Establishes: the winning seat, by pure comparison over the arguments; and,
for the Trick Order winner, that strength is read for CANDIDATES ONLY.
Illegal after: nothing — pure functions, no state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import Card, Player, rank_strength

# An outcome function picks the trick winner from the plays, the led suit,
# the trump suit (None when no trump), and the game's rank-strength map.
RankIndex = Mapping[str, int]


def recorded_plays(
    pairs: tuple[tuple[Player | None, Card], ...], caller: str, expected: int
) -> list[tuple[Player, Card]]:
    """A completed trick's plays, read off the pile's [[arrival-record]]
    pairs (issue #256) — the shared guard of every hand-rolled trick winner.

    Two Owner Guards, both the hosting description's errors: the pile must
    hold exactly the completed trick (`expected` plays — a wrong call site
    used to be caught by the same count over zipped cards), and every entry
    must carry a deciding actor (a card an engine deal placed has no player
    to attribute the play to)."""
    if len(pairs) != expected:
        raise OwnerGuardError(
            f"{caller}: trick pile holds {len(pairs)} cards, expected "
            f"a completed {expected}-card trick"
        )
    played: list[tuple[Player, Card]] = []
    for actor, card in pairs:
        if actor is None:
            raise OwnerGuardError(
                f"{caller}: {card} arrived with no deciding actor (an engine "
                f"deal, not a play) — every trick card must have been played "
                f"by a seat"
            )
        played.append((actor, card))
    return played


@dataclass(frozen=True)
class Arrival:
    """One play, with the three per-card facts the game's [[trick-order]] rows
    computed for its card. The projection happens once, at the call boundary
    (`runtime/trick_order.py`); this module compares, and never asks a row
    anything."""

    actor: Player
    card: Card
    is_trump: bool
    follow_class: str | None


def effective_lead(arrivals: list[Arrival]) -> Arrival | None:
    """The arrival that SET the trick's class — the first that is a trump or
    carries a follow class. Not the same as the first card played: a
    class-less card (Tarot's Excuse) leads to nothing, and the next card sets
    the class instead. `None` when nothing has led yet, or when every arrival
    so far is class-less (decisions.md "Trick Order", the [[effective-lead]];
    the state variable `led_suit` is the LITERAL first card's suit and is a
    different fact)."""
    for a in arrivals:
        if a.is_trump or a.follow_class is not None:
            return a
    return None


@dataclass(frozen=True)
class LeadFacts:
    """The [[effective-lead]]'s two facts, as much of them as a follow question
    needs. `follow_class` is None for a TRUMP lead — not "class-less", but
    "not consulted": when the lead is a trump only trumps follow, so its class
    is never compared and asking a row for it would be work no answer uses."""

    is_trump: bool
    follow_class: str | None


def effective_lead_facts(
    plays: list[tuple[Player, Card]],
    is_trump_of: Callable[[Card], bool],
    class_of: Callable[[Card], str | None],
) -> LeadFacts | None:
    """The [[effective-lead]] of `plays`, computed LAZILY: the scan stops at
    the first arrival that is a trump or carries a class, and asks each row
    only where the answer can still change the outcome.

    The eager twin is `effective_lead` above, over already-projected
    `Arrival`s. That one is the SPECIFICATION — it is what the algorithm
    means, and what the grid's value cells test; this is the implementation the
    legality path runs, because a follow filter asks this question once per
    candidate per decision and projecting the whole pile each time is the
    dominant cost of the construct. The two agree cell for cell, proven by
    execution rather than by inspection
    (tests/test_trick_order.py::test_the_lazy_lead_agrees_with_the_eager_one).

    Laziness is sound because a [[trick-order]] row is HERMETIC: a pure
    function of the card and public state, emitting no observation and
    touching no state. So how MANY rows are evaluated, and in what order,
    cannot be observed — which is exactly what the hermeticity guards buy,
    spent here."""
    for _actor, card in plays:
        if is_trump_of(card):
            return LeadFacts(True, None)
        cls = class_of(card)
        if cls is not None:
            return LeadFacts(False, cls)
    return None


def follows_lead_lazily(
    cand_is_trump: Callable[[], bool],
    cand_class: Callable[[], str | None],
    plays: list[tuple[Player, Card]],
    is_trump_of: Callable[[Card], bool],
    class_of: Callable[[Card], str | None],
) -> bool:
    """`follows_lead`, asking only the rows the answer needs. The candidate's
    two facts arrive as THUNKS: its class is asked only when the lead is a
    plain class AND the candidate is not itself a trump, which are the only
    circumstances in which the comparison happens."""
    lead = effective_lead_facts(plays, is_trump_of, class_of)
    if lead is None:
        return False
    if lead.is_trump:
        return cand_is_trump()
    if cand_is_trump():
        return False
    return cand_class() == lead.follow_class


def follows_lead(
    is_trump: bool, follow_class: str | None, arrivals: list[Arrival]
) -> bool:
    """Whether a card with these facts follows what has been led — the
    winner's candidate test, and the SPECIFICATION of the lazy form above.

    False when there is no [[effective-lead]]: with nothing led, nothing
    follows (issue #345's ruling — the VALUE false, not an error, so the
    leader's `where` filter is written `if any … then … else true`, the
    `follow_ok` shape). If the lead is a trump, only trumps follow; otherwise
    only non-trumps of the same class do — a trump never follows a plain
    class, whatever suit it is printed."""
    lead = effective_lead(arrivals)
    if lead is None:
        return False
    if lead.is_trump:
        return is_trump
    return not is_trump and follow_class == lead.follow_class


def highest_by_trick_order(
    arrivals: list[Arrival],
    strength_of: Callable[[Card], int],
    caller: str,
    label: str | None = None,
) -> Player:
    """The winner of a trick under the game's declared [[trick-order]]: the
    strongest trump if any trump was played, else the strongest card of the
    [[effective-lead]]'s class.

    Over a COMPLETE trick this is the winner; over a partial one it is the
    winner so far, which is designed surface (issue #350) — nothing here reads
    how many plays a trick should hold, so a mid-trick read is an ordinary
    answer rather than a special case.

    Strength is read for CANDIDATES ONLY, and lazily: a card that can neither
    lead nor win is never passed to `strength_of`. That is load-bearing, not an
    optimization — under the default strength a class-less card may be outside
    the game's `ranking:` altogether (French Tarot's Excuse), and asking would
    fire `rank_strength`'s Owner Guard about a card whose strength no rule
    consults.

    [[first-of-equals]]: the scan keeps the incumbent on a tie (strict `>`),
    and the arrivals are in play order, so of two equal cards the earlier
    played wins.

    `caller` leads both messages; `label`, when the caller read a named zone,
    parametrizes the remedy so the author is told which pile to guard."""
    if not arrivals:
        raise OwnerGuardError(
            f"{caller}: the pile is empty — no plays to name a winner from; "
            f"guard the read"
            + (f" (`{label} is not empty`)" if label is not None else "")
        )
    candidates = [a for a in arrivals if a.is_trump]
    if not candidates:
        lead = effective_lead(arrivals)
        if lead is None:
            raise OwnerGuardError(
                f"{caller}: no card can win — every arrival is class-less "
                f"(`follow_class` none) and none is a trump; guard the read"
                + (
                    f" (`any card in {label} where is_trump(card) or "
                    f"follow_class(card) is not none`)"
                    if label is not None
                    else ""
                )
            )
        cls = lead.follow_class
        candidates = [a for a in arrivals if not a.is_trump and a.follow_class == cls]
    best = candidates[0]
    best_strength = strength_of(best.card)
    for a in candidates[1:]:
        strength = strength_of(a.card)
        if strength > best_strength:
            best, best_strength = a, strength
    return best.actor


def _strongest(
    candidates: list[tuple[Player, Card]], rank_index: RankIndex, reader: str
) -> Player:
    """The first-played candidate of greatest declared strength (`max` keeps
    the first maximal element, so equals resolve to the earlier play —
    [[first-of-equals]], the module docstring's kernel rule).
    Strength reads go through `rank_strength`, the runtime Owner Guard for a
    rank outside a partial `ranking:` — naming `reader`, the DSL-visible
    winner, so the message says which read failed."""
    return max(
        candidates, key=lambda pc: rank_strength(rank_index, pc[1].rank, reader)
    )[0]


def highest_of_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The player who played the highest-ranked card of the led suit. Reads no
    trump: the argument is the winner contract's, accepted and unused — which
    is why resolve refuses a `trump` clause on this winner
    (`TRUMP_READING_WINNERS`, cardlang/builtins/functions.py)."""
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return _strongest(of_suit, rank_index, "highest_of_led_suit")


def highest_trump_or_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The highest trump if any trump was played, else the highest card of the
    led suit (the standard trick winner for a trump game)."""
    trumps = [(p, c) for (p, c) in played if c.suit == trump]
    if trumps:
        return _strongest(trumps, rank_index, "highest_trump_or_led_suit")
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return _strongest(of_suit, rank_index, "highest_trump_or_led_suit")
