"""No implicit actions: kernel decision points fail loudly when nothing is legal.

These pin the "no implicit actions" contract (decisions.md "No implicit actions"):
a decision with no legal move is a malformed game, reported as an error — never a
silent skip or an implicit default. A regression that restored the old silent
no-op would make one of these tests fail.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


def _run(src: str) -> None:
    play_game(check_dsl(src, "t.cardlang"), random.Random(0))


OFFER_NO_LEGAL = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play { for each player p: offer to p one of [never] }
  winner: highest coins
}
move_type never { when: false  effect { coins[actor] += 1 } }
"""


def test_offer_with_no_legal_move_raises() -> None:
    # The only move's guard is always false, so the player has nothing legal —
    # the offer must raise, not silently no-op.
    with pytest.raises(RuntimeError, match="none of.*is legal"):
        _run(OFFER_NO_LEGAL)


CHOOSE_EMPTY_RANGE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { x[player] : Integer = 0 }
  phase play { for each player p: x[p] := choose integer in 5 .. 2 }
  winner: highest x
}
"""


def test_choose_over_empty_range_raises() -> None:
    # An inverted range offers no candidate — `choose` must raise, not pick a
    # silent default.
    with pytest.raises(RuntimeError, match="empty range"):
        _run(CHOOSE_EMPTY_RANGE)


RULE_WITHOUT_IF_IMPOSSIBLE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { x[player] : Integer = 0 }
  phase play { }
  winner: highest x
}
rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
}
"""


def test_card_set_demand_without_if_impossible_is_rejected() -> None:
    # A card-set demand can filter the legal set to empty; the rule must declare
    # its `if_impossible` fallback at compile time rather than rely on a silent
    # default. This catches the gap statically, not only when a void state runs.
    with pytest.raises(DiagnosticError, match="no `if_impossible`"):
        check_dsl(RULE_WITHOUT_IF_IMPOSSIBLE, "t.cardlang")


TRICK_ROUND_WITH_AUCTION_OUTCOME = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { leader : Player? = none }
  phase play {
    leader := 0
    round play_to_trick from leader over all players source hand into trick_pile
          outcome bridge_auction_outcome
  }
  winner: highest leader
}
"""


AUCTION_ROUND_WITH_TRICK_OUTCOME = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { passes : Integer = 0 }
  phase bid {
    round offering [pass] from 0 over all players until (passes >= 2)
          outcome highest_trump_or_led_suit
  }
  winner: highest passes
}
move_type pass { effect { passes += 1 } }
"""


def test_trick_round_rejects_an_auction_outcome() -> None:
    # A trick round whose outcome names an auction-form callback resolves to the
    # wrong dispatcher at runtime — reject it at compile time, by form-specific
    # outcome namespace, not with a late AssertionError.
    with pytest.raises(DiagnosticError, match="not a trick outcome function"):
        check_dsl(TRICK_ROUND_WITH_AUCTION_OUTCOME, "t.cardlang")


def test_auction_round_rejects_a_trick_outcome() -> None:
    with pytest.raises(DiagnosticError, match="not an auction outcome function"):
        check_dsl(AUCTION_ROUND_WITH_TRICK_OUTCOME, "t.cardlang")


AUCTION_NON_BOOLEAN_UNTIL = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { passes : Integer = 0 }
  phase bid {
    round offering [pass] from 0 over all players until 1
          outcome bridge_auction_outcome
  }
  winner: highest passes
}
move_type pass { effect { passes += 1 } }
"""


def test_auction_until_must_be_boolean() -> None:
    # The `until` termination is a predicate; a non-Boolean (here Integer `1`)
    # would silently fall back to Python truthiness at runtime, so it is a
    # type error.
    with pytest.raises(DiagnosticError, match="`until` condition must be Boolean"):
        check_dsl(AUCTION_NON_BOOLEAN_UNTIL, "t.cardlang")


PARAM_NAME_COLLIDES_WITH_STATE = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { strain : Integer = 0  done[player] : Integer = 0 }
  phase play {
    for each player p: offer to p one of [pick]
    for each player p: done[p] := strain + 1
  }
  winner: highest done
}
move_type pick(strain : Suit?) { when: always  effect { } }
"""


def test_move_param_does_not_shadow_a_same_named_state_var() -> None:
    # A move parameter binds only in its own guard/effect. A same-named state var
    # read elsewhere (`strain` here) must still resolve as state — not be captured
    # as the move's local and read from an empty `ctx.locals` at runtime.
    result = play_game(check_dsl(PARAM_NAME_COLLIDES_WITH_STATE, "t.cardlang"), random.Random(0))
    assert result.winner in (0, 1)
