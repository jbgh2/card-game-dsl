"""What one wager does to a betting round, from each position it can act in.

property:        a wager's effect on the round — where the bet then stands,
                 whether it spent one of the street's aggressions, and whether
                 the seats behind it must answer again — is decided by TWO
                 numbers: where the bet stands, and the last wager any seat
                 made IN FULL. Every cell below drives one wager from one
                 position and asserts all three outcomes.
domain:          the five positions a betting round reaches, crossed with the
                 wager sizes reachable from each. The positions are derived
                 from the pair (standing bet, last full wager) rather than
                 named by hand — `_position` computes the label and
                 `test_every_cell_sits_in_the_position_it_claims` refuses a
                 cell that mislabels itself. The wager sizes are driven by the
                 ACTOR'S STACK, because `raise` has no amount of its own: it
                 goes to its computed target or all-in short of it, so a stack
                 IS a wager size and the axis needs no separate lever.
registry:        `CELLS` below; the library under test is
                 `docs/libraries/poker_betting.cardlang`.
does not prove:  the expected column is a READING of Robert's Rules, not a
                 quotation of it — a misreading survives every cell here
                 together. Only tests/test_poker_betting_rulebook.py, whose
                 expected values are figures printed in the books, can catch
                 that, and it covers only the positions the books happen to
                 illustrate. A green run of this module means the library
                 agrees with one reading, and no more.

WHY A SEQUENCE. Four review findings landed in this construct and one of them
was invisible to every single-decision grid the repo had, because it is not a
property of a decision at all: it takes a forced post, THEN a short all-in over
it, before the position exists in which a completion moves less than half a bet
while still reaching a full wager. That position is `post-plus-short` below, and
it is the whole reason this module drives scripts rather than states. A grid
that writes its state directly can reach any state it can NAME; it cannot reach
a state nobody thought to name.
"""

from __future__ import annotations

import random
from typing import Any, NamedTuple

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

LIMIT = 10
"""The street's bet size. Ten so that HALF of it is a whole number of chips and
a wager can sit on either side of the half-bet line without a rounding argument."""

POST = 2
"""A forced post, short of the street — Stud's bring-in shape."""


def _position(standing: int, level: int) -> str:
    """The three positions, derived rather than declared.

    A standing bet is nothing, or a wager some seat made in full, or a wager
    short of one. The third is where every finding in this construct has been,
    and a forced post and a short all-in both land in it — which is why one
    rule governs both.
    """
    if standing == 0:
        return "open"
    if standing == level:
        return "level"
    return "short"


class Cell(NamedTuple):
    """One wager, from one position."""

    name: str
    stacks: tuple[int, ...]
    post: bool
    setup: tuple[str, ...]
    """Moves played before the seat under test, one per decision."""
    standing_before: int
    level_before: int
    """The last wager made in full when the seat under test acts. Authored, and
    checked against the library's own standing bet by the position test below."""
    action: str
    standing_after: int
    counted: bool
    """Did the wager spend one of the street's aggressions."""
    reopened: bool
    """Must the seats that already acted answer again."""
    why: str

    @property
    def position(self) -> str:
        return _position(self.standing_before, self.level_before)

    @property
    def id(self) -> str:
        return f"{self.position}-{self.name}"


# Seat 0 posts when a cell has a post. The setup moves are taken by the seats
# after it in turn, so the seat under test is whichever one comes next, and its
# stack is the last entry that matters. Every cell leaves at least one seat
# holding `acted` before the wager under test, or `reopened` could not be seen.
CELLS: tuple[Cell, ...] = (
    # --- from OPEN: nothing stands, and `bet` is the only wager ---------------
    Cell(
        name="bet-a-full-street",
        stacks=(30, 30, 30),
        post=False,
        setup=("check",),
        standing_before=0,
        level_before=0,
        action="bet",
        standing_after=LIMIT,
        counted=True,
        reopened=True,
        why="a full bet is the street's first aggression and everyone answers it",
    ),
    Cell(
        name="bet-all-in-under-half",
        stacks=(30, 4, 30),
        post=False,
        setup=("check",),
        standing_before=0,
        level_before=0,
        action="bet",
        standing_after=4,
        counted=False,
        reopened=False,
        why="under half a bet: it does not reopen for a seat that has acted",
    ),
    Cell(
        name="bet-all-in-half-or-more",
        stacks=(30, 6, 30),
        post=False,
        setup=("check",),
        standing_before=0,
        level_before=0,
        action="bet",
        standing_after=6,
        counted=True,
        reopened=True,
        why="half a bet or more is treated as a full bet",
    ),
    # --- from LEVEL: a full wager stands --------------------------------------
    Cell(
        name="raise-a-full-street",
        stacks=(30, 30, 30, 30),
        post=False,
        setup=("bet", "call"),
        standing_before=LIMIT,
        level_before=LIMIT,
        action="raise",
        standing_after=LIMIT * 2,
        counted=True,
        reopened=True,
        why="a full raise is the standing full wager plus the street",
    ),
    Cell(
        name="raise-all-in-under-half",
        stacks=(30, 30, 13, 30),
        post=False,
        setup=("bet", "call"),
        standing_before=LIMIT,
        level_before=LIMIT,
        action="raise",
        standing_after=13,
        counted=False,
        reopened=False,
        why="moves three chips of a ten-chip street: not a raise at all",
    ),
    Cell(
        name="raise-all-in-exactly-half",
        stacks=(30, 30, 15, 30),
        post=False,
        setup=("bet", "call"),
        standing_before=LIMIT,
        level_before=LIMIT,
        action="raise",
        standing_after=15,
        counted=True,
        reopened=True,
        why='"a half a bet OR MORE" — exactly half counts, so the test is >=',
    ),
    # --- from SHORT, reached by a forced post ---------------------------------
    Cell(
        name="complete-a-post",
        stacks=(30, 30, 30),
        post=True,
        setup=("call",),
        standing_before=POST,
        level_before=0,
        action="raise",
        standing_after=LIMIT,
        counted=True,
        reopened=True,
        why="completing the post makes the street's first full wager",
    ),
    Cell(
        name="post-then-all-in-under-half",
        stacks=(30, 30, 6, 30),
        post=True,
        setup=("call",),
        standing_before=POST,
        level_before=0,
        action="raise",
        standing_after=6,
        counted=False,
        reopened=False,
        why="four chips over the post, under half a bet: still no full wager",
    ),
    # --- from SHORT, reached by a post AND a short all-in over it -------------
    # The position no single-decision grid can reach. Two sub-full wagers stack,
    # so the completion that finally reaches a full bet moves less than half of
    # one — and a rule that measures only the last movement loses it.
    Cell(
        name="complete-over-a-stacked-short",
        stacks=(30, 30, 6, 30),
        post=True,
        setup=("call", "raise"),
        standing_before=6,
        level_before=0,
        action="raise",
        standing_after=LIMIT,
        counted=True,
        reopened=True,
        why=(
            "reaching a full wager is what counts, however little the last "
            "hand moved it — four chips here, under half a bet"
        ),
    ),
    # --- from SHORT, reached by a short all-in over a full wager --------------
    Cell(
        name="complete-over-a-level",
        stacks=(30, 30, 13, 30, 30),
        post=False,
        setup=("bet", "call", "raise"),
        standing_before=13,
        level_before=LIMIT,
        action="raise",
        standing_after=LIMIT * 2,
        counted=True,
        reopened=True,
        why="the completion measures from the last full wager, not from 13",
    ),
    Cell(
        name="call-a-short-all-in",
        stacks=(30, 30, 13, 30, 30),
        post=False,
        setup=("bet", "call", "raise"),
        standing_before=13,
        level_before=LIMIT,
        action="call",
        standing_after=13,
        counted=False,
        reopened=False,
        why="a call moves nothing and answers for nobody but its own seat",
    ),
)


_PROBE = """
game Transitions {{
  uses poker_betting
  players: {seats}
  cards: standard52
  max_length: 200
  zones {{ deck : Deck }}
  state {{
    stack[player]     : Integer = 0
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 99
  }}
  phase play {{
    run open_street({limit})
{stacks}{post}    round offering [check, bet, call, raise] from {first}
          over players where pending(player)
          until false
  }}
  winner: highest stack
}}
"""


class _Landed(Exception):
    """Carries the round out after the wager under test has been made."""

    def __init__(self, offered: frozenset[str]) -> None:
        self.offered = offered


def _source(cell: Cell) -> str:
    stacks = "".join(
        f"    stack[{seat}] := {chips}\n" for seat, chips in enumerate(cell.stacks)
    )
    post = ""
    if cell.post:
        post = (
            f"    bet_by[0] := {POST}\n"
            f"    stack[0] := stack[0] - {POST}\n"
            f"    committed[0] := committed[0] + {POST}\n"
            f"    bet_to_match := {POST}\n"
        )
    return _PROBE.format(
        seats=len(cell.stacks),
        limit=LIMIT,
        stacks=stacks,
        post=post,
        first=1 if cell.post else 0,
    )


def _run(cell: Cell, stop_before_the_wager: bool = False) -> RuntimeState:
    """Play the setup, then the wager under test, and hand back the round."""
    script = cell.setup if stop_before_the_wager else cell.setup + (cell.action,)
    game = check_dsl(_source(cell), "transitions.cardlang")
    box: list[RuntimeState] = []
    step = 0

    def on_first(state: RuntimeState) -> None:
        box.append(state)

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        nonlocal step
        if step == len(script):
            raise _Landed(frozenset(name for name, _ in candidates))
        want = script[step]
        step += 1
        for candidate in candidates:
            if candidate[0] == want:
                return [candidate]
        raise AssertionError(
            f"{cell.id}: step {step - 1} wanted `{want}`, offered "
            f"{sorted(name for name, _ in candidates)}"
        )

    try:
        play_game(game, random.Random(0), None, chooser, None, on_first)
    except _Landed:
        return box[0]
    raise AssertionError(f"{cell.id}: the probe ran out of decisions")


def _acted_seats(state: RuntimeState) -> list[int]:
    # Per-player state reads back as a seat-keyed MAPPING, not a sequence.
    return sorted(seat for seat, flag in state.get("acted").items() if flag)


@pytest.mark.parametrize("cell", CELLS, ids=[c.id for c in CELLS])
def test_every_cell_sits_in_the_position_it_claims(cell: Cell) -> None:
    """The setup reaches the standing bet the cell says it does.

    A cell that has drifted out of its position would keep asserting its
    outcomes faithfully against a situation nobody meant to test — the failure
    mode a hand-labelled position table cannot see. Only the standing bet is
    checked here: the last full wager is the fact the library does not record,
    which is why the cells carry it and this test cannot.

    red under: change any cell's `standing_before` — the setup then lands
    somewhere else and this names the cell.
    """
    state = _run(cell, stop_before_the_wager=True)
    assert state.get("bet_to_match") == cell.standing_before, (
        f"{cell.id}: the setup leaves the bet at {state.get('bet_to_match')}, "
        f"not the {cell.standing_before} the cell is written against"
    )


@pytest.mark.parametrize("cell", CELLS, ids=[c.id for c in CELLS])
def test_the_wager_lands_where_the_rules_put_it(cell: Cell) -> None:
    """Where the bet stands, what it spent, and who must answer.

    All three together, because they are one ruling: a wager that is a full
    wager counts and reopens, and one that is not does neither. Asserting them
    separately would let a library that reopens without counting look half
    right in two places instead of wrong in one.

    red under: any change to `raise`'s counting arm — the `complete-*` cells
    are the ones that separate the readings.
    """
    before = _run(cell, stop_before_the_wager=True)
    raises_before = before.get("raises")
    acted_before = set(_acted_seats(before))

    after = _run(cell)
    standing = after.get("bet_to_match")
    counted = after.get("raises") > raises_before
    still_acted = set(_acted_seats(after))
    # The actor sets its own `acted`, so the seats that must ANSWER again are
    # the ones that held it before this wager and do not hold it now.
    reopened = bool(acted_before - still_acted)

    assert (standing, counted, reopened) == (
        cell.standing_after,
        cell.counted,
        cell.reopened,
    ), (
        f"{cell.id}: the bet stands at {standing}, "
        f"{'spent' if counted else 'spent no'} aggression, and "
        f"{'reopened' if reopened else 'did not reopen'} — the rules give "
        f"{cell.standing_after}, {'spent' if cell.counted else 'spent no'} "
        f"aggression, {'reopened' if cell.reopened else 'no reopening'}.\n"
        f"  {cell.why}"
    )


def test_the_positions_are_all_reached_and_each_carries_a_reason() -> None:
    """Every position the rule distinguishes has a cell, and every cell says why.

    Completeness by superset over `_position`'s own range: a fourth position
    added to the rule arrives as a label no cell holds. The `why` is not
    decoration — this module's expected column is a reading, so a cell that
    cannot say which sentence it is reading is not reviewable, and review is
    the only thing that checks the column at all.

    red under: delete the `open`, `level` or `short` cells, or blank a `why`.
    """
    reached = {cell.position for cell in CELLS}
    assert reached == {"open", "level", "short"}, (
        f"positions {sorted({'open', 'level', 'short'} - reached)} have no cell"
    )
    # The stacked-short position is the one no single-decision grid can reach,
    # and the reason this module exists; losing it would leave the module green
    # and the class open.
    assert any(len(cell.setup) >= 2 and cell.post for cell in CELLS), (
        "no cell stacks a short all-in over a forced post — the position that "
        "needs two wagers to reach, and the one a state-writing grid misses"
    )
    for cell in CELLS:
        assert len(cell.why.split()) >= 6, f"{cell.id}: no reason given"
