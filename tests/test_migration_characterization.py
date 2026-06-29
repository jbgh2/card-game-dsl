"""Characterization nets for byte-identical kernel migrations.

Bridge and Schnapsen move their multi-way decision from a Boolean state gate to a
typed phase outcome. The migration only changes a mechanic's *return protocol*
(set-state-and-return-Player -> raise `_ProduceSignal`); it moves no chooser
calls, so for a fixed playout the per-seed results must stay **byte-identical**.

Pinochle lifts its ascending auction out of `run_pinochle_hand` onto the kernel
`round` (the participant-filter axis). The auction reproduces the monolith's
chooser draws exactly — same offered turns, same two-candidate `[bid, pass]`
vocabulary, same no-draw skips of passed/high bidders — so the per-seed results
must likewise stay byte-identical. This golden is pinned pre-migration.

French Tarot does the same for its four-level bid (a counterclockwise single-pass
ring of nullary level moves), reproducing the monolith's per-turn candidate lists
(`pass` then the levels above the standing bid) and ring order. Its golden is
pinned pre-migration too.

The Schnapsen golden was pinned pre-migration; a diff is a settlement bug (its
six-way settlement has no other independent-recompute net — see roadmap.md).

`rules.legal_cards` returns a `set`, so the chooser sees candidates in
hash-dependent order — the per-seed scores vary with `PYTHONHASHSEED`. We capture
in a `PYTHONHASHSEED=0` subprocess so the goldens are reproducible.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).parent.parent
GOLDEN = Path(__file__).parent / "golden"

_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

name = sys.argv[1]
game = check_dsl(Path(f"docs/games/{name}.cardlang").read_text(), f"{name}.cardlang")
out = {}
for seed in range(50):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(k): v for k, v in sorted(r.scores.items())},
        "winner": r.winner,
        "hands_played": r.hands_played,
    }
print(json.dumps(out))
"""


def _capture_pinned(name: str) -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE, name],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


@pytest.mark.parametrize("name", ["bridge", "schnapsen", "pinochle", "french-tarot"])
def test_migration_preserves_per_seed_results(name: str) -> None:
    expected = json.loads((GOLDEN / f"{name}_scores.json").read_text())
    assert _capture_pinned(name) == expected


# Stud's end-of-game scores are degenerate — the winner always holds all 400
# chips — so the generic capture above would pin only `winner` + `hands_played`,
# too coarse to catch a chooser-draw divergence that doesn't flip the eventual
# winner. Instead pin the full per-hand stack-vector sequence: any divergence in
# the betting/showdown draws surfaces at the hand it occurs. Pinned pre-migration.
_STUD_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(
    Path("docs/games/seven-card-stud.cardlang").read_text(), "seven-card-stud.cardlang"
)
out = {}
for seed in range(50):
    hands = []

    def tracer(event, data, _h=hands):
        if event == "stud_hand":
            _h.append([data["stacks"][p] for p in sorted(data["stacks"])])

    play_game(game, random.Random(seed), tracer)
    out[str(seed)] = hands
print(json.dumps(out))
"""


def _capture_stud_hands() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _STUD_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_stud_migration_preserves_per_hand_stacks() -> None:
    expected = json.loads((GOLDEN / "seven-card-stud_hands.json").read_text())
    assert _capture_stud_hands() == expected


# Tichu (climbing + the combination model) moves its whole hand — pushing, the
# climbing trick, the special cards, finishing, and scoring — from a Python
# monolith onto the kernel. The migration reproduces the monolith's RNG sequence
# (chooser draws plus two non-chooser draws — the Tichu-call gates and the Dragon
# routing — reproduced by stdlib primitives), so the per-seed results stay
# byte-identical. We pin `scores` + `winner` (not `hands_played`: the monolith has
# no `scoring` phase so the driver's hand counter reads 0, but the migration adds
# one — a structural change, not a draw divergence). Team scores accumulate every
# hand's card points, so any draw divergence cascades into the finals. Pinned
# pre-migration.
_TICHU_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/tichu.cardlang").read_text(), "tichu.cardlang")
out = {}
for seed in range(50):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(k): v for k, v in sorted(r.scores.items())},
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def _capture_tichu() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _TICHU_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_tichu_migration_preserves_per_seed_results() -> None:
    expected = json.loads((GOLDEN / "tichu_scores.json").read_text())
    assert _capture_tichu() == expected
