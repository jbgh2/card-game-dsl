import random
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

SRC = """
game G {
  players: 4
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  trump: spades
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  captured[player] : PlayerPile<player> }
  state { tricks_won[player] : Integer = 0  leader : Player? = none }
  phase deal { shuffle deck  deal 13 cards from deck to each hand  leader := 0 }
  phase play {
    active_rules: [MustFollowSuit]
    legal_moves: [play_to_trick]
    repeat until (all player p: hand[p] is empty) {
      round play_to_trick from leader over all players source hand into trick_pile outcome highest_trump_or_led_suit
      move all cards from trick_pile to captured[outcome]
      tricks_won[outcome] += 1
      leader := outcome
    }
  }
  winner: highest tricks_won
}
rule MustFollowSuit { constrains: play_to_trick  applies_when: state.led_suit is not none  demands: hand.cards_of_suit(state.led_suit) }
"""


def test_round_plays_full_tricks_and_conserves_cards() -> None:
    game = check_dsl(SRC, "g.cardlang")
    for seed in range(20):
        plays: list[Any] = []
        tricks: list[Any] = []
        census: dict[str, Any] = {}

        def tr(e: str, d: Any) -> None:
            if e == "play": plays.append(d)
            elif e == "trick": tricks.append(d)
            elif e == "game_end": census.clear(); census.update(d)
        result = play_game(game, random.Random(seed), tr)
        assert len(tricks) == 13 and len(plays) == 52
        assert census["total"] == 52 and census["hands_with_cards"] == 0
        assert sum(result.scores.values()) == 13  # 13 tricks distributed
