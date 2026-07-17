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

The Schnapsen golden was pinned pre-migration, then re-pinned once under a
SANCTIONED normalization: the monolith offered marriage candidates in
hash-dependent set order (`{c.suit for c in lh}`), which the deterministic kernel
cannot reproduce, so the iteration was normalized to deck-suit order (the `Suit`
domain order the auction form enumerates) and the two hash-sensitive seeds (32,
41 — measured across PYTHONHASHSEED 0..23) regenerated. Any other diff is a
settlement bug (its six-way settlement has no other independent-recompute net —
see roadmap.md).

`rules.legal_cards` returns a `set`, so the chooser sees candidates in
hash-dependent order — the per-seed scores vary with `PYTHONHASHSEED`. We capture
in a `PYTHONHASHSEED=0` subprocess so the goldens are reproducible.

A second SANCTIONED regeneration covers every gather-using golden here
(schnapsen/french-tarot/skat scores; stud/tichu/cribbage/schnapsen/skat hand
vectors; tichu scores): the gather (`move all cards to <zone>`) was
canonicalized to collect zones in sorted-name order instead of declaration
order (decisions.md, the gather paragraph — declaration order was
observation-visible and shaped info sets, which the metamorphic suite's
declaration-reorder transform flagged). The gather stacks cards into the deck
in collection order, so the next same-seed shuffle permutes differently and
every subsequent deal moves — a wholesale per-seed shift, not a draw
divergence. The coup golden did not move (Coup has no gather), and neither did
bridge/pinochle/big-two (the zones actually non-empty at their gathers collect
in the same order under both rules). Any diff NOT explained by that
regeneration is a real divergence.
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


def assert_golden(captured: Any, expected: Any) -> None:
    """Compare a capture against its golden — including the TYPE of every scalar.

    A plain `captured == expected` on parsed JSON is blind to exactly the change
    these goldens exist to catch. In Python `False == 0` and `True == 1`, so a state
    variable converted from Integer to Boolean emits `false` where the golden holds
    `0`, and the assertion passes anyway. Coup's `alive[p]` made that concrete: the
    int -> bool conversion changed the observation payload of every seed and the
    golden did not notice.

    These files pin payloads. A payload whose type changed IS a changed payload, so
    the comparison checks types too — and a conversion like that now has to be
    signed off with a regenerated golden rather than sliding through green.
    """
    assert _typed_equal(captured, expected), "golden mismatch (values or types)"


def _typed_equal(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_typed_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


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


@pytest.mark.parametrize("name", ["bridge", "schnapsen", "pinochle", "french-tarot", "skat"])
def test_migration_preserves_per_seed_results(name: str) -> None:
    expected = json.loads((GOLDEN / f"{name}_scores.json").read_text())
    assert_golden(_capture_pinned(name), expected)


# Stud's end-of-game scores are degenerate — the winner always holds all 400
# chips — so the generic capture above would pin only `winner` + `hands_played`,
# too coarse to catch a chooser-draw divergence that doesn't flip the eventual
# winner. Instead pin the full per-hand stack-vector sequence: any divergence in
# the betting/showdown draws surfaces at the hand it occurs. Pinned pre-migration.
#
# Anchored on the driver's own `hand_end` trace (driver.py, emitted once per hand
# as `dict(rs.get(score_var))` — for Stud's `winner: highest stack`, that is
# `dict(stack)`) rather than the mechanic-local `stud_hand` trace the showdown
# used to emit: same values, same count, but a signal that survives the showdown
# leaving `instantiate` for the kernel (docs/kernel-migration.md).
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
        if event == "hand_end":
            _h.append([data[p] for p in sorted(data)])

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
    assert_golden(_capture_stud_hands(), expected)


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
# Re-pinned at the WS5 upgrade (real call windows + Dragon choice): captures run
# under the reference policy from tests/test_playout_tichu.py (grand 4%, small
# 2% per offer, uniform otherwise) — the uniform chooser diverges (the
# unbounded-lines witness), and the policy keeps the pinned profile close to
# the pre-WS5 rng gates.
_TICHU_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/tichu.cardlang").read_text(), "tichu.cardlang")

def policy(rng):
    from cardlang.runtime.chooser import random_chooser
    base = random_chooser(rng)
    def chooser(player, candidates, n):
        names = {c[0]: c for c in candidates if isinstance(c, tuple) and c}
        if "call_grand_tichu" in names:
            return [names["call_grand_tichu"] if rng.random() < 0.04 else names["decline_grand"]]
        if "call_tichu" in names:
            return [names["call_tichu"] if rng.random() < 0.02 else names["no_call"]]
        return base(player, candidates, n)
    return chooser

out = {}
for seed in range(50):
    rng = random.Random(seed)
    r = play_game(game, rng, None, policy(rng))
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


def test_tichu_ws5_pins_per_seed_results() -> None:
    expected = json.loads((GOLDEN / "tichu_scores.json").read_text())
    assert_golden(_capture_tichu(), expected)


# Tichu's finals accumulate ~100 card points a hand, so a late divergence could
# in principle be masked by an offsetting one; like Stud/Cribbage/Schnapsen/Skat
# we also pin the full per-hand vector — the sorted per-team score (the driver's
# own `hand_end` trace) plus the hand's double-victory flag and card-point total
# (the game's own `tichu_hand` trace, emitted by the monolith and by the kernel
# migration's `tichu_hand_summary` alike) — so a divergence surfaces at the hand
# it first perturbs. The monolith iterates no sets (measured: ZERO divergent
# seeds across PYTHONHASHSEED {0,1,2,3,7} x 50 seeds), so this golden pinned
# pre-migration with nothing sanctioned; any diff is a real draw divergence.
_TICHU_HANDS_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/tichu.cardlang").read_text(), "tichu.cardlang")

def policy(rng):
    from cardlang.runtime.chooser import random_chooser
    base = random_chooser(rng)
    def chooser(player, candidates, n):
        names = {c[0]: c for c in candidates if isinstance(c, tuple) and c}
        if "call_grand_tichu" in names:
            return [names["call_grand_tichu"] if rng.random() < 0.04 else names["decline_grand"]]
        if "call_tichu" in names:
            return [names["call_tichu"] if rng.random() < 0.02 else names["no_call"]]
        return base(player, candidates, n)
    return chooser

out = {}
for seed in range(50):
    hands = []
    pending = []

    def tracer(event, data, _h=hands, _p=pending):
        if event == "tichu_hand":
            _p.append([int(data["double_victory"]), data["card_points"]])
        elif event == "hand_end":
            summary = _p.pop() if _p else [None, None]
            _h.append([data[t] for t in sorted(data)] + summary)

    rng = random.Random(seed)
    play_game(game, rng, tracer, policy(rng))
    out[str(seed)] = hands
print(json.dumps(out))
"""


def _capture_tichu_hands() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _TICHU_HANDS_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_tichu_ws5_pins_per_hand_results() -> None:
    expected = json.loads((GOLDEN / "tichu_hands.json").read_text())
    assert_golden(_capture_tichu_hands(), expected)


# Big Two (the second climbing instance) moves its whole hand — the climbing
# trick, the combination model, the 3♦ opening, the shedding finish, and penalty
# scoring — onto the kernel `climb` construct alongside Tichu. The migration must
# reproduce the monolith's chooser-draw sequence, so the per-seed results stay
# byte-identical. We pin `scores` + `winner` (Big Two has no `scoring` phase, so
# the driver's hand counter reads 0, as for Tichu). Its engine is set-free, so the
# capture is hash-independent, but we still pin under `PYTHONHASHSEED=0` to match
# the harness. Pinned pre-migration.
_BIGTWO_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/big-two.cardlang").read_text(), "big-two.cardlang")
out = {}
for seed in range(50):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(k): v for k, v in sorted(r.scores.items())},
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def _capture_bigtwo() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _BIGTWO_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_bigtwo_migration_preserves_per_seed_results() -> None:
    expected = json.loads((GOLDEN / "bigtwo_scores.json").read_text())
    assert_golden(_capture_bigtwo(), expected)


# Cribbage moves the whole hand — crib discards, the starter cut and his heels,
# the pegging count (fifteens/pairs/runs/31/go), and the show (non-dealer hand,
# dealer hand, crib) — from `run_cribbage_hand` onto the kernel: filtered
# movements reproduce the two discard draws and the per-play pegging draw
# exactly, and ordinary statement control flow (`repeat until`, `if`/`else`,
# `skip to next hand`) reproduces the 121-cutoff gating. Cribbage's score
# trajectory (not just the eventual winner) can cross 121 at any component of
# any play, so — like Stud — we pin the full per-hand score vector rather than
# just `scores`/`winner`: a chooser-draw divergence surfaces at the hand it
# first perturbs. Anchored on the driver's own `hand_end` trace (driver.py,
# `dict(rs.get(score_var))` — for Cribbage's `winner: highest score`, that is
# `dict(score)`), a signal that survives the migration (no mechanic-local trace
# is read by any test — the old `cribbage_show` trace's only occurrence was its
# own emission). `hands_played` is NOT pinned: Cribbage has no phase named
# `scoring`, so the driver's hand counter reads 0 both before and after — the
# per-hand vector list length already carries that information. Cribbage's
# chooser candidate lists are hand-ordered lists (never sets), so this capture
# is hash-independent; `PYTHONHASHSEED=0` is kept for harness consistency, as
# for Big Two. Pinned pre-migration.
_CRIBBAGE_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/cribbage.cardlang").read_text(), "cribbage.cardlang")
out = {}
for seed in range(50):
    hands = []

    def tracer(event, data, _h=hands):
        if event == "hand_end":
            _h.append([data[p] for p in sorted(data)])

    play_game(game, random.Random(seed), tracer)
    out[str(seed)] = hands
print(json.dumps(out))
"""


def _capture_cribbage_hands() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _CRIBBAGE_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_cribbage_migration_preserves_per_hand_scores() -> None:
    expected = json.loads((GOLDEN / "cribbage_hands.json").read_text())
    assert_golden(_capture_cribbage_hands(), expected)


# Schnapsen moves the whole hand — the leader's mixed lead decision (play a
# card / declare a marriage / exchange the trump jack / close the talon), the
# follower's strict-endgame answer, the trick-draw loop, and claiming 66 — from
# `run_schnapsen_hand` onto the kernel (the auction form over a
# single-participant ring, plus filtered movements). A hand settles only 1–3
# game points either way, so the final match score can mask a mid-game draw
# divergence; like Stud and Cribbage we also pin the full per-hand `game_score`
# vector, so a divergence surfaces at the hand it first perturbs. Anchored on
# the driver's own `hand_end` trace (driver.py, `dict(rs.get(score_var))` — for
# Schnapsen's `winner: lowest game_score`, that is `dict(game_score)`), a signal
# that survives the hand leaving `instantiate` for the kernel. Pinned under the
# same normalization as the scores golden (see the module docstring).
_SCHNAPSEN_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/schnapsen.cardlang").read_text(), "schnapsen.cardlang")
out = {}
for seed in range(50):
    hands = []

    def tracer(event, data, _h=hands):
        if event == "hand_end":
            _h.append([data[p] for p in sorted(data)])

    play_game(game, random.Random(seed), tracer)
    out[str(seed)] = hands
print(json.dumps(out))
"""


def _capture_schnapsen_hands() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _SCHNAPSEN_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_schnapsen_migration_preserves_per_hand_scores() -> None:
    expected = json.loads((GOLDEN / "schnapsen_hands.json").read_text())
    assert_golden(_capture_schnapsen_hands(), expected)


# Skat moves the whole hand — the Reizen call-and-response (a role-guarded
# two-participant ring on the auction form), the contract declaration, the ten
# strict-follow tricks, and the base x multiplier scoring — from
# `run_skat_hand` onto the kernel. Unlike Schnapsen, the monolith iterates no
# sets (measured: ZERO divergent seeds across PYTHONHASHSEED {0,1,2,3,7} x 50
# seeds), so these goldens pinned pre-migration with nothing sanctioned, and
# any diff is a real draw divergence. A hand settles only the declarer's
# ±game_value, so the final 36-hand score can mask a mid-game divergence; like
# Stud/Cribbage/Schnapsen we also pin the full per-hand `score` vector,
# anchored on the driver's own `hand_end` trace (for Skat's `winner: highest
# score`, that is `dict(score)`).
_SKAT_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/skat.cardlang").read_text(), "skat.cardlang")
out = {}
for seed in range(50):
    hands = []

    def tracer(event, data, _h=hands):
        if event == "hand_end":
            _h.append([data[p] for p in sorted(data)])

    play_game(game, random.Random(seed), tracer)
    out[str(seed)] = hands
print(json.dumps(out))
"""


def _capture_skat_hands() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _SKAT_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_skat_migration_preserves_per_hand_scores() -> None:
    expected = json.loads((GOLDEN / "skat_hands.json").read_text())
    assert_golden(_capture_skat_hands(), expected)


# Coup at real interactive scope (WS5): every challenge, block, claimed
# character, and action target is a chooser decision, so random play decides
# them uniformly at the offers. This golden pins the strongest per-seed
# discriminator the game emits: the full reveal sequence (every influence
# flip, in order, with its character — where every elimination happens) plus
# final coins, the alive vector, and the winner, over 40 seeds under
# PYTHONHASHSEED=0 (the WS5 behaviour-change re-pin — see kernel-migration.md,
# Workstream 5). Regenerate by running _COUP_CAPTURE exactly as _capture_coup
# does.
_COUP_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(Path("docs/games/coup.cardlang").read_text(), "coup.cardlang")
out = {}
for seed in range(40):
    reveals = []
    summary = {}

    def tracer(event, data, _r=reveals, _s=summary):
        if event == "coup_reveal":
            _r.append([data[0], data[1]])
        elif event == "coup_game":
            _s.update(
                coins={str(k): v for k, v in sorted(data["coins"].items())},
                alive={str(k): v for k, v in sorted(data["alive"].items())},
            )

    r = play_game(game, random.Random(seed), tracer)
    out[str(seed)] = {
        "reveals": reveals,
        "coins": summary["coins"],
        "alive": summary["alive"],
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def _capture_coup() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _COUP_CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_coup_migration_preserves_per_seed_results() -> None:
    expected = json.loads((GOLDEN / "coup_scores.json").read_text())
    assert_golden(_capture_coup(), expected)
