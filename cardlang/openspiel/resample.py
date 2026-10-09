"""Worlds a seat cannot tell from the one being played: the construction
behind `CardlangState.resample_from_infostate`.

A determinizing solver (OpenSpiel's `ISMCTSBot` and its family) asks, at a
seat's decision, for a [[world]] drawn from that seat's information set. The
adapter's state is ``(seed, script, history)`` (`cardlang.openspiel.game`), so
an answer is a new such triple whose replay leaves the seat's information
state and the seat to move exactly as they were — and the legal actions too,
when the seat is the one to move — while every card the seat has not seen
may lie elsewhere.

The construction is by rejection over a proposal that is a function of the
seat's information state and the sampler's randomness alone:

- **What the seat has identified.** Every card its observation log names, and
  every card its Seat View shows at the pause (a zone it sees at identity, a
  State Variable), is identified — and identified *as of the draw that last
  placed it*, its epoch, because a card seen before a reshuffle says nothing
  about where the reshuffle put it.
- **Draws.** Draw `i` of the new world keeps each card identified in epoch
  `i` at the position the true draw gave it, and permutes the rest of its
  items uniformly over the remaining positions.
- **Picks.** The seat's own picks replay as recorded; so does another seat's
  pick of an identified card, and another seat's non-card pick that the seat
  heard announced (an `announce` event spelling it). Every other pick is one
  the seat did not see, and is re-chosen uniformly among the legal actions
  that move no identified card.
- **Acceptance.** The proposal is run forward, its observation stream
  compared with the seat's log event by event, and accepted only when the
  pause it reaches renders the same information state, asks the same seat,
  and — when the observer is that seat — offers it the same actions. The run that accepts it is `replay.run` under the
  script and picks it returns, so the adapter's own replay of the returned
  triple arrives at that same pause (pinned in tests/openspiel_ready/test_ismcts.py).

So a constructed world is the posterior of the observer's information state
under uniform chance and uniform play at the picks it did not see, with one
designed residual: an identified card keeps its true trajectory within its
epoch — the position it was dealt from and the picks that moved it — even
where the seat saw only where it ended up (a card passed between two
opponents and later played). The cards still in play that the seat has not
identified are the ones a solver's search reads, and those are redrawn.

Contract
--------
Assumes: a game `ActionSpace.for_game` derives, at a decision node, whose
draws are all reached through `ScriptedRandom` (`replay.generator_for`).
Establishes: a returned world replays, under `replay.run`, to a decision of
the same seat — with the same legal actions when the observer is that seat —
and the observer's information state byte-identical; the proposal reads the true line only through what
the observer has identified, its own picks, and the announcements it heard,
so two worlds the observer cannot tell apart yield the same proposal from
the same sampler randomness. A game this construction does not cover —
a deck with repeated cards, a random selection — is refused before any
proposal is drawn, and a budget spent without an acceptance is refused too,
each as `ResampleRefusal`. Illegal after this: handing a solver a world this
module did not accept; reading a true pick's action id at a pick the
observer did not see.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from cardlang.openspiel.encoding import ComboAction
from cardlang.openspiel.infostate import derive, information_state
from cardlang.openspiel.replay import (
    DecisionNode,
    Drawn,
    Moment,
    Picked,
    Seen,
    chance_free,
    load,
    run,
)
from cardlang.runtime.chance import Draw, Outcome
from cardlang.runtime.observe import render
from cardlang.runtime.state import ChooserAbort
from cardlang.runtime.values import Card, build_deck

# How many proposals `resample` judges before refusing; a refusal names it.
ATTEMPTS = 2000
# How many of them are independent draws before the search turns to repair.
FRESH = 16

# An identified card, keyed by its epoch: the index of the draw that last
# placed it, or None for a card no draw has touched.
_Unit = tuple[int | None, Card]


class ResampleRefusal(Exception):
    """No world can be constructed for this request.

    Author: the engine maintainer. The game is legal and the request is the
    one OpenSpiel's solvers make; what is missing is construction this module
    does not yet perform — a deck with repeated cards, a draw it cannot
    script, or a proposal too weak to be accepted within `ATTEMPTS`. Outside
    `GameDescriptionError` for that reason: a harness catching that base to
    report an illegal game must not swallow a capability gap.
    """


@dataclass(frozen=True)
class Constructed:
    """A world `resample` accepted: the adapter state's three parts."""

    seed: int
    script: tuple[Outcome, ...]
    history: tuple[int, ...]


@dataclass(frozen=True)
class Entitlement:
    """What the observer is entitled to at the pause of the true line, and the
    true line's shape a proposal must keep."""

    observer: int
    pause: DecisionNode
    information_state: str
    log: tuple[tuple[Any, ...], ...]
    draws: tuple[Draw, ...]
    known: tuple[frozenset[Card], ...]  # per draw: the cards identified in its epoch
    identified: frozenset[_Unit]
    deciders: tuple[int, ...]
    replayed: tuple[bool, ...]  # per pick: replay the recorded action id


def _cards_named(x: Any, by_render: dict[str, Card]) -> Iterable[Card]:
    """Every card an observation event or a Seat View field names: an exact
    rendering in an event, a `Card` in a view, walked through tuples, lists
    and mappings."""
    if isinstance(x, Card):
        yield x
    elif isinstance(x, str):
        card = by_render.get(x)
        if card is not None:
            yield card
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _cards_named(k, by_render)
            yield from _cards_named(v, by_render)
    elif isinstance(x, (tuple, list, set, frozenset)):
        for y in x:
            yield from _cards_named(y, by_render)


def _moves(value: Any) -> tuple[Card, ...]:
    """The cards a decoded action moves: a card's id names it, a combination's
    names its card-set (`encoding.ComboAction`), and an offering moves the
    cards among its parameters. A bare name or an integer moves none."""
    if isinstance(value, ComboAction):
        return tuple(value.cards)
    return tuple(card for card in _cards_named(value, {}) if isinstance(card, Card))


def _renderings(path: str) -> dict[str, Card]:
    game, _ = load(path)
    deck = build_deck(game.deck)
    by_render = {str(c): c for c in deck}
    if len(by_render) != len(deck):
        raise ResampleRefusal(
            f"{path}: its deck holds repeated cards, and a world is constructed "
            f"by telling every card from every other (issue #830)"
        )
    return by_render


def entitlement(
    path: str,
    seed: int,
    script: tuple[Outcome, ...],
    history: tuple[int, ...],
    observer: int,
) -> Entitlement:
    """Replay the true line and derive what `observer` has identified."""
    by_render = _renderings(path)
    _, space = load(path)
    moments: list[Moment] = []
    pause = run(path, seed, history, script=script, listen=moments.append)
    if not isinstance(pause, DecisionNode):
        raise ValueError("a world is resampled at a decision node, and this line has ended")

    epoch: dict[Card, int] = {}
    identified: set[_Unit] = set()
    draws: list[Draw] = []
    deciders: list[int] = []
    moved: dict[int, frozenset[_Unit]] = {}  # pick index -> the cards it moves, in their epochs
    unheard: dict[int, list[int]] = {}  # seat -> its non-card picks not yet announced
    heard: set[int] = set()
    log: list[tuple[Any, ...]] = []
    for moment in moments:
        if isinstance(moment, Drawn):
            if moment.draw.kind != "shuffle":
                raise ResampleRefusal(
                    f"{path}: a random selection draws here, and no world is "
                    f"constructed across one yet (issue #831)"
                )
            draws.append(moment.draw)
            for card in moment.draw.after:
                epoch[card] = moment.draw.index
        elif isinstance(moment, Picked):
            deciders.append(moment.decider)
            value = space.decode(history[moment.index])
            cards = _moves(value)
            if cards:
                moved[moment.index] = frozenset((epoch.get(card), card) for card in cards)
            elif moment.decider != observer:
                unheard.setdefault(moment.decider, []).append(moment.index)
        elif moment.player == observer:
            log.append(moment.event)
            for card in _cards_named(moment.event, by_render):
                identified.add((epoch.get(card), card))
            if moment.event[0] == "announce":
                _, seat, spelled = moment.event
                for index in unheard.get(seat, []):
                    if render(space.decode(history[index])) == spelled:
                        heard.add(index)
                        unheard[seat].remove(index)
                        break
    view = derive(observer, pause.rs, pause.obs_logs[observer])
    for card in _cards_named((view.zones, view.state), by_render):
        identified.add((epoch.get(card), card))

    replayed = tuple(
        decider == observer
        or not moved.get(index, frozenset()).isdisjoint(identified)
        or index in heard
        for index, decider in enumerate(deciders)
    )
    return Entitlement(
        observer=observer,
        pause=pause,
        information_state=information_state(observer, pause.rs, pause.obs_logs[observer]),
        log=tuple(log),
        draws=tuple(draws),
        known=tuple(
            frozenset(card for e, card in identified if e == draw.index) for draw in draws
        ),
        identified=frozenset(identified),
        deciders=tuple(deciders),
        replayed=replayed,
    )


class _Rejected(Exception):
    """A proposal left the observer's information set. The argument says
    where."""


@dataclass(frozen=True)
class _Proposal:
    """A candidate world, as the randomness that builds it: per draw, one key
    per position not holding an identified card (the free items take those
    positions in key order), and per pick one key choosing among the actions a
    pick the observer did not see may take."""

    draws: tuple[tuple[float, ...], ...]
    picks: tuple[float, ...]


@dataclass(frozen=True)
class _Verdict:
    """How far a proposal got: its world if accepted, else where it left the
    observer's information set; `progress` counts the observations matched
    and picks made before it did."""

    world: tuple[tuple[Outcome, ...], tuple[int, ...]] | None
    reason: str
    progress: int


def _free_slots(owed: Entitlement) -> tuple[int, ...]:
    return tuple(
        sum(card not in known for card in draw.after)
        for draw, known in zip(owed.draws, owed.known)
    )


def _fresh(owed: Entitlement, history: tuple[int, ...], rnd: random.Random) -> _Proposal:
    return _Proposal(
        draws=tuple(tuple(rnd.random() for _ in range(n)) for n in _free_slots(owed)),
        picks=tuple(rnd.random() for _ in history),
    )


def _neighbour(proposal: _Proposal, owed: Entitlement, rnd: random.Random) -> _Proposal:
    """One step from `proposal`: two free items of one draw trade places, or
    one unseen pick takes a new key."""
    swappable = [i for i, keys in enumerate(proposal.draws) if len(keys) >= 2]
    unseen = [j for j, replayed in enumerate(owed.replayed) if not replayed]
    if swappable and (not unseen or rnd.random() < 0.75):
        i = rnd.choices(swappable, weights=[len(proposal.draws[i]) for i in swappable])[0]
        keys = list(proposal.draws[i])
        a, b = rnd.sample(range(len(keys)), 2)
        keys[a], keys[b] = keys[b], keys[a]
        return _Proposal(proposal.draws[:i] + (tuple(keys),) + proposal.draws[i + 1 :], proposal.picks)
    if unseen:
        j = rnd.choice(unseen)
        picks = proposal.picks[:j] + (rnd.random(),) + proposal.picks[j + 1 :]
        return _Proposal(proposal.draws, picks)
    return proposal


def _evaluate(
    path: str, history: tuple[int, ...], owed: Entitlement, proposal: _Proposal
) -> _Verdict:
    """Run `proposal` forward and judge it against the observer's view."""
    _, space = load(path)
    script: list[Outcome] = []
    taken: list[int] = []
    epoch: dict[Card, int] = {}
    heard = 0

    def construct(index: int, kind: str, items: list[Any]) -> Outcome:
        if index >= len(owed.draws):
            raise _Rejected("a draw the true line does not make")
        true = owed.draws[index]
        known = owed.known[index]
        keys = proposal.draws[index]
        rest = [card for card in items if card not in known]
        if kind != true.kind or len(items) != len(true.before) or len(rest) != len(keys):
            raise _Rejected(f"draw {index} over different items")
        order = sorted(range(len(rest)), key=keys.__getitem__)
        fill = iter(rest[k] for k in order)
        dealt = [card if card in known else next(fill) for card in true.after]
        at = {card: position for position, card in enumerate(items)}
        outcome = tuple(at[card] for card in dealt)
        script.append(outcome)
        return outcome

    def listen(moment: Moment) -> None:
        nonlocal heard
        if isinstance(moment, Drawn):
            for card in moment.draw.after:
                epoch[card] = moment.draw.index
        elif isinstance(moment, Seen) and moment.player == owed.observer:
            if heard >= len(owed.log) or moment.event[0] != owed.log[heard][0]:
                raise _Rejected(f"observation {heard}: a different kind of event")
            if moment.event != owed.log[heard]:
                raise _Rejected(f"observation {heard}: a different {moment.event[0]!r}")
            heard += 1

    def moves_identified(aid: int) -> bool:
        return any(
            (epoch.get(card), card) in owed.identified for card in _moves(space.decode(aid))
        )

    def pick(decider: int, legal: list[int]) -> int:
        index = len(taken)
        if index == len(history):
            raise ChooserAbort(decider, legal)
        if decider != owed.deciders[index]:
            raise _Rejected(f"pick {index}: a different seat decides")
        if owed.replayed[index]:
            aid = history[index]
            if aid not in legal:
                raise _Rejected(f"pick {index}: the recorded action is not legal")
        else:
            options = [aid for aid in legal if not moves_identified(aid)]
            if not options:
                raise _Rejected(f"pick {index}: every legal action moves an identified card")
            aid = options[int(proposal.picks[index] * len(options))]
        taken.append(aid)
        return aid

    try:
        node = run(
            path,
            0,
            (),
            listen=listen,
            construct=None if chance_free(path) else construct,
            beyond=pick,
        )
    except _Rejected as rejected:
        return _Verdict(None, str(rejected), heard + len(taken))
    progress = heard + len(taken)
    if not isinstance(node, DecisionNode) or len(taken) != len(history):
        return _Verdict(None, "the line ends before the pause", progress)
    if len(script) != len(owed.draws):
        return _Verdict(None, "fewer draws than the true line", progress)
    if node.player != owed.pause.player:
        return _Verdict(None, "a different seat to move at the pause", progress)
    if owed.observer == node.player and node.legal != owed.pause.legal:
        return _Verdict(None, "different legal actions at the pause", progress)
    if (
        information_state(owed.observer, node.rs, node.obs_logs[owed.observer])
        != owed.information_state
    ):
        return _Verdict(None, "a different information state at the pause", progress)
    return _Verdict((tuple(script), tuple(taken)), "", progress)


def resample(
    path: str,
    seed: int,
    script: tuple[Outcome, ...],
    history: tuple[int, ...],
    observer: int,
    rnd: random.Random,
    seeds: int,
    attempts: int = ATTEMPTS,
) -> Constructed:
    """A world `observer` cannot tell from ``(seed, script, history)``, drawn
    with `rnd`; its seed, which deals every draw past the pause, is drawn from
    ``range(seeds)``.

    The first `FRESH` proposals are independent, so a world accepted among
    them is drawn from the posterior exactly. Past them, the search repairs
    the proposal that got furthest, one `_neighbour` step at a time, keeping a
    step that gets no less far: the world it reaches is in the information set
    and built from the observer's view alone, without the posterior's weights.
    """
    owed = entitlement(path, seed, script, history, observer)
    where: Counter[str] = Counter()
    best: tuple[_Proposal, int] | None = None
    for attempt in range(attempts):
        if attempt < FRESH or best is None:
            proposal = _fresh(owed, history, rnd)
        else:
            proposal = _neighbour(best[0], owed, rnd)
        verdict = _evaluate(path, history, owed, proposal)
        if verdict.world is not None:
            return Constructed(rnd.randrange(seeds), *verdict.world)
        where[verdict.reason] += 1
        if best is None or verdict.progress >= best[1]:
            best = (proposal, verdict.progress)
    commonest = ", ".join(f"{reason} ({count})" for reason, count in where.most_common(3))
    raise ResampleRefusal(
        f"{path}: no world consistent with seat {observer}'s information state "
        f"was accepted in {attempts} proposals at pick {len(history)}; they "
        f"left it at: {commonest} (issue #832)"
    )
