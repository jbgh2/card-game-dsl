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


def test_rejects_backward_continue_to() -> None:
    # `continue to` is forward-only: targeting an earlier sibling is rejected at
    # compile time (it would otherwise re-run the producer forever).
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase early { }
    phase decide -> outcome { back | stay } { produce back }
    decide produces:
      back { continue to early }
      stay { }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "early" in str(ei.value) or "later sibling" in str(ei.value)


def test_rejects_non_sibling_produces_consumer() -> None:
    # `decide produces:` lives in a different branch from the `decide` outcome
    # phase, so the producer never ran in the same pass — reject it statically.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase branch_a {
    phase decide -> outcome { a | b } { produce a }
  }
  phase branch_b {
    decide produces:
      a { score[0] += 1 }
      b { score[0] += 0 }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "decide" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_continue_to_a_top_level_phase() -> None:
    # `play_game` iterates top-level phases with a plain loop (no run_body), so a
    # `continue to` a later top-level phase can't be caught — reject it statically
    # even though top-level phases are siblings for `produces:`.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase first {
    phase decide -> outcome { go | stay } { produce go }
    decide produces:
      go   { continue to second }
      stay { }
  }
  phase second { }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "second" in str(ei.value) or "later sibling" in str(ei.value)


def test_rejects_skip_to_next_hand_in_a_lifecycle_hook() -> None:
    # `run_phase` only catches `_SkipHand` around the phase body, not the hooks, so
    # a skip from before_each/after_each would abort the run — reject it statically.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  n : Integer = 0 }
  phase loop repeats until (n >= 1) {
    before_each { n := n + 1  skip to next hand }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "hook" in str(ei.value)


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
