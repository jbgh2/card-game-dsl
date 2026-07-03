"""Observation emission across a real playout: per-player logs derived from
zone declarations alone, and no behavior change without an observer."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _play_with_logs(path: str, seed: int) -> dict[int, list[tuple[Any, ...]]]:
    game = check_source(GAMES / path)
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(game.players.low)}
    play_game(
        game,
        random.Random(seed),
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    return logs


def test_hearts_deal_is_private_per_recipient() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        deals = [e for e in logs[p] if e[0] == "move" and e[3] == f"hand[{p}]"]
        assert deals, f"player {p} saw no deal into their own hand"
        first = deals[0]
        assert isinstance(first[4], tuple) and len(first[4]) == 13  # own: identity
        other = [
            e for e in logs[p] if e[0] == "move" and e[3] == f"hand[{(p + 1) % 4}]"
        ]
        assert other and other[0][4] == 13  # someone else's deal: a count


def test_hearts_trick_plays_are_public() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        to_trick = [e for e in logs[p] if e[0] == "move" and e[3] == "trick_pile"]
        assert to_trick
        # every observer sees each played card at identity (TrickPile: identity to all)
        assert all(isinstance(e[4], tuple) and len(e[4]) == 1 for e in to_trick)


def test_hearts_pass_hides_other_players_picks() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        # "chose" events are actor-only by construction; every one in p's log is p's own.
        chose = [e for e in logs[p] if e[0] == "chose"]
        assert chose  # p chose pass cards and trick plays
        # p sees others' hand->hand pass transfers only as counts
        pass_moves = [
            e
            for e in logs[p]
            if e[0] == "move"
            and e[1].startswith("hand[")
            and e[3].startswith("hand[")
            and e[1] != f"hand[{p}]"
            and e[3] != f"hand[{p}]"
        ]
        assert pass_moves and all(
            isinstance(e[2], int) and isinstance(e[4], int) for e in pass_moves
        )


def test_no_observer_changes_nothing() -> None:
    game = check_source(GAMES / "hearts.cardlang")
    a = play_game(game, random.Random(7))
    b_logs: dict[int, list[Any]] = {p: [] for p in range(4)}
    b = play_game(game, random.Random(7), observer=lambda pl, ev: b_logs[pl].append(ev))
    assert a.scores == b.scores and a.winner == b.winner
