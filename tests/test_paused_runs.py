"""A Paused Run answers every query as the replay of its history answers it.

The adapter's state is `(seed, script, history)`, and every query is answered
as `replay.run` over that history answers it. A [[paused-run]] answers it
without replaying when one is waiting at the history or one pick before it
(`cardlang.openspiel.paused`). These tests hold that pool to the replay it
stands in for, and to the guarantees that make it safe to stand there.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        at every step of a walk through the pyspiel API — clones held
                 and returned to, so a run is consumed under a state that still
                 points at it — the seat to move, the legal actions, every
                 seat's information state and the terminal returns equal
                 `replay.run`'s over the same `(seed, script, history)`; a node
                 whose run has moved on is never read; the live Paused Runs
                 never exceed the cap and every one is released when the pool
                 is cleared; a hand-off that stalls past its bound raises; a
                 pick the paused decision does not offer raises what its replay
                 raises.
domain:          two axes, crossed. The games: `harness.REGISTERED_GAMES`. The
                 implementations behind the seam: `paused.IMPLEMENTATIONS`, the
                 replaying one included, so the seam is held by two
                 implementations from the start and an implementation added
                 later takes the same grid.
registry:        `tests/openspiel_ready/harness.py::REGISTERED_GAMES`;
                 `cardlang.openspiel.paused.IMPLEMENTATIONS`; the oracle,
                 `replay.run`, is called directly, and that `replay.py` never
                 reaches the pool is `test_only_the_adapter_reaches_the_pool`.
does not prove:  agreement past each walk's step budget; the long-line witness
                 compares returns at the end of one full Hearts match, not every
                 step of it.

red under: a resume that leaves the generation where it was turns the
`ThreadedRun` column of the grid red, and so does a node handed out with
another seat's observation log; a lease that never goes stale turns
`test_a_consumed_run_is_never_read` red; a hand-off that never answers is the
raise `test_a_stalled_hand_off_raises` pins.
"""

from __future__ import annotations

import ast
import random
import re
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # noqa: E402
from cardlang.openspiel import paused, replay  # noqa: E402
from cardlang.openspiel.infostate import information_state  # noqa: E402
from tests.openspiel_ready.harness import REGISTERED_GAMES  # noqa: E402

# Steps per walk: deep enough that every game makes real decisions and every
# held clone falls behind its line, shallow enough that the oracle's own
# replay of each step stays cheap.
_STEPS = 30
_DEAL = 5


@pytest.fixture
def pool_of(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Set the pool's implementation and cap for one test, from an empty pool,
    and leave it empty."""

    def configure(implementation: type[Any], cap: int = paused.POOL_CAP) -> None:
        paused.clear()
        monkeypatch.setattr(paused, "IMPLEMENTATION", implementation)
        monkeypatch.setattr(paused, "POOL_CAP", cap)

    yield configure
    paused.clear()


def _oracle(state: Any) -> replay.DecisionNode | replay.TerminalNode:
    return replay.run(
        state._path, state._seed, tuple(state._history_ids), script=state._script
    )


def _agree(state: Any, where: str) -> None:
    """The state's every answer against the replay of its history."""
    if state.is_chance_node():
        return
    expected = _oracle(state)
    players = range(state.get_game().num_players())
    if isinstance(expected, replay.TerminalNode):
        assert state.is_terminal(), f"{where}: the replay ended, the state did not"
        assert state.returns() == expected.returns, f"{where}: returns"
        return
    assert not state.is_terminal(), f"{where}: the state ended, the replay did not"
    assert state.current_player() == expected.player, f"{where}: seat to move"
    assert state.legal_actions() == expected.legal, f"{where}: legal actions"
    for p in players:
        assert state.information_state_string(p) == information_state(
            p, expected.rs, expected.obs_logs[p]
        ), f"{where}: seat {p}'s information state"


def _walk(short_name: str, rnd: random.Random) -> None:
    game = pyspiel.load_game(short_name)
    state = game.new_initial_state()
    if state.is_chance_node():
        state.apply_action(_DEAL)
    held: list[Any] = []
    for step in range(_STEPS):
        _agree(state, f"{short_name} step {step}")
        if state.is_terminal():
            break
        if rnd.random() < 0.3:
            # Asked at once, the clone shares the run the walk then advances.
            held.append(state.clone())
            held[-1].legal_actions()
        if held and rnd.random() < 0.2:
            state = held.pop(rnd.randrange(len(held)))
        else:
            state.apply_action(rnd.choice(state.legal_actions()))
    for i, behind in enumerate(held):
        _agree(behind, f"{short_name} held clone {i}")


@pytest.mark.parametrize("implementation", paused.IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("short_name", [s for s, _ in REGISTERED_GAMES])
def test_a_paused_run_answers_as_the_replay_does(
    pool_of: Any, short_name: str, implementation: type[Any]
) -> None:
    pool_of(implementation)
    _walk(short_name, random.Random(short_name))


def test_cap_zero_is_the_replay(pool_of: Any) -> None:
    """With no room in the pool every query replays, and no run is held."""
    pool_of(paused.ThreadedRun, cap=0)
    before = threading.active_count()
    _walk("cardlang_hearts", random.Random(0))
    assert threading.active_count() == before
    assert paused.live() == 0


def _a_seen_pick(game: Any) -> tuple[Any, int]:
    """A Hearts state whose next pick changes seat 0's information state,
    and that pick."""
    state = game.new_initial_state()
    state.apply_action(_DEAL)
    while True:
        a = state.legal_actions()[0]
        after = state.clone()
        after.apply_action(a)
        if after.information_state_string(0) != state.information_state_string(0):
            return state, a
        state = after


def test_a_consumed_run_is_never_read(pool_of: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A state whose run another state has since advanced asks again rather
    than reading the moved world. Reddens under a lease that never goes stale:
    the held state then reads the world one pick on."""
    pool_of(paused.ThreadedRun)
    game = pyspiel.load_game("cardlang_hearts")
    state, pick = _a_seen_pick(game)
    paused.clear()
    held = state.clone()
    before = held.information_state_string(0)  # parks a run at this history
    moved = held.clone()
    moved.apply_action(pick)
    moved.information_state_string(0)  # advances that run one pick
    assert held.information_state_string(0) == before
    _agree(held, "the held state")

    monkeypatch.setattr(paused.Lease, "fresh", lambda self: True)
    paused.clear()
    held = state.clone()
    before = held.information_state_string(0)
    moved = held.clone()
    moved.apply_action(pick)
    moved.information_state_string(0)
    assert held.information_state_string(0) != before, (
        "the planted fault went unseen: a lease that never goes stale should "
        "have read the world one pick on"
    )


def test_a_copied_state_asks_again(pool_of: Any) -> None:
    """pyspiel copies a Python state with `copy.deepcopy`. A copy, or a state
    pickled and loaded, carries none of the answer its original read under a
    lease, so it asks again — after the original's run has moved on as well.
    Reddens when the copy takes the lease along (a run's queues cannot be
    copied) or the node (read past its run's next pick)."""
    import copy
    import pickle

    pool_of(paused.ThreadedRun)
    game = pyspiel.load_game("cardlang_hearts")
    state, pick = _a_seen_pick(game)
    state.legal_actions()  # read under a lease
    for twin in (copy.deepcopy(state), pickle.loads(pickle.dumps(state))):
        assert twin._answer.lease is None and twin._answer.node is None
        _agree(twin, "a copy at the paused history")
    behind = copy.deepcopy(state)
    state.apply_action(pick)
    state.legal_actions()  # advances the run the original read under
    _agree(behind, "a copy taken before its original's run moved on")


def test_the_live_runs_never_exceed_the_cap_and_clear_releases_them(pool_of: Any) -> None:
    pool_of(paused.ThreadedRun, cap=3)
    baseline = threading.active_count()
    game = pyspiel.load_game("cardlang_hearts")
    for deal in range(6):
        state = game.new_initial_state()
        state.apply_action(deal)
        state.apply_action(state.legal_actions()[0])
        state.legal_actions()
        assert paused.live() <= 3
        assert threading.active_count() <= baseline + 3
    paused.clear()
    assert paused.live() == 0
    for t in threading.enumerate():
        if t.name.startswith(paused.THREAD_PREFIX):
            t.join(timeout=5)
    assert threading.active_count() == baseline


def test_a_stalled_hand_off_raises(pool_of: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A run that never reaches its next decision raises past the bound,
    naming the line, instead of waiting for ever. The stall is planted: the
    run's replay blocks until the test releases it."""
    pool_of(paused.ThreadedRun)
    release = threading.Event()
    real = replay.run

    def stalled(*args: Any, **kwargs: Any) -> Any:
        release.wait()
        return real(*args, **kwargs)

    monkeypatch.setattr(paused, "HAND_OFF_BOUND", 0.2)
    monkeypatch.setattr(replay, "run", stalled)
    state = pyspiel.load_game("cardlang_hearts").new_initial_state()
    state.apply_action(_DEAL)
    try:
        with pytest.raises(paused.PausedRunStalled, match="hearts"):
            state.legal_actions()
    finally:
        release.set()


def test_a_pick_the_decision_does_not_offer_raises_what_its_replay_raises(
    pool_of: Any,
) -> None:
    pool_of(paused.ThreadedRun)
    state = pyspiel.load_game("cardlang_hearts").new_initial_state()
    state.apply_action(_DEAL)
    illegal = next(a for a in range(10_000) if a not in state.legal_actions())
    expected = state.clone()
    expected._history_ids.append(illegal)
    with pytest.raises(Exception) as oracle:
        _oracle(expected)
    state._apply_action(illegal)  # pyspiel's own apply refuses it first
    with pytest.raises(type(oracle.value), match=re.escape(str(oracle.value))):
        state.legal_actions()


def test_a_whole_match_runs_through_one_paused_run(pool_of: Any) -> None:
    """The longest line in the corpus walked to its end through the pool —
    every frame of a full Hearts match on the run's own thread — ending where
    its replay ends."""
    pool_of(paused.ThreadedRun)
    state = pyspiel.load_game("cardlang_hearts").new_initial_state()
    state.apply_action(_DEAL)
    rnd = random.Random(0)
    while not state.is_terminal():
        state.apply_action(rnd.choice(state.legal_actions()))
    assert len(state._history_ids) > 300, "not the long line this witness is for"
    _agree(state, "the end of the match")


def test_only_the_adapter_reaches_the_pool() -> None:
    """The pool stands behind `CardlangState` alone. `replay.py` above all
    never reaches it: the replay is the oracle the pool is judged against."""
    package = Path(ogame.__file__).resolve().parent.parent
    reaching = set()
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            if "cardlang.openspiel.paused" in names:
                reaching.add(path.relative_to(package.parent).as_posix())
    assert reaching == {"cardlang/openspiel/game.py"}
