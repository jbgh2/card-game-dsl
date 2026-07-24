"""A Player or Team literal must name a seat/team the game has.

An integer literal coerces to `Player` AND to `Team` (`assignable(Integer,
Player)`, `assignable(Integer, Team)` -- both are 0-based int identities), so at
every position that expects one, an out-of-range literal names a member that does
not exist and the reader (a zone family with no such instance, a board frame's
per-seat sign, a per-team score) crashes at runtime on a typechecked game. The
class is closed BY CONSTRUCTION: every operand coercion routes through one
function, `typecheck._check_operand`, which runs the two-sided range check
(`typecheck._check_role_literal`, dispatching `Player`->`max_players`,
`Team`->`max_teams`). No position is walled by being individually enumerated --
the per-site pattern that shipped on PR #92 rotted the day a new position was
added. `tests/test_operand_choke_point.py` is the pin: it fails the day a new
coercion site calls `assignable(...)` directly instead of routing through
`_check_operand`.

The position axis is the framing-check reconciliation -- a fresh reading of the
grammar and AST for every place an integer reaches a Player/Team, NOT the set of
sites the wall happens to touch. It is: the EXPRESSION and CALL positions
(zone-family subscript, keyed-state index read/write, stdlib/game-function/
procedure call arg, each also with an OPTIONAL `Player?`/`Team?` expectation);
the DECLARATION and BINDING positions (`state` default, scalar `:=`, struct
field, variant payload, `as`, `turns from`/`over`); and the clauses that carried
NO player check at all before the choke point (`offer to`, `loser:`, `round
from`/`over`) -- typed AND ranged in one move now. The TEAM axis is the same
positions wherever a Team is expected.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   an integer literal in a Player/Team position is accepted iff it names
            a member the game has (`0 <= k < bound`; bound = a range game's `high`
            for players, `len(partnerships)` for teams); otherwise a check-time
            diagnostic. Two-sided -- a negative literal is rejected as well as an
            over-high one. Holds at EVERY position an integer coerces to a
            Player/Team, by construction: all route through `_check_operand`.
domain:     {position} x {in range | over high} x role {Player | Team}, plus the
            shared lower bound pinned once (a negative literal). {position} = the
            framing-reconciled set above (`_PLAYER_BUILDERS`/`_TEAM_BUILDERS`
            below): expression/call, declaration/binding, and the
            formerly-untyped clauses. Player positions run on a fixed 2-seat game
            (plus a `players: 2..4` range-count boundary: seat 3 accepted, seat 4
            rejected); Team positions on a 2-team (`partnerships: [[0,2],[1,3]]`)
            game.
registry:   the range check is `_check_role_literal`, called from the ONE choke
            point `_check_operand`. The pin `tests/test_operand_choke_point.py`
            derives the coercion set from the `assignable(...)` CALL nodes in
            cardlang/typecheck.py (via `ast`, so docstrings do not count) and
            asserts each is inside `_check_operand` or `# choke-point-exempt`.
            Bounds: `TypeEnv.max_players` (from `game.players`) and
            `TypeEnv.max_teams` (`len(game.partnerships)`), threaded in
            `env_from_game`.
covered:    the grid below -- `_PLAYER_BUILDERS` x {over high rejected, in range
            accepted} (`test_choke_point_rejects/accepts_..._player`) and
            `_TEAM_BUILDERS` likewise; a negative literal rejected (`score[-1]`,
            the lower bound); the range-count boundary; the formerly-untyped
            clauses additionally rejecting a non-player String
            (`test_untyped_clause_now_rejects_a_non_player`). The pin proves no
            coercion escapes the choke point. Runtime backstops behind the static
            wall stay covered: a COMPUTED out-of-range frame-verb seat
            (tests/test_movement_verbs.py::test_frame_verb_runtime_seat_backstop),
            a COMPUTED phantom key and a `TAny`-typed non-player `loser:`
            selection (both tests/test_fail_loud.py).
sampled:    the Team axis runs two positions (a team-keyed index, a Team call
            arg). The other Team-reachable positions (struct field, variant
            payload, state default, scalar assign) are covered COMPOSITIONALLY,
            not each executed: the pin proves every position routes through
            `_check_operand`, the Player grid proves each such position reaches
            it, and the two team rows prove `_check_operand`->`_check_role_literal`
            ranges a `Team`. Their product is every team position ranged.
residual:   `partnerships:` seat/team lists (`partnerships: [[0, 5]]` on a
            two-seat game) are raw parse-time integers OUTSIDE the type system --
            they never become an operand expression, so the choke point cannot
            reach them (roadmap.md, "Out-of-range seats in a `partnerships:`
            list"). A COMPUTED out-of-range index (`hand[0 + 9]`) is the separate
            "Zone-family index strictness" roadmap entry, backstopped at runtime
            by the typed `ZoneStore` miss.
"""

from __future__ import annotations

from typing import Callable

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


# --- the DECLARATION / BINDING / untyped / TEAM positions the operand-check ---
# --- choke point closes (`_check_operand`, one call every coercion routes) -----
#
# The positions above are the EXPRESSION and CALL sites the per-site helper
# already walled. These are the rest of the class: every position an integer
# literal coerces to a Player -- a `state` default, a scalar `:=`, an `as`
# binding, a `turns`/`round` seat, a struct field, a variant payload -- plus the
# clauses that carried NO player type-check at all (`offer to`, `loser:`,
# `round`), plus the parallel TEAM axis (`Integer` coerces to `Team` too, and the
# range gate ignored it). One operand check (`_check_operand`) routes them all
# through the same two-sided range check. The domain (the position axis) is the
# framing-check reconciliation recorded in the ledger below, not the set of sites
# the wall happens to touch.


def _diagnose(source: str) -> str | None:
    """The first diagnostic's message, or None when the game type-checks. Unlike
    `_reject` (which asserts a raise), this reports acceptance as data, so a
    position ACCEPTED today reads as `None` -- the red state each row below is
    authored against."""
    try:
        check_dsl(source, "seat.cardlang")
        return None
    except DiagnosticError as exc:
        return exc.diagnostic.message


def _decl_game(
    *,
    extra_state: str = "",
    body: str = "",
    leader: str = "0",
    participants: str = "all players",
    offer_tgt: str = "t",
    loser: str = "",
    prelude: str = "",
) -> str:
    """A 2-seat card game with a slot at each declaration/binding/untyped Player
    position. Every slot defaults to an in-range, well-formed value, so a probe
    changes exactly one position and nothing else moves."""
    return (
        f"{prelude}"
        "game Seats {\n"
        "  players: 2\n"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        f"  state {{ score[player] : Integer = 0{extra_state} }}\n"
        "  phase play {\n"
        f"{body}"
        f"    turns t from {leader} over {participants} "
        "until (any player where score[player] is 1) {\n"
        f"      offer to {offer_tgt} one of [pass]\n"
        "    }\n"
        "  }\n"
        "  winner: highest score\n"
        f"{loser}"
        "}\n"
        "move_type pass { effect { score[actor] := 1 } }\n"
    )


def _variant_game(seat: int) -> str:
    """A phase-outcome variant carrying a Player payload -- the `produce won(K)`
    position, checked in `_check_produce_stmt`."""
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { winner_seat : Player? = none  score[player] : Integer = 0 }\n"
        "  phase round {\n"
        "    phase declare -> outcome { won(Player) | abandoned } {\n"
        f"      produce won({seat})\n"
        "    }\n"
        "    declare produces:\n"
        "      won(p) { winner_seat := p }\n"
        "      abandoned { winner_seat := none }\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
    )


def _round_game(*, leader: str = "0", participants: str = "all players") -> str:
    """The kernel `round` (auction form): its `from <leader>` and
    `over <participants>` seats, unchecked before the choke point."""
    return (
        "game Mini {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { high : Integer = 0  passes : Integer = 0 }\n"
        "  phase bid {\n"
        f"    round offering [raise, pass] from {leader} over {participants}\n"
        "          until (passes >= 2) outcome bridge_auction_outcome\n"
        "  }\n"
        "  winner: highest high\n"
        "}\n"
        "move_type raise { effect { high += 1  passes := 0 } }\n"
        "move_type pass { effect { passes += 1 } }\n"
    )


def _team_game(*, body: str = "") -> str:
    """A 4-seat, 2-team game (`partnerships` makes teams 0 and 1). `Integer`
    coerces to `Team` exactly as it does to `Player`, so a team literal names a
    team the game must have -- the parallel axis the range gate had ignored."""
    return (
        "game Teams {\n"
        "  players: 4\n"
        "  partnerships: [[0, 2], [1, 3]]\n"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { won[team] : Integer = 0 }\n"
        "  phase play {\n"
        f"{body}"
        "    turns t from 0 over all players until (any team where won[team] is 1) {\n"
        "      offer to t one of [pass]\n"
        "    }\n"
        "  }\n"
        "  winner: highest won\n"
        "}\n"
        "move_type pass { effect { won[team_of(actor)] := 1 } }\n"
    )


# position id -> builder(seat) : the exportable cell table for the position axis.
# Each builder puts the seat literal in ONE Player position of a 2-seat game.
_PLAYER_BUILDERS: dict[str, Callable[[int], str]] = {
    # declaration / binding positions (coerce via `assignable`, range-unchecked)
    "state_default":      lambda k: _decl_game(extra_state=f"  dealer : Player = {k}"),
    "scalar_assign":      lambda k: _decl_game(extra_state="  dealer : Player = 0", body=f"    dealer := {k}\n"),
    "as_block":           lambda k: _decl_game(body=f"    as {k} {{ score[actor] := 1 }}\n"),
    "turns_leader":       lambda k: _decl_game(leader=str(k)),
    "turns_participants": lambda k: _decl_game(participants=f"[{k}]"),
    "struct_field":       lambda k: _decl_game(prelude="type Rec = { who : Player }\n",
                                               extra_state=f"  r : Rec = Rec {{ who: {k} }}"),
    "variant_payload":    _variant_game,
    # untyped clauses (no player type-check at all before the choke point)
    "offer_to":           lambda k: _decl_game(offer_tgt=str(k)),
    "loser":              lambda k: _decl_game(loser=f"  loser: {k}\n"),
    "round_leader":       lambda k: _round_game(leader=str(k)),
    "round_participants": lambda k: _round_game(participants=f"[{k}]"),
}

# team id -> builder(team) : the parallel TEAM axis (2-team game, teams 0 and 1).
_TEAM_BUILDERS: dict[str, Callable[[int], str]] = {
    "team_keyed_index": lambda k: _team_game(body=f"    won[{k}] := 1\n"),
    "team_call_arg":    lambda k: _team_game(body=f"    won[0] := canasta_meld_points({k})\n"),
}

# The single knob for the staged red->green flip: a position here is still
# residual (its out-of-range row is xfail). Starts as EVERY position (all accept
# an out-of-range literal today -- proven red before the choke point exists) and
# is emptied as each stage lands; at the end it is empty and every row is green.
# `xfail_strict` (pyproject) then turns a leftover mark on a now-passing row into
# a loud failure, so no flip is forgotten.
_NOT_YET_WALLED: set[str] = set()  # every position walled by the choke point


def _reject_params(builders: dict[str, Callable[[int], str]]) -> list[object]:
    """Parametrization for the out-of-range rows: xfail (AssertionError, the shape
    of `assert msg is not None` when the seat is still ACCEPTED) for any position
    not yet walled, plain otherwise."""
    out: list[object] = []
    for pid in builders:
        marks = (
            [pytest.mark.xfail(strict=True, raises=AssertionError,
                               reason=f"residual until the operand choke point walls `{pid}`")]
            if pid in _NOT_YET_WALLED
            else []
        )
        out.append(pytest.param(pid, marks=marks))
    return out


@pytest.mark.parametrize("pid", _reject_params(_PLAYER_BUILDERS))
def test_choke_point_rejects_out_of_range_player(pid: str) -> None:
    # Seat 5 in a 2-seat game -- 5 != the count (2), so the message pins the
    # offending value and the count as two independent numbers.
    msg = _diagnose(_PLAYER_BUILDERS[pid](5))
    assert msg is not None, f"{pid}: out-of-range seat 5 accepted (choke point not reached)"
    assert "seat 5 is out of range" in msg
    assert "2 player(s) (0..1)" in msg


@pytest.mark.parametrize("pid", sorted(_PLAYER_BUILDERS))
def test_choke_point_accepts_in_range_player(pid: str) -> None:
    # Seat 1 is a real seat of the 2-seat game: accepted before and after the
    # wall, so the wall is proven to reject the out-of-range literal specifically,
    # not the position.
    assert _diagnose(_PLAYER_BUILDERS[pid](1)) is None


@pytest.mark.parametrize("pid", _reject_params(_TEAM_BUILDERS))
def test_choke_point_rejects_out_of_range_team(pid: str) -> None:
    # Team 5 in a 2-team game. 5 != the team count (2) AND != the seat count (4),
    # so "team 5 ... 2 team(s)" pins the value against the TEAM bound specifically.
    msg = _diagnose(_TEAM_BUILDERS[pid](5))
    assert msg is not None, f"{pid}: out-of-range team 5 accepted (choke point not reached)"
    assert "team 5 is out of range" in msg
    assert "2 team(s) (0..1)" in msg


@pytest.mark.parametrize("pid", sorted(_TEAM_BUILDERS))
def test_choke_point_accepts_in_range_team(pid: str) -> None:
    assert _diagnose(_TEAM_BUILDERS[pid](1)) is None


# The untyped clauses (`offer to`, `loser:`, `round … from`) carried NO player
# type-check at all before the choke point -- the worse half of the bug: they
# accepted a STRING, not just an out-of-range seat. Routing them through
# `_check_operand(_, _, TPlayer(), _)` types them too. A non-player value is now
# a check-time error (the same wall the runtime backstop sat behind, moved
# earlier -- tests/test_fail_loud.py keeps the backstop for the `TAny` case).
_UNTYPED_NON_PLAYER = {
    "offer_to": lambda: _decl_game(offer_tgt='"nope"'),
    "loser": lambda: _decl_game(loser='  loser: "nope"\n'),
    "round_leader": lambda: _round_game(leader='"nope"'),
}


@pytest.mark.parametrize("pid", sorted(_UNTYPED_NON_PLAYER))
def test_untyped_clause_now_rejects_a_non_player(pid: str) -> None:
    msg = _diagnose(_UNTYPED_NON_PLAYER[pid]())
    assert msg is not None, f"{pid}: a non-player (String) selection accepted"
    assert "expected a Player" in msg
    assert "String" in msg
