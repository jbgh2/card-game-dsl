# Stage 3b: the corpus adopts the `primitives { }` block

Operator go: Ben, 2026-08-29 ("Start on 3b"). This is the plan of record for
epic #142's stage 3 (the corpus sweep). The construct's own plan is
`docs/plans/2026-08-28-primitives-block-stage3a.md`; the adoption test that
precedes this sweep is the Salvo experiment (PR #482), whose review yield —
every defect a namespace seam around the block, none in it — shapes the
per-game recipe below.

## Acceptance criteria (bind every PR in the stage)

1. **Runs** — every migrated game builds and plays under the declared regime.
2. **Regression-clean** — bare `mypy`; CI's three checks; **byte-identical
   per-seed PLAYOUT goldens at FULL WIDTH** for every migrated game
   (`CARDLANG_GOLDEN_SEEDS=full pytest tests/test_migration_characterization.py`),
   verified, never regenerated — neutrality is the claim, and a block that
   moves a playout golden is a defect by definition. The IR goldens are the
   one stated exception: a migrated game's IR gains the block's own nodes, so
   its `tests/golden/*.ir.json` regenerates with that reason quoted (the
   framing check's axis: everything else in the IR is byte-identical).
3. **Info sets derive** — a block is declaration-only surface: no zone, move,
   or observation change; the `tests/openspiel_ready/` proofs stay green
   untouched.

Corpus-lockstep: the migrated `docs/games/*.cardlang` files themselves, plus
`docs/kernel-migration.md` and `docs/design-notes/primitive-sidecars.md`
section 5 status in the same PRs (operating rule 2).

## Gate record (cardlang-planning)

- **Gate 1 (owners):** decisions.md "Closed-domain completeness" governs the
  new guard's write-time triage; "Surface totality" is not tripped (no grammar
  change anywhere in this stage — optional types are already spellable,
  `payload_optional`, proven by an accept/accept/refused-control probe). No
  glossary mints. Ordering: #142 stage 3, operator-started. No Hoyle (no Lane
  A surface). Architect counsel on the two machinery designs attaches to the
  3b-0 PR.
- **Gate 2 (classes):** a resolve Owner Guard + diagnostic (the F1 refusal) —
  audit fires, grid red first; a domain refinement of a rigor-critical
  reconcile pin — same discipline; ten corpus game files; per-game
  `PRIMITIVE_READS` row deletions.
- **Gate 3.5 (reachability):** the stage is R2 (anyone migrating or authoring
  a declaring game meets the block); the F1 defect is R3, confirmed by
  execution in the post-#475 review, and its fix is small.
- **Gate 4:** the framing check runs fresh-context over the definition sources
  before the 3b-0 grids freeze; the grids are authored red before
  implementation. Outcome recorded in the 3b-0 PR.

## The cohort — derived 2026-08-29, not recalled

Derivation: `PRIMITIVE_IMPLEMENTATIONS` (contract per name) x `CALL_SIGS`
(signature spellability against `DECLARABLE_BUILTIN_TYPE_NAMES` + the
`payload_optional` spelling) x the owning game per module.

**Ready (ten):** seven-card-stud, holdem, holdem-heads-up, pinochle, skat,
canasta, tichu, belote, five-hundred, french-tarot — every primitive BUNDLED
or PURE, every signature spellable (optionals included).

**Walled (three, each tracked):** gin-rummy behind issue #472 (`TCollection`
parameters); cribbage behind issue #473 (the SITE_READ pegging scorers); coup
behind the `coup_game_summary` trace-emitter eviction (its own step under
#142).

**Outside the block's scope:** president, big-two, bridge — their only
Primitive couplings are walled-namespace rows (climb queries, the shared
trick winner), which the block deliberately does not cover; they wait on the
co-location stage's declaration slots (#142 stage 4).

## 3b-0 — the wave-clearers (one PR, engine + tests, Lane B)

1. **The F1 refusal** (per the Architect's counsel, option A). A read name
   declared as PHASE-local state and as a zone classifies silently as the
   zone: `classify_read` never consults phase state, and resolve's
   phase-local diagnostic sits in the arm reached only when classification
   fails. Fix: the collision-set predicate lands in `primitives_block.py` as
   the third sibling (phase-local x zone names, plus a phase-carrying helper
   so the diagnostic can name the owning phase), and the REFUSAL lands in
   resolve's reads validation before `classify_read` is consulted —
   `classify_read` itself stays collision-unaware (it is also the loader's
   materialization call, where a refusal could never fire). The grid covers
   the pairwise name-membership product over {game-level state, phase-local
   state, zone family, single zone}, with the monotonicity argument written
   into the ledger (every game-state-carrying vector is owned by the two
   existing arms, and the phase x zone arm's game-level subtraction can only
   hand a name to them, never to acceptance — so pairwise ownership covers
   every multi-membership vector), one
   three-way probe, the phase axis crossed with BOTH zone kinds, self-pair
   cells citing `_check_duplicate_names` as their Owner, and the library
   path's boundary. That boundary is narrower than the counsel's
   "uses-spliced-zone cell", which is not constructible: `?library_item`
   holds no `zones` clause, so no library contributes a zone to any
   collision, and `test_the_collision_namespace_axis_is_derived` reads that
   off the grammar so the day one does, the gap reddens. What a library DOES
   reach is provided STATE — spliced into the game's own `state { }` before
   the block is checked, so a `reads` name classifies against it — and every
   collision between a provided name and a game's own declaration is refused
   upstream by `_apply_uses`'s own Owner Guards. The diagnostic's
   message is pinned in the blessed-snapshot rejection harness; the grid
   module's over-crediting ledger sentence is corrected to the guard's new
   truth; `primitives_block.py`'s Contract Establishes clause gains the read
   classification it currently leaves to a function docstring.
2. **The dual-definition pin's grain** (per the Architect's counsel: the
   consumer-derived ROW exemption; module-membership is REJECTED on the
   tichu counterexample — `runtime/tichu.py` implements both a call
   primitive and the walled climb queries, and `climb_row` binds its row at
   import, so a module-grain pin false-fires on batch C and deleting the row
   kills the climb machinery at load). Claim (3) quantifies per row: a
   declared game's row is refused unless the walled binders bind it —
   derived as the climb binder's own answers plus the shared dispatch
   module's rows (`runtime/primitives.py`: the three auction-outcome rows
   and cribbage's pegging call sites; there is NO shared trick winner — that
   registry is empty), the latter backed by an assert that no
   implementation-index entry names that module. `_reconcile` takes the rows
   table as a parameter (its docstring already claims it does). Three
   plants, all run in 3b-0: coexistence still caught; the exemption exempts
   something (the real pinochle auction row + a declared pinochle);
   the tichu climb cell, with the exemption's climb half named as the
   reddening mutation. The existing dual-site red-under plants a GAME and
   would fail loudly mid-wave — it converts to row-plant form here.
3. **The declared path's failure channel** (framing check, headline 1). An
   entry whose `reads` under-declares what its implementation consults
   checks clean and dies mid-playout as a bare `KeyError` from the
   `GameReads` bundle — violating `reads.py`'s own Contract ("never a bare
   `KeyError`"), which the legacy accessors keep. R2 for the wave: every
   hand-authored block can under-declare. Fix: the declared-path bundle
   refuses an absent key in the typed channel, naming the primitive, the
   missing name, and the declaration to extend. Artifacts: a red test per
   bundle half (state and families), the Contract line made true.
4. **De-couple `tests/test_primitive_narrowing.py` from live rows** (framing
   check, list 3): `_bundle_row()` hard-codes skat's row (batch A deletes
   it → loud StopIteration mid-wave), and the kind-coverage guard is
   conditional on rows carrying each field, so deletions can silently
   retire probe kinds. Convert to synthetic rows or a stability-guaranteed
   source before batch A.
5. **The post-#475 residuals, batched here by the operator's stage-3b call:**
   the `_collidable_native_registries` candidates claim made true (derived,
   or honestly stated hand-written with its completeness argument); the
   review's prose-register findings re-derived over the 3a delta and fixed;
   `ambiguous_read_names` hoisted out of the per-read loop.
6. **Issues filed for the framing check's unpinned axes that this stage does
   not close** (record-and-file per Gate 3.5, not fixes): the library-tier
   function-shadow asymmetry; a game's block reading library-PROVIDED state
   (a cross-file coupling nothing pins through a library rename); a zone or
   state variable silently coexisting with a declared entry's name; the
   `CALL_SIGS`-absent shape-skip in typecheck (unreachable until the
   closing PR deletes the Primitive half — that PR's stated obligation).
   Slot-position regime-blindness is already #142 stage-4 scope and needs
   no new issue.

## The wave — three PRs, each gated on 3b-0

Per-game recipe (the Salvo seam playbook plus the framing check's yield, now
doctrine for this stage):

1. Derive the game's primitive CALL SITES from its own body — the framing
   check proved a library-originated primitive call is impossible by two
   independent walls (no `primitives_block` in the library grammar; the
   library-alone encapsulation sweep), so the block declares exactly the
   names the game body calls, no more (a declared-but-uncalled name keeps
   dead Python alive: the reconcile counts declared names as reached).
2. Author the block to match `implementation_sig` exactly and the reads to
   match the game's `PRIMITIVE_READS` row content. First verify no row name
   is phase-local-only (the authored-row pin tolerates what a block's reads
   refuse — a game hitting that asymmetry is a stop-and-report, not a
   workaround).
3. Delete the game's CALL-NAMESPACE row **and, in the same change, the
   runtime module's import-time `ROW = reads.row(...)` binding and its
   legacy dispatch arm's row wiring** — the binding executes at import, so
   a deleted row with a surviving binding crashes the module for BOTH
   regimes, and `tests/test_primitive_reads.py`'s module-source scan is the
   pin that forces the coupled edit. A row the walled binders bind SURVIVES
   the migration, and the narrowed pin is what says so checkably (tichu's
   climb row outlives its block; pinochle's and french-tarot's auction rows
   outlive theirs).
4. Sweep consumer registries for every moving name (the derived readers pin
   covers `RANKING_GATED_FUNCS`; sibling-query the rest).
5. Run the full-width byte-identical playout-golden proof; regenerate the
   game's IR golden with the block-nodes reason stated; move the
   kernel-migration status line.

- **Batch A:** seven-card-stud, holdem, holdem-heads-up, skat, five-hundred.
- **Batch B:** pinochle, french-tarot, belote (pinochle and french-tarot
  carry surviving auction rows — the day-one exercise of 3b-0's pin grain;
  belote carries none).
- **Batch C:** canasta, tichu (the fat read rows; canasta's bare-family
  reads; tichu is the game whose row survives for the CLIMB binders — the
  carve-out the narrowed pin encodes).

Proving artifact per game: the quoted full-width byte-identical run, and the
corpus reconcile pin green (its domain covers every corpus game by glob).

## Closing steps, gated — recorded here so the end state is one place

- gin (#472), cribbage (#473), coup (the eviction): one PR each, when its
  wall falls.
- The legacy-table deletion that ticks #142's stage-3 box: `PRIMITIVE_READS`
  loses its last call-namespace row with batch C; the Primitive half of
  `CALL_SIGS` is deleted and the signature moves to a column on
  `PRIMITIVE_IMPLEMENTATIONS` (`implementation_sig` is the designed one-site
  change) only after the three walls fall — the box is the operator's tick,
  on full elimination, never on the wave alone.

## The Architect's counsel (2026-08-29, attached per docs/harness.md "The Architect")

**Headnote.** Two machinery rulings, both narrower than asked. First: the phase-state-versus-zone collision is real — a probe game checks clean today and classifies the colliding name as the zone — and the fix is a compile refusal in the resolver's diagnostic channel, with the new collision set stated in the leaf classification module beside its two siblings; refusing inside the classifier itself is rejected, because the classifier is also called after validation by the loader, where such a refusal could never fire. The pairwise domain over the four name namespaces is the right statement: a third membership never un-refuses a name, so one three-way probe suffices, and the within-namespace duplicate cells already have their owner in the duplicate-name guard — settled law also says cross-level shadowing is legal at declaration level, so the refusal must stay at the reads clause and no wider. Second: the pin refinement the plan proposed — count only rows whose module implements a call primitive — is rejected on a derived counterexample, not a hypothetical: exactly 1 of the 14 implementation modules both implements a call primitive and is a climb home (tichu), its row is what the climb binder imports at load, and tichu is in the migration cohort — under the proposed grain its surviving row false-fires the pin, and deleting the row to appease the pin crashes the climb machinery at load. Recommended instead: exempt exactly the rows the walled binders bind, derived by asking the binders — the climb binder's own answers plus the shared dispatch module's rows, the latter guarded by an assert that the shared module implements no call primitive — at row grain, not game grain, with the reconcile taking its rows table as a parameter so both red-under directions actually plant. Newly required for migrating agents: tichu's row survives its migration, and every batch-B and batch-C PR meets a pin that permits precisely the walled survivors and nothing else. Facts the plan's first draft did not state: there is no shared trick winner (that registry is empty; the survivors are three auction-outcome rows and one pegging-scorer row), belote carries no surviving walled row, the existing dual-site red-under dies loudly mid-wave unless converted now, and the leaf module's contract does not yet claim the read classification this fix leans on. Info sets do not move — both designs are compile-time and test machinery.

**1. The decision.** Not "is F1 a defect" (confirmed by execution: a game declaring `pot` as a zone and as phase-local state, with a `primitives` entry reading `pot`, passes `check_dsl` clean and classifies the read `SINGLE_ZONE`). The choices actually at stake: (a) which module states the phase-state x zone collision set, and which layer refuses it — specifically whether `classify_read` itself may refuse; (b) whether the pairwise membership product over {game-level state, phase-local state, zone family, single zone} is the whole domain; (c) the discriminator that lets claim (3) keep refusing dual definition sites while the walled-namespace rows legitimately outlive a game's block — module-membership, an authored row field, or a consumer-derived exemption — and the red-under that keeps the narrowed claim trusted.

**2. The law.** decisions.md "Closed-domain completeness" binds three ways: write-time triage — the owning pass's Contract decides where a check belongs; the channel law — compile stages fail as `DiagnosticBag` diagnostics with a span, and "a raw registry raise mid-resolve is loud in the wrong channel"; and the enforcement ladder — a fact derived from one defining site so a second copy cannot exist outranks an authored copy, and a pin's ledger says why the fact cannot live a rung higher. resolve's Contract: it is the ONLY pass that classifies names; downstream dispatches on the classification, never re-derives it. `primitives_block.py`'s Contract: a leaf of the front end, names and classifications only, whose facts "hold before resolve has validated anything" — its Establishes clause names the regime and the implementation index but NOT the read classification, which only `classify_read`'s docstring claims; the fix extends that Contract line in the same change. `_check_duplicate_names`' own docstring settles the level: scopes that legitimately shadow ACROSS levels are separate namespaces and stay legal; duplication is rejected only WITHIN one declaration list — so a declaration-level refusal of the collision would re-litigate settled law, and the class is reads-clause-level, where one flat name namespace merges what the game's own syntax keeps apart. `reads.py`'s Contract: name-keyed reads fail as typed `PrimitiveReadError`, and the rows are pinned both ways by `tests/test_primitive_reads.py` — content drift of a surviving row stays that test's duty, not claim (3)'s. The grid module's ledger property (4) currently over-credits; the prose register requires correcting it to the guard's new truth in the same change.

**3. Precedent.** P2: facts materialize in the owning pass and are never re-derived downstream — the collision sets are name facts the leaf owns; the refusal is the resolver's. P6: a rejection test that does not pin the message tests half the diagnostic — the F1 rejection fixture lands in the blessed-snapshot harness. P7: the failure channel is addressee, span, applicability — the diagnostic names the declaring phase because the addressee is a designer who must find it; the walk behind `phase_local_state_names` drops the owning phase, so a phase-carrying helper is part of the fix. P9: one source, every scrape derived and pinned — the walled-row exemption derives from the binders rather than being authored a second time. P11: a reconciliation pin is trusted only after it has caught a planted fault — both directions of the narrowed claim plant, and the pin never calls the code it judges (it reads the climb binder, which is the judged state's consumer, not the judged artifact; the distinction is stated in the ledger, not assumed).

**4. The options.** *F1's placement.* A (counseled): predicate in the leaf, refusal in resolve — `primitives_block.py` gains the third sibling (phase-local x zone names, disjoint from both existing siblings by construction since it excludes game-level state) plus a phase-carrying helper; `_check_primitive_reads` gains the third refusal arm before `classify_read` is consulted, hoisted alongside the `ambiguous_read_names` hoist the same PR performs; `classify_read` stays collision-unaware; `ReadKind` remains exactly the driver's materializable closed domain. B (rejected): refuse inside `classify_read` — called twice (resolve validates, loader materializes); at the loader a refusal is a guard that cannot fire, at resolve a raise in the wrong channel, and it would split "classifiable" from "materializable" inside one closed domain. C (rejected): declaration-level game-wide refusal — re-litigates settled cross-level shadowing law and over-refuses. *The domain statement.* Pairwise is right, with the completeness argument stated: each pairwise predicate is a set intersection, so membership in a third namespace never removes a name from a refusing pair — refusal is monotone, and pairwise coverage covers every 2-plus membership vector. The grid carries the three cross-level pairs (phase axis crossed with BOTH zone kinds), one three-way probe pinning "at least one arm speaks", self-pair rows citing `_check_duplicate_names` as Owner rather than re-covering, and one uses-spliced-zone cell — `_check_primitives_block` runs after `_apply_uses`, so library-contributed zones are in the collision domain, and the second library path is historically the under-contracted one. *The pin's grain.* A (counseled): consumer-derived row exemption — claim (3) quantifies per ROW; a declared game's row is refused unless it is one of the rows the walled binders bind, derived as the climb binder's own answers over the two climb registries union the shared dispatch module's rows, the latter backed by an assert that no implementation-index entry names that module (a call primitive later landing there reddens the pin instead of silently widening the exemption); `_reconcile` takes the rows table as a parameter. Cost, honestly: the pin's domain depends on one runtime binder's answers; a climb-binder mis-binding reshapes the exemption silently — the ledger's does-not-prove line says so, and the climb machinery's own tests own that fault. B (rejected — the plan's first proposal): module-membership — fails on the tichu counterexample above. C (rejected): the row carries its namespace as a field — derivable from the consumers, so the field is a second copy on a lower enforcement rung, hand-edited per migration PR, and its drift check is this pin again with an extra table. *The red-under.* Three plants, all runnable in 3b-0: (i) coexistence still caught — a planted call-namespace row keyed to the declared witness game's module must refuse; (ii) the narrowing is load-bearing — the real shared-module pinochle row plus a declared game named as pinochle passes the narrowed claim while the unnarrowed membership set is asserted non-empty on that state; (iii) the climb cell — tichu's real row plus a declared game named as tichu passes, and removing the climb half of the exemption is the named reddening mutation. The existing dual-site red-under plants a GAME because rows cannot currently be planted; it converts to row-plant form now.

**5. What becomes illegal after.** resolve newly establishes that every classified reads name is unambiguous across all four name namespaces — a colliding name never reaches classification, so the loader's `classify_read` calls meet only single-membership names; the grid ledger's property sentence becomes true as written. `primitives_block` newly claims, in its Contract's Establishes clause, the ONE classification of reads names and its collision predicates; illegal after: any consumer testing name membership against the state/zone walks itself. The reconcile pin newly quantifies per row; illegal after: a declared game's row that no walled binder binds, and — via the backing assert — a call implementation registered in the shared dispatch module. The per-game recipe's "delete that row" step becomes conditional for the first time: tichu's row survives its own migration, and the pin is what says so checkably. Nothing changes in any runtime pass Contract.

**6. Counsel.** For: both rulings are the house doctrine executed — the collision refusal lands in the pass whose Contract owns name validity, speaks the designer's channel with a span and the phase's name, and its predicates sit beside the two siblings whose rationale it completes; the pin exemption derives from the defining consumers so no second authored statement exists to drift, and the narrowed claim keeps a checkable coexistence window through all three batches. Against, strongest: the exemption couples a front-end test's domain to a runtime binder's behavior — the pin becomes wrong exactly when the binder is, and green then proves less than it reads; the mitigation is the non-vacuity plant plus stating the dependence in the ledger, not more machinery. What the Architect would do: land F1 as option A with the message pinned in the blessed-snapshot harness and the monotonicity argument written into the grid ledger; take the consumer-derived row exemption with rows parameterized and all three plants demonstrated; correct the plan's two factual labels in the same PR; and put one sentence in the PR body naming tichu's carve-out so the batch-C agent inherits a rule, not a surprise.
