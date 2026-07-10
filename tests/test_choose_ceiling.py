"""The static ceiling of an integer `choose` (decisions.md "The integer
`choose` domain").

Every `choose integer in lo .. hi` must have a statically known, non-negative
upper bound — its own literal `hi`, or an explicit `up to N` clause when `hi` is
a runtime expression. That ceiling sizes the OpenSpiel integer action block and
is enforced as a live-range guard at runtime; a range that escapes it would
offer a legal value with no action id.
"""

from __future__ import annotations

import random
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Iterator

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _walk(node: object) -> Iterator[object]:
    if is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


def _only_choose(game: n.Game) -> n.Choose:
    chooses = [nd for nd in _walk(game) if isinstance(nd, n.Choose)]
    assert len(chooses) == 1
    return chooses[0]


def _game(body_state: str, choose: str) -> str:
    return f"""
game G {{
  players: 2
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ {body_state} }}
  phase play {{ for each player p: x[p] := {choose} }}
  winner: highest x
}}
"""


def test_literal_hi_is_its_own_ceiling() -> None:
    # A literal upper bound needs no `up to`: it IS the static ceiling.
    game = check_dsl(_game("x[player] : Integer = 0", "choose integer in 0 .. 13"), "t")
    choose = _only_choose(game)
    assert choose.ceiling is None
    assert n.static_ceiling(choose) == 13


def test_up_to_clause_declares_the_ceiling() -> None:
    game = check_dsl(
        _game("n : Integer = 3  x[player] : Integer = 0", "choose integer in 0 .. n up to 10"),
        "t",
    )
    choose = _only_choose(game)
    assert choose.ceiling == 10
    assert n.static_ceiling(choose) == 10


def test_runtime_hi_without_up_to_is_rejected() -> None:
    # A runtime upper bound (`n`) with no declared ceiling cannot be sized into
    # the fixed OpenSpiel action space — rejected at resolve, not papered over.
    with pytest.raises(DiagnosticError, match="statically known upper bound"):
        check_dsl(
            _game("n : Integer = 3  x[player] : Integer = 0", "choose integer in 0 .. n"),
            "t",
        )


def test_live_range_exceeding_ceiling_raises() -> None:
    # `n` is 15 at runtime but the declared ceiling is 10: the live range
    # escaped its domain and would offer values 11..15 with no action id. The
    # guard is on the RANGE, so it fires regardless of which value is drawn —
    # the failure a value-only check would miss whenever the draw is small.
    src = _game("n : Integer = 15  x[player] : Integer = 0", "choose integer in 0 .. n up to 10")
    with pytest.raises(RuntimeError, match="escaped its declared domain"):
        play_game(check_dsl(src, "t"), random.Random(0))


def test_computed_hi_is_not_treated_as_static() -> None:
    # Only a bare literal `hi` (or `up to N`) counts as static — a computed
    # expression, even over literals, yields no ceiling and is rejected. Keeps
    # the static-bound rule simple: no constant folding to reason about.
    with pytest.raises(DiagnosticError, match="statically known upper bound"):
        check_dsl(
            _game("x[player] : Integer = 0", "choose integer in 0 .. (13 - 1)"),
            "t",
        )


def test_action_space_sizes_to_the_declared_ceiling() -> None:
    # Oh Hell's `0 .. hand_size up to 10` reserves ids 0..10 (11), not a
    # deck-sized 53 — num_distinct reflects the declared bound.
    space = ActionSpace.for_game(check_source(GAMES / "oh-hell.cardlang"))
    assert space._int_ceiling == 10
    assert space.decode(space.encode(10)) == 10
    with pytest.raises(AssertionError):
        space.encode(11)  # beyond the reserved block


def test_action_space_takes_the_largest_ceiling() -> None:
    # Two chooses of different ceilings share one block sized to the larger.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { x[player] : Integer = 0  y[player] : Integer = 0 }
  phase a { for each player p: x[p] := choose integer in 0 .. 4 }
  phase b { for each player p: y[p] := choose integer in 0 .. 12 }
  winner: highest x
}
"""
    space = ActionSpace.for_game(check_dsl(src, "t"))
    assert space._int_ceiling == 12
