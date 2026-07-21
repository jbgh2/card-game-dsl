"""The participant-filter axis of the auction `round`: the `over players where
<pred>` ring is re-evaluated *each turn*, so a player the predicate drops
mid-ring (a standing high bidder, a player who has passed for good) is never
offered another turn and consumes no chooser draw — the shrinking ring the
ascending auctions (Pinochle, Tarot, Skat) and Stud's betting need.

The execution counterpart to test_auction_round_parse.py (which pins the
frontend). Here we drive a continuous ring with an injected chooser and assert
the excluded player is not re-offered.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# A three-player continuous ring. `leader` is the standing high bidder: once a
# player bids it is set to that player and the participants predicate excludes
# it. The auction borrows bridge_auction_outcome's all-pass arm (made_bid stays
# false) for a trivial termination once `steps` reaches the cap.
SHRINKING_RING_SRC = """
game G {
  players: 3
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state {
    leader   : Player? = none
    made_bid : Boolean = false
    steps    : Integer = 0
    marker[player] : Integer = 0
  }
  phase hand {
    phase auction -> outcome { contract_finalized(Player, Integer, Suit?, Integer) | all_pass } {
      round offering [bid, pass] from 0
            over players where (leader is none or player is not leader)
            until steps >= 6 outcome bridge_auction_outcome
    }
    auction produces:
      contract_finalized(d, l, s, x) { }
      all_pass { }
  }
  winner: highest marker
}
move_type bid  { effect { leader := actor  steps := steps + 1 } }
move_type pass { effect { steps := steps + 1 } }
"""


def test_participant_ring_re_evaluated_each_turn() -> None:
    # Player 0 bids on its first turn (becoming the standing leader); everyone
    # else — and player 0 if it is ever re-offered — passes. With per-turn
    # re-evaluation the leader is excluded from every later ring step, so it is
    # asked exactly once. Under a once-at-entry snapshot, player 0 would stay in
    # the ring and be re-offered on each wrap (asks.count(0) > 1).
    game = check_dsl(SHRINKING_RING_SRC, "g.cardlang")
    asks: list[int] = []
    bid_made = [False]

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        asks.append(player)
        if player == 0 and not bid_made[0]:
            bid_made[0] = True
            return [c for c in candidates if c[0] == "bid"]
        return [c for c in candidates if c[0] == "pass"]

    play_game(game, random.Random(0), chooser=chooser)

    assert asks.count(0) == 1, f"standing leader was re-offered a turn: asks={asks}"
    # The other two seats kept the ring turning until the step cap.
    assert asks.count(1) >= 1 and asks.count(2) >= 1
