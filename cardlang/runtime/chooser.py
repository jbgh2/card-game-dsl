"""[[chooser]]s: how a player decision is resolved at a decision point.

For random playout, a player picks `n` cards uniformly at random from the legal
[[candidate]]s. The same interface is where a ranking policy plugs in
(`tests/playout_policy.py`), and where OpenSpiel's action-driven control
does (`openspiel/replay.py`).
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import Chooser
from cardlang.runtime.values import Player


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
