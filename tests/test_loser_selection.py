"""A `loser:` selection names a seat of the table, or the playout refuses it.

`loser: <selection>` takes any expression, and a computed one is usually
gradually typed, so the checker's Player typing passes it through and the
value is first known at game end. The driver is the Owner Guard for that
dynamic class: the selected value must be a seat of this table, and anything
else is an `OwnerGuardError` naming the clause. The returns OpenSpiel trains
on depend on it -- `returns_for` pays the loser `-(n-1)` and every other seat
`+1`, which sums to zero only when the loser is one of the `n` seats.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   the value a `loser:` selection yields at game end is accepted
            exactly when it is a seat of the table -- an `int`, not a `bool`,
            in `0 <= seat < players` -- and every other value is refused in
            the runtime's own currency, so a finished elimination game's
            returns sum to zero.
domain:     the runtime value shapes a selection can yield through the
            permissive top: one value per declarable type, in its plain and
            optional form, crossed in by a scalar state variable the
            selection's `else` branch reads; and the integer boundary of a
            three-seat table (below it, its first and last seats, one past
            it) plus a Boolean literal, written directly in the branch.
            Every corpus game that declares `loser:` is swept for the
            sum-to-zero property. The table size is split at two: a
            one-seat elimination game is refused at check time.
registry:   declared types: `tests/winner_axes.py` (`type_cells`, over
            `typecheck.KNOWN_TYPE_NAMES`, its default table pinned by
            `tests/test_winner_target.py::test_default_table_covers_every_declared_type`).
            Elimination games: the `docs/games/*.cardlang` glob, filtered on
            the parsed `loser` clause.
does not prove:  that a value meaning something other than a seat is
            refused. The language coerces an Integer to a Player, so an
            in-range Integer -- a count, a score, `out + 1` -- is accepted as
            that seat; and a Team reaching the selection through a mixed `if`
            is an integer at runtime, indistinguishable from one. What a
            green establishes is that the loser is a seat of the table.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.openspiel.replay import returns_for
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from tests.playout_policy import reference_policy_for
from tests.winner_axes import type_cells

REPO = Path(__file__).resolve().parent.parent
SEATS = 3

# The `then` branch is never taken (no `x` is ever 1), so the `else` branch is
# the selection, and the mixed `if` keeps the checker's type open.
TEMPLATE = """
game G {{
  players: {seats}
  max_length: 1000
  cards: standard52
  teams: [[0, 2], [1]]
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ x[player] : Integer = 0  v : {ty} = {default} }}
  phase play {{ shuffle deck }}
  loser: if (any player where x[player] is 1) then (the player where x[player] is 1) else {selection}
}}
"""

# A cell's expected outcome: the seat accepted, or `None` for a refusal.
Cell = tuple[str, str, str, int | None]


def _cells() -> list[Cell]:
    cells: list[Cell] = []
    for written, default, optional in type_cells():
        # A plain Integer-shaped default (`0`) is seat 0 at runtime; every
        # other default is a string, a Boolean or `none`.
        seat = 0 if not optional and written in ("Integer", "Player", "Team") else None
        cells.append((f"type-{written.replace('?', '_opt')}", written, default, seat))
    return cells


def _boundary_cells() -> list[tuple[str, str, int | None]]:
    return [
        ("below-the-table", "-1", None),
        ("first-seat", "0", 0),
        ("last-seat", str(SEATS - 1), SEATS - 1),
        ("one-past-the-table", str(SEATS), None),
        ("boolean-true", "true", None),
    ]


def _outcome(source: str) -> int | None:
    """The accepted seat, or `None` when the playout refuses the selection."""
    game = check_dsl(source, "t.cardlang")
    try:
        result = play_game(game, random.Random(0))
    except OwnerGuardError as exc:
        assert "`loser:`" in str(exc), exc
        return None
    # A flag would compare equal to a seat-0 or seat-1 cell's expectation.
    assert type(result.loser) is int, result.loser
    return result.loser


@pytest.mark.parametrize(
    ("ty", "default", "seat"),
    [pytest.param(ty, default, seat, id=cid) for cid, ty, default, seat in _cells()],
)
def test_a_loser_value_of_each_declared_type(ty: str, default: str, seat: int | None) -> None:
    source = TEMPLATE.format(seats=SEATS, ty=ty, default=default, selection="v")
    assert _outcome(source) == seat


@pytest.mark.parametrize(
    ("selection", "seat"),
    [pytest.param(sel, seat, id=cid) for cid, sel, seat in _boundary_cells()],
)
def test_a_loser_value_at_the_table_boundary(selection: str, seat: int | None) -> None:
    source = TEMPLATE.format(seats=SEATS, ty="Integer", default="0", selection=selection)
    assert _outcome(source) == seat


def _elimination_games() -> list[str]:
    names = []
    for path in sorted((REPO / "docs/games").glob("*.cardlang")):
        game = check_dsl(path.read_text(), path.name)
        if game.loser is not None:
            names.append(path.stem)
    return names


ELIMINATION_GAMES = _elimination_games()


def test_the_corpus_has_an_elimination_game() -> None:
    """The sweep below is a property over a glob; an empty glob is a green
    nobody earned."""
    assert ELIMINATION_GAMES


@pytest.mark.parametrize("name", ELIMINATION_GAMES)
def test_an_elimination_games_returns_sum_to_zero(name: str) -> None:
    """red under: `returns_for`'s loser arm paying the loser `-(n_players - 2)`."""
    game = check_dsl((REPO / f"docs/games/{name}.cardlang").read_text(), f"{name}.cardlang")
    for seed in range(10):
        rng = random.Random(seed)
        result = play_game(game, rng, chooser=reference_policy_for(name, rng))
        assert sum(returns_for(game, result)) == 0, (name, seed, result.loser)


ONE_SEAT = """
game G {{
  players: {seats}
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  phase setup {{ move 13 cards from deck to hand[0] }}
  loser: the player where hand[player] is not empty
}}
"""


@pytest.mark.parametrize("seats", [1, 2], ids=["one-seat", "two-seat"])
def test_an_elimination_game_seats_at_least_two(seats: int) -> None:
    """A one-seat table's only player is its loser, so nobody is left to win
    and the result's winners would be empty. The table-size axis is the
    count `players:` takes, split where an elimination stops meaning one."""
    source = ONE_SEAT.format(seats=seats)
    if seats == 1:
        with pytest.raises(DiagnosticError, match="at least two players"):
            check_dsl(source, "t.cardlang")
        return
    result = play_game(check_dsl(source, "t.cardlang"), random.Random(0))
    assert (result.loser, result.winners) == (0, frozenset({1}))
