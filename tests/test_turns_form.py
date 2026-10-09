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
            two generic walkers (expand, openspiel/encoding) whose guard is
            reflection over dataclass fields.
does not prove:  that a body statement of any given kind behaves under
            `turns`. The body-kind axis is sampled: a body's statements run
            through the same execute dispatch `if`/`as` use, and the form
            adds rotation rather than per-statement logic, so what a green
            establishes is the rotation around a body, never the body's own
            dispatch.
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
from cardlang.runtime.errors import OwnerGuardError


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


# --- resolve/typecheck guards (misuse probes) ---


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
    # loop ends when nobody is eligible... which must be the loud guard, so
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
    with pytest.raises(OwnerGuardError, match="no eligible participant"):
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
    # folding, like the phantom-key `n[0 + 9]`), so it passes the static guard and
    # the runtime must guard the non-seat value to the game's author — the same
    # seat-guard class as `as (0 + 5)` — never a bare ValueError from rotation
    # arithmetic.
    game = check_dsl(
        _game("  phase p { turns t from (0 + 5) over all players until stop { score[t] += 1 } }"),
        "test.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="not a seat"):
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
    # counter — the turn count itself must be bounded (the same Shadow Guard as
    # `repeat until`, one loop class, one guard).
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over all players until stop {\n"
            "    score[t] += 0\n"
            "  } }"
        ),
        "test.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="max_length"):
        play_game(game, random.Random(0))


# --- the ring cells the auction form carried (issue #819) ---
#
# Every bidding and betting ring in the corpus is this form with an `offer`
# body, so the ring semantics the auction form pinned are pinned here on the
# construct that now carries them: a leader the predicate excludes is skipped
# with no turn; the participants predicate shrinks the ring per turn; the
# decider's own `asked` event names `offer`; a typed outcome is `produce`d
# from the body; a single seat is re-asked through `repeat until`; and the
# loop splices through a procedure. Each born-green cell names the mutation
# that reddens it.


def _asked_seats(game: n.Game, chooser: Any) -> list[tuple[int, str]]:
    """Every (seat, construct) the decider's own `asked` event carries."""
    seen: list[tuple[int, str]] = []

    def observer(player: int, event: tuple[Any, ...]) -> None:
        if event[0] == "asked":
            seen.append((player, event[2]))

    play_game(game, random.Random(0), chooser=chooser, observer=observer)
    return seen


def _scripted(*names: str) -> Any:
    """A chooser that takes the named moves in order, then the first candidate."""
    script = list(names)

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        if script:
            want = script.pop(0)
            picked = [c for c in candidates if c[0] == want]
            assert picked, f"{want} not offered: {candidates}"
            return picked[:count]
        return candidates[:count]

    return choose


def test_a_leader_the_predicate_excludes_is_skipped_without_a_turn() -> None:
    """The ring opens at the first ELIGIBLE seat from the leader, and the
    excluded leader takes no turn and makes no decision — the shape of a
    standing high bidder named as `from` (Pinochle's `opener`).

    red under: in `execute._turns`, open the first turn at `leader`
    unconditionally instead of at the first candidate the predicate admits."""
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over players where player is not 0\n"
            "            until score[1] > 0 { score[t] += 1 } }"
        ),
        "test.cardlang",
    )
    assert play_game(game, random.Random(0)).scores == {0: 0, 1: 1, 2: 0}


def test_an_offer_body_asks_the_turn_holder_and_the_ring_shrinks_per_turn() -> None:
    """The ascending-auction shape: each seat is asked by `offer`, a seat that
    passes leaves the ring the moment the predicate stops holding for it, and
    the decider's own `asked` event names the construct that asked — `offer`.

    red under: in `execute._turns`, evaluate the participants once before the
    first turn instead of at every pick — the passed seat is asked again."""
    game = check_dsl(
        _game(
            "  phase p { turns b from 1 over players where not passed[player]\n"
            "            until (number of players where not passed[player]) <= 1 {\n"
            "    offer to b one of [bid, pass]\n"
            "  } }",
            extra_state="passed[player] : Boolean = false  bids : Integer = 0",
        )
        + "move_type bid { effect { bids += 1 } }\n"
        + "move_type pass { effect { passed[actor] := true } }\n",
        "test.cardlang",
    )
    asked = _asked_seats(game, _scripted("bid", "pass", "bid", "pass"))
    assert asked == [(1, "offer"), (2, "offer"), (0, "offer"), (1, "offer")]


def test_a_typed_outcome_is_produced_from_the_body() -> None:
    """A ring in an outcome phase ends the phase from inside a turn — the
    auction's result is a `produce`, written where the ring closes.

    red under: catch `_ProduceSignal` inside `execute._turns`."""
    game = check_dsl(
        _game(
            "  phase hand {\n"
            "    phase decide -> outcome { won(Player) | nobody } {\n"
            "      turns t from 0 over all players until stop {\n"
            "        if t is 2 { produce won(t) }\n"
            "        score[t] += 1\n"
            "      }\n"
            "      produce nobody\n"
            "    }\n"
            "    decide produces:\n"
            "      won(w) { score[w] += 10 }\n"
            "      nobody { stop := true }\n"
            "  }"
        ),
        "test.cardlang",
    )
    assert play_game(game, random.Random(0)).scores == {0: 1, 1: 1, 2: 10}


def test_a_single_seat_is_re_asked_through_repeat_until() -> None:
    """One seat whose free actions leave the loop's condition false is asked
    again until it acts — Schnapsen's leader. `repeat until` + `offer` is the
    whole of a single-seat ring.

    red under: in `execute._repeat_until`, evaluate the condition once."""
    game = check_dsl(
        _game(
            "  phase p { repeat until led { offer to 1 one of [free, lead] } }",
            extra_state="led : Boolean = false  frees : Integer = 0",
        )
        + "move_type free { when: frees < 2  effect { frees += 1 } }\n"
        + "move_type lead { effect { led := true } }\n",
        "test.cardlang",
    )
    asked = _asked_seats(game, _scripted("free", "free", "lead"))
    assert asked == [(1, "offer")] * 3


def test_the_ring_splices_through_a_procedure() -> None:
    """A procedure body may hold the loop, binding its own turn-holder, and a
    `run` of it rotates exactly as the inline text does.

    red under: add `n.Turns` to `resolve._WINNER_BINDING_STMTS`."""
    game = check_dsl(
        _game(
            "  phase p { run ring(1) }"
        )
        + "procedure ring(first : Player) {\n"
        + "  turns t from first over all players until score[0] > 0 { score[t] += 10 }\n"
        + "}\n",
        "test.cardlang",
    )
    assert play_game(game, random.Random(0)).scores == {0: 10, 1: 10, 2: 10}
