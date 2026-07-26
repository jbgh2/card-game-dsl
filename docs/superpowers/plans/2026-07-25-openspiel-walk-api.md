# Scoping: a resumable OpenSpiel adapter state

Scoping for removing the O(n^2) cost of driving a line through the OpenSpiel
adapter. Written 2026-07-25 against `claude/test-suite-consolidation-8b7a3c`.

**This is a scoping document, not an approved plan.** It ends with a
recommendation and a decision Ben has to make, because the work that would
actually recover the time amends a settled rationale in decisions.md.

## The measurement that motivates it

`pytest -q --durations=0`: 5088 tests, 1163.69s local; CI jobs run 31-58
minutes (median ~53). The cost is concentrated, not spread — 19% of the tests
are 94% of the wall-clock, and one test is 23.8% of it:

| class | sec | % | tests |
|---|---|---|---|
| adapter-quadratic (`openspiel_ready/` + legacy hearts) | 481.9 | 41.4% | 160 |
| genuine playout/fuzz depth (driver-bound) | 455.6 | 39.2% | 794 |
| vestigial `PYTHONHASHSEED` subprocesses | 157.0 | 13.5% | 16 |
| everything else | 60.7 | 5.2% | 4118 |

The adapter class is quadratic by construction. `CardlangState._run`
(`cardlang/openspiel/game.py`) caches only the current history; each
`apply_action` invalidates it and the next query calls
`replay.run(path, seed, tuple(history))`, which re-simulates from step 0.
Measured on `cardlang_canasta`, cumulative walk time: hist=100 15.6s,
hist=200 61.8s, hist=400 269.8s — 4.0x and 4.4x per doubling.

## Where the cost actually sits — the finding that shaped this scope

`openspiel_ready/` is 439.8s of call time. Split by which layer drives the
walk:

| sec | % | test | layer |
|---|---|---|---|
| 316.2 | 71.9% | `test_pyspiel_conformance` | drives `CardlangState` via pyspiel |
| 104.1 | 23.7% | `test_adapter_agrees_with_the_dsl_information_state` | both, deliberately |
| 10.7 | 2.4% | `test_perfect_recall_logs_are_append_only` | `replay.run` loop |
| 4.9 | 1.1% | per-game bespoke tests | mixed |
| 3.9 | 0.9% | swap + soundness + seed proofs | `replay.run`, shallow |

Outside `openspiel_ready/`, the legacy `tests/test_openspiel_hearts.py` (42.1s)
completes the 481.9s class. Its three expensive tests —
`test_random_sim_conformance` 19.7s, `test_perfect_recall_no_duplicate_infostates_in_a_game`
12.2s, `test_full_rollout_returns_negated_scores` 10.2s — are **also**
pyspiel-driven, so also Tier-2-only. They are additionally redundant (issue #83
lever 1), which makes that file the one place the quadratic can be removed by
deletion rather than by engineering.

**96% of the class is driven through `CardlangState`, not through
`replay.run`.** That kills the cheap fix. A bulk-walk API at the `replay`
layer — one pass that visits every decision on a line, driven by a policy
callback instead of `ChooserAbort` — is easy, safe, and reaches **3.3%** of
the class (14.6s). It is not worth doing for CI on its own.

The reason is structural, not incidental. `test_pyspiel_conformance` picks its
action from the *pyspiel* state's `legal_actions()` and then calls
`state.apply_action(...)`. The driver has to be suspended *between* those two
calls, because the action does not exist until the caller has seen the legal
list. A policy callback cannot supply it. Only a genuinely resumable state can.

The adapter-agreement test is the same shape and additionally re-simulates the
pyspiel side **on purpose** — its docstring makes the independence a feature
("the comparison doubles as a per-game determinism check"), so half its cost is
bought coverage, not waste.

## Gate 1 — Owners

- **decisions.md, "OpenSpiel compilation"** (line 2218) is the owner. It
  settles the re-simulation design and states its rationale: the state is
  `(seed, history)` so it is "trivially cloneable (the property OpenSpiel
  exercises most)", and it names "the eventual compilation pass" as the
  general path.
- **A resumable state amends that rationale.** This is the decision Ben owns.
  The amendment is narrow — see "Cloneability under a park" — but it is an
  amendment, not an addition, and it does not ship without decisions.md
  moving in the same change.
- **The tracker** sequences this, not a doc: issue #139 owns the adapter's
  performance line and issue #143 pins the cross-cutting order. The
  deferred-work backlog left roadmap.md in PR #151.
- **open-questions/structural-infoset-proofs.md** owns the proof harness this
  speeds up. Nothing here changes what the proofs assert.
- Contracts read before planning: `replay.py` (the `ChooserAbort` protocol),
  `runtime/driver.py`, `runtime/state.py` (`ChooserAbort` attaches the **live**
  `RuntimeState`).

### Doc drift found, deliberately NOT in scope

decisions.md:2227 says "Hearts is registered as a `pyspiel.Game`" and
decisions.md:2234 says "The adapter is per-game and proof-scoped". Both are
stale: `registry.GAMES` derives from the `docs/games/` glob (29 games, all
registered) and `game.py`'s docstring says "One general adapter (SP1 spec)",
matching CLAUDE.md. Real operating-rule-1 violation, but not lockstep with
this change. Separate one-paragraph edit, Ben's call.

## Gate 2 — Classification

**Runtime adapter (`cardlang/openspiel/`) + proof harness (`tests/`).** No
grammar surface, no AST, no resolve/typecheck, no stdlib registry, no corpus
game.

**The surface-totality audit FIRES.** Not because grammar surface moves, but
because this is rigor-critical foundational machinery (CLAUDE.md: "foundational
code (proof harness, projections, encodings, invariants) is complete against
its own domain") and its domain — `registry.GAMES` — is closed and enumerable.
The Gate 2 tie-breaker ("when unsure, it matches") confirms it.

## Gate 3 — Acceptance criteria

1. **Runs.** The resumable state reaches the same decisions as re-simulation,
   for every registered game.
2. **Regression-clean.** `mypy` (bare) + full `pytest -q`. Goldens
   byte-identical — this change claims complete behavioural neutrality, so any
   golden diff is a defect, not a regeneration.
3. **Info sets derive — and identically.** Byte-identical
   `information_state_string` for every player at every step versus today's
   path. This is the criterion, not a side-effect: the value of the adapter is
   derived info sets, and a faster path that renders them differently is a
   failure however green it runs.

**Corpus lockstep list: empty, and that is load-bearing.** No language surface
moves, so no file in `docs/games/` changes. If one needs to, the change has
exceeded its classification and returns to Gate 2.

**Witness:** all 29 corpus games exercise this through `tests/openspiel_ready/`.
The *depth* axis needs its own witness — canasta at 400 steps is the only place
the quadratic is visible at test scale, so it is the named deep case.

## The design: park the driver

`play_game` is a recursive interpreter whose chooser is a callback and whose
continuation lives on the Python stack. To suspend between `legal_actions()`
and `apply_action()`, run it in a worker thread and have the chooser block on a
queue: the adapter hands the thread an action, the chooser returns it, and the
simulation advances to the next decision and blocks again. `ChooserAbort` stays
exactly as it is for the existing `run()` path.

**Feasibility gate, partially checked — read the scope before trusting it.** An
AST scan of `cardlang/runtime/*.py` and `cardlang/openspiel/*.py`, covering
**top-level `Assign`/`AnnAssign` whose value is a mutable literal or a
`list`/`dict`/`set` constructor only**, found rank tables, point values and
suit orders (`values.COMPONENT_SETS`, `driver.RANK_DIR_TO_PICK`, the per-game
scoring tables) — all read-only in use, no accumulators.

That scan does **not** establish "the runtime has no shared mutable state". It
would miss a mutable default argument, a class-level mutable attribute, a
module-level dict built by a loop or comprehension, and everything in
`cardlang/stdlib/`. Closing those is a task, not a finding. What is true is
that each parked game owns its own `RuntimeState` and `random.Random(seed)`,
and the `parse_text`/`_check` memos are `lru_cache` (thread-safe in CPython).

### Cloneability under a park — the amendment

decisions.md defends `(seed, history)` because it makes `clone()` trivial, and
that is the property OpenSpiel exercises most. The amendment keeps it:

- `clone()` stays **O(1)**. It copies `(seed, history)` and marks the clone
  *cold* — no thread, no shared state with the original.
- A cold state's **first** query re-simulates once (O(n)) and parks. Every
  subsequent step on that state is O(1).
- So a walk of length n costs O(n) instead of O(n^2); a clone at depth d then
  walked to n costs O(d) once plus O(n-d).

What genuinely changes is that a live advanced state now **owns an OS thread**.
That is the cost decisions.md's design avoided, and it is the real risk:

- **Thread explosion.** MCTS/CFR hold many un-terminated states. Mitigations to
  design: materialize the thread lazily (only on the second query), tear it
  down on `__del__` and on `is_terminal()`, and cap live threads with a
  fallback to today's re-simulation past the cap. The cap makes the change
  strictly no-worse-than-today rather than a new failure mode.
- **Cleanup.** A parked thread blocked on a queue leaks if the state is dropped
  without terminating. Needs an explicit close protocol, and a test that
  asserts thread count returns to baseline after a walk.
- **Greenlets** would avoid both, at the cost of a dependency. Worth pricing
  before committing to threads.

### The aliasing hazard, whichever tier ships

`Pause` carries `rs`, the **live** `RuntimeState`. `ChooserAbort` attaches it
without copying, and `Zone` is mutable and mutated in place. Today that is safe
because every `Pause` comes from a fresh `play_game`. Under any resumable or
single-pass design it is not: a `Pause` read after the simulation continues
reports **end-of-game** state.

Measured on canasta, per pause: `deepcopy(rs)` is 3.39 ms at history=120 and
3.92 ms at history=380 — **flat** with depth (cards move between zones, they
are not created). Rendering all four players' `information_state` eagerly costs
0.87 ms / 1.03 ms — **3.8x cheaper than snapshotting**.

So the split is affordable and it is a **wall**, not a docstring warning,
triaged at the layer that owns the class:

- **`PauseView`** — `player`, `legal`, `infostates: dict[int, str]` rendered
  eagerly. No `rs` attribute, so a live alias is unrepresentable.
- **`SnapshotPause`** — adds a deep-copied `rs` **and a copied `obs_logs`**
  (`{q: list(log) for ...}`). `obs_logs` is a dict of lists appended in place by
  the `observe` closure and `deepcopy(rs)` does not touch it; leaving it by
  reference reproduces the exact bug the wall exists to stop, and
  `information_state(q, rs, obs_logs[q])` reads both.

Why this must be a wall: `harness.py`'s swap proof holds `pause_a` across later
`run()` calls and reads `pause_a.rs.zones.instance(hz, opp1).cards`. Handed a
live alias it would read post-walk hands and **still pass** — vacuously green,
in the machinery whose whole job is proving info sets.

## Gate 4 — The grid (task 1, authored red)

**Domain:** `registry.GAMES` x step-wise equivalence, axes derived in code from
the registry — never a hand-written game list, so a 30th game cannot land
uncovered.

**Property, per game, per step:** the resumable path and today's re-simulation
path agree on `player`, `legal`, every player's `information_state` string, and
terminal `returns`.

**Coverage bound and its residual (recorded, not silent).** The grid's oracle
*is* the O(n^2) path, so deep equivalence on all 29 games costs more than the
change saves. The bound: a short prefix (~40 steps) on all 29, plus one deep
case. The deep case is the residual — depth equivalence proven for one game,
not the corpus — and it gets a tracker record on issue #83.

**Born-green risk:** cells pass the moment the resumable path delegates to the
same `play_game`. Each names its reddening mutation (yield the live `rs`; drop
the per-draw `chose` emission; let the parked thread outlive its state).

## Task list — every step names its proving artifact

1. **Grid, red.** Parametrized equivalence over `registry.GAMES`; expected
   outcomes authored before the implementation. *Artifact:* the grid module,
   red.
2. **Fix the coverage bound.** Pick the deep-case game; record prefix depth and
   residual. *Artifact:* ledger in the grid docstring + an issue #83 record.
3. **Finish the shared-mutable-state sweep** the feasibility scan only started:
   mutable default arguments, class-level mutable attributes, module dicts
   built by loops or comprehensions, and all of `cardlang/stdlib/`. Sweep the
   class, do not spot-check. *Artifact:* a concurrent-walk test that two parked
   games of the same corpus game interleave without diverging from their
   sequential results.
4. **Price greenlets vs threads.** *Artifact:* a written comparison against the
   thread-explosion and cleanup risks above; a decision recorded before code.
5. **Park mechanism behind the existing `Pause` contract.** *Artifact:* the
   existing `run()` path unchanged and still covered.
6. **`PauseView` / `SnapshotPause` split, red first.** *Artifact:* a test that
   a `SnapshotPause` taken at step k still reports step k's world — for `rs`
   AND `obs_logs` — after the walk continues. The red-under must be verified to
   fail for THIS wall, not a neighbour.
7. **Lifecycle wall.** *Artifact:* thread count returns to baseline after a
   walk; a dropped state leaks nothing.
8. **`CardlangState` on the parked path, with the cap fallback.**
   *Artifact:* grid cells green; `test_pyspiel_conformance` unchanged in what
   it asserts.
9. **decisions.md amendment.** The cloneability paragraph gains the cold-clone
   model. *Artifact:* the edit, in the same change.
10. **Re-measure.** Full `pytest -q --durations=0`; report the printed number,
    not a projection.

## Recommendation

**Do not start this yet.** It is the largest single lever in the suite (~40% of
wall-clock) and it is also the riskiest thing in this scope: it puts an OS
thread behind a `pyspiel.State`, in the machinery the readiness proofs depend
on. Ben should decide it on its merits for **algorithm performance** — IS-MCTS
and CFR pay this quadratic on every rollout, which is the project's actual
purpose — with the CI saving as a secondary benefit.

### Issue #83's levers 1 and 2 were checked and are far smaller than billed

Both were verified against the code rather than cited. Neither is worth ~200s;
together they are **~25s**, and neither is a clean "no coverage change".

**Lever 2 saves ~5s, not 157.0s.** The 157.0s is the *file* total, and it is
almost entirely the 50 `play_game` calls the capture script runs — not the
subprocess. Measured directly: subprocess overhead (fresh interpreter +
`import cardlang` + one Earley parse) is **0.35-0.40s per launch**, and there
are 14 launches, so ~5s. The playouts survive the change: french-tarot costs
**81.61s in-process** against a measured test duration of 81.10s. Removing the
subprocess removes the overhead, not the work. The real cost in that file is
french-tarot's 50 seeds, which is a seed-count decision (issue #83 lever 3),
not a subprocess one.

**Lever 1 saves ~19.7s, not 42.1s — the rest is not redundant.** Checked
per test, as issue #83 itself instructs:

- `test_random_sim_conformance` (19.7s) — **safe to delete.** The bounded walk
  in `openspiel_ready/test_hearts.py` covers the same walk, and 14 of the 29
  games still run the full `pyspiel.random_sim_test` against the *same general
  adapter*, so the OpenSpiel API-invariant battery is not lost. Its one unique
  assertion, `num_distinct_actions() == 52`, is held by
  `test_openspiel_encoding.py::test_hearts_space_is_cards_only`.
- `test_full_rollout_returns_negated_scores` (10.2s) — **keep.** It is the only
  test that drives hearts through the pyspiel `State` to Terminal and checks
  `returns()`. Hearts sets `adapter_terminal_steps=None`, so the readiness
  proofs stop at `depth` and never reach Terminal.
- `test_perfect_recall_no_duplicate_infostates_in_a_game` (12.2s) — **keep.**
  Grepping the suite, the no-duplicate-info-state assertion exists **nowhere
  else**. The harness's `test_perfect_recall_logs_are_append_only` is a
  different, structural property.

**A false coverage claim found while checking.** `openspiel_ready/test_hearts.py`'s
docstring justifies bounding its walk by asserting that hearts'
"full-game-to-Terminal coverage **through the actual pyspiel `State` wrapper**
lives in `test_openspiel_replay.py`'s KERNEL_GAMES list". It does not.
`_record` (test_openspiel_replay.py:38) calls `play_game` directly and then
`replay.run` — the DSL layer. It never constructs a `CardlangState`. The
bounding was sanctioned on a premise that does not hold; the coverage it names
is real but is at the wrong layer. Worth fixing on its own terms, independently
of any performance work.

### The one large, safe lever is the stopgap

1. **A stopgap decision on `conformance_steps`.** Canasta's walk is bounded at
   400 and costs 277.4s; the next most expensive conformance walk is 6.2s.
   This does not need modelling — the same walk was timed at every depth:
   **150 steps costs 34.8s against 400 steps at 269.8s, an 87% reduction**
   (120 steps: 24.1s, 91%). This **is** a coverage trade — the 400 exists so
   canasta reaches multiple deals — so it wants an explicit decision and a
   recorded residual, exactly as issue #83 says of its lever 3. A stopgap, not
   a fix: the quadratic stays.

The `replay`-layer walk API is **not** recommended as a standalone change. At
3.3% of the class it does not pay for its own risk. If the park ships, the
`PauseView`/`SnapshotPause` split comes with it as the aliasing wall.
