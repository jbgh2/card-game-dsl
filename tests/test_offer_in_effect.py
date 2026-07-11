"""Pin: an `offer` statement inside a `move_type` effect is legal and
announced — the construct combination Task 3's Coup window pattern (challenge
/ block / claim polls nested inside an action's effect) depends on. Per
docs/superpowers/specs/2026-07-10-ws5-coup-interactive-windows-design.md,
"Architecture decision": the runtime's `_offer` recurses through the same
statement executor (`run_body`), so a nested offer's inner decision runs with
the offered player bound as actor, not the outer actor.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

SRC = """
game OfferInEffect {
  players: 2
  direction: clockwise
  max_length: 100
  cards: standard52

  zones {
    deck : Deck
  }

  state {
    outer_ran     : Boolean = false
    flag          : Boolean = false
    score[player] : Integer = 0
  }

  phase play {
    offer to 0 one of [outer]
  }

  winner: highest score
}

move_type outer {
  effect {
    outer_ran := true
    score[0] := 1
    offer to 1 one of [inner_yes, inner_no]
  }
}
move_type inner_yes {
  effect {
    flag := true
    score[1] := 1
  }
}
move_type inner_no  { effect { } }
"""


def _pick_first(player: int, candidates: list[Any], k: int) -> list[Any]:
    """A scripted chooser: always take the vocabulary's first candidate — index
    0 at both the outer offer (picks `outer`) and the inner offer (picks
    `inner_yes`, listed first in `[inner_yes, inner_no]`)."""
    return list(candidates[:k])


def test_offer_in_effect_runs_the_inner_decision_with_the_offered_actor() -> None:
    game = check_dsl(SRC, "offer_in_effect.cardlang")
    logs: dict[int, list[tuple[Any, ...]]] = {0: [], 1: []}
    result = play_game(
        game,
        random.Random(0),
        chooser=_pick_first,
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    assert result is not None  # the game completed (no exception, no hang)
    # `outer`'s effect runs its own `outer_ran := true` (a statement BEFORE the
    # nested offer) and `inner_yes`'s effect runs `flag := true` — each move
    # type mirrors its state-var write into `score` in the same statement, so
    # a nonzero score is direct proof the write executed (not just that the
    # decision was announced).
    assert result.scores == {0: 1, 1: 1}

    announces = [e for p in (0, 1) for e in logs[p] if e[0] == "announce"]
    outer_announces = {e for e in announces if e[1:] == (0, "outer")}
    inner_announces = {e for e in announces if e[1:] == (1, "inner_yes")}
    # Both decisions announce publicly — every player's log carries both.
    for player in (0, 1):
        assert ("announce", 0, "outer") in logs[player]
        assert ("announce", 1, "inner_yes") in logs[player]
    assert outer_announces and inner_announces

    # The inner actor is the OFFERED player (1), not the outer actor (0):
    # only player 1 sees a "chose" for the inner pick.
    chose_inner = [e for e in logs[1] if e == ("chose", "inner_yes")]
    assert chose_inner
    assert ("chose", "inner_yes") not in logs[0]
    # Symmetrically, only player 0 sees a "chose" for the outer pick.
    assert ("chose", "outer") in logs[0]
    assert ("chose", "outer") not in logs[1]
