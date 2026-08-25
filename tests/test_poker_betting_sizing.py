"""What a betting move COSTS, and what standing bet it leaves behind.

property:        `bet` opens a street at the street's bet size; `call` matches
                 the standing bet without moving it; `raise` adds a full size to
                 where the bet STANDS — except from a standing bet short of the
                 size, which it COMPLETES to the size instead. Those are two
                 rules and not one, and the pair is the whole property: the
                 betting level does not re-form around multiples of the size, so
                 a bet left off one by an all-in for less stays off it and is
                 raised from where it is. Where a stack cannot cover what the
                 move wants, it pays what it holds.
domain:          where the standing bet sits relative to the street's size,
                 crossed with each move the library can size and with whether
                 the actor's stack covers what that move wants. The positions
                 are enumerated from the ARITHMETIC — none, short of the size,
                 exactly the size, a multiple of it, and off any multiple —
                 never from what the corpus happens to reach: three of the five
                 appear in no game file, and an axis read off `docs/games/`
                 could not have generated them. The actor holds chips in every
                 cell, because a ring only offers a turn to a seat that can act.
registry:        the moves that size a payment, and the state they read:
                 `n.Library.move_types`, `.requires` and `.state` of
                 `libraries.load_library("poker_betting")`, crossed in
                 `_cells`. Which of those moves is OFFERED at a given decision
                 is a different property with its own module and ledger,
                 tests/test_poker_betting_offers.py. The chips a whole hand
                 then settles are tests/test_holdem_settle.py's.
does not prove:  a cell drives one move from a hand-built state, so nothing
                 here bounds what a STREET costs end to end — that a street
                 stops at its declared number of bets is
                 tests/test_playout_holdem_heads_up.py's cap pin. And the
                 expected column is the rules' arithmetic, so a green says the
                 library charges what fixed-limit poker charges; it says
                 nothing about whether a given game declared the right bet
                 sizes for the variant it names.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from cardlang.libraries import load_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

LIBRARY = load_library("poker_betting")

# The moves that move chips. `check` is the fourth move type and sizes nothing —
# derived rather than assumed, so a fifth move type arrives as a name this
# module must account for.
VOCABULARY: tuple[str, ...] = tuple(m.name for m in LIBRARY.move_types)
SIZING_MOVES: tuple[str, ...] = tuple(m for m in VOCABULARY if m != "check")

LIMIT = 5  # the street's bet size


def _raise_target(standing: int) -> int:
    """Where the rules put a raise's target, and it is TWO rules, not one.

    A standing bet short of the street's size is COMPLETED to it. Pagat, on
    Stud's bring-in: "subsequent players have the option to complete the bet to
    a small bet ($5), to call the bring-in ($2) or to fold" — so from a
    bring-in of 2 at a size of 5, the target is 5 and not 7.

    From anywhere else a raise adds a full size to WHERE THE BET STANDS, even
    when an all-in for less has left it off any multiple of the size. Pagat,
    worked: "player A bets $4 and player B who has $6 left goes all-in, which is
    a raise of $2 ... Player C may now fold, call for $6 or raise $4 by putting
    in $10 of which $6 goes into the main pot and $4 into the side pot." C's
    total is B's all-in plus a full raise — 6 + 4 — not A's last full bet plus
    one, which would be 8. The betting level does not re-form around the size
    after a short all-in, and a target computed as "the next multiple of the
    size above the standing bet" would charge 10 where the rules charge 12.
    """
    return LIMIT if standing < LIMIT else standing + LIMIT


class Cell(NamedTuple):
    move: str
    standing: int  # bet_to_match before the move
    bet_by: int  # what the actor has already put in this street
    stack: int
    rung: str  # where the standing bet sits, for the id
    purse: str

    @property
    def id(self) -> str:
        return f"{self.move}-{self.rung}-{self.purse}"


# Where the standing bet can sit relative to the street's size, enumerated from
# the arithmetic. `first-rung` and `later-rung` are the ordinary cases; the
# other three are what a forced post, a short opening bet or an all-in for less
# can leave behind.
RUNGS: dict[str, int] = {
    "no-bet": 0,
    "below-first": 2,
    "first-rung": LIMIT,
    "later-rung": 2 * LIMIT,
    "off-grid": 7,
}


def _cells() -> list[Cell]:
    out: list[Cell] = []
    for move in SIZING_MOVES:
        for rung, standing in RUNGS.items():
            # `bet` opens a street, so it only ever sizes from no standing bet;
            # `call` and `raise` answer one, so they never size from none.
            if (move == "bet") != (standing == 0):
                continue
            for bet_by in sorted({0, standing}):
                if move == "call" and bet_by == standing:
                    continue  # nothing owed; `check` is that decision, not `call`
                wants = (
                    LIMIT if move == "bet" else standing - bet_by
                    if move == "call"
                    else _raise_target(standing) - bet_by
                )
                for purse, stack in (("covers", wants + 1), ("short", max(1, wants - 1))):
                    if stack <= 0:
                        continue
                    posted = "posted" if bet_by else "fresh"
                    out.append(
                        Cell(
                            move=move,
                            standing=standing,
                            bet_by=bet_by,
                            stack=stack,
                            rung=f"{rung}-{posted}",
                            purse=purse,
                        )
                    )
    return out


CELLS = _cells()


class Outcome(NamedTuple):
    paid: int
    standing: int


def _expected(cell: Cell) -> Outcome:
    """What the rules charge, and what standing bet they leave.

    Authored from the rules, never from a game file: a corpus twin documents
    what its game does, so an expected column read from one agrees with
    whatever defect the game has.
    """
    if cell.move == "bet":
        wants = LIMIT  # a street opens at its own size
    elif cell.move == "call":
        wants = cell.standing - cell.bet_by
    else:
        wants = _raise_target(cell.standing) - cell.bet_by
    paid = min(wants, cell.stack)
    standing = cell.standing if cell.move == "call" else max(cell.standing, cell.bet_by + paid)
    return Outcome(paid=paid, standing=standing)


_PROBE = """
game Sizing {{
  uses poker_betting
  players: 3
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{
    hero              : Player = 0
    stack[player]     : Integer = 10
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 9
  }}
  phase play {{
    run open_street({limit})
    bet_to_match := {standing}
    for each player p: bet_by[p] := {bet_by}
    for each player p: stack[p] := {stack}
    round offering [{vocabulary}] from 0
          over players where player is hero
          until false
  }}
  winner: highest stack
}}
"""


class _Done(Exception):
    """Carries the post-move numbers out at the decision AFTER the one under
    test, which is the first moment the effect has finished running."""

    def __init__(self, paid: int, standing: int) -> None:
        self.paid = paid
        self.standing = standing


def _drive(cell: Cell) -> Outcome:
    source = _PROBE.format(
        limit=LIMIT,
        standing=cell.standing,
        bet_by=cell.bet_by,
        stack=cell.stack,
        vocabulary=", ".join(VOCABULARY),
    )
    game = check_dsl(source, "sizing.cardlang")
    box: list[Any] = []
    drawn = 0

    def on_first(state: Any) -> None:
        box.append(state)

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        nonlocal drawn
        drawn += 1
        offered = [name for name, _ in candidates]
        if drawn == 1:
            assert cell.move in offered, (
                f"{cell.id}: `{cell.move}` is not offered in this state "
                f"({offered}) — the cell cannot drive the move it names"
            )
            return [next(c for c in candidates if c[0] == cell.move)]
        state = box[0]
        raise _Done(
            paid=cell.stack - state.get("stack")[player],
            standing=state.get("bet_to_match"),
        )

    try:
        play_game(game, random.Random(0), None, chooser, None, on_first)
    except _Done as done:
        return Outcome(paid=done.paid, standing=done.standing)
    raise AssertionError(f"{cell.id}: the probe never reached a second decision")


@pytest.mark.parametrize("cell", CELLS, ids=[c.id for c in CELLS])
def test_a_move_pays_the_ladder(cell: Cell) -> None:
    """Both numbers per cell: what left the actor's stack, and what stands after.

    Asserting the pair rather than either alone is what makes this a sizing pin.
    The two come apart — Hold'em's small blind and its button pay different
    amounts for the same raise and leave the same standing bet — so a rule that
    charged correctly and recorded the wrong bet, or the reverse, passes a test
    that watches one of them.
    """
    assert _drive(cell) == _expected(cell), (
        f"{cell.id}: standing {cell.standing} at a bet size of {LIMIT}, actor in "
        f"for {cell.bet_by} holding {cell.stack}"
    )


def test_the_domain_separates_completing_from_adding_and_from_snapping() -> None:
    """The control: the cells must be able to tell the three candidate rules apart.

    Three rules agree almost everywhere and disagree exactly where this grid has
    to be right — so a domain missing either separating position would pass under
    any of them and prove nothing.

    - COMPLETE a short standing bet to the size, then add a size (the rules);
    - always add a size, completing nothing (charges 7 from a bring-in of 2);
    - snap to the next multiple of the size (charges 10 where the rules charge
      12, after an all-in for less has left the bet off a multiple).

    The third is worth naming rather than dropping: it is the plausible wrong
    rule, it reads as tidier than the right one, and it was authored into this
    module's expected column and shipped before Pagat's worked example was
    consulted. See `_raise_target`.
    """
    add_only = {r for r, s in RUNGS.items() if _raise_target(s) != s + LIMIT}
    snap = {
        r
        for r, s in RUNGS.items()
        if _raise_target(s) != (s // LIMIT + 1) * LIMIT
    }
    assert add_only == {"below-first"}, (
        f"only a standing bet short of the size should be COMPLETED rather than "
        f"added to; the domain says {sorted(add_only)}"
    )
    assert snap == {"off-grid"}, (
        f"only a standing bet off a multiple of the size should separate the "
        f"rules' target from the next multiple; the domain says {sorted(snap)}"
    )
    driven = {c.rung.split("-posted")[0].split("-fresh")[0] for c in CELLS}
    missing = (add_only | snap) - driven
    assert not missing, f"{sorted(missing)} separates two rules but no cell drives it"
