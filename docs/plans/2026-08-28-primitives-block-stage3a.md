# Plan: the `primitives { }` block — sidecar stage 3a

Epic #142, stage 3 of `docs/design-notes/primitive-sidecars.md` section 5,
split 3a/3b (ratified 2026-08-28). 3a lands the block, the both-ways
checks, the derivation, and the coexistence pin, with ZERO corpus game
files moving; 3b (separate change) sweeps the corpus and deletes the
legacy tables. Implementation is dispatched to an Opus worktree agent;
this plan and its two counsel blocks are the brief's contract.

## Gate 1 — owners

- Settled: decisions.md "Surface totality", "Closed-domain completeness"
  (the dual-definition-site rule governs the coexistence window);
  operating rule 2 (lockstep) — vacuous in 3a by design, binding in 3b.
- Named: glossary [[primitive]], [[primitive-bundle]] (which already
  records "becomes a NamedTuple when the sidecar design lands" — 3a
  redeems that line), [[native-code]], [[builtins]]. New surface words
  (`primitives`, `reads`) mint or extend glossary entries in the change.
- Sequenced: epic #142 (this is its first unchecked box); #364's defect
  class (cross-game primitive leakage) closes as a consequence; #158's
  freeze-cost lever (per-primitive reads) is enabled but NOT fixed here.
- Sketched: primitive-sidecars.md sections 2 and 5 (this change edits
  §2's `->` sketch to the counseled colon form, and §5 to the 3a/3b
  split, in lockstep); primitive-inventory.md (the ledger is the
  witness list; its "sidecar relocation: orthogonal, immediate" line is
  the sequencing authority).
- Surface: Hoyle's counsel below. Engine-structural: the Architect's
  counsel below. Both attach to the PR.

## Gate 2 — classification

Grammar surface + parse builder + AST + resolve + typecheck + native
registry (derivation) + tests. Audit-triggering on two closed domains
(the block's surface; the primitive registry's definition site). Gate 4
applies; the grid is authored red before implementation.

## Gate 3 — acceptance criteria

1. Runs: a fixture game declaring a primitive plays through the runtime;
   `check_dsl` accepts the block and rejects each misuse probe loudly.
2. Regression-clean: bare `mypy`, full `pytest -q`; **byte-identical
   goldens** — 3a changes no behavior for any existing game (the
   declarations regime has no corpus members yet).
3. Info sets derive: 3a emits no new observations and moves none — the
   reads clause makes Python's hidden-zone reads *declared and visible*,
   and the derived-reveal analysis (a hidden read flowing into public
   state implies a reveal) is recorded follow-on in the epic, not
   silently absent.

Corpus-lockstep list for 3a: **empty by construction** (the coexistence
pin makes "undeclared game" a checked regime). Witness: a minimal
fixture game under tests/ declaring and calling one primitive
(plan step, not a hope); Salvo (experiment tier) is the first real
adopter the moment 3a lands, ahead of 3b.

## Gate 3.5 — reachability

R2: every agent or designer adding a game with game-local Python meets
the three-table hand-edit today, and #364 shows the current resolution
already misroutes a real cross-game case. The work executes a ratified,
operator-sequenced plan (not proportionality-checked afresh per stage —
the epic carries the authority; this stage is the epic's named remainder).

## Gate 4 — audit step 1: the framing-check enumeration is the
## authoritative domain

The fresh-context framing check (run at planning, definition sources
only) produced the 26-axis enumeration reproduced in the appendix
below; it supersedes the plan author's provisional six axes, and the
grid derives from IT. Where the two enumerations disagreed, the
framing check won on the merits each time; the material corrections
and their plan resolutions:

- **The regime is namespace-scoped, not game-scoped** (axis 12). The
  block covers the CALL-position namespace (`PRIMITIVE_CALL_FUNCS`)
  only; the other five primitive namespaces (auction outcomes, climb
  leads/follows, early predicates, trick winners) stay wholly legacy
  in 3a regardless of block presence. The resolve-stamped regime and
  the reconciliation pin quantify over the call namespace; the other
  five are grid rows proving the block CANNOT name them (Hoyle's
  wall), each citing the epic's stage-4 box.
- **Bare family reads are legal** (axis 8): `reads hand` grants the
  whole family (Canasta's and Coup's real need); `reads hand[p]`
  narrows to the binder's instance. This corrects one of Hoyle's
  probes: the misuse cell is the UNDECLARED binder (`hand[q]`), not
  the bare family. Binder domains include position domains, not only
  players (axis 9).
- **The spellable type set excludes `TAny`, `TNull`, `TOutcome`,
  `TStruct`, `TLine`, `TDir`** (axes 5, 18). Declared types drive
  `coerce_args` freezing, and `TAny` hands implementations raw
  objects — designer-unreachable by construction in 3a, with the
  ledger recording which legacy signatures therefore cannot migrate
  until typed properly (that is 3b's problem to surface, not
  silently absorb). `tests/test_native_call_boundary.py`'s pinned
  set gains the probe proving the block cannot reach it.
- **Zero-arg entries are legal** (axis 6) — real members exist.
- **Empty block and absent block are distinct states** (axis 2), the
  `trick_order` presence-partition template; a `library { }` carrying
  a primitives block is statically refused (axis 1).
- **Two instruments' premises are falsified and re-argued in the
  change** (axes 23, 24): `resolve._LIBRARY_UNSWEPT["primitive_query"]`'s
  "closed: identical either side" reason dies with game-local
  declarations — the sweep row reopens with a real check or a new
  honest reason; the rename-metamorphic oracle currently derives its
  coupled-name exclusions from `PRIMITIVE_READS`, and a game-file
  declaration makes the coupling structural — the oracle re-points at
  the declaration AST, and the ledger records what it can no longer
  catch and why that is now enforced by construction.
- **Partition totality** (axis 19): the trick-order row partition's
  "every `PRIMITIVE_CALL_FUNCS` member is uncallable by construction"
  argument must be re-established over declared names or the
  partition test extended — a named grid row, never a silent premise.
- **Codec-needing call positions** (axis 20): a declared primitive in
  `where jointly` meets the existing loud `ActionSpace` guard; the
  cell is covered by a probe proving the guard fires, with the
  Python-side codec registry recorded as the pairing obligation.
- **Dual game-file forms** (axis 25): the derivation reads the same
  extraction path the pipeline reads; a fixture with `.md`/`.cardlang`
  disagreement is a probe, not an assumption.
- **Census trips** (axis 26): every new module lands its census rows
  in the same change, and every new test module imports pyspiel-free
  at collection (the recorded trap).

Misuse probes (updated per the corrections): `= 0` default on an
entry; `reads hand[q]` with an undeclared binder; declaring a
Builtin's name; duplicate entries / second block; calling a neighbor
game's primitive (#364); a round-slot name in the block; `TAny`
spelled as a declared type; a primitives block inside `library { }`.
Each proves loud in its layer's failure currency, with the
red-under-plant verified per doctrine.

## Gate 5 — steps, each with its proving artifact

1. Grid authored red from the diffed axes — `xfail(strict=True)` cells
   in the new grid module (artifact: the red run).
2. Grammar + parse builder for the block (artifact: parse goldens +
   keyword-fusion sweep green over the new `_PRIMITIVES_KW`/`_READS_KW`).
3. Resolve + typecheck: both-ways checks, reads validation, call-site
   checking against declarations (artifact: grid rows green; rejection
   fixtures with spans).
4. Derivation: registry/signatures/dispatch materialized from
   declarations; coexistence pin (artifact: the reconciliation test the
   Architect's counsel names; legacy behavior byte-identical).
5. Per-primitive reads → bundle mechanics per the Architect's counsel
   (artifact: narrowing wall stays green; PrimitiveReadError probes).
6. Witness fixture game end-to-end (artifact: runtime playout test).
7. Ledger in the grid module docstring; sidecars-note §2/§5 and glossary
   edits in the same change (artifact: the docs diff).
8. Gates: bare mypy, full pytest, audit re-check before commit.

Deferred with records: derived-reveal analysis (epic #142 checkbox);
round-slot declaration slots (stage 4); the corpus sweep and legacy
deletion (3b, its own plan).

## Hoyle's counsel

**Headnote.** The recommended sentence, verbatim:
`pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit` —
an entry row of a `primitives { }` block sitting inside the game block
beside `uses`. The losing rival: the sentence form
`pinochle_meld_value(p : Player) gives Integer, reading hand[p]` —
declaration rows in this language are colon-rows, not sentences, and
`gives` would mint a keyword no witness forces. Merge Lane A: the
grammar widens by one block production and two anchored keywords.
Corpus: zero game files move in 3a; 3b sweeps the primitive-using
games named in the inventory ledger. One prior sketch is cut against
and edited in lockstep: the sidecars note's own `->` arrow, foreign to
a surface that has never used one. Info sets: nothing moves — the
clause DECLARES hidden reads that today happen invisibly, and the
reveal-derivation follow-on is recorded in the epic. Bottom line:
adopt the colon form and the beside-`uses` placement; the strongest
against is the coexistence window itself — a live dual-definition
domain — priced by making the regime axis first-class grid rows and
scheduling 3b promptly; the operator approves the sentence and the
window, and merges at the end.

1. **The sentences.** In situ:

   ```text
   game Pinochle {
     players: 4
     ...
     uses trick_conventions
     primitives {
       pinochle_meld_value(p : Player) : Integer
           reads hand[p], trump_suit
     }
     zones { ... }
   ```

   Salvo's stage-5 entry, the next witness:
   `salvo_combos(p : Player, loc : Integer) : Integer reads army_a[p], army_b[p], army_c[p], location_a, location_b, location_c`.
   Alternatives weighed: (B) the `gives … reading …` sentence form —
   reads aloud more warmly, but every declaration in this language is a
   colon-row (`zones`, `state`, `card_points`, `require`), and the
   block is a declaration; (C) the sketch's `-> Integer` — an arrow is
   foreign to the entire surface and stillborn. Shared-delimiter
   hazards for the prober: the comma serves both the param list and the
   reads list across the `)` boundary; `: Integer reads` must not
   absorb a state-row's `= default`; an index binder in reads must
   resolve to a declared parameter of the same entry.

2. **Precedent.** Extends: the colon-row declaration register; typed
   params from `move_type name(dst : column)` and
   `function dist(c : Card, …)`; the `uses` block as the import-tier
   sibling (game_item). The reads vocabulary is already the term of
   art (`PrimitiveReads`, `GameReads` — glossary [[primitive-bundle]]).
   Reserved words clean: neither `primitives` nor `reads` collides;
   both follow the `_<WORD>_KW` anchoring discipline, proven by the
   keyword-fusion sweep. Cuts against: only the sidecars note's own
   arrow sketch, edited in lockstep.

3. **Corpus impact.** 3a: zero files; the witness fixture plus Salvo
   (experiment) carry the construct. Forced by: epic #142's named
   remainder, defect #364 (a game-local trick winner named in another
   game dies bare — per-game declarations close the class), and the
   inventory note's sequencing line ("sidecar relocation: orthogonal,
   immediate, stops the littering"). Not speculative.

4. **The totality edge.** The grid axes above; the five misuse
   sentences above. The block's domain deliberately EXCLUDES the
   round-slot and winner-slot primitive names (trick winners, auction
   outcomes) — they are not call-position and take their own
   declaration slots in stage 4; a round-slot name written in the
   block is refused loudly, and the ledger row cites the epic.

5. **The info-set bound.** Scoring primitives emit nothing and 3a adds
   no observation events; information sets do not move. What changes
   is epistemic hygiene: hidden-zone reads become declared. The
   derived-reveal analysis (result-of-hidden-read flowing to public
   state implies a reveal) is the epic's recorded follow-on — debt
   named, not incurred silently.

6. **Counsel.** For: closes #364's class; enables #158's cost lever;
   the registry stops being three hand-edited files; the declaration
   register stays uniform. Against, strongest: the coexistence window
   is a live dual-definition-site domain — the exact shape the audit
   doctrine ranks worst when unmanaged — and the block adds surface
   most game AUTHORS never write (they read it; visibility is the
   point, but the cost is real). What Hoyle would do: adopt the colon
   form, place the block beside `uses`, wall round-slot names, make
   the regime axis first-class grid rows, and schedule 3b before the
   window grows comfortable.

## Plan resolutions from the counsels

- **Derivation shape: the Architect's option A** (front-end-owned).
  Parse stamps `Game.primitives` (None vs empty distinguishable, the
  `trick_order` template); resolve validates the block, checks
  declared-vs-implemented against the names-only implementation index,
  and stamps the game's regime; typecheck materializes the declared
  `Sig` (its own contract's sanctioned materialization); the driver
  builds the runtime table at load; `reads.row()` refuses a legacy-row
  bind for a block-regime game as the load-time Shadow Guard.
- **EngineFacts in the reads vocabulary: DEFERRED loud in 3a.** The
  block's reads name zones and state variables only; the facts half
  stays whole-bundle behind a refusal citing its issue, and
  `narrowing.py`'s docstring is edited in the same change so its prose
  states what 3a does (the register forbids it asserting otherwise).
  This is the fork the Architect reserves to the operator — surfaced
  in the PR for the merge ruling, with the deferral as the
  3a-proportionate default.
- **Goldens claim, scoped per the counsel**: behavior and observation
  byte-identical corpus-wide in 3a (no corpus game adopts the block);
  the witness fixture and Salvo adopt outside the corpus goldens.
- **Risk retired**: the note's "agree rebase order with the
  family-library branch" line is stale — that branch is merged
  (Kuhn/Leduc and `docs/libraries/` on main, verified 2026-08-28).
- The corpus reconciliation pin layers ON TOP of front-end checking
  (the Architect's option C as the corpus-wide second layer), with its
  reddening mutations demonstrated per the verify-the-plant doctrine.

## Architect's counsel

**Headnote.** The question narrows to three engine choices, not one surface: where the registry derived from `primitives { }` declarations comes to exist, how the declared and legacy regimes coexist without a silent fallback, and what becomes of the module-wide read declarations once reads are per-primitive. Settled law already binds most of it in plain words: the resolver classifies every name once and nothing downstream re-derives it; when a downstream consumer needs a type, the type pass materializes it rather than letting it be re-inferred; every deferral is loud or it is a defect; the bundle a primitive receives becomes a named pair; freezing always copies. Recommended: front-end-owned derivation — the resolver validates the block and stamps the game's regime and classified reads, the type pass materializes the declared signatures, and the loader binds implementations from the one Python-side index that survives (implementations cannot derive from declarations; reconciling the two independently authored sides IS the both-ways check) — with the regime picked once by block presence, and per-primitive read rows whose per-module union is derived only for the static walls. Rejected: load-time derivation, where the runtime builds everything and the resolver stays unaware — it moves a designer's declaration typo from a compile error to a playout crash, the wrong failure channel. Newly required: an engine author adds a primitive by one index entry plus a game-file declaration, never by editing three tables and a match arm; newly impossible: a declared game reaching any legacy table. Info sets do not move — the reads clause is checked for validity and drives the bundle; the reveal analysis stays recorded follow-on work. The freeze question stays open deliberately: the tracker's own measurement says freezing costs 82 to 94 seconds of every 100 seconds of playout on primitive-heavy games, and this change shrinks what gets frozen without deciding how freezing is policed. Bottom line: take the front-end-owned shape; the strongest reason against is that the compile gate grows a dependency on knowing what Python implements, a coupling the front end has so far avoided, paid as one names-only index import; the operator must decide whether the engine-facts half of a primitive's reads enters the block's vocabulary in 3a or stays whole-bundle behind a loud, issue-cited deferral.

**1. The decision.** Not "how to parse the block" (Hoyle's) but: (a) which pass owns each half of the derived registry and each of the both-ways errors; (b) the mechanism that keeps every primitive in exactly one regime during coexistence; (c) whether the module-granular `PRIMITIVE_READS` rows are derived or deleted, and what the binder binds.

**2. The law.** resolve's Contract: it is the ONLY pass that classifies names; downstream dispatches on the classification, never re-derives it. typecheck's Contract: inferred types are ephemeral, and "a downstream consumer that needs a type is a signal to materialize it in this pass, never to re-infer it there" — the runtime's `coerce_args` is signature-driven, so the declared signature is exactly such a consumer, and typecheck's own rule licenses the one materialization. reads.py's Contract: name-keyed reads fail as typed `PrimitiveReadError`, and direct state access outside the engine core is illegal via the whole-file AST wall (which keeps its no-exemption shape). primitives.py's Contract: a game module sees only what its declared row permits; the unknown-name refusal is its Shadow Guard. decisions.md "Closed-domain completeness": dispatch arms over a registry are a closed domain — derive, pin statically, refuse the remainder; a dual-definition-site domain is first-class grid rows. The glossary's Primitive Bundle entry: the pair becomes a NamedTuple with this design — honor it in `narrowing.bind`'s return. deep_freeze always copies — settled, untouched.

**3. Precedent.** House: `Game.trick_order: TrickOrder | None` is the exact template — a declaration block that is "the ONE source" of its facts, whose *presence* partitions the legal surface in both directions (`_check_trick_order_partition`); the regime pin should be its sibling, not a new invention. Book: P2 (Area 1, nanopass — materialize in the owning pass, never re-derive downstream); P9 (Area 4 — one source, every scrape derived and pinned); P11 (Area 5 — the reconciliation pin must redden on a planted orphan before it is trusted); P13 (Area 6 — the reads clause is the declared-once substrate that later makes hidden-read reveals derivable; nothing in 3a may weaken it). All established; no unverified marks relied on.

**4. The options.**
- **A (counseled): front-end-owned derivation.** Parse stamps `Game.primitives` (`None` vs empty distinguishable, as with `trick_order`). resolve validates the block — duplicate names, Builtin-name collision, unknown signature type names (`KNOWN_TYPE_NAMES`), each reads name classified against the game's own declarations into the row kinds (state var / zone family / single zone) by one exhaustive classifier — checks declared-but-unimplemented against the keys of the one surviving Python index (name -> lazy implementation reference; names-only import, so the front end never imports game modules), resolves block-regime calls against block-union-Builtins, and stamps the regime. typecheck materializes the declared `Sig` per its own contract and owns call-site arity/type errors. The driver builds the runtime table (impl, materialized sig, per-primitive row) at load; `native_call` takes the sig from the game table for block names, `CALL_SIGS` otherwise — a classified lookup, never try-then-fall. Cost: the compile gate imports an index that describes runtime implementations — a real new coupling, kept to names.
- **B (rejected): load-time derivation.** resolve checks names only; the runtime assembles registry and dispatch when the driver loads the game. Cheapest coupling, but declared-but-unimplemented becomes a load/playout error and `check_dsl` passes an unrunnable game — the designer's failure channel is the compile diagnostic, and this option surrenders it.
- **C (rejected as sole mechanism): static-test-only reconciliation.** The corpus pin catches orphans in-tree but the next out-of-tree game gets a runtime `AssertionError`. The impl index makes this a *closed* domain, so exhaustive front-end checking is owed; keep C as the corpus-wide layer on top of A, not instead of it.

**5. What becomes illegal after (option A).** *resolve* newly establishes the resolved block and the game's regime as stamped facts; illegal after: a block-regime call resolving through `PRIMITIVE_CALL_FUNCS`, an unclassified reads name, a declaration naming no implementation, a block entry shadowing a Builtin. *typecheck* newly establishes the materialized declared-sig table (the sanctioned exception to ephemerality, by its own contract line); illegal after: any consumer rebuilding a `Sig` from type names. *primitives.py*: the migrated match arms are gone; a hand-written arm for a declared name is the defect the derivation exists to end; the unknown-name refusal survives as Shadow Guard. *reads.py*: authored rows for migrated games are deleted; the binder binds the primitive's OWN row; the per-module union is DERIVED and consumed only by the static walls (the AST accessor scan and the rename-metamorphic exclusions), never by the binder — a binder reading the union would silently undo the granularity this stage buys. `reads.row()` refuses a legacy-row bind for a block-regime game (typed `PrimitiveReadError`), which is the load-time wall: regime is decided once at resolve, and the runtime's only role is to refuse contradiction, never to fall back. *narrowing.py*: `bind` returns the Primitive Bundle NamedTuple; its docstring's claim that stage 3 narrows `EngineFacts` per primitive is either made true (facts field names, derived from the dataclass registry, admitted into the reads vocabulary and classified by the same exhaustive classifier) or edited in the same change to state the loud deferral, issue cited — the prose register forbids leaving it asserting what 3a does not do. Out-of-block consumers (climb rows via `climb_row`, the auction outcomes, the pegging call sites) keep their authored rows untouched; the arrival-zones facet, which no authored row uses today, gets a statically refused grammar cell with an issue, not a designed-in clause.

**6. Counsel.** *For A:* it is the write-time-triage doctrine executed — every error lands in the pass whose Contract already owns its class, the designer's errors are compile diagnostics, the runtime keeps only typed Shadow Guards, and the three hand tables plus the match collapse into one authored index whose reconciliation is checkable both ways. The presence partition reuses a proven house mechanism, so "undeclared game" is a stamped, checked regime rather than a lookup order. Per-primitive rows are also the first honest step toward issue #158: keep `deep_freeze` the single choke point inside `game_reads`/`engine_facts`, pin immutability *semantics* (never freeze counts or object identities), and cache nothing across calls — that leaves sampling or gating a one-site change later. *Against A:* the front end learns what Python implements — a dependency direction it has not had — and the coexistence period doubles the grid (every probe rows out per regime), which is real audit cost paid now for a table that stage 4 partially reshapes when co-location changes how implementations are found. *The Architect would* take A, with the corpus reconciliation pin layered on (derived from the games glob through the pipeline, crossed against the index and the legacy tables, both directions, its reddening mutations demonstrated — an orphaned implementation planted, a dual claim planted), the misuse probes of §5 extended with the collision, empty-block-with-legacy-call, and regime-mismatch cells, and the goldens claim scoped honestly: per-seed playout goldens and observation stream hashes byte-identical at FULL WIDTH, while the IR goldens of migrated games change by exactly the printed block and regenerate at their own width — "byte-identical" is claimable over behavior and observation, not over emitted text.

## Appendix — the framing-check enumeration (verbatim planning artifact,
## produced fresh-context from definition sources only, 2026-08-28)

1. **Block placement in `game_item`** — grammar `?game_item` alternatives; the new block is one more. MISS-RISK: `?library_item` is a separate list — a primitives block in `library { }` is legal or statically refused; silence = accepted-but-ignored.
2. **Block delimiter / entry-cardinality shape** — `entry*` vs `entry+` families and the reject-arm twins (`trick_order`'s three). MISS-RISK: empty block vs absent block are different attribution states under two regimes (an empty declared row is meaningful today: `climb_row`).
3. **Clause repeatability** — {absent, once, twice+}; `uses_decl` is the only repeatable game_item today; parse.py holds the both/neither Owner Guards precedent.
4. **Keyword-exclusion registries** — `CARD_RANK_NAME`, `STRUCT_TYPE_NAME`, `_KEYWORD_RESERVED`/`RESERVED_VALUE_NAMES`, each with its pinning test, plus the `_<WORD>_KW` anchored form. MISS-RISK: entries begin with NAME so the block IS absorbable — `STRUCT_TYPE_NAME` exclusion is required; `_RESERVED_WHY` needs its entry or a diagnostic path KeyErrors.
5. **Declared param/return type value set** — `cardlang/types.py` constructors crossed with {param slot, return slot}. MISS-RISK: `TAny`/`TNull`/`TOutcome`/`TStruct`/`TLine`/`TDir` constructible but not designer-spellable; `CALL_SIGS` uses `TAny` load-bearingly — a surface that cannot spell it cannot express the whole existing table.
6. **Arity** — zero-arg members exist (`bring_in_seat`, `tichu_dragon_won`, `coup_game_summary`); derivation `max(len(s.params) for s in CALL_SIGS.values())`.
7. **Reads-clause name kinds** — `PrimitiveReads` fields: `state_vars`, `zone_families`, `single_zones`, `arrival_zones` — four, not one. MISS-RISK: `arrival_zones` is a FACET of a `single_zones` name with two bind-time validations; no spelling = silently dropped channel.
8. **Family granularity** — whole family vs one binder-keyed instance vs single zone vs state var vs indexed state var. MISS-RISK: today's rows grant whole families and Canasta/Coup need that; binder-only cannot express them, family-only cannot narrow. Both cells exist.
9. **Index-binder domain** — {player, team, game-declared position domain} per `zone_decl`/`positions { }`/`index_domain`.
10. **Zone type of a named read** — `LIBRARY_ZONE_TYPES` keys crossed with `ZONE_PROJECTIONS` owner/others levels; the projection level is the info-set axis in disguise (see 21).
11. **EngineFacts, the un-narrowed half** — six fields crossed with {declarable, granted-unconditionally}; `round_state` vs `last_round_state` differ mid-round by design.
12. **Which primitive namespace the block covers** — six sets (`PRIMITIVE_CALL_FUNCS`, `_AUCTION_OUTCOMES`, `_CLIMB_LEADS`, `_CLIMB_FOLLOWS`, `_EARLY_PREDICATES`, `_TRICK_WINNERS`); signature homes differ (`CALL_SIGS` typed vs `VALUE_SIGS`/`EARLY_SIGS` no-params). MISS-RISK: four have contracts a typed param list cannot spell; "exactly one regime" must state per-name-per-namespace vs per-game.
13. **Regime attribution** — {block absent, present-listing-all, present-listing-some} x {name in `PRIMITIVE_*`, only in block, in neither} x {game in `PRIMITIVE_READS`, not}. MISS-RISK: block-present-but-partial — attributable to both or neither.
14. **Module-game cardinality** — rows keyed `(module, game_file)`: one-one, one-module-many-games, one-game-many-modules, identical-rows-import-bind (issue #232's shape).
15. **Two-way check's layer and failure channel** — resolve/typecheck never import runtime game modules; channels: parse reject arm, DiagnosticBag, `PrimitiveReadError`, `OwnerGuardError`, `AssertionError`, pytest scrape, mypy. MISS-RISK: declared-but-unimplemented landing only in a test means `check_dsl` reports clean on an unrunnable game; implemented-but-undeclared is the direction only an AST scrape sees.
16. **Syntactic positions of a primitive name** — expression calls (let/assign/`+=`), if conditions, `when:` guards, movement `where` filters, `where jointly`, quantifier bodies, rule clauses, phase qualifiers, bare-name slots (`winner`, `outcome`, `early`, `combinations`/`follows`), function/procedure/define bodies, trick_order rows. MISS-RISK: bare-name slots resolve against different namespaces than calls; two names live in two positions each with its own namespace.
17. **Name collision with each namespace** — Builtin, primitive, the game's own six definition kinds, imported library kinds, zone names, state vars, `RESERVED_VALUE_NAMES`, magic `hand`. MISS-RISK: Builtin shadowing — no lookup today is order-sensitive, so a duplicate key silently wins somewhere.
18. **Declared type drives runtime freezing** — `coerce_args`: `TCollection` -> elements + deep_freeze; `TAny` -> RAW; else deep_freeze. MISS-RISK: a wrong declared type silently changes what the implementation receives; `tests/test_native_call_boundary.py`'s pinned `TAny` set becomes designer-reachable for the first time.
19. **Partitions over `CALL_FUNCS` that must stay total** — flavor partitions, trick-order row callable/uncallable, `ARRIVAL_RECORD_CALLS`, `_FRAME_CALL_FUNCS`, each with its pinning test. MISS-RISK: the trick-order partition covers only the Builtin half on the ground that primitives are "uncallable by construction" — a declared name breaks the argument or vacuates the test.
20. **Codec dependency** — `joint_codec_function` / `climb_universe_function` / `climb_codec_function`: {enumerable, arithmetic codec, neither}. MISS-RISK: a declared primitive as a `where jointly` predicate needs a Python-side codec entry the game file cannot populate; the `ActionSpace.for_game` guard is the loud wall.
21. **PAIRWISE reads-kind x syntactic position** — `ZONE_PROJECTIONS` x the position list; rigor-critical cells are non-identity zones read inside `when:` guards, `where` filters, `where jointly` — a concealed read inside a legal-action set. MISS-RISK: the general reads clause makes the cross checkable for the first time; a missing guard is a silently widened info set.
22. **PAIRWISE declared type x consuming operation** — type constructors x {`coerce_args` arm, `_check_call`, `evaluate` dispatch, `join`/`coercible`, `where jointly` (needs `TCollection`), winner/loser slot typing, `ARRIVAL_RECORD_CALLS` `TAny` requirement}.
23. **PAIRWISE block x family-library `uses`** — `resolve._LIBRARY_UNSWEPT["primitive_query"]`'s recorded reason ("closed: identical either side") ceases to hold with game-local declarations; the sweep row reopens. Same shape as the falsified `index_domain` row.
24. **PAIRWISE block x rename-metamorphic oracle** — the oracle derives coupled-name exclusions FROM `PRIMITIVE_READS`; a game-file declaration co-renames with the zone, making the coupling unobservable to the oracle. The instrument that found the class must be re-pointed or its narrowed scope recorded.
25. **Game-file input form** — `.md` fenced extraction vs `.cardlang`, both-present-disagreeing; `PrimitiveReads.game_file` names basenames; the derivation must read the pipeline's extraction path.
26. **Repo-level censuses** — signatures reconciliation, dispatch-split grid, reserved declarations, classification prose, openspiel_ready coverage, eviction grid, tools sweeps; derivation query `grep -rln --include='*.py' -E "CALL_FUNCS|CALL_SIGS|PRIMITIVE_READS|VALUE_NAMES" cardlang tests tools experiments`. MISS-RISK: a new module is a new census row; a new test module must import pyspiel-free at collection.
