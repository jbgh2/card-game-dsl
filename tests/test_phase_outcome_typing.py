from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

# A phase declares a variant outcome; a sibling `produces:` consumer dispatches.
EXHAUSTIVE = """
game G {
  players: 2
  max_length: 1000
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
  max_length: 1000
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
  max_length: 1000
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
  max_length: 1000
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
  max_length: 1000
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
    # `round` is not a `repeat until` loop, so there is no hand to skip.
    src = """
game G {
  players: 2
  max_length: 1000
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
  max_length: 1000
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
  max_length: 1000
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
  max_length: 1000
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


def test_produces_consumer_requires_an_earlier_OUTCOME_sibling() -> None:
    # The earlier sibling `decide` is a normal phase (writes no outcome); a global
    # outcome phase of the same name in another branch must not satisfy the scope
    # check — the consumer would fail at runtime with "did not produce".
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase branch {
    phase decide { }
    decide produces:
      a { score[0] += 1 }
      b { score[0] += 0 }
  }
  phase other {
    phase decide -> outcome { a | b } { produce a }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "decide" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_two_consumers_of_one_phase_outcome() -> None:
    # The runtime pops the outcome on the first consumer, so a second `decide
    # produces:` would find nothing — reject it statically.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase decide -> outcome { a | b } { produce a }
    decide produces:
      a { score[0] += 1 }
      b { score[0] += 0 }
    decide produces:
      a { score[0] += 2 }
      b { score[0] += 0 }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "more than one" in str(ei.value) or "decide" in str(ei.value)


def test_rejects_non_sibling_consumer_nested_in_an_arm() -> None:
    # A `produces:` nested in an arm must still obey the earlier-sibling rule: here
    # the nested consumer names `later`, which runs after the enclosing consumer.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase first -> outcome { a | b } { produce a }
    first produces:
      a {
        later produces:
          x { score[0] += 1 }
      }
      b { }
    phase later -> outcome { x } { produce x }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "later" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_validates_exhaustiveness_of_a_consumer_nested_in_an_arm() -> None:
    # A `produces:` nested in an arm is still checked for exhaustiveness: the inner
    # consumer omits `y`.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase first -> outcome { a | b } { produce a }
    phase inner -> outcome { x | y } { produce x }
    first produces:
      a {
        inner produces:
          x { score[0] += 1 }
      }
      b { }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "exhaustive" in str(ei.value) or "y" in str(ei.value)


def test_outer_arm_binder_is_typed_inside_a_nested_consumer() -> None:
    # The outer `got(s)` binder (a Suit) stays in scope inside the nested
    # consumer's arm; assigning it to an Integer state var must be rejected (it
    # was TAny before nested consumers got the arm env).
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase outer -> outcome { got(Suit) } { produce got(hearts) }
    phase inner -> outcome { val(Integer) } { produce val(5) }
    outer produces:
      got(s) {
        inner produces:
          val(n) { score[0] := s }
      }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "score" in str(ei.value) or "Suit" in str(ei.value)


def test_rejects_second_consumer_nested_in_an_arm() -> None:
    # A second consumer of the same phase outcome hidden inside the first's arm is
    # still a double-pop — descend into arm bodies to catch it.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase decide -> outcome { a | b } { produce a }
    decide produces:
      a {
        decide produces:
          a { score[0] += 1 }
          b { score[0] += 0 }
      }
      b { }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "more than one" in str(ei.value) or "decide" in str(ei.value)


def test_rejects_consumer_of_a_when_guarded_producer() -> None:
    # A `when`-guarded producer may not run, so an unconditional consumer can't
    # depend on it.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  flag : Boolean = false }
  phase round {
    phase decide -> outcome { a } when flag { produce a }
    decide produces:
      a { score[0] += 1 }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "decide" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_consumer_of_a_repeating_producer() -> None:
    # A `repeat until` producer may run zero iterations (or not produce on its
    # last), so a later consumer can't depend on it either.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  k : Integer = 0 }
  phase round {
    phase decide -> outcome { a } repeat until (k >= 1) {
      before_each { k := k + 1 }
      produce a
    }
    decide produces:
      a { score[0] += 1 }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "decide" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_consumer_in_a_loop_of_an_outer_producer() -> None:
    # The producer runs once before the loop; a consumer inside the loop would pop
    # it on the first iteration and find nothing on the next. Reject it.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  k : Integer = 0 }
  phase outer_prod -> outcome { val(Integer) } { produce val(5) }
  phase loop repeat until (k >= 2) {
    before_each { k := k + 1 }
    outer_prod produces:
      val(x) { score[0] += x }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "outer_prod" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_consumer_in_a_statement_repeat_of_a_phase_producer() -> None:
    # A phase producer runs once; a consumer under a statement-level `repeat until`
    # would pop it on the first iteration and find nothing afterwards.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  k : Integer = 0 }
  phase round {
    phase decide -> outcome { val(Integer) } { produce val(5) }
    repeat until (k >= 2) {
      k := k + 1
      decide produces:
        val(x) { score[0] += x }
    }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "decide" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_phase_consumer_inside_a_for_each() -> None:
    # `for each` loops, so a run-once phase producer is gone after the first
    # player's dispatch.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase decide -> outcome { val(Integer) } { produce val(5) }
    for each player p:
      decide produces:
        val(x) { score[p] += x }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "decide" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_phase_consumer_in_before_each_hook() -> None:
    # `before_each` runs before the phase body, so a sibling producer has not run
    # yet when the hook's consumer executes.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  k : Integer = 0 }
  phase loop repeat until (k >= 2) {
    phase prod -> outcome { val(Integer) } { produce val(5) }
    before_each {
      k := k + 1
      prod produces:
        val(x) { score[0] += x }
    }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "prod" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_rejects_consumer_of_a_producer_a_jump_can_skip() -> None:
    # `decide` jumps to `tail`, skipping `prod`; a consumer of `prod` after `tail`
    # can't rely on it having run.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase decide -> outcome { go | stay } { produce go }
    decide produces:
      go   { continue to tail }
      stay { }
    phase prod -> outcome { val(Integer) } { produce val(5) }
    phase tail { }
    prod produces:
      val(x) { score[0] += x }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "prod" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_accepts_producer_after_a_phase_with_a_locally_handled_jump() -> None:
    # `inner`'s `continue to b` is handled inside `inner`, so it doesn't skip the
    # later `prod`; a consumer of `prod` is valid.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase round {
    phase inner {
      phase a -> outcome { go | stay } { produce go }
      a produces:
        go   { continue to b }
        stay { }
      phase b { }
    }
    phase prod -> outcome { val(Integer) } { produce val(5) }
    prod produces:
      val(x) { score[0] += x }
  }
  winner: highest score
}
"""
    check_dsl(src, "g.cardlang")  # no raise — prod always runs


def test_rejects_after_each_consumer_of_a_producer_after_a_skip() -> None:
    # `skip to next hand` (in gate's arm) aborts the body before `prod`, but
    # after_each still runs — so it can't consume `prod`.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  k : Integer = 0 }
  phase loop repeat until (k >= 2) {
    before_each { k := k + 1 }
    phase gate -> outcome { skipnow | go } {
      if (k is 1) { produce skipnow } else { produce go }
    }
    gate produces:
      skipnow { skip to next hand }
      go      { }
    phase prod -> outcome { val(Integer) } { produce val(5) }
    after_each {
      prod produces:
        val(x) { score[0] += x }
    }
  }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "prod" in str(ei.value) or "earlier sibling" in str(ei.value)


def test_accepts_after_each_consuming_its_loop_body_producer() -> None:
    # after_each runs after the body on every iteration, so it can consume
    # `prod`, a producer in its own loop body with no skip before it. This is
    # the only place an after_each consumer's producer can live: hooks belong
    # to `repeat until` phases (on any other phase the runtime never runs
    # them, and the checker rejects the combination), and the loop wall keeps
    # outer run-once producers from carrying in.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  k : Integer = 0 }
  phase loop repeat until (k >= 2) {
    before_each { k := k + 1 }
    phase prod -> outcome { val(Integer) } { produce val(5) }
    after_each {
      prod produces:
        val(x) { score[0] += x }
    }
  }
  winner: highest score
}
"""
    check_dsl(src, "g.cardlang")  # no raise — prod reruns each pass before the hook


def test_rejects_outcome_phase_define_name_collision() -> None:
    # An outcome phase named like a define would shadow it in the shared registry
    # and the runtime phase_outcomes dict.
    src = """
define dup -> { x } { produce x }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase dup -> outcome { x } { produce x }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "collides" in str(ei.value) or "dup" in str(ei.value)


def test_rejects_continue_to_in_a_define_body() -> None:
    # Control flow outside a phase body (here a define) would escape play_game.
    src = """
define D -> { go } { produce go  continue to p }
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase p { }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "phase body" in str(ei.value)


def test_rejects_skip_to_next_hand_in_a_lifecycle_hook() -> None:
    # `run_phase` only catches `_SkipHand` around the phase body, not the hooks, so
    # a skip from before_each/after_each would abort the run — reject it statically.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  n : Integer = 0 }
  phase loop repeat until (n >= 1) {
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
  max_length: 1000
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
