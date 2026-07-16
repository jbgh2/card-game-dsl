"""The `as <player> { … }` single-actor binder (decisions.md "Single-actor
decisions: the `as` block").

`as <player-expr> { … }` evaluates its player expression in the OUTER context,
binds the acting player to that one player, and runs its body once as a block
scope. It replaces the `for each player p: if p is <who> { … }` idiom, which
silently captures `actor` (true for every `p`) and — when the body mutates the
guard variable — re-matches a later player mid-pass.

property:   `as <p> { … }` binds the acting player to exactly one evaluated
            Player, runs its body once, in a block scope whose `let`s do not
            escape; every grammar-accepted combination executes or is
            statically rejected.
domain:     (player-expr ∈ Expr union) × (body ∈ Stmt* — every statement kind)
registry:   the Expr and Stmt unions (cardlang/ast/nodes.py); the statement
            dispatch is pinned exhaustively by `assert_never` in resolve,
            typecheck (×4), ir, deckcheck, and runtime/execute.
covered:    - omitted player-expr / malformed → parse error [grammar]
            - unresolved name in player position → resolve reject
            - non-Player player-expr → typecheck reject (assignable(_, Player),
              keeping the Integer-stands-for-player leniency of
              `dealer : Player = 0`) [typecheck]
            - body `let` does not escape the block [resolve + runtime]
            - the acting player reaches a `chosen` movement in the body via
              `acting_as`, byte-identical to the loop idiom [runtime]
            - `as` lexes distinctly from `as-equally-as-possible` and from a
              statement-leading `as…` identifier (anchored `_AS_KW`) [grammar]
sampled:    - the remaining body statement kinds (rotate, epistemic, round,
              produces, …) execute through the SAME `run_body`/`execute`
              dispatch used by `if`/`Block`; AsBlock adds no per-statement-kind
              logic, only the ctx rebind, so `move chosen` (the motivating
              case), nested `as`, and let-scope are probed and the rest sampled.
residual:   none — the construct produces no new value shape, so there are no
            new expr-consumer pairwise cells.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _walk
from cardlang.runtime.driver import play_game


def _as_blocks(game: n.Game) -> list[n.AsBlock]:
    return [nd for nd in _walk(game) if isinstance(nd, n.AsBlock)]


def _game(body: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player>\n"
        "          discard : Discard }\n"
        "  state { dealer : Player = 0\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"{body}\n"
        "}\n"
    )


def test_as_block_parses_to_an_asblock_node() -> None:
    dsl = _game("  phase p { as dealer { score[dealer] += 1 } }")
    game = parse_text(dsl, "test.cardlang")
    blocks = _as_blocks(game)
    assert len(blocks) == 1
    assert isinstance(blocks[0].player, n.NameRef)
    assert blocks[0].player.name == "dealer"
    assert len(blocks[0].body) == 1


def test_as_block_checks_clean() -> None:
    check_dsl(_game("  phase p { as dealer { score[dealer] += 1 } }"), "test.cardlang")


# --- misuse probes (surface-totality rejection tests) ---


def test_omitted_player_expr_is_a_syntax_error() -> None:
    # `as { … }` — the mandatory player expression is missing.
    with pytest.raises(DiagnosticError):
        check_dsl(_game("  phase p { as { score[dealer] += 1 } }"), "test.cardlang")


def test_non_player_expr_is_rejected() -> None:
    # A zone is a plausible wrong operand (`as hand[dealer]` instead of a player).
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game("  phase p { as hand[dealer] { score[dealer] += 1 } }"),
            "test.cardlang",
        )
    assert "Player" in e.value.diagnostic.message


def test_boolean_player_expr_is_rejected() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game("  phase p { as (dealer is dealer) { score[dealer] += 1 } }"),
            "test.cardlang",
        )
    assert "Player" in e.value.diagnostic.message


def test_unresolved_name_in_player_position_is_rejected() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game("  phase p { as nobody { score[dealer] += 1 } }"), "test.cardlang"
        )
    assert "nobody" in e.value.diagnostic.message


def test_body_let_does_not_escape_the_block() -> None:
    # A `let` bound inside the `as` body is out of scope after it.
    with pytest.raises(DiagnosticError):
        check_dsl(
            _game(
                "  phase p { as dealer { let x = 1 }\n"
                "            score[dealer] += x }"
            ),
            "test.cardlang",
        )


def test_as_equally_as_possible_still_parses() -> None:
    # The new `as` keyword must not steal the `as` in `as-equally-as-possible`.
    getaway = Path(__file__).parent.parent / "docs" / "games" / "getaway.cardlang"
    check_dsl(getaway.read_text(), str(getaway))


def test_leading_as_identifier_still_lexes_as_a_name() -> None:
    # `assets` must lex as a NAME, not `as` + `sets`.
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state { assets : Integer = 0 }\n"
        "  winner: highest assets\n"
        "  phase p { assets := 5 }\n"
        "}\n"
    )
    check_dsl(dsl, "test.cardlang")


# --- runtime equivalence: `as <p>` ≡ `for each p: if p is <p>` (byte-identical) ---


def _decision_game(decision_body: str, dealer: int = 1) -> n.Game:
    """A tiny complete game whose only decision is one dealer discard, spelled
    by the caller as either an `as` block or the `for each … if` idiom."""
    src = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck\n"
        "          hand[player] : Hand<player>\n"
        "          discard : Discard }\n"
        f"  state {{ dealer : Player = {dealer}\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        "  phase setup { deal 3 cards from deck to each hand }\n"
        f"  phase act {{ {decision_body} }}\n"
        "}\n"
    )
    return check_dsl(src, "test.cardlang")


def _run_capturing(game: n.Game) -> tuple[list[Any], list[Any]]:
    obs: list[Any] = []
    calls: list[Any] = []

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        calls.append((player, list(candidates), k))
        return list(candidates[:k])

    def observer(player: int, event: tuple[Any, ...]) -> None:
        obs.append((player, event))

    play_game(game, random.Random(7), chooser=chooser, observer=observer)
    return obs, calls


def test_as_block_is_byte_identical_to_the_loop_idiom() -> None:
    as_form = _decision_game(
        "as dealer { move chosen 1 cards from hand[dealer] to discard }"
    )
    loop_form = _decision_game(
        "for each player p: if p is dealer "
        "{ move chosen 1 cards from hand[p] to discard }"
    )
    as_obs, as_calls = _run_capturing(as_form)
    loop_obs, loop_calls = _run_capturing(loop_form)

    # Same single decision, offered to the same player (the dealer, seat 1),
    # with the same candidates and the same emitted observation stream.
    assert as_calls == loop_calls
    assert len(as_calls) == 1
    assert as_calls[0][0] == 1  # the dealer chose, not seat 0
    assert as_obs == loop_obs


def test_as_block_runs_its_body_once_not_per_matching_player() -> None:
    # The semantic that separates `as` from the loop idiom: when the body mutates
    # the guard variable, `as` runs once, but the loop re-matches the other
    # player mid-pass. With dealer = seat 0, the body flips `dealer` to seat 1,
    # which the loop's later iteration (p = 1) then re-matches — offering a
    # SECOND decision. `as` evaluates the player once and offers exactly one.
    # (In Cribbage the two forms are observably identical anyway — its `active`
    # alternates so the loop's double-execution yields the same flat sequence —
    # but that is a property of Cribbage's structure, not of the constructs.)
    as_form = _decision_game(
        "as dealer { move chosen 1 cards from hand[dealer] to discard\n"
        "            dealer := the player where player is not dealer }",
        dealer=0,
    )
    loop_form = _decision_game(
        "for each player p: if p is dealer "
        "{ move chosen 1 cards from hand[p] to discard\n"
        "  dealer := the player where player is not dealer }",
        dealer=0,
    )
    _, as_calls = _run_capturing(as_form)
    _, loop_calls = _run_capturing(loop_form)

    assert len(as_calls) == 1  # one turn, as written
    assert len(loop_calls) == 2  # the loop re-matches the flipped dealer — the bug


def test_nested_as_rebinds_to_the_inner_player() -> None:
    # `as` composes: the inner block rebinds over the outer, so the decision is
    # attributed to the inner player (dealer = 1, so `other` = 0 chooses).
    game = _decision_game(
        "as dealer {\n"
        "  let other = the player where player is not dealer\n"
        "  as other { move chosen 1 cards from hand[other] to discard }\n"
        "}",
        dealer=1,
    )
    _, calls = _run_capturing(game)
    assert len(calls) == 1
    assert calls[0][0] == 0  # the inner `as other`, not the outer `as dealer`
