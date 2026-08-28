"""What a betting move COSTS, and what standing bet it leaves behind.

property:        `bet` opens a street at the street's bet size; `call` matches
                 the standing bet without moving it; `raise` goes to ONE place —
                 the last wager any seat made in full, plus the street's size.
                 From a standing bet nobody made in full, that target is the
                 COMPLETION; from one somebody did, it is a full raise; there is
                 no third arm, which is the point of measuring from the level
                 rather than from where the bet stands. Where a stack cannot
                 cover what the move wants, it pays what it holds.
domain:          where the standing bet sits relative to the level, crossed with
                 each move the library can size and with whether the actor's
                 stack covers what that move wants. This module writes its
                 standing bets rather than playing them, so its cells all sit at
                 a level of zero, and its positions are derived from the
                 invariant that bounds them — the level, up to but not including
                 the level plus the street — rather than listed: a standing bet
                 outside that band is a state no play reaches, and a cell
                 holding one would ask the library a question the rules never
                 pose. The positions above a level are reached by PLAYING to
                 them, in tests/test_poker_betting_transitions.py. The actor
                 holds chips in every cell, because a ring only offers a turn
                 to a seat that can act.
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
    """Where the rules put a raise's target, measured from the LEVEL.

    A raise goes to the last wager anyone made IN FULL, plus the street's size.
    This module writes its standing bet directly and never plays one, so no
    full wager is ever made in its cells and the level stays at zero — which
    makes every target here the street's size itself, the completion.

    Pagat's worked example is the one that fixes the yardstick, because in it
    the two candidate readings AGREE and it is easy to read the wrong one out:
    "player A bets $4 and player B who has $6 left goes all-in, which is a
    raise of $2 ... Player C may now fold, call for $6 or raise $4 by putting
    in $10". B's $2 is half of $4, so it counts and B's six BECOMES the level;
    C's ten is therefore the level plus the size, and equals the standing bet
    plus the size only because the level moved. Where an all-in moves the bet
    by less than half, the level does not move and the two part company —
    Pagat again, "player D goes all-in for $6 ... player E has the option to
    fold, to call for $6 or to complete the raise for $10" on a $5 street,
    which is the level's five plus five and not the standing six plus five.
    That case is pinned in tests/test_poker_betting_rulebook.py, and reached
    by play in tests/test_poker_betting_transitions.py.
    """
    return LEVEL + LIMIT


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
LEVEL = 0
"""The last wager made in full, which in this module is always none.

`level` is state the LIBRARY owns, so a probe game cannot write it — a game
may only reach a level by playing a wager that makes one. Every cell here
writes its standing bet instead, so every cell sits at a level of zero.
"""

# Where the standing bet can sit, derived from the invariant rather than
# listed: a standing bet is at least the level and short of the next full
# wager, because a wager reaching that becomes the level itself. At a level of
# zero that admits 0 and the sizes below the street's, and it EXCLUDES the
# rungs this module used to carry — a standing bet at or above the street size
# with no full wager behind it is a state no play reaches, and writing one
# asks the library a question the rules never pose. Those positions are
# reached by playing to them, in tests/test_poker_betting_transitions.py.
RUNGS: dict[str, int] = {
    name: standing
    for name, standing in (("no-bet", 0), ("below-first", 2), ("just-below", LIMIT - 1))
    if LEVEL <= standing < LEVEL + LIMIT
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
                    # `raise` needs a stack that EXCEEDS the call, or the seat
                    # is calling all-in and `call` is that decision. Where the
                    # target sits one chip above the call there is no short
                    # purse that can still raise, and the cell does not exist.
                    if move == "raise" and stack <= standing - bet_by:
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
    level             : Integer = 0
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


def test_the_domain_separates_the_level_from_where_the_bet_stands() -> None:
    """The control: the cells must tell the two candidate yardsticks apart.

    A raise measures a full size from the LAST WAGER MADE IN FULL. The
    plausible wrong rule measures it from WHERE THE BET STANDS, and the two
    agree everywhere except after a wager that moved the bet without being a
    full one — which is exactly the position this module's cells occupy, since
    their standing bets are written rather than played and no full wager stands
    behind them. A domain in which both yardsticks gave the same number would
    pass under either and prove nothing.

    The third candidate — snap to the next multiple of the size — cannot be
    separated here, because at a level of zero it agrees with the rule for
    every standing bet this module can hold. It is separated by playing to a
    level above zero, in tests/test_poker_betting_transitions.py, whose
    `complete-over-a-level` cell charges twenty where snapping would charge
    twenty and adding would charge twenty-three.

    red under: drop every rung but `no-bet` — the two yardsticks then agree on
    the whole domain and the assertion names it.
    """
    diverging = {
        rung
        for rung, standing in RUNGS.items()
        if _raise_target(standing) != standing + LIMIT
    }
    assert diverging, (
        "every cell's standing bet sits where the two yardsticks agree, so no "
        "cell here can tell a raise measured from the level apart from one "
        "measured from the standing bet"
    )
    driven = {c.rung.split("-posted")[0].split("-fresh")[0] for c in CELLS}
    assert not (diverging - driven), (
        f"{sorted(diverging - driven)} separates the two yardsticks but no cell "
        f"drives it"
    )
