"""Undertow experiment: pyspiel registration + replay memo (the Green Lane
pattern, re-pointed at this directory; see ../green-lane/glcommon.py for the
commentary). Undertow shuffles a full deck, so the chance root SAMPLES the
deal space — default 2048 seeds."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.game import CardlangState, _Observer

HERE = Path(__file__).resolve().parent
SHORT_NAME = "undertow"
FILENAME = "undertow.cardlang"

_orig_run = replay.run


@functools.lru_cache(maxsize=400_000)
def _cached_run(path_str: str, seed: int, history: tuple[int, ...]) -> Any:
    return _orig_run(path_str, seed, history)


def _run_dispatch(
    path_str: str, seed: int, history: tuple[int, ...], on_first_decision: Any = None
) -> Any:
    if on_first_decision is not None:
        return _orig_run(path_str, seed, history, on_first_decision)
    return _cached_run(path_str, seed, history)


class _State(CardlangState):
    def __init__(self, game: pyspiel.Game, path: str, num_players: int, num_seeds: int) -> None:
        super().__init__(game, path, num_players)
        self._num_seeds = num_seeds

    def chance_outcomes(self) -> list[tuple[int, float]]:
        assert self._seed is None
        p = 1.0 / self._num_seeds
        return [(i, p) for i in range(self._num_seeds)]

    def clone(self) -> "_State":
        copy = _State(self.get_game(), self._path, self._num_players, self._num_seeds)
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy


def register(num_seeds: int = 2048) -> str:
    replay.run = _run_dispatch  # type: ignore[assignment]
    path = str(HERE / FILENAME)
    game_ast, space = replay.load(path)
    num_players = game_ast.players.low
    game_type = pyspiel.GameType(
        short_name=SHORT_NAME,
        long_name="Cardlang experiment Undertow",
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
        information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
        utility=pyspiel.GameType.Utility.CONSTANT_SUM,  # tricks sum to 13
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
        max_chance_outcomes=num_seeds,
        num_players=num_players,
        min_utility=0.0,
        max_utility=13.0,
        utility_sum=13.0,
        max_game_length=game_ast.max_length or 800,
    )

    class _Game(pyspiel.Game):
        def __init__(self, params: Any = None) -> None:
            super().__init__(game_type, game_info, params or dict())

        def new_initial_state(self) -> _State:
            return _State(self, path, num_players, num_seeds)

        def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> _Observer:
            return _Observer()

    pyspiel.register_game(game_type, _Game)
    return path
