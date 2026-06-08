"""The re-sim engine: replaying recorded actions reproduces a reference game
exactly, and an exhausted history surfaces the next decision as a Pause.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.openspiel.encoding import card_to_action
from cardlang.openspiel.replay import (
    Pause,
    Terminal,
    _returns_from,
    hearts_game,
    run,
)
from cardlang.runtime.driver import play_game


def _record(seed: int, policy_seed: int) -> tuple[list[int], list[float]]:
    """Play Hearts with shuffles driven by `seed` and decisions by a *separate*
    policy RNG (so the shuffle stream is a pure function of `seed`), recording the
    chosen action ids and the resulting returns."""
    policy = random.Random(policy_seed)
    recorded: list[int] = []

    def recording(player: int, candidates: list[Any], n: int) -> list[Any]:
        chosen = policy.sample(list(candidates), n)
        recorded.extend(card_to_action(c) for c in chosen)
        return chosen

    result = play_game(hearts_game(), random.Random(seed), chooser=recording)
    return recorded, _returns_from(result)


def test_replay_reproduces_reference_game() -> None:
    for seed in range(5):
        recorded, native_returns = _record(seed, policy_seed=100 + seed)
        result = run(seed, tuple(recorded))
        assert isinstance(result, Terminal)
        assert result.returns == native_returns


def test_empty_history_pauses_at_first_decision() -> None:
    result = run(0, ())
    assert isinstance(result, Pause)
    assert result.player in range(4)
    assert len(result.legal) == 13  # first decision is a pass over a full hand
    assert all(0 <= a < 52 for a in result.legal)
    assert result.legal == sorted(result.legal)


def test_stepping_one_action_advances() -> None:
    first = run(0, ())
    assert isinstance(first, Pause)
    a = first.legal[0]
    nxt = run(0, (a,))
    assert isinstance(nxt, (Pause, Terminal))
