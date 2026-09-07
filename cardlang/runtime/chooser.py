"""[[chooser]]s: how a player decision is resolved at a decision point.

For random playout, a player picks `n` cards uniformly at random from the legal
[[candidate]]s. The same interface is where a ranking policy plugs in
(`tests/playout_policy.py`), and where OpenSpiel's action-driven control
does (`openspiel/replay.py`).

`sequential_decisions` below is the other half: how one such call reads as the
game tree's own decisions, for every route that resolves or numbers a call one
[[candidate]] at a time.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.observe import render
from cardlang.runtime.state import Chooser
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
    pool = list(candidates)
    taken: list[Any] = []
    for _ in range(n):
        choice = decide(player, pool)
        pool.remove(choice)
        taken.append(choice)
        emit(player, ("chose", render(choice)))
    return taken


def random_chooser(rng: random.Random) -> Chooser:
    def choose(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if n > len(candidates):
            # The game asked for more than the pool holds — an authoring
            # error, so the Owner Guard names the author. Nothing upstream
            # compares the count against the live pool (`_check_count` bars
            # only negative and zero), which is what makes this the Owner
            # rather than a Shadow. Note it guards `random_chooser`, not the
            # `Chooser` seam: `ReplayChooser` has no equivalent.
            raise OwnerGuardError(f"cannot choose {n} of {len(candidates)} candidates")
        return rng.sample(candidates, n)

    return choose
