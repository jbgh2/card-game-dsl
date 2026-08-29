"""Random-playout harness for GOPS.

GOPS's whole hand is recomputable from the public observation stream alone:
the prize order arrives as `prize_deck -> prize` movements (identity at the
public destination), the sealed bids arrive as `reveal` events, and the
scoring is a closed formula over rank values (A=1 .. K=13, higher bid takes
the prize, equal bids discard it — the native-OpenSpiel/Pagat-variant tie
rule the game file declares). Every seed is replayed and EVERYTHING is
recomputed independently from player 0's observation log — an implementation
of the rules written against the observation channel, not the runtime — and
the driver's final scores, winner, and routing movements must match exactly.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GOPS = Path(__file__).parent.parent / "docs" / "games" / "gops.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "gops_scores.json"
REPO = Path(__file__).parent.parent

ROUNDS = 13
VALUE = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
         "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}
SUIT_SYM = {"clubs": "♣", "diamonds": "♦", "hearts": "♥", "spades": "♠"}


def _rank(card_str: str) -> str:
    """The rank of a rendered card ('10♦' -> '10')."""
    return card_str[:-1]


def _suit_sym(card_str: str) -> str:
    return card_str[-1]


def _run_and_verify(game: Any, seed: int) -> int:
    """Play one seeded game, recompute the whole hand from player 0's
    observation log, and verify every recomputable fact. Returns the number
    of tied rounds (for coverage assertions across seeds)."""
    log: list[tuple[Any, ...]] = []

    def observer(player: int, event: tuple[Any, ...]) -> None:
        if player == 0:
            log.append(event)

    result = play_game(game, random.Random(seed), observer=observer)

    # Slice the log into rounds: each round opens with the prize exposure.
    prizes: list[str] = []
    bids: list[tuple[str, str]] = []
    routings: list[tuple[Any, ...]] = []
    pending: dict[str, str] = {}
    for event in log:
        if event[0] == "move" and event[1] == "prize_deck" and event[3] == "prize":
            assert len(event[4]) == 1, f"seed {seed}: multi-card prize exposure"
            prizes.append(event[4][0])
        elif event[0] == "reveal":
            pending[event[1]] = event[2]
            if len(pending) == 2:
                bids.append((pending.pop("bid[0]"), pending.pop("bid[1]")))
        elif event[0] == "move" and event[1] == "prize":
            routings.append(event)

    assert len(prizes) == ROUNDS, f"seed {seed}: {len(prizes)} rounds"
    assert len(bids) == ROUNDS, f"seed {seed}: {len(bids)} bid pairs"
    assert len(routings) == ROUNDS, f"seed {seed}: {len(routings)} prize routings"

    # The prize order is the whole diamond suit, once each (91 points).
    assert all(_suit_sym(p) == SUIT_SYM["diamonds"] for p in prizes), f"seed {seed}"
    assert sorted(_rank(p) for p in prizes) == sorted(VALUE), f"seed {seed}"

    # Each player bid each of their 13 cards exactly once, in their own suit.
    for i, suit in ((0, "clubs"), (1, "spades")):
        cards = [b[i] for b in bids]
        assert all(_suit_sym(c) == SUIT_SYM[suit] for c in cards), f"seed {seed}"
        assert sorted(_rank(c) for c in cards) == sorted(VALUE), f"seed {seed}"

    # Recompute the scores round by round and check the routing movements.
    points = {0: 0, 1: 0}
    discarded = 0
    ties = 0
    for rnd, (prize, (b0, b1), routing) in enumerate(zip(prizes, bids, routings)):
        v0, v1 = VALUE[_rank(b0)], VALUE[_rank(b1)]
        assert routing[2] == (prize,), f"seed {seed} round {rnd}: routed {routing[2]}"
        if v0 == v1:
            ties += 1
            discarded += VALUE[_rank(prize)]
            dest = "discard"
        else:
            winner = 0 if v0 > v1 else 1
            points[winner] += VALUE[_rank(prize)]
            dest = f"captured[{winner}]"
        assert routing[3] == dest, (
            f"seed {seed} round {rnd}: prize routed to {routing[3]}, expected {dest}"
        )

    # Conservation: won points plus tied-away prizes account for the suit.
    assert points[0] + points[1] + discarded == 91, f"seed {seed}"
    assert result.scores == points, f"seed {seed}: {result.scores} != {points}"
    top = max(result.scores.values())
    assert result.winner in [p for p, s in result.scores.items() if s == top], (
        f"seed {seed}"
    )
    return ties


def test_40_random_games_recompute_exactly() -> None:
    game = check_source(GOPS)
    total_ties = 0
    decided = 0
    for seed in range(40):
        ties = _run_and_verify(game, seed)
        total_ties += ties
        decided += ROUNDS - ties
    # Both resolution branches are really exercised across the run.
    assert total_ties > 0, "no tied round in 40 seeds — the discard branch is dead"
    assert decided > 0


# Exact-score golden, captured in a subprocess for interpreter isolation. The
# scores do not depend on PYTHONHASHSEED (test_migration_characterization.py's
# `test_a_playout_is_hash_seed_independent`), so the capture reproduces under
# whatever hash seed the run draws.
_CAPTURE = """
import json, random
from pathlib import Path
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

game = check_source(Path("docs/games/gops.cardlang"))
out = {}
for seed in range(40):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(p): s for p, s in sorted(r.scores.items())},
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def test_per_seed_scores_match_golden() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    captured = json.loads(proc.stdout)
    expected = json.loads(GOLDEN.read_text())
    assert captured == expected
