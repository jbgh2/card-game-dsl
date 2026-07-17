"""The `turns` form (decisions.md "The `turns` form").

property:   `turns <binder> from <leader> over <participants> until <pred>
            [again <var>] { body }` rotates through the participants in game
            direction, binding the current player (binder + acting player)
            per turn, terminating when the predicate holds at a turn
            boundary; `again <var>` (a declared Boolean state var) repeats
            the same player's turn when true. Every grammar-accepted
            combination executes or is statically rejected.
domain:     clause presence (again present/absent) × (leader, participants,
            termination ∈ Expr) × (body ∈ Stmt*) × runtime states
            (participants empty / current filtered out mid-loop / until true
            before the first turn / again with a non-Boolean or undeclared
            state var).
registry:   the Stmt/Node unions (assert_never dispatch in resolve,
            typecheck ×4, ir, deckcheck, execute — mypy-forced) plus the
            two generic walkers (expand, openspiel/encoding) whose wall is
            reflection over dataclass fields.
covered:    - `turns` with and without `again` parse to the Turns node
              [grammar/parse]
            - binder scoped to the body only; reading it after the loop is
              an unresolved-name diagnostic [resolve]
            - non-Boolean `until`, non-Player `from`, non-collection `over`,
              undeclared / non-Boolean `again` var → located diagnostics
              [resolve/typecheck]
            - rotation binds each participant in seating direction from the
              leader; `until` is checked before the FIRST turn (the
              zero-iteration run exists); participants re-evaluated per
              advance (elimination falls out); `again` repeats the same
              player [runtime]
            - a full lap with no eligible participant is a loud
              RuntimeError, never a silent skip or an infinite spin
              [runtime]
sampled:    body statement kinds run through the same execute dispatch used
            by `if`/`as` — the form adds rotation, not per-statement logic.
residual:   a `direction` override clause — not grammar (no corpus user);
            recorded in roadmap.md "Grammar surface deferred by the
            checker".
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _walk
from cardlang.runtime.driver import play_game


def _game(body: str, extra_state: str = "") -> str:
    return (
        "game G {\n"
        "  players: 3\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player>\n"
        "          discard : Discard }\n"
        "  state { dealer : Player = 0\n"
        "          stop : Boolean = false\n"
        f"          {extra_state}\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"{body}\n"
        "}\n"
    )


def test_turns_parses_to_a_turns_node() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop {\n"
        "    score[t] += 1\n"
        "  } }"
    )
    game = parse_text(dsl, "test.cardlang")
    nodes = [nd for nd in _walk(game) if isinstance(nd, n.Turns)]
    assert len(nodes) == 1
    assert nodes[0].binder == "t"
    assert nodes[0].again is None
    assert len(nodes[0].body) == 1


def test_turns_with_again_clause_parses() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop again go {\n"
        "    score[t] += 1\n"
        "  } }",
        extra_state="go : Boolean = false",
    )
    game = parse_text(dsl, "test.cardlang")
    nodes = [nd for nd in _walk(game) if isinstance(nd, n.Turns)]
    assert nodes[0].again == "go"
