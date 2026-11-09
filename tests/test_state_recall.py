"""Perfect recall of the public state: every way a State Variable's rendering
can change between two decision nodes, held to what the seat remembers.

A seat's information state renders the State Variables in scope as they stand
(`cardlang/openspiel/infostate.py`). Each cell below is a complete game in
which seat 1 holds one concealed card, a value derived from that card reaches
seat 0's first decision through one write door, and the value converges
through the same door before seat 0's next decision. Two deals that differ
only in the concealed card's rank class separate seat 0 at its first
decision, so perfect recall requires that they separate it at every later
one.

property:        For every write door, two deals seat 0 told apart at its
                 first decision are told apart at every later decision of
                 seat 0, and a value written and overwritten with no decision
                 node between leaves the deals indistinguishable.
domain:          The write doors: every `AssignStmt` operator in the grammar's
                 `ASSIGN_OP` terminal crossed with both target shapes (a
                 scalar, and an indexed slot written in place), `rotate`, the
                 go-again flag a `turns` ring clears, and a phase-local
                 variable leaving scope as its phase ends; plus the implicit
                 flow, where only an `if` reading the concealed card chooses
                 which constant is written. The statement that selects a
                 write is outside this axis by construction: a State Delta
                 diffs the rendered state at each decision node, whatever
                 wrote it.
registry:        write sites: `cardlang.resolve._STATE_WRITE_SITES`;
                 operators: the `ASSIGN_OP` terminal of
                 `cardlang/grammar/cardlang.lark`; scope frames:
                 `RuntimeState.push_frame` / `pop_frame`; the corpus-wide
                 check over Constructed Worlds:
                 tests/openspiel_ready/test_ismcts.py::test_every_game_resamples_or_is_a_pinned_refusal.
held by:         Single owner. `chooser.decide` emits the State Delta for every
                 decision node through `observe.state_delta`, which diffs the
                 one rendering `observe.public_state` gives, so no write door
                 can bypass it; this grid is the executed witness of that
                 owner, one row per door.
does not prove:  That the zone half of a seat's view is recoverable from its
                 log — that rests on every zone change being observed (epic
                 #999). Nor anything about a game's own choice to publish a
                 concealed fact into state: a State Delta makes the seat
                 remember what it was shown, not whether showing it is honest
                 play (issue #471).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang import resolve
from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, run

GRAMMAR = Path(__file__).resolve().parent.parent / "cardlang" / "grammar" / "cardlang.lark"

HIGH = "number of cards in hand[1] where rank_value(card) >= 8"
LOW = "number of cards in hand[1] where rank_value(card) < 8"
HIGH_RANKS = frozenset({"8", "9", "10", "J", "Q", "K", "A"})
ASK = "as 0 { guess[0] := choose integer in 0 .. 1 }"


def _assign_ops() -> tuple[str, ...]:
    """The grammar's assignment operators, scraped from the terminal itself."""
    match = re.search(r"^ASSIGN_OP:\s*(.+)$", GRAMMAR.read_text(), re.MULTILINE)
    assert match is not None, "ASSIGN_OP terminal not found in the grammar"
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


@dataclass(frozen=True)
class Cell:
    door: str
    site: type[n.Stmt] | None  # the `_STATE_WRITE_SITES` member the door writes through
    state: str
    phases: str
    remembers: bool = True  # False: the value never reaches a decision node


def _game(cell: Cell) -> str:
    return f"""game Recall {{
  players: 2
  max_length: 8
  cards: standard52
  ranking: aces high
  zones {{
    deck         : Deck
    hand[player] : Hand<player>
  }}
  state {{
{cell.state}
    guess[player] : Integer = 0
  }}
  phase setup {{
    shuffle deck
    deal 1 card from deck to hand[1]
  }}
{cell.phases}
  winner: highest guess
}}
"""


def _assign_cell(op: str, indexed: bool) -> Cell:
    target = "v[1]" if indexed else "v"
    decl = "    v[player] : Integer = 0" if indexed else "    v : Integer = 0"
    first, second = {
        ":=": (f"{target} := {HIGH}", f"{target} := 0"),
        "+=": (f"{target} += {HIGH}", f"{target} += {LOW}"),
        "-=": (f"{target} -= {HIGH}", f"{target} -= {LOW}"),
    }[op]
    return Cell(
        f"assign {op} {'indexed' if indexed else 'scalar'}",
        n.AssignStmt,
        decl,
        f"  phase peek {{\n    {first}\n    {ASK}\n    {second}\n    {ASK}\n  }}",
    )


def _cells() -> list[Cell]:
    cells = [_assign_cell(op, indexed) for op in _assign_ops() for indexed in (False, True)]
    cells += [
        Cell(
            "rotate",
            n.RotateStmt,
            "    facing : SeatDirection = hold",
            f"""  phase peek {{
    if ({HIGH}) > 0 {{
      rotate facing through [left, right, across, hold]
    }}
    {ASK}
    if ({HIGH}) is 0 {{
      rotate facing through [left, right, across, hold]
    }}
    {ASK}
  }}""",
        ),
        Cell(
            "turns again",
            n.Turns,
            "    went_again : Boolean = false\n    done : Integer = 0",
            f"""  phase ring {{
    turns t from 1 over players where player is 1
          until done is 1
          again went_again {{
      went_again := any card in hand[1] where rank_value(card) >= 8
      {ASK}
      done := 1
    }}
    {ASK}
  }}""",
        ),
        Cell(
            "scope exit",
            None,
            "",
            f"""  phase peek {{
    state {{
      seen : Integer = 0
    }}
    seen := {HIGH}
    {ASK}
  }}
  phase after {{
    {ASK}
  }}""",
        ),
        Cell(
            "scope re-entry",
            None,
            "    round : Integer = 0",
            f"""  phase hands repeat until round >= 2 {{
    phase peek {{
      state {{
        seen : Integer = 0
      }}
      if round is 0 {{
        seen := {HIGH}
      }}
      {ASK}
      round += 1
    }}
  }}""",
        ),
        Cell(
            "scope shadow",
            None,
            "    seen : Integer = 0",
            f"""  phase peek {{
    seen := {HIGH}
    {ASK}
  }}
  phase inner {{
    state {{
      seen : Integer = 0
    }}
    {ASK}
  }}""",
        ),
        Cell(
            "keyed alias",
            n.AssignStmt,
            "    mark[player] : Integer = 0\n    copy[player] : Integer = 0",
            f"""  phase peek {{
    copy := mark
    mark[1] := {HIGH}
    {ASK}
    mark[1] := 0
    {ASK}
  }}""",
        ),
        Cell(
            "implicit flow",
            None,
            "    flag : Integer = 0",
            f"""  phase peek {{
    if ({HIGH}) > 0 {{ flag := 1 }} else {{ flag := 0 }}
    {ASK}
    flag := 0
    {ASK}
  }}""",
        ),
        Cell(
            "transient write",
            n.AssignStmt,
            "    flag : Integer = 0",
            f"  phase peek {{\n    flag := {HIGH}\n    flag := 0\n    {ASK}\n    {ASK}\n  }}",
            remembers=False,
        ),
    ]
    return cells


CELLS = _cells()


def _seat0_states(path: str, seed: int) -> list[str]:
    """Seat 0's information state at each of its decisions, every seat taking
    its first legal action, so two deals run the same picks."""
    states: list[str] = []
    history: tuple[int, ...] = ()
    while True:
        node = run(path, seed, history)
        if not isinstance(node, DecisionNode):
            return states
        if node.player == 0:
            states.append(information_state(0, node.rs, node.obs_logs[0]))
        history += (node.legal[0],)


def _deals(path: str) -> tuple[int, int]:
    """A seed dealing seat 1 a high card and one dealing it a low card."""
    found: dict[bool, int] = {}
    for seed in range(200):
        node = run(path, seed, ())
        assert isinstance(node, DecisionNode)
        (card,) = node.rs.zones.instance("hand", 1).cards
        found.setdefault(card.rank in HIGH_RANKS, seed)
        if len(found) == 2:
            return found[True], found[False]
    raise AssertionError("no pair of seeds dealt seat 1 both rank classes")


@pytest.mark.parametrize("cell", CELLS, ids=[c.door for c in CELLS])
def test_seat_remembers_the_public_state_it_was_shown(cell: Cell, tmp_path: Path) -> None:
    """Every forgetting cell ran red before the State Delta existed. The
    transient cell is the ruling's other half, born green: red under an
    assignment that delivers its value to every seat as it is written
    (`execute._assign` observing `("was", name, None, str(new))`)."""
    path = tmp_path / "recall.cardlang"
    path.write_text(_game(cell))
    high, low = _deals(str(path))
    a, b = _seat0_states(str(path), high), _seat0_states(str(path), low)
    assert len(a) == len(b) >= 2, f"{cell.door}: seat 0 must decide at least twice in both deals"
    if not cell.remembers:
        assert a == b, (
            f"{cell.door}: a value overwritten before any decision node reached "
            f"seat 0's information state\n  high: {a[0]}\n  low:  {b[0]}"
        )
        return
    assert a[0] != b[0], f"{cell.door}: the deals do not separate seat 0 at its first decision"
    for index in range(1, len(a)):
        assert a[index] != b[index], (
            f"{cell.door}: seat 0 forgot at decision {index} what it was shown at "
            f"decision 0\n  high: {a[index]}\n  low:  {b[index]}"
        )


def test_every_state_write_site_has_a_cell() -> None:
    """red under: a new member of `resolve._STATE_WRITE_SITES` with no cell
    here (append `(n.ForEach, "binder")` to the tuple)."""
    assert {cls for cls, _ in resolve._STATE_WRITE_SITES} <= {
        cell.site for cell in CELLS if cell.site is not None
    }


def test_every_assignment_operator_has_both_target_shapes() -> None:
    """The operator axis is the grammar's, not this module's: an operator added
    to `ASSIGN_OP` arrives here as two cells, or as a KeyError in
    `_assign_cell` naming it.
    red under: deleting `| "-="` from the `ASSIGN_OP` terminal."""
    ops = _assign_ops()
    assert set(ops) == {":=", "+=", "-="}
    doors = {cell.door for cell in CELLS}
    for op in ops:
        assert {f"assign {op} scalar", f"assign {op} indexed"} <= doors
