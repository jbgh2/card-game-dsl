"""The betting form of the kernel `round` — a continuous ring with no outcome.

The auction form produces a typed variant (a contract) when the ring closes.
Betting does not: each action mutates shared chip/fold state directly, and when
the ring closes play simply moves on to the next street. So the betting form is
the auction form with the `outcome` clause omitted — the ring runs to its `until`
predicate and returns normally, raising no produce signal.
"""

from __future__ import annotations

import random

from cardlang import ast as a
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# A minimal betting-shaped game: each player acts once (both moves drop the actor
# from the ring), the ring empties, and the outcome-less round returns. No phase
# variant, no `produces:` arm.
SRC = """
game G {
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck }
  state { acted[player] : Boolean = false  bumps[player] : Integer = 0 }
  phase run {
    round offering [bump, stop] from 0 over players where not acted[player]
          until (number of players where not acted[player]) is 0
  }
  winner: highest bumps
}
move_type bump { effect { bumps[actor] := bumps[actor] + 1  acted[actor] := true } }
move_type stop { effect { acted[actor] := true } }
"""


def _round_node(game: a.nodes.Game) -> a.nodes.AuctionRound:
    for phase in game.phases:
        for item in phase.items:
            if isinstance(item, a.nodes.AuctionRound):
                return item
    raise AssertionError("no AuctionRound node found")


def test_betting_round_parses_without_an_outcome_clause() -> None:
    game = check_dsl(SRC, "betting.cardlang")
    rnd = _round_node(game)
    assert rnd.offering == ("bump", "stop")
    assert rnd.outcome_fn is None  # the betting form omits the outcome


def test_outcome_less_round_runs_to_termination_and_returns() -> None:
    game = check_dsl(SRC, "betting.cardlang")
    for seed in range(20):
        result = play_game(game, random.Random(seed))  # must not raise
        assert result.winner in (0, 1, 2)
