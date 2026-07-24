"""A player literal must name a seat the game has.

An integer literal coerces to `Player` (`assignable(Integer, Player)`) at every
position that expects a player. This module walls the EXPRESSION and CALL
positions: a player-indexed zone subscript (`reserve[2]`), a player-keyed state
index read and write (`result[2]` / `result[2] := 1`), a player-typed call
argument (`home(2)`, `team_of(2)`, a game function's Player param), and a
procedure's Player param (`run set(2)`, whose expansion runs after
typechecking) -- by calling one helper (`typecheck._check_player_literal`) from
each site. Unchecked, such a literal names a seat with no player, and the reader
-- a zone family holding no such instance, or a board frame's per-seat sign --
fails at runtime: a typechecked game crashing. This is the position class Codex
flagged on PR #92; the frame verbs were one member -- `reserve[2]`/`result[2]`
had the same hole.

The helper is called from those sites, NOT from one choke point every
`assignable(_, Player)` coercion passes through. So the DECLARATION and BINDING
positions -- a `state` default (`dealer : Player = 5`), a scalar assignment
(`dealer := 5`), an `as` binding, a `turns from`/`over` seat, a struct Player
field, a variant Player payload -- are NOT walled and still accept an
out-of-range literal, as do the clauses carrying no Player type-check at all
(`loser:`, `round`). That residual is real: `dealer : Player = 5`, `dealer := 5`,
`as 5`, `turns from 5`, `turns over [5]`, a struct field, `loser: 5` (even
`loser: "x"`, so `loser:` is genuinely untyped), and `offer to 5` were each run
and accepted on a 2-seat game while writing this; the variant-payload and `round`
positions are audit-identified, confirmed red-first by the follow-up. It is
recorded in roadmap.md; the plan that closes it -- one operand check every
coercion routes through, plus a pin that no `assignable(_, Player)` escapes it --
is docs/superpowers/plans/2026-07-23-player-literal-operand-choke-point.md.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   at the EXPRESSION and CALL positions above, an integer literal in a
            Player position is accepted iff it is a seat of the game
            (`0 <= k < max_seats`; `max_seats` = a range game's `high`, a fixed
            game's count); otherwise a resolve diagnostic. The bound is
            two-sided -- a negative literal is rejected as well as an over-high
            one. This property does NOT hold at the declaration/binding
            positions (the residual).
domain:     {walled position} x {in range | over high} x {fixed | range count},
            plus the shared lower bound pinned once (a negative literal), since
            every walled position calls the one helper and its `0 <=` check is
            single. {walled position} = zone-family subscript, keyed-state index
            (read + write), stdlib call arg, game-function call arg, PROCEDURE
            call arg (expansion runs after typechecking), each also with an
            OPTIONAL `Player?` expectation. These are the sites
            `_check_player_literal` is called from (`_check_expr` x3,
            `_check_assign`, the `RunStmt` arg loop), unwrapping `Player?` first.
registry:   the walled sites are the `_check_player_literal(...)` call sites in
            cardlang/typecheck.py; the seat bound is `TypeEnv.max_players`,
            threaded from `game.players` in `env_from_game`. The wall is NOT
            derived from the set of `assignable(_, Player)` coercions -- that set
            is larger, and the gap between it and these call sites is the
            residual, which the choke-point follow-up closes by construction.
covered:    the grid below -- each walled position rejected out-of-range and
            accepted in-range on a fixed 2-seat game; a negative literal rejected
            (`score[-1]`, the lower bound); the range-count boundary
            (`players: 2..4`: seat 3 accepted, seat 4 rejected); the runtime
            backstop for a COMPUTED out-of-range seat reaching a frame verb is
            tests/test_movement_verbs.py::test_frame_verb_runtime_seat_backstop.
sampled:    none among the walled positions -- every one is an executed row.
residual:   the DECLARATION/BINDING positions and the untyped clauses accept an
            out-of-range literal. Run and confirmed: `dealer : Player = 5`,
            `dealer := 5`, `turns from 5`, `offer to 5`, `turns over [5]`,
            `as 5`, a struct Player field, `loser:` (untyped -- accepts even a
            string). Audit-identified, confirmed red-first by the follow-up: a
            variant Player payload, `round`. A `Team` literal is the parallel
            case on the team axis (`team[2]` on a two-team game). All are
            recorded in roadmap.md ("Out-of-range player
            literals in declaration/binding positions") and closed together by
            the operand-check choke point in docs/superpowers/plans/
            2026-07-23-player-literal-operand-choke-point.md, the follow-up that
            also brings `loser:`/`round` into Player type-checking. This grid
            grows to those positions there, red first.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "seat.cardlang")
    return exc.value.diagnostic.message


# --- a minimal card game whose setup body carries the probe ------------------


def card_game(*, players: str = "  players: 2\n", body: str = "") -> str:
    return (
        "game Seats {\n"
        f"{players}"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase play {\n"
        f"{body}"
        "    turns t from 0 over all players until (any player where score[player] is 1) {\n"
        "      offer to t one of [pass]\n"
        "    }\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        "move_type pass { effect { score[actor] := 1 } }\n"
    )


# (label, body): each body places an out-of-range seat literal in one Player
# position of a 2-seat game. The literal is 5, deliberately NOT equal to the
# seat count (2), so the assertion below pins the OFFENDING value and the count
# as two independent numbers -- a message that hardcoded either as the other
# would pass a `seat 2 ... 2 player(s)` probe but fails this one.
_OUT_OF_RANGE = [
    ("zone subscript", "    move all cards from hand[0] to hand[5]\n"),
    ("state index (write)", "    score[5] := 1\n"),
    ("state index (read)", "    score[0] := score[5]\n"),
    ("stdlib call arg (team_of)", "    score[0] := 0 offset_by (if team_of(5) is team_of(0) then left else right)\n"),
]


@pytest.mark.parametrize("label, body", _OUT_OF_RANGE, ids=[x[0] for x in _OUT_OF_RANGE])
def test_out_of_range_seat_literal_is_rejected(label: str, body: str) -> None:
    msg = _reject(card_game(body=body))
    # The offending seat is the actual literal (5), and the count is the game's
    # (2) -- distinct numbers, each reported from its own source.
    assert "seat 5 is out of range" in msg
    assert "2 player(s) (0..1)" in msg


@pytest.mark.parametrize(
    "body",
    [
        "    move all cards from hand[0] to hand[1]\n",  # subscript, valid seat 1
        "    score[1] := 1\n",  # state write, valid
        "    score[0] := score[1]\n",  # state read, valid
    ],
)
def test_valid_seat_literal_is_accepted(body: str) -> None:
    check_dsl(card_game(body=body), "seat.cardlang")


def test_negative_seat_literal_is_rejected() -> None:
    # -1 is an `IntLit` with a negative value (there is no separate
    # negative-literal AST node), so the helper's two-sided `0 <= k < max` bound
    # rejects it: the lower bound is load-bearing, not vestigial. One row proves
    # it for every walled position -- all call the one helper's single check.
    msg = _reject(card_game(body="    score[-1] := 1\n"))
    assert "seat -1 is out of range" in msg
    assert "2 player(s) (0..1)" in msg


# --- the range-count boundary: the bound is the MAX seats -------------------


def test_range_game_accepts_up_to_the_max_seat() -> None:
    # players: 2..4 -> seats 0..3 possible; seat 3 is legal at the largest table.
    check_dsl(card_game(players="  players: 2..4\n", body="    score[3] := 1\n"), "seat.cardlang")


def test_range_game_rejects_beyond_the_max_seat() -> None:
    # Seat 9, count 4 -- distinct, so the range boundary (`high`) is proven the
    # count source, not echoed from the offending literal.
    msg = _reject(card_game(players="  players: 2..4\n", body="    score[9] := 1\n"))
    assert "seat 9 is out of range" in msg
    assert "4 player(s) (0..3)" in msg


# --- the board frame-verb position (home/far_row/neighbor take a Player) -----


def _board_game(body: str, *, players: str = "  players: 2\n") -> str:
    return (
        "game BoardSeats {\n"
        f"{players}"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        "  board: grid(8, 8)\n"
        "  pieces: xo_marks\n"
        "  zones { box : Deck  square[cell] : Cell<cell>  reserve[player] : PlayerPile<player> }\n"
        "  state { done : Boolean = false }\n"
        "  phase setup {\n"
        "    move all pieces from box where piece.side is x to reserve[0]\n"
        "    move all pieces from box to reserve[1]\n"
        f"{body}"
        "  }\n"
        "  phase play { turns t from 0 over all players until done "
        "{ offer to t one of [stop] } }\n"
        "  winner: highest done\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )


def test_frame_verb_out_of_range_seat_arg_is_rejected() -> None:
    # `home(5)` in a 2-seat game -- a Player call arg, the position Codex named
    # (5, not 2, so the offending value is pinned distinct from the count).
    msg = _reject(
        _board_game("    for each cell c: if c in home(5) { done := true }\n")
    )
    assert "seat 5 is out of range" in msg
    assert "2 player(s) (0..1)" in msg


def test_frame_verb_valid_seat_arg_is_accepted() -> None:
    check_dsl(
        _board_game("    for each cell c: if c in home(1) { done := true }\n"),
        "seat.cardlang",
    )


# --- the two positions Codex's round-3 audit found unswept --------------------


def test_out_of_range_seat_literal_to_a_procedure_is_rejected() -> None:
    # Procedure expansion runs AFTER typechecking, so `run set(5)` would become
    # an unchecked `score[5] := 1` in the spliced body -- the RunStmt arg loop
    # must call the same wall.
    src = card_game(body="    run set(5)\n") + "procedure set(p : Player) { score[p] := 1 }\n"
    msg = _reject(src)
    assert "seat 5 is out of range" in msg


def test_valid_seat_literal_to_a_procedure_is_accepted() -> None:
    src = card_game(body="    run set(1)\n") + "procedure set(p : Player) { score[p] := 1 }\n"
    check_dsl(src, "seat.cardlang")


def test_out_of_range_seat_literal_to_an_optional_player_param_is_rejected() -> None:
    # `Player?` accepts an Integer via `assignable` reaching the optional's
    # payload, so the helper must unwrap the optional before deciding it is a
    # player position.
    src = card_game(body="    score[0] := (if seat_ok(5) then 1 else 0)\n") + "function seat_ok(p : Player?) = 1\n"
    msg = _reject(src)
    assert "seat 5 is out of range" in msg


def test_valid_seat_literal_to_an_optional_player_param_is_accepted() -> None:
    src = card_game(body="    score[0] := (if seat_ok(1) then 1 else 0)\n") + "function seat_ok(p : Player?) = 1\n"
    check_dsl(src, "seat.cardlang")
