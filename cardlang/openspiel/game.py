"""Hearts as a registered ``pyspiel.Game``.

Wraps the cardlang runtime via the re-simulation engine (:mod:`replay`). The
state is ``(seed, history)``: a root chance node fixes the seed (one of ``K``
deal outcomes), then players choose cards (action ids 0–51). Cloning is trivial
(copy two values) because every query re-simulates.

Importing this module registers the game; load it with
``pyspiel.load_game("cardlang_hearts")``.
"""

from __future__ import annotations

from typing import Any

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.encoding import NUM_DISTINCT_ACTIONS, action_to_card
from cardlang.openspiel.infostate import hearts_information_state

_NUM_PLAYERS = 4
_NUM_SEEDS = 4096  # distinct deal outcomes at the root chance node

_GAME_TYPE = pyspiel.GameType(
    short_name="cardlang_hearts",
    long_name="Cardlang Hearts",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=_NUM_PLAYERS,
    min_num_players=_NUM_PLAYERS,
    provides_information_state_string=True,
    provides_information_state_tensor=False,
    provides_observation_string=False,
    provides_observation_tensor=False,
    provides_factored_observation_string=False,
)
_GAME_INFO = pyspiel.GameInfo(
    num_distinct_actions=NUM_DISTINCT_ACTIONS,
    max_chance_outcomes=_NUM_SEEDS,
    num_players=_NUM_PLAYERS,
    min_utility=-200.0,
    max_utility=200.0,
    utility_sum=0.0,
    max_game_length=10000,
)


class CardlangHeartsGame(pyspiel.Game):
    def __init__(self, params: Any = None) -> None:
        super().__init__(_GAME_TYPE, _GAME_INFO, params or dict())

    def new_initial_state(self) -> "CardlangHeartsState":
        return CardlangHeartsState(self)

    def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> "_HeartsObserver":
        return _HeartsObserver()


class CardlangHeartsState(pyspiel.State):
    def __init__(self, game: pyspiel.Game) -> None:
        super().__init__(game)
        self._seed: int | None = None
        self._history_ids: list[int] = []
        self._cache_key: Any = object()  # sentinel so first _run() always computes
        self._cache: replay.Pause | replay.Terminal | None = None

    # --- re-sim memoised per (seed, history) ---
    def _run(self) -> replay.Pause | replay.Terminal:
        assert self._seed is not None
        key = (self._seed, tuple(self._history_ids))
        if self._cache_key != key:
            self._cache = replay.run(self._seed, tuple(self._history_ids))
            self._cache_key = key
        assert self._cache is not None
        return self._cache

    # --- pyspiel API ---
    def current_player(self) -> int:
        if self._seed is None:
            return pyspiel.PlayerId.CHANCE
        r = self._run()
        return pyspiel.PlayerId.TERMINAL if isinstance(r, replay.Terminal) else r.player

    def _legal_actions(self, player: int) -> list[int]:
        r = self._run()
        assert isinstance(r, replay.Pause)
        return r.legal

    def chance_outcomes(self) -> list[tuple[int, float]]:
        assert self._seed is None
        p = 1.0 / _NUM_SEEDS
        return [(i, p) for i in range(_NUM_SEEDS)]

    def _apply_action(self, action: int) -> None:
        if self._seed is None:
            self._seed = int(action)
        else:
            self._history_ids.append(int(action))

    def _action_to_string(self, player: int, action: int) -> str:
        if player == pyspiel.PlayerId.CHANCE:
            return f"Deal(seed={action})"
        return str(action_to_card(action))

    def is_terminal(self) -> bool:
        return self._seed is not None and isinstance(self._run(), replay.Terminal)

    def returns(self) -> list[float]:
        if self._seed is None:
            return [0.0] * _NUM_PLAYERS
        r = self._run()
        return r.returns if isinstance(r, replay.Terminal) else [0.0] * _NUM_PLAYERS

    def information_state_string(self, player: int | None = None) -> str:
        if player is None:
            player = self.current_player()
        r = self._run()
        if not isinstance(r, replay.Pause):
            return ""
        return hearts_information_state(player, r.rs, r.observed_log)

    def clone(self) -> "CardlangHeartsState":
        copy = CardlangHeartsState(self.get_game())
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy

    def __str__(self) -> str:
        return f"seed={self._seed} history={self._history_ids}"


class _HeartsObserver:
    """Minimal observer providing the information-state string (no tensors)."""

    def __init__(self) -> None:
        self.tensor = None
        self.dict: dict[str, Any] = {}

    def set_from(self, state: CardlangHeartsState, player: int) -> None:
        pass  # no tensor representation

    def string_from(self, state: CardlangHeartsState, player: int) -> str:
        return state.information_state_string(player)


pyspiel.register_game(_GAME_TYPE, CardlangHeartsGame)
