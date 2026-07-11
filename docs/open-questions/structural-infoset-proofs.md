# Structural proofs of the OpenSpiel-readiness properties

**Tier 2 — high impact, blocked on a data point.** The load-bearing project
requirement is that information sets are *derived* (CLAUDE.md;
[decisions.md](../decisions.md) "Knowledge, visibility, and the projection
model"). The `openspiel_ready` harness proves the readiness properties —
indistinguishability, soundness, perfect recall, conformance, and the
fact-level certification checks below — **empirically**:
it simulates a line, perturbs a hidden card, and checks the derived information
state. That strategy leans on per-game heuristics, and each new information
structure the corpus adds breaks a *different* one, forcing a per-game
accommodation. This is whack-a-mole; the goal is to prove the whole surface at
once.

## The property

A player's derived information state is correct when it separates exactly the
worlds their declared visibility separates: two worlds yield the same
information state for a player **iff** they agree on everything that player is
entitled to see — their zone projections, the public state variables, and
their accumulated observation log. Failure has two directions, and today's
coverage is asymmetric between them:

- **Too fine — a leak.** The observer distinguishes worlds that differ only in
  hidden content. This is the direction the indistinguishability proof
  samples.
- **Too coarse — over-hiding.** The observer *fails* to distinguish worlds
  that differ in something declared visible to them. Today's soundness proof
  perturbs exactly one visible fact — the observer's own hand — so every other
  visible fact (each projection they are entitled to, each public state
  variable, each observation event) is unchecked in this direction. A fact
  silently dropped from the information state passes every leak probe there
  is; only a visible-fact perturbation can catch it.

## The accreting exceptions

Two *distinct* kinds of harness misfit already exist, each patched per game:

- **Driver-exploration gap (Bridge, French Tarot).** The greedy replay (always
  `legal[0]`) never places a bid, so the per-game proofs cover only the pass-only
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

Both failure directions matter to anything that consumes the partition. A
leak enables clairvoyant play; over-hiding misspecifies the game itself —
agents are made artificially ignorant, so any measurement built on the
partition (an equilibrium baseline, a who-knows-what study of belief
reasoning across seats) quietly measures the wrong game while every test
reads green. Two standing caveats bound any partition claim made today: the
Tichu scope reductions keep its call gates and Dragon routing inside rng
primitives, so those choices appear in *no one's* information set until
Tichu's chooser upgrade ([kernel-migration.md](../kernel-migration.md),
Workstream 5 — Coup's upgrade is done: its challenges, blocks, claimed
characters, and targets are real announced decisions); and the guarantee
covers the *structured* partition only — if the
language ever grows free-form communication channels (an LLM seat and
table-talk), meaning carried in that text lives outside the game state and
outside this guarantee.

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

## What any resolution must certify

Whichever option wins, these are the obligations of a correct partition,
with today's coverage named honestly. They double as the acceptance
checklist for resolving this question.

- **Determinism.** The information state is a pure function of the runtime
  state and the observation log — no map-ordering or rendering
  nondeterminism. *Covered:* pinned at the unit level
  (`tests/test_openspiel_infostate.py`, the dict-insertion-order test), by
  the replay engine's pure-function-of-`(seed, history)` design, and per
  game by the adapter-agreement proof, whose two independent replays of the
  same line must render byte-identically.
- **Indistinguishability — no leak.** Perturbing only hidden content leaves
  the observer's information state byte-identical. *Covered, weakly
  sampled:* one seed, one depth, the first legally-replaying swap pair, the
  greedy `legal[0]` line — plus the accreting exceptions above.
- **Soundness, generalized — nothing over-hidden.** Perturbing any
  *declared-visible* fact must change the observer's information state.
  The general obligation is one perturbation per visible fact — every zone
  projection the observer is entitled to, every public state variable, every
  observation event; the zone declarations and their projections *are* the
  machine-readable visibility specification, so the perturbation set is
  enumerated from them rather than hand-picked. *Covered at the snapshot
  level:* the per-visible-fact matrix
  (`tests/openspiel_ready/partition.py`, run per game and per observer by
  the shared harness) applies exactly that enumeration at a replayed pause,
  including the converse — a count-preserving swap in a `count_only` zone
  and any change in a `trivial` zone must NOT move the state. The probe set
  per projection level is itself a declared table (`ZONE_PROBES`), pinned
  complete against the projection registry and enforced fail-loud at probe
  time — a new emission rule cannot be silently under-probed — and the
  observation log is probed along every sequence dimension (presence,
  per-index deletion, adjacent order, extension). The
  replay-level probe still perturbs only the observer's own hand; declared
  frames only — mid-round mechanic state is
  [round-state-in-information-states](round-state-in-information-states.md).
- **Perfect recall over histories.** Information sets are functions of the
  observation *log*, not the current snapshot — true by construction (the
  log is embedded verbatim in the information state) and pinned by the
  append-only proof. Worth adding: paired-line probes — two lines differing
  in an observation a player received must yield that player different
  information states.
- **Seed and undrawn-randomness non-observability.** No information state
  may be sensitive to the root chance seed beyond what dealt-and-observed
  cards already reveal, nor to rng draws not yet made — including the
  rules-level rng gates carrying the Tichu/Coup scope reductions, which
  draw from the same generator. *Pinned structurally per game:* replacing
  the live generator outright and reversing every all-hidden stock's order
  at a paused world leaves every player's information state byte-identical.
  On today's renderer this cannot fail — the information state reads only
  (projected zones, public state, the observation log) — so the assertion
  is a regression pin that bites the moment rendering couples to the
  generator or to hidden-stock order, not a discriminating probe;
  seed-sensitivity through the deal itself is the swap proof's territory.
- **Legal-action agreement.** Two worlds in the same information set for the
  player to move must offer identical legal actions — otherwise the offered
  moves are themselves a leak channel, one OpenSpiel does not police.
  *Covered:* the swap proof asserts the paired worlds pause on the same
  player and offer identical legal actions.
- **Public means public.** A public observation (an announce, an
  identity-projection move) appears identically in every player's log and
  information state. *Partial:* unit-pinned (`test_announce_reaches_everyone`)
  and spot-checked by per-game observational tests; not systematic per
  public fact.
- **Own view present.** The observer's own zones at their owner projection,
  their own decisions in their log. *Covered:* the per-game soundness proof,
  the own-hand-at-identity unit test, and the `chose` events.
- **Adapter agreement.** The proofs run at the DSL level; the partition that
  matters is the one OpenSpiel algorithms actually consume. *Covered per
  game:* a replayed line asserts the registered pyspiel game's rendering —
  current player, legal actions, every player's information-state string —
  equals the DSL-level rendering at every step, which doubles as a per-game
  determinism check across independent replays. The nine games whose greedy
  line terminates walk to the end and assert the terminal returns agree
  (reaching Terminal is itself asserted, so the comparison cannot rot into
  dead code); the six multi-hand score-target games record
  `terminal=False`, their returns exercised only by the conformance sim.

Two obligations on the *proof machinery itself*, whatever form it takes,
both of which the harness meets: a failing check must report its witness —
the two worlds, the perturbed fact, and the information-state fragment that
wrongly agrees or differs — because a bare boolean cannot debug the
compiler (assertion messages carry the perturbed fact and a
first-divergence fragment); and a passing run must record what it covered
(exhaustive vs sampled, seeds, pair counts per game), because that record
is what any external claim about the partition cites (the coverage
registry in `tests/openspiel_ready/partition.py`, rendered as a pytest
terminal summary and dumped as JSON via `CARDLANG_PARTITION_REPORT`).

### Built against the empirical harness

Legal-action agreement, the seed/rng assertions, adapter agreement, the
enumerated per-visible-fact soundness perturbations, and the
witness-and-coverage obligations are built, as per-game proofs over
today's swap-and-replay harness (`tests/openspiel_ready/harness.py` +
`partition.py`) — none of them waited on the data point below. Only the
constructive world generator — building indistinguishable worlds from the
projection lattice instead of sampling swaps — remains blocked, and it is
what keeps this question open.

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

Only the constructive world generator is blocked (everything in "Actionable
now" is not). Its general shape wants **the first game that defeats a simple
swap-axis constraint** — a compound hidden-function probe, whose public outcome is a
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
