# Structural proofs of the OpenSpiel-readiness properties

**Tier 2 — high impact, blocked on a data point.** The load-bearing project
requirement is that information sets are *derived* (CLAUDE.md;
[decisions.md](../decisions.md) "Knowledge, visibility, and the projection
model"). The `openspiel_ready` harness proves the four readiness properties —
indistinguishability, soundness, perfect recall, conformance — **empirically**:
it simulates a line, perturbs a hidden card, and checks the derived information
state. That strategy leans on per-game heuristics, and each new information
structure the corpus adds breaks a *different* one, forcing a per-game
accommodation. This is whack-a-mole; the goal is to prove the whole surface at
once.

## The accreting exceptions

Two *distinct* kinds of harness misfit already exist, each patched per game:

- **Driver-exploration gap (Bridge, French Tarot).** The greedy replay (always
  `legal[0]`) never places a bid, so the four proofs cover only the pass-only
  line of the auction; the real bidding / chien discard / trick decisions are
  covered by separate dedicated tests (the CLAUDE.md honesty note).
- **World-generator gap (Go Fish).** Swap-and-replay assumes a hidden swap that
  replays *legally* yields a world *indistinguishable* to the observer. That is
  false when a public observation is a function of hidden content — Go Fish's
  ask publicly reveals a transfer count that reads the target's hidden hand — so
  the harness fails on a legally-replayed but distinguishable world. Patched with
  a same-`rank` swap axis (bespoke-test fallback); a *compound* hidden-function
  probe would defeat any simple swap axis.

Both are the same root: the proof is a **simulate-and-perturb sampler** over a
property that is really **structural**.

## Why this matters

Derived info sets are the whole reason the DSL beats hand-coding each game
against OpenSpiel, so their correctness is the acceptance criterion for every
game. Establishing it by random simulation plus hand-tuned perturbation is a
method whose coverage gaps *grow* with game diversity — exactly as the corpus
expands toward the generalization-path dream (all fixed-outcome games;
[design-notes/generalization-path.md](../design-notes/generalization-path.md)).
Each new probing or hidden-function mechanic risks a fresh *silent* gap (the
worst failure mode — a proof that passes vacuously or never reaches the
mechanic). A structural proof would cover the entire surface once, without
per-game tuning, and turn "passed a random sim" into a real guarantee.

## The direction

`information_state(P)` is, by construction, a pure function of (P's zone
projections, the public state, P's observation log)
([decisions.md](../decisions.md) "Hidden information lives only in zones; state
is public"). That makes indistinguishability **analytic**, not empirical:

- **Construct indistinguishable worlds directly** — hold P's observation log and
  projections fixed and vary only genuinely-hidden content — instead of swapping
  hidden cards and hoping the replay stays both legal and unobserved. The
  equivalence classes come from the projection lattice plus the
  observation-emission sites, not from a sampled line.
- **Reduce the proof to the emission sites.** If every decision / movement site
  emits the correct per-observer observation, indistinguishability holds by
  construction of the info-state function; the obligation becomes "prove each
  emission site correct" — checkable once, over the kernel's finite set of
  sites, rather than once per game per random line.
- **Keep the empirical harness as a cheap smoke test**, with the structural
  argument as the actual guarantee.

## The options

- **Structural / constructive proof (recommended direction).** Build the
  indistinguishability equivalence classes from the projections + emission sites
  and prove the info-state function constant within a class. Replaces the swap
  generator entirely; subsumes both existing misfits.
- **Keep patching per game.** A new swap axis or bespoke test each time a game
  breaks a heuristic. Rejected as the standing strategy — it is the whack-a-mole
  this question exists to end — though it remains the cheap fallback for any one
  game.
- **Hybrid.** Structural proof for indistinguishability + soundness (the
  perturbation-sensitive properties); keep the simulation harness for
  conformance and perfect recall, where it fits.

## Blocked on

The general shape wants **the first game that defeats a simple swap-axis
constraint** — a compound hidden-function probe, whose public outcome is a
non-trivial function of hidden state (e.g. "how many red cards do you hold", a
sum-capture reveal, a partial-information bid comparison). That case forces the
equivalence-class machinery to be general rather than axis-shaped, and pins
whether the structural proof can be fully static or needs a constructive
sampler. Until then the direction is clear but a committed design risks
generalizing from two points. It could instead graduate to a design-note and be
built proactively if the corpus is about to add such a game — the whack-a-mole
cost is paid per game, so moving before the next mole is the point.

Related: the readiness harness (`tests/openspiel_ready/harness.py`);
[decisions.md](../decisions.md) "Knowledge, visibility, and the projection
model" and "Hidden information lives only in zones; state is public"; the
load-bearing section of CLAUDE.md;
[decisions.md](../decisions.md) "Declared parameter domains" (Go Fish, the
game that surfaced the world-generator gap); and
[design-notes/generalization-path.md](../design-notes/generalization-path.md)
(why whack-a-mole doesn't scale).
