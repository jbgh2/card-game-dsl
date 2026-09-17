"""Random-playout harness for Hearts.

The runtime net's acceptance test: play Hearts to completion with random legal
moves and assert the invariants implementation.md names — it terminates, the
legal-move set is never empty before terminal (else the chooser would raise),
scores reconcile, and a winner emerges.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def _hearts() -> n.Game:
    return check_source(HEARTS)


def test_200_random_games_satisfy_invariants() -> None:
    game = _hearts()
    for seed in range(200):
        hand_totals: list[int] = []

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                hand_totals.append(sum(data.values()))  # noqa: B023 -- consumed before the loop advances

        result = play_game(game, random.Random(seed), tracer)

        # Terminates (returned), and someone crossed the 100-point threshold.
        assert max(result.scores.values()) >= 100
        # Winner is the lowest cumulative score.
        assert result.winner is not None
        assert result.winner == min(result.scores, key=lambda p: result.scores[p])
        assert result.loser is None
        # Each hand contributes 26 points (13 hearts + Q♠). A shoot-the-moon
        # contributes what its shooter chose: 78 with the other three charged
        # 26 each, or -26 with the shooter credited.
        deltas = [b - a for a, b in zip([0, *hand_totals], hand_totals)]
        assert all(d in (26, 78, -26) for d in deltas), f"seed {seed}: hand deltas {deltas}"
        assert len(hand_totals) == result.hands_played


def test_a_moon_scores_the_way_its_shooter_chose() -> None:
    """Shooting the moon is a decision, and both arms are played: the other
    three charged 26 each, or 26 credited to the shooter (Pagat, Scoring).

    The 120-step conformance walk in `tests/openspiel_ready/test_hearts.py`
    ends inside the first hand, so this is where the two arms are exercised;
    that module records them as unreached with this test as their reason.
    """
    arms: dict[str, int] = {}
    moons = 0
    game = _hearts()
    for seed in range(200):
        # Each list carries the trick count at the moment of the event, which
        # is what assigns a scoring decision to the hand that earned it.
        tricks: list[tuple[int, Any]] = []
        chosen: list[tuple[int, int, str]] = []
        hand_ends: list[tuple[int, dict[int, int]]] = []
        arm_names = {"charge_the_others", "credit_the_shooter"}

        def tracer(event: str, data: Any) -> None:
            if event == "trick":
                tricks.append(data)  # noqa: B023 -- consumed before the loop advances
            elif event == "hand_end":
                hand_ends.append((len(tricks), dict(data)))  # noqa: B023

        def observer(seat: int, event: tuple[Any, ...]) -> None:
            # The announcement every seat sees, read once: a scoring choice is
            # public, which is the channel `cardlang demo` prints from.
            if seat == 0 and event[0] == "announce" and event[2] in arm_names:  # noqa: B023
                chosen.append((len(tricks), event[1], event[2]))  # noqa: B023

        play_game(game, random.Random(seed), tracer, observer=observer)

        # Replay each hand: penalty points per player from the tricks they won,
        # against the score the hand actually moved.
        start, before = 0, {p: 0 for p in range(4)}
        for end, after in hand_ends:
            points = {p: 0 for p in range(4)}
            for winner, cards in tricks[start:end]:
                points[winner] += sum(
                    1 if c.suit == "hearts" else 13 if (c.rank, c.suit) == ("Q", "spades") else 0
                    for c in cards
                )
            delta = {p: after[p] - before[p] for p in range(4)}
            decisions = [(who, arm) for at, who, arm in chosen if at == end]
            shooters = [p for p in range(4) if points[p] == 26]
            if shooters:
                moons += 1
                assert len(decisions) == 1, f"seed {seed}: {decisions} for one moon"
                shooter, arm = decisions[0]
                assert shooter == shooters[0], f"seed {seed}: {shooter} chose, {shooters[0]} shot"
                arms[arm] = arms.get(arm, 0) + 1
                expected = (
                    {p: (0 if p == shooter else 26) for p in range(4)}
                    if arm == "charge_the_others"
                    else {p: (-26 if p == shooter else 0) for p in range(4)}
                )
                assert delta == expected, f"seed {seed}: {arm} scored {delta}"
            else:
                assert not decisions, f"seed {seed}: {decisions} offered without a moon"
                assert delta == points, f"seed {seed}: hand scored {delta}, tricks say {points}"
            start, before = end, after

    assert moons > 0
    assert set(arms) == {"charge_the_others", "credit_the_shooter"}, arms


def test_one_game_trace_is_coherent() -> None:
    game = _hearts()
    plays: list[tuple[int, Any]] = []
    tricks: list[tuple[int, list[Any]]] = []

    def tracer(event: str, data: Any) -> None:
        if event == "play":
            plays.append(data)
        elif event == "trick":
            tricks.append(data)

    result = play_game(game, random.Random(7), tracer)

    # Thirteen tricks per hand, four plays per trick.
    assert len(tricks) == 13 * result.hands_played
    assert len(plays) == 4 * len(tricks)

    for i, (winner, cards) in enumerate(tricks):
        group = plays[i * 4 : (i + 1) * 4]
        players_in_trick = {p for p, _ in group}
        assert len(players_in_trick) == 4  # all four play once
        assert winner in players_in_trick  # the winner is one of them
        assert len(cards) == 4
