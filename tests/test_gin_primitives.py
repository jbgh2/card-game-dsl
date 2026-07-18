"""Known-value tests for Gin Rummy's stdlib primitives
(cardlang/runtime/gin.py), following the test_cribbage_primitives.py pattern:
the combination machinery — meld validity, the optimal-deadwood partition,
the meld-universe codec — is proven against hands whose values are known by
construction, independent of the ctx-adapter wiring.

The deadwood optimizer is the load-bearing piece: knock legality, the
arrangement guard, and the gin bonus all read it. Its known-value hands pin
the classic trap (a card claimable by both a set and a run must go where the
TOTAL deadwood is minimal, not where a greedy scan puts it).
"""

from __future__ import annotations

import pytest

from cardlang.runtime.gin import (
    GIN_MELD_CODEC,
    card_points,
    flat_points,
    minimal_deadwood,
    valid_meld,
)
from cardlang.runtime.values import Card


def _c(spec: str) -> Card:
    rank, suit = spec[:-1], {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}[spec[-1]]
    return Card(rank, suit)


def _h(*specs: str) -> list[Card]:
    return [_c(s) for s in specs]


def test_card_points() -> None:
    assert card_points(_c("AS")) == 1
    assert card_points(_c("7H")) == 7
    assert card_points(_c("10D")) == 10
    assert card_points(_c("JC")) == 10
    assert card_points(_c("KC")) == 10


def test_valid_melds() -> None:
    assert valid_meld(_h("7C", "7D", "7H"))            # set of 3
    assert valid_meld(_h("7C", "7D", "7H", "7S"))      # set of 4
    assert valid_meld(_h("AC", "2C", "3C"))            # ace-low run
    assert valid_meld(_h("9S", "10S", "JS", "QS", "KS"))  # long run to the king
    assert not valid_meld(_h("QC", "KC", "AC"))        # ace never high
    assert not valid_meld(_h("7C", "7D"))              # too small
    assert not valid_meld(_h("7C", "8D", "9C"))        # mixed-suit "run"
    assert not valid_meld(_h("7C", "8C", "10C"))       # gapped run
    assert not valid_meld(_h("7C", "7D", "7H", "8H"))  # neither shape


def test_minimal_deadwood_known_hands() -> None:
    # One set + one run + four loose cards: K + Q + 4 + 2 = 26.
    assert minimal_deadwood(
        _h("7C", "7D", "7H", "8D", "9D", "10D", "KS", "QH", "4C", "2D")
    ) == 26
    # The set-vs-run overlap: 7♦ can serve the set 7♠7♥7♦ (leaving 8♦9♦ = 17)
    # or the run 7♦8♦9♦ (leaving 7♠7♥ = 14) — the optimum takes the run.
    assert minimal_deadwood(_h("7S", "7H", "7D", "8D", "9D", "KS")) == 24
    # A gin hand: two runs and a set partition all ten cards.
    assert minimal_deadwood(
        _h("AC", "2C", "3C", "4C", "5D", "6D", "7D", "9H", "9S", "9C")
    ) == 0
    # No melds at all: every card is deadwood.
    assert minimal_deadwood(_h("AC", "3D", "5H", "7S")) == 16
    # Empty hand (the gin-after-discard read): zero.
    assert minimal_deadwood([]) == 0


def test_flat_points_is_the_plain_sum() -> None:
    assert flat_points(_h("KS", "QH", "4C")) == 24
    assert flat_points([]) == 0


def test_meld_codec_universe_is_the_329_melds_of_standard52() -> None:
    # Sets: 13 ranks x (C(4,3)+C(4,4)) = 65. Runs: 4 suits x (11+10+...+1)
    # = 264. Total 329 — the closed universe the action encoder sizes by.
    assert GIN_MELD_CODEC.size == 329


def test_meld_codec_round_trips_every_meld() -> None:
    for idx in range(GIN_MELD_CODEC.size):
        cards = frozenset(GIN_MELD_CODEC.decode(idx))
        assert valid_meld(list(cards))
        assert GIN_MELD_CODEC.encode_cards(cards) == idx
        assert GIN_MELD_CODEC.kind_of(idx) in ("set", "run")


def test_meld_codec_rejects_a_non_meld() -> None:
    with pytest.raises(KeyError):
        GIN_MELD_CODEC.encode_cards(frozenset(_h("7C", "8D", "9C")))


def test_gin_primitive_in_a_zone_less_game_fails_typed() -> None:
    """The game-local-primitive precondition wall (one chokepoint for the
    whole class, cribbage included): a primitive reading gin's zones from a
    game without them is a typed RuntimeError naming the situation, never a
    bare KeyError naming only the zone."""
    import random

    from cardlang.runtime.gin import gin_deadwood
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating

    rs = RuntimeState(Seating(2), ZoneStore((), (0, 1)), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))
    with pytest.raises(RuntimeError, match="zone family"):
        gin_deadwood(ctx, 0)


def test_can_knock_quantifies_the_discard_over_the_hand_zone_only() -> None:
    """The 3%-of-seeds crash class (found by a 300-seed adversarial sweep):
    a hand whose ONLY knock-legal discard is the just-taken staging card must
    NOT offer the knock — the knock movement's candidate pool is `hand`, and
    the taken card is never in it (the different-card rule). The witness:
    hand 2♣3♣4♣ + 8♣8♦8♥8♠ + A♠4♥5♥ (every hand discard leaves 15+), taken
    K♦ (discarding IT would leave exactly 10)."""
    import random

    from cardlang.pipeline import check_source
    from cardlang.runtime.gin import gin_can_knock, gin_knock_ok
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating
    from pathlib import Path

    game = check_source(
        Path(__file__).parent.parent / "docs" / "games" / "gin-rummy.cardlang"
    )
    rs = RuntimeState(Seating(2), ZoneStore(game.zones, (0, 1)), random.Random(0))
    hand = _h("2C", "3C", "4C", "8C", "8D", "8H", "8S", "AS", "4H", "5H")
    rs.zones.instance("hand", 0).add_all(hand)
    rs.zones.instance("taken", 0).add_all(_h("KD"))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))

    # The taken K♦ would be a legal knock-discard — but it is not in the pool.
    assert gin_knock_ok(ctx, 0, _c("KD"))
    assert not any(gin_knock_ok(ctx, 0, c) for c in hand)
    # So the announce must not be offered: guard == movement-has-a-candidate.
    assert not gin_can_knock(ctx, 0)
