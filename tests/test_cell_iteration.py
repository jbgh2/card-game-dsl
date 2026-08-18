"""`for each cell` iteration and `cell in <cellset>` membership.

The statement twin of the landed cell QUANTIFIER register (tests/
test_cell_queries.py). A `for each <role> <binder>` may range over the closed
seat/axis roles and, from rung 2, over a board's NAMED-MEMBER position domain
(`cell`) -- breakthrough's fixed setup array is the witness that lifts the
recorded `for each <position>` residual (issue #111). Integer `positions {}` domains stay guarded: no game
addresses columns by loop, so they remain rejected rather than
accepted-and-unwitnessed.

Three seams carry it, and they must land together (each is dark until the one
before it opens):
  * resolve admits the role iff it is a named-member position domain
    (`_validate_refs`, the `ForEach` guard);
  * typecheck types the binder from the game's position domains -- the
    `ForEach` node rides `_Binders` lazily, exactly as a `let` does, because a
    position domain's member type is per-game and only `_scoped_env` holds it
    (`role_type` is a CLOSED registry and deliberately raises for `cell`);
  * the runtime enumerates `rs.position_domains[role]` directly -- the
    `_domain_query` twin -- so `role_members`, whose closed registry raises for
    anything outside it, is never reached and its subset pin
    (tests/test_permissive_top.py) still holds.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   `for each <role>` ranges over exactly the closed iteration roles
            plus a board's named-member position domain; the binder carries
            that domain's member type; every other role -- including a
            declared INTEGER position domain -- is rejected with a diagnostic,
            never silently iterated or crashed on.
domain:     {for-each role} x {closed role, named-member position (cell),
            integer position (column), unknown/boardless}
            UNION {membership element x collection element type}
registry:   cardlang/domains.py::ITERABLE_ROLES (the closed roles);
            game.positions partitioned by `members_named` (named-member vs
            integer) -- the axis the lift turns on.
covered:    each cell proven by a run probe below --
              for each cell (board game)        -> accept, binder is a Cell,
                                                   body runs once per cell
              for each cell + `in <region>`     -> accept, places one piece per
                                                   region cell (runtime proof)
              for each column (integer position)-> reject (resolve; the message
                                                   is unchanged, so
                                                   tests/rejections/
                                                   positions_for_each is the
                                                   standing fixture twin)
              for each cell (boardless game)    -> reject (resolve)
              for each player (unchanged)       -> accept (regression control)
              cell in Collection<Cell>          -> accept (already generic via
                                                   `unify`; proven, not wired)
              cell in Collection<Card>          -> reject (typecheck)
sampled:    none -- every row above is an executed probe.
red under:  the five ACCEPT rows are born red -- reverting any of the three
            seams (resolve guard, `_scoped_env` ForEach arm, `_for_each`
            position arm) fails them, verified by stashing all three. The three
            GUARD/control rows are born green and carry their own mutations:
            `for each column` reddens if integer domains join
            `iterable_positions`; the boardless row reddens if the lift stops
            gating on the game's OWN domains (a global `cell` admission); and
            `for each player` reddens if the position arm shadows the closed
            role path (drop the `in ctx.rs.position_domains` guard).
residual:   `for each <integer position>` stays guarded (no witness; the guard
            and its roadmap line are the record). A collection-valued
            `for each cell c in <expr>` form is grammatically inexpressible
            (the bare role form plus a membership guard covers the setup
            witness); implement when a game needs the restricted form.
            A `c.foo` on the binder is guarded by the Member arm, swept as the
            fieldless-type class in tests/test_typecheck_errors.py -- not
            re-guarded here.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

FAR_ROW_0 = ("a3", "b3", "c3")  # grid(3, 3): player 0's far edge is the top rank
OTHER_CELLS = ("a1", "b1", "c1", "a2", "b2", "c2")


def board_game(*, setup: str, board: str = "  board: grid(3, 3)\n") -> str:
    """A minimal board game whose setup phase is the probe's payload. `n` is a
    scalar counter the probes read; `result[player]` exists only because
    `winner:` needs a per-seat target."""
    return (
        "game G {\n"
        "  players: 2\n"
        "  direction: clockwise\n"
        "  max_length: 30\n"
        f"{board}"
        "  pieces: xo_marks\n"
        "  zones {\n"
        "    box             : Deck\n"
        "    square[cell]    : Cell<cell>\n"
        "    reserve[player] : PlayerPile<player>\n"
        "  }\n"
        "  state {\n"
        "    result[player] : Integer = 0\n"
        "    n              : Integer = 0\n"
        "    done           : Boolean = false\n"
        "  }\n"
        "  phase setup {\n"
        f"{setup}"
        "  }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest result\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )


DEAL = (
    "    move all pieces from box where piece.side is x to reserve[0]\n"
    "    move all pieces from box to reserve[1]\n"
)


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "cell_iteration.cardlang")
    return exc.value.diagnostic.message


def _board_after_setup(source: str) -> dict[str, int]:
    """Zone occupancies captured at the first decision -- i.e. once setup has
    run and before any move perturbs them."""
    game = check_dsl(source, "cell_iteration.cardlang")
    seen: dict[str, int] = {}

    def snap(rs: object) -> None:
        zones = rs.zones  # type: ignore[attr-defined]
        for cell in FAR_ROW_0 + OTHER_CELLS:
            seen[cell] = len(zones.instance("square", cell))
        seen["reserve0"] = len(zones.instance("reserve", 0))
        seen["n"] = rs.get("n")  # type: ignore[attr-defined]

    play_game(game, random.Random(5), on_first_decision=snap)
    return seen


# --- accept: the lift, and what it binds --------------------------------------


def test_for_each_cell_over_a_region_places_one_piece_per_cell() -> None:
    # The setup-array witness: the body runs once per cell, the membership
    # guard selects the region, and the binder indexes the cell-zone family.
    seen = _board_after_setup(
        board_game(
            setup=DEAL
            + "    for each cell c: if c in far_row(0) "
            "{ move one piece from reserve[0] to square[c] }\n"
        )
    )
    assert [seen[c] for c in FAR_ROW_0] == [1, 1, 1]
    assert [seen[c] for c in OTHER_CELLS] == [0] * len(OTHER_CELLS)
    assert seen["reserve0"] == 2  # 5 x marks, 3 placed


def test_for_each_cell_runs_once_per_cell_over_the_whole_domain() -> None:
    # Unguarded, the body runs over the WHOLE domain, not a region: grid(3, 3)
    # has 9 cells. Counted in state so the probe is free of piece supply.
    seen = _board_after_setup(board_game(setup=DEAL + "    for each cell c: n := n + 1\n"))
    assert seen["n"] == 9


def test_for_each_cell_membership_selects_the_region() -> None:
    # The guard narrows the same 9-cell walk to a region: home(0) is the two
    # low ranks (6 cells), disjoint from far_row(0)'s top rank.
    seen = _board_after_setup(
        board_game(setup=DEAL + "    for each cell c: if c in home(0) { n := n + 1 }\n")
    )
    assert seen["n"] == 6


def test_for_each_cell_binder_is_a_cell() -> None:
    # Proven by consumption: `square[c]` is a cell-indexed family, so the
    # subscript-key guard (coercible(idx, Cell)) accepts only a Cell-typed
    # binder. A `c.foo` on it is rejected by the Member arm's fieldless-type
    # class (tests/test_typecheck_errors.py) -- cross-referenced, not re-guarded.
    check_dsl(
        board_game(
            setup=DEAL
            + "    for each cell c: if c in far_row(0) "
            "{ move one piece from reserve[0] to square[c] }\n"
        ),
        "cell_iteration.cardlang",
    )


def test_for_each_player_still_accepted() -> None:
    # Regression control: lifting the position role must not disturb the closed
    # roles, which still route through `role_members`/`binds_actor`.
    check_dsl(
        board_game(setup=DEAL + "    for each player p: n := 0\n"),
        "cell_iteration.cardlang",
    )


# --- reject: what stays guarded ------------------------------------------------


def test_for_each_over_an_integer_position_domain_is_rejected() -> None:
    # The residual that does NOT lift: an integer `positions {}` domain has no
    # iteration witness. The message lists only the closed roles, because a
    # game with no named-member domain contributes none -- which is why
    # tests/rejections/positions_for_each keeps its expected text verbatim.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  positions { column : 1..4 }
  zones { deck : Deck  pile[column] : Cascade<column> }
  state { n : Integer = 0  score[player] : Integer = 0 }
  phase play {
    for each column c: n := 1
  }
  winner: highest score
}
"""
    msg = _reject(src)
    assert "unknown `for each` role 'column'" in msg
    assert "player, rank, suit, team" in msg


def test_for_each_cell_in_a_boardless_game_is_rejected() -> None:
    # No board mints no `cell` domain, so the role is unknown there.
    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { n : Integer = 0  score[player] : Integer = 0 }
  phase play {
    for each cell c: n := 1
  }
  winner: highest score
}
"""
    msg = _reject(src)
    assert "unknown `for each` role 'cell'" in msg


def test_cell_membership_against_a_card_collection_is_rejected() -> None:
    # Membership is generic (`unify`), so the wrong-element case was already
    # guarded; this pins that the region forms did not open a hole in it.
    msg = _reject(
        board_game(
            setup=DEAL + "    for each cell c: if c in box { n := 1 }\n"
        )
    )
    assert "membership" in msg.lower() or "never true" in msg.lower()
