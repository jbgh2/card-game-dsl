"""The `Card` move-parameter domain (the first state-dependent domain).

A Card-parameterized move in an auction `round offering` enumerates the ACTING
player's live hand, in hand order — not a static deck-order enumeration
filtered to the hand, which would reorder the candidate list and shift the
chooser draw (card plays are offered in hand order, like every other card-play
form). The domain set is closed at resolve time (decisions.md "Surface
totality"): `Suit`/`Suit?`/`Rank`/`Player` (static) and `Card` (the live hand)
are enumerable, and `Card` only as a move's sole parameter (`resolve.py`'s
shared `_check_move_params`, exercised end to end for the closed set in
tests/test_resolve_param_domains.py); anything else is rejected rather than
left to crash `enumerate_domain` mid-playout.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

# A single-participant ring: player 0 either plays a specific hand card (the
# Card-parameterized move, which ends the round) or stops. The hand is dealt
# unshuffled, so its contents are the deck's top five in deck order.
CARD_PARAM_SRC = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state {
    done : Boolean = false
    marker[player] : Integer = 0
  }
  phase root {
    deal 5 cards from deck to each hand
    round offering [play_one, stop] from 0
          over players where player is 0
          until done
  }
  winner: highest marker
}
move_type play_one(c : Card) {
  effect {
    move one card from hand[actor] where card is c to pile
    done := true
  }
}
move_type stop { effect { done := true } }
"""


def test_card_param_enumerates_the_live_hand_in_hand_order() -> None:
    game = check_dsl(CARD_PARAM_SRC, "g.cardlang")
    hand_at_decision: list[Card] = []
    offered: list[list[Any]] = []

    def snapshot(rs: Any) -> None:
        hand_at_decision.extend(rs.zones.instance("hand", 0).cards)

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        offered.append(list(candidates))
        return [candidates[2]]  # a mid-hand play_one, so order is exercised

    play_game(game, random.Random(0), chooser=chooser, on_first_decision=snapshot)

    assert len(offered) == 1
    expected = [("play_one", c) for c in hand_at_decision] + [("stop", None)]
    assert offered[0] == expected, f"candidates {offered[0]} != hand order {expected}"


def test_card_param_effect_moves_the_chosen_card() -> None:
    game = check_dsl(CARD_PARAM_SRC, "g.cardlang")
    chosen: list[Any] = []

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        chosen.append(candidates[2])
        return [candidates[2]]

    def snapshot(rs: Any) -> None:
        snapshot.rs = rs  # type: ignore[attr-defined]

    play_game(game, random.Random(0), chooser=chooser, on_first_decision=snapshot)

    rs = snapshot.rs  # type: ignore[attr-defined]
    (_, card) = chosen[0]
    assert rs.zones.single("pile").cards == [card]
    assert card not in rs.zones.instance("hand", 0).cards


GUARDED_SRC = CARD_PARAM_SRC.replace(
    "move_type play_one(c : Card) {\n  effect {",
    'move_type play_one(c : Card) {\n  when: c.rank is "4"\n  effect {',
)


def test_card_param_guard_filters_the_hand() -> None:
    # Unshuffled, player 0's hand is 2..6 of clubs; the rank guard keeps one.
    game = check_dsl(GUARDED_SRC, "g.cardlang")
    offered: list[list[Any]] = []

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        offered.append(list(candidates))
        return [candidates[0]]

    play_game(game, random.Random(0), chooser=chooser)

    assert offered[0] == [("play_one", Card("4", "clubs")), ("stop", None)]


# --- the closed domain set: everything else is rejected at resolve time ------


def _rejects(src: str, *needles: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    msg = str(ei.value)
    assert any(needle in msg for needle in needles), msg


def test_rejects_a_non_enumerable_param_domain_in_a_round_vocabulary() -> None:
    # Bounded-Integer parameter domains are deferred, not silently ignored —
    # see tests/test_resolve_param_domains.py for the full closed-set gate.
    _rejects(
        CARD_PARAM_SRC.replace("play_one(c : Card)", "play_one(c : Integer)"),
        "bounded-Integer parameter domains are deferred",
    )


def test_rejects_an_optional_card_param_domain() -> None:
    # `Card?` parses (payload types are optional-able) but has no enumeration:
    # a hand holds cards, never `none`.
    _rejects(
        CARD_PARAM_SRC.replace("play_one(c : Card)", "play_one(c : Card?)"),
        "unsupported parameter domain 'Card?'",
    )


def test_rejects_two_card_parameterized_moves_in_one_vocabulary() -> None:
    src = CARD_PARAM_SRC.replace(
        "round offering [play_one, stop]", "round offering [play_one, play_two, stop]"
    ).replace(
        "move_type stop { effect { done := true } }",
        "move_type stop { effect { done := true } }\n"
        "move_type play_two(c : Card) { effect { done := true } }",
    )
    _rejects(src, "more than one Card-parameterized move")


def test_rejects_a_card_param_without_a_hand_zone() -> None:
    src = CARD_PARAM_SRC.replace(
        "zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }",
        "zones { deck : Deck  stash[player] : Hand<player>  pile : TrickPile }",
    ).replace(
        "deal 5 cards from deck to each hand", "deal 5 cards from deck to each stash"
    ).replace(
        "move one card from hand[actor] where card is c to pile", "done := true"
    )
    _rejects(src, "enumerates the actor's `hand[player]` zone")
