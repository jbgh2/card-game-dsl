"""[[paused-run]]s: a line of play held at a decision, so the adapter's next
pick on that line advances it instead of replaying it from the first pick.

The adapter's state is ``(seed, script, history)``, and every query it answers
is answered as `replay.run` over that history answers it. Replaying is the
whole cost of a query, and a line walked one pick at a time replays its
prefix at every pick. A Paused Run keeps the run waiting at its decision; a
query one pick further along the same line hands it that pick, and it plays
on to the next decision.

The seam is `PausedRun`: start, resume by one pick, close. Two
implementations stand behind it, listed in `IMPLEMENTATIONS`. `ReplayedRun`
replays at every resume, which is the adapter without a pool and the second
implementation that keeps the seam from taking the shape of the first.
`ThreadedRun` holds the run on its own thread, handed one pick at a time, so
exactly one thread runs the interpreter at any moment. Nothing outside an
implementation depends on how it holds a run, so an implementation on another
substrate (a greenlet) takes the same seam, the same pool and the same tests.
What makes that hold is fixed here, not in either implementation: a pool
belongs to one OS thread (`_pool`), a run starts in a copy of the caller's
context, and an exception a run raises reaches the caller as itself.

The `RunPool` keeps up to `POOL_CAP` runs per OS thread, keyed by line and
history, least recently used first out. A run is consumed when it is
advanced, since a paused run can be continued along one pick and cannot be
copied: a state left behind on the old history replays when it next asks. A
query is answered from the pool only as a `Lease`, stamped with the run's
generation; advancing or closing a run moves its generation on, so a node the
run has since moved past is never read again, only asked for anew.

Contract
--------
Assumes: `replay.run` is the definition of what a query at ``(path, seed,
script, history)`` answers; its ``beyond`` continuation is asked at each pick
past the history while every phase frame stands.
Establishes: a node handed out under a fresh `Lease` is the one `replay.run`
returns for that history, up to identity of the world object; a lease goes
stale the moment its run is advanced or closed; at most `POOL_CAP` runs are
live per OS thread, and `clear` releases every one; a hand-off unanswered
for `HAND_OFF_BOUND` seconds raises `PausedRunStalled`; a pick the paused
decision does not offer is answered by a fresh run, so it raises what its
replay raises.
Illegal after: reading a node whose lease is stale; reaching the pool from
anywhere but `CardlangState` (`replay.py` above all, which is the oracle the
pool is judged against); a run resumed by a thread other than the one whose
pool holds it.
"""

from __future__ import annotations

import contextvars
import queue
import threading
import weakref
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from cardlang.openspiel import replay
from cardlang.runtime.chance import Outcome
from cardlang.runtime.state import ChooserAbort

Node = replay.DecisionNode | replay.TerminalNode
# A line of play: the game file, the shuffle seed and the Draw Script.
Line = tuple[str, int, tuple[Outcome, ...]]

# Runs kept per OS thread. 0 keeps none: every query replays.
POOL_CAP = 8

# Seconds a caller waits for a run to reach its next decision before refusing.
HAND_OFF_BOUND = 600.0

# A run's thread is given at least the stack a main thread has, since the
# interpreter recurses as deeply on one as on the other; some platforms give
# a new thread far less by default.
_RUN_STACK = 16 * 1024 * 1024

THREAD_PREFIX = "cardlang paused run"


class PausedRunStalled(RuntimeError):
    """A Paused Run did not reach its next decision within `HAND_OFF_BOUND`."""


class PausedRun(Protocol):
    """One line held at a decision.

    ``generation`` moves on at every `resume` and at `close`, before either
    acts, so a node handed out before it is stale from that moment."""

    generation: int

    def start(self) -> Node:
        """Play the recorded history; the node past it."""
        ...

    def resume(self, action: int) -> Node:
        """Play one more pick; the node past it. Only from a decision node,
        and only with one of its legal actions."""
        ...

    def close(self) -> None:
        """Abandon the run and release what holds it."""
        ...


class ReplayedRun:
    """A run held as its history: every resume replays it."""

    def __init__(self, line: Line, history: tuple[int, ...]) -> None:
        self.line = line
        self.history = history
        self.generation = 0

    def start(self) -> Node:
        return _replay(self.line, self.history)

    def resume(self, action: int) -> Node:
        self.generation += 1
        self.history = self.history + (action,)
        return _replay(self.line, self.history)

    def close(self) -> None:
        self.generation += 1


def _replay(line: Line, history: tuple[int, ...]) -> Node:
    path, seed, script = line
    return replay.run(path, seed, history, script=script)


class _Close:
    """The signal that abandons a run waiting at a decision."""


@dataclass(frozen=True)
class _Raised:
    """An exception a run raised, carried to the caller to be raised there."""

    exc: BaseException


class ThreadedRun:
    """A run held on its own thread, waiting at a decision for its next pick.

    The run is `replay.run` with a continuation: past the history, each pick
    hands the decision to the caller and waits for the pick. The caller waits
    while the run plays, so one thread runs the interpreter at a time."""

    def __init__(self, line: Line, history: tuple[int, ...]) -> None:
        self.line = line
        self.history = history
        self.generation = 0
        self._to_run: queue.SimpleQueue[int | _Close] = queue.SimpleQueue()
        self._to_caller: queue.SimpleQueue[Node | _Raised] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None

    def start(self) -> Node:
        path, seed, script = self.line
        game, _ = replay.load(path)
        logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(game.players.count)}
        world: list[Any] = []

        def listen(moment: replay.Moment) -> None:
            if isinstance(moment, replay.Seen):
                logs[moment.player].append(moment.event)

        def hand_off(decider: int, legal: list[int]) -> int:
            self._to_caller.put(replay.DecisionNode(decider, list(legal), world[0], logs))
            pick = self._to_run.get()
            if isinstance(pick, _Close):
                # The pause `replay.run` already knows: the run unwinds as a
                # suspended one, without the iteration's `after_each`.
                raise ChooserAbort(decider, legal)
            return pick

        def body() -> None:
            try:
                node = replay.run(
                    path,
                    seed,
                    self.history,
                    on_first_decision=world.append,
                    script=script,
                    listen=listen,
                    beyond=hand_off,
                )
            except ChooserAbort:
                return  # closed while waiting
            except BaseException as exc:
                self._to_caller.put(_Raised(exc))
                return
            self._to_caller.put(node)

        context = contextvars.copy_context()
        # `stack_size` applies to threads created after it, process-wide, so it
        # is set and restored around this one creation.
        default = threading.stack_size(_RUN_STACK)
        try:
            self._thread = threading.Thread(
                target=context.run,
                args=(body,),
                name=f"{THREAD_PREFIX} {Path(path).name}",
                daemon=True,
            )
            self._thread.start()
        finally:
            threading.stack_size(default)
        return self._receive()

    def resume(self, action: int) -> Node:
        self.generation += 1
        self._to_run.put(action)
        return self._receive()

    def close(self) -> None:
        self.generation += 1
        if self._thread is not None and self._thread.is_alive():
            self._to_run.put(_Close())
            self._thread.join(timeout=HAND_OFF_BOUND)

    def _receive(self) -> Node:
        try:
            got = self._to_caller.get(timeout=HAND_OFF_BOUND)
        except queue.Empty:
            raise PausedRunStalled(
                f"the paused run of {Path(self.line[0]).name} (seed {self.line[1]}) "
                f"did not reach its next decision within {HAND_OFF_BOUND} seconds"
            ) from None
        if isinstance(got, _Raised):
            raise got.exc
        return got


# Every implementation behind the seam, for the tests that hold each to it.
IMPLEMENTATIONS: tuple[type[ReplayedRun] | type[ThreadedRun], ...] = (ReplayedRun, ThreadedRun)

# The implementation a pool starts its runs with.
IMPLEMENTATION: Callable[[Line, tuple[int, ...]], PausedRun] = ThreadedRun


class Lease:
    """A node handed out by the pool, readable while its run has not moved on."""

    def __init__(self, run: PausedRun) -> None:
        self.run = run
        self.generation = run.generation

    def fresh(self) -> bool:
        return self.run.generation == self.generation


@dataclass
class _Parked:
    run: PausedRun
    node: Node


def _close_all(parked: OrderedDict[tuple[Line, tuple[int, ...]], _Parked]) -> None:
    while parked:
        _, entry = parked.popitem()
        entry.run.close()


class RunPool:
    """The Paused Runs of one OS thread, least recently used first out."""

    def __init__(self) -> None:
        self._parked: OrderedDict[tuple[Line, tuple[int, ...]], _Parked] = OrderedDict()
        # An OS thread that ends with runs parked still releases them.
        weakref.finalize(self, _close_all, self._parked)

    def node(self, line: Line, history: tuple[int, ...]) -> tuple[Node, Lease]:
        key = (line, history)
        entry = self._parked.get(key)
        if entry is not None:
            self._parked.move_to_end(key)
            return entry.node, Lease(entry.run)
        if history:
            parent = self._parked.pop((line, history[:-1]), None)
            if parent is not None:
                node = parent.node
                if isinstance(node, replay.DecisionNode) and history[-1] in node.legal:
                    return self._park(key, parent.run, lambda: parent.run.resume(history[-1]))
                parent.run.close()  # an unoffered pick is a fresh run's to refuse
        run = IMPLEMENTATION(line, history)
        return self._park(key, run, run.start)

    def _park(
        self, key: tuple[Line, tuple[int, ...]], run: PausedRun, advance: Callable[[], Node]
    ) -> tuple[Node, Lease]:
        try:
            node = advance()
        except BaseException:
            run.close()
            raise
        self._parked[key] = _Parked(run, node)
        while len(self._parked) > POOL_CAP:
            _, evicted = self._parked.popitem(last=False)
            evicted.run.close()
        return node, Lease(run)

    def clear(self) -> None:
        _close_all(self._parked)

    def __len__(self) -> int:
        return len(self._parked)


_LOCAL = threading.local()


def _pool() -> RunPool:
    """This OS thread's pool: a run is resumed only by the thread that holds
    it."""
    pool: RunPool | None = getattr(_LOCAL, "pool", None)
    if pool is None:
        pool = _LOCAL.pool = RunPool()
    return pool


def node(line: Line, history: tuple[int, ...]) -> tuple[Node, Lease | None]:
    """What a query at ``history`` on ``line`` answers, and the lease it is
    read under; no lease when the pool keeps nothing."""
    if POOL_CAP <= 0:
        return _replay(line, history), None
    return _pool().node(line, history)


def clear() -> None:
    """Release every run this OS thread's pool holds."""
    _pool().clear()


def live() -> int:
    """How many runs this OS thread's pool holds."""
    return len(_pool())
