"""Generalized re-simulation engine: drive ANY fully-kernel game
action-by-action by replaying a recorded action history through ``play_game``.

The OpenSpiel ``State`` is just ``(seed, history)``. Every query re-runs the
game with a :class:`ReplayChooser` that decodes and returns the recorded
actions in order and raises ``ChooserAbort`` at the first decision beyond the
history — surfacing the current decision point with the live world and the
per-player observation logs attached. The chooser makes no RNG calls, so a run
is a pure function of ``seed``."""

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


@lru_cache(maxsize=None)
def load(path_str: str) -> tuple[n.Game, ActionSpace]:
    """Parse + check a game and derive its action space (cached per path)."""
    game = check_source(Path(path_str))
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


# The grammar's RANK_DIR terminal (`cardlang.lark`, "lowest" | "highest"),
# mapped to the sign that makes a higher return the better outcome.
# Exhaustive by construction: `returns_for` below raises loudly on any key
# not present here, and `test_rank_dir_set_is_pinned`
# (tests/test_comprehension_aggregators.py) reconciles this set against the
# grammar terminal so a new RANK_DIR token cannot land uncovered here.
RANK_DIR_TO_SIGN: dict[str, float] = {"highest": 1.0, "lowest": -1.0}


def _winner_target_is_team_keyed(game: n.Game) -> bool:
    """Whether the `winner:` target's score variable is keyed by TEAM.

    Read from the variable's own DECLARATION (`StateDecl.index`), never inferred
    from the shape of the score dict. The shape cannot tell: a game whose team
    count equals its player count has team keys (`{0, 1}` for two teams) that are
    indistinguishable from player keys, so a key-set test read team scores as
    player scores and paid the wrong seats — silently, since nothing about
    `partnerships: [[1], [0]]` on two seats is malformed. `driver` builds the
    score dict from exactly this variable (`rs.get(game.winner.target)`), so its
    declared index IS the keying.

    A target that names no declaration, or one indexed by anything other than
    `team` (a player index, or no index at all), is not team-keyed: the identity
    mapping applies, which is what a player-indexed or scalar score wants."""
    assert game.winner is not None  # callers check; keeps mypy and intent aligned
    target = game.winner.target
    for block in n.state_blocks(game):
        for decl in block.decls:
            if decl.name == target:
                return decl.index == "team"
    return False


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
    if game.winner.rank_dir not in RANK_DIR_TO_SIGN:
        # Internal invariant, not a user diagnostic: the grammar's RANK_DIR
        # terminal and this mapping are out of sync.
        raise AssertionError(
            f"returns_for: unhandled RANK_DIR value {game.winner.rank_dir!r} — add "
            "it to RANK_DIR_TO_SIGN"
        )
    sign = RANK_DIR_TO_SIGN[game.winner.rank_dir]
    scores = result.scores
    if not _winner_target_is_team_keyed(game):
        return [sign * scores[p] for p in range(n_players)]
    # Team-keyed scores (Bridge, Spades): one score per TEAM, handed to every
    # member of that team.
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
