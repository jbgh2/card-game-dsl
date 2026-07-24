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
covered:    - `turns` with and without `again` parse to the Turns node;
              fused keyword typos (`turnst`, `againgo`) are loud syntax
              errors (anchored `_TURNS_KW`/`_AGAIN_KW`) [grammar/parse]
            - binder scoped to the body only; reading it after the loop is
              an unresolved-name diagnostic [resolve]
            - non-Boolean `until`, non-Player `from`, non-collection `over`,
              undeclared / non-Boolean `again` var → located diagnostics
              [resolve/typecheck]
            - rotation binds each participant in GAME direction from the
              leader (counterclockwise pinned); `until` is checked before
              the FIRST turn (the zero-iteration run exists); participants
              re-evaluated per advance, including eligibility revoked by an
              earlier seat's turn (the snapshot-mutant witness); `again`
              repeats the same player and is CONSUMED on read (a stale flag
              buys at most one repeat) [runtime]
            - a non-seat leader (out-of-range Integer, loose pronoun) is a
              typed RuntimeError at the bind — the `as`/`offer` seat-wall
              class, never rotation-arithmetic ValueError [runtime]
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


# --- resolve/typecheck walls (misuse probes) ---


def test_turns_checks_clean() -> None:
    check_dsl(
        _game(
            "  phase p { turns t from dealer over all players until stop {\n"
            "    score[t] += 1  stop := true\n"
            "  } }"
        ),
        "test.cardlang",
    )


def test_binder_is_scoped_to_the_body_only() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop { score[t] += 1 }\n"
        "            score[t] += 1 }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "unresolved name 't'" in e.value.diagnostic.message


def test_non_boolean_until_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until dealer { score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "Boolean" in e.value.diagnostic.message


def test_non_player_leader_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from stop over all players until stop { score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "Player" in e.value.diagnostic.message


def test_non_collection_participants_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over stop until stop { score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "players" in e.value.diagnostic.message


def test_undeclared_again_var_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop again ghost {\n"
        "    score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "ghost" in e.value.diagnostic.message


def test_non_boolean_again_var_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop again dealer {\n"
        "    score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "Boolean" in e.value.diagnostic.message


def test_fused_keyword_typos_are_syntax_errors() -> None:
    # The anchored `_TURNS_KW`/`_AGAIN_KW`: an unanchored inline keyword
    # matches as a PREFIX under the dynamic lexer, so unanchored, `turnst
    # from …` would parse as `turns t` and `againgo` as `again go` — a
    # misspelling compiling to a running game.
    with pytest.raises(DiagnosticError, match="syntax"):
        check_dsl(
            _game("  phase p { turnst from dealer over all players until stop { stop := true } }"),
            "test.cardlang",
        )
    with pytest.raises(DiagnosticError, match="syntax"):
        check_dsl(
            _game(
                "  phase p { turns t from dealer over all players until stop againgo {\n"
                "    score[t] += 1 } }",
                extra_state="go : Boolean = false",
            ),
            "test.cardlang",
        )


# --- runtime semantics ---


def test_rotation_binds_each_participant_in_direction_order() -> None:
    game = check_dsl(
        _game(
            "  phase p { turns t from 1 over all players until score[0] > 0 {\n"
            "    score[t] += 10\n"
            "  } }"
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    # From seat 1 clockwise: 1, 2, then 0 scores and `until` fires before
    # seat 1 comes round again.
    assert result.scores == {0: 10, 1: 10, 2: 10}


def test_until_is_checked_before_the_first_turn() -> None:
    game = check_dsl(
        _game(
            "  phase p { stop := true\n"
            "            turns t from 0 over all players until stop { score[t] += 1 } }"
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    assert all(v == 0 for v in result.scores.values())  # the zero-iteration run


def test_participants_reevaluated_per_advance() -> None:
    # A player leaves the ring the moment their score reaches 10 — the filter
    # must see mid-loop state, so each seat takes exactly one turn and the
    # loop ends when nobody is eligible... which must be the loud wall, so
    # `until` fires first here: everyone at 10 IS the termination.
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over players where score[player] < 10\n"
            "            until (number of players where score[player] < 10) is 0 {\n"
            "    score[t] += 10\n"
            "  } }"
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 10, 1: 10, 2: 10}  # one turn each, no repeats


def test_again_repeats_the_same_player() -> None:
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over all players until score[0] >= 2 again go {\n"
            "    score[t] += 1\n"
            "    go := (t is 0) and (score[0] < 2)\n"
            "  } }",
            extra_state="go : Boolean = false",
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    # Seat 0 goes twice back-to-back; nobody else ever gets a turn.
    assert result.scores == {0: 2, 1: 0, 2: 0}


def test_no_eligible_participant_is_a_loud_error() -> None:
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over players where score[player] > 99\n"
            "            until stop { score[t] += 1 } }"
        ),
        "test.cardlang",
    )
    with pytest.raises(RuntimeError, match="no eligible participant"):
        play_game(game, random.Random(0))


def test_rotation_follows_counterclockwise_direction() -> None:
    # The round forms rotate on `Seating.clockwise`; `turns` must too — a ccw
    # game's turns pass the other way (0 -> 2 -> 1), not seat order.
    dsl = (
        "game G {\n"
        "  players: 3\n"
        "  direction: counterclockwise\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { seen : Integer = 0\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        "  phase p { turns t from 0 over all players until seen >= 3 {\n"
        "    seen += 1\n"
        "    score[t] := seen\n"
        "  } }\n"
        "}\n"
    )
    game = check_dsl(dsl, "test.cardlang")
    r = play_game(game, random.Random(0))
    # Each seat's score is its turn ordinal: the ccw lap from 0 is 0, 2, 1.
    assert r.scores == {0: 1, 1: 3, 2: 2}


def test_non_seat_leader_is_a_loud_typed_error() -> None:
    # A LITERAL out-of-range leader (`turns … from 5`) is rejected statically now
    # (the operand choke point ranges it, tests/test_player_literal_range.py); the
    # leader here is COMPUTED (`0 + 5`, a BinOp the checker leaves Integer without
    # folding, like the phantom-key `n[0 + 9]`), so it passes the static wall and
    # the runtime must wall the non-seat value in game currency — the same
    # seat-wall class as `as (0 + 5)` — never a bare ValueError from rotation
    # arithmetic.
    game = check_dsl(
        _game("  phase p { turns t from (0 + 5) over all players until stop { score[t] += 1 } }"),
        "test.cardlang",
    )
    with pytest.raises(RuntimeError, match="not a seat"):
        play_game(game, random.Random(0))


def test_stale_again_flag_is_consumed_not_replayed() -> None:
    # The form CONSUMES the go-again flag (reset on read): a value left true
    # by an earlier phase buys at most one repeat, never a silent monopoly.
    # Here nothing in the body ever writes `go`, so the pre-set flag repeats
    # seat 0 exactly once and rotation then proceeds: 0, 0, 1, 2.
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over all players until score[2] > 0\n"
            "            again go {\n"
            "    score[t] += 1\n"
            "  } }",
            extra_state="go : Boolean = true",
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 2, 1: 1, 2: 1}


def test_participants_narrowed_by_anothers_turn_are_skipped() -> None:
    # The distinguishing witness against a snapshot-at-entry participants
    # evaluation (a mutant that snapshots passes the other re-eval test):
    # seat 0's turn makes seat 1 ineligible, so seat 1 must never act.
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over players where score[player] >= 0\n"
            "            until score[2] > 0 {\n"
            "    if t is 0 { score[1] := 0 - 5 }\n"
            "    score[t] += 1\n"
            "  } }"
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    # Seat 0 acts (score[1] := -5, then score[0] += 1); seat 1 is now
    # ineligible and skipped; seat 2 acts and ends the loop.
    assert result.scores == {0: 1, 1: -5, 2: 1}


def test_decisionless_nontermination_hits_the_iteration_backstop() -> None:
    # A body that makes no decisions is invisible to the max_length DECISION
    # counter — the turn count itself must be bounded (the same backstop as
    # `repeat until`, one loop class, one guard).
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over all players until stop {\n"
            "    score[t] += 0\n"
            "  } }"
        ),
        "test.cardlang",
    )
    with pytest.raises(RuntimeError, match="max_length"):
        play_game(game, random.Random(0))
