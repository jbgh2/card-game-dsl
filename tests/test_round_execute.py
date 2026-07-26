import random
from typing import Any

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

SRC = """
game G {
  players: 4
  max_length: 1000
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
    repeat until (all players where hand[player] is empty) {
      round play_to_trick from leader over all players source hand into trick_pile outcome highest_trump_or_led_suit
      move all cards from trick_pile to captured[outcome]
      tricks_won[outcome] += 1
      leader := outcome
    }
  }
  winner: highest tricks_won
}
"""


EARLY_SRC = """
game G {
  players: 4
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  waste : Discard }
  state { tricks_won[player] : Integer = 0  leader : Player? = none }
  phase deal { shuffle deck  deal 13 cards from deck to each hand  leader := 0 }
  phase play {
    active_rules: [MustFollowSuit]
    legal_moves: [play_to_trick]
    // A tochoo ends the trick, so hands deplete unevenly; only non-empty hands
    // play, and we stop once at most one player still holds cards.
    repeat until (number of players where hand[player] is not empty) <= 1 {
      round play_to_trick from leader over players where hand[player] is not empty source hand into trick_pile outcome highest_of_led_suit early on_play_of_tochoo
      move all cards from trick_pile to waste
      tricks_won[outcome] += 1
      leader := outcome
    }
  }
  winner: highest tricks_won
}
"""


def test_round_early_termination_ends_tricks_early() -> None:
    # A tochoo (off-suit play, only possible when void) must end the trick: with
    # the early predicate wired, some tricks see fewer than 4 plays.
    game = check_dsl(EARLY_SRC, "g.cardlang")
    early_terminations = 0
    for seed in range(20):

        def tr(e: str, d: Any) -> None:
            nonlocal early_terminations
            if e == "trick_end" and d["early"]:
                early_terminations += 1

        play_game(game, random.Random(seed), tr)
    assert early_terminations > 0


def test_round_early_termination_fires_only_on_a_tochoo() -> None:
    # Not just "fires at all": when a trick ends early, the breaking (last) card
    # must be off the led suit — a genuine tochoo. Guards against an over-eager
    # predicate that fires on a legal follow. (A tochoo by the last player in turn
    # order still ends the trick, so play count alone is not the signal.)
    game = check_dsl(EARLY_SRC, "g.cardlang")
    checked = 0
    for seed in range(20):
        plays: list[Any] = []

        def tr(e: str, d: Any) -> None:
            nonlocal checked
            if e == "play":
                plays.append(d[1])  # (player, card) -> the card  # noqa: B023 -- consumed before the loop advances
            elif e == "trick_end":
                if d["early"]:
                    led = plays[0].suit  # noqa: B023 -- consumed before the loop advances
                    assert plays[-1].suit != led  # the tochoo is off-suit  # noqa: B023 -- consumed before the loop advances
                    checked += 1
                plays.clear()  # noqa: B023 -- consumed before the loop advances

        play_game(game, random.Random(seed), tr)
    assert checked > 0


NO_ROUND_SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase setup {
    shuffle deck
    deal 1 card from deck to each hand
    // Reading `state.x` with no round having run is a bug; it must fail loudly,
    // not silently return a stale or empty frame.
    if state.trick_terminated_early { score[0] := 1 }
  }
  winner: highest score
}
"""


def test_round_state_read_without_a_round_fails_loudly() -> None:
    # A premature `state.` read is the game description's error (the checker
    # validates the field, not the read's position in game flow), so the loud
    # failure is a typed RuntimeError — the runtime's currency — not an assert.
    game = check_dsl(NO_ROUND_SRC, "g.cardlang")
    with pytest.raises(RuntimeError, match="no active or just-completed round"):
        play_game(game, random.Random(0))


STATE_SRC = """
game G {
  players: 4
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  waste : Discard }
  state { tricks_won[player] : Integer = 0  leader : Player? = none }
  phase deal { shuffle deck  deal 13 cards from deck to each hand  leader := 0 }
  phase play {
    active_rules: [MustFollowSuit]
    legal_moves: [play_to_trick]
    repeat until (number of players where hand[player] is not empty) <= 1 {
      round play_to_trick from leader over players where hand[player] is not empty source hand into trick_pile outcome highest_of_led_suit early on_play_of_tochoo
      // Read the just-finished round's terminal state in the surrounding body.
      if state.trick_terminated_early { tricks_won[outcome] += 1 }
      move all cards from trick_pile to waste
      leader := outcome
    }
  }
  winner: highest tricks_won
}
"""


def test_round_terminated_state_readable_in_body() -> None:
    # After a `round` returns, the surrounding body must see the round's terminal
    # state (`state.trick_terminated_early`) — the Getaway conditional-routing
    # pattern. The body counts one per early-terminated trick; that count must
    # equal the tracer's early `trick_end` events for every seed.
    game = check_dsl(STATE_SRC, "g.cardlang")
    total_early = 0
    for seed in range(20):
        traced_early = 0

        def tr(e: str, d: Any) -> None:
            nonlocal traced_early
            if e == "trick_end" and d["early"]:
                traced_early += 1

        result = play_game(game, random.Random(seed), tr)
        assert sum(result.scores.values()) == traced_early
        total_early += traced_early
    assert total_early > 0


def test_round_plays_full_tricks_and_conserves_cards() -> None:
    game = check_dsl(SRC, "g.cardlang")
    for seed in range(20):
        plays: list[Any] = []
        tricks: list[Any] = []
        census: dict[str, Any] = {}

        def tr(e: str, d: Any) -> None:
            if e == "play": plays.append(d)  # noqa: B023 -- consumed before the loop advances
            elif e == "trick": tricks.append(d)  # noqa: B023 -- consumed before the loop advances
            elif e == "game_end": census.clear(); census.update(d)  # noqa: B023 -- consumed before the loop advances
        result = play_game(game, random.Random(seed), tr)
        assert len(tricks) == 13 and len(plays) == 52
        assert census["total"] == 52 and census["hands_with_cards"] == 0
        assert sum(result.scores.values()) == 13  # 13 tricks distributed
