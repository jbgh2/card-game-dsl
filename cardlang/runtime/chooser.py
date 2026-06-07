"""Choosers: how a player decision is resolved at a decision point.

For random playout, a player picks `n` cards uniformly at random from the legal
candidates. The same interface is where a real policy (or OpenSpiel's
action-driven control) would plug in later.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.runtime.state import Chooser
from cardlang.runtime.values import Player


def random_chooser(rng: random.Random) -> Chooser:
    def choose(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if n > len(candidates):
            raise ValueError(f"cannot choose {n} of {len(candidates)} candidates")
        return rng.sample(candidates, n)

    return choose
