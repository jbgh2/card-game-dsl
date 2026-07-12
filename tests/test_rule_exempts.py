"""The rule `exempts:` clause: cards an applicable rule exempts sit outside the
`legal_cards` demand cascade entirely — never narrowed by it, never counted
toward satisfying it — and are appended after every other legal card, in hand
order, regardless of where they sit in the hand (French Tarot's Excuse: always
playable, never bound by follow-suit/trump obligations, offered last — the
monolith's `base + excuse` candidate order the RNG stream depends on).

A game that declares no `exempts` rule must see this codepath as a no-op: the
existing test_legal_cards.py cases (unchanged by this commit) are that proof.
These tests exercise the exempt mechanics specifically, with a small fixture
game whose "joker" (rank "2") is exempt from following suit — the same shape
as Tarot's Excuse, one level simpler (a standard52 deck, no trump).
"""

from __future__ import annotations

import random

from cardlang.pipeline import check_dsl
from cardlang.runtime import rules
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

SRC = """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase p {
    active_rules: [MustFollowSuit, JokerIsExempt]
    legal_moves:  [play_to_trick]
  }
  winner: highest score
}

rule JokerIsExempt {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  exempts: cards in hand where card.rank is "2"
}
"""

JOKER_CLUBS = Card("2", "clubs")


def _ctx(led_suit: str | None, hand0: list[Card]) -> Ctx:
    game = check_dsl(SRC, "mini.cardlang")
    ri = {r.name: r for r in game.rules}
    active = tuple(ri[name] for name in ("MustFollowSuit", "JokerIsExempt"))
    rs = RuntimeState(Seating(2), ZoneStore(game.zones, (0, 1)), random.Random(0))
    rs.mech_state.append({"led_suit": led_suit})
    rs.zones.instance("hand", 0).add_all(hand0)
    return Ctx(rs=rs, chooser=random_chooser(random.Random(0)), active_rules=active)


def test_exempt_card_is_appended_last_regardless_of_hand_position() -> None:
    # The joker sits FIRST in hand, ahead of a card that follows the led suit —
    # the follower must still come first in the result, joker last.
    hand = [JOKER_CLUBS, Card("5", "hearts"), Card("K", "clubs")]
    legal = rules.legal_cards(0, "play_to_trick", _ctx("hearts", hand))
    assert legal == [Card("5", "hearts"), JOKER_CLUBS]


def test_exempt_card_does_not_satisfy_the_demand_it_would_structurally_match() -> None:
    # Led suit is clubs; the joker IS a club, but being exempt it must not
    # count as a follow — the follow-suit demand sees only the non-exempt K.
    hand = [JOKER_CLUBS, Card("K", "clubs"), Card("5", "hearts")]
    legal = rules.legal_cards(0, "play_to_trick", _ctx("clubs", hand))
    assert legal == [Card("K", "clubs"), JOKER_CLUBS]


def test_void_in_led_suit_falls_back_to_if_impossible_with_exempt_still_last() -> None:
    # No non-exempt club to follow with (void in the led suit once the joker is
    # set aside) -> if_impossible: hand admits the whole (non-exempt) working
    # set; the joker still appends last, never blocking the fallback.
    hand = [JOKER_CLUBS, Card("5", "hearts"), Card("9", "spades")]
    legal = rules.legal_cards(0, "play_to_trick", _ctx("clubs", hand))
    assert legal == [Card("5", "hearts"), Card("9", "spades"), JOKER_CLUBS]


def test_exempt_only_hand_returns_just_the_exempt_card() -> None:
    hand = [JOKER_CLUBS]
    legal = rules.legal_cards(0, "play_to_trick", _ctx("hearts", hand))
    assert legal == [JOKER_CLUBS]


def test_exempt_rule_inapplicable_leaves_the_card_in_its_natural_position() -> None:
    # `applies_when: state.led_suit is not none` is false while leading (no
    # led suit yet) -> the exempt rule does not fire at all, so the joker
    # stays in its ordinary hand-order slot (Tarot's "leader sees the full,
    # unreordered hand" case).
    hand = [Card("K", "clubs"), JOKER_CLUBS, Card("5", "hearts")]
    legal = rules.legal_cards(0, "play_to_trick", _ctx(None, hand))
    assert legal == hand
