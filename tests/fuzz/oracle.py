"""T1 + T3: the fuzzing oracle (grammar-fuzzing.md, "The oracle").

`run_oracle` is the whole T1 contract in one function: an arbitrary text
either passes `cardlang.pipeline.check_dsl`, or it fails as a located
`DiagnosticError` — those are the only two legitimate outcomes. ANY other
exception escaping `check_dsl` is a finding, in the wrong-channel defect
class (decisions.md "Closed-domain completeness"; severity 5 in the
`cardlang-code-review` skill's order): the front end let an internal Python
exception leak instead of rejecting the input in its own diagnostic
channel.

`run_playout` is T3: a mutant that PASSES the pipeline is not yet proven
sound — it still has to run. A bounded random playout under a deterministic
chooser checks the runtime-net invariants implementation.md names: the game
terminates (or is cut off — see "Termination" below), the legal-move set at
every decision covers the requested pick (the runtime chooser's own `n <=
len(candidates)` precondition, of which "never empty" is the special case —
see `_CappedSortedChooser`), and the terminal `GameResult` reconciles
against the game's own declared `winner:`/`loser:` shape. An exception here
is a second, distinct finding class: "accepted-then-crashes-at-playout" —
the mutant slipped past every static wall and only broke at runtime.

The chooser. Same idiom as `tests/metamorphic/pairing.py` (T1 of the
metamorphic suite, merged first): sort every candidate list by
`repr(observe.render(candidate))` before picking, rather than pinning
`PYTHONHASHSEED`. `render` is the runtime's own closed-domain candidate
rendering (`cardlang/runtime/observe.py`) — reusing it means this module
adds no new vocabulary, and it fails loudly (via `render`'s own
`AssertionError`, itself caught and reported as a playout finding) on any
candidate shape it does not recognize. This is a stronger, verified
guarantee than hashseed-pinning (see pairing.py's docstring for the
empirical four-game cross-hashseed check); `PYTHONHASHSEED` is therefore not
pinned here either, a deliberate deviation from the plan's literal wording
that the plan's own T1 predecessor already made and verified.

Termination. Corpus games (and their mutants) are not guaranteed to reach a
natural end under a small step budget — `tests/metamorphic/pairing.py`
documents entire corpus games (Coup, Tichu) whose greedy/sorted line runs
into the tens of thousands of decisions. `run_playout` therefore caps at
`STEP_CAP` chooser calls (env-tunable via `CARDLANG_FUZZ_STEPS`, the plan's
"env-var knob" for a deeper local run) and reports a clean `"cutoff"`
outcome rather than a finding — a cutoff proves nothing about whether the
mutant would have terminated, so it is not evidence of anything broken.
Only an actual exception (or a reconciliation assertion failing on a
NATURALLY terminated game) counts as a T3 finding.

Feed-forward rule (grammar-fuzzing.md, "Findings are minimized, then made
permanent"; CLAUDE.md's kernel-migration doctrine applied to this harness).
A finding discovered here is recorded, not fixed, in `findings.py`'s
`KNOWN_FINDINGS` — concurrent work is touching resolve/typecheck in this
repo right now, so this package makes zero edits to `cardlang/`. Once a
finding IS fixed (in a later, separate change), its minimal input becomes a
new `tests/rejections/<case>.cardlang` + `.expected` pair (T1's rejection
corpus deletes a `KNOWN_FINDINGS` entry, T2/T3 gain one permanent regression
case each) — never a silent removal, so the fix is provably load-bearing.

Residual. T4 (grammar-directed generation walking `cardlang.grammar` rules
directly) and T5 (delta-debug shrinking) are NOT implemented in this
package — findings below are shrunk by hand. Every `KNOWN_FINDINGS` entry
therefore records the smallest input a human reduced it to, not a
mechanically minimal one; a smaller repro may exist. This is the honest
residual grammar-fuzzing.md asks this stage to state up front.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-------------------------------------------------------------------------
Assumes:      `text` is arbitrary — untrusted, possibly malformed DSL
              source. `game` (for `run_playout`) already passed
              `cardlang.pipeline.check_dsl` (resolve/typecheck/expand/
              capacity all ran clean).
Establishes:  `OracleOutcome`/`PlayoutOutcome` — a closed three-way
              classification (`"rejected"`/`"passed"`/`"crash"` and
              `"terminated"`/`"cutoff"`/`"crash"` respectively) that never
              lets a raw exception escape THIS module — callers branch on
              `.kind`, never on a bare `try/except` around these functions.
Now illegal:  nothing downstream — this is leaf test machinery, consumed
              only by `test_fuzz.py` and `findings.py`.
Verified by:  `test_fuzz.py` (the corpus-mutation sweep, T2) replaying every
              `KNOWN_FINDINGS` entry (the "loud and pinned" test, module
              docstring in `findings.py`) plus the ordinary corpus
              (unmutated) games, which must always come back `"passed"`
              then `"terminated"`/`"cutoff"` — never `"crash"`.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any, Literal

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.observe import render
from cardlang.runtime.values import Player

OracleKind = Literal["rejected", "passed", "crash"]


@dataclass(frozen=True)
class OracleOutcome:
    """`kind` is the whole T1 verdict. `game` is set only for `"passed"`;
    `diagnostic` only for `"rejected"`; `exception` only for `"crash"`."""

    kind: OracleKind
    game: n.Game | None = None
    diagnostic: DiagnosticError | None = None
    exception: BaseException | None = None

    def summary(self) -> str:
        if self.kind == "rejected":
            assert self.diagnostic is not None
            return f"rejected: {self.diagnostic}"
        if self.kind == "crash":
            assert self.exception is not None
            return f"crash: {type(self.exception).__name__}: {self.exception}"
        return "passed"


def run_oracle(text: str, source_name: str) -> OracleOutcome:
    """T1. `check_dsl` either returns a checked `Game` or raises
    `DiagnosticError` — both are legitimate. Any other exception is caught
    here (never re-raised) and reported as `"crash"`: the whole point of
    this function is that IT never raises on the fuzzer's behalf."""
    try:
        game = check_dsl(text, source_name)
    except DiagnosticError as e:
        return OracleOutcome("rejected", diagnostic=e)
    except Exception as e:  # noqa: BLE001 -- deliberate: this catch IS the oracle
        return OracleOutcome("crash", exception=e)
    return OracleOutcome("passed", game=game)


class PlayoutCutoff(Exception):
    """Internal sentinel: `STEP_CAP` chooser calls were made. Caught inside
    `run_playout`; never observed by a caller."""


_DEFAULT_STEP_CAP = 60
STEP_CAP = int(os.environ.get("CARDLANG_FUZZ_STEPS", _DEFAULT_STEP_CAP))


def _sort_key(candidate: Any) -> str:
    # Same idiom as tests/metamorphic/pairing.py._sort_key: `repr`, not the
    # rendered value directly, because `render` can return `int`, `str`, or
    # `tuple` depending on the candidate's shape, and a raw `sorted()` over a
    # mixed-type list would raise `TypeError` itself (a false-positive
    # finding, not a real one) rather than comparing like-shaped candidates.
    return repr(render(candidate))


@dataclass
class _CappedSortedChooser:
    """A deterministic, PYTHONHASHSEED-independent chooser (module
    docstring, "The chooser") that raises `PlayoutCutoff` after `cap` calls
    and enforces the runtime chooser's own precondition: `k` must not exceed
    the candidate pool. `cardlang/runtime/chooser.py`'s `random_chooser`
    raises `ValueError("cannot choose {n} of {len} candidates")` on exactly
    this condition (and `rng.sample` would refuse anyway), so a substitute
    chooser that quietly truncated to a short prefix would make the playout
    PROCEED where the real runtime errors — masking exactly the
    accepted-then-crashes-at-playout findings T3 exists to catch (an
    empty pool at `k >= 1` is the special case, subsumed here). The check is
    the same condition in the harness's own channel (`AssertionError`,
    naming the violated invariant), which `run_playout` reports as a
    `"crash"` finding just like the runtime's `ValueError` would be."""

    cap: int
    calls: int = field(default=0, init=False)

    def __call__(self, player: Player, candidates: list[Any], k: int) -> list[Any]:
        self.calls += 1
        if self.calls > self.cap:
            raise PlayoutCutoff()
        if k > len(candidates):
            raise AssertionError(
                f"playout invariant violated: player {player} was asked to "
                f"choose {k} candidate(s) from a legal set of "
                f"{len(candidates)} (the runtime chooser's own contract — "
                "cardlang/runtime/chooser.py; implementation.md: \"the "
                "legal-move set is non-empty until terminal\")"
            )
        ordered = sorted(candidates, key=_sort_key)
        return ordered[:k]


PlayoutKind = Literal["terminated", "cutoff", "crash"]


@dataclass(frozen=True)
class PlayoutOutcome:
    kind: PlayoutKind
    decisions: int
    result: GameResult | None = None
    exception: BaseException | None = None

    def summary(self) -> str:
        if self.kind == "crash":
            assert self.exception is not None
            return f"crash after {self.decisions} decisions: {type(self.exception).__name__}: {self.exception}"
        if self.kind == "cutoff":
            return f"cutoff after {self.decisions} decisions"
        return f"terminated after {self.decisions} decisions: {self.result}"


def _check_reconciliation(game: n.Game, result: GameResult) -> None:
    """T3's "scores reconcile" invariant, generically: `play_game` already
    computes `winner`/`loser` from the game's own declared shape
    (`cardlang/runtime/driver.py`), so this re-checks the SHAPE agrees with
    what was declared — the same stop-and-fix tell CLAUDE.md names (don't
    re-derive a fact another pass established) would flag a per-game score
    arithmetic re-check as out of place here; this is the one fact `play_game`
    does NOT already assert about its own return value."""
    if game.winner is not None:
        if result.winner is None or result.loser is not None:
            raise AssertionError(
                f"a `winner:`-declared game returned {result!r} — expected "
                "winner set, loser unset"
            )
    else:
        assert game.loser is not None  # resolve rejects neither being set
        if result.loser is None or result.winner is not None:
            raise AssertionError(
                f"a `loser:`-declared game returned {result!r} — expected "
                "loser set, winner unset"
            )


def run_playout(game: n.Game, seed: int, *, step_cap: int = STEP_CAP) -> PlayoutOutcome:
    """T3. Plays `game` (already pipeline-checked) out under `seed` with the
    capped sorted chooser. See module docstring, "Termination", for why a
    cutoff is not itself a finding."""
    chooser = _CappedSortedChooser(step_cap)
    try:
        result = play_game(game, random.Random(seed), chooser=chooser)
        _check_reconciliation(game, result)
    except PlayoutCutoff:
        return PlayoutOutcome("cutoff", decisions=chooser.calls)
    except Exception as e:  # noqa: BLE001 -- deliberate: this catch IS the T3 oracle
        return PlayoutOutcome("crash", decisions=chooser.calls, exception=e)
    return PlayoutOutcome("terminated", decisions=chooser.calls, result=result)
