"""Salvo-mini pyspiel registration (the ut/glcommon pattern re-pointed at
this directory) with one addition: the chance root takes an explicit
SEED LIST, not a count. A single-element list is a fixed public deal
(Green Lane's exactly solvable shape — the only hidden information is
staged-but-unflipped cards); a longer list is a deal-sampled game.

Also installs the replay memo (full-Pause lru). Memory note: each cached
entry holds a small mini world; the solve script sizes sampled runs so
the tree stays within the memo bound instead of thrashing it."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Sequence

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.game import CardlangState, _Observer

HERE = Path(__file__).resolve().parent
FILENAME = "salvo-mini.cardlang"

MEMO_MAX = 800_000

_orig_run = replay.run


@functools.lru_cache(maxsize=MEMO_MAX)
def _cached_run(path_str: str, seed: int, history: tuple[int, ...]) -> Any:
    return _orig_run(path_str, seed, history)


def _run_dispatch(
    path_str: str, seed: int, history: tuple[int, ...], on_first_decision: Any = None
) -> Any:
    if on_first_decision is not None:
        return _orig_run(path_str, seed, history, on_first_decision)
    return _cached_run(path_str, seed, history)


def memo_info() -> Any:
    return _cached_run.cache_info()


class _State(CardlangState):
    def __init__(self, game: pyspiel.Game, path: str, num_players: int, seeds: tuple[int, ...]) -> None:
        super().__init__(game, path, num_players)
        self._seeds = seeds

    def chance_outcomes(self) -> list[tuple[int, float]]:
        assert self._seed is None
        p = 1.0 / len(self._seeds)
        return [(s, p) for s in self._seeds]

    def clone(self) -> "_State":
        copy = _State(self.get_game(), self._path, self._num_players, self._seeds)
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy


def register(short_name: str, seeds: Sequence[int]) -> str:
    replay.run = _run_dispatch
    seeds_t = tuple(seeds)
    path = str(HERE / FILENAME)
    game_ast, space = replay.load(path)
    num_players = game_ast.players.low
    game_type = pyspiel.GameType(
        short_name=short_name,
        long_name="Cardlang experiment Salvo-mini",
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
        information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
        utility=pyspiel.GameType.Utility.ZERO_SUM,  # final is the differential
        reward_model=pyspiel.GameType.RewardModel.TERMINAL,
        max_num_players=num_players,
        min_num_players=num_players,
        provides_information_state_string=True,
        provides_information_state_tensor=False,
        provides_observation_string=False,
        provides_observation_tensor=False,
        provides_factored_observation_string=False,
    )
    game_info = pyspiel.GameInfo(
        num_distinct_actions=space.num_distinct_actions,
        max_chance_outcomes=max(seeds_t) + 1,
        num_players=num_players,
        min_utility=-96.0,
        max_utility=96.0,
        utility_sum=0.0,
        max_game_length=game_ast.max_length or 60,
    )

    # pyspiel ships no stubs, so its `Game` is `Any` (see glcommon.py).
    class _Game(pyspiel.Game):  # type: ignore[misc]
        def __init__(self, params: Any = None) -> None:
            super().__init__(game_type, game_info, params or dict())

        def new_initial_state(self) -> _State:
            return _State(self, path, num_players, seeds_t)

        def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> _Observer:
            return _Observer()

    pyspiel.register_game(game_type, _Game)
    return path
