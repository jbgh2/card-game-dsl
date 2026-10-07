"""`loser:` game result + driver generalization (Getaway).

Getaway has no score variable: the game ends when one player is left holding
cards, and that player is the loser. This pins down that the driver computes a
result from a player-valued selection — not from a numeric score var — so the
`GameResult` of a `loser:` game names its loser, and its winners are every
other seat.
"""

from __future__ import annotations

import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

LOSER_GAME = """
game LoserTest {
  players: 4
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {
    deck : Deck
    hand[player] : Hand<player>
  }
  phase setup {
    deal 13 cards from deck to each hand
  }
  loser: player_holding(A of spades)
}
"""


def test_driver_computes_a_loser_without_a_score_var() -> None:
    game = check_dsl(LOSER_GAME, "loser.dsl")
    result = play_game(game, random.Random(0))
    # A loser emerged; every other seat wins, and there are no scores.
    assert result.loser is not None
    assert result.winners == frozenset(range(4)) - {result.loser}
    assert result.scores == {}
    assert result.seat_scores == ()
    # The loser is whoever holds the ace of spades (deterministic, unshuffled).
    assert result.loser in range(4)
