"""Every fully-kernel game as a registered ``pyspiel.Game``.

One general adapter (SP1 spec): the state is ``(seed, history)`` over the
re-simulation engine — that seed being the [[shuffle-seed]] the root chance node
draws, fixed and unexposed for a Chance-Free Game, whose tree carries no such
node — the action space and information states are DERIVED, and
registration is a loop over the game table — adding a fully-kernel game to the
table is the whole per-game cost. Importing this module registers every game
in the table; load with e.g. ``pyspiel.load_game("cardlang_hearts")``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.infostate import information_state
from cardlang.runtime.errors import ShadowGuardError

_NUM_SEEDS = 4096  # sampled deal space at the root chance node (known limitation)
# The seed a Chance-Free Game runs under. Any value does: its generator refuses
# every draw (`cardlang.runtime.chance`), so no branch of the collapsed node
# could have differed from any other.
_CHANCE_FREE_SEED = 0
_GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"

from cardlang.openspiel.registry import GAMES as GAMES


class _Observer:
    """Minimal observer providing the information-state string (no tensors)."""

    def __init__(self) -> None:
        self.tensor = None
        self.dict: dict[str, Any] = {}

    def set_from(self, state: CardlangState, player: int) -> None:
        pass  # no tensor representation

    def string_from(self, state: CardlangState, player: int) -> str:
        return state.information_state_string(player)


class CardlangState(pyspiel.State):
    """``_seed is None`` exactly while a root chance node is pending.

    A Chance-Free Game has no such node, so its seed is fixed at construction
    and the predicate stays true by definition rather than carrying a second
    meaning: `current_player` never reports CHANCE for it, and the root is its
    first decision.
    """

    def __init__(
        self, game: pyspiel.Game, path: str, num_players: int, chance_free: bool
    ) -> None:
        super().__init__(game)
        self._path = path
        self._num_players = num_players
        self._chance_free = chance_free
        self._seed: int | None = _CHANCE_FREE_SEED if chance_free else None
        self._history_ids: list[int] = []
        self._cache_key: Any = object()
        self._cache: replay.DecisionNode | replay.TerminalNode | None = None

    def _run(self) -> replay.DecisionNode | replay.TerminalNode:
        assert self._seed is not None
        key = (self._seed, tuple(self._history_ids))
        if self._cache_key != key:
            self._cache = replay.run(self._path, self._seed, tuple(self._history_ids))
            self._cache_key = key
        assert self._cache is not None
        return self._cache

    def current_player(self) -> int:
        if self._seed is None:
            return pyspiel.PlayerId.CHANCE
        r = self._run()
        return pyspiel.PlayerId.TERMINAL if isinstance(r, replay.TerminalNode) else r.player

    def _legal_actions(self, player: int) -> list[int]:
        r = self._run()
        assert isinstance(r, replay.DecisionNode)
        return r.legal

    def chance_outcomes(self) -> list[tuple[int, float]]:
        if self._chance_free:
            # Unreachable while the classification is right — pyspiel asks only
            # at a chance node, and this game declares none. Saying so beats the
            # bare assert it replaces: a wrong classification surfaces as the
            # sentence that names it, not as a traceback the reader must decode.
            raise ShadowGuardError(
                "cardlang.runtime.chance.chance_sites",
                f"pyspiel asked {self._path} for chance outcomes, but it is "
                f"registered DETERMINISTIC because nothing in it draws",
            )
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
            return f"Chance(seed={action})"
        _, space = replay.load(self._path)
        return space.to_string(action)

    def is_terminal(self) -> bool:
        return self._seed is not None and isinstance(self._run(), replay.TerminalNode)

    def returns(self) -> list[float]:
        if self._seed is None:
            return [0.0] * self._num_players
        r = self._run()
        return r.returns if isinstance(r, replay.TerminalNode) else [0.0] * self._num_players

    def information_state_string(self, player: int | None = None) -> str:
        if self._seed is None:
            return ""  # chance root
        if player is None:
            player = self.current_player()
        r = self._run()
        if not isinstance(r, replay.DecisionNode):
            return ""
        return information_state(player, r.rs, r.obs_logs[player])

    def clone(self) -> CardlangState:
        copy = CardlangState(
            self.get_game(), self._path, self._num_players, self._chance_free
        )
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy

    def __str__(self) -> str:
        if self._chance_free:
            return f"history={self._history_ids}"
        return f"seed={self._seed} history={self._history_ids}"


def _register(short_name: str, filename: str) -> None:
    path = str(_GAMES_DIR / filename)
    game_ast, space = replay.load(path)
    # The one read of the classification per registered game. The GameType's
    # chance mode, the declared outcome count and the state's opening node all
    # come off this single answer, so they cannot describe different games.
    chance_free = replay.chance_free(path)
    num_players = game_ast.players.low
    assert game_ast.max_length is not None, "resolve() must reject a missing max_length"
    game_type = pyspiel.GameType(
        short_name=short_name,
        long_name=f"Cardlang {game_ast.name}",
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=(
            pyspiel.GameType.ChanceMode.DETERMINISTIC
            if chance_free
            else pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC
        ),
        information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
        utility=pyspiel.GameType.Utility.GENERAL_SUM,
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
        max_chance_outcomes=0 if chance_free else _NUM_SEEDS,
        num_players=num_players,
        min_utility=-100000.0,  # loose static bounds; true scores are far inside
        max_utility=100000.0,
        utility_sum=None,
        max_game_length=game_ast.max_length,
    )

    class _Game(pyspiel.Game):
        def __init__(self, params: Any = None) -> None:
            super().__init__(game_type, game_info, params or {})

        def new_initial_state(self) -> CardlangState:
            return CardlangState(self, path, num_players, chance_free)

        def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> _Observer:
            return _Observer()

    pyspiel.register_game(game_type, _Game)


for _short_name, _filename in GAMES.items():
    _register(_short_name, _filename)
