"""`deal … as-equally-as-possible` — the round-robin deal Getaway uses to spread
an indivisible deck across 3–8 hands."""

from __future__ import annotations

import random

from cardlang.pipeline import check_dsl

# 5 players, 52 cards -> 11, 11, 10, 10, 10 (the first two get the remainder).
DEAL_GAME = """
game DealTest {
  players: 5
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {
    deck : Deck
    hand[player] : Hand<player>
  }
  phase setup { deal all cards from deck as-equally-as-possible to each hand }
  loser: the player where (number of players where hand[player] is not empty) is 0
}
"""


def test_round_robin_spreads_the_remainder() -> None:
    game = check_dsl(DEAL_GAME, "deal.dsl")
    # play_game will assert on the loser selection (no player has 0 cards here),
    # so capture hand sizes via a tracer-free run guarded against the loser eval.
    from cardlang.runtime.state import RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating, build_deck

    seating = Seating(5)
    zones = ZoneStore(game.zones, seating.players)
    rs = RuntimeState(seating, zones, random.Random(0))
    rs.zones.single("deck").add_all(build_deck("standard52"))
    from cardlang.ast import nodes as n
    from cardlang.runtime.chooser import random_chooser
    from cardlang.runtime.execute import execute
    from cardlang.runtime.state import Ctx

    ctx = Ctx(rs=rs, chooser=random_chooser(random.Random(0)))
    rs.push_frame()
    deal = next(it for it in game.phases[0].items if isinstance(it, n.Movement))
    execute(deal, ctx)

    sizes = sorted(len(rs.zones.instance("hand", p).cards) for p in seating.players)
    assert sizes == [10, 10, 10, 11, 11]
    assert rs.zones.single("deck").empty
