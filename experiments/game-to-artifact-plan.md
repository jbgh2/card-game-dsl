# Proposal: Institutionalizing the design→solve→ship loop

> Status: proposal (experiment-grade, produced by a planning agent from the two
> completed instances — Green Lane and Undertow). Promotion of any part into
> `cardlang/` or `tests/` follows the repo's corpus-first doctrine and the
> surface-totality gate. Companion evidence: `green-lane/REPORT.md`,
> `undertow/REPORT.md`.

## Goal and non-goals

**Goal.** Turn the pattern proven twice — design a game in the DSL outside the corpus, evaluate it through the OpenSpiel adapter (exact battery for small games, probe battery for large ones), then ship a self-contained playable artifact with a measured AI opponent — into repeatable infrastructure: a promoted, gate-covered evaluation library (`cardlang/lab/`), a shared artifact kit with mechanical drift protection (differential fixtures), and a scaffolded per-experiment workflow. Extract, don't rewrite: `glcommon.py`/`utcommon.py`, `solve.py`, `proofs.py`, the `analyze_*` scripts, and the Green Lane play template are the source material, and the repo's promotion doctrine (corpus-first, promote at second/third instance) decides what moves into the package versus what stays experiment-grade.

**Non-goals.** No changes to the corpus adapter (`cardlang/openspiel/game.py`), the runtime, the grammar, or the corpus games; no per-game code in the package; no shipped-artifact LLM capability or network access (strict-CSP, self-contained pages stay the contract); no attempt to make tabular solver output deployable beyond small games; no automation of the genuinely creative steps (game design, UI art direction, DESIGN/REPORT prose, heuristic invention). CI stays exactly `mypy` (bare) + `pytest -q`; `experiments/` stays outside both gates.

## The per-game workflow after the infrastructure exists

A designer's-eye walkthrough, from `.cardlang` to published artifact. Steps marked **[1 cmd]** are single commands; unmarked steps are creative work.

1. **Scaffold.** `python experiments/new.py rip-current` **[1 cmd]** — copies `experiments/_template/` to `experiments/rip-current/`: `DESIGN.md` skeleton, `rip-current.cardlang` stub, `REPORT.md` skeleton with the honesty-ledger section preprinted, `probes.py` stub (game-specific probe plugs), `opponent.py` stub, `play/` with the kit page template, `variants/`.
2. **Design.** Write `DESIGN.md` and the game file(s), including a `-mini` reduction if a small-state exact solve is wanted. `cardlang experiments/rip-current/rip-current.cardlang` **[1 cmd]** checks it through the full front end.
3. **Evaluate.** `python -m cardlang.lab experiments/rip-current/rip-current.cardlang --out experiments/rip-current/results.json` **[1 cmd]**. The battery self-tiers: it registers the game (declared-or-verified utility, configurable seed sampling), runs smoke shape (lengths, branching, seat balance, zero/constant-sum verification, sample infostates), the four generic info-set proofs, then either the **exact tier** (budgeted census → CFR+ with exploitability trend → game value, mixedness, reach-weighted top decisions, naive-grid-vs-best-response using the rules plugged in `probes.py`) or the **probe tier** (decision-liveness by ply, obs-log-driven probes from `probes.py`, MCCFR training + skill gradient + head-to-head arena). One JSON out, REPORT-ready. Variants: same command per file in `variants/`.
4. **Iterate.** Read `results.json`, red-team, write variants, re-run step 3 per variant, record the round in `REPORT.md`.
5. **Choose and benchmark the opponent.** Fill in `opponent.py` (a policy over the adapter's `Pause`, parameters explicit). `python -m cardlang.lab.arena experiments/rip-current/opponent.py --vs equilibrium,best_response,mccfr:120000,random --out opponent-bench.json` **[1 cmd]** produces the measured strength claim (exact deviation/BR loss when the tree fits; head-to-head means ± stderr when it doesn't). For a tabular opponent, `python -m cardlang.lab.policy_export ...` **[1 cmd]** solves, canonicalizes keys, proves key injectivity, writes `play/policy.json`, and re-verifies the exported table's exploitability. For PIMC, the same arena command benchmarks `cardlang.lab.pimc` with chosen worlds/rollouts (shuffle-only games).
6. **Export the drift barrier.** `python -m cardlang.lab.fixtures experiments/rip-current/rip-current.cardlang --traces 200 --views --out experiments/rip-current/play/fixtures/` **[1 cmd]** — action-id/label table, per-trace deal + per-step legal sets/labels + per-player view projections + terminal returns; exhaustive full-tree fixtures for mini-sized games.
7. **Build the page.** Write the game's JS rules engine and UI against the kit's engine interface (`init/legal/apply/returns/view`), dropping in kit modules (fixture replayer, PRNG, opponent shells, relay briefing renderer/parser). `node experiments/_kit/replay.js experiments/rip-current/play/` **[1 cmd]** must pass every fixture — legal-set, label, view, and returns equality at every step — plus opponent parity and relay round-trip checks. Also runnable as a browser test page.
8. **Publish.** `python -m cardlang.lab.build_artifact experiments/rip-current/play/rip-current.template.html` **[1 cmd]** — inlines fonts/assets and the generated tables, injects the CSP meta, refuses external references, enforces the size budget, stamps the footer with the benchmark claim and fixture-pass provenance. Output: one `.html` file.
9. **Report.** `REPORT.md` cites `results.json`, `opponent-bench.json`, and the fixture-pass stamp. Done.

## Phases

Effort legend: **S** ≤ half a day, **M** 1–3 days, **L** multi-day. "Extracted" names the existing source; "new" means written fresh.

### P0 — One lab substrate (kill the glcommon/utcommon fork)

The registration/memo boilerplate is at its second instance, which is exactly the repo's promotion trigger.

- **`cardlang/lab/register.py`** — extracted from the two `*common.py` files. One `register_experiment(path, *, short_name, num_seeds, utility)` covering both shapes: configurable seed count at the chance root (1 for shuffle-free, sampled for dealt games), declared utility (`zero_sum` / `constant_sum(k)` / `general`) mapped to `pyspiel.GameType`, and an empirical utility verification (N random playouts must sum as declared). **(M)**
- Replace the monkey-patching memos with a first-class cached path: the lab's `_State` subclass calls a module-level `lru_cache`d runner keyed `(path, seed, history)` directly, and memoizes the infostate string in an explicit bounded dict — no mutation of `cardlang.openspiel.replay` or `CardlangState`. **(S)**
- Retarget both experiments: `glcommon.py`/`utcommon.py` become thin shims. **(S)**
- `pyproject.toml`: extend the pyspiel mypy override to `cardlang.lab.register`. **(S)**
- Tests in `tests/test_lab_register.py` (skip-if-no-pyspiel): registration round-trip on a tiny fixture game, utility misdeclaration refused loudly, memo purity. Needs a **nano fixture game** at `tests/fixtures/nano-duel.cardlang` (a 2-3 decision shuffle-free game, walkable exhaustively in tests) — also serves P1/P2 tests. **(M)**

Acceptance: gates green; `proofs.py` and a 20-iteration `solve.py` run reproduce prior outputs through the shims; no import of `experiments/` from `cardlang/` or `tests/`.

### P1 — The size-tiered, game-agnostic evaluation battery

- **`cardlang/lab/exact.py`** — extracted from `analyze_mini.py` + `solve.py`: budgeted census (node/time caps decide tier), CFR+ with exploitability trend, expected value, reach-weighted strategies, mixedness. Green-Lane-specific label assumptions removed from the core. **(M)**
- **`cardlang/lab/naive.py`** — extracted from `analyze_heuristics.py`/`analyze_exploit.py`: `joint_value`, best-response exploitation, and a *pluggable* naive-rule grid — generic defaults (uniform, first-legal) plus rules the experiment's `probes.py` registers. The two-column "vs equilibrium / vs best response" table becomes standard output whenever the tree fits. **(M)**
- **`cardlang/lab/probes.py` + `cardlang/lab/obslog.py`** — extracted from `analyze_undertow.py`: shape, decision-liveness, and a typed accessor API over the observation log so probes stop regexing raw tuples (the event vocabulary is closed — the accessor can be complete against it, pinned). Undertow's tide probe rewrites onto this API but stays in `experiments/undertow/`. **(M)**
- **`cardlang/lab/sampled.py` + `cardlang/lab/arena.py`** — extracted from `analyze_full.py` + `analyze_undertow.py`: MCCFR training (2p outcome-sampling and n-player rotation), weak/strong gradient, head-to-head arena (seats alternating/rotating, mean ± stderr). **(M)**
- **`cardlang/lab/proofs.py`** — generalized from Green Lane's: the four experiment-grade checks with the game-specific node classifier replaced by an observation-delta classifier (a decision is concealed for observer Q iff Q's obs-log delta is identical across alternatives — derived, not configured). Does **not** touch `tests/openspiel_ready/`; overlap recorded as a promotion candidate. **(M)**
- **`cardlang/lab/__main__.py` + `report.py`** — the one-command driver: auto-tier, run battery + proofs, write one versioned results JSON. **(M)**
- Tests over the nano fixture game for every module. **(M)**

Acceptance: `python -m cardlang.lab` reproduces Green Lane mini's recorded census and exploitability trajectory; selects the probe tier on Undertow and reproduces the liveness table's shape; gates green; zero game-specific labels in the battery.

### P2 — The artifact kit: fixtures, JS harness, opponent kit, build

- **`cardlang/lab/fixtures.py`** (new; precedent: `tests/test_differential_gops.py`'s lockstep walk): export (1) the action table (every reachable global action id + label); (2) per-trace: seed, post-setup deal, per-step actor, legal ids + labels, chosen action, optional per-player view projections (zone views, public state, obs-log delta — the briefing ground truth), terminal returns; (3) `--exhaustive` full-tree fixtures when the census fits. Trace policies: random plus registered policies (solver-driven traces reach states random play misses). Schema versioned; provenance embedded. **(M)**
- **`experiments/_kit/`** (new, JS/HTML only): `replay.js` node fixture replayer against the kit engine interface (`init/legal/apply/returns/view`) + `replay.html` browser variant; `prng.js` + `cardlang/lab/prng.py` (one deterministic PRNG both sides, cross-checked); opponent shells `tabular.js` / `heuristic.js` / `pimc.js` / `relay.js` (generalized from the Green Lane template). **(M)**
- **`cardlang/lab/policy_export.py`** (new): exact-tier average policy → `policy.json` keyed by a canonical key (player + own-view projection + rendered own-choice history — never the runtime infostate string), injectivity asserted over all solved infosets, truncation rules, and reload-verification (recompute exploitability from the exported table; ship only on match). **(M)**
- **`cardlang/lab/parity.py`** (new): K exported decision points; the JS twin must reproduce the Python twin's distribution and sampled action exactly (IEEE-754 both sides, operation order pinned). **(S–M)**
- **`cardlang/lab/pimc.py` + `forced_deal.py`** (new): Python PIMC twin for hidden-deal games — consistent-world sampler (unseen cards, hand counts, voids and reveals from the obs log) + a prescribed-shuffle `Random` so sampled worlds replay through the real runtime. Hard wall: refuse any game whose rng use exceeds the setup shuffle. **(L)**
- **`cardlang/lab/build_artifact.py`** (new): placeholder inlining, CSP meta injection, refusal of external URLs, size budget, provenance footer (benchmark numbers + fixture-pass stamp). **(S–M)**
- **Retrofit Green Lane** as the kit's first proof: fixtures for the shipped page's engine; port the officer to a Python twin and produce its first real benchmark via the arena. Divergences found = the kit demonstrating its value. **(M)**
- Optional gated test: `tests/test_artifact_kit.py` runs `replay.js` on the nano game via node, `skipif` node absent. **(S)**

Acceptance: Green Lane page passes full fixture replay; `policy_export` on the mini reload-verifies; parity fixtures pass in node; `build_artifact` reproduces a byte-stable page; gates green.

### P3 — Institutionalize: scaffold, docs, second dogfood

- **`experiments/_template/`** + `experiments/new.py` copier. **(S–M)**
- **`experiments/README.md`** — the workflow, tier thresholds, opponent taxonomy with input/benchmark requirements, and the **promotion ledger** (what is experiment-grade vs promoted; standing triggers — a third copy of any pattern promotes it; named candidates: unifying `lab/proofs.py` with the corpus harness core; the JS IR interpreter, trigger below). One line in CLAUDE.md's tree. **(S)**
- **Undertow artifact** — the kit's second, harder dogfood and first PIMC instance (est. 150–250 engine lines; sampler, n-player arena, 4-player relay). **(L)**
- Surface-totality audit over the promoted registries (fixture schema version, obslog accessor completeness, utility-declaration domain, PIMC rng wall): misuse-probe rejection tests + completeness ledger. **(M)**

Acceptance: from-scratch dry run of the scaffold reaches a built page via the documented commands; Undertow's page passes its fixtures; gates green.

## The faithfulness decision

**Recommendation: per-game hand-port + promoted differential fixtures, hardened by generating *data* (not code) from the IR/ActionSpace — with the JS IR interpreter recorded as a roadmap candidate behind an explicit trigger.**

Evidence (measured):

- The corpus-wide IR uses **57 distinct node kinds** and **73 stdlib calls** (mostly per-game primitives, climb engines, auction vocabularies); a corpus-covering JS interpreter ≈ a port of ~2,900+ lines of runtime semantics. Not the use case.
- The experiment games are small: Green Lane 27 IR kinds, one stdlib call, no `round`, ~70 lines of hand-written JS engine; Undertow 32 kinds, 3 stdlib calls, one `round` + one library rule. An experiment-class interpreter still needs the expression evaluator, statement executor, phase driver, rules engine, trick mechanic, visibility — **1.5–2.5k lines of JS** vs **~100–250 per hand-ported engine**: a 10–20× multiple that pays only across many games.
- The IR is a sidecar today (runtime and adapter consume the checked AST; IR fidelity pinned only by goldens). A JS IR-walker would be the first *executing* consumer — a second semantic seam that would itself need differential gating. **Fixtures are the floor under every option.**
- The hybrid "generate legality from IR" still requires ~60% of the interpreter (expressions + rules engine) and misses that for some games the *effects* are the substance. Fixtures cover both halves uniformly.
- What survives from the hybrid: a tiny exporter emitting the action-id/label table, deck composition, ranking order, choose ceilings, move-type names — JS consumes these as constants, eliminating the transcription-drift class at near-zero cost.
- Doctrine: one shipped artifact today; the fixture format has two-instance demand (both experiments will carry artifacts) and promotes now; the interpreter has zero instances of demonstrated recurring cost. **Trigger to revisit**: the third artifact-bearing game, or the first fixture-escaping rules divergence in a shipped artifact, or the first engine port exceeding ~500 lines.

Fixture strength requirements: exhaustive full-tree fixtures whenever the census fits; otherwise random **plus** solver-policy-driven traces; per-step legal *sets* and labels; per-player view projections (information handling is diffed, not assumed); one-command regeneration with provenance.

## Opponent-kit specifics

Common substrate: every opponent's Python twin runs against the adapter via `lab/arena.py`; every JS port passes a parity or reload gate before `build_artifact` stamps the page.

**(a) Exported tabular policy** (small games only): inputs = exact-tier average policy + census + reachable-infoset list; canonical key = player + own view projection + rendered own-choice history (never the runtime infostate string); injectivity asserted at export; JS `tabular.js` with loud counted uniform fallback (zero hits required on exhaustive fixtures); measured claim = reloaded-table exploitability + arena vs uniform, printed in the artifact footer.

**(b) Solver-informed parametric heuristic**: inputs = equilibrium marginals / opening books + the naive-grid floor + sweep lessons; Python twin mandatory (`opponent.py`, explicit parameters, tuned by arena sweeps); benchmark = deviation loss vs equilibrium AND vs exact best response (exact tier) or arena vs MCCFR-strong/random (probe tier); JS `heuristic.js` = pure `(view, params, prngFloat) → distribution` with params as generated JSON; parity gate on K exported decision points. (The shipped Green Lane officer has no Python twin or measured claim yet — the P2 retrofit closes that.)

**(c) Determinized Monte Carlo / PIMC** (hidden-deal games): needs the fixture-proven JS engine + parameters chosen by benchmark; consistent-world sampler (unseen cards, hand counts, voids from failure-to-follow, reveals); Python benchmark replays sampled worlds through the real runtime via prescribed shuffles (valid exactly for shuffle-only games; loud wall otherwise); arena vs random / heuristic / trained MCCFR; JS parity on sampler outputs + sampler-soundness property tests; latency budget <~1s/decision in the test page.

**(d) LLM by relay**: inputs = per-state opponent-view projections + action label table + log-line vocabulary; JS `relay.js` renders a structured `briefingData` (pronoun flip in the renderer, never the data) and parses replies with legality validation; measured claim is **faithfulness, not strength** — briefingData equals the fixture's view projection byte-for-byte at every decision; round-trip totality over every legal action; a no-leak assertion that briefingData reads only `view(state, opponent)`.

## Risks and open questions — each with its cheapest probe

1. **Canonical-key injectivity for tabular export** — probe: compute the candidate key for all 144 solved Green Lane mini infosets, diff against the runtime partition (minutes).
2. **Observation-delta classifier for generalized proofs** — probe: implement and compare against `is_ship_node` on Green Lane; must classify nothing concealed at Undertow's public trick plays.
3. **Fixture size with `--views`** — probe: export 50 Undertow traces with views, measure; set cap/compression + commit policy.
4. **JS/Python float parity** — probe: 100 random officer-formula evaluations in node vs CPython, compare bit patterns.
5. **PIMC forced-deal wall** — probe: an instrumented `Random` counting draw sites per game (doubles as the wall's implementation).
6. **Exploitability acceptance envelope** (constant-sum vs general-sum) — probe: one-line check of stock `exploitability` vs `nash_conv` on toys; pin which metric each tier reports.
7. **Node in CI** — probe: confirm runner availability once; test is `skipif` node absent either way.
8. **Proof-harness duplication** (`lab/proofs.py` vs `tests/openspiel_ready/harness.py`) — deliberate for now; probe: after P1, list actually-shared signatures; ≥3 copies fires the promotion ledger.
