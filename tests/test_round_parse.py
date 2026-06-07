from cardlang.ast import nodes as n
from cardlang.parse import parse_text

SRC = """
game G {
  players: 4
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  captured[player] : PlayerPile<player> }
  state { leader : Player? = none  trump_suit : Suit? = none }
  phase play {
    active_rules: [MustFollowSuit]
    legal_moves: [play_to_trick]
    round play_to_trick from leader over all players source hand into trick_pile outcome highest_trump_or_led_suit trump trump_suit
    leader := outcome
  }
  winner: highest leader
}
rule MustFollowSuit { constrains: play_to_trick  applies_when: state.led_suit is not none  demands: hand.cards_of_suit(state.led_suit) }
"""


def test_round_parses() -> None:
    game = parse_text(SRC, "g.cardlang")
    rnd = next(i for i in game.phases[0].items if isinstance(i, n.Round))
    assert rnd.move_type == "play_to_trick"
    assert rnd.source_zone == "hand" and rnd.play_zone == "trick_pile"
    assert rnd.outcome_fn == "highest_trump_or_led_suit"
    assert isinstance(rnd.leader, n.NameRef) and rnd.leader.name == "leader"
    assert isinstance(rnd.participants, n.AllPlayers)
    assert rnd.trump is not None and isinstance(rnd.trump, n.NameRef)
