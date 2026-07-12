"""User-defined named functions (`function name(params) = expr`).

A named, parameterized expression callable anywhere an expression appears, so a
game can factor a predicate it would otherwise repeat. The body is hermetic — it
sees only its parameters and game/phase state (read at call time), never the
caller's binders — and it is validated through every pass: resolve classifies its
names and rejects a body local that is not a parameter (and call cycles), and
typecheck checks call arity and infers the body's type.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang import ast as a
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.resolve import _walk
from cardlang.runtime.driver import play_game

# `ready(player)` factors a predicate used in both `over` and `until`; `busy`
# composes it (function-calls-function).
SRC = """
game G {
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck }
  state { score[player] : Integer = 0  done[player] : Boolean = false }
  phase run {
    round offering [step, stop] from 0 over players where ready(player)
          until (number of players where ready(player)) == 0
  }
  winner: highest score
}
move_type step { effect { score[actor] := score[actor] + 1  done[actor] := true } }
move_type stop { effect { done[actor] := true } }
function ready(p : Player) = not done[p] and not busy(p)
function busy(p : Player)  = score[p] >= 5
"""


def _functions(game: a.nodes.Game) -> dict[str, a.nodes.FunctionDef]:
    return {f.name: f for f in game.functions}


def test_function_def_parses_and_resolves() -> None:
    game = check_dsl(SRC, "fn.cardlang")
    fns = _functions(game)
    assert set(fns) == {"ready", "busy"}
    assert [p.name for p in fns["ready"].params] == ["p"]
    assert fns["ready"].params[0].type_name == "Player"


def test_function_is_callable_at_runtime() -> None:
    game = check_dsl(SRC, "fn.cardlang")
    for seed in range(20):
        result = play_game(game, random.Random(seed))  # must not raise
        assert result.winner in (0, 1, 2)


def test_unknown_function_call_is_rejected() -> None:
    src = SRC.replace("where ready(player)", "where mystery(player)")
    with pytest.raises(DiagnosticError):
        check_dsl(src, "unknown.cardlang")


def test_wrong_arity_is_rejected() -> None:
    src = SRC.replace("where ready(player)", "where ready(player, player)")
    with pytest.raises(DiagnosticError):
        check_dsl(src, "arity.cardlang")


def test_body_local_that_is_not_a_param_is_rejected() -> None:
    # `q` is a binder elsewhere (so the flat classifier tags it `local`) but is not
    # a parameter of `ready` — a compile error, not a runtime KeyError.
    src = SRC.replace(
        "function ready(p : Player) = not done[p] and not busy(p)",
        "function ready(p : Player) = not done[p] and not busy(q)",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "freevar.cardlang")


def test_recursive_function_is_rejected() -> None:
    src = SRC.replace(
        "function busy(p : Player)  = score[p] >= 5",
        "function busy(p : Player)  = busy(p)",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "cycle.cardlang")


def test_function_param_does_not_leak_into_pronoun_sites() -> None:
    # A parameter scopes to its own body only. A function whose parameter is named
    # `actor` must not turn the unrelated `score[actor]` in the move effects into a
    # local lookup: those moves receive `actor` as a pronoun (the acting player),
    # and a leaked classification makes them read a missing local and fail at run.
    src = SRC.replace(
        "function ready(p : Player) = not done[p] and not busy(p)",
        "function lead(actor : Player) = score[actor]\n"
        "function ready(p : Player) = not done[p] and not busy(p)",
    )
    game = check_dsl(src, "shadow.cardlang")
    move_actor_kinds = {
        ref.ref_kind
        for mt in game.move_types
        for ref in _walk(mt)
        if isinstance(ref, a.nodes.NameRef) and ref.name == "actor"
    }
    assert move_actor_kinds == {"pronoun"}, move_actor_kinds
    for seed in range(10):
        play_game(game, random.Random(seed))  # the score[actor] writes must resolve


def test_function_reading_a_call_site_pronoun_is_rejected() -> None:
    # A hermetic body may not read `actor`/`action`/`outcome` — the runtime clears
    # them, so the body would read None. Reject at compile time, not at run time.
    src = SRC.replace(
        "function busy(p : Player)  = score[p] >= 5",
        "function busy(p : Player)  = score[actor] >= 5",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "pronoun-capture.cardlang")


def test_function_shadowing_a_stdlib_call_is_rejected() -> None:
    # A user function may not reuse a stdlib call name: a call would type-check
    # against the stdlib signature but dispatch to the user function at runtime
    # (`evaluate` consults user functions first). Reject the collision.
    src = SRC + "function team_of(p : Player) = score[p] >= 0\n"
    with pytest.raises(DiagnosticError):
        check_dsl(src, "shadow-stdlib.cardlang")


def test_function_call_in_a_move_guard_is_arity_checked() -> None:
    # A `when:` guard is an expression position: a function call in it gets the same
    # arity validation as one in a statement (here `ready` wants one argument).
    src = SRC.replace(
        "move_type stop { effect { done[actor] := true } }",
        "move_type stop { when: ready() effect { done[actor] := true } }",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "guard-arity.cardlang")


# A rule whose `demands` predicate calls a function with the wrong arity: the rule
# expression positions (`applies_when`/`demands`/`if_impossible`) are checked too.
RULE_SRC = """
game G {
  players: 2
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { active_rules: [R]  legal_moves: [play_to_trick] }
  winner: highest score
}
rule R {
  constrains: play_to_trick
  applies_when: always
  demands: hand.where(c => owes())
  if_impossible: hand
}
function owes(p : Player) = score[p] >= 0
"""


def test_function_call_in_a_rule_expression_is_arity_checked() -> None:
    with pytest.raises(DiagnosticError):
        check_dsl(RULE_SRC, "rule-arity.cardlang")


# A function may factor a bare per-player zone; the family instance resolves through
# the acting player the caller set (`current_player` is inherited, not cleared).
ZONE_FN_SRC = """
game G {
  players: 2
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  waste : Discard }
  state { tricks[player] : Integer = 0  leader : Player? = none }
  phase setup {
    shuffle deck
    deal all cards from deck as-equally-as-possible to each hand
    leader := 0
  }
  phase play {
    active_rules: [FollowViaFunction]
    legal_moves: [play_to_trick]
    repeat until (all player p: hand[p] is empty) {
      round play_to_trick from leader over all players source hand into trick_pile
            outcome highest_of_led_suit
      tricks[outcome] += 1
      move all cards from trick_pile to waste
      leader := outcome
    }
  }
  winner: highest tricks
}
rule FollowViaFunction {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: must_follow()
  if_impossible: hand
}
function must_follow() = hand.cards_of_suit(state.led_suit)
"""


def test_function_reading_a_bare_per_player_zone_runs_at_play() -> None:
    # The rule `demands: must_follow()` is evaluated per acting player during
    # legal-card selection; the bare `hand` must resolve to that player's hand
    # rather than asserting on a cleared current player.
    game = check_dsl(ZONE_FN_SRC, "zone-fn.cardlang")
    for seed in range(10):
        play_game(game, random.Random(seed))  # must not raise


def test_function_call_in_a_state_default_is_arity_checked() -> None:
    src = SRC.replace(
        "done[player] : Boolean = false }",
        "done[player] : Boolean = busy() }",
    )
    with pytest.raises(DiagnosticError):
        check_dsl(src, "state-default-arity.cardlang")


# A transition predicate (`where …`) is an expression position; a function call in
# it gets the same arity validation.
TRANSITION_SRC = """
game G {
  players: 2
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase play {
    phase a {
      transition_to: b when play_to_trick where flag()
    }
    phase b { }
  }
  winner: highest score
}
function flag(p : Player) = score[p] >= 0
"""


def test_function_call_in_a_transition_predicate_is_arity_checked() -> None:
    with pytest.raises(DiagnosticError):
        check_dsl(TRANSITION_SRC, "transition-arity.cardlang")


# A derived type-field body is an expression position too.
DERIVED_SRC = """
type R = {
  a : Integer
} derived {
  bad = tag()
}
game G {
  players: 2
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck }
  state { r : R = none  score[player] : Integer = 0 }
  phase p { }
  winner: highest score
}
function tag(p : Player) = p == p
"""


def test_function_call_in_a_derived_field_is_arity_checked() -> None:
    with pytest.raises(DiagnosticError):
        check_dsl(DERIVED_SRC, "derived-arity.cardlang")
