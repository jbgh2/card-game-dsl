from __future__ import annotations

import random

import cardlang.runtime.state as state
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


def test_phase_outcome_dispatches_to_arm_and_binds_payload() -> None:
    # The phase `settle` produces won(7); the sibling consumer binds amount=7.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase round {
    phase settle -> outcome { won(Integer) | lost } { produce won(7) }
    settle produces:
      won(amount) { for each player p: points[p] += amount }
      lost        { }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 7 and result.scores[1] == 7


def test_continue_to_skips_intermediate_sibling_phase() -> None:
    # `decide` produces go; the arm jumps to `finish`, skipping `middle` (+100).
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase round {
    phase decide -> outcome { go | stop } { produce go }
    decide produces:
      go   { continue to finish }
      stop { }
    phase middle { for each player p: points[p] += 100 }
    phase finish { for each player p: points[p] += 1 }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 1 and result.scores[1] == 1


def test_skip_to_next_hand_aborts_hand_but_runs_after_each() -> None:
    # Each iteration: `decide` produces skipit -> skip aborts `work` (+100), but
    # after_each (+1) still fires. Loop ends when points reach 3.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase rubber repeats until (any player p: points[p] >= 3) {
    after_each { for each player p: points[p] += 1 }
    phase decide -> outcome { skipit | keep } { produce skipit }
    decide produces:
      skipit { skip to next hand }
      keep   { }
    phase work { for each player p: points[p] += 100 }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 3 and result.scores[1] == 3


def test_outcome_survives_an_intervening_repeat_phase() -> None:
    # A producer's outcome must persist across an intervening `repeats until`
    # sibling phase before its consumer runs (regression: an over-eager per-hand
    # clear of phase_outcomes would erase it).
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0  loops : Integer = 0 }
  phase round {
    phase decide -> outcome { val(Integer) } { produce val(7) }
    phase spin repeats until (loops >= 1) {
      before_each { loops := loops + 1 }
    }
    decide produces:
      val(x) { for each player p: points[p] += x }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 7 and result.scores[1] == 7


def test_skip_unwind_does_not_leak_a_frame(monkeypatch) -> None:
    # A leaked frame is behaviourally transparent (empty), so assert frame
    # balance directly: every push_frame on the unwind path is matched by a pop.
    # Fails if run_phase pops outside `finally`.
    counts = {"push": 0, "pop": 0}
    orig_push = state.RuntimeState.push_frame
    orig_pop = state.RuntimeState.pop_frame
    monkeypatch.setattr(
        state.RuntimeState,
        "push_frame",
        lambda self: (counts.__setitem__("push", counts["push"] + 1), orig_push(self))[1],
    )
    monkeypatch.setattr(
        state.RuntimeState,
        "pop_frame",
        lambda self: (counts.__setitem__("pop", counts["pop"] + 1), orig_pop(self))[1],
    )
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase rubber repeats until (any player p: points[p] >= 3) {
    after_each { for each player p: points[p] += 1 }
    phase outer {
      phase decide -> outcome { skipit | keep } { produce skipit }
      decide produces:
        skipit { skip to next hand }
        keep   { }
    }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    play_game(game, random.Random(0))
    assert counts["push"] == counts["pop"]


def test_continue_to_unwinds_through_a_nested_phase() -> None:
    # `continue to finish` fires inside the nested `outer` phase; it must unwind
    # out of outer's run_phase (popping its frame) and resume at `finish`, a
    # sibling of `outer`, skipping `middle`.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase round {
    phase outer {
      phase decide -> outcome { go | stop } { produce go }
      decide produces:
        go   { continue to finish }
        stop { }
    }
    phase middle { for each player p: points[p] += 100 }
    phase finish { for each player p: points[p] += 1 }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 1 and result.scores[1] == 1


def test_skip_to_next_hand_unwinds_through_a_nested_phase() -> None:
    # `skip to next hand` fires inside the nested `outer` phase; it must unwind
    # through outer's run_phase (popping its frame) up to the hand loop, while
    # after_each still runs and `work` (+100) is skipped.
    src = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase rubber repeats until (any player p: points[p] >= 3) {
    after_each { for each player p: points[p] += 1 }
    phase outer {
      phase decide -> outcome { skipit | keep } { produce skipit }
      decide produces:
        skipit { skip to next hand }
        keep   { }
    }
    phase work { for each player p: points[p] += 100 }
  }
  winner: highest points
}
"""
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 3 and result.scores[1] == 3
