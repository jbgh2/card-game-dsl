"""The Stop Result: what a game is worth when the engine stops it at its
declared `max_length` (docs/decisions.md, "Game result: `winner:` and
`loser:`"). `at max_length: tie` pays every seat 0, as a game that declares
nothing does; `at max_length: as it stands` reads the game's `winner:` clause
at the stopped position; `at max_length: highest <variable>` ranks a state
variable the game keeps, in `winner:`'s own shape.

The grid crosses four axes, each cell a small game built from
tests/test_length_stop.py's template with one Stop Result line beside its
bound:

- **declaration**, the three written members of the clause (the absent
  column is tests/test_length_stop.py's grid, which this one does not
  repeat);
- **result clause**, the `winner:` target's index role crossed with its type,
  plus `loser:`;
- **position** of the stop: a turn boundary, inside a Decision Episode, inside
  each round form, and mid-call through an n-pick;
- **channel**, where the end is reported: the driver's `GameResult` under the
  uniform Chooser that answers a call at once, the adapter's `TerminalNode`, a
  `LiveLine`'s `LiveEnd` and the pyspiel State, which walk the picks one at a
  time, `demo`'s and `play`'s lines, and the readiness harness's greedy walk,
  which feeds the coverage record.

Every template puts seat 0 (team 0) ahead on the `winner:` target and seat 1
(team 1) ahead on `other`, the variable the ranking member ranks, so a cell
scored from the wrong clause names the wrong winners.

Completeness ledger
-------------------
property:        a game stopped at its bound is scored by its declared Stop
                 Result in every channel: `tie` as every seat a winner and
                 every return 0; `as it stands` by its `winner:` clause read at
                 the game-level frame; a ranking by its own variable and
                 direction, the returns signed by the direction the result was
                 ranked by; and the sentence `demo` and `play` print names the
                 declared result. `as it stands` on a game whose only result
                 clause is `loser:` is refused at check time.
domain:          DECLARATIONS x CLAUSES x POSITIONS x CHANNELS below, plus the
                 direction x result-clause cells, the shadowed-target cells,
                 and the designer's misuse sentences. A game that declares
                 both `winner:` and `loser:` is scored by `winner:` at the
                 stop, as it is at a rules end (issue #247). The result reads
                 the world standing at the stopped pick, a partial call's
                 picks unapplied. The ranking target's declaration shapes are
                 tests/test_winner_target.py's slot-crossed grid.
registry:        declaration axis: the `stop_value` alternatives of
                 `cardlang.lark`, reconciled by
                 `test_the_declarations_are_the_stop_values`; clause axis:
                 tests/test_length_stop.py's `CLAUSES`
                 (`driver.SEAT_KEY_BY_ROLE` x `resolve._RANKABLE_TYPES`, plus
                 `loser:`); position axis: the round row fanned out by
                 `delegation.FORM_CONSTRUCTS`, reconciled by
                 `test_the_round_positions_are_the_forms`; direction axis:
                 `driver.RANK_DIR_TO_PICK`; the Length Stop itself:
                 tests/test_length_stop.py::test_the_length_stop_grid.
held by:         the result's shape is a closed enum (`driver.ScoredBy`) that
                 `returns_for` matches exhaustively (Unrepresentable); the
                 declaration's arm is a `Literal` the driver matches
                 exhaustively (Unrepresentable); the game-level read is one
                 site, `driver._ranked`, pinned by the shadow cells (Derived
                 and Pinned).
does not prove:  that a corpus game's Stop Result matches its written rules
                 (the twins and the registry pin,
                 tests/test_length_registry_pin.py, carry that), or that the
                 stop is common knowledge to every seat (the swap proof's
                 terminal assertion in tests/openspiel_ready/harness.py).
"""

from __future__ import annotations

import io
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from cardlang.cli import main
from cardlang.ast.nodes import STOP_KINDS
from cardlang.diagnostics import DiagnosticError
from cardlang.openspiel.replay import LiveLine, TerminalNode, returns_for, run
from cardlang.openspiel.seat_policy import FirstSeatPolicy
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.delegation import FORM_CONSTRUCTS
from cardlang.runtime.driver import RANK_DIR_TO_PICK, play_game
from cardlang.runtime.state import RuntimeState
from tests import test_length_stop as length_stop

BOUND = length_stop.BOUND
SEED = length_stop.SEED

def _ended_by(thing: object) -> object:
    return getattr(getattr(thing, "ended_by", None), "value", None)


# --- the declaration axis -------------------------------------------------------

# The grammar alias of each written member, and the line a game writes for it.
DECLARATIONS: dict[str, str] = {
    "stop_tie": "at max_length: tie",
    "stop_as_it_stands": "at max_length: as it stands",
    "stop_ranking": "at max_length: highest other",
}


def _stop_value_aliases() -> set[str]:
    from cardlang.parse import _parser

    return {
        str(rule.alias)
        for rule in _parser().rules
        if getattr(rule.origin, "name", None) == "stop_value" and rule.alias
    }


def test_the_declarations_are_the_stop_values() -> None:
    """Every alternative of `stop_value` is a column of the grid and a member
    of the AST's `StopKind`, and no column names an alternative the grammar
    lacks. red under: add a fourth alternative to `stop_value`."""
    assert _stop_value_aliases() == set(DECLARATIONS)
    assert {alias.removeprefix("stop_") for alias in DECLARATIONS} == set(STOP_KINDS)


# --- the position axis ----------------------------------------------------------

# Each position, as (tests/test_length_stop.py's site, its position row).
POSITIONS: dict[str, tuple[str, str]] = {
    "turn boundary": ("turns", "offer"),
    "decision episode": ("statement repeat until", "episode"),
    "trick": ("statement repeat until", "trick"),
    "climb": ("statement repeat until", "climb"),
    "mid n-pick": ("statement repeat until", "transfer"),
}


def test_the_round_positions_are_the_forms() -> None:
    """Every round form is a position of the grid. red under: add a form to
    `delegation.FORM_CONSTRUCTS`."""
    forms = {
        length_stop.POSITIONS[row].form
        for _site, row in POSITIONS.values()
        if length_stop.POSITIONS[row].point == "mechanics.run_decision_round"
    }
    assert forms == set(FORM_CONSTRUCTS)


# --- the cells --------------------------------------------------------------------


def _replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, f"the template no longer has one {old!r}"
    return source.replace(old, new)


def cell_source(declaration: str, clause_name: str, position: str) -> str:
    site, row = POSITIONS[position]
    clause = length_stop.CLAUSES[clause_name]
    index = "team" if clause.teamed else "player"
    source = length_stop.cell_source(site, clause_name, row)
    source = _replace_once(
        source, f"  max_length: {BOUND}\n", f"  max_length: {BOUND}\n  {DECLARATIONS[declaration]}\n"
    )
    source = _replace_once(
        source, "    ticks  : Integer = 0\n", f"    other[{index}] : Integer = 0\n    ticks  : Integer = 0\n"
    )
    return _replace_once(source, f"    {clause.lead}\n", f"    {clause.lead}\n    other[1] := 5\n")


@dataclass(frozen=True)
class Scored:
    """A cell's expected result: the winners, every seat's return, the
    direction it was ranked by, and the words the stop's sentence carries."""

    winners: frozenset[int]
    returns: list[float]
    rank_dir: str | None
    words: str


# Each clause's `winner:` target, per seat, as its template's lead leaves it.
_TARGET_BY_SEAT: dict[str, list[int]] = {
    "winner-player-Integer": [5, 0],
    "winner-player-Boolean": [1, 0],
    "winner-team-Integer": [5, 0, 5, 0],
    "winner-team-Boolean": [1, 0, 1, 0],
}

TIE_WORDS = "the game is a tie"
AS_IT_STANDS_WORDS = "the game is scored as it stands, by its `winner: highest target`"
RANKING_WORDS = "the game is scored by its `at max_length: highest other`"


def _ranked(seat_scores: list[int], words: str) -> Scored:
    best = max(seat_scores)
    return Scored(
        frozenset(seat for seat, score in enumerate(seat_scores) if score == best),
        [float(score) for score in seat_scores],
        "highest",
        words,
    )


def expected(declaration: str, clause_name: str) -> Scored | None:
    """The design column; None where the game is refused at check time."""
    seats = 4 if length_stop.CLAUSES[clause_name].teamed else 2
    if declaration == "stop_tie":
        return Scored(frozenset(range(seats)), [0.0] * seats, None, TIE_WORDS)
    if declaration == "stop_as_it_stands":
        if clause_name == "loser":
            return None
        return _ranked(_TARGET_BY_SEAT[clause_name], AS_IT_STANDS_WORDS)
    assert declaration == "stop_ranking", declaration
    return _ranked([0, 5] * (seats // 2), RANKING_WORDS)


def test_the_target_table_is_the_winner_clauses() -> None:
    assert set(_TARGET_BY_SEAT) == {c for c in length_stop.CLAUSES if c != "loser"}


_PATHS: dict[tuple[str, str, str], str] = {}


@pytest.fixture(scope="module")
def cell_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("stop_result_cells")


def cell_path(cell_dir: Path, declaration: str, clause: str, position: str) -> str:
    key = (declaration, clause, position)
    if key not in _PATHS:
        path = cell_dir / f"{'_'.join(k.replace(' ', '-') for k in key)}.cardlang"
        path.write_text(cell_source(declaration, clause, position))
        _PATHS[key] = str(path)
    return _PATHS[key]


# --- the channel axis -------------------------------------------------------------


def _first(view: Any, legal: Any) -> int:
    return FirstSeatPolicy()(view, legal)


def _seats(want: Scored) -> int:
    return len(want.returns)


def channel_result(path: str, want: Scored) -> None:
    game = check_source(Path(path))
    world: list[RuntimeState] = []
    result = play_game(game, random.Random(SEED), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert world[0].decisions_made == BOUND
    assert result.winners == want.winners, f"winners {sorted(result.winners)}"
    assert result.loser is None, f"a stop names no loser, got {result.loser!r}"
    assert getattr(result, "rank_dir", "missing") == want.rank_dir
    assert returns_for(game, result) == want.returns


def channel_terminal_node(path: str, want: Scored) -> None:
    line = LiveLine(path, SEED)
    line.play({seat: _first for seat in range(_seats(want))})
    node = run(path, SEED, tuple(line.history))
    assert isinstance(node, TerminalNode)
    assert _ended_by(node) == "length"
    assert node.returns == want.returns


def channel_live_end(path: str, want: Scored) -> None:
    end = LiveLine(path, SEED).play({seat: _first for seat in range(_seats(want))})
    assert _ended_by(end) == "length"
    assert end.returns == want.returns


def channel_pyspiel(path: str, want: Scored) -> None:
    pyspiel = pytest.importorskip("pyspiel")
    from cardlang.openspiel.game import register_game_file

    state = pyspiel.load_game(register_game_file(path)).new_initial_state()
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
            continue
        state.apply_action(state.legal_actions()[0])
    assert state.ended_by() == "length"
    assert state.returns() == want.returns


def _trim(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _returns_line(want: Scored) -> str:
    return "returns      " + ", ".join(f"P{p} {_trim(r)}" for p, r in enumerate(want.returns))


def channel_demo(path: str, want: Scored, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["demo", path, "--seed", str(SEED)])
    out, err = capsys.readouterr()
    first = out.splitlines()[0] if out else err
    assert "reached" in first and "max_length" in first, first
    assert want.words in first, first
    assert TIE_WORDS not in first or want.words == TIE_WORDS, first
    assert code == 1


def channel_play(
    path: str, want: Scored, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("1\n" * (BOUND + 2) + "q\n"))
    code = main(["play", path, "--seed", str(SEED), "--vs", "all=first"])
    out, err = capsys.readouterr()
    assert "the game is over" in out, out + err
    over = out[out.index("the game is over"):]
    assert "reached its max_length" in over and want.words in over, over
    assert TIE_WORDS not in over or want.words == TIE_WORDS, over
    assert code == 0, err


def channel_coverage(path: str, want: Scored) -> None:
    pytest.importorskip("pyspiel")
    from tests.openspiel_ready.harness import greedy_line

    line, returns, ended_by = greedy_line(path, SEED, BOUND)
    assert len(line) == BOUND
    assert returns == want.returns
    assert getattr(ended_by, "value", None) == "length"


CHANNELS: dict[str, Callable[..., None]] = {
    "GameResult": channel_result,
    "TerminalNode": channel_terminal_node,
    "LiveEnd": channel_live_end,
    "pyspiel State": channel_pyspiel,
    "demo": channel_demo,
    "play": channel_play,
    "coverage record": channel_coverage,
}

AS_IT_STANDS_ON_LOSER = (
    "`as it stands` reads the game's `winner:` clause at the stop, and this "
    "game declares `loser:` — the last player holding cards — which a stopped "
    "game has not decided: at a Length Stop it would name nobody, several "
    "seats, or the wrong one. Declare `at max_length: tie` — every seat a "
    "winner — or rank a state variable the game keeps: `at max_length: lowest "
    "<variable>`."
)


def _cells() -> list[Any]:
    out = []
    for declaration in DECLARATIONS:
        for clause in length_stop.CLAUSES:
            for position in POSITIONS:
                if expected(declaration, clause) is None:
                    out.append(
                        pytest.param(
                            declaration, clause, position, "check",
                            id=f"{declaration}|{clause}|{position}|check",
                        )
                    )
                    continue
                for channel in CHANNELS:
                    out.append(
                        pytest.param(
                            declaration, clause, position, channel,
                            id=f"{declaration}|{clause}|{position}|{channel}",
                        )
                    )
    return out


@pytest.mark.parametrize(("declaration", "clause", "position", "channel"), _cells())
def test_the_stop_result_grid(
    declaration: str,
    clause: str,
    position: str,
    channel: str,
    cell_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = cell_path(cell_dir, declaration, clause, position)
    want = expected(declaration, clause)
    if want is None:
        with pytest.raises(DiagnosticError) as refused:
            check_source(Path(path))
        assert AS_IT_STANDS_ON_LOSER in refused.value.diagnostic.message
        return
    run_channel = CHANNELS[channel]
    if channel == "demo":
        run_channel(path, want, capsys)
    elif channel == "play":
        run_channel(path, want, capsys, monkeypatch)
    else:
        run_channel(path, want)


# --- the direction the returns are signed by ---------------------------------------

# The result clause of a game ranked at its stop, and the ranking's direction:
# a `winner:` clause ranking the other way is the cell where a sign read off
# the game's declaration pays a seat that did not win.
_DIRECTION_CLAUSES: dict[str, str] = {
    "winner-highest": "winner: highest target",
    "winner-lowest": "winner: lowest target",
    "loser": "loser: the player where target[player] > 1000",
}


def _direction_source(rank_dir: str, clause: str) -> str:
    source = length_stop.cell_source("statement repeat until", "winner-player-Integer", "offer")
    source = _replace_once(source, "  winner: highest target\n", f"  {_DIRECTION_CLAUSES[clause]}\n")
    source = _replace_once(
        source, f"  max_length: {BOUND}\n", f"  max_length: {BOUND}\n  at max_length: {rank_dir} other\n"
    )
    source = _replace_once(
        source, "    ticks  : Integer = 0\n", "    other[player] : Integer = 0\n    ticks  : Integer = 0\n"
    )
    return _replace_once(source, "    target[0] := 5\n", "    target[0] := 5\n    other[1] := 5\n")


@pytest.mark.parametrize(
    ("rank_dir", "clause"),
    [
        pytest.param(rank_dir, clause, id=f"{rank_dir}|{clause}")
        for rank_dir in sorted(RANK_DIR_TO_PICK)
        for clause in _DIRECTION_CLAUSES
    ],
)
def test_the_returns_are_signed_by_the_direction_the_stop_ranked_by(
    rank_dir: str, clause: str, tmp_path: Path
) -> None:
    """The best return goes to a winner, whichever direction the game's own
    `winner:` clause ranks in and whether it has one at all.
    red under: sign `returns_for` by `game.winner.rank_dir`."""
    path = tmp_path / "direction.cardlang"
    path.write_text(_direction_source(rank_dir, clause))
    game = check_source(path)
    result = play_game(game, random.Random(SEED))
    assert _ended_by(result) == "length"
    other = [0, 5]
    best = RANK_DIR_TO_PICK[rank_dir](other)
    assert result.winners == frozenset(s for s, v in enumerate(other) if v == best)
    assert getattr(result, "rank_dir", "missing") == rank_dir
    sign = 1.0 if rank_dir == "highest" else -1.0
    returns = returns_for(game, result)
    assert returns == [sign * v for v in other]
    top = max(returns)
    assert {s for s, r in enumerate(returns) if r == top} == set(result.winners)
    end = LiveLine(str(path), SEED).play({seat: _first for seat in range(2)})
    assert end.returns == returns


# --- the game-level frame -------------------------------------------------------------

# The phase the stop falls in declares its own `target` and `other`, each
# putting the OTHER seat ahead; the game-level frame is the one the result
# clauses name.
_SHADOW = """game Shadow {{
  players: 2
  max_length: {bound}
  {stop}
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ target[player] : Integer = 0  other[player] : Integer = 0  ticks : Integer = 0 }}
  phase setup {{
    target[0] := 5
    other[1] := 5
  }}
  phase play {{
    state {{ target[player] : Integer = 0  other[player] : Integer = 0 }}
    target[1] := 9
    other[0] := 9
    repeat until false {{
      as 0 {{ offer to 0 one of [tick] }}
    }}
  }}
  winner: highest target
}}
move_type tick {{ effect {{ ticks += 1 }} }}
"""


@pytest.mark.parametrize(
    ("stop", "winners"),
    [
        pytest.param("at max_length: as it stands", frozenset({0}), id="as it stands"),
        pytest.param("at max_length: highest other", frozenset({1}), id="ranking"),
    ],
)
def test_a_stop_is_scored_from_the_game_level_frame(stop: str, winners: frozenset[int]) -> None:
    """Every phase frame stands at the stop, and the phase it falls in shadows
    both result targets; the result reads the game-level declaration, the
    only one a result clause may name.
    red under: read the target with `rs.get` in `driver._ranked`."""
    game = check_dsl(_SHADOW.format(bound=BOUND, stop=stop), "shadow.cardlang")
    world: list[RuntimeState] = []
    result = play_game(game, random.Random(SEED), on_first_decision=world.append)
    assert _ended_by(result) == "length"
    assert len(world[0].frames) > 1, "the phase frame stands at the stop"
    assert result.winners == winners
    assert result.seat_scores == ((5, 0) if winners == {0} else (0, 5))


# --- the designer's misuse ---------------------------------------------------------------

_MISUSE = """game Misuse {{
  players: 2
  max_length: 30
  {stop}
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ coins[player] : Integer = 0  alive[player] : Boolean = true  done : Boolean = false }}
  phase play {{
    turns t from 0 over all players until done {{
      as t {{ offer to t one of [stop] }}
    }}
  }}
  {result}
}}
move_type stop {{ effect {{ done := true }} }}
"""


def _misuse(stop: str, result: str = "winner: highest alive") -> str:
    return _MISUSE.format(stop=stop, result=result)


BOUND_HINT = (
    "`max_length:` takes a whole number and nothing more; what a game is worth "
    "when the engine stops it at its bound is a game clause of its own: `at "
    "max_length: tie`, `at max_length: as it stands`, or `at max_length: highest "
    "<variable>`"
)

STOP_LEAD_TWIN = (
    "the game ends AT its bound and nothing lies beyond it — write `at max_length: …`"
)


def _refused(source: str) -> str:
    with pytest.raises(DiagnosticError) as refused:
        check_dsl(source, "misuse.cardlang")
    return str(refused.value.diagnostic.message)


# (the sentence, a phrase its refusal carries). Each is refused at the layer
# that owns its slip, in that layer's words.
MISUSE_REFUSED: dict[str, tuple[str, str]] = {
    "1 draw": (_misuse("at max_length: draw"), "unexpected `draw`; expected"),
    "1 drawn": (_misuse("at max_length: drawn"), "unexpected `drawn`; expected"),
    "1 tied": (_misuse("at max_length: tied"), "unexpected `tied`; expected"),
    "1 a number": (_misuse("at max_length: 600"), "unexpected `600`; expected"),
    "1 the value left off": (
        _misuse("", "winner: highest alive\n  at max_length:"),
        "unexpected `}`; expected",
    ),
    "2 as is": (_misuse("at max_length: as is"), "unexpected `is`; expected `it`"),
    "2 as it stand": (_misuse("at max_length: as it stand"), "unexpected `stand`; expected `stands`"),
    "2 no colon": (_misuse("at max_length tie"), "unexpected `tie`; expected `:`"),
    "2 atmax_length fused": (_misuse("atmax_length: tie"), "unexpected `atmax_length`"),
    "2 itstands fused": (_misuse("at max_length: as itstands"), "unexpected `itstands`; expected `it`"),
    "3 at the bound": (_misuse("at the bound: tie"), "unexpected `the`; expected `max_length`"),
    "4 beyond": (_misuse("beyond max_length: tie"), STOP_LEAD_TWIN),
    "4 after": (_misuse("after max_length: as it stands"), STOP_LEAD_TWIN),
    "5 highest above a clause": (
        _misuse("at max_length: highest"),
        "unexpected `cards`; expected a state variable name",
    ),
    "5 an expression": (_misuse("at max_length: highest coins + 1"), "unexpected `+`"),
    "6 twice": (
        _misuse("at max_length: tie\n  at max_length: as it stands"),
        "a game declares one `at max_length:` — the repeat would silently replace the first; keep one",
    ),
    "7 without max_length": (
        _misuse("at max_length: tie").replace("  max_length: 30\n", ""),
        "ends there, scored by its Stop Result",
    ),
    "9 as it stands on loser": (
        _misuse("at max_length: as it stands", "loser: the player where coins[player] > 9"),
        AS_IT_STANDS_ON_LOSER,
    ),
    "10 a zone": (
        _misuse("at max_length: highest hand"),
        "`at max_length:` references unknown variable 'hand'",
    ),
    "13 max_length as a value": (
        _misuse("").replace("until done", "until done or coins[0] >= max_length"),
        length_stop.MAX_LENGTH_AS_VALUE,
    ),
    "15 a clause after the bound": (
        _misuse("").replace("max_length: 30", "max_length: 30 then tie"),
        "unexpected `then`",
    ),
    "15 the bound's hint after a clause": (
        _misuse("").replace("max_length: 30", "max_length: 30 then tie"),
        BOUND_HINT,
    ),
    "15 a comma after winner": (
        _misuse("", "winner: highest alive, at max_length tie"),
        "unexpected `,`",
    ),
    "P5a misplaced in a phase": (
        _misuse("").replace("    turns t", "    at max_length: tie\n    turns t"),
        BOUND_HINT,
    ),
}

@pytest.mark.parametrize(
    ("source", "phrase"),
    [
        pytest.param(*MISUSE_REFUSED[name], id=name)
        for name in MISUSE_REFUSED
    ],
)
def test_a_misused_stop_result_is_refused_in_its_layers_words(source: str, phrase: str) -> None:
    message = _refused(source)
    assert phrase in message, message
    assert "the game is a tie" not in message, message


MISUSE_ACCEPTED: dict[str, str] = {
    "8 tie written out": _misuse("at max_length: tie"),
    "12 on a game its rules bound": _misuse("at max_length: as it stands"),
    "14 the ranking equal to winner": _misuse("at max_length: highest alive"),
    "a state variable named tie": _misuse("at max_length: tie").replace(
        "done : Boolean = false", "done : Boolean = false  tie : Integer = 0"
    ),
    "ranking a variable named tie": _misuse("at max_length: highest tie").replace(
        "done : Boolean = false", "done : Boolean = false  tie[player] : Integer = 0"
    ),
}


@pytest.mark.parametrize("name", sorted(MISUSE_ACCEPTED))
def test_a_stop_result_sentence_is_accepted(name: str) -> None:
    game = check_dsl(MISUSE_ACCEPTED[name], "accepted.cardlang")
    assert getattr(game, "stop_result", None) is not None


def test_a_bound_game_without_the_clause_has_no_stop_result() -> None:
    game = check_dsl(_misuse(""), "absent.cardlang")
    assert getattr(game, "stop_result", None) is None
