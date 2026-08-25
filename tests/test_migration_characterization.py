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
see issue #83).

`rules.legal_cards` returns a `set`, so the chooser sees candidates in
hash-dependent order — the per-seed scores vary with `PYTHONHASHSEED`. We capture
in a `PYTHONHASHSEED=0` subprocess so the goldens are reproducible.

A SIXTH sanctioned regeneration covers `seven-card-stud_hands.json` on every
seed it holds: `poker_betting`'s `raise` climbs to the next RUNG of the street's
ladder instead of adding a bet size to wherever the bet stands (issue #431).
Those are the same thing on every street that opens with no bet or with one the
size of the street, which is every street of every other consumer — so this is
the rare library change with a measured whole-tree negative: capturing per-seed
scores and per-hand stack vectors before and after moves 0 of 12 seeds for Kuhn,
Leduc, Hold'em and heads-up Hold'em, and 12 of 12 for Stud. Stud is the one
consumer that opens a street with a forced post SHORTER than the street's size —
the bring-in of 2 against a 5 — so completing it now makes the bet 5 rather than
7, and 3rd street runs Pagat's 2/5/10. That reprices every 3rd street, which
moves the chips, which moves the deal of every later hand.
`seven-card-stud.ir.json` moves with it through its own `UPDATE_GOLDEN=1` path:
two hunks inside `raise`'s effect, the `owed` binding becoming a `target` one.
The ladder itself is pinned away from these vectors, in
tests/test_poker_betting_sizing.py, which drives each move from a hand-built
standing bet — because a characterization vector shows that something repriced,
never that it repriced correctly.

A FIFTH sanctioned regeneration covers `seven-card-stud_hands.json` on every
seed it holds: `poker_betting`'s `raise` now admits a seat that owes nothing but
has not taken a turn on the street, which is Stud's bring-in poster (issue
#237). Called around, that seat is offered `raise` beside `check` where it had
`check` alone, so 3rd street gains a decision node in nearly every hand — which
moves the chooser draws, and so the deal of every later street and every later
hand. `seven-card-stud.ir.json` moves with it through its own `UPDATE_GOLDEN=1`
path, and there the diff is one hunk inside `raise`'s guard, the old `>`
comparison becoming the `and` that heads the new disjunction. The negative
control for this change is the family members with NO forced post — Kuhn and
Leduc, whose antes set no standing bet — and it is measured in
tests/test_poker_betting_offers.py, which drives every consumer and asserts the
count is zero for exactly those two. Both Hold'em variants move and are pinned
by their playout modules, not here. What this vector attests for Stud is
unchanged by the addition: a characterization of the current game, per the
third and fourth regenerations below.

A FOURTH sanctioned regeneration covers `seven-card-stud_hands.json` again, this
time on every seed it holds: retiring the `order priority` value put Stud's
betting on the default ring, so after a bet or raise the seats behind the
aggressor decide before the seats it re-opened (issue #198). The same seats
commit the same chips — chip conservation and the side-pot known-value tests do
not move — but the ORDER of the asking does, which reorders the whole hand and
so every later deal. `seven-card-stud.ir.json` moves with it through its own
`UPDATE_GOLDEN=1` path, and there the diff is five `order_mode` values going
null: the clause is gone from the game, and null is what an absent clause emits.
The family's 2-seat members are the change's negative control, and this module
holds no golden for any of them, so the control is measured where their decision
order is pinned — the readiness proofs and playouts under `tests/openspiel_ready/`
and `tests/test_playout_holdem_heads_up.py` — never here. Why they do not move:
at a two-seat street's first decision both seats are pending, and the pointer is
at the leader, so a re-scan from the leader picks the seat the pointer already
names; after either seat acts it stops being pending, so only one ever is. The
two traversals agree at every decision, not because the pending set is a
singleton throughout.
That vector loses nothing it had, for the reason below: the pre-kernel monolith
asked in the same wrong order, so this is the same trade the third regeneration
made, and the migration claim now rests on the family's other pins rather than
on these seeds.

A THIRD sanctioned regeneration covers `seven-card-stud_hands.json` (25 of its 50
seeds moved): `poker_betting`'s `raise` gained the clause requiring an opponent
who can still act, so a player facing none is now offered only call and fold
(issue #197). The same clause moves `seven-card-stud.ir.json`, which is this
module's sibling pin in tests/test_seven_card_stud_ir.py and regenerates through
its own `UPDATE_GOLDEN=1` path; that diff is the guard expression gaining its
`and`, and is meant to be read rather than trusted. Stud's pre-kernel implementation shared the defect, so
correcting it necessarily diverges from it — and that is the cost this
regeneration pays: for the seeds that moved, this vector no longer attests
"the kernel migration reproduced the monolith" but "the migrated game plus one
deliberate rule correction". The fourth regeneration above extends that cost to
every seed, so what this vector pins for Stud today is a characterization of the
current game, not a migration claim; a future divergence in it is still a real
one, which is what keeps the pin worth having. The rule was corrected rather than kept because the extra
decision node is an ACTION-SPACE defect, invisible to every chip-conservation
check the family relies on (the side-pot layering returns an uncalled excess to
its sole contributor), and the OpenSpiel target is what this corpus exists for.

Regenerate at the golden's OWN width, never at `seeds_for(...)`: the sweep count
is a sampling dial below the pinned count, so capturing at the dial and writing
the result silently discards the rest — and `assert_golden_seeds` compares a
slice, so the suite stays green while the coverage shrinks.

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

# Each capture sweeps this many seeds. A game may choose its own — the sweeps
# differ in what a single seed is worth (Stud plays ~170 hands per match,
# Schnapsen ~5), and a game whose divergences concentrate in a rare branch can
# buy detection here rather than argue for it.
#
# WHY 10 IS THE DEFAULT. A seed catches a divergence iff that divergence fires
# at least once in that seed's match — the goldens pin cumulative results, so
# there is no partial credit. Detection over N seeds is 1-(1-q)^N for q = the
# chance of firing at least once in one match. N=10 gives 95% detection for
# q >= 0.259; N=50 gives it for q >= 0.058. So the seeds beyond ten buy exactly
# the band q in [0.06, 0.26] — for French Tarot's 36-hand match, a divergence
# confined to between 0.17% and 0.83% of hands (1 hand in 600 to 1 in 120).
# Above that band ten seeds suffice; below it fifty do not reach 95% either.
# Every divergence this file has actually caught sat at q = 1.0: the
# gather-order canonicalization moved every gather-using golden, and Coup's
# `alive[p]` int -> bool changed the payload of every seed.
#
# RAISING A COUNT NEEDS NO REGENERATION. The goldens on disk keep every seed
# they were pinned with; a capture compares against the slice it swept. Raise a
# number here and the extra seeds are already recorded and waiting. Lowering is
# equally free. The pin at the foot of this module rejects a count larger than
# the golden holds, and a key naming a game this module does not capture.
DEFAULT_SEEDS = 10
SEEDS_BY_GAME: dict[str, int] = {}

# The games captured here, and the goldens each one's captures compare against
# — the domain the table above is keyed over.
CAPTURE_GOLDENS: dict[str, tuple[str, ...]] = {
    "bridge": ("bridge_scores.json",),
    "schnapsen": ("schnapsen_scores.json", "schnapsen_hands.json"),
    "pinochle": ("pinochle_scores.json",),
    "french-tarot": ("french-tarot_scores.json",),
    "skat": ("skat_scores.json", "skat_hands.json"),
    "seven-card-stud": ("seven-card-stud_hands.json",),
    "tichu": ("tichu_scores.json", "tichu_hands.json"),
    "bigtwo": ("bigtwo_scores.json",),
    "cribbage": ("cribbage_hands.json",),
    "coup": ("coup_scores.json",),
}


def seeds_for(game: str) -> int:
    return SEEDS_BY_GAME.get(game, DEFAULT_SEEDS)


def assert_golden_seeds(game: str, captured: Any, expected: Any) -> None:
    """Compare a capture against the corresponding SLICE of its golden.

    The count is a sampling dial (see `DEFAULT_SEEDS`), so the golden holds more
    seeds than a run sweeps. Two things have to be checked before the slice is
    honest: that the capture actually produced the seeds it was asked for — a
    capture that swept none would otherwise compare an empty dict against an
    empty slice and pass — and that every seed it produced is one the golden
    records, so a count raised past the golden fails loudly instead of
    comparing fewer."""
    want = seeds_for(game)
    assert len(captured) == want, (
        f"{game}: captured {len(captured)} seeds, asked for {want}"
    )
    unpinned = sorted(set(captured) - set(expected), key=int)
    assert not unpinned, (
        f"{game}: seeds {unpinned} are not in the golden — it was pinned with "
        f"{len(expected)}, so a count above that has nothing to compare against"
    )
    assert_golden(captured, {s: expected[s] for s in captured})


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
for seed in range(int(sys.argv[2])):
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
        [sys.executable, "-c", _CAPTURE, name, str(seeds_for(name))],
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
    assert_golden_seeds(name, _capture_pinned(name), expected)


# Stud's end-of-game scores are degenerate — the winner always holds all 400
# chips — so the generic capture above would pin only `winner` + `hands_played`,
# too coarse to catch a chooser-draw divergence that doesn't flip the eventual
# winner. Instead pin the full per-hand stack-vector sequence: any divergence in
# the betting/showdown draws surfaces at the hand it occurs. Pinned pre-migration.
#
# Anchored on the driver's own `hand_end` trace (driver.py, emitted once per hand
# as `dict(rs.get(score_var))` — for Stud's `winner: highest stack`, that is
# `dict(stack)`) rather than any trace the showdown itself could emit: same
# values, same count, but a signal that does not depend on how the showdown is
# implemented. That independence is what makes this a net across a
# reimplementation of it rather than a restatement of one.
_STUD_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

game = check_dsl(
    Path("docs/games/seven-card-stud.cardlang").read_text(), "seven-card-stud.cardlang"
)
out = {}
for seed in range(int(sys.argv[1])):
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
        [sys.executable, "-c", _STUD_CAPTURE, str(seeds_for("seven-card-stud"))],
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
    assert_golden_seeds("seven-card-stud", _capture_stud_hands(), expected)


# Tichu (climbing + the combination model) moves its whole hand — pushing, the
# climbing trick, the special cards, finishing, and scoring — from a Python
# monolith onto the kernel. The migration reproduces the monolith's RNG sequence
# (chooser draws plus two non-chooser draws — the Tichu-call gates and the Dragon
# routing — reproduced by Primitives), so the per-seed results stay
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
for seed in range(int(sys.argv[1])):
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
        [sys.executable, "-c", _TICHU_CAPTURE, str(seeds_for("tichu"))],
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
    assert_golden_seeds("tichu", _capture_tichu(), expected)


# Tichu's finals accumulate ~100 card points a hand, so a late divergence could
# in principle be masked by an offsetting one; like Stud/Cribbage/Schnapsen/Skat
# we also pin the full per-hand vector — the sorted per-team score (the driver's
# own `hand_end` trace) plus the hand's double-victory flag and card-point total,
# derived at the harness from observation events (tests/playout_trace.py; the
# golden's values were pinned while the game's own `tichu_hand` trace still
# emitted them, so byte-identity here doubles as the derivation's standing
# witness) — so a divergence surfaces at the hand it first perturbs. The
# monolith iterated no sets (measured: ZERO divergent seeds across
# PYTHONHASHSEED {0,1,2,3,7} x 50 seeds), so this golden pinned pre-migration
# with nothing sanctioned; any diff is a real draw divergence.
_TICHU_HANDS_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from tests.playout_trace import TichuHands

game = check_dsl(Path("docs/games/tichu.cardlang").read_text(), "tichu.cardlang")
team_of = {p: ti for ti, members in enumerate(game.teams) for p in members}

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
for seed in range(int(sys.argv[1])):
    hands = []
    log = TichuHands(team_of)

    def tracer(event, data, _h=hands, _log=log):
        if event == "hand_end":
            _h.append([data[t] for t in sorted(data)] + _log.hand_summary())

    rng = random.Random(seed)
    play_game(game, rng, tracer, policy(rng), observer=log.observer)
    out[str(seed)] = hands
print(json.dumps(out))
"""


def _capture_tichu_hands() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _TICHU_HANDS_CAPTURE, str(seeds_for("tichu"))],
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
    assert_golden_seeds("tichu", _capture_tichu_hands(), expected)


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
for seed in range(int(sys.argv[1])):
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
        [sys.executable, "-c", _BIGTWO_CAPTURE, str(seeds_for("bigtwo"))],
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
    assert_golden_seeds("bigtwo", _capture_bigtwo(), expected)


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
# `dict(score)`), a signal that does not depend on how the scoring mechanic is
# implemented — no mechanic-local trace is read by any test. `hands_played` is NOT pinned: Cribbage has no phase named
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
for seed in range(int(sys.argv[1])):
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
        [sys.executable, "-c", _CRIBBAGE_CAPTURE, str(seeds_for("cribbage"))],
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
    assert_golden_seeds("cribbage", _capture_cribbage_hands(), expected)


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
for seed in range(int(sys.argv[1])):
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
        [sys.executable, "-c", _SCHNAPSEN_CAPTURE, str(seeds_for("schnapsen"))],
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
    assert_golden_seeds("schnapsen", _capture_schnapsen_hands(), expected)


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
for seed in range(int(sys.argv[1])):
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
        [sys.executable, "-c", _SKAT_CAPTURE, str(seeds_for("skat"))],
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
    assert_golden_seeds("skat", _capture_skat_hands(), expected)


# Coup at real interactive scope (WS5): every challenge, block, claimed
# character, and action target is a chooser decision, so random play decides
# them uniformly at the offers. This golden pins the strongest per-seed
# discriminator the playout yields: the full reveal sequence (every influence
# flip, in order, with its character — where every elimination happens),
# derived at the harness from the flips' observation events
# (tests/playout_trace.py; the golden's values were pinned while the game's
# own `coup_reveal` trace still emitted them, so byte-identity here doubles
# as the derivation's standing witness), plus final coins, the alive vector,
# and the winner, over 40 seeds under PYTHONHASHSEED=0 (the WS5
# behaviour-change re-pin — see kernel-migration.md, Workstream 5).
# Regenerate by running _COUP_CAPTURE exactly as _capture_coup does.
_COUP_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from tests.playout_trace import CoupReveals

game = check_dsl(Path("docs/games/coup.cardlang").read_text(), "coup.cardlang")
out = {}
for seed in range(int(sys.argv[1])):
    log = CoupReveals()
    summary = {}

    def tracer(event, data, _s=summary):
        if event == "coup_game":
            _s.update(
                coins={str(k): v for k, v in sorted(data["coins"].items())},
                alive={str(k): v for k, v in sorted(data["alive"].items())},
            )

    r = play_game(game, random.Random(seed), tracer, observer=log.observer)
    out[str(seed)] = {
        "reveals": log.reveals,
        "coins": summary["coins"],
        "alive": summary["alive"],
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def _capture_coup() -> dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _COUP_CAPTURE, str(seeds_for("coup"))],
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
    assert_golden_seeds("coup", _capture_coup(), expected)


# --- the seed table's own pin ------------------------------------------------


def test_every_seed_override_is_usable() -> None:
    """`SEEDS_BY_GAME` is a table of numbers with no other consumer, so nothing
    else would notice a key naming a game this module stopped capturing, or a
    count larger than the golden it will be compared against. Both would read as
    a deliberate choice while quietly doing something else — a raised count
    would compare against every seed the golden HAS and pass, looking like more
    coverage than it bought.

    red under: add `SEEDS_BY_GAME["hearts"] = 10` (hearts is captured by
    tests/test_playout_hearts.py, not here); set any game's count above the
    seeds its golden records; or set `DEFAULT_SEEDS = 0`.
    """
    unknown = sorted(set(SEEDS_BY_GAME) - set(CAPTURE_GOLDENS))
    assert not unknown, (
        f"{unknown} name no capture in this module — the counts do nothing"
    )
    for game in sorted(CAPTURE_GOLDENS):
        want = seeds_for(game)
        # The EFFECTIVE count, not the override table's entries: a zero
        # reached through `DEFAULT_SEEDS` empties every capture, and
        # `assert_golden_seeds` would accept it — nothing captured equals
        # nothing expected. Checking the table alone leaves that unguarded
        # while the table is empty, which is exactly its state today.
        assert want >= 1, f"{game}: a sweep of {want} seeds checks nothing"
        for name in CAPTURE_GOLDENS[game]:
            pinned = len(json.loads((GOLDEN / name).read_text()))
            assert want <= pinned, (
                f"{game}: asks for {want} seeds but {name} pins {pinned} — "
                f"regenerate the golden before raising the count"
            )
