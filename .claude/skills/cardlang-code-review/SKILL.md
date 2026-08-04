---
name: cardlang-code-review
description: Use for ANY code review in this repository — reviewing a branch, a PR, a diff, or uncommitted changes. Replaces the generic code-review angle set with angles derived from this repo's pipeline (grammar → parse → resolve → typecheck → IR → runtime → OpenSpiel) and its named defect classes. If the generic /code-review command is invoked in this repo, use this skill's severity order and finder angles as the angle set; keep the generic command's phase structure and output contract.
---

# Cardlang code review

This repo is a language implementation, and a language's worst bugs are not
crashes — they are wrong meanings delivered confidently. A crash reaches a
designer as a bug report; a silent misread reaches them as a wrong game they
trust. Generic review angles are tuned for crashes and null derefs; run
head-to-head against a pipeline-aware review of the same branch, they found
line-level items but missed every misparse and every cross-context guard hole —
the highest-severity classes here, visible only by *running* the pipeline and
tracing constructs *across* layers. This skill encodes those two motions.

## Severity order (project-specific — this inverts generic ranking)

Rank findings in this order. The silent classes outrank crash bugs because a
loud failure is the system working; silence is the enemy.

1. **Misparse** — a legal-looking sentence parses to a different meaning than
   it plainly reads (e.g. an `or`-delimited default absorbing part of the
   predicate). No error ever fires; the designer gets a different game.
2. **Accepted-but-ignored** — a clause parses and no layer honors it
   (decisions.md "Surface totality").
3. **Silently-false** — typechecks clean but is unsatisfiable or vacuous at
   runtime: cross-enum comparison, a string literal never validated against
   its domain, a `TAny` leak past a guard, a predicate checked without its
   binder's type bound.
4. **Vacuously-green** — a test or check presented as a guarantee that cannot
   fail: an assertion loop over nodes a retired construct can no longer
   produce, a ledger row with no pinning test (decisions.md "Closed-domain
   completeness").
5. **Wrong-currency failure** — the right rejection in the wrong shape or
   layer: a raw lark/Python exception where a located, bag-collected
   diagnostic belongs; a bare `assert`; a runtime crash for a statically
   checkable error; a diagnostic that directs the user to syntax the grammar
   cannot accept.
6. **Registry drift** — a closed domain (binder-introducing nodes, Card
   fields, iteration roles, enum value sources) enumerated at two or more
   sites with nothing pinning them equal.
7. **Crash-path correctness** — the generic bug classes. Real, but loud.
8. **Message/spec drift** — diagnostics or docs teaching retired spellings;
   corpus games out of lockstep (CLAUDE.md operating rules 1–2).
9. **Cleanup** — reuse / simplification / efficiency.

Reachability (decisions.md, "Reachability ranks the work") orders findings
*within* a class and tempers the order across classes: an R4 finding of
any silent class ranks below an R2 finding of any class at all. The
severity inversion this prevents is real — a vacuously-green pin over
scaffolding outranking a designer-reachable crash reads as rigor and
allocates backwards.

## Phase 0 — Scope, classify, and gate on artifacts

1. Gather the diff: `git diff main...HEAD` (or upstream range), plus
   `git diff HEAD` if the working tree is dirty.
2. Classify which layers it touches: grammar (`.lark`), parse builders, AST
   nodes, resolve, typecheck, IR, runtime (`evaluate`/`execute`/`driver`/
   `state`), stdlib (`rules.cardlang`, registries), `docs/games/` corpus,
   docs prose, tests/goldens. The classification selects the conditional
   angles below — do not run angles whose trigger the diff does not match.
3. **Artifact gate — run before any finder.** If the diff adds or extends
   grammar surface, a checker Owner Guard or diagnostic, a stdlib registry, or any
   closed-domain mechanism (the `surface-totality-audit` trigger) — including
   a diff that ANSWERS AN EARLIER FINDING on one, which must additionally
   carry that skill's **class ledger** showing the finding was swept as a
   class rather than patched as an instance — the change
   must ship that skill's artifacts: the **grid** (the crossed coverage
   domain as an executable parametrized test — axes derived in code, born
   red before the implementation), misuse-probe **rejection tests**, and
   the **completeness ledger** (judgment columns in the grid module's
   docstring). Absence of any is a severity-2 finding reported first —
   never a below-the-fold conventions note. When the artifacts exist, use
   them:
   - **Run the grid against the merge base — with the HEAD-derived cell
     set.** Derive the cell list on the proposed tree and carry it to the
     merge-base worktree as data; never let the base re-derive it (a
     change that ADDS a production or registry member would have its new
     cells silently vanish from the base's derivation — the gate would
     then under-report the delta or misread an absent cell as a green
     one). The delta is the cells that fail on the base PLUS the cells
     that cannot exist there (added cells); classify each failure before
     counting it — an outcome-mismatch (the cell's own assertion) is
     delta, while an ERROR is either an added cell failing to construct
     (delta) or a grid defect (class 4), never silently assumed to be
     the former. Diff that set against what the change claims. An unclaimed flip is a finding (class 3 —
     behavior changed silently); a claimed flip whose cell RUNS green on
     the base means the grid does not reach the behavior (class 4) — an
     added cell is part of the delta, never evidence of vacuity.
   - **Check each axis is derived, not hand-listed.** A hand-listed axis is
     the tell the framing check was skipped, and it goes stale silently
     when a parallel branch extends the surface.
   - **Replay `red under:` witnesses per credited CLAIM, not per
     module.** Every guard the ledger credits is a pin with its own
     witness; a module-level witness proves the module can fail, not that
     each credited assertion can — a dead assert hides behind a live
     neighbor. A pin with no named witness, one its named mutation leaves
     green, or one whose witness edits the pin itself (its assertion, its
     expected literal — a fault planted in the test proves nothing about
     the code under guard) is class 4.
   - Take the `residual` rows as the review's priority slice.
   The review checks and samples the artifacts; it never re-derives them,
   and it never substitutes for a missing grid or ledger.

## Phase 1 — Finder angles

Run finders as parallel subagents via the Agent tool, each returning up to 6
candidates with `file`, `line`, one-line `summary`, and a concrete
`failure_scenario`. Pass every candidate with a nameable failure scenario
through to verification — silently dropping half-believed candidates is the
dominant cause of misses.

**Always run:**

- **A. Line-by-line diff scan** (generic; empirically still productive
  here). Read every hunk, then the enclosing function; bugs on unchanged
  lines of a touched function are in scope.
- **B. Silently-false hunter.** For each predicate context the diff touches
  or creates (query `where`, movement/reveal filters, `demands` /
  `applies_when`, `transition_to … where`, aggregation bodies and defaults,
  quantifier bodies), ask three questions: what binds here, what type does
  the checker believe it has, and does the Owner Guard that guards this shape in
  *other* contexts fire in this one? Hunt `TAny` leaks specifically:
  pronoun-rooted members (`action.card.*`), subscripts landing in generic
  postfix positions, and any value that crosses a layer without its type.
  Also hunt unvalidated literals: a string or name compared against a domain
  (ranks, suits, zone names) that no layer checks membership in.
- **C. Failure-currency auditor.** Every new or changed error path: compile
  errors are located, bag-collected diagnostics; runtime errors are typed
  exceptions; no bare `assert` on a user-reachable path; no raw
  lark/Python exception escaping (the `VisitError`-unwrap class — check
  every `transform` call site, not just the one that motivated the unwrap).
  Every new guard passes the write-time triage (decisions.md
  "Closed-domain completeness"): it is an Owner Guard at the owning layer, or a
  Shadow Guard whose comment names the Owner Guard it shadows — a guard that names
  neither is a finding (class 5 or 6) even if the condition it checks is
  true.
  Grep each new diagnostic's quoted syntax against the grammar: a message
  that names a retired spelling, or directs the user to a sentence the
  grammar rejects, is a finding.

**Run when the classification matches:**

- **D. Misparse prober** *(grammar or builder changes)*. Do not reason about
  parses — run them. For each changed production, write probe sentences at
  precedence and adjacency boundaries and parse each with a short script,
  comparing the actual tree/AST shape to the sentence's plain-English
  reading. Mandatory probe shapes: the omitted optional clause **with an
  absorbing operand** (the remaining text contains the boundary token at top
  level, so the parser has something to misread — truncation-only probes
  test the error path, not the misread); boundary-token doubling; the
  `or`/`where`/`:` shared-delimiter splits; singular/plural noun swaps.
  Re-run the explicit-ambiguity count (`ambiguity="explicit"`, count
  `_ambig` nodes). Attach parse output to every candidate.
- **E. Construct-row tracer** *(grammar or AST changes)*. For each new or
  changed construct, walk its full row: grammar → builder → AST node →
  resolve (binder registration, name classification) → typecheck (infer
  *and* check, in every predicate context) → IR arm → runtime arm → tests.
  A missing cell is an accepted-but-ignored candidate. Derive the row's
  checklist from the Expr/Stmt unions and the `assert_never` dispatches, not
  from the diff.
- **F. Registry-drift sweeper** *(any enumeration in the diff)*. For each
  closed domain the diff touches, grep ALL its definition sites and diff
  them. Two sites without a pin is a finding even if they are currently
  equal — the defect is the missing pin, not the current values. A change
  that gives an existing domain a second definition source (a derived
  namespace beside a declared list) must show its reconciliation check;
  absence is a finding. The same class covers re-derivation: a downstream
  site that recomputes a fact an earlier pass established (re-classifying
  a name instead of reading `ref_kind`, re-inferring a type, re-computing
  a zone projection) is a finding even while its answer is currently
  correct — the two computations will drift.
- **G. Test-integrity auditor** *(test, golden, or construct-retiring
  changes)*. Hunt vacuous tests: assertion loops whose trigger condition a
  retired construct can no longer produce, guards over deleted grammar,
  tests green by construction. A pin born green must name its reddening
  mutation (`red under:` in its docstring, per the surface-totality-audit);
  no witness, or a witness that leaves the pin green when replayed, is
  class 4. A retirement creates vacuous guards **at a
  distance**: for every construct the diff deletes (grammar production, AST
  node, registry entry), grep the whole test suite for tests conditioned on
  it — a guard whose trigger can no longer occur is vacuously green even
  though its file never appears in the diff. Never assert "retired cleanly"
  without this grep.
  Check goldens were verified rather than regenerated-to-match where the
  change claims semantic neutrality (byte-identical trace goldens are the
  proof; regenerated IR goldens need a stated reason). Exact-score tests pin
  `PYTHONHASHSEED`.
- **H. Spec-lockstep sweeper** *(docs or surface changes)*. The corpus
  (`docs/games/`) and every doc table/example use the current register —
  where cheap, parse doc examples rather than eyeballing them. The docs that
  describe a changed surface (decisions.md, library.md, and roadmap.md,
  "Grammar surface deferred by the checker") moved in the same change, and a newly deferred cell got its
  tracker record. No history voice in `docs/` (maintaining.md rule 1).
- **I. Info-set / observation checker** *(movement, visibility,
  decision-site, or adapter changes)*. The change emits per-observer
  observations through declared zone projections; no decision runs outside
  the observation-event stream; `tests/openspiel_ready/` proofs cover the
  touched mechanic or game. A mechanic that runs but derives no info sets is
  incomplete for the OpenSpiel target — report it as such (CLAUDE.md,
  load-bearing section), severity 2.

## Phase 2 — Verify (recall-biased, evidence-hungry)

Dedup near-duplicates, then one verifier per candidate → **CONFIRMED /
PLAUSIBLE / REFUTED**.

- **CONFIRMED requires executed evidence**: a run probe, an actual parse
  tree, a reproduced diagnostic or crash, or a quoted line pair that is
  self-evidently contradictory. Grammar-level claims are never CONFIRMED
  from reading alone — parse the sentence.
- **PLAUSIBLE is the default** for realistic-state claims (rare-but-reachable
  paths, boundary values, cold state). Do not refute for "speculative".
- **REFUTED only constructively**: quote the guard, the type, or the
  invariant that makes the scenario impossible, or show the diff already
  handles it.
- **Sweep at report time.** A CONFIRMED finding that is one cell of a
  crossable product — an axis a registry or the grammar defines — is an
  incomplete finding until the product is crossed: build the small grid and
  report the pattern (which rows, which columns), not the instance.
  Sweep-the-class (decisions.md "Closed-domain completeness") binds the
  reporter, not only the fixer; the cost is minutes, and the alternative is
  a review that certifies one cell of a four-cell defect.

Keep CONFIRMED and PLAUSIBLE; drop REFUTED.

## Output

Rank by the severity order above, at most 15 findings. If the
`ReportFindings` tool is available, report through it; otherwise output the
JSON array (`file`, `line`, `summary`, `failure_scenario`, `verdict`,
`category`, `reaches` — the R1–R4 reachability tag).
State the Phase-0 artifact-gate verdict explicitly (artifacts
present / absent; grid run against the merge base or not; witnesses
replayed or not) even when it produced no finding. List cut findings one line each — a silent cap reads as "covered
everything".

## Effort scaling

- **Quick check**: no subagent fan-out; angles A + B inline over changed
  hunks only; the Phase-0 artifact gate always runs.
- **Standard**: conditional angles per the classification; a typical surface
  change activates 5–6 angles.
- **Thorough**: additionally, one fresh adversarial probe subagent per
  changed surface (given only the surface spec, told to break it), sliced
  one-per-ledger, not one-per-branch. For author-side completeness proof,
  hand off to `surface-totality-audit` — the review samples; the audit
  proves.
- **The tier keys to the delta's side of the scaffolding test**
  (decisions.md, "The machinery is guarded once"): a diff that changes no
  refusal, no runtime step, and no proof obligation caps at **Standard** —
  no adversarial probe subagents, one review round, its findings filed
  with their reachability rather than driven to fix-now. Thorough is
  reserved for deltas a designer, the corpus, or a proof can meet, and a
  request for more on a scaffolding-only diff gets this rule quoted back
  before it gets the subagents.
