"""The generalized re-sim engine: replaying recorded actions reproduces a
reference game exactly, for every fully-kernel game; an exhausted history
surfaces the next decision as a Pause with per-player observation logs."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.replay import Pause, Terminal, load, returns_for, run
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
HEARTS = str(GAMES / "hearts.cardlang")
BIGTWO = str(GAMES / "big-two.cardlang")
KERNEL_GAMES = [
    "hearts.cardlang",
    "getaway.cardlang",
    "spades.cardlang",
    "bridge.cardlang",
    "oh-hell.cardlang",
    "big-two.cardlang",
    "seven-card-stud.cardlang",
    "pinochle.cardlang",
    "french-tarot.cardlang",
    "cribbage.cardlang",
]


def _record(path: str, seed: int, policy_seed: int) -> tuple[list[int], list[float]]:
    game, space = load(path)
    policy = random.Random(policy_seed)
    recorded: list[int] = []

    def recording(player: int, candidates: list[Any], n: int) -> list[Any]:
        chosen = policy.sample(list(candidates), n)
        recorded.extend(space.encode(c) for c in chosen)
        return chosen

    result = play_game(game, random.Random(seed), chooser=recording)
    return recorded, returns_for(game, result)


@pytest.mark.parametrize("name", KERNEL_GAMES)
def test_replay_reproduces_a_reference_game(name: str) -> None:
    path = str(GAMES / name)
    recorded, native = _record(path, seed=1, policy_seed=101)
    result = run(path, 1, tuple(recorded))
    assert isinstance(result, Terminal)
    assert result.returns == native


def test_empty_history_pauses_with_encoded_legal_and_logs() -> None:
    r = run(HEARTS, 0, ())
    assert isinstance(r, Pause)
    assert r.player in range(4)
    assert len(r.legal) == 13 and r.legal == sorted(r.legal)
    assert all(0 <= a < 52 for a in r.legal)
    assert set(r.obs_logs) == {0, 1, 2, 3}
    assert all(any(e[0] == "move" for e in log) for log in r.obs_logs.values())  # the deal


def test_bigtwo_first_decision_offers_combos() -> None:
    _, space = load(BIGTWO)
    r = run(BIGTWO, 0, ())
    assert isinstance(r, Pause)
    assert all(a >= space._name_base for a in r.legal)  # every legal action is a name ("pass") or combo — no bare cards
    # stepping one combo action advances
    nxt = run(BIGTWO, 0, (r.legal[0],))
    assert isinstance(nxt, (Pause, Terminal))


def test_on_first_decision_mutates_the_replayed_world() -> None:
    r0 = run(HEARTS, 0, ())
    assert isinstance(r0, Pause)
    baseline = len(r0.rs.zones.instance("hand", 0).cards)

    def strip_one(rs: Any) -> None:
        hand = rs.zones.instance("hand", 0)
        hand.remove(hand.cards[0])

    r1 = run(HEARTS, 0, (), on_first_decision=strip_one)
    assert isinstance(r1, Pause)
    assert len(r1.rs.zones.instance("hand", 0).cards) == baseline - 1


def test_returns_for_team_scored_game_maps_players_through_teams() -> None:
    game, _ = load(str(GAMES / "bridge.cardlang"))
    from cardlang.runtime.driver import GameResult

    result = GameResult(scores={0: 120, 1: 90}, winner=0, loser=None, hands_played=1)
    rets = returns_for(game, result)
    assert len(rets) == 4
    team_of = {p: ti for ti, members in enumerate(game.partnerships) for p in members}
    assert rets == [float(result.scores[team_of[p]]) for p in range(4)]


def test_returns_for_loser_game() -> None:
    game, _ = load(str(GAMES / "getaway.cardlang"))
    from cardlang.runtime.driver import GameResult

    result = GameResult(scores={}, winner=None, loser=2, hands_played=1)
    n = game.players.low
    rets = returns_for(game, result)
    assert rets[2] == float(-(n - 1))
    assert all(rets[p] == 1.0 for p in range(n) if p != 2)
    assert abs(sum(rets)) < 1e-9


def test_instantiate_games_are_rejected_as_infoset_debt() -> None:
    # (lru_cache does not cache exceptions, so no cache management is needed.)
    with pytest.raises(ValueError, match="info-set debt"):
        load(str(GAMES / "coup.cardlang"))
