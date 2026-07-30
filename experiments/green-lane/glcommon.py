"""Green Lane experiment: pyspiel registration + replay memoization.

The corpus adapter (`cardlang.openspiel.game`) registers only registry games
from `docs/games/`. This experiment lives outside the corpus, so it repeats
the small registration dance here with three deliberate differences:

- the game files load from THIS directory;
- the chance root has ONE seed — Green Lane has no shuffle, so every seed
  replays the identical deal (the corpus adapter samples 4096);
- the declared utility is zero-sum (Green Lane's scoring mirrors by
  construction), so `exploitability()` accepts the game.

It also wraps `cardlang.openspiel.replay.run` in a bounded memo: the function
is a pure map from (path, seed, history) to the paused/terminal result, and
tree-walking algorithms (CFR, best response) revisit the same nodes every
iteration. The corpus adapter re-simulates per state object; the memo makes
whole-tree solvers feasible without touching the package.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.game import CardlangState, _Observer

HERE = Path(__file__).resolve().parent

GAMES: dict[str, str] = {
    "greenlane": "green-lane.cardlang",
    "greenlane_mini": "green-lane-mini.cardlang",
}


# --- replay memo -----------------------------------------------------------

_orig_run = replay.run


@functools.lru_cache(maxsize=300_000)
def _cached_run(path_str: str, seed: int, history: tuple[int, ...]) -> Any:
    return _orig_run(path_str, seed, history)


def _run_dispatch(
    path_str: str,
    seed: int,
    history: tuple[int, ...],
    on_first_decision: Any = None,
) -> Any:
    if on_first_decision is not None:  # side-effecting caller: never memoize
        return _orig_run(path_str, seed, history, on_first_decision)
    return _cached_run(path_str, seed, history)


def install_replay_memo() -> None:
    replay.run = _run_dispatch


def replay_memo_info() -> Any:
    return _cached_run.cache_info()


# The information-state string is likewise a pure function of
# (path, seed, history, player) — tree-walking solvers re-request it at every
# visit, and the render walks the whole observation log each time. Memoizing
# it cuts CFR wall-clock several-fold on this adapter.

_orig_infostate = CardlangState.information_state_string


def install_infostate_memo() -> None:
    cache: dict[tuple[str, int, tuple[int, ...], int], str] = {}

    def memoized(self: CardlangState, player: int | None = None) -> str:
        if self._seed is None:
            return ""
        if player is None:
            player = self.current_player()
        key = (self._path, self._seed, tuple(self._history_ids), player)
        hit = cache.get(key)
        if hit is None:
            hit = _orig_infostate(self, player)
            if len(cache) < 600_000:
                cache[key] = hit
        return hit

    CardlangState.information_state_string = memoized  # type: ignore[method-assign]


# --- registration ----------------------------------------------------------


class _State(CardlangState):
    """CardlangState with a configurable seed count at the chance root."""

    def __init__(
        self, game: pyspiel.Game, path: str, num_players: int, num_seeds: int
    ) -> None:
        super().__init__(game, path, num_players)
        self._num_seeds = num_seeds

    def chance_outcomes(self) -> list[tuple[int, float]]:
        assert self._seed is None
        p = 1.0 / self._num_seeds
        return [(i, p) for i in range(self._num_seeds)]

    def clone(self) -> _State:
        copy = _State(self.get_game(), self._path, self._num_players, self._num_seeds)
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy


def register(
    short_name: str, filename: str, num_seeds: int = 1, base_dir: Path | None = None
) -> None:
    path = str((base_dir or HERE) / filename)
    game_ast, space = replay.load(path)
    num_players = game_ast.players.low
    assert game_ast.max_length is not None
    game_type = pyspiel.GameType(
        short_name=short_name,
        long_name=f"Cardlang experiment {game_ast.name}",
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
        information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
        utility=pyspiel.GameType.Utility.ZERO_SUM,
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
        min_utility=-1000.0,
        max_utility=1000.0,
        utility_sum=0.0,
        max_game_length=game_ast.max_length,
    )

    # pyspiel ships no stubs, so its `Game` is `Any` (the same exemption
    # `cardlang.openspiel.game` carries in pyproject; local here because a
    # script is not a package module an override can name).
    class _Game(pyspiel.Game):  # type: ignore[misc]
        def __init__(self, params: Any = None) -> None:
            super().__init__(game_type, game_info, params or {})

        def new_initial_state(self) -> _State:
            return _State(self, path, num_players, num_seeds)

        def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> _Observer:
            return _Observer()

    pyspiel.register_game(game_type, _Game)


def register_all(num_seeds: int = 1) -> None:
    install_replay_memo()
    for short_name, filename in GAMES.items():
        register(short_name, filename, num_seeds)
