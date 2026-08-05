"""The auction form of `round`: a continuous ring with a move vocabulary and a
termination predicate (`round offering [..] from <seat> over <ring> until <pred>
outcome <fn>`).

This is the same kernel `round` construct as the trick, configured along
different axes — a move-vocabulary (`offering`) instead of a single card play,
and a continuous-ring termination (`until`) instead of a single pass. Here we pin
only the frontend: it parses, resolves, type-checks, and round-trips to the IR
with the trick-specific fields left absent. The runtime lands in a later commit.
"""

from __future__ import annotations

from typing import Any

from cardlang.ast import nodes as n
from cardlang.ir import emit
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl

SRC = """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { high : Integer = 0  passes : Integer = 0 }
  phase bid {
    round offering [raise, pass] from 0 over all players
          until (passes >= 2) outcome bridge_auction_outcome
  }
  winner: highest high
}
move_type raise { effect { high += 1  passes := 0 } }
move_type pass { effect { passes += 1 } }
"""


def _round(game: n.Game) -> n.Round:
    phase = game.phases[0]
    return next(i for i in phase.items if isinstance(i, n.Round))


def test_auction_round_parses_vocab_and_termination() -> None:
    rnd = _round(parse_text(SRC, "g.cardlang"))
    assert rnd.offering == ("raise", "pass")
    assert rnd.termination is not None
    assert rnd.outcome_fn == "bridge_auction_outcome"
    # The trick-specific fields are absent in the auction form.
    assert rnd.move_type is None
    assert rnd.source_zone is None and rnd.play_zone is None


def test_auction_round_round_trips_to_ir() -> None:
    ir: Any = emit(check_dsl(SRC, "g.cardlang"))
    rnd = next(
        i for i in ir["phases"][0]["items"] if i["kind"] == "round"
    )
    assert rnd["offering"] == ["raise", "pass"]
    assert rnd["move_type"] is None
    assert rnd["source_zone"] is None
    assert rnd["termination"] is not None
