"""Generalized re-simulation engine: drive ANY fully-kernel game
action-by-action by replaying a recorded action history through ``play_game``.

The OpenSpiel ``State`` is just ``(seed, history)``. Every query re-runs the
game with a :class:`ReplayChooser` that decodes and returns the recorded
actions in order and raises ``ChooserAbort`` at the first decision beyond the
history — surfacing the current decision point with the live world and the
per-player observation logs attached. The chooser makes no RNG calls, so a run
is a pure function of ``seed``. Games with `instantiate` mechanics are
rejected: their Python phases emit no observations (info-set debt,
docs/kernel-migration.md)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, cast

from cardlang.ast import nodes as n
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_source
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.observe import render
from cardlang.runtime.state import ChooserAbort, RuntimeState


def _has_instantiate(game: n.Game) -> bool:
    from cardlang.openspiel.encoding import _walk

    return any(isinstance(node, n.Instantiate) for node in _walk(game))


@lru_cache(maxsize=None)
def load(path_str: str) -> tuple[n.Game, ActionSpace]:
    """Parse + check a game and derive its action space (cached per path)."""
    game = check_source(Path(path_str))
    if _has_instantiate(game):
        raise ValueError(
            f"game '{game.name}' uses a Python `instantiate` mechanic: its hidden "
            f"state emits no observations, so information sets cannot be derived "
            f"(info-set debt — see docs/kernel-migration.md)"
        )
    return game, ActionSpace.for_game(game)


@dataclass
class Pause:
    """A suspended player decision."""

    player: int
    legal: list[int]  # global action ids, sorted ascending
    rs: RuntimeState  # the live world at the pause
    obs_logs: dict[int, list[tuple[Any, ...]]]  # per-player observation logs


@dataclass
class Terminal:
    """A completed game."""

    returns: list[float]


class ReplayChooser:
    """Returns recorded actions in order; aborts at the first un-recorded one.
    A chooser call requesting ``k`` picks decomposes into ``k`` sequential
    actions, so multi-card selections stay in the same global action space.

    Each consumed pick is emitted to the actor as a ``("chose", ...)`` event at
    the moment of the draw. The runtime's own aggregate `chose` (fired when the
    whole call returns) cannot cover a pause *inside* a multi-pick call — the
    picks already made would be invisible, collapsing distinct decision nodes
    into one information state (a perfect-recall violation). Per-draw emission
    keeps every replayed pick in the actor's log, and the log append-only
    across ``(seed, history)`` extensions; the runtime aggregate that follows a
    completed call is kept (it is the canonical event native playouts emit)."""

    def __init__(
        self,
        space: ActionSpace,
        history: tuple[int, ...],
        emit: Callable[[int, tuple[Any, ...]], None],
    ) -> None:
        self.space = space
        self.history = history
        self.emit = emit
        self.cursor = 0

    def __call__(self, player: int, candidates: list[Any], k: int) -> list[Any]:
        pool = list(candidates)
        picked: list[Any] = []
        for _ in range(k):
            if self.cursor >= len(self.history):
                legal = sorted({self.space.encode(c) for c in pool})
                raise ChooserAbort(player, legal)
            aid = self.history[self.cursor]
            self.cursor += 1
            choice = self.space.match(aid, pool)  # must be among the candidates
            pool.remove(choice)
            picked.append(choice)
            self.emit(player, ("chose", render(choice)))
        return picked


def returns_for(game: n.Game, result: GameResult) -> list[float]:
    """General-sum returns from the game's own result (SP1 spec, component 6):
    true scores, sign-adjusted so higher is better (negated for `lowest`
    winners); team-keyed scores map each player to their team's score. An
    elimination (`loser:`) game returns +1 per survivor and -(n-1) for the
    loser, which sums to zero."""
    n_players = game.players.low
    if game.winner is None:
        assert result.loser is not None
        return [
            float(-(n_players - 1)) if p == result.loser else 1.0
            for p in range(n_players)
        ]
    sign = -1.0 if game.winner.rank_dir == "lowest" else 1.0
    scores = result.scores
    if set(scores) == set(range(n_players)):
        return [sign * scores[p] for p in range(n_players)]
    # Team-keyed scores (Bridge, Spades). All six games have 4 players, so the
    # player-key and team-key sets can never coincide ambiguously here.
    team_of = {p: ti for ti, members in enumerate(game.partnerships) for p in members}
    return [sign * scores[team_of[p]] for p in range(n_players)]


def run(
    path_str: str,
    seed: int,
    history: tuple[int, ...],
    on_first_decision: Callable[[RuntimeState], None] | None = None,
) -> Pause | Terminal:
    """Replay ``history`` under ``seed``; return the next decision or the result."""
    game, space = load(path_str)
    logs: dict[int, list[tuple[Any, ...]]] = {
        p: [] for p in range(game.players.low)
    }

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    chooser = ReplayChooser(space, history, observe)
    try:
        result = play_game(
            game,
            random.Random(seed),
            chooser=chooser,
            observer=observe,
            on_first_decision=on_first_decision,
        )
    except ChooserAbort as abort:
        assert abort.rs is not None
        return Pause(abort.player, list(cast("list[int]", abort.legal)), abort.rs, logs)
    return Terminal(returns_for(game, result))
