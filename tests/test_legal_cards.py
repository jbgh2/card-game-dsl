"""The legal-move engine narrows per rule and honors each rule's `if_impossible`.

Regression guards for two runtime bugs found in review:
- An empty intersection would collapse to the whole hand, wiping out *other*
  active rules — e.g. letting a Hearts player void in the led suit dump penalty
  cards on the first trick even while holding a safe off-suit card.
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


def _ctx(
    game: n.Game, active_names: list[str], led_suit: str | None, hand0: list[Card]
) -> Ctx:
    ri = {r.name: r for r in game.rules}
    active = tuple(ri[name] for name in active_names)
    rs = RuntimeState(Seating(4), ZoneStore(game.zones, tuple(range(4))), random.Random(0))
    rs.mech_state.append({"led_suit": led_suit})
    rs.zones.instance("hand", 0).add_all(hand0)
    return Ctx(rs=rs, chooser=random_chooser(random.Random(0)), active_rules=active)


def test_per_rule_narrowing_excludes_penalty_cards_on_first_trick() -> None:
    game = check_source(HEARTS)
    # Player is void in the led suit (clubs) but holds a safe diamond. The empty
    # follow-suit set must NOT re-open penalty cards (Q of spades, hearts).
    ctx = _ctx(
        game,
        ["MustFollowSuit", "NoPenaltyCardsOnFirstTrick"],
        led_suit="clubs",
        hand0=[Card("Q", "spades"), Card("A", "hearts"), Card("5", "diamonds")],
    )
    legal = rules.legal_cards(0, "play_to_trick", ctx)
    assert legal == [Card("5", "diamonds")]


def test_explicit_if_impossible_error_rejects_the_move() -> None:
    game = check_source(HEARTS)
    # Leading (led_suit is none) under the forced two-of-clubs rule, but the
    # player does not hold the two of clubs -> the rule's error fires.
    ctx = _ctx(
        game,
        ["MustFollowSuit", "MustLeadTwoOfClubsOnFirstPlay"],
        led_suit=None,
        hand0=[Card("A", "hearts"), Card("5", "diamonds")],
    )
    with pytest.raises(IllegalMove):
        rules.legal_cards(0, "play_to_trick", ctx)


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
