"""Observation emission across a real playout: per-player logs derived from
zone declarations alone, and no behavior change without an observer."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.observe import ChoseEvent, MovementEvent, ObservationEvent
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _play_with_logs(path: str, seed: int) -> dict[int, list[ObservationEvent]]:
    game = check_source(GAMES / path)
    logs: dict[int, list[ObservationEvent]] = {p: [] for p in range(game.players.count)}
    play_game(
        game,
        random.Random(seed),
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    return logs


def test_hearts_deal_is_private_per_recipient() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        deals = [
            e for e in logs[p] if isinstance(e, MovementEvent) and e.destination == f"hand[{p}]"
        ]
        assert deals, f"player {p} saw no deal into their own hand"
        first = deals[0]
        own = first.destination_view
        assert isinstance(own, tuple) and len(own) == 13  # own: identity
        other = [
            e
            for e in logs[p]
            if isinstance(e, MovementEvent) and e.destination == f"hand[{(p + 1) % 4}]"
        ]
        assert other and other[0].destination_view == 13  # someone else's deal: a count


def test_hearts_trick_plays_are_public() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        to_trick = [
            e for e in logs[p] if isinstance(e, MovementEvent) and e.destination == "trick_pile"
        ]
        assert to_trick
        # every observer sees each played card at identity (TrickPile: identity to all)
        assert all(
            isinstance(e.destination_view, tuple) and len(e.destination_view) == 1
            for e in to_trick
        )


def test_hearts_pass_hides_other_players_picks() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        # "chose" events are actor-only by construction; every one in p's log is p's own.
        chose = [e for e in logs[p] if isinstance(e, ChoseEvent)]
        assert chose  # p chose pass cards and trick plays
        # p sees others' hand->hand pass transfers only as counts
        pass_moves = [
            e
            for e in logs[p]
            if isinstance(e, MovementEvent)
            and e.source.startswith("hand[")
            and e.destination.startswith("hand[")
            and e.source != f"hand[{p}]"
            and e.destination != f"hand[{p}]"
        ]
        assert pass_moves and all(
            isinstance(e.source_view, int) and isinstance(e.destination_view, int)
            for e in pass_moves
        )


def test_no_observer_changes_nothing() -> None:
    game = check_source(GAMES / "hearts.cardlang")
    a = play_game(game, random.Random(7))
    b_logs: dict[int, list[Any]] = {p: [] for p in range(4)}
    b = play_game(game, random.Random(7), observer=lambda pl, ev: b_logs[pl].append(ev))
    assert a.scores == b.scores and a.winners == b.winners
