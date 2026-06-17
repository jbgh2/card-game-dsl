"""No implicit actions: kernel decision points fail loudly when nothing is legal.

These pin the "no implicit actions" contract (decisions.md "No implicit actions"):
a decision with no legal move is a malformed game, reported as an error — never a
silent skip or an implicit default. A regression that restored the old silent
no-op would make one of these tests fail.
"""

from __future__ import annotations

import random

import pytest

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
