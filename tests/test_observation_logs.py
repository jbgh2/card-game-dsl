"""The table's Observation Logs are one aggregate the runtime keeps, written
by one door and read as frozen snapshots (`observe.ObservationLogs`).

Every reader of a seat's knowledge -- a replay, a paused run, a live line,
the terminal command, a resampled world -- reads the log the run itself
kept, so no two of them can disagree about what a seat was told.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a snapshot of a seat's log is the events delivered to the
                 seat before it was taken, in delivery order, and nothing
                 delivered after it is ever part of it; a snapshot offers no
                 write; under `cardlang/` the aggregate is made only by
                 `driver.play_game`, written only by `Ctx.observe`, and read
                 off the world only through `observe.logs_of`; a run is
                 observed exactly when it is asked to be, and the listener
                 hears every delivery in the order made across seats.
domain:          `ObservationLog`'s read surface (length, iteration, an index
                 either side of zero, a slice, equality, hash); the Mapping a
                 snapshot is; every `.py` file under `cardlang/`, every
                 construction of `ObservationLogs` and every attribute read
                 of `observations` in it; `play_game`'s two observing
                 arguments, crossed.
registry:        `ObservationLog`, `ObservationLogs`, `observe.logs_of`
                 (cardlang/runtime/observe.py); `RuntimeState.observations`
                 (cardlang/runtime/state.py).
held by:         Unrepresentable for a snapshot's immutability to its reader
                 -- `ObservationLog` is a `Sequence` with slots and no write,
                 and the snapshot's Mapping is a `MappingProxyType`; Derived
                 and Pinned for append-only and for who touches the aggregate
                 -- the scrapes below. Why not higher: `append` is a public
                 method of a Python object, and which code calls it is a fact
                 about the text.
does not prove:  that the events delivered are the right ones -- the
                 per-observer proofs under tests/openspiel_ready/ and the
                 spelling capture in tests/test_observation_spelling.py hold
                 that; anything outside `cardlang/` -- the proof harness and
                 the test suite build worlds and logs of their own by design.
red under:       each test names its own reddening mutation.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.observe import (
    AnnounceEvent,
    ChoseEvent,
    ObservationEvent,
    ObservationLog,
    ObservationLogs,
    RevealEvent,
)
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, Player

REPO = Path(__file__).parent.parent
CARDLANG = REPO / "cardlang"
HEARTS = REPO / "docs" / "games" / "hearts.cardlang"

E1, E2, E3 = ChoseEvent("Q spades"), AnnounceEvent(1, "pass"), RevealEvent("hand[0]", str(Card("K", "clubs")))


def _logs() -> ObservationLogs:
    logs = ObservationLogs(range(2))
    logs.append(0, E1)
    logs.append(1, E2)
    logs.append(0, E2)
    return logs


def test_a_snapshot_holds_nothing_delivered_after_it() -> None:
    """red under: a snapshot bounded by the live list's length at read time
    (`len(self._events)` in place of `self._length`) -- every read below sees
    the event appended after the snapshot."""
    logs = _logs()
    before = logs.snapshot()[0]
    logs.append(0, E3)
    assert len(before) == 2
    assert list(before) == [E1, E2]
    assert before[-1] == E2
    assert before[:] == (E1, E2)
    with pytest.raises(IndexError):
        before[2]
    with pytest.raises(IndexError):
        before[-3]
    assert before == (E1, E2)
    assert logs.snapshot()[0] == (E1, E2, E3)


def test_a_snapshot_offers_no_write() -> None:
    """red under: `ObservationLog` deriving from `MutableSequence`, or the
    snapshot's Mapping a plain dict -- a reader could then write a seat's log."""
    snapshot = _logs().snapshot()
    log = snapshot[0]
    for name in ("append", "extend", "insert", "pop", "remove", "clear", "__setitem__"):
        assert not hasattr(log, name), name
    assert not hasattr(log, "__dict__")
    with pytest.raises(TypeError):
        snapshot[0] = log  # type: ignore[index]


def test_two_snapshots_of_one_log_are_one_value() -> None:
    """red under: `ObservationLog` with identity equality -- the paused run's
    agreement with `replay.run` (tests/test_paused_runs.py) compares logs as
    values."""
    logs = _logs()
    first, second = logs.snapshot()[0], logs.snapshot()[0]
    assert first == second and hash(first) == hash(second)
    assert first == (E1, E2)
    assert first != [E1, E2], "a log is a frozen value, never equal to a list"
    logs.append(0, E3)
    assert logs.snapshot()[0] != first


def test_the_listener_hears_every_delivery_in_order() -> None:
    """red under: `append` telling the listener before writing the log, or
    not at all -- the order across seats is the listener's alone."""
    heard: list[tuple[Player, ObservationEvent]] = []
    logs = ObservationLogs(range(2), lambda seat, event: heard.append((seat, event)))
    logs.append(0, E1)
    logs.append(1, E2)
    logs.append(0, E3)
    assert heard == [(0, E1), (1, E2), (0, E3)]


@pytest.mark.parametrize(
    ("observed", "listens"),
    [(False, False), (True, False), (False, True), (True, True)],
    ids=["unobserved", "observed", "listened", "observed-and-listened"],
)
def test_a_run_keeps_the_logs_exactly_when_asked(observed: bool, listens: bool) -> None:
    """red under: `play_game` making the logs whatever it is asked -- an
    unobserved playout would then build every event -- or only for one of the
    two arguments."""
    game = check_source(HEARTS)
    world: list[RuntimeState] = []
    heard: list[ObservationEvent] = []
    play_game(
        game,
        random.Random(0),
        observer=(lambda _seat, event: heard.append(event)) if listens else None,
        on_first_decision=world.append,
        observed=observed,
    )
    keeps = observed or listens
    assert (world[0].observations is not None) is keeps
    if keeps:
        assert world[0].observations is not None
        delivered = sum(len(log) for log in world[0].observations.snapshot().values())
        assert delivered > 0
        if listens:
            assert delivered == len(heard)


def _sites(pred: Any) -> set[str]:
    """Every node satisfying `pred` under `cardlang/`, as
    "module.enclosing_function"."""
    sites: set[str] = set()
    for path in sorted(CARDLANG.rglob("*.py")):
        tree = ast.parse(path.read_text())
        spans = [
            (node.lineno, node.end_lineno or node.lineno, node.name)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        for node in ast.walk(tree):
            if isinstance(node, ast.AST) and pred(node):
                lineno = getattr(node, "lineno")
                enclosing = [name for lo, hi, name in spans if lo <= lineno <= hi]
                sites.add(f"{path.stem}.{enclosing[-1] if enclosing else '<module>'}")
    return sites


def test_the_logs_are_made_only_by_the_run() -> None:
    """red under: a caller building its own `ObservationLogs` -- for instance
    `replay.run` keeping a second copy beside the world's -- the scrape gains
    that site."""

    def makes(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and (node.func.id if isinstance(node.func, ast.Name) else node.func.attr)
            == "ObservationLogs"
        )

    assert _sites(makes) == {"driver.play_game"}, (
        "the table's Observation Logs are made by the run (`play_game`), so "
        "every reader reads the one the run kept"
    )


def test_the_world_s_logs_are_touched_only_by_their_owners() -> None:
    """red under: any read of `observations` off a world outside its three
    owners -- an interpreter rule reading a seat's log, or a caller appending
    to it -- the scrape gains that site. This is what keeps the logs on the
    world from becoming a second road to a seat's knowledge: the interpreter
    writes them through `Ctx.observe` and never reads them."""

    def touches(node: ast.AST) -> bool:
        return isinstance(node, ast.Attribute) and node.attr == "observations"

    assert _sites(touches) == {
        "state.__init__",  # declared, None
        "state.observing",  # the one predicate an emitter reads
        "state.observe",  # the one write
        "driver.play_game",  # made, when the run is observed
        "observe.logs_of",  # the one read, a snapshot
    }


def test_a_snapshot_is_read_only_through_logs_of() -> None:
    """red under: a reader calling `snapshot()` on the aggregate itself
    rather than through `observe.logs_of`, which refuses a world whose run was
    not observed -- the scrape gains that site."""

    def snapshots(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "snapshot"
        )

    assert _sites(snapshots) == {"observe.logs_of"}


def test_an_unobserved_world_has_no_logs_to_read() -> None:
    """red under: `logs_of` answering an empty table for an unobserved run --
    a reader would then derive every seat's view with no log, silently."""
    game = check_source(HEARTS)
    world: list[RuntimeState] = []
    play_game(game, random.Random(0), on_first_decision=world.append)
    from cardlang.runtime.observe import logs_of

    with pytest.raises(AssertionError):
        logs_of(world[0])


def test_a_log_is_the_sequence_type_derive_reads() -> None:
    """The one type every reader is handed (`DecisionNode.obs_logs`, `derive`'s
    argument): a snapshot is a `Sequence` of events, so a reader cannot be
    handed a live list by one route and a frozen log by another."""
    log = _logs().snapshot()[0]
    assert isinstance(log, ObservationLog)
