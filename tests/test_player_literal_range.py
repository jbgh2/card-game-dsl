"""A player literal must name a seat the game has.

An integer literal coerces to `Player` (`assignable(Integer, Player)`) at every
position that expects a player: a player-indexed zone subscript (`reserve[2]`),
a player-keyed state index read and write (`result[2]` / `result[2] := 1`), and
a player-typed call argument (`home(2)`, `team_of(2)`, a game function's Player
param). Unchecked, such a literal names a seat with no player, and the reader
-- a zone family holding no such instance, or a board frame's per-seat sign --
fails at runtime: a typechecked game crashing. The wall is placed once, at the
coercion (`typecheck._check_player_literal`), so the whole CLASS of player
positions is covered rather than the single one a bug report happens to name
(this is the general form of the frame-verb crash Codex flagged on PR #92; the
frame verbs were one member of the class -- `reserve[2]`/`result[2]` had the
same hole).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   an integer literal in a Player position is accepted iff it is a
            seat of the game (`0 <= k < max_seats`, `max_seats` = a range
            game's `high`, a fixed game's count); otherwise a resolve
            diagnostic, never a silent accept that crashes downstream.
domain:     {Player-coercion position} x {in range | out of range} x
            {fixed count | range count}
            where {position} = zone-family subscript, keyed-state index
            (read + write), stdlib call arg (Player param), game-function
            call arg (Player param) -- the four `assignable(_, TPlayer)`
            sites in typecheck (`_check_expr` x3 + `_check_assign`), which the
            one helper is called from.
registry:   the coercion sites are the `assignable(idx/arg, <Player key/param>)`
            calls in cardlang/typecheck.py; the seat bound is
            `TypeEnv.max_players`, threaded from `game.players` in
            `env_from_game`.
covered:    the grid below -- each position rejected out-of-range and accepted
            in-range on a fixed 2-seat game; the range-count boundary
            (`players: 2..4`: seat 3 accepted, seat 4 rejected); the runtime
            backstop for a COMPUTED out-of-range seat reaching a frame verb is
            tests/test_movement_verbs.py::test_frame_verb_runtime_seat_backstop.
sampled:    none -- every position is an executed row.
residual:   a Team literal is the parallel case (`team[2]` on a two-team game)
            and a NEGATIVE literal (`reserve[-1]`, a distinct `NegIntLit` node)
            is never a real seat; neither is walled here -- no crash witness,
            recorded in roadmap.md. The lower bound `0 <=` in the helper covers
            a zero-or-positive literal only because `IntLit` is non-negative.
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
