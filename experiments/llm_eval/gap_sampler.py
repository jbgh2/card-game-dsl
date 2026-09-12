"""The literal posterior at a Cheat challenge window — P(the standing claim is
a lie | the observer's information state) — by importance sampling over the
worlds the observer cannot rule out.

The reference measure: the deal is uniform, and every hidden card choice by a
player other than the observer is uniform over that player's hand at the time.
Public decisions — the announced count, a challenge call — carry no likelihood
weight, so this is the LITERAL posterior and not the policy-aware one
(`belief-calibration-spec.md`, R2 versus this).

Uniform over the IDEALIZED deal space, every deal of the deck, and not over the
deals the adapter's root chance node addresses. That subsample is the same
idealization the readiness proofs run under, and a reference predictor does not
condition on it (`belief-calibration-spec.md`, the deal-space note) — which is
also why a sampled world is replayed by installing its deal rather than by
finding a seed that deals it.

**The estimate is a function of the information-state string and nothing else.**
That is the property that makes it a reference a model's stated belief can be
scored against: the recorded history names the cards other seats played face
down, and conditioning on those collapses the posterior onto the ground truth it
exists to predict (`belief-calibration-spec.md` §4, the decode-pin trap). The
module therefore reaches no engine at all — `gap_replay` holds the replay check,
behind a callable this module is handed.

The slot model
--------------
Every deal position in the hands the observer cannot see is a distinguishable
SLOT, and the observation log is replayed as slot movement: a face-down play
moves slots out of a hand into `played`, and on to `pile` or — challenged —
through `flipped` into the loser's hand; a pile pickup moves every pile slot
into one hand. Identities are labels on slots, learned lazily: a flip names the
identities of the slots it moved, and a pile pickup into the observer's own hand
names the identity of every slot in the pile.

A world is a (structure, labelling) pair, and under the reference measure every
pair consistent with the log has the same probability — the per-card draw
probability is one over a hand size, and hand sizes are public. So the posterior
is the share of consistent pairs whose standing play carries a rank other than
the claimed one, and a sample's importance weight is the reciprocal of its own
proposal probability times the number of ways its unlabelled slots can be
completed. The completion is integrated rather than drawn: given the labels the
prefix pins, the chance that every unlabelled slot of the standing play draws
the claimed rank is a ratio of falling factorials over the identities still
unplaced.

`Proposal` is the knob that says how a sample is drawn, never what it is worth:
weights are computed from the proposal actually used, so a blind proposal and a
lookahead proposal estimate the same number at different cost.

What rejection costs
--------------------
A rejected proposal costs efficiency and never accuracy: the proposal's support
is the whole consistent set — a slot is forced to move only where the seat's
remaining plays could not carry it — so the estimate stays unbiased however
many worlds are thrown away, and `Estimate` reports the acceptance count and
effective sample size a run actually bought.

Acceptance falls as a line lengthens, and one route is why. A card a later flip
names has to be in the flipping seat's hand by then, and a card in another
seat's hand gets there only by a journey: played into a pile, collected by the
seat that loses the next challenge. The lookahead forces and bars that journey
over ONE pickup, which the log settles exactly; a journey that needs two is
proposed by luck and rejected when the luck does not hold. So a deep window buys
effective samples with proposals, and the way to more of them is lookahead over
longer journeys rather than a bigger sample count.

Contract
--------
Assumes: an information-state string as `cardlang.openspiel.infostate` renders
it, for a four-player `standard52` Cheat line, at a decision where a play stands
with the challenge window open; and a game whose only hidden decision is the
choice of a card (every other decision is announced, so the action line can be
reconstructed from the log).
Establishes: `Estimate` — a self-normalized importance-sampling estimate of the
literal posterior carrying its acceptance count, effective sample size,
split-half halves and rejection tally — and, per accepted sample, a `World`
naming a full deal and the action line that reaches this window in it.
Illegal after: reading any fact about this window from a transcript's action
ids, a `pyspiel.State` or a `RuntimeState`. A reference predictor that does so
is conditioning on cards the observer never saw, and is not a belief.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from .infostate import RANKS, Info, parse, parse_events, rank_of, zone_player

#: The suit glyphs a card renders with, and the deck built from them. Held as a
#: literal for the same reason `infostate.RANKS` is — this module stays a string
#: parser with no engine dependency — and reconciled against
#: `cardlang.runtime.values.build_deck` by `tests/test_gap_sampler.py`, so a deck
#: change reddens rather than silently shrinking the pool of hidden identities.
SUITS: tuple[str, ...] = ("♣", "♦", "♥", "♠")

#: Every identity a hidden slot can carry. The observer's own cards are removed
#: from it at the deal; what remains is what the sampler assigns.
DECK: tuple[str, ...] = tuple(sorted(f"{rank}{suit}" for rank in RANKS for suit in SUITS))

#: Membership test behind the draw-order reading — a draw event names a card or
#: it names some other decision's value.
_DECK: frozenset[str] = frozenset(DECK)

#: The zones the slot model moves cards between. `deck` is absent on purpose:
#: the whole deck is dealt, so no slot ever sits there once the deal is over,
#: and the count check at the end of a walk holds that to the observer's own
#: projection of it.
PLAYED = "played"
PILE = "pile"
FLIPPED = "flipped"


@dataclass(frozen=True)
class Proposal:
    """How a sample is drawn — never what it is worth.

    `label_up_front` assigns every hidden identity at the deal instead of at the
    reveal that names it, which turns every later constraint into a rejection.
    `lookahead` lets a hidden play read the reveal that will resolve it, so the
    slots a flip is about to name are moved with probability one instead of by
    luck.

    Both are proposal choices, and the importance weight is computed from
    whichever was used, so all four combinations estimate the same posterior and
    differ only in acceptance and variance. The default is the cheap one;
    labelling up front with no lookahead is the naive rejection sampler the
    tests weigh it against.
    """

    label_up_front: bool = False
    lookahead: bool = True


#: The production proposal: lazy labels, lookahead on.
SMART = Proposal()


@dataclass(frozen=True)
class World:
    """One world the observer cannot rule out: a complete deal and the action
    line that reaches this window in it.

    `deal` is indexed by seat and holds the identities that seat is dealt;
    `actions` is every decision of the prefix in order, as the value it names —
    a move-type name, an announced count, or a card's rendering. `gap_replay`
    turns the pair into a replay and asserts the observer cannot tell it from
    the world the transcript came from.
    """

    deal: tuple[tuple[str, ...], ...]
    actions: tuple[tuple[str, str | int], ...]


@dataclass(frozen=True)
class Sample:
    """One proposed world.

    `reject` names the constraint that ruled it out, and is None exactly when
    the sample counts. `p_lie` is the sample's own conditional probability that
    the standing claim is false — the completion of its unlabelled slots is
    integrated, not drawn, so this is a probability and not a Boolean.
    `log_weight` is the log importance weight; `world` is materialized only when
    a caller asks, since nothing but the replay check needs it.
    """

    log_weight: float
    p_lie: float
    reject: str | None
    world: World | None = None


@dataclass(frozen=True)
class Estimate:
    """The posterior, with everything needed to judge it.

    Every count carries its denominator: `n_accepted` of `n_proposed` proposals
    were consistent, `ess` is the effective sample size those weights are worth,
    and `split_half` estimates the same quantity from alternate samples — two
    numbers that disagree say the run is short, which a point estimate cannot.
    `rejects` tallies why the rest were dropped.

    A half with no accepted sample reports `nan`, never 0.0: "no sample" and
    "no lie" are different claims.
    """

    p_lie: float
    n_proposed: int
    n_accepted: int
    ess: float
    split_half: tuple[float, float]
    seed: int
    n_checked: int
    rejects: tuple[tuple[str, int], ...]


class _Reject(Exception):
    """A proposed world contradicts the log. Weight zero, not an error."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class _Slot:
    """One deal position: where it sits now, and the identity on it if the
    observer has been told one."""

    deal_hand: int
    where: str
    label: str | None = None


@dataclass(frozen=True)
class _Line:
    """The public facts of one window, parsed once and shared by every sample."""

    info: Info
    events: tuple[tuple[Any, ...], ...]
    #: The identities no slot in the observer's own hand was dealt — the pool
    #: the sampler assigns, in a deterministic order.
    pool: tuple[str, ...]
    #: What the log says about each hidden play, by the index of its movement
    #: event. Derived from the log alone, so every sample reads the same plan
    #: rather than re-deriving it.
    plans: dict[int, _Plan]


@dataclass(frozen=True)
class _Plan:
    """What the log already says about one hidden play.

    Three kinds, and they are the whole domain of how a hidden play can be
    constrained by what comes after it:

    - `"flip"` — a challenge turns this play face up, so the log names its
      cards outright.
    - `"pile"` — it joins a pile that someone later collects. `named` is that
      pile's whole contents where the observer collects it (and so the only
      cards that may be in it); `owed` is the cards this play's seat must start
      toward the pile because the seat who collects it is flipped holding them
      before any other pile changes hands, which leaves this pile as the only
      route; `barred` is the mirror — cards flipped out of some OTHER seat's
      hand in that same stretch, which this pile would carry to the wrong seat.
      `capacity` is what this seat's remaining plays into the same pile could
      carry instead of this one, and `by_flip` is the cards a later flip of this
      seat's own play names — those move at that play, not this one.
    - `"open"` — nothing in the log constrains it: the standing play, or a pile
      nobody collects before the window.

    Owed and barred are read off the log and are exact, never guesses: a card
    reaches another hand only by being played into a pile and collected, so
    between two pickups there is at most one pile to ride and the log says who
    collects it. A journey that needs two pickups is left to chance — the sample
    that does not make it is rejected, which costs samples and not accuracy.
    """

    kind: str
    revealed: frozenset[str] = frozenset()
    named: frozenset[str] | None = None
    owed: frozenset[str] = frozenset()
    barred: frozenset[str] = frozenset()
    by_flip: frozenset[str] = frozenset()
    capacity: int = 0


@dataclass(frozen=True)
class _Options:
    """How a hidden play's slots are sorted by what the log reveals later.

    `forced` moves with probability one; at least `least` of `owed` must move
    now and the rest may; `free` is whatever else this play may take. The three
    are disjoint, and a slot in none of them cannot move.
    """

    forced: list[int] = field(default_factory=list)
    owed: list[int] = field(default_factory=list)
    least: int = 0
    free: list[int] = field(default_factory=list)


@dataclass
class _Drawn:
    """What one completed walk establishes about its world."""

    log_weight: float
    p_lie: float


def _log_choose(n: int, k: int) -> float:
    return math.log(math.comb(n, k))


def _log_factorial(n: int) -> float:
    return math.lgamma(n + 1)


def _falling_ratio(good: int, total: int, draws: int) -> float:
    """The chance that `draws` identities drawn without replacement from
    `total` are all among the `good` ones."""
    out = 1.0
    for i in range(draws):
        if good - i <= 0:
            return 0.0
        out *= (good - i) / (total - i)
    return out


def _identities(payload: Any, what: str) -> tuple[str, ...]:
    """A payload the observer sees as identities. The parser's own totality: a
    count where identities are entitled means the log is not the one this model
    was written against, and reading it as empty would make every constraint
    below vacuous."""
    if not isinstance(payload, tuple) or not all(isinstance(c, str) for c in payload):
        raise ValueError(f"{what}: expected card identities, got {payload!r}")
    return tuple(str(c) for c in payload)


def _count(payload: Any, what: str) -> int:
    if isinstance(payload, bool) or not isinstance(payload, int):
        raise ValueError(f"{what}: expected a count, got {payload!r}")
    return payload


def _line(infostate: str) -> _Line:
    """Parse a window's information state, refusing anything that is not one.

    The posterior is about a STANDING claim. At an announce or a count decision
    nothing stands; at a card decision a play is being assembled and `played`
    holds only the cards drawn so far. Answering at any of those would report a
    posterior about a claim nobody has made.
    """
    info = parse(infostate)
    if info.state.get("window_open") != "True":
        raise ValueError(
            "this decision is not a challenge window (window_open is "
            f"{info.state.get('window_open')!r}) — no claim stands to be false"
        )
    claimant = info.claimant
    if claimant is None:
        raise ValueError("the window names no claimant — no claim stands")
    standing = info.zones[PLAYED]
    if not isinstance(standing, int) or standing != info.claim_count:
        raise ValueError(
            f"the standing play holds {standing!r} cards against a claim of "
            f"{info.claim_count} — this is not an open window"
        )
    events = tuple(parse_events(info.obs))
    own = _own_deal(events, info.player)
    unknown = [card for card in own if card not in DECK]
    if unknown:
        raise ValueError(f"cards outside the deck this sampler models: {unknown}")
    return _Line(
        info=info,
        events=events,
        pool=tuple(card for card in DECK if card not in set(own)),
        plans=_plans(events, info.player),
    )


@dataclass
class _Movements:
    """The log's plays, their resolutions, and its pickups — the skeleton every
    plan is read off."""

    #: (event index, seat, cards moved) per hidden play, in order.
    plays: list[tuple[int, int, int]] = field(default_factory=list)
    #: play index -> ("flip", the cards it names) or ("pile", nothing).
    resolution: dict[int, tuple[str, frozenset[str]]] = field(default_factory=dict)
    #: (event index, the seat who collects, the cards it names to the observer).
    pickups: list[tuple[int, int, frozenset[str] | None]] = field(default_factory=list)
    #: (event index, the seat whose play it was, the cards it names) per flip.
    flips: list[tuple[int, int, frozenset[str]]] = field(default_factory=list)


def _movements(events: Sequence[tuple[Any, ...]], observer: int) -> _Movements:
    out = _Movements()
    pending: tuple[int, int] | None = None  # the play `played` currently holds
    for index, event in enumerate(events):
        if event[0] != "move" or len(event) != 5:
            continue
        _, source, _source_view, destination, destination_view = event
        from_seat = zone_player(str(source))
        to_seat = zone_player(str(destination))
        if from_seat is not None and destination == PLAYED:
            out.plays.append(
                (index, from_seat, _count(destination_view, "a play's arrival"))
            )
            pending = (index, from_seat)
        elif source == PLAYED and destination in (FLIPPED, PILE):
            if pending is None:
                raise ValueError(
                    f"the log resolves a play at event {index} that it never "
                    f"recorded — the movements do not pair up"
                )
            if destination == FLIPPED:
                named = frozenset(_identities(destination_view, "a challenge flip"))
                out.resolution[pending[0]] = ("flip", named)
                out.flips.append((index, pending[1], named))
            else:
                out.resolution[pending[0]] = ("pile", frozenset())
            pending = None
        elif source == PILE and to_seat is not None:
            collected = (
                frozenset(_identities(destination_view, "a pile pickup"))
                if to_seat == observer
                else None
            )
            out.pickups.append((index, to_seat, collected))
    return out


def _plans(events: Sequence[tuple[Any, ...]], observer: int) -> dict[int, _Plan]:
    """What the log says about every hidden play, derived once per line.

    A card only ever travels from one hand to another by being played into a
    pile and collected, so a flip that names a card the log has already placed
    in another seat's hand says exactly which plays must have carried it. That
    is what makes forcing safe here rather than a guess: the reveal is in the
    log before the sample is drawn.
    """
    seen = _movements(events, observer)
    out: dict[int, _Plan] = {}
    for index, seat, _moved in seen.plays:
        if seat == observer:
            continue  # the observer's own play is forced by identity
        resolution = seen.resolution.get(index)
        if resolution is None:
            out[index] = _Plan(kind="open")  # the standing play
            continue
        if resolution[0] == "flip":
            out[index] = _Plan(kind="flip", revealed=resolution[1])
            continue
        pickup = next((entry for entry in seen.pickups if entry[0] > index), None)
        if pickup is None:
            out[index] = _Plan(kind="open")  # nothing collects this pile in time
            continue
        at, collector, named = pickup
        # This seat's own remaining plays into the same pile: what they could
        # carry instead of this one, and what a flip of theirs already claims.
        capacity = 0
        by_flip: frozenset[str] = frozenset()
        for other, other_seat, moved in seen.plays:
            if other_seat != seat or not index < other < at:
                continue
            later = seen.resolution.get(other)
            if later is None:
                continue  # the standing play reaches no pile in this prefix
            if later[0] == "pile":
                capacity += moved
            else:
                by_flip |= later[1]
        owed: frozenset[str] = frozenset()
        barred: frozenset[str] = frozenset()
        if named is None:
            # The pile's contents are not named to the observer, so what it must
            # carry is whatever the seat collecting it is caught holding before
            # the next pickup — and what it must NOT carry is whatever another
            # seat is caught holding in that same stretch, since this pile would
            # deliver it to the collector instead.
            until = next(
                (entry[0] for entry in seen.pickups if entry[0] > at), len(events)
            )
            for flip, flip_seat, flipped in seen.flips:
                if not at < flip < until:
                    continue
                if flip_seat == collector:
                    owed |= flipped
                else:
                    barred |= flipped
        out[index] = _Plan(
            kind="pile",
            named=named,
            owed=owed,
            barred=barred - owed,
            by_flip=by_flip,
            capacity=capacity,
        )
    return out


def _own_deal(events: Sequence[tuple[Any, ...]], observer: int) -> tuple[str, ...]:
    own = f"hand[{observer}]"
    for event in events:
        if event[0] == "move" and len(event) == 5 and event[1] == "deck" and event[3] == own:
            return _identities(event[4], "the observer's own deal")
    raise ValueError(
        "the observation log carries no deal into the observer's own hand — "
        "without it the pool of hidden identities is unknown"
    )


class _Walk:
    """One proposed world, built by replaying the observation log as slot
    movement. Raises `_Reject` the moment the world contradicts the log."""

    def __init__(self, line: _Line, proposal: Proposal, rng: random.Random) -> None:
        self.line = line
        self.observer = line.info.player
        self.proposal = proposal
        self.rng = rng
        self.log_q = 0.0
        self.slots: list[_Slot] = []
        self.where: dict[str, set[int]] = {PLAYED: set(), PILE: set(), FLIPPED: set()}
        self.assigned: dict[str, int] = {}
        self.pool: list[str] = list(line.pool)
        self.items: list[tuple[str, str | int]] = []
        #: The cards the observer has drawn since its last play, in draw order.
        self.drawn: list[str] = []

    # --- the walk ------------------------------------------------------------

    def run(self) -> _Drawn:
        for index, event in enumerate(self.line.events):
            tag = event[0]
            if tag == "move":
                self._move(index, event)
            elif tag == "announce":
                self._announce(event)
            elif tag == "chose":
                self._chose(event)
            else:
                raise ValueError(
                    f"observation event {tag!r} is not one this sampler models "
                    f"(it replays 'move', 'announce' and 'chose'): {event!r}"
                )
        return self._finish()

    def _move(self, index: int, event: tuple[Any, ...]) -> None:
        if len(event) != 5:
            raise ValueError(f"movement event with {len(event)} fields: {event!r}")
        _, source, source_view, destination, destination_view = event
        from_seat = zone_player(str(source))
        to_seat = zone_player(str(destination))
        if source == "deck" and to_seat is not None:
            self._deal(to_seat, destination_view)
        elif from_seat is not None and destination == PLAYED:
            self._play(index, from_seat, source_view, destination_view)
        elif source == PLAYED and destination == PILE:
            self._tuck(destination_view)
        elif source == PLAYED and destination == FLIPPED:
            self._flip(destination_view)
        elif source == FLIPPED and to_seat is not None:
            self._route(to_seat, source_view, destination_view)
        elif source == PILE and to_seat is not None:
            self._pickup(to_seat, source_view, destination_view)
        else:
            raise ValueError(
                f"movement {source!r} -> {destination!r} is not one this sampler "
                f"models: {event!r}"
            )

    def _chose(self, event: tuple[Any, ...]) -> None:
        """The actor's own draw, and the ONE thing only it records: the ORDER
        the observer took its own cards in.

        A card's identity is already in the movement event, but sorted — and the
        observer's own log carries a draw event per card, in draw order, so a
        replayed line that took the same cards in another order is a
        distinguishable world. Every other decision arrives as an announcement,
        and the runtime emits a draw event for those too; the card renderings
        are the ones this picks out.
        """
        if len(event) != 2:
            raise ValueError(f"draw event with {len(event)} fields: {event!r}")
        value = event[1]
        if isinstance(value, str) and value in _DECK:
            self.drawn.append(value)

    def _announce(self, event: tuple[Any, ...]) -> None:
        if len(event) != 3:
            raise ValueError(f"announce event with {len(event)} fields: {event!r}")
        value = event[2]
        if isinstance(value, bool):
            raise ValueError(f"announced value {value!r} names no action")
        if isinstance(value, int):
            self.items.append(("count", value))
        elif isinstance(value, str):
            self.items.append(("name", value))
        else:
            raise ValueError(
                f"announced value {value!r} is neither a move-type name nor a count"
            )

    def _deal(self, seat: int, destination_view: Any) -> None:
        if seat == self.observer:
            for card in _identities(destination_view, "the observer's own deal"):
                self._create(seat, card)
            return
        for _ in range(_count(destination_view, f"the deal into hand[{seat}]")):
            self._create(seat, None)

    def _play(
        self, index: int, seat: int, source_view: Any, destination_view: Any
    ) -> None:
        moved_count = _count(destination_view, "the cards played face down")
        if seat == self.observer:
            cards = _identities(source_view, "the observer's own play")
            if len(cards) != moved_count:
                raise ValueError(
                    f"the observer played {len(cards)} cards into a movement of "
                    f"{moved_count}"
                )
            if sorted(self.drawn) != sorted(cards):
                raise ValueError(
                    f"the observer's own draws {self.drawn} are not the cards its "
                    f"play moved {list(cards)}"
                )
            # In DRAW order, not the movement's sorted order: the draw events are
            # in the observer's own log, so the order is part of what it saw.
            moved = [self._slot_of(card) for card in self.drawn]
            self.drawn.clear()
            for slot in moved:
                if self.slots[slot].where != f"hand[{self.observer}]":
                    raise ValueError(
                        f"the observer played {self.slots[slot].label}, which this "
                        f"walk has in {self.slots[slot].where}"
                    )
        else:
            if _count(source_view, f"the play out of hand[{seat}]") != moved_count:
                raise ValueError("a play's source and destination counts disagree")
            if self.drawn:
                raise ValueError(
                    f"the observer's draws {self.drawn} are unaccounted for at a "
                    f"play by seat {seat} — the log's draw events and its movements "
                    f"do not pair up as this walk reads them"
                )
            moved = self._choose(index, seat, moved_count)
        for slot in moved:
            self._relocate(slot, PLAYED)
            self.items.append(("card", slot))

    def _tuck(self, destination_view: Any) -> None:
        moved = sorted(self.where[PLAYED])
        if _count(destination_view, "the pile arrival") != len(moved):
            raise ValueError("an unchallenged play's arrival count is not what it moved")
        for slot in moved:
            self._relocate(slot, PILE)

    def _flip(self, destination_view: Any) -> None:
        revealed = _identities(destination_view, "a challenge flip")
        moved = sorted(self.where[PLAYED])
        if len(moved) != len(revealed):
            raise ValueError(
                f"a flip named {len(revealed)} cards out of a play of {len(moved)}"
            )
        self._reveal(moved, revealed, "the flipped cards")
        for slot in moved:
            self._relocate(slot, FLIPPED)

    def _route(self, seat: int, source_view: Any, destination_view: Any) -> None:
        revealed = _identities(source_view, "a flip leaving the flipped zone")
        moved = sorted(self.where[FLIPPED])
        if len(moved) != len(revealed):
            raise ValueError(
                f"a verdict routed {len(revealed)} flipped cards where this walk "
                f"has {len(moved)}"
            )
        labels = sorted(self._label_of(slot) for slot in moved)
        assert labels == sorted(revealed), (
            "the flip that filled `flipped` labelled it with other cards than "
            "the verdict routes — the walk's own bookkeeping is wrong"
        )
        if seat == self.observer:
            arriving = _identities(destination_view, "a verdict into the observer's hand")
            if sorted(arriving) != labels:
                raise ValueError("a verdict's departure and arrival name different cards")
        else:
            if _count(destination_view, f"a verdict into hand[{seat}]") != len(moved):
                raise ValueError("a verdict's arrival count is not what it routed")
        for slot in moved:
            self._relocate(slot, f"hand[{seat}]")

    def _pickup(self, seat: int, source_view: Any, destination_view: Any) -> None:
        moved = sorted(self.where[PILE])
        if _count(source_view, "the pile leaving") != len(moved):
            raise ValueError(
                f"a pickup took {source_view!r} cards where this walk has "
                f"{len(moved)} in the pile"
            )
        if seat == self.observer:
            revealed = _identities(
                destination_view, "a pile pickup into the observer's own hand"
            )
            if len(revealed) != len(moved):
                raise ValueError("a pickup's departure and arrival counts disagree")
            self._reveal(moved, revealed, "the pile the observer collected")
        else:
            if _count(destination_view, f"a pickup into hand[{seat}]") != len(moved):
                raise ValueError("a pickup's arrival count is not what it took")
        for slot in moved:
            self._relocate(slot, f"hand[{seat}]")

    # --- the proposal --------------------------------------------------------

    def _choose(self, index: int, seat: int, wanted: int) -> list[int]:
        """Which of `seat`'s slots this hidden play moves.

        Drawn from the three classes `_Options` sorts the hand into, and every
        draw is charged to the proposal probability — the count of owed slots
        taken now, which of the owed, and which of the free.
        """
        hand = sorted(self.where[f"hand[{seat}]"])
        options = self._constrain(index, seat, hand)
        need = wanted - len(options.forced)
        if need < 0:
            raise _Reject("more cards are revealed from this play than it moved")
        least = max(options.least, need - len(options.free))
        most = min(need, len(options.owed))
        if least > most:
            raise _Reject(
                "this play cannot carry the cards a later reveal owes the pile "
                "and still be the size it was"
            )
        if least == most:
            owed_now = least
        else:
            owed_now = least + self.rng.randrange(most - least + 1)
            self.log_q -= math.log(most - least + 1)
        self.log_q -= _log_choose(len(options.owed), owed_now)
        self.log_q -= _log_choose(len(options.free), need - owed_now)
        return (
            options.forced
            + self.rng.sample(options.owed, owed_now)
            + self.rng.sample(options.free, need - owed_now)
        )

    def _constrain(self, index: int, seat: int, hand: list[int]) -> _Options:
        """How this hidden play's slots are constrained, from its `_Plan`.

        With `lookahead` off, anything in the hand may move and the reveals sort
        it out by rejection. With it on:

        - **A flip** names the identities the play moved. A slot already
          carrying one of them is in this play, every other slot in it is
          unlabelled, and a named card sitting anywhere else rules the world out
          on the spot.
        - **A pile** the observer collects is named whole, so a labelled slot
          may join it only if the pickup names that card — and every slot that
          carries a named card owes the pile. A pile the observer does not see
          names nothing: what it owes is what the seat collecting it is caught
          holding next, and what it is barred from carrying is what another seat
          is caught holding in the same stretch.

        Owed slots are forced only where this seat's remaining plays into the
        same pile could not carry them, so no consistent world is left
        unproposable.
        """
        if not self.proposal.lookahead:
            return _Options(free=hand)
        plan = self.line.plans.get(index)
        if plan is None or plan.kind == "open":
            return _Options(free=hand)
        if plan.kind == "flip":
            held = set(hand)
            forced = []
            for card in sorted(plan.revealed):
                slot = self.assigned.get(card)
                if slot is None:
                    continue
                if slot not in held:
                    raise _Reject(
                        f"{card} is flipped out of this play but this world has it "
                        f"in {self.slots[slot].where}"
                    )
                forced.append(slot)
            return _Options(
                forced=forced,
                free=[slot for slot in hand if self.slots[slot].label is None],
            )
        if plan.kind != "pile":
            raise AssertionError(f"plan kind {plan.kind!r} has no proposal")
        owed: list[int] = []
        free: list[int] = []
        for slot in hand:
            label = self.slots[slot].label
            if label is None:
                free.append(slot)
            elif label in plan.by_flip or label in plan.barred:
                continue  # this pile is the wrong way out of this hand
            elif label in (plan.named if plan.named is not None else plan.owed):
                owed.append(slot)
            elif plan.named is None:
                free.append(slot)
            # else: the pickup names the pile whole, and not this card
        return _Options(
            owed=owed, least=max(0, len(owed) - plan.capacity), free=free
        )

    def _reveal(self, slots: list[int], revealed: tuple[str, ...], what: str) -> None:
        """Put `revealed` on `slots` — the labelling step, and the only place a
        world can be found inconsistent with what the observer was told."""
        held = set(slots)
        for card in revealed:
            slot = self.assigned.get(card)
            if slot is not None and slot not in held:
                raise _Reject(
                    f"{card} is named by {what} but this world has it in "
                    f"{self.slots[slot].where}"
                )
        for slot in slots:
            label = self.slots[slot].label
            if label is not None and label not in revealed:
                raise _Reject(f"{label} sits where {what} name other cards")
        free_slots = [slot for slot in slots if self.slots[slot].label is None]
        free_labels = sorted(card for card in revealed if card not in self.assigned)
        assert len(free_slots) == len(free_labels), (
            "the unlabelled slots and the unplaced identities of a reveal are "
            "matched by the checks above; a mismatch is a bookkeeping error"
        )
        order = list(free_labels)
        self.rng.shuffle(order)
        self.log_q -= _log_factorial(len(order))
        for slot, card in zip(free_slots, order, strict=True):
            self._assign(slot, card)

    # --- slots ---------------------------------------------------------------

    def _create(self, seat: int, label: str | None) -> None:
        hand = f"hand[{seat}]"
        slot = len(self.slots)
        self.slots.append(_Slot(deal_hand=seat, where=hand, label=None))
        self.where.setdefault(hand, set()).add(slot)
        if label is not None:
            self._assign(slot, label)
        elif self.proposal.label_up_front:
            self._assign(slot, self.pool[self.rng.randrange(len(self.pool))])

    def _assign(self, slot: int, card: str) -> None:
        if card in self.assigned:
            raise AssertionError(f"{card} is already placed — labels are a bijection")
        self.slots[slot].label = card
        self.assigned[card] = slot
        if card in self.pool:
            self.pool.remove(card)

    def _slot_of(self, card: str) -> int:
        slot = self.assigned.get(card)
        if slot is None:
            raise ValueError(
                f"the log names {card} in the observer's own hand, but this walk "
                f"never put it there"
            )
        return slot

    def _label_of(self, slot: int) -> str:
        label = self.slots[slot].label
        assert label is not None, "a flipped slot is labelled by the flip itself"
        return label

    def _relocate(self, slot: int, destination: str) -> None:
        self.where[self.slots[slot].where].discard(slot)
        self.where.setdefault(destination, set()).add(slot)
        self.slots[slot].where = destination

    # --- the answer ----------------------------------------------------------

    def _finish(self) -> _Drawn:
        self._check_zones()
        claim_rank = self.line.info.claim_rank
        labels = [self.slots[slot].label for slot in sorted(self.where[PLAYED])]
        unlabelled = sum(1 for label in labels if label is None)
        remaining = len(self.pool)
        assert remaining == sum(1 for slot in self.slots if slot.label is None), (
            "the pool of unplaced identities and the unlabelled slots have come "
            "apart — the walk's bookkeeping is wrong"
        )
        if any(label is not None and rank_of(label) != claim_rank for label in labels):
            p_lie = 1.0
        else:
            of_rank = sum(1 for card in self.pool if rank_of(card) == claim_rank)
            p_lie = 1.0 - _falling_ratio(of_rank, remaining, unlabelled)
        # The completions of the unlabelled slots are the worlds this sample
        # stands for, and there are `remaining!` of them — the factor that makes
        # samples whose reveals labelled different numbers of slots comparable.
        return _Drawn(log_weight=_log_factorial(remaining) - self.log_q, p_lie=p_lie)

    def _check_zones(self) -> None:
        """Every zone the observer projects holds as many slots as the
        information state says it does.

        The walk's own oracle: the projections are counts the observer is
        entitled to, computed by the engine, and a slot model that has dropped
        or duplicated a movement disagrees with them. `deck` is covered by the
        same loop — no slot is ever in it, so the check reads its projection as
        the zero it is once the deal is over.
        """
        for label, view in self.line.info.zones.items():
            size = len(view) if isinstance(view, list) else view
            if size is None:
                raise ValueError(f"zone {label} is not visible even as a count")
            held = len(self.where.get(label, set()))
            assert held == size, (
                f"this walk has {held} cards in {label} where the observer's "
                f"information state shows {size} — the slot model has lost a "
                f"movement"
            )

    def materialize(self, rng: random.Random) -> World:
        """One complete world from this walk: a uniform completion of the
        unlabelled slots, and the action line the log names.

        Drawn from its own generator, so asking for a world changes no other
        sample — and carrying no weight, because the completions are already
        integrated into `_Drawn.log_weight`.
        """
        free = [slot for slot, state in enumerate(self.slots) if state.label is None]
        order = list(self.pool)
        rng.shuffle(order)
        labels = [state.label for state in self.slots]
        for slot, card in zip(free, order, strict=True):
            labels[slot] = card
        seats = 1 + max(state.deal_hand for state in self.slots)
        deal: list[list[str]] = [[] for _ in range(seats)]
        for slot, state in enumerate(self.slots):
            dealt = labels[slot]
            assert dealt is not None, "every slot is labelled by the completion"
            deal[state.deal_hand].append(dealt)
        actions: list[tuple[str, str | int]] = []
        for kind, value in self.items:
            if kind == "card":
                assert isinstance(value, int), "a card item names a slot"
                played = labels[value]
                assert played is not None, "every slot is labelled by the completion"
                actions.append(("card", played))
            else:
                actions.append((kind, value))
        return World(
            deal=tuple(tuple(sorted(hand)) for hand in deal),
            actions=tuple(actions),
        )


def draw(
    infostate: str,
    *,
    seed: int,
    samples: int,
    proposal: Proposal = SMART,
    materialize: bool = False,
) -> Iterator[Sample]:
    """Propose `samples` worlds at this window, rejected ones included.

    Each sample gets its own generator, derived from `seed` and its index, so a
    sample is reproducible on its own and asking one for a world perturbs no
    other.
    """
    if samples <= 0:
        raise ValueError(f"a posterior needs at least one proposal, not {samples}")
    line = _line(infostate)
    for index in range(samples):
        walk = _Walk(line, proposal, random.Random(f"{seed}:{index}"))
        try:
            drawn = walk.run()
        except _Reject as rejected:
            yield Sample(log_weight=-math.inf, p_lie=math.nan, reject=rejected.reason)
            continue
        world = (
            walk.materialize(random.Random(f"{seed}:{index}:completion"))
            if materialize
            else None
        )
        yield Sample(
            log_weight=drawn.log_weight, p_lie=drawn.p_lie, reject=None, world=world
        )


def _self_normalized(weights: Sequence[float], values: Sequence[float]) -> float:
    """The weighted mean of `values`, or `nan` where there is nothing to
    average — a rate over zero samples is not zero."""
    total = sum(weights)
    if not weights or total <= 0.0:
        return math.nan
    return sum(w * v for w, v in zip(weights, values, strict=True)) / total


def estimate(
    infostate: str,
    *,
    seed: int,
    samples: int,
    proposal: Proposal = SMART,
    check: Callable[[World], None] | None = None,
    check_count: int = 0,
) -> Estimate:
    """The literal posterior at this window.

    `check` is the replay check (`gap_replay.make_checker`), applied to the
    first `check_count` accepted worlds and recorded as `n_checked`. It is
    passed in rather than imported so this module stays unable to reach the
    engine — the property the whole estimate rests on.
    """
    if check_count and check is None:
        raise ValueError(
            f"check_count={check_count} asks for replays with no checker to run "
            f"them — the result would record n_checked=0 and read as checked"
        )
    log_weights: list[float] = []
    conditionals: list[float] = []
    rejects: Counter[str] = Counter()
    checked = 0
    for sample in draw(
        infostate,
        seed=seed,
        samples=samples,
        proposal=proposal,
        materialize=check is not None,
    ):
        if sample.reject is not None:
            rejects[sample.reject] += 1
            continue
        log_weights.append(sample.log_weight)
        conditionals.append(sample.p_lie)
        if check is not None and checked < check_count:
            assert sample.world is not None, "an accepted sample was asked to materialize"
            check(sample.world)
            checked += 1
    if not log_weights:
        raise ValueError(
            f"no consistent world in {samples} proposals at this window. A deep "
            f"line is the likely reason and more proposals the answer — the "
            f"proposal leaves the long journeys to luck (see this module's "
            f"'What rejection costs'). A window where no sample count helps is "
            f"instead a line this sampler's model of the log gets wrong, and the "
            f"rejections say which constraint: {dict(rejects)}"
        )
    # Normalized against the largest, because the weight of a world is a
    # factorial over the identities it leaves unplaced and overflows a float
    # long before the estimate needs it.
    top = max(log_weights)
    weights = [math.exp(w - top) for w in log_weights]
    total = sum(weights)
    return Estimate(
        p_lie=_self_normalized(weights, conditionals),
        n_proposed=samples,
        n_accepted=len(weights),
        ess=total * total / sum(w * w for w in weights),
        split_half=(
            _self_normalized(weights[0::2], conditionals[0::2]),
            _self_normalized(weights[1::2], conditionals[1::2]),
        ),
        seed=seed,
        n_checked=checked,
        rejects=tuple(sorted(rejects.items())),
    )
