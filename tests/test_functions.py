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
