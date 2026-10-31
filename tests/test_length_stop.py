"""The Length Stop: a game that reaches its declared `max_length` ends there
as a tie, flagged in every channel, and a loop that makes no picks and never
ends is still refused as its author's defect (docs/decisions.md, "Game
length as a declared contract").

The grid crosses four axes, each cell a small game built from one template
that stops by length on every line:

- **site**, where the picks are made: a straight run of statements (the pick
  count alone), and inside each of the three iteration guards' loops (the
  phase-level `repeat until`, the statement-level `repeat until`, `turns`);
- **result clause**, the `winner:` target's index role crossed with its type,
  plus `loser:`;
- **position**, the decision point the picks are asked at, one per row of
  `delegation.DECISION_POINTS` with the round row fanned out by form, plus a
  decision inside a procedure (a Decision Episode);
- **channel**, where the end is reported: the driver's `GameResult`, the
  adapter's `TerminalNode` replaying the line, a `LiveLine`'s `LiveEnd`,
  `demo`'s summary and exit code, `play`'s summary and exit code, and the
  readiness harness's greedy walk, which feeds the coverage record.

Every template sets one seat ahead on the result clause's target before the
first pick and gives `loser:` a selection that names no seat, so a cell that
read either clause at the stop would name a winner or refuse; the default tie
reads neither.

Completeness ledger
-------------------
property:        a run that reaches `max_length` picks ends there, after
                 exactly `max_length` picks on every route, as a tie (every
                 seat a winner, no loser, zero returns) flagged
                 `ended_by == length`, in every channel the pyspiel State
                 included; a loop whose `until` does not hold at a head after
                 more than `max_length` bodies with no pick in them is
                 refused, and one whose `until` holds there is not.
domain:          SITES x CLAUSES x POSITIONS x CHANNELS below; the sites are
                 the pick count alone and every loop the decisionless-spin
                 guard counts, the climbing round's ring through the climb
                 position. The adapter
                 numbers no inline `where jointly` pick
                 (`ActionSpace.for_game` refuses the game before a run), so
                 the joint position's adapter-routed channels expect that
                 refusal, and its `demo` and `GameResult` cells run natively.
                 The decisionless-spin rows cover each iteration guard; the
                 alternating rows cover a loop whose picks fall on some
                 boundaries only; the boundary rows cover an `until` holding
                 after exactly `max_length` and `max_length + 1` decisionless
                 bodies at each statement-shaped loop, and refused one body
                 later. A climbing round's `until` is read only once a play
                 stands, so a ring that asks nobody never reaches it: its row
                 is the refusal alone. A Hosted Poll's ask is a round's
                 decision point, not a row of its own, and its stop is
                 Tichu's under the uniform Chooser.
registry:        clause axis: `driver.SEAT_KEY_BY_ROLE` x
                 `resolve._RANKABLE_TYPES`, plus `loser:`; position axis:
                 `delegation.DECISION_POINTS` and `delegation.FORM_CONSTRUCTS`,
                 reconciled by `test_the_positions_are_the_decision_points`
                 and reached by `test_each_position_asks_at_its_decision_point`;
                 site axis: the constructions of `state.DecisionlessSpin`,
                 reconciled by `test_every_spin_guard_is_a_grid_row`;
                 channel axis: `EndedBy` members by
                 `test_ended_by_has_two_arms`; the Hosted Poll's stop:
                 tests/test_length_registry_pin.py::test_tichu_under_the_uniform_chooser_is_a_length_stop;
                 a chosen movement's source visible to its decider:
                 tests/test_rejections.py::test_rejection_case[hidden_read_blind_draw].
held by:         the end's kind is a closed enum (`driver.EndedBy`) every
                 consumer matches exhaustively (Unrepresentable); the one
                 counting site is `chooser.decide`'s Contract, pinned here by
                 the picks each cell counts (Derived and Pinned).
does not prove:  that a corpus game ends by its rules (the registry pin,
                 tests/test_length_registry_pin.py, measures that), or that
                 the stop is common knowledge to every seat (the swap proof's
                 terminal assertion in tests/openspiel_ready/harness.py and
                 the corollary pin in tests/test_zone_projections.py).
"""

from __future__ import annotations

import ast
import io
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import cardlang
from cardlang.cli import main
from cardlang.domains import Role
from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.replay import HistoryMismatch, LiveLine, TerminalNode, load, run
from cardlang.openspiel.seat_policy import FirstSeatPolicy
from cardlang.pipeline import check_dsl, check_source
from cardlang.resolve import _RANKABLE_TYPES
from cardlang.runtime import chooser as chooser_module
from cardlang.runtime import evaluate, execute, mechanics
from cardlang.runtime.delegation import DECISION_POINTS, FORM_CONSTRUCTS
from cardlang.runtime.driver import SEAT_KEY_BY_ROLE, GameResult, play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import RuntimeState

FIXTURES = Path(__file__).parent / "fixtures"
SHUTTLE = FIXTURES / "shuttle.cardlang"
STRADDLE = FIXTURES / "straddle.cardlang"
SPIN = FIXTURES / "decisionless_spin.cardlang"

BOUND = 4  # every cell's `max_length`
SEED = 1


def _ended_by(thing: object) -> object:
    """The `ended_by` arm's value, read without importing the enum, so the
    grid collects on a tree that has none."""
    return getattr(getattr(thing, "ended_by", None), "value", None)


# --- the result-clause axis ---------------------------------------------------


@dataclass(frozen=True)
class Clause:
    decl: str      # the target's declaration
    lead: str      # the setup line putting one side ahead
    result: str    # the result clause
    teamed: bool


def _winner_clause(role: Role, type_name: str) -> Clause:
    teamed = role is Role.TEAM
    index = "team" if teamed else "player"
    if type_name == "Integer":
        return Clause(f"target[{index}] : Integer = 0", "target[0] := 5", "winner: highest target", teamed)
    assert type_name == "Boolean", type_name
    return Clause(f"target[{index}] : Boolean = true", "target[1] := false", "winner: highest target", teamed)


CLAUSES: dict[str, Clause] = {
    **{
        f"winner-{role.name.lower()}-{type_name}": _winner_clause(role, type_name)
        for role in SEAT_KEY_BY_ROLE
        for type_name in sorted(_RANKABLE_TYPES)
    },
    # A selection that names no seat: read at the stop, it would refuse.
    "loser": Clause(
        "target[player] : Integer = 0",
        "target[0] := 5",
        "loser: the player where target[player] > 1000",
        False,
    ),
}


# --- the position axis --------------------------------------------------------


@dataclass(frozen=True)
class Position:
    point: str          # the DECISION_POINTS row its picks are asked at
    form: str | None    # the round form, for the round row
    snippet: str        # `{who}` is the acting seat
    tail: str = ""      # the definitions the snippet names
    numbered: bool = True  # whether the adapter numbers its picks


_TICK = "\nmove_type tick { effect { ticks += 1 } }\n"
_SETS = """
combinations sets {
  single: 1 card
  pair:   2 of a kind
}

function beats(play : Combination, standing : Combination?) =
  standing is none
  or ((number of cards in play) is (number of cards in standing)
      and (highest rank_value(card) over cards in play or 0)
          > (highest rank_value(card) over cards in standing or 0))
"""

POSITIONS: dict[str, Position] = {
    "offer": Position("execute._offer", None, "offer to {who} one of [tick]", _TICK),
    "transfer": Position("execute._select_from", None, "move chosen 3 cards from hand[{who}] to pile"),
    "filtered": Position(
        "execute._select_filtered",
        None,
        "move chosen 3 cards from hand[{who}] where rank_value(card) >= 0 to pile",
    ),
    "joint": Position(
        "execute._select_joint",
        None,
        "move chosen some cards from hand[{who}] where jointly (number of cards in cards) is 1 to pile",
        numbered=False,
    ),
    "simultaneous": Position(
        "execute._pass_selection",
        None,
        "each player simultaneously:\n          move chosen 3 cards from hand[player] to pile",
    ),
    "choose": Position("evaluate._choose", None, "picked := choose integer in 1 .. 3"),
    "trick": Position(
        "mechanics.run_decision_round",
        "TrickRound",
        "round play_to_trick from 0 over all players\n"
        "          source hand into trick_pile winner highest_of_led_suit\n"
        "        move all cards from trick_pile to pile",
    ),
    "climb": Position(
        "mechanics.run_decision_round",
        "ClimbRound",
        "round climb play_combination from 0 over all players\n"
        "          source hand into trick_pile combinations sets follows beats\n"
        "          until ticks > 100\n"
        "        move all cards from trick_pile to pile",
        _SETS,
    ),
    # The decision sits inside a procedure's body, spliced at its call.
    "procedure": Position(
        "execute._offer",
        None,
        "run asking({who})",
        _TICK + "\nprocedure asking(who : Player) {\n  as who {\n    offer to who one of [tick]\n  }\n}\n",
    ),
    # A Decision Episode: a flag window, an offer-bearing `repeat until` gated
    # on a Boolean state variable, open (non-idle) while its offers are asked.
    "episode": Position(
        "execute._offer",
        None,
        "window_open := true\n"
        "        repeat until not window_open {{\n"
        "          offer to {who} one of [tick]\n"
        "        }}\n"
        "        window_open := false",
        _TICK,
    ),
}


# --- the site axis ------------------------------------------------------------

# The guard each loop site is counted by (`state.DecisionlessSpin`'s
# constructions), and the climbing round's ring, which the climb position's
# own plays are made inside.
SPIN_GUARDS: dict[str, str] = {
    "driver.run_phase": "phase repeat until",
    "execute._repeat_until": "statement repeat until",
    "execute._turns": "turns",
    "mechanics.ClimbForm.next_actor": "climb",
}

SITES: dict[str, str] = {
    # More statements than the bound has picks, and no loop at all.
    "pick count": "  phase play {{\n{five}\n  }}",
    "phase repeat until": "  phase play repeat until false {{\n{one}\n  }}",
    "statement repeat until": "  phase play {{\n    repeat until false {{\n{one}\n    }}\n  }}",
    "turns": "  phase play {{\n    turns t from 0 over all players until false {{\n{turn}\n    }}\n  }}",
}


def cell_source(site: str, clause_name: str, position: str) -> str:
    clause = CLAUSES[clause_name]
    snippet = POSITIONS[position].snippet
    one = "      as 0 {\n        " + snippet.format(who="0") + "\n      }"
    turn = "      as t {\n        " + snippet.format(who="t") + "\n      }"
    teams = "  teams: [[0, 2], [1, 3]]\n" if clause.teamed else ""
    return (
        "game Cell {\n"
        f"  players: {4 if clause.teamed else 2}\n"
        "  direction: clockwise\n"
        f"  max_length: {BOUND}\n"
        f"{teams}"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones {\n"
        "    deck         : Deck\n"
        "    hand[player] : Hand<player>\n"
        "    pile         : Discard\n"
        "    trick_pile   : TrickPile\n"
        "  }\n"
        "  state {\n"
        f"    {clause.decl}\n"
        "    ticks  : Integer = 0\n"
        "    picked : Integer = 0\n"
        "    window_open : Boolean = false\n"
        "  }\n"
        "  phase setup {\n"
        "    shuffle deck\n"
        "    deal 12 cards from deck to each hand\n"
        f"    {clause.lead}\n"
        "  }\n"
        + SITES[site].format(five="\n".join([one] * 5), one=one, turn=turn)
        + f"\n  {clause.result}\n}}\n"
        + POSITIONS[position].tail
    )


_PATHS: dict[tuple[str, str, str], str] = {}


@pytest.fixture(scope="module")
def cell_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("length_stop_cells")


def cell_path(cell_dir: Path, site: str, clause: str, position: str) -> str:
    key = (site, clause, position)
    if key not in _PATHS:
        path = cell_dir / f"{'_'.join(k.replace(' ', '-') for k in key)}.cardlang"
        path.write_text(cell_source(site, clause, position))
        _PATHS[key] = str(path)
    return _PATHS[key]


# --- the channel axis ---------------------------------------------------------


def _first(view: Any, legal: Any) -> int:
    return FirstSeatPolicy()(view, legal)


def _seats(clause: str) -> int:
    return 4 if CLAUSES[clause].teamed else 2


def _assert_tie(winners: frozenset[int], loser: object, returns: list[float] | None, seats: int) -> None:
    assert winners == frozenset(range(seats)), f"winners {sorted(winners)}: a stop is a tie"
    assert loser is None, f"a stop names no loser, got {loser!r}"
    if returns is not None:
        assert returns == [0.0] * seats, f"returns {returns}: a tie pays every seat 0"


def channel_result(path: str, clause: str) -> None:
    """The driver's own result, under the uniform Chooser that answers a call
    all at once."""
    game = check_source(Path(path))
    world: list[RuntimeState] = []
    result = play_game(game, random.Random(SEED), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert world[0].decisions_made == BOUND
    _assert_tie(result.winners, result.loser, None, _seats(clause))


def channel_terminal_node(path: str, clause: str) -> None:
    """The adapter's node for the line a `first` table plays, replayed from
    its history, and a pick past the bound refused as a mismatch."""
    line = LiveLine(path, SEED)
    line.play({seat: _first for seat in range(_seats(clause))})
    assert len(line.history) == BOUND
    node = run(path, SEED, tuple(line.history))
    assert isinstance(node, TerminalNode)
    assert _ended_by(node) == "length"
    assert node.returns == [0.0] * _seats(clause)
    with pytest.raises(HistoryMismatch):
        run(path, SEED, (*line.history, line.history[-1]))


def channel_live_end(path: str, clause: str) -> None:
    line = LiveLine(path, SEED)
    end = line.play({seat: _first for seat in range(_seats(clause))})
    assert _ended_by(end) == "length"
    assert end.returns == [0.0] * _seats(clause)
    assert len(line.history) == BOUND
    assert set(end.views) == set(range(_seats(clause))), "every seat's view at the stop"


def channel_demo(path: str, clause: str, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["demo", path, "--seed", str(SEED)])
    out, err = capsys.readouterr()
    first = out.splitlines()[0] if out else ""
    assert "reached" in first and "max_length" in first and "tie" in first, first
    assert f"decisions    {BOUND}" in out
    assert "non-termination" not in out + err
    assert "static checks passed" not in out + err
    assert code == 1


def channel_play(path: str, clause: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("1\n" * (BOUND + 2) + "q\n"))
    code = main(["play", path, "--seed", str(SEED), "--vs", "all=first"])
    out, err = capsys.readouterr()
    assert "the game is over" in out
    over = out[out.index("the game is over"):]
    assert "reached its max_length" in over and "tie" in over, over
    assert "P0 was you" in over
    assert "non-termination" not in out + err
    assert "static checks passed" not in out + err
    assert code == 0, err


def channel_coverage(path: str, clause: str) -> None:
    """The readiness harness's greedy walk, whose end the coverage record
    carries."""
    pytest.importorskip("pyspiel")
    from tests.openspiel_ready.harness import greedy_line

    line, returns, ended_by = greedy_line(path, SEED, BOUND)
    assert len(line) == BOUND
    assert returns == [0.0] * _seats(clause)
    assert getattr(ended_by, "value", None) == "length"


def channel_pyspiel(path: str, clause: str) -> None:
    """The registered pyspiel game, walked by its first legal action: terminal
    after exactly the bound, its State saying the bound ended it."""
    pyspiel = pytest.importorskip("pyspiel")
    from cardlang.openspiel.game import register_game_file

    state = pyspiel.load_game(register_game_file(path)).new_initial_state()
    steps = 0
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
            continue
        assert state.ended_by() is None
        state.apply_action(state.legal_actions()[0])
        steps += 1
    assert steps == BOUND
    assert state.ended_by() == "length"
    assert state.returns() == [0.0] * _seats(clause)


CHANNELS: dict[str, Callable[..., None]] = {
    "GameResult": channel_result,
    "TerminalNode": channel_terminal_node,
    "LiveEnd": channel_live_end,
    "pyspiel State": channel_pyspiel,
    "demo": channel_demo,
    "play": channel_play,
    "coverage record": channel_coverage,
}

# The channels that reach the game through the adapter's action space.
ADAPTER_CHANNELS = frozenset({"TerminalNode", "LiveEnd", "pyspiel State", "play", "coverage record"})


def expected(site: str, clause: str, position: str, channel: str) -> str:
    """The design column. `stop`: the cell ends by length as a tie, flagged.
    `unnumbered`: the adapter refuses the game before any run, a cell born
    green. red under: let `ActionSpace.for_game` number an inline
    `where jointly` pick."""
    if channel in ADAPTER_CHANNELS and not POSITIONS[position].numbered:
        return "unnumbered"
    return "stop"


def _cells() -> list[Any]:
    out = []
    for site in SITES:
        for clause in CLAUSES:
            for position in POSITIONS:
                for channel in CHANNELS:
                    want = expected(site, clause, position, channel)
                    out.append(
                        pytest.param(
                            site, clause, position, channel, want,
                            id=f"{site}|{clause}|{position}|{channel}",
                        )
                    )
    return out


@pytest.mark.parametrize(("site", "clause", "position", "channel", "want"), _cells())
def test_the_length_stop_grid(
    site: str,
    clause: str,
    position: str,
    channel: str,
    want: str,
    cell_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = cell_path(cell_dir, site, clause, position)
    if want == "unnumbered":
        with pytest.raises(NotImplementedError):
            ActionSpace.for_game(check_source(Path(path)))
        return
    run_channel = CHANNELS[channel]
    if channel == "demo":
        run_channel(path, clause, capsys)
    elif channel == "play":
        run_channel(path, clause, capsys, monkeypatch)
    else:
        run_channel(path, clause)


# --- the axes, reconciled against their registries -----------------------------


def test_the_positions_are_the_decision_points() -> None:
    """Every decision point is a position, and the round row is crossed with
    every form. red under: add a row to `DECISION_POINTS`."""
    assert {p.point for p in POSITIONS.values()} == set(DECISION_POINTS)
    round_forms = {p.form for p in POSITIONS.values() if p.point == "mechanics.run_decision_round"}
    assert round_forms == set(FORM_CONSTRUCTS)


@pytest.mark.parametrize("position", sorted(POSITIONS))
def test_each_position_asks_at_its_decision_point(
    position: str, cell_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The position's fixture reaches its own row of the decision-point table
    and no other, so the position axis is the table's and not a name.
    red under: write `transfer`'s snippet with a `where` filter."""
    seen: set[tuple[str, str | None]] = set()
    decide = chooser_module.decide

    def recording(ctx: Any, decider: Any, candidates: Any, n: int, site: str,
                  destination: Any = None, construct: Any = None) -> Any:
        seen.add((site, construct))
        return decide(ctx, decider, candidates, n, site, destination, construct)

    for module in (execute, mechanics, evaluate):
        monkeypatch.setattr(module, "decide", recording)
    game = check_source(Path(cell_path(cell_dir, "statement repeat until", "winner-player-Integer", position)))
    try:
        play_game(game, random.Random(SEED))
    except OwnerGuardError:
        pass
    row = POSITIONS[position]
    construct = FORM_CONSTRUCTS[row.form] if row.form is not None else None
    assert seen == {(row.point, construct)}


def _spin_guard_sites() -> set[str]:
    """`module.function` (or `module.Class.method`) of every construction of
    `DecisionlessSpin` in the package, read from source."""
    root = Path(str(cardlang.__file__)).parent
    found: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text())
        module = path.stem

        def walk(node: ast.AST, scope: list[str]) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    walk(child, [*scope, child.name])
                    continue
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "DecisionlessSpin"
                ):
                    found.add(".".join([module, *scope]))
                walk(child, scope)

        walk(tree, [])
    return found


def test_every_spin_guard_is_a_grid_row() -> None:
    """Every loop the decisionless-spin guard counts is a site of the grid, or
    the climb position for the climbing round's ring, so a fifth loop cannot
    arrive unlisted. red under: construct a `DecisionlessSpin` in a new
    function."""
    assert _spin_guard_sites() == set(SPIN_GUARDS)
    for row in SPIN_GUARDS.values():
        assert row in SITES or row in POSITIONS, row
    assert set(SITES) - {"pick count"} == {
        row for row in SPIN_GUARDS.values() if row in SITES
    }


def test_ended_by_has_two_arms() -> None:
    from cardlang.runtime.driver import EndedBy

    assert {arm.value for arm in EndedBy} == {"rules", "length"}


# --- the iteration guards: refused only for a decisionless spin ---------------

_SPINS = {
    "phase repeat until": "  phase spin repeat until false {\n  }\n",
    "statement repeat until": "  phase spin {\n    repeat until false {\n    }\n  }\n",
    "turns": "  phase spin {\n    turns t from 0 over all players until false {\n      ticks += 1\n    }\n  }\n",
}


def _spin_game(site: str) -> str:
    return (
        "game Spin {\n"
        "  players: 2\n"
        "  max_length: 5\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { n[player] : Integer = 0  ticks : Integer = 0 }\n"
        "  phase opening { as 0 { offer to 0 one of [tick] } }\n"
        f"{_SPINS[site]}"
        "  winner: highest n\n"
        "}\n"
        + _TICK
    )


@pytest.mark.parametrize("site", sorted(_SPINS))
def test_a_decisionless_spin_is_refused(site: str) -> None:
    """A loop that completes more than `max_length` bodies with no pick in
    them, its `until` still false, is the author's defect, refused after a
    pick has been made, in words naming what the loop lacks and how many
    bodies it ran."""
    game = check_dsl(_spin_game(site), "spin.cardlang")
    with pytest.raises(OwnerGuardError) as refused:
        play_game(game, random.Random(0))
    message = str(refused.value)
    assert "completed 6 times with no decision made" in message
    assert "max_length (5)" in message
    assert "non-termination" in message


_CLIMB_SPIN = """game ClimbSpin {
  players: 2
  max_length: 5
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { n[player] : Integer = 0 }
  phase play {
    round climb play_combination from 0 over all players
          source hand into trick_pile combinations sets follows beats
          until false
  }
  winner: highest n
}
""" + _SETS


def test_a_climbing_ring_that_asks_nobody_is_refused() -> None:
    """Nobody holds a card, so the ring skips every seat and asks no one: past
    `max_length` steps it is refused, with the climbing round's remedies."""
    game = check_dsl(_CLIMB_SPIN, "climb_spin.cardlang")
    with pytest.raises(OwnerGuardError) as refused:
        play_game(game, random.Random(0))
    message = str(refused.value)
    assert "a climbing round's ring completed 6 times with no decision made" in message
    assert "max_length (5)" in message
    assert "drop players who can never play from the `over` clause" in message


# The statement-shaped loops, each running decisionless bodies until a lap
# count reaches `{k}`.
_LAPS = {
    "phase repeat until": "  phase spin repeat until laps >= {k} {{\n    laps += 1\n  }}\n",
    "statement repeat until": (
        "  phase spin {{\n    repeat until laps >= {k} {{\n      laps += 1\n    }}\n  }}\n"
    ),
    "turns": (
        "  phase spin {{\n    turns t from 0 over all players until laps >= {k} {{\n"
        "      laps += 1\n    }}\n  }}\n"
    ),
}

_SPIN_BOUND = 5


@pytest.mark.parametrize(
    ("site", "bodies", "refused"),
    [
        (site, bodies, bodies > _SPIN_BOUND + 1)
        for site in sorted(_LAPS)
        for bodies in (_SPIN_BOUND, _SPIN_BOUND + 1, _SPIN_BOUND + 2)
    ],
)
def test_an_until_holding_at_the_bound_ends_by_its_rules(site: str, bodies: int, refused: bool) -> None:
    """The loop's `until` holds once `bodies` decisionless bodies have run. At
    `max_length` and `max_length + 1` bodies it holds at the head where the
    count is read, so the loop ends by its rules; one body later the head
    finds `max_length + 1` decisionless bodies and an `until` still false."""
    game = check_dsl(
        "game Laps {\n  players: 2\n"
        f"  max_length: {_SPIN_BOUND}\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { n[player] : Integer = 0  laps : Integer = 0 }\n"
        + _LAPS[site].format(k=bodies)
        + "  winner: highest n\n}\n",
        "laps.cardlang",
    )
    if refused:
        with pytest.raises(OwnerGuardError) as refusal:
            play_game(game, random.Random(0))
        assert f"completed {_SPIN_BOUND + 1} times" in str(refusal.value)
        return
    result = play_game(game, random.Random(0))
    assert _ended_by(result) == "rules"


# A loop whose picks fall on every other boundary: its boundaries outrun the
# bound before its picks reach it.
_ALTERNATING = {
    "phase repeat until": (
        "  phase play repeat until false {\n"
        "    flip := not flip\n"
        "    if flip { as 0 { offer to 0 one of [tick] } }\n"
        "  }\n"
    ),
    "statement repeat until": (
        "  phase play {\n    repeat until false {\n"
        "      flip := not flip\n"
        "      if flip { as 0 { offer to 0 one of [tick] } }\n"
        "    }\n  }\n"
    ),
    "turns": (
        "  phase play {\n    turns t from 0 over all players until false {\n"
        "      flip := not flip\n"
        "      if flip { offer to t one of [tick] }\n"
        "    }\n  }\n"
    ),
}


@pytest.mark.parametrize(
    "site",
    sorted(_ALTERNATING),
)
def test_a_loop_making_picks_on_some_boundaries_stops_by_length(site: str) -> None:
    game = check_dsl(
        "game Alternating {\n"
        "  players: 2\n"
        "  max_length: 5\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { n[player] : Integer = 0  ticks : Integer = 0  flip : Boolean = false }\n"
        f"{_ALTERNATING[site]}"
        "  winner: highest n\n"
        "}\n" + _TICK,
        "alternating.cardlang",
    )
    world: list[RuntimeState] = []
    result = play_game(game, random.Random(0), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert world[0].decisions_made == 5


# --- the world a stop scores ----------------------------------------------------


def test_a_stop_runs_no_statement_past_the_stopped_pick() -> None:
    """The stop falls inside an iteration: its `after_each` does not run, the
    statement after the stopped pick does not run, every frame stands and the
    `game_end` trace fires."""
    game = check_dsl(
        "game Standing {\n"
        "  players: 2\n"
        "  max_length: 3\n"
        "  cards: standard52\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { n[player] : Integer = 0  ticks : Integer = 0  after : Integer = 0  past : Integer = 0 }\n"
        "  phase play repeat until false {\n"
        "    after_each { after += 1 }\n"
        "    as 0 { offer to 0 one of [tick] }\n"
        "    as 1 { offer to 1 one of [tick] }\n"
        "    past += 1\n"
        "  }\n"
        "  winner: highest n\n"
        "}\n" + _TICK,
        "standing.cardlang",
    )
    world: list[RuntimeState] = []
    traced: list[str] = []
    result = play_game(
        game, random.Random(0), lambda event, _data: traced.append(event),
        on_first_decision=world.append,
    )
    assert _ended_by(result) == "length"
    rs = world[0]
    assert rs.get("ticks") == 3, "three picks were applied"
    assert rs.get("past") == 1, "the statement after the stopped pick did not run"
    assert rs.get("after") == 1, "no after_each ran past the stop"
    assert len(rs.frames) == 2, "the game frame and the phase frame stand"
    assert traced[-1] == "game_end"


# --- the route agreement on a straddling call -----------------------------------


def test_native_and_replay_routes_stop_a_straddling_call_at_one_length() -> None:
    """A call for three picks against a bound of two: the native Chooser
    answers all three at once and the third is discarded, the replay route
    is stopped before it asks the third; both record two picks, apply none,
    and leave the decider one `asked`."""
    path = str(STRADDLE)
    game = check_source(STRADDLE)
    logs: dict[int, list[tuple[Any, ...]]] = {0: [], 1: []}
    world: list[RuntimeState] = []
    result = play_game(
        game, random.Random(SEED),
        observer=lambda seat, event: logs[seat].append(event),
        on_first_decision=world.append,
    )
    assert _ended_by(result) == "length"
    native = [e[0] for e in logs[0] if e[0] in ("asked", "chose")]
    assert native == ["asked", "chose", "chose"]
    assert world[0].decisions_made == 2
    assert len(world[0].zones.single("pile").cards) == 0, "a straddled call applies no pick"

    line = LiveLine(path, SEED)
    end = line.play({0: _first, 1: _first})
    assert _ended_by(end) == "length"
    assert len(line.history) == 2
    node = run(path, SEED, tuple(line.history))
    assert isinstance(node, TerminalNode)
    replayed = [e[0] for e in node_logs(path, tuple(line.history))[0] if e[0] in ("asked", "chose")]
    assert replayed == native


def node_logs(path: str, history: tuple[int, ...]) -> dict[int, list[tuple[Any, ...]]]:
    from cardlang.openspiel.replay import Seen

    logs: dict[int, list[tuple[Any, ...]]] = {}

    def listen(moment: object) -> None:
        if isinstance(moment, Seen):
            logs.setdefault(moment.player, []).append(moment.event)

    run(path, SEED, history, listen=listen)
    return logs


def test_a_call_beginning_at_the_bound_is_never_asked() -> None:
    """The first call fills the bound exactly, so the pick past it is the
    first of the next call: that call's decider is not told it is being
    asked."""
    filled = check_dsl(
        STRADDLE.read_text().replace("max_length: 2", "max_length: 3"), "straddle3.cardlang"
    )
    logs: dict[int, list[tuple[Any, ...]]] = {0: [], 1: []}
    result = play_game(
        filled, random.Random(SEED), observer=lambda seat, event: logs[seat].append(event)
    )
    assert _ended_by(result) == "length"
    assert [e[0] for e in logs[0] if e[0] in ("asked", "chose")] == ["asked", "chose", "chose", "chose"]
    assert not [e for e in logs[1] if e[0] == "asked"], "the second call stops before its `asked`"


# --- the bounded game the registry pin plants ------------------------------------

TIC_TAC_TOE = Path(__file__).parent.parent / "docs" / "games" / "tic-tac-toe.cardlang"


def bounded_tic_tac_toe() -> str:
    """Tic-tac-toe declaring `max_length: 5`: a game bounded by its rules at
    nine placements, given a bound it can reach before any line is decided.
    The registry pin's planted fault (tests/test_length_registry_pin.py)."""
    text = TIC_TAC_TOE.read_text()
    assert "  max_length: 30\n" in text, "the corpus file's bound moved; re-derive the plant"
    return text.replace("  max_length: 30\n", "  max_length: 5\n")


def test_a_one_pick_turn_stops_by_the_pick_count_with_the_turns_guard_silent() -> None:
    """One placement per turn and a bound of five: the sixth turn boundary is
    reached with five picks made, and what ends the game is the sixth pick,
    never the `turns` guard counting its boundaries."""
    game = check_dsl(bounded_tic_tac_toe(), "p6_bounded_game_short_bound.cardlang")
    ends: dict[object, int] = {}
    for seed in range(10):
        world: list[RuntimeState] = []
        result = play_game(game, random.Random(seed), on_first_decision=world.append)
        ends[_ended_by(result)] = ends.get(_ended_by(result), 0) + 1
        if _ended_by(result) == "length":
            assert world[0].decisions_made == 5
            _assert_tie(result.winners, result.loser, None, 2)
    assert ends.get("length", 0) > 0, ends


# --- the solved first witness ----------------------------------------------------


@pytest.mark.parametrize("seed", range(5))
def test_the_shuttle_stops_at_exactly_its_bound_as_a_tie(seed: int) -> None:
    """Every line of the shuttle is infinite and its value is a tie by
    construction, so a stop at any other length, a winner, or a nonzero
    return is a contradiction rather than a plausible number."""
    game = check_source(SHUTTLE)
    assert game.max_length is not None
    world: list[RuntimeState] = []
    result: GameResult = play_game(game, random.Random(seed), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert world[0].decisions_made == game.max_length
    _assert_tie(result.winners, result.loser, None, 2)

    line = LiveLine(str(SHUTTLE), seed)
    end = line.play({0: _first, 1: _first})
    assert _ended_by(end) == "length"
    assert len(line.history) == game.max_length
    assert end.returns == [0.0, 0.0]


def test_the_shuttle_is_terminal_in_openspiel_after_exactly_its_bound() -> None:
    pyspiel = pytest.importorskip("pyspiel")
    from cardlang.openspiel.game import register_game_file

    game_ast = check_source(SHUTTLE)
    short = register_game_file(SHUTTLE)
    game = pyspiel.load_game(short)
    assert game.max_game_length() == game_ast.max_length
    state = game.new_initial_state()
    steps = 0
    while not state.is_terminal():
        assert steps < game.max_game_length(), "the adapter's advertised length is a promise"
        state.apply_action(state.legal_actions()[0])
        steps += 1
    assert steps == game_ast.max_length
    assert state.returns() == [0.0, 0.0]
    assert state.ended_by() == "length"


def test_the_pyspiel_state_says_how_a_game_its_rules_ended_ended() -> None:
    """The other arm: tic-tac-toe's every line ends by its rules.
    red under: drop `ended_by` from `CardlangState`."""
    pyspiel = pytest.importorskip("pyspiel")
    import cardlang.openspiel.game  # noqa: F401  (registers on import)

    state = pyspiel.load_game("cardlang_tic_tac_toe").new_initial_state()
    while not state.is_terminal():
        assert state.ended_by() is None
        state.apply_action(state.legal_actions()[0])
    assert state.ended_by() == "rules"


def test_the_playtest_report_counts_length_stops_and_credits_them_to_no_seat() -> None:
    """Every rollout of the shuttle ends by length: none of them is a finish
    any seat earned. red under: credit a length stop's best return in
    `report.playtest_report`."""
    pytest.importorskip("pyspiel")
    from cardlang.openspiel.game import register_game_file
    from cardlang.openspiel.report import playtest_report

    report = playtest_report(register_game_file(SHUTTLE), num_games=3, seed=0)
    assert report["length_stops"] == 3
    assert report["best_seat_counts"] == [0, 0]


def test_a_stop_inside_a_decision_episode_leaves_its_window_open(cell_dir: Path) -> None:
    """The stop falls while the flag window's offers are asked, so the
    window's state variable stands non-idle in the world the stop is read
    at, and the result is the tie."""
    for site in SITES:
        game = check_source(Path(cell_path(cell_dir, site, "winner-player-Integer", "episode")))
        world: list[RuntimeState] = []
        result = play_game(game, random.Random(SEED), on_first_decision=world.append)
        assert _ended_by(result) == "length", site
        assert world[0].frames[0]["window_open"] is True, site
        _assert_tie(result.winners, result.loser, None, 2)


# --- the designer's misuse ----------------------------------------------------

_MISUSE_BASE = (
    "game Misuse {{\n"
    "  players: 2\n"
    "  {length}\n"
    "  cards: standard52\n"
    "  zones {{ deck : Deck  hand[player] : Hand<player> }}\n"
    "  state {{ n[player] : Integer = 0  turns_played : Integer = 0 }}\n"
    "  phase play {{\n"
    "    turns t from 0 over all players until {until} {{\n"
    "      turns_played += 1\n"
    "    }}\n"
    "  }}\n"
    "  winner: highest n\n"
    "}}\n"
)

MAX_LENGTH_AS_VALUE = (
    "`max_length` is the bound the engine stops a game at, not a value a rule "
    "can read. To end the game after a number of turns by its rules, count the "
    "turns in a state variable and write that number. To stop it at the bound, "
    "write nothing: the engine stops it there, and the game is a tie"
)


@pytest.mark.parametrize(
    "until",
    [
        pytest.param("turns_played >= max_length", id="a ring's until"),
        pytest.param("(turns_played > 3) or (turns_played >= max_length)", id="behind an or"),
    ],
)
def test_max_length_read_as_a_value_is_refused_in_designer_words(until: str) -> None:
    from cardlang.diagnostics import DiagnosticError

    with pytest.raises(DiagnosticError) as refused:
        check_dsl(_MISUSE_BASE.format(length="max_length: 30", until=until), "p7.cardlang")
    assert MAX_LENGTH_AS_VALUE in str(refused.value.diagnostic.message)


def test_max_length_read_in_a_state_default_is_refused_in_designer_words() -> None:
    from cardlang.diagnostics import DiagnosticError

    source = _MISUSE_BASE.format(length="max_length: 30", until="false").replace(
        "turns_played : Integer = 0", "turns_played : Integer = max_length"
    )
    with pytest.raises(DiagnosticError) as refused:
        check_dsl(source, "p7b.cardlang")
    assert MAX_LENGTH_AS_VALUE in str(refused.value.diagnostic.message)


BOUND_NEEDS_NO_CLAUSE = "`max_length:` takes a whole number and nothing more"


@pytest.mark.parametrize(
    "length",
    [
        pytest.param("max_length: 30 ends the game", id="P5a"),
        pytest.param("max_length: unbounded", id="no number"),
        pytest.param("max_length: 30 decisions", id="a unit"),
    ],
)
def test_a_clause_on_max_length_is_a_parse_refusal_naming_the_rule(length: str) -> None:
    from cardlang.diagnostics import DiagnosticError

    with pytest.raises(DiagnosticError) as refused:
        check_dsl(_MISUSE_BASE.format(length=length, until="false"), "p5a.cardlang")
    message = str(refused.value.diagnostic.message)
    assert BOUND_NEEDS_NO_CLAUSE in message
    assert "the engine stops a game there" in message
