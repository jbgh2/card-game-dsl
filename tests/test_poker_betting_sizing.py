"""What a betting move COSTS, and what standing bet it leaves behind.

property:        a street runs on a ladder of rungs, one bet size apart. `bet`
                 opens it on the first rung; `call` matches the standing bet
                 without moving it; `raise` moves the standing bet to the NEXT
                 RUNG ABOVE wherever it stands — not up by one bet size from
                 wherever it stands, which is the same thing only when the
                 standing bet is already on a rung. Where a stack cannot cover
                 what the move wants, it pays what it holds.
domain:          the position of the standing bet on the ladder, crossed with
                 each move the library can size and with whether the actor's
                 stack covers what that move wants. The positions are
                 enumerated from the ARITHMETIC — below the first rung, on the
                 first rung, on a later rung, between two rungs, and none at
                 all — never from what the corpus happens to reach: three of
                 the five appear in no game file, and an axis read off
                 `docs/games/` could not have generated them. The actor holds
                 chips in every cell, because a ring only offers a turn to a
                 seat that can act.
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
                 expected column is the rule's arithmetic, so a green says the
                 library computes what fixed-limit poker's ladder says; it says
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

LIMIT = 5  # the street's bet size: one rung to the next


def _next_rung(standing: int) -> int:
    """Where the rules put a raise's target: the first rung strictly above the
    standing bet. Written as the ladder rather than as `standing + LIMIT`,
    because those agree only when the standing bet is already on a rung — and
    the whole property is about the cells where it is not."""
    return (standing // LIMIT + 1) * LIMIT


class Cell(NamedTuple):
    move: str
    standing: int  # bet_to_match before the move
    bet_by: int  # what the actor has already put in this street
    stack: int
    rung: str  # the ladder position, for the id
    purse: str

    @property
    def id(self) -> str:
        return f"{self.move}-{self.rung}-{self.purse}"


# The ladder positions, enumerated from the arithmetic. `first-rung` and
# `later-rung` are the on-grid cases; the other three are what a forced post, a
# short opening bet or an incomplete raise can leave behind.
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
                    else _next_rung(standing) - bet_by
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

    Authored from fixed-limit poker's ladder, never from a game file: the corpus
    twin for Stud DOCUMENTS the wrong 3rd-street sizes, so expectations read
    from it would agree with the defect they are meant to catch.
    """
    if cell.move == "bet":
        wants = LIMIT  # a street opens on its first rung
    elif cell.move == "call":
        wants = cell.standing - cell.bet_by
    else:
        wants = _next_rung(cell.standing) - cell.bet_by
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


def _deferred(cell: Cell) -> bool:
    """Raising from a standing bet that sits BETWEEN two rungs — and only where
    the actor can afford the difference between the two rules. A stack too short
    to reach either target pays what it holds under both, so those cells are
    already green and marking them would be an xfail that cannot fail."""
    return (
        cell.move == "raise"
        and cell.standing > LIMIT
        and cell.standing % LIMIT != 0
        and cell.purse == "covers"
    )


def _not_yet_on_the_ladder(cell: Cell) -> bool:
    """Raising from a standing bet BELOW the first rung — Stud's sub-limit
    bring-in, and any opening bet a short stack could not size to the street.
    The library adds a bet size to the post instead of climbing to the rung."""
    return (
        cell.move == "raise"
        and 0 < cell.standing < LIMIT
        and cell.purse == "covers"
    )


_PARAMS = [
    pytest.param(
        cell,
        id=cell.id,
        marks=(
            pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="issue #436: a raise from a bet between two rungs adds a "
                "bet size to it rather than climbing to the rung above",
            )
            if _deferred(cell)
            else pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="issue #431: a raise from a bet below the first rung adds "
                "a bet size to it rather than climbing to the rung",
            )
            if _not_yet_on_the_ladder(cell)
            else ()
        ),
    )
    for cell in CELLS
]


@pytest.mark.parametrize("cell", _PARAMS)
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


def test_the_rung_ladder_is_not_the_add_one_bet_rule() -> None:
    """The control: the cells only discriminate where the two rules differ.

    `_next_rung` and `standing + LIMIT` agree on every on-grid position, so a
    grid whose ladder positions were all on-grid would pass under either rule
    and prove nothing. This asserts the domain contains positions that separate
    them, and names them — the empty-input-set defect wearing a grid's clothes.
    """
    separating = {
        rung
        for rung, standing in RUNGS.items()
        if _next_rung(standing) != standing + LIMIT
    }
    assert separating == {"below-first", "off-grid"}, (
        f"the positions where the ladder rule differs from add-one-bet are "
        f"{sorted(separating)} — the grid must contain them or it cannot see "
        f"the difference between the two rules"
    )
    driven = {c.rung.split("-posted")[0].split("-fresh")[0] for c in CELLS}
    assert separating <= driven, (
        f"{sorted(separating - driven)} separates the two rules but no cell "
        f"drives it"
    )
