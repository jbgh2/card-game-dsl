"""`before_each` / `after_each` run once per loop iteration.

A synthetic loop game whose `after_each` increments a per-player score until
the loop's predicate fires, proving the hooks run every iteration.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

LOOP_GAME = """
game L {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck }
  state { score[player] : Integer = 0 }
  phase loop repeats until (any player p: score[p] >= 3) {
    before_each { }
    after_each {
      for each player p: score[p] += 1
    }
  }
  winner: lowest score
}
"""


def test_after_each_runs_every_iteration() -> None:
    game = check_dsl(LOOP_GAME, "loop.cardlang")
    iterations = 0

    def tracer(event: str, data: Any) -> None:
        nonlocal iterations
        if event == "hand_end":
            iterations += 1

    result = play_game(game, random.Random(0), tracer)
    # after_each adds 1 to each score per iteration; loop stops at >= 3.
    assert iterations == 3
    assert result.scores == {0: 3, 1: 3}
