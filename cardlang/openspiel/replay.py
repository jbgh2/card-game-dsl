"""Re-simulation engine: drive Hearts action-by-action by replaying a recorded
action history through ``play_game``.

The OpenSpiel ``State`` is just ``(seed, history)``. Every query re-runs the game
with a :class:`ReplayChooser` that returns the recorded actions in order and
raises ``ChooserAbort`` at the first decision beyond the history — surfacing the
current decision point (with the live world attached). Because the chooser makes
no RNG calls, all shuffles are a pure function of ``seed``, so a run is fully
deterministic and reproduces a reference game exactly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from cardlang.openspiel.encoding import action_to_card, card_to_action
from cardlang.pipeline import check_source
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.state import ChooserAbort
from cardlang.runtime.values import Card

_HEARTS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "games" / "hearts.cardlang"


@lru_cache(maxsize=1)
def hearts_game() -> Any:
    """Parse + check Hearts once (cached)."""
    return check_source(_HEARTS_PATH)


@dataclass
class Pause:
    """A suspended player decision."""

    player: int
    legal: list[int]  # action ids, sorted ascending
    rs: Any  # the live RuntimeState at the pause
    observed_log: list[tuple[int, int, str]]  # (player, action_id, kind)


@dataclass
class Terminal:
    """A completed game."""

    returns: list[float]


class ReplayChooser:
    """Returns recorded actions in order; aborts at the first un-recorded one.

    Each chooser call requesting ``n`` picks decomposes into ``n`` sequential
    single-card actions, so the action space stays the 52 cards. ``kind`` tags a
    pick as ``"pass"`` (n>1 call, actor-private) or ``"play"`` (n=1, public).
    """

    def __init__(self, history: tuple[int, ...]) -> None:
        self.history = history
        self.cursor = 0
        self.observed_log: list[tuple[int, int, str]] = []

    def __call__(self, player: int, candidates: list[Any], n: int) -> list[Any]:
        pool: list[Card] = list(candidates)
        kind = "pass" if n > 1 else "play"
        picked: list[Card] = []
        for _ in range(n):
            if self.cursor >= len(self.history):
                legal = sorted(card_to_action(c) for c in pool)
                raise ChooserAbort(player, legal)
            aid = self.history[self.cursor]
            self.cursor += 1
            card = action_to_card(aid)
            pool.remove(card)  # recorded action must be among the candidates
            picked.append(card)
            self.observed_log.append((player, aid, kind))
        return picked


def _returns_from(result: GameResult) -> list[float]:
    """Hearts is low-score-wins; recentre scores to a zero-sum utility vector."""
    scores = result.scores
    players = sorted(scores)
    mean = sum(scores[p] for p in players) / len(players)
    return [mean - scores[p] for p in players]


def run(seed: int, history: tuple[int, ...]) -> Pause | Terminal:
    """Replay ``history`` under ``seed``; return the next decision or the result."""
    chooser = ReplayChooser(history)
    try:
        result = play_game(hearts_game(), random.Random(seed), chooser=chooser)
    except ChooserAbort as abort:
        assert abort.rs is not None
        legal = list(cast("list[int]", abort.legal))
        return Pause(abort.player, legal, abort.rs, chooser.observed_log)
    return Terminal(_returns_from(result))
