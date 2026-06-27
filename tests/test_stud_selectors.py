"""Stud's seat-selector stdlib primitives (bring-in and first-to-act).

These are argmin/argmax over players keyed on card ranks/suits — not expressible
in the DSL today — so they are stdlib runtime-primitives called from the betting
phase. The pure ranking logic is unit-tested here against known cards; their
DSL-callability (signature wiring) is checked with a fixture that references both.
"""

from __future__ import annotations

from cardlang.pipeline import check_dsl
from cardlang.runtime.stud import _highest_upcards, _lowest_door
from cardlang.runtime.values import Card


def _c(rank: str, suit: str) -> Card:
    return Card(rank, {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[suit])


def test_lowest_door_picks_lowest_rank_then_lowest_suit() -> None:
    # Players 1 and 2 both show a 5; clubs (2C suit ordinal 0) beats diamonds.
    door = {0: _c("7", "C"), 1: _c("5", "D"), 2: _c("5", "C")}
    assert _lowest_door([0, 1, 2], door) == 2
    # An ace door is the *highest*, never the bring-in.
    door = {0: _c("A", "S"), 1: _c("K", "C"), 2: _c("2", "H")}
    assert _lowest_door([0, 1, 2], door) == 2


def test_highest_upcards_compares_sorted_ranks_lexicographically() -> None:
    # [14] (a lone ace) beats [13, 2] on the first rank; player 1 acts first.
    up = {0: [_c("K", "S"), _c("2", "D")], 1: [_c("A", "C")], 2: [_c("Q", "H"), _c("Q", "S")]}
    assert _highest_upcards([0, 1, 2], up) == 1
    # Equal high card decides on the next: [13,12] beats [13,5].
    up = {0: [_c("K", "S"), _c("Q", "D")], 1: [_c("K", "C"), _c("5", "H")]}
    assert _highest_upcards([0, 1], up) == 0


# Both selectors are nullary stdlib calls returning a Player; the resolver/checker
# must accept them in expression position (the betting phase assigns the result to
# a `leader`/`bringer` state var).
_FIXTURE = """
game G {
  players: 4
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  upcards[player] : PublicHand<player> }
  state { stack[player] : Integer = 100  folded[player] : Boolean = false  leader : Player? = none }
  phase setup {
    leader := bring_in_seat()
    leader := first_to_act_seat()
  }
  winner: highest stack
}
"""


def test_selectors_are_callable_from_the_dsl() -> None:
    game = check_dsl(_FIXTURE, "selectors.cardlang")  # resolves + typechecks the calls
    assert game.name == "G"
