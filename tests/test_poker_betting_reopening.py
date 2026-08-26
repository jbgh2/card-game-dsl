"""Which aggressions re-open the betting, and which are action only.

property:        an aggression that moves the standing bet at least HALF as far
                 as a full raise would is a raise for every purpose — it clears
                 every other seat's turn, so they are asked again with the right
                 to re-raise, and it spends one of the street's counted
                 aggressions. One that moves the bet less than half is action
                 only: no seat's turn is restored and no count is spent, so the
                 seats already in answer it with call or fold alone.
domain:          every distance an aggression can move the standing bet, from
                 one chip to a full raise, crossed with the two moves that can
                 make one (`bet` opening a street, `raise` answering a standing
                 bet). The distances are chosen so that one of them is EXACTLY
                 half a full raise, which is the boundary the rule's "or more"
                 decides and the only cell that separates `>=` from `>`.
registry:        the moves that can aggress, derived in `AGGRESSIONS` from
                 `libraries.load_library("poker_betting")` — a fifth move type
                 that clears `acted` arrives as a name this module does not
                 account for. What a seat is then OFFERED once its turn is or is
                 not restored is the sibling property, asserted over `acted` as
                 an axis in tests/test_poker_betting_offers.py; the two compose,
                 and neither restates the other.
does not prove:  a cell drives one aggression from a hand-built state, so this
                 says nothing about how many aggressions a street can hold end
                 to end — that is
                 tests/test_playout_holdem_heads_up.py's cap pin — nor about
                 what the aggression COSTS, which is
                 tests/test_poker_betting_sizing.py's.
"""

from __future__ import annotations

import random
from dataclasses import fields, is_dataclass
from typing import Any, Iterator, NamedTuple

import pytest

from cardlang.ast import nodes as n
from cardlang.libraries import load_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

LIBRARY = load_library("poker_betting")

def _walk(node: object) -> Iterator[object]:
    if is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


def _reopens_the_table(move: n.MoveTypeDef) -> bool:
    """Does this move's effect write `acted` for players OTHER than the actor?

    Walked from the effect's own tree rather than matched against its text: a
    per-player write is a `ForEach` with an assignment to `acted` somewhere
    inside it, and `acted[actor] := true` — which every move does — sits outside
    any loop and so cannot be mistaken for one.
    """
    return any(
        isinstance(node, n.NameRef) and node.name == "acted"
        for loop in _walk(move.effect)
        if isinstance(loop, n.ForEach)
        for node in _walk(loop)
    )


# The moves that re-open the betting, found by what their effects DO rather than
# by name, so a move type that starts clearing the table's turns cannot join the
# library without this grid driving it.
AGGRESSIONS: tuple[str, ...] = tuple(
    m.name for m in LIBRARY.move_types if _reopens_the_table(m)
)

# A bet size of 4 makes half a full raise exactly 2, so the boundary the rule
# names is an integer this grid can drive. At 5 it would fall between chips and
# the `>=` could never be told from `>`.
LIMIT = 4

# Where the standing bet sits when a `raise` answers it. ON-SIZE is the ordinary
# case; SUB_SIZE is a forced post shorter than the street — Stud brings in for 2
# on a street of 5 — and it is the only position that separates the yardstick
# below from the distance a full raise happens to travel FROM HERE. Completing a
# sub-size post moves the bet less than a full bet does, and it is a full bet the
# rule measures against, so the two come apart exactly here.
ON_SIZE = LIMIT
SUB_SIZE = 2


class Cell(NamedTuple):
    move: str
    standing: int  # the bet already on the table, 0 when `bet` opens the street
    moved: int  # how far this aggression shifts the standing bet

    @property
    def full(self) -> int:
        """A FULL BET, which is the street's size and nothing else.

        Not the distance a full raise would travel from the standing bet: those
        agree everywhere except from a post shorter than the street, and Pagat
        settles which one the rule means — "player A bets $4 and player B who
        has $6 left goes all-in, which is a raise of $2, i.e. HALF A FULL
        RAISE". Two against a street of four. The yardstick is the street.
        """
        return LIMIT

    @property
    def reopens(self) -> bool:
        """Robert's Rules 5: "An all-in wager of a half a bet or more is treated
        as a full bet". OR MORE — so exactly half re-opens, and the comparison
        is `>=`."""
        return self.moved * 2 >= self.full

    @property
    def id(self) -> str:
        share = {1: "under-half", 2: "exactly-half", 3: "over-half"}.get(
            self.moved, "full"
        )
        where = (
            "opening"
            if self.move == "bet"
            else "on-size"
            if self.standing == ON_SIZE
            else "sub-size"
        )
        return f"{self.move}-{where}-moves-{self.moved}-of-{self.full}-{share}"


def _cells() -> list[Cell]:
    out: list[Cell] = []
    for move in AGGRESSIONS:
        # `bet` opens a street, so there is no standing bet to answer; `raise`
        # answers one, and the position it answers from is an axis.
        standings = [0] if move == "bet" else [ON_SIZE, SUB_SIZE]
        for standing in standings:
            # One aggression can carry the bet as far as its target and no
            # further, both effects paying `min(what the rules want, what the
            # seat holds)`. From a sub-size post the target is the street's size
            # rather than a size beyond the post, so the reachable distances are
            # SHORTER there — which is the same fact that makes the position
            # discriminating, seen from the domain's side.
            target = LIMIT if standing < LIMIT else standing + LIMIT
            for moved in range(1, target - standing + 1):
                out.append(Cell(move=move, standing=standing, moved=moved))
    return out


CELLS = _cells()

_PROBE = """
game Reopening {{
  uses poker_betting
  players: 3
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{
    hero              : Player = 0
    witness           : Player = 1
    stack[player]     : Integer = 50
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 9
  }}
  phase play {{
    run open_street({limit})
    round offering [check] from 1
          over players where player is witness and not acted[player]
          until (number of players where acted[player]) is 1
    bet_to_match := {standing}
    raises := {raises}
    for each player p: bet_by[p] := 0
    for each player p: if p is hero {{ stack[p] := {hero_stack} }}
    round offering [{vocabulary}] from 0
          over players where player is hero
          until false
  }}
  winner: highest stack
}}
"""


class _Done(Exception):
    def __init__(self, witness_acted: bool, raises: int, standing: int) -> None:
        self.witness_acted = witness_acted
        self.raises = raises
        self.standing = standing


class Aftermath(NamedTuple):
    witness_turn_restored: bool
    aggression_counted: bool


def _drive(cell: Cell) -> Aftermath:
    """Prime one seat to have taken its turn, aggress by `cell.moved`, and read
    back whether that seat's turn was restored and whether the count moved.

    The distance is set by the aggressor's STACK rather than by any choice it
    makes: both effects pay `min(what the rules want, what the seat holds)`, so
    a seat holding exactly the standing bet plus `moved` can shift the bet by
    exactly that much and no further.
    """
    standing = cell.standing
    hero_stack = cell.moved if cell.move == "bet" else standing + cell.moved
    before_raises = 0 if cell.move == "bet" else 1
    source = _PROBE.format(
        limit=LIMIT,
        standing=standing,
        raises=before_raises,
        hero_stack=hero_stack,
        vocabulary=", ".join(m.name for m in LIBRARY.move_types),
    )
    game = check_dsl(source, "reopening.cardlang")
    box: list[Any] = []
    drawn = 0

    def on_first(state: Any) -> None:
        box.append(state)

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        nonlocal drawn
        drawn += 1
        if drawn == 1:
            return list(candidates[:count])  # the witness takes its turn
        if drawn == 2:
            offered = [name for name, _ in candidates]
            assert cell.move in offered, (
                f"{cell.id}: `{cell.move}` is not offered here ({offered}) — the "
                f"cell cannot drive the aggression it names"
            )
            return [next(c for c in candidates if c[0] == cell.move)]
        state = box[0]
        raise _Done(
            witness_acted=bool(state.get("acted")[1]),
            raises=int(state.get("raises")),
            standing=int(state.get("bet_to_match")),
        )

    try:
        play_game(game, random.Random(0), None, chooser, None, on_first)
    except _Done as done:
        assert done.standing - standing == cell.moved, (
            f"{cell.id}: the aggression moved the bet {done.standing - standing}, "
            f"not the {cell.moved} this cell is built to drive"
        )
        return Aftermath(
            witness_turn_restored=not done.witness_acted,
            aggression_counted=done.raises > before_raises,
        )
    raise AssertionError(f"{cell.id}: the probe never reached a third decision")


def test_the_aggression_registry_is_derived() -> None:
    """The two moves that re-open, found by what their effects DO.

    red under: delete the `for each player p: if ... { acted[p] := false }` line
    from `bet` in the library — `bet` drops out of the registry, the grid loses
    every `bet` cell, and this names it.
    """
    assert set(AGGRESSIONS) == {"bet", "raise"}, (
        f"the moves whose effects write another seat's `acted` are "
        f"{sorted(AGGRESSIONS)} — a move type that re-opens the betting must be "
        f"driven by this grid, and one that no longer does must leave it"
    )


@pytest.mark.parametrize("cell", CELLS, ids=[c.id for c in CELLS])
def test_only_a_half_bet_reopens_and_only_a_reopening_counts(cell: Cell) -> None:
    """One switch governs both consequences, so both are asserted per cell.

    Splitting them is how the two could drift apart — a library that re-opened
    on the threshold but counted unconditionally would give a street more
    aggressions than its cap names, and the cap pin could not see it because the
    cap would still be respected, just reached by wagers that were never raises.

    red under, four edits to the library, each RUN rather than predicted and
    each reddening exactly one cell:

    - `raise`'s `for each player p: if moved + moved >= full { … }` made
      unconditional — the pre-change behaviour — fails `raise-moves-1-of-4`;
    - `raise`'s `raises := if moved + moved >= full …` made `raises + 1`
      unconditionally — same cell, which is why both consequences are asserted
      together;
    - either `>=` in `raise` weakened to `>` — fails
      `raise-moves-2-of-4-exactly-half` and nothing else, which is the whole
      reason a bet size with a whole-number half is used;
    - `bet`'s pair made unconditional — fails `bet-moves-1-of-4`, so the
      `bet` half of the grid is proven to bite too and not carried by its
      sibling.
    """
    got = _drive(cell)
    want = Aftermath(
        witness_turn_restored=cell.reopens, aggression_counted=cell.reopens
    )
    assert got == want, (
        f"{cell.id}: moving the bet {cell.moved} of a full raise's {cell.full} "
        f"{'is' if cell.reopens else 'is not'} at least half, so it "
        f"{'re-opens and counts' if cell.reopens else 'is action only'}"
    )


def test_the_domain_reaches_both_sides_of_the_boundary() -> None:
    """The control: a grid entirely on one side of the threshold proves nothing.

    It also pins that the boundary itself is DRIVEN. "Half a bet or more" makes
    exactly-half re-open, so that cell is the only one where `>=` and `>` differ
    — every other cell passes under either, and an off-by-one here would be
    invisible without it.
    """
    assert any(c.reopens for c in CELLS), "no cell re-opens the betting"
    assert any(not c.reopens for c in CELLS), "no cell is action only"
    boundary = [c for c in CELLS if c.moved * 2 == c.full]
    assert boundary, (
        "no cell moves the bet by EXACTLY half a full raise, so this grid cannot "
        "tell `>=` from `>` — choose a bet size whose half is a whole number"
    )
    assert all(c.reopens for c in boundary), (
        "a cell at exactly half is expected not to re-open; Robert's Rules 5 "
        "says 'a half a bet OR MORE is treated as a full bet'"
    )


def test_the_domain_separates_the_street_size_from_the_completion_distance() -> None:
    """The control: the cells must be able to tell the two yardsticks apart.

    A full BET and the distance a full RAISE travels from the standing bet are
    the same number everywhere except from a post shorter than the street, so a
    domain whose standing bets all sat on a size would pass under either reading
    and prove nothing about which one the rule means. This asserts the domain
    contains a position that separates them, and a distance at which they
    actually disagree — the empty-input-set defect wearing a grid's clothes.

    Written because its absence let exactly that through: the first version of
    this module drove one standing bet, equal to the street size, and could not
    see a threshold computed from the completion distance.
    """
    separating = [
        c
        for c in CELLS
        if c.move == "raise"
        and c.standing < LIMIT
        and (c.moved * 2 >= LIMIT) != (c.moved * 2 >= LIMIT - c.standing)
    ]
    assert separating, (
        "no cell distinguishes a threshold measured against the street's size "
        "from one measured against the distance left to complete a short post — "
        "every standing bet in the domain must sit on a size"
    )
    assert {c.standing for c in CELLS if c.move == "raise"} == {ON_SIZE, SUB_SIZE}, (
        "the raise cells must answer a standing bet from BOTH positions; one of "
        "them alone cannot see which yardstick the threshold uses"
    )
