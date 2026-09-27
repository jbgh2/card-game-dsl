"""A seat sees the same decision through pyspiel and at the table.

property:        A native playout — `driver.play_game` under a Chooser that
                 makes all of a call's picks at once, the route the table,
                 the LLM rigs and every playout test take — and pyspiel, fed
                 the same picks as action ids, agree at every decision they
                 both reach: the same seat is asked, over the same legal
                 action ids, and every seat's information state is the same
                 string, the `state:` segment and the observation log
                 included. Played to the end, the two agree on the returns,
                 and every seat's whole observation log is the log the
                 adapter's replay of the same picks records.
domain:          Every game in the adapter registry (`GAMES`), at each seed in
                 `_SEEDS`, under the game's reference policy where a uniform
                 draw does not finish it
                 (`tests/playout_policy.REFERENCE_POLICIES`), else uniformly. Compared at the Chooser calls `_CALLS` names that
                 the line reaches — the first decision of each call, the
                 position both routes have — and at the terminal position.
registry:        games: `cardlang.openspiel.registry.GAMES`; the generator a
                 `(path, seed)` plays under: `replay.generator_for`; the one
                 site a pick is recorded: `cardlang.runtime.chooser.decide`.
does not prove:  The positions inside a multi-pick call past its first pick:
                 a Chooser that makes its picks at once has no such position,
                 so only the adapter's routes reach them, and
                 tests/test_cli_surface.py holds `demo --at` to pyspiel there.
                 Lines under any other Chooser, calls outside
                 `_CALLS` (the final logs compare every event, so a record
                 missing or doubled anywhere is still caught), and seeds
                 outside `_SEEDS`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import (
    ReplayChooser,
    TerminalNode,
    generator_for,
    load,
    returns_for,
    run,
)
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from tests.playout_policy import reference_policy_for

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.game import _CHANCE_FREE_SEED, register_game_file

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"

_SEEDS = (0, 1)
_CALLS = frozenset({0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89})


@dataclass(frozen=True)
class _Call:
    """One Chooser call of the native line, as the table saw it asked."""

    at: int  # how many picks the line had made when the call was asked
    decider: int
    legal: tuple[int, ...]
    views: tuple[str, ...]  # every seat's information state, by seat


@dataclass(frozen=True)
class _NativeLine:
    history: tuple[int, ...]
    calls: tuple[_Call, ...]
    logs: dict[int, list[tuple[Any, ...]]]
    returns: list[float]


def _native(path: str, seed: int) -> _NativeLine:
    game, space = load(path)
    seats = game.players.count
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(seats)}
    world: list[RuntimeState] = []
    history: list[int] = []
    calls: list[_Call] = []
    # A generator of its own: a policy drawing from the game's would deal the
    # later hands differently from the adapter, whose Chooser draws nothing.
    rng = random.Random(f"route-agreement:{seed}")
    policy = reference_policy_for(Path(path).stem, rng) or random_chooser(rng)

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        index = len(calls)
        views = (
            tuple(information_state(q, world[0], logs[q]) for q in range(seats))
            if index in _CALLS
            else ()
        )
        legal = tuple(sorted({space.encode(c) for c in candidates}))
        calls.append(_Call(len(history), player, legal, views))
        picks = policy(player, candidates, count)
        history.extend(space.encode(pick) for pick in picks)
        return picks

    result = play_game(
        game,
        generator_for(path, seed),
        chooser=choose,
        observer=observe,
        on_first_decision=world.append,
    )
    return _NativeLine(tuple(history), tuple(calls), logs, returns_for(game, result))


def _replayed_logs(path: str, seed: int, history: tuple[int, ...]) -> dict[int, list[tuple[Any, ...]]]:
    game, space = load(path)
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(game.players.count)}

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    chooser = ReplayChooser(space, history)
    play_game(game, generator_for(path, seed), chooser=chooser, observer=observe)
    assert chooser.cursor == len(history), "the replay ended before the line's last pick"
    return logs


@pytest.mark.parametrize("seed", _SEEDS)
@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_a_seat_sees_the_same_decision_through_pyspiel_and_at_the_table(short_name: str, seed: int) -> None:
    """red under: record a Chooser call's picks as one aggregate `chose` in
    `chooser.decide`, or pop the phase frame in `driver.run_phase` when a
    Chooser suspends the run; pyspiel's string then differs at the first
    decision after a pick, or names fewer state variables."""
    path = str(GAMES_DIR / GAMES[short_name])
    line = _native(path, seed)
    state = pyspiel.load_game(register_game_file(Path(path))).new_initial_state()
    # A Chance-Free Game has no root chance node: its generator refuses every
    # draw, so the seed names no deal and only the policy's line varies.
    chance_free = not state.is_chance_node()
    if not chance_free:
        state.apply_action(seed)
    # pyspiel's state replays its whole history per query, so it walks only as
    # far as the last compared call; the returns come from one replay.
    applied = 0
    for index, call in enumerate(line.calls):
        if index not in _CALLS:
            continue
        for action in line.history[applied : call.at]:
            state.apply_action(action)
        applied = call.at
        where = f"{short_name} seed {seed}, call {index} (pick {call.at})"
        assert state.current_player() == call.decider, (
            f"{where}: pyspiel asks P{state.current_player()}, the table P{call.decider}"
        )
        assert tuple(state.legal_actions()) == call.legal, f"{where}: the legal action ids differ"
        for seat, view in enumerate(call.views):
            assert str(state.information_state_string(seat)) == view, (
                f"{where}: P{seat}'s information state differs between the routes"
            )
    end = run(path, _CHANCE_FREE_SEED if chance_free else seed, line.history)
    assert isinstance(end, TerminalNode), f"{short_name} seed {seed}: the adapter's line does not end"
    assert end.returns == line.returns
    replayed = _replayed_logs(path, seed, line.history)
    for seat, log in line.logs.items():
        assert replayed[seat] == log, (
            f"{short_name} seed {seed}: P{seat}'s observation log differs between the routes"
        )
