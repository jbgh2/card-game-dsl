"""The legal-move engine narrows per rule and honors each rule's `if_impossible`.

Regression guards for two runtime bugs found in review:
- An empty intersection would collapse to the whole hand, wiping out *other*
  active rules — e.g. letting a Hearts leader who does not hold the two of
  clubs lead a heart before hearts are broken.
- An explicit `if_impossible: error(...)` would be ignored; a forced-lead rule
  that cannot be satisfied must reject the move (raise `IllegalMove`).
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime import rules
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.state import Ctx, IllegalMove, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

HEARTS = "docs/games/hearts.cardlang"
# Getaway is the corpus's `if_impossible: error(...)` witness: its opening lead
# is forced to one named card with no fallback.
GETAWAY = "docs/games/getaway.cardlang"


def _ctx(
    game: n.Game, active_names: list[str], led_suit: str | None, hand0: list[Card]
) -> Ctx:
    ri = {r.name: r for r in game.rules}
    active = tuple(ri[name] for name in active_names)
    rs = RuntimeState(Seating(4), ZoneStore(game.zones, tuple(range(4))), random.Random(0))
    rs.mech_state.append({"led_suit": led_suit})
    rs.zones.instance("hand", 0).add_all(hand0)
    return Ctx(rs=rs, chooser=random_chooser(random.Random(0)), active_rules=active)


def test_per_rule_narrowing_survives_a_rule_that_demands_nothing() -> None:
    game = check_source(HEARTS)
    # Leading without the two of clubs: that rule's demand is empty and falls
    # back to the hand, which must NOT re-open the heart the unbroken-hearts
    # rule excludes.
    ctx = _ctx(
        game,
        ["MustLeadTwoOfClubs", "NoLeadingSuitUntilBroken"],
        led_suit=None,
        hand0=[Card("Q", "spades"), Card("A", "hearts"), Card("5", "diamonds")],
    )
    legal = rules.legal_cards(0, "play_to_trick", ctx)
    assert set(legal) == {Card("Q", "spades"), Card("5", "diamonds")}


def test_explicit_if_impossible_error_rejects_the_move() -> None:
    game = check_source(GETAWAY)
    # Leading (led_suit is none) under the forced ace-of-spades rule, but the
    # player does not hold the ace of spades -> the rule's error fires.
    ctx = _ctx(
        game,
        ["MustFollowSuit", "MustLeadAceOfSpadesOnFirstPlay"],
        led_suit=None,
        hand0=[Card("A", "hearts"), Card("5", "diamonds")],
    )
    with pytest.raises(IllegalMove):
        rules.legal_cards(0, "play_to_trick", ctx)


def test_a_forced_lead_rule_is_empty_once_its_card_is_gone() -> None:
    game = check_source(HEARTS)
    # The same leader after the two of clubs has been played: `if_impossible:
    # hand` leaves every later lead to the other rules, here hearts broken.
    ctx = _ctx(
        game,
        ["MustLeadTwoOfClubs"],
        led_suit=None,
        hand0=[Card("A", "hearts"), Card("5", "diamonds")],
    )
    legal = rules.legal_cards(0, "play_to_trick", ctx)
    assert set(legal) == {Card("A", "hearts"), Card("5", "diamonds")}


def test_no_constraint_leaves_the_whole_hand_legal() -> None:
    game = check_source(HEARTS)
    # Following with cards of the led suit: the legal set is exactly those.
    ctx = _ctx(
        game,
        ["MustFollowSuit"],
        led_suit="hearts",
        hand0=[Card("A", "hearts"), Card("3", "hearts"), Card("5", "diamonds")],
    )
    legal = rules.legal_cards(0, "play_to_trick", ctx)
    assert set(legal) == {Card("A", "hearts"), Card("3", "hearts")}
