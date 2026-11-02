"""The grid of `tests/native_oracle.py::walk_paired_prefix`: how one paired
line ends, at every combination of the game's node and the oracle's state the
walker can meet.

Each cell walks a scripted tic-tac-toe line against a scripted oracle: the
real native `tic_tac_toe` state, wrapped so that it ends the line early, plays
on past the game's terminal, or reports the other outcome. The wrapper stands
in for an oracle whose draw rule differs from the game's; the two real
witnesses are the nine men's morris differential (the oracle's turn cap) and
the breakthrough and tic-tac-toe manifests below (no truncation at all).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   every line a paired walk returns is agreed to a shared terminal
            (`Rules`) or truncated where the oracle ended it by a draw rule
            the game does not play (`Truncated`); every other meeting of the
            two sides is a loud failure naming the ply, and a manifest whose
            every line truncated is refused.
domain:     the game's node kinds (the return union of `replay.run`), crossed
            at a decision node with the oracle live or terminal, the
            predicate's verdict, and the oracle's terminal outcome; at the
            game's terminal, with how the game ended (`EndedBy`), its outcome
            (each `classify` class for a rules end; the Length Stop's own tie
            in a scratch copy whose `max_length` falls inside a line), the
            oracle live, agreeing or disagreeing, and the predicate's verdict.
            Beside the grid: a game terminal at its root, a wrong first mover,
            a paused replay disagreeing with the live run at either end, and
            the tally over each `LineEnd` constructor. A native chance or
            simultaneous node is outside the walker by design, refused by
            `assert_node_agrees` at the node.
registry:   node kinds: `typing.get_type_hints(replay.run)["return"]`; ends:
            `EndedBy`; line ends: `typing.get_args(native_oracle.LineEnd)`.
held by:    comparing returns on a truncated line is Unrepresentable
            (`Truncated` carries none, and `tally_line_ends` dispatches with
            `assert_never`); a truncation at a live oracle is Unrepresentable
            (the predicate is asked only of a terminal oracle, which cannot
            become live again, so it is monotone along a line by
            construction); the all-truncated refusal is Derived and Pinned,
            because "some line reached a rules end" is a fact about a run, not
            a type.
does not prove:  that a predicate names the oracle's rule rather than a
            genuine draw the game lacks (the walker holds that a truncation
            is a draw, and the caller's predicate holds which draw); nor that
            the two sides would agree past a truncation; nor anything at the
            node where the line truncates, which the oracle no longer poses.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args, get_type_hints

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel import replay
from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.replay import DecisionNode, TerminalNode
from cardlang.runtime.driver import EndedBy
from tests import native_oracle
from tests.native_oracle import (
    Choose,
    LineEnd,
    Rules,
    Truncated,
    classify,
    tally_line_ends,
    uniform,
    walk_paired_prefix,
)
from tests.test_differential_breakthrough import CONTACT_OPENING, Mirror
from tests.test_differential_breakthrough import NATIVE as BT_NATIVE
from tests.test_differential_breakthrough import PATH as BT
from tests.test_differential_tic_tac_toe import NATIVE as TTT_NATIVE
from tests.test_differential_tic_tac_toe import PATH as TTT
from tests.test_differential_tic_tac_toe import to_native as ttt_to_native

NODE_KINDS: tuple[type, ...] = get_args(get_type_hints(replay.run)["return"])
LINE_ENDS: tuple[type, ...] = get_args(LineEnd)

# One line per `classify` class; the oracle's own returns name its class.
SCRIPTS: dict[str, tuple[str, ...]] = {
    "p0": ("a1", "a3", "b1", "b3", "c1"),
    "p1": ("a1", "a3", "b1", "b3", "c2", "c3"),
    "draw": ("a3", "b2", "c3", "b3", "b1", "c2", "a2", "a1", "c1"),
}
ORACLE_ENDS_AT = 3  # a decision node of every script, past the first mover's
LENGTH_STOP = 3  # the scratch copy's `max_length`, inside every script


class _Stop(Exception):
    """The script has no further step."""


def scripted(cells: Sequence[str]) -> Choose:
    steps: Iterator[str] = iter(cells)

    def choose(legal: list[int], space: ActionSpace) -> int:
        cell = next(steps, None)
        if cell is None:
            raise _Stop
        return space.encode(("place", cell))

    return choose


@dataclass(frozen=True)
class Shape:
    """How the scripted oracle departs from the real one."""

    ends_at: int | None = None  # the ply it ends the line at, with `end_returns`
    end_returns: tuple[float, float] = (0.0, 0.0)
    plays_on: bool = False  # it is never terminal
    reports: tuple[float, float] | None = None  # its terminal returns, replaced


class ScriptedOracle:
    def __init__(self, shape: Shape) -> None:
        self.real = pyspiel.load_game(TTT_NATIVE).new_initial_state()
        self.shape = shape
        self.ply = 0

    def _ended(self) -> bool:
        return self.shape.ends_at is not None and self.ply >= self.shape.ends_at

    def is_chance_node(self) -> bool:
        return bool(self.real.is_chance_node())

    def is_terminal(self) -> bool:
        if self._ended():
            return True
        if self.shape.plays_on:
            return False
        return bool(self.real.is_terminal())

    def current_player(self) -> int:
        return int(self.real.current_player())

    def legal_actions(self) -> list[int]:
        return list(self.real.legal_actions())

    def apply_action(self, action: int) -> None:
        self.real.apply_action(action)
        self.ply += 1

    def returns(self) -> list[float]:
        if self._ended():
            return list(self.shape.end_returns)
        if self.shape.reports is not None:
            return list(self.shape.reports)
        return list(self.real.returns())


class Predicate:
    """A fixed verdict that records whether it was asked of a live oracle."""

    def __init__(self, verdict: bool) -> None:
        self.verdict = verdict
        self.asked_live = 0

    def __call__(self, native: Any) -> bool:
        if not native.is_terminal():
            self.asked_live += 1
        return self.verdict


def install(monkeypatch: pytest.MonkeyPatch, shape: Shape) -> None:
    game = SimpleNamespace(new_initial_state=lambda: ScriptedOracle(shape))
    monkeypatch.setattr(
        native_oracle, "pyspiel",
        SimpleNamespace(load_game=lambda name: game, PlayerId=pyspiel.PlayerId),
    )


def observe(
    path: str, script: Sequence[str], predicate: Predicate, *, label: str
) -> str:
    """The cell's outcome as one string: the end's kind, or the failure."""
    try:
        end = walk_paired_prefix(
            path, TTT_NATIVE, ttt_to_native, predicate, 0, scripted(script),
            label=label,
        )
    except AssertionError as failure:
        outcome = f"fail: {failure}"
    except _Stop:
        outcome = "script ran out"
    else:
        outcome = "rules" if isinstance(end, Rules) else "truncated"
    if predicate.asked_live:
        outcome += " (the predicate was asked of a live oracle)"
    return outcome


def disagreeing(outcome: str) -> tuple[float, float]:
    return (-1.0, 1.0) if outcome == "p0" else (1.0, -1.0)


@dataclass(frozen=True)
class Cell:
    node: type
    ended_by: EndedBy | None  # at the game's terminal
    outcome: str  # the script's `classify` class
    oracle: str  # "live", "ended-draw", "ended-decisive", "agrees", "disagrees"
    named: bool  # the predicate's verdict

    @property
    def id(self) -> str:
        kind = self.node.__name__ if self.ended_by is None else f"Terminal-{self.ended_by.name}"
        return f"{kind}/{self.outcome}/oracle-{self.oracle}/{'named' if self.named else 'unnamed'}"

    def shape(self) -> Shape:
        if self.oracle == "ended-draw":
            return Shape(ends_at=ORACLE_ENDS_AT)
        if self.oracle == "ended-decisive":
            return Shape(ends_at=ORACLE_ENDS_AT, end_returns=(1.0, -1.0))
        if self.oracle == "live" and self.node is TerminalNode:
            return Shape(plays_on=True)
        if self.oracle == "agrees" and self.ended_by is EndedBy.LENGTH:
            return Shape(ends_at=LENGTH_STOP)
        if self.oracle == "disagrees":
            if self.ended_by is EndedBy.LENGTH:
                return Shape(ends_at=LENGTH_STOP, end_returns=(1.0, -1.0))
            return Shape(reports=disagreeing(self.outcome))
        return Shape()


def derive_cells() -> list[Cell]:
    cells: list[Cell] = []
    for node in NODE_KINDS:
        if node is DecisionNode:
            for oracle, named in product(("live", "ended-draw", "ended-decisive"), (False, True)):
                cells.append(Cell(node, None, "p0", oracle, named))
            continue
        assert node is TerminalNode, f"replay.run returns a node kind the grid lacks: {node}"
        for ended_by, oracle, named in product(EndedBy, ("live", "agrees", "disagrees"), (False, True)):
            outcomes = tuple(SCRIPTS) if ended_by is EndedBy.RULES else ("draw",)
            for outcome in outcomes:
                cells.append(Cell(node, ended_by, outcome, oracle, named))
    return cells


ORACLE_ENDED = r"native is already terminal while our game still offers a decision"
DECISIVE = r"step 3: truncate_when names a decisive oracle end \[1\.0, -1\.0\]"
ORACLE_LIVE = r"step \d+: our game is terminal \(\[-?1\.0, -?1\.0\]\) but native is not"
TIE_LIVE = r"step 9: our game ended in a tie by its own rule while the oracle plays on"
OUTCOME = r"step \d+: outcome classification diverges"
LENGTH = r"step 3: our game's Length Stop ended the line"

# The expected column, one decision per cell.
EXPECTED: dict[str, str] = {
    "DecisionNode/p0/oracle-live/unnamed": "rules",
    "DecisionNode/p0/oracle-live/named": "rules",
    "DecisionNode/p0/oracle-ended-draw/unnamed": f"fail: {ORACLE_ENDED}",
    "DecisionNode/p0/oracle-ended-draw/named": "truncated",
    "DecisionNode/p0/oracle-ended-decisive/unnamed": f"fail: {ORACLE_ENDED}",
    "DecisionNode/p0/oracle-ended-decisive/named": f"fail: {DECISIVE}",
    **{
        f"Terminal-RULES/{o}/oracle-live/{n}": f"fail: {TIE_LIVE if o == 'draw' else ORACLE_LIVE}"
        for o in ("p0", "p1", "draw") for n in ("named", "unnamed")
    },
    **{
        f"Terminal-RULES/{o}/oracle-agrees/{n}": "rules"
        for o in ("p0", "p1", "draw") for n in ("named", "unnamed")
    },
    **{
        f"Terminal-RULES/{o}/oracle-disagrees/{n}": f"fail: {OUTCOME}"
        for o in ("p0", "p1", "draw") for n in ("named", "unnamed")
    },
    **{
        f"Terminal-LENGTH/draw/oracle-{s}/{n}": f"fail: {LENGTH}"
        for s in ("live", "agrees", "disagrees") for n in ("named", "unnamed")
    },
}

CELLS = derive_cells()


def test_expected_column_covers_the_derived_cells() -> None:
    """red under: a third member of `EndedBy` in `cardlang/runtime/driver.py`."""
    assert sorted(EXPECTED) == sorted(c.id for c in CELLS)


@pytest.fixture
def length_copy(tmp_path: Path) -> str:
    source = Path(TTT).read_text()
    assert source.count("max_length: 30") == 1
    copy = tmp_path / "tic-tac-toe-length-stop.cardlang"
    copy.write_text(source.replace("max_length: 30", f"max_length: {LENGTH_STOP}"))
    return str(copy)


@pytest.mark.parametrize("cell", [pytest.param(c, id=c.id) for c in CELLS])
def test_line_end_grid(cell: Cell, monkeypatch: pytest.MonkeyPatch, length_copy: str) -> None:
    install(monkeypatch, cell.shape())
    path = length_copy if cell.ended_by is EndedBy.LENGTH else TTT
    observed = observe(path, SCRIPTS[cell.outcome], Predicate(cell.named), label=cell.id)
    expected = EXPECTED[cell.id]
    if expected.startswith("fail: "):
        assert observed.startswith("fail: ") and re.search(expected[6:], observed), (
            f"{cell.id}: expected a failure matching {expected[6:]!r}, observed {observed!r}"
        )
    else:
        assert observed == expected, f"{cell.id}: expected {expected!r}, observed {observed!r}"


def test_scripts_end_as_their_class() -> None:
    """Each script is a real tic-tac-toe line ending in its own class.

    red under: `to_native` in `tests/test_differential_tic_tac_toe.py` reading
    the files as `"bac"`, which turns the drawn line into a win."""
    for outcome, script in SCRIPTS.items():
        state = pyspiel.load_game(TTT_NATIVE).new_initial_state()
        for cell in script:
            assert not state.is_terminal(), f"{outcome}: the line ended before {cell}"
            state.apply_action(ttt_to_native(("place", cell)))
        assert state.is_terminal() and classify(list(state.returns())) == outcome


def _patched_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    live: Callable[..., DecisionNode | TerminalNode] | None = None,
    paused: Callable[..., DecisionNode | TerminalNode] | None = None,
) -> None:
    real = replay.run

    def run(path: str, seed: int, history: tuple[int, ...], **kwargs: Any) -> DecisionNode | TerminalNode:
        if kwargs.get("beyond") is not None:
            return (live or real)(path, seed, history, **kwargs)
        return (paused or real)(path, seed, history, **kwargs)

    monkeypatch.setattr(native_oracle, "run", run)


def test_terminal_at_the_root_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_run(monkeypatch, live=lambda *a, **k: TerminalNode([0.0, 0.0], EndedBy.RULES))
    with pytest.raises(AssertionError, match="ended before its first decision"):
        walk_paired_prefix(
            TTT, TTT_NATIVE, ttt_to_native, Predicate(False), 0,
            scripted(SCRIPTS["p0"]), label="root",
        )


def test_wrong_first_mover_is_refused() -> None:
    with pytest.raises(AssertionError, match="first mover is P0, expected P1"):
        walk_paired_prefix(
            TTT, TTT_NATIVE, ttt_to_native, Predicate(False), 0,
            scripted(SCRIPTS["p0"]), label="first mover", expected_first_player=1,
        )


def test_paused_replay_disagreeing_at_a_rules_end_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_run(monkeypatch, paused=lambda *a, **k: TerminalNode([0.0, 0.0], EndedBy.RULES))
    with pytest.raises(AssertionError, match="step 5: the paused replay of the line ends"):
        walk_paired_prefix(
            TTT, TTT_NATIVE, ttt_to_native, Predicate(False), 0,
            scripted(SCRIPTS["p0"]), label="paused",
        )


def test_paused_replay_disagreeing_at_a_truncation_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, Shape(ends_at=ORACLE_ENDS_AT))
    _patched_run(monkeypatch, paused=lambda *a, **k: TerminalNode([0.0, 0.0], EndedBy.RULES))
    with pytest.raises(AssertionError, match="step 3: the paused replay of the line ends"):
        walk_paired_prefix(
            TTT, TTT_NATIVE, ttt_to_native, Predicate(True), 0,
            scripted(SCRIPTS["p0"]), label="paused",
        )


SAMPLES: dict[type, LineEnd] = {
    Rules: Rules(5, (1.0, -1.0), (1.0, -1.0)),
    Truncated: Truncated(3),
}


@pytest.mark.parametrize("kind", LINE_ENDS, ids=lambda k: k.__name__)
def test_tally_counts_each_line_end(kind: type) -> None:
    """red under: `tally_line_ends` counting a `Truncated` end under `draw`."""
    end = SAMPLES[kind]
    ends = [SAMPLES[Rules], end]
    tally = tally_line_ends(ends)
    key = "truncated" if isinstance(end, Truncated) else classify(list(end.ours))
    assert tally[key] == (2 if kind is Rules else 1), dict(tally)


def test_samples_cover_every_line_end() -> None:
    """red under: a third member of `LineEnd` in `tests/native_oracle.py`."""
    assert set(SAMPLES) == set(LINE_ENDS)


@pytest.mark.parametrize(
    "ends",
    [pytest.param([], id="empty"), pytest.param([Truncated(3), Truncated(7)], id="all-truncated")],
)
def test_tally_refuses_a_manifest_with_no_rules_end(ends: list[LineEnd]) -> None:
    with pytest.raises(AssertionError, match="no line of the manifest reached a rules end"):
        tally_line_ends(ends)


def never(native: Any) -> bool:
    return False


def every_end(native: Any) -> bool:
    """A predicate that names every oracle end, a stand-in no real oracle has."""
    return True


def exact(end: LineEnd) -> LineEnd:
    if isinstance(end, Rules):
        assert end.ours == end.native, f"returns diverge: ours {end.ours} native {end.native}"
    return end


def test_tic_tac_toe_manifest_reaches_every_outcome() -> None:
    """Tic-tac-toe's oracle has no draw rule the game lacks: every policy line
    is a `Rules` end, with exact returns, and the manifest holds each outcome.

    red under: the walker's terminal branch returning `Truncated(len(history))`
    in place of `Rules(...)`, which makes the tally refuse the manifest."""
    tally = tally_line_ends(
        exact(walk_paired_prefix(
            TTT, TTT_NATIVE, ttt_to_native, never, 0, uniform(seed),
            label=f"tic-tac-toe policy {seed}",
        ))
        for seed in range(TTT_SEEDS)
    )
    assert tally["p0"] and tally["p1"] and tally["draw"], dict(tally)
    assert not tally["truncated"]


TTT_SEEDS = 40
BT_SEEDS = 8


def breakthrough_line(choose: Choose, mirror: Mirror, *, label: str) -> LineEnd:
    def advance(player: int, decoded: Any) -> None:
        assert player == mirror.player, f"{label}: P{player} moved, mirror expects P{mirror.player}"
        mirror.apply(decoded)

    return walk_paired_prefix(
        BT, BT_NATIVE, mirror.to_native, every_end, 0, choose,
        label=label, advance=advance,
    )


def test_breakthrough_manifest_never_asks_the_predicate_at_a_shared_end() -> None:
    """Breakthrough's oracle ends only where the game does, so a predicate
    naming every oracle end is never asked: each policy line is a `Rules` end
    with exact returns, the mirror following it through `advance`, and both
    seats win somewhere in the manifest.

    red under: the walker asking `truncate_when` at its own terminal node and
    returning `Truncated` when it holds, which makes the tally refuse the
    manifest."""
    tally = tally_line_ends(
        exact(breakthrough_line(uniform(seed), Mirror(), label=f"breakthrough policy {seed}"))
        for seed in range(BT_SEEDS)
    )
    assert tally["p0"] and tally["p1"] and not tally["truncated"], dict(tally)


def breakthrough_script(moves: Sequence[tuple[str, str]]) -> Choose:
    steps = iter(moves)

    def choose(legal: list[int], space: ActionSpace) -> int:
        move = next(steps, None)
        if move is None:
            raise _Stop
        return space.encode(("step", move))

    return choose


def test_blind_capture_bit_is_a_tripwire() -> None:
    """The prefix walk FAILS when `to_native` never sets the capture bit: the
    contact opening agrees until a diagonal step has an enemy under it.

    red under: `walk_paired_prefix` dropping its `assert_node_agrees` call."""
    with pytest.raises(AssertionError, match="legal actions diverge"):
        breakthrough_line(
            breakthrough_script(CONTACT_OPENING), Mirror(capture_bit=False),
            label="blind capture bit",
        )


def test_advance_out_of_step_is_a_tripwire() -> None:
    """The prefix walk FAILS at the next node when `advance` misses a ply: the
    mirror still holds P1 to move, so P0's steps map onto P1's directions.

    red under: `walk_paired_prefix` dropping its `assert_node_agrees` call."""
    mirror = Mirror()
    plies = iter(range(1 << 30))

    def advance(player: int, decoded: Any) -> None:
        if next(plies) != 1:
            mirror.apply(decoded)

    with pytest.raises(AssertionError, match="out of step step 2: legal actions diverge"):
        walk_paired_prefix(
            BT, BT_NATIVE, mirror.to_native, every_end, 0,
            breakthrough_script(CONTACT_OPENING), label="out of step", advance=advance,
        )
