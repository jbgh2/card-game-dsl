"""Gin Rummy: random-playout invariants plus a characterization pin.

A counting game with hidden hands: the strongest falsifiable checks are the
match-level invariants (exactly one champion — the reacher of 100, robust
even when the loser's boxes push their settled total past 100, which seed 1
actually produces), card conservation, and the settle arithmetic's floor.
The per-hand combination machinery (deadwood, melds, the codec) has its own
known-value net in tests/test_gin_primitives.py.

The arrange-guard totality claim — a knocked hand always reaches a legal
shown arrangement, random play included — is exercised implicitly by every
completing seed: an unreachable arrangement would raise the joint
selection's loud no-satisfying-subset error mid-playout.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GIN = Path(__file__).parent.parent / "docs" / "games" / "gin-rummy.cardlang"


def _run(seed: int) -> tuple[int | None, dict[int, int], dict[int, int], dict[str, int]]:
    game = check_source(GIN)
    rs_box: list[Any] = []
    final: dict[str, Any] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            # Game-level frames pop when the game exits — capture while live.
            final["match_score"] = dict(rs_box[0].get("match_score"))
            final["hands_won"] = dict(rs_box[0].get("hands_won"))
            final["census"] = data

    result = play_game(
        game,
        random.Random(seed),
        tracer=tracer,
        on_first_decision=lambda rs: rs_box.append(rs),
    )
    return result.winner, final["match_score"], final["hands_won"], final["census"]


def test_30_random_matches_satisfy_invariants() -> None:
    for seed in range(30):
        winner, match_score, hands_won, census = _run(seed)
        assert census["total"] == 52, f"seed {seed}: {census}"
        # Exactly one champion, and the settle gives them at least the game
        # bonus on top of the 100 they reached.
        assert winner is not None
        assert match_score[winner] >= 200, f"seed {seed}: {match_score}"
        assert hands_won[winner] >= 1, f"seed {seed}: {hands_won}"
        # Every point on the table came from a won hand.
        for p, s in match_score.items():
            if s > 0:
                assert hands_won[p] >= 1, f"seed {seed}: {match_score} {hands_won}"


def test_seed0_characterization() -> None:
    # Byte-identity pin for the whole match: any change to the constructs'
    # decision sequence (turns rotation, joint enumeration order, offer
    # order) moves this vector. PYTHONHASHSEED=0 per the suite convention.
    winner, match_score, hands_won, _ = _run(0)
    assert winner == 1
    assert match_score == {0: 76, 1: 254}
    assert hands_won == {0: 1, 1: 2}
