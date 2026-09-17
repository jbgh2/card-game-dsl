"""[[chooser]]s: how a player decision is resolved at a decision point.

For random playout, a player picks `n` cards uniformly at random from the legal
[[candidate]]s. The same interface is where a ranking policy plugs in
(`tests/playout_policy.py`), and where OpenSpiel's action-driven control
does (`openspiel/replay.py`).

`sequential_decisions` below is the other half: how one such call reads as the
game tree's own decisions, for every route that resolves or numbers a call one
[[candidate]] at a time.

Contract
--------
Assumes: a checked game, and a [[context]] naming the phase and the decider.
Establishes: `decide` is the one route from a decision site to the Chooser, and
it emits the decider's `asked` observation before the Chooser is consulted, so
what a seat is asked reaches it by the same channel as what it chose. Illegal
after this: `ctx.chooser(...)` outside `decide`; a decision site absent from
`delegation.DECISION_POINTS`; a decision asked outside every phase.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from cardlang.runtime.delegation import DECISION_POINTS
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.observe import render
from cardlang.runtime.state import Chooser, Ctx
from cardlang.runtime.values import Player


def sequential_decisions(
    player: Player,
    candidates: list[Any],
    n: int,
    decide: Callable[[Player, list[Any]], Any],
    emit: Callable[[Player, tuple[Any, ...]], None],
) -> list[Any]:
    """One Chooser call as the `n` decisions the game tree makes of it.

    A call for `n` [[candidate]]s branches the tree `n` times, each from the
    pool the ones before it left (docs/authoring.md, "`move chosen N cards` is
    N sequential single-card decisions"). `decide` answers at one of those
    decisions; `emit` delivers the [[decider]]'s own record of what it took.
    Every route that walks a call this way reads this one definition, so no two
    of them can number the same call differently or leave a seat remembering
    different halves of it.

    Two details are load-bearing. `decide` sees the pool before the candidate
    it names leaves it and the log before that candidate is recorded, so a
    route that pauses inside the call surfaces exactly what is already
    committed — which is what keeps the `n` positions distinguishable, and one
    decision's worth of recall apart. And the pool drops the FIRST candidate
    equal to the one taken, so a two-deck game takes one of a matching pair
    rather than both.
    """
    if n > len(candidates):
        # The game asked for more than the pool holds: the authoring error
        # `random_chooser` refuses on the per-call route, refused here for every
        # route that reads a call one pick at a time, before the first pick
        # leaves a later one choosing from nothing.
        raise OwnerGuardError(f"cannot choose {n} of {len(candidates)} candidates")
    pool = list(candidates)
    taken: list[Any] = []
    for _ in range(n):
        choice = decide(player, pool)
        pool.remove(choice)
        taken.append(choice)
        emit(player, ("chose", render(choice)))
    return taken


def decide(
    ctx: Ctx,
    decider: Player,
    candidates: list[Any],
    n: int,
    site: str,
    destination: str | None = None,
    construct: str | None = None,
) -> list[Any]:
    """The one route from a decision site to the [[chooser]].

    Tells the [[decider]] what it is being asked before the Chooser is
    consulted, then asks. The ask names the phase, the construct asking, how
    many picks it wants and — where the site knows it before the choice — the
    zone they land in. It is delivered to the decider alone, which is who the
    question is put to; a seat watching learns what moved, through the
    projections, not what its neighbour was invited to do.

    `site` is the caller's own row of `DECISION_POINTS`, so the construct word
    is the table's rather than the call's. A round passes its form's word
    instead, because one `round` sentence asks a trick, an auction or a climb
    and those are three decisions to a designer; a form takes that word from
    `FORM_CONSTRUCTS` when it is built, so an unknown form has already failed
    by the time a seat is asked.
    """
    word = construct if construct is not None else DECISION_POINTS[site].construct
    if ctx.current_phase is None:
        # A decision names the stretch of play it is asked in, and there is no
        # honest name for one asked outside every phase. Setup deals and the
        # result read make no decisions, so nothing legitimate lands here; a
        # sentinel would put an unreadable phase in every seat's information
        # state instead of naming the malformed game.
        raise OwnerGuardError(
            f"a {word} decision at {site} is asked outside every phase, so "
            f"it can name no stretch of play — a decision belongs to a phase"
        )
    ctx.observe(decider, ("asked", ctx.current_phase.name, word, n, destination))
    return ctx.chooser(decider, candidates, n)


def random_chooser(rng: random.Random) -> Chooser:
    def choose(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if n > len(candidates):
            # The game asked for more than the pool holds — an authoring
            # error, so the Owner Guard names the author. Nothing upstream
            # compares the count against the live pool (`_check_count` bars
            # only negative and zero), which is what makes this the Owner
            # rather than a Shadow. It owns the per-call route; the per-pick
            # routes meet the same refusal in `sequential_decisions`.
            raise OwnerGuardError(f"cannot choose {n} of {len(candidates)} candidates")
        return rng.sample(candidates, n)

    return choose
