from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

# A phase declares a variant outcome; a sibling `produces:` consumer dispatches.
EXHAUSTIVE = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0  trump_suit : Suit? = none }
  phase round {
    phase declare -> outcome { trump_declared(Suit) | bid_abandoned } {
      produce bid_abandoned
    }
    declare produces:
      trump_declared(t) { trump_suit := t }
      bid_abandoned     { trump_suit := none }
  }
  winner: highest points
}
"""


def test_accepts_exhaustive_phase_outcome() -> None:
    check_dsl(EXHAUSTIVE, "g.cardlang")  # no raise


def test_rejects_non_exhaustive_phase_match() -> None:
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { trump_suit : Suit? = none  score[player] : Integer = 0 }
  phase round {
    phase declare -> outcome { trump_declared(Suit) | bid_abandoned } {
      produce bid_abandoned
    }
    declare produces:
      trump_declared(t) { trump_suit := t }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "exhaustive" in str(ei.value) or "bid_abandoned" in str(ei.value)


def test_rejects_unknown_variant_in_phase_match() -> None:
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { trump_suit : Suit? = none  score[player] : Integer = 0 }
  phase round {
    phase declare -> outcome { trump_declared(Suit) | bid_abandoned } {
      produce bid_abandoned
    }
    declare produces:
      trump_declared(t) { trump_suit := t }
      bid_abandoned     { trump_suit := none }
      drew              { trump_suit := none }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "drew" in str(ei.value) or "unknown variant" in str(ei.value)


def test_rejects_wrong_payload_type_in_phase_produce() -> None:
    # `produce trump_declared(7)` — an Integer where the case declares Suit.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { trump_suit : Suit? = none  score[player] : Integer = 0 }
  phase round {
    phase declare -> outcome { trump_declared(Suit) | bid_abandoned } {
      produce trump_declared(7)
    }
    declare produces:
      trump_declared(t) { trump_suit := t }
      bid_abandoned     { trump_suit := none }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "trump_declared" in str(ei.value) or "Suit" in str(ei.value)


def test_rejects_continue_to_unknown_phase() -> None:
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase declare -> outcome { made | quit } { produce made }
    declare produces:
      made { continue to nowhere }
      quit { }
    phase play { }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "nowhere" in str(ei.value) or "continue to" in str(ei.value)


def test_rejects_skip_to_next_hand_outside_a_hand_loop() -> None:
    # `round` is not a `repeats until` loop, so there is no hand to skip.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase declare -> outcome { made | quit } { produce quit }
    declare produces:
      made { }
      quit { skip to next hand }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "skip to next hand" in str(ei.value) or "hand loop" in str(ei.value)


def test_rejects_produce_inside_a_produces_arm() -> None:
    # A bare `produce` belongs in a define/outcome-phase body, not a consumer arm.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase decide -> outcome { a | b } { produce a }
    decide produces:
      a { produce b }
      b { }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "produces: arm" in str(ei.value) or "may not appear" in str(ei.value)
