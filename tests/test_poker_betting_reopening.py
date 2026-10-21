"""Which aggressions re-open the betting, and which are action only.

property:        an aggression that leaves the bet standing at least half of a
                 FULL BET above the LAST FULL WAGER — the street's size, never
                 the distance a full raise happens to travel from here, and
                 measured from the level, never from the bet it answered — is
                 a raise for every purpose: it clears every other seat's turn,
                 so they are asked again with the right to re-raise, and it
                 spends one of the street's counted aggressions. One that
                 leaves the bet less than half a full bet above the level is
                 action only: no seat's turn is restored and no count is
                 spent, so the seats already in answer it with call or fold
                 alone. Pagat measures from the level in its own worked
                 example: over a $5 bet and a $6 all-in, an $8 all-in re-opens
                 "since the total raise since the last full bet is now $3".
domain:          every distance an aggression can move the standing bet, from
                 one chip to its target, crossed with the two moves that can
                 make one (`bet` opening a street, `raise` answering a standing
                 bet) and with where the standing bet sits against the level.
                 The distances are chosen so that one total is EXACTLY half
                 a full bet, which is the boundary the rule's "or more"
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

from tests.poker_probe import probe_betting

from cardlang.ast import nodes as n
from cardlang.libraries import load_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


@pytest.fixture(autouse=True)
def _probe_library() -> Iterator[None]:
    """The probes open their street with `probe_open_street`, which only the
    probe library holds (tests/poker_probe.py)."""
    with probe_betting():
        yield


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
# below from the two it is not: the distance moved from the standing bet, and
# the distance a full raise happens to travel FROM HERE. A post of one chip on a
# four-chip street separates both, at a one-chip move.
ON_SIZE = LIMIT
SUB_SIZE = 1

# The street's SECOND size, for the two moves that wager it. Twice the small
# bet, which is the family's own ladder (Stud runs 5 and 10). The yardstick
# below does NOT move with it: `floor` is the smallest wager that is a full one,
# and until a big wager is actually placed that is still the small bet — so a
# big wager falling short is measured against the small size exactly as a small
# one is. Holding the yardstick still is what keeps these cells comparable with
# their small twins, so the only thing the big arm varies is how far one
# aggression can travel.
BIG = 2 * LIMIT


class Cell(NamedTuple):
    move: str
    standing: int  # the bet already on the table, 0 when `bet` opens the street
    moved: int  # how far this aggression shifts the standing bet

    @property
    def level(self) -> int:
        """The last wager made in full when the cell's aggression is driven.

        An ON-SIZE standing bet IS one — a standing bet at or past the street
        with no full wager behind it is a state no play reaches, since a wager
        arriving there becomes the level itself. A SUB-SIZE standing bet is a
        forced post, which is exactly a bet nobody made in full.
        """
        return self.standing if self.standing >= LIMIT else 0

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
    def total(self) -> int:
        """How far the bet stands above the last full wager once the cell's
        aggression lands — Pagat's "total raise since the last full bet"."""
        return self.standing + self.moved - self.level

    @property
    def reopens(self) -> bool:
        """Pagat: an all-in "at least half the amount of a normal full bet or
        raise ... is treated as a full bet or raise". AT LEAST — so exactly
        half re-opens, and the comparison is `>=`."""
        return self.total * 2 >= self.full

    @property
    def id(self) -> str:
        share = {1: "under-half", 2: "exactly-half", 3: "over-half"}.get(
            self.total, "full"
        )
        where = (
            "opening"
            if self.standing == 0
            else "on-size"
            if self.standing == ON_SIZE
            else "sub-size"
        )
        return (
            f"{self.move}-{where}-moves-{self.moved}-"
            f"to-{self.total}-over-level-of-{self.full}-{share}"
        )


def _cells() -> list[Cell]:
    out: list[Cell] = []
    for move in AGGRESSIONS:
        # `bet` opens a street, so there is no standing bet to answer; `raise`
        # answers one, and the position it answers from is an axis.
        standings = [0] if move in ("bet", "bet_big") else [ON_SIZE, SUB_SIZE]
        size = BIG if move.endswith("_big") else LIMIT
        for standing in standings:
            # One aggression can carry the bet as far as its target and no
            # further, both effects paying `min(what the rules want, what the
            # seat holds)`. From a sub-size post the target is the street's size
            # rather than a size beyond the post, so the reachable distances are
            # SHORTER there — which is the same fact that makes the position
            # discriminating, seen from the domain's side.
            target = size if standing < LIMIT else standing + size
            small_target = LIMIT if standing < LIMIT else standing + LIMIT
            for moved in range(1, target - standing + 1):
                # A `_big` move is offered only where it can out-wager its
                # small twin: both pay `min(what the rules want, what the seat
                # holds)`, so a seat too short to pass the SMALL target posts
                # the same chips either way and the library suppresses the big
                # name rather than mint a second id for one action. Those
                # distances are therefore not cells of this grid — they are
                # the small twin's cells, which are already here, and a cell
                # generated for them could never drive the move it names.
                if move.endswith("_big") and standing + moved <= small_target:
                    continue
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
    level             : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 9
    big_raise_only    : Boolean = false
  }}
  phase play {{
    run probe_open_street({limit}, {big})
    turns t from 1
          over players where player is witness and not acted[player]
          until (number of players where acted[player]) is 1 {{
      offer to t one of [check]
    }}
    bet_to_match := {standing}
    level := {level}
    raises := {raises}
    for each player p: bet_by[p] := 0
    for each player p: if p is hero {{ stack[p] := {hero_stack} }}
    turns t from 0
          over players where player is hero
          until false {{
      offer to t one of [{vocabulary}, fold]
    }}
  }}
  winner: highest stack
}}
// The library contracts for the game's `fold`, and a game-own move type no
// reachable offer presents is refused: these probes measure the library's
// own moves, so the game's `fold` is offered beside them and never legal (no
// standing bet is negative).
move_type fold {{ when: bet_to_match < 0 effect {{ folded[actor] := true }} }}
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
    opens = cell.standing == 0
    hero_stack = cell.moved if opens else standing + cell.moved
    before_raises = 0 if opens else 1
    source = _PROBE.format(
        limit=LIMIT,
        big=BIG if cell.move.endswith("_big") else 0,
        standing=standing,
        level=cell.level,
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
    """The moves that re-open, found by what their effects DO — and each of
    them actually driven.

    The second half is not decoration. The `_big` arm's cells are generated
    CONDITIONALLY, because a big wager too short to pass its small twin's
    target is suppressed by the library rather than minted as a second id for
    one action. A guard that widened that suppression would empty the arm
    silently, and a registry check that only compared NAMES would stay green
    over a grid driving nothing.

    red under, both run: delete the `for each player p: if ... { acted[p] :=
    false }` line from `bet` in the library — `bet` drops out of the registry,
    the grid loses every `bet` cell, and the first assertion names it. For the
    second, widen `_cells`' twin filter to `if move.endswith("_big")`, which
    drops the arm wholesale: exactly this assertion fires, naming both moves.

    A library guard made unsatisfiable does NOT reach here — cells come from
    this module's own arithmetic, not from what the library offers, so they are
    still generated and fail one by one in
    `test_only_a_half_bet_reopens_and_only_a_reopening_counts` with "cannot
    drive the aggression it names" (measured: 4 rows). The two checks guard
    different things, and this one guards the FILTER.
    """
    assert set(AGGRESSIONS) == {"bet", "bet_big", "raise", "raise_big"}, (
        f"the moves whose effects write another seat's `acted` are "
        f"{sorted(AGGRESSIONS)} — a move type that re-opens the betting must be "
        f"driven by this grid, and one that no longer does must leave it"
    )
    driven = {cell.move for cell in CELLS}
    assert driven == set(AGGRESSIONS), (
        f"{sorted(set(AGGRESSIONS) - driven)} re-open the betting and this grid "
        f"generates no cell for them, so nothing here drives them at all"
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

    - `raise`'s `for each player p: if counts { … }` made unconditional —
      fails `raise-on-size-moves-1-to-1-over-level-of-4-under-half`;
    - `raise`'s `raises := if counts …` made `raises + 1` unconditionally —
      same cell, which is why both consequences are asserted together;
    - the `>=` in `raise`'s `counts` weakened to `>` — fails
      `raise-on-size-moves-2-to-2-over-level-of-4-exactly-half`, which is the
      whole reason a bet size with a whole-number half is used;
    - `bet`'s pair made unconditional — fails `bet-opening-moves-1-to-1-…`, so
      the `bet` half of the grid is proven to bite too and not carried by its
      sibling;
    - `raise`'s `moved` measured from `bet_to_match` rather than `level` —
      fails `raise-sub-size-moves-1-to-2-over-level-of-4-exactly-half`, the
      cell `test_the_domain_separates_the_three_yardsticks` keeps in the
      domain.
    """
    got = _drive(cell)
    want = Aftermath(
        witness_turn_restored=cell.reopens, aggression_counted=cell.reopens
    )
    assert got == want, (
        f"{cell.id}: leaving the bet {cell.total} over the last full wager, of "
        f"a full bet's {cell.full}, {'is' if cell.reopens else 'is not'} at "
        f"least half, so it "
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
    boundary = [c for c in CELLS if c.total * 2 == c.full]
    assert boundary, (
        "no cell moves the bet by EXACTLY half a full raise, so this grid cannot "
        "tell `>=` from `>` — choose a bet size whose half is a whole number"
    )
    assert all(c.reopens for c in boundary), (
        "a cell at exactly half is expected not to re-open; Pagat says 'AT "
        "LEAST half the amount of a normal full bet or raise' is a full one"
    )


def test_the_domain_separates_the_three_yardsticks() -> None:
    """The control: the cells must be able to tell the rule from its misreadings.

    The rule measures the TOTAL the bet stands above the last full wager
    against a FULL BET, the street's size. Two misreadings agree with it
    everywhere except from a post shorter than the street: measuring the
    distance moved from the STANDING bet, and measuring against the distance a
    full raise travels FROM HERE. A domain whose standing bets all sat on a
    size would pass under all three and prove nothing about which one the
    rule means; this asserts a cell where each misreading disagrees with the
    rule — the empty-input-set defect wearing a grid's clothes.

    red under: `SUB_SIZE` set equal to `ON_SIZE`, or to 2 — at a two-chip post
    every one-chip move reaches half the completion distance as well.
    """
    raises = [c for c in CELLS if c.move == "raise" and c.standing < LIMIT]
    from_standing = [
        c for c in raises if (c.moved * 2 >= LIMIT) != (c.total * 2 >= LIMIT)
    ]
    to_completion = [
        c
        for c in raises
        if (c.moved * 2 >= LIMIT - c.standing) != (c.total * 2 >= LIMIT)
    ]
    assert from_standing, (
        "no cell distinguishes a threshold measured from the last full wager "
        "from one measured from the standing bet — Pagat's '$3 since the last "
        "full bet' is the reading this grid must be able to see"
    )
    assert to_completion, (
        "no cell distinguishes a threshold measured against the street's size "
        "from one measured against the distance left to complete a short post"
    )
    assert {c.standing for c in CELLS if c.move == "raise"} == {ON_SIZE, SUB_SIZE}, (
        "the raise cells must answer a standing bet from BOTH positions; one of "
        "them alone cannot see which yardstick the threshold uses"
    )
