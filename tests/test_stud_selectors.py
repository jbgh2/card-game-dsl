"""Stud's seat-selector Primitives (bring-in, best-showing, first-to-act).

These are argmin/argmax over players keyed on card ranks/suits — not expressible
in the DSL today — so they are Primitives called from the betting
phase. The pure ranking logic is unit-tested here against known cards; their
DSL-callability (signature wiring) is checked with a fixture that declares and
calls each.

`_best_showing` and `_highest_upcards` answer the same question in two orders,
and the cases below are written so a reader can see them apart: the first is
Stud's rule (multiplicity ahead of card value), the second compares card values
one at a time. Issue #636 owns collapsing them.
"""

from __future__ import annotations

from cardlang.pipeline import check_dsl
from cardlang.runtime.stud import _best_showing, _highest_upcards, _lowest_door
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


def test_best_showing_ranks_multiplicity_ahead_of_card_value() -> None:
    # Pagat's own worked example, three cards showing: "3-3-3 is higher than
    # 7-7-8, which is higher than A-K-Q."
    trips = [_c("3", "C"), _c("3", "D"), _c("3", "H")]
    pair = [_c("7", "C"), _c("7", "D"), _c("8", "H")]
    high = [_c("A", "C"), _c("K", "D"), _c("Q", "H")]
    assert _best_showing([0, 1, 2], {0: high, 1: pair, 2: trips}) == 2
    assert _best_showing([0, 1], {0: high, 1: pair}) == 1
    # The other order reads the same three boards the other way round.
    assert _highest_upcards([0, 1, 2], {0: high, 1: pair, 2: trips}) == 0


def test_best_showing_orders_every_class_multiplicity_can_show() -> None:
    # Four cards showing: quads > trips > two pair > pair > high card, whatever
    # the card values under them say.
    quads = [_c("2", "C"), _c("2", "D"), _c("2", "H"), _c("2", "S")]
    trips = [_c("3", "C"), _c("3", "D"), _c("3", "H"), _c("4", "S")]
    two_pair = [_c("5", "C"), _c("5", "D"), _c("6", "H"), _c("6", "S")]
    pair = [_c("7", "C"), _c("7", "D"), _c("8", "H"), _c("9", "S")]
    high = [_c("A", "C"), _c("K", "D"), _c("Q", "H"), _c("J", "S")]
    boards = {0: high, 1: pair, 2: two_pair, 3: trips, 4: quads}
    for better, worse in ((4, 3), (3, 2), (2, 1), (1, 0)):
        assert _best_showing([better, worse], boards) == better
    # Transitively, the whole field: the quads seat opens against all of them.
    assert _best_showing(sorted(boards), boards) == 4


def test_best_showing_does_not_count_incomplete_straights_or_flushes() -> None:
    # "Incomplete straights and flushes do not count": four to a straight flush
    # is a high-card board, and the lowest possible pair outranks it.
    straight_flush_draw = [_c("9", "H"), _c("8", "H"), _c("7", "H"), _c("6", "H")]
    lowest_pair = [_c("2", "C"), _c("2", "D"), _c("3", "H"), _c("4", "S")]
    assert _best_showing([0, 1], {0: straight_flush_draw, 1: lowest_pair}) == 1


def test_best_showing_breaks_a_tie_on_the_suit_of_the_highest_card() -> None:
    # Same ranks in both hands, so the suits of the highest card decide, on
    # clubs (low), diamonds, hearts, spades (high).
    assert _best_showing(
        [0, 1],
        {0: [_c("K", "C"), _c("4", "S")], 1: [_c("K", "S"), _c("4", "C")]},
    ) == 1
    # The tie-break reads the HIGHEST card's suit, not the whole board's best
    # suit: seat 0 holds the only spade and still loses on the king.
    assert _best_showing(
        [0, 1],
        {0: [_c("K", "D"), _c("4", "S")], 1: [_c("K", "H"), _c("4", "D")]},
    ) == 1


# All three selectors are nullary native calls returning a Player; the resolver/checker
# must accept them in expression position (the betting phase assigns the result to
# a `leader`/`bringer` state var). A declaration is their only route to Python, so
# the fixture writes the block; its reads are the ones the implementations consult,
# declared here at game level because this probe has no betting phase to declare
# them in.
_FIXTURE = """
game G {
  players: 4
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  primitives {
    bring_in_seat() : Player reads stack, upcards
    best_showing_seat() : Player reads stack, folded, upcards
    first_to_act_seat() : Player reads stack, folded, upcards
  }
  zones { deck : Deck  upcards[player] : PublicHand<player> }
  state { stack[player] : Integer = 100  folded[player] : Boolean = false  leader : Player? = none }
  phase setup {
    leader := bring_in_seat()
    leader := best_showing_seat()
    leader := first_to_act_seat()
  }
  winner: highest stack
}
"""


def test_selectors_are_callable_from_the_dsl() -> None:
    game = check_dsl(_FIXTURE, "selectors.cardlang")  # resolves + typechecks the calls
    assert game.name == "G"
