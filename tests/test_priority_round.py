"""The kernel's `priority` order value on the betting/auction round.

The auction form walks a *continuous ring* — `order[i % n]`, the pointer advancing
each turn. The `priority` order value instead re-scans the seat order from the
leader every turn and offers the first still-pending participant. So a seat that
stays pending is re-offered before later seats — the model Stud's betting uses
(and Coup's response windows will). This is a pre-designed value on the closed
order axis (turn-from-a-seat / priority / simultaneous), not a new axis.

The two orders are distinguished by a fixture where each seat must act twice:
priority drains seat 0 fully before seat 1 ([0,0,1,1,2,2]); the ring interleaves
([0,1,2,0,1,2]).
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# Each seat acts until its counter reaches 2; `step` is always the lone legal move.
SRC_PRIORITY = """
game G {
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck }
  state { acted_count[player] : Integer = 0 }
  phase run {
    round offering [step] from 0 over players where acted_count[player] < 2
          order priority
          until (number of players where acted_count[player] < 2) == 0
  }
  winner: highest acted_count
}
move_type step { effect { acted_count[actor] := acted_count[actor] + 1 } }
"""

SRC_RING = SRC_PRIORITY.replace("          order priority\n", "")


def _actor_sequence(src: str) -> list[int]:
    game = check_dsl(src, "order.cardlang")
    seq: list[int] = []

    def recording_chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        seq.append(player)
        return list(candidates[:count])

    play_game(game, random.Random(0), chooser=recording_chooser)
    return seq


def test_priority_order_drains_each_seat_before_advancing() -> None:
    assert _actor_sequence(SRC_PRIORITY) == [0, 0, 1, 1, 2, 2]


def test_continuous_ring_interleaves_the_seats() -> None:
    # The default (no `order` clause) is the continuous ring — the contrast.
    assert _actor_sequence(SRC_RING) == [0, 1, 2, 0, 1, 2]
