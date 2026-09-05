# Cribbage adopts the `primitives { }` block, the site-read contract retires, and the two-phase wall lifts for nested phases (issues #473 and #517)

Operator go: Ben, 2026-09-04 ("on to cribbage!"), then the fork ruling the
same day: "Do it properly, option A. Ask Hoyle and Foster for their input
and if there is consensus begin implementation" — option A lifts the wall
of issue #517 for NESTED phases with Cribbage as its named witness, in this
same change. Merge Lane: not A (no grammar surface — the per-read tails
already parse), but a language-LAW change that Hoyle ruled as a wall, so
Hoyle sits (reopening event) and the Architect sits on the containment
machinery; both counsels attach below; operator-merge per docs/harness.md. Stage plan this serves:
`docs/plans/2026-08-29-primitives-block-stage3b.md` (closing steps:
cribbage is one of the three legacy holdouts; after it, coup alone).
The tail this game needs is the construct of
`docs/plans/2026-08-30-phase-scoped-reads.md`.

## Acceptance criteria (bind the change)

1. **Runs** — cribbage declares its block and plays under the declared
   regime; the pegging phase calls both normalized scorers through the
   bundle, and the show calls its three siblings.
2. **Regression-clean** — bare `mypy`; CI's three checks; the per-seed
   playout goldens byte-identical at FULL WIDTH (cribbage carries
   `tests/golden/cribbage_hands.json` in the characterization manifest —
   no substitute instrument is needed, but the read oracle below still
   runs, because the neutrality claim rests on an equivalence the goldens
   witness only by outcome). IR goldens: cribbage has none; none moves.
3. **Info sets derive** — declaration-only surface over signatures
   `CALL_SIGS` already carries (`peg_pair_points() : Integer`,
   `peg_run_points() : Integer` — the DSL calls them with no arguments
   today; the site supplied the pile). The frozen pile the bundle hands
   over must be the SAME shape the site froze (`reads.deep_freeze` of the
   zone's cards at the site; `gr.singles["play_pile"]` through the bundle)
   — an EQUIVALENCE CLAIM, so it carries its falsifying probe: the
   implementer captures both shapes at one call and compares, and the
   full-width goldens plus `tests/openspiel_ready/test_cribbage.py`
   (untouched) close the outcome side. Nothing new is emitted; no debt.

**Corpus lockstep** (operating rule 2): `docs/games/cribbage.cardlang`
gains the five-entry block; both legacy `PRIMITIVE_READS` rows delete —
`cardlang/runtime/cribbage.py`'s own (with its `ROW` binding and the three
bundled dispatch arms) AND the dispatch module's cribbage row `_CRIBBAGE_R`
(with the two site-read arms) — so the reconcile pin's carve-out (the
shared dispatch module's rows) shrinks to the three auction rows by
derivation; the five names move to `DECLARED_ONLY_CALL_FUNCS`. The twin:
`docs/games/cribbage.md` is a link-shape rulebook after PR #563 (no fenced
block; `PROSE_ONLY_TWINS` pins the set) — its prose is re-read for
sentences that go false. `docs/design-notes/primitive-sidecars.md`
section 5 is rollout-agnostic; section 2 names the site-read shape if
anywhere — swept. No glossary entry names the contract (checked
2026-09-04: `ls docs/glossary/ | grep -i -E "invocation|contract|site"`
is empty), so no mint and no retirement there; the enum's own docstring
is the definition.

**Witness:** cribbage, in-change.

## Gate record (cardlang-planning)

- **Gate 1 (owners):** the fix's DESIGN is the issue's own body, filed by
  the 3a change with the Architect's classification of every
  `PRIMITIVE_CALL_FUNCS` member by dispatch shape: normalize both
  scorers onto `impl(facts, gr, *args)`, reading `gr.singles["play_pile"]`
  and `facts.rank_index`; the reads move to cribbage.py's own row (which
  already names `play_pile`). The one question the issue leaves open —
  what becomes of `InvocationContract.SITE_READ` when it has no member —
  is answered by settled doctrine, not counsel: decisions.md
  "Closed-domain completeness" (a refusal arm no input can reach is a
  check that cannot fail) and the partition's OWN pin
  (`tests/test_primitives_block.py::test_every_contract_arm_is_used`,
  `used == set(InvocationContract)`, whose recorded red-under is exactly
  "an arm with no row using it"). The member retires with its refusal
  branch and its cells; the partition re-derives. No Hoyle (no surface);
  no Architect sitting (the structure was ruled at 3a; this change
  re-derives nothing and adds no mechanism). The reconcile carve-out's
  derivation (the Architect's 3b counsel) absorbs the row's departure
  unchanged. Ordering: #143's 3b line; #473 is holdout two of three.
- **Gate 2 (classification):** runtime (`cardlang/runtime/cribbage.py`
  two signatures; `cardlang/runtime/primitives.py` five arms and one
  module-keyed row deleted), native registry (`PRIMITIVE_IMPLEMENTATIONS`
  two contracts SITE_READ -> BUNDLED; the enum loses SITE_READ;
  `DECLARABLE_CONTRACTS` unchanged in content; `DECLARED_ONLY_CALL_FUNCS`
  gains five; `RANKING_GATED_FUNCS` unchanged — `peg_run_points` is already a member and already a derived reader; executed by the Architect),
  resolve (the contract refusal's issue citation simplifies: only
  EMITTING remains, cited #142), reads registry (two rows delete), corpus
  game (cribbage), tests (derived cells retire; one born-green pin reddens
  and is answered). A closed-domain partition shrinks: the audit fires at
  it; Gate 4 applies.
- **Gate 3.5 (reachability):** #473 is R2 (anyone migrating cribbage
  meets the refusal on the first two entries) and the fix is mechanical
  — proportionate; it unblocks holdout two of three and the stage-3
  deletion behind them. Nothing here edits doctrine or adds scaffolding.
- **Gate 4:** the framing check ran 2026-09-04 fresh-context over the
  contract partition and its consumers (report attached below as a dated
  record); its diff against the author's derivation is recorded in "The
  accepted domain". The red set is stated before implementation.

## The design, as the issue states it and the tree confirms

- `peg_pair_points(facts, gr) -> int`: reads `gr.singles["play_pile"]`
  (the site's `deep_freeze(reads.single(rs, _CRIBBAGE_R, "play_pile").cards)`
  becomes the bundle's own materialization of the same single zone).
- `peg_run_points(facts, gr) -> int`: reads `gr.singles["play_pile"]` and
  `facts.rank_index` (the site's second argument). `peg_run_points` is
  ALREADY in `RANKING_GATED_FUNCS` and already counted by the
  derived-readers pin (executed by the Architect, 2026-09-04): membership
  does not change; the only pin that can redden on this axis is the
  control pair — `peg_pair_points` must name `rank_index` nowhere in its
  call closure, which the helper split below guarantees by construction.
- The two site-read arms and `_CRIBBAGE_R` delete; the three bundled arms
  delete with cribbage.py's `ROW` binding at migration; `call()`'s arm set
  stays equal to `PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS` (the
  dispatch-split pin).
- `InvocationContract.SITE_READ` retires: the enum member, resolve's
  citation branch (`'#142' if EMITTING else '#473'` collapses to the
  EMITTING citation), the enum docstring's description of the shape, and
  every derived cell that enumerated it. `DECLARABLE_CONTRACTS` keeps
  {BUNDLED, PURE}; the refused set keeps {EMITTING} (coup), so
  `test_the_declarable_contracts_are_a_proper_subset` stays non-vacuous.
  Illegal after: an implementation registered with a contract the
  dispatch cannot answer — every remaining contract has a member and an
  arm shape.

## The block (illustrative — the migration derives reads ENTRY-GRAIN from
## cardlang/runtime/cribbage.py, never from this plan)

```
  primitives {
    peg_pair_points() : Integer                 reads play_pile
    peg_run_points() : Integer                  reads play_pile
    peg_origin_of(c : Card) : Player            reads play_pile, seq_bits in play, seq_len in play, dealer in hand_sequence
    cribbage_show_value(p : Player) : Integer   reads played[p], starter
    cribbage_crib_value() : Integer             reads crib, starter
  }
```

Measured 2026-09-04: `dealer` is `phase hand_sequence`'s state; `seq_bits`
and `seq_len` are `phase play`'s (a descendant of `hand_sequence`);
`score` and every zone are game-level. So cribbage is a PHASE-LOCAL
migration too, and `peg_origin_of` reads from TWO phases on one ancestor
path — the sentence above is REFUSED on main by the one-phase rule
(executed: "reads state from phases `hand_sequence`, `play` — one entry's
`reads` clause names at most one phase … split the entry, or pass the
second value as an argument"). That is wall #517, whose named witness is
exactly this shape. The operator ruled option A: LIFT the wall for nested
phases — an entry may name phases lying on one ancestor path, and it is
callable only where the innermost runs (the intersection of the nested
subtrees; the non-nested pair's intersection is empty and stays refused).
Call positions: all three `peg_origin_of` sites sit inside `phase play`
(lines 106, 117, 136 — the innermost), the peg scorers likewise, the show
entries inside `hand_sequence`'s body reading no phase-local name — all
inside the containment rule under the lifted law. `facts.seating` and
`facts.rank_index` are the EngineFacts channel, undeclared by design.
Hoyle's and the Architect's counsels on the lift are attached below; the
plan's design follows them where they speak.

## Counsel outcome and the operator's standing instruction (2026-09-04)

Both seats sat (Hoyle first; the Architect composing on Hoyle's block and
writing the bottom line). The Architect's consensus line: "the seats agree
on every material point" — nested-only; nest-and-innermost; no order
meaning; no depth cap; the non-nested pair a designed constraint with the
"no place in this game runs both" reason; #516/#518/#521 standing and
re-probed with two tails; the prose sites; the two-phases rejection
re-blessed; the ancestor-case register fixed from the same paths; the
implementation-order hazard closed by red-first order; information sets
unmoved. Per Ben's standing instruction ("if there is consensus begin
implementation"), implementation begins on this plan. The one point both
seats reserve to the operator — that the non-nesting refusal closes as a
DESIGNED constraint with NO issue, recorded at the arm, in the glossary
sentence and in the rejection fixture, its premise pinned by the one-line
frame-pop test — is taken as ruled by consensus under that instruction and
is flagged in the PR body for the operator's veto at merge.

The Architect's machinery, binding on the implementer: `phase_paths(game)`
(one recursion over the phase tree yielding every phase's path, declaring
or not; `phase_names` and `_phase_state_decls` derive from it) and
`phase_chain(game, phases) -> tuple | None` in `primitives_block`
(outer-to-inner when the paths are prefix-ordered, `None` otherwise);
`_scoped_entry_phases` returns a frozen `_ScopedEntry(chain, region,
binding)` per entry, asking the SAME predicate the arm asks; the nest arm
sits at ENTRY grain after every per-read tail has validated (a misspelled
tail has no path — asking "nest?" first would co-report); the region is
`_walk(region)`; `_check_scoped_read_containment` builds a position
attribution `phase_of_node` (deeper phases overriding) so the outer-side
diagnostic says "in `Q`, which encloses `R` but runs outside it (`R`'s
state does not stand here)" when Q's path is a proper prefix of R's —
which also fixes the existing ancestor-case misregister; `_outside` names
the binding read and the region. No runtime line changes (executed under
a shim: nested pair, three-chain and inner hooks play; the vacuous window
is real — outer-body, outer-hook and sibling calls check clean and crash
at playout in the shadow guard's channel). Three born-green pins with
named reddening mutations: the shape-class derivation pin, the
non-declaring-ancestor path pin, and the frame-pop pin on `run_phase`
(`len(rs.frames)` equal before and after). The red-first ORDER is
mandatory: (0) the new cells committed red against main; (1)
`phase_paths`/`phase_chain` with unit cells; (2) `_scoped_entry_phases`
chain-aware while the old arm still refuses; (3) the arm replaced and
`_outside` taught enclosure — step (3) before (2) is the forbidden order.
Take 2 (the arm lifted alone, in the working tree, never a commit) is
quoted dated in the grid module's docstring: accepts green, outer-side
and sibling refusals red as DID NOT RAISE.

## The lift, as Hoyle ruled it (2026-09-04; counsel attached below)

- **The law of the clause, in the designer's words:** *the phases an
  entry's `reads` clause names must nest, one inside the next; the entry
  is callable only where the innermost of them runs.* Each read keeps its
  own tail (the per-read spelling does not change); the innermost tail is
  the one that sets where the entry may be called. Resolve's Contract
  carries the engine's statement of the same rule (region = the
  intersection of the named phases' subtrees = the innermost's subtree).
- **No order meaning, no depth cap.** Inner-first and outer-first
  spellings are both accepted (executed: today both are refused by one
  arm with identical text, because the tailed set is a set); the
  recommended spelling for cribbage is the game's own order (the pile,
  the provenance bits, the parity key), not legislated; three phases on
  one path follow the same sentence and a synthetic three-deep cell plays.
- **What stays refused, and what each is:** two phases NOT on one path
  (siblings, cousins) — a DESIGNED constraint, not a wall: `run_phase`
  pops a phase's frame when it ends, so no place in the game runs both
  and the entry could never be called; refused in the tail-validation arm
  with the teaching reason ("no place in this game runs both — keep one,
  and pass the other value as an argument or declare it in the game's
  `state { }`"), and NO issue (the operator's one language-half decision:
  ratify that it closes without one). The same phase twice on one read —
  the doubled-tail parse cell, unchanged. The same NAME under two tails —
  the repeat guard, unchanged in law (its wording is the Architect's).
  The inner phase re-declaring a name the outer tail names — the fourth
  predicate `descendant_redeclarations` refuses it per read; today the
  per-entry arm fires first, so that cell is refused for the WRONG reason
  and is authored red-first. #516 (game-and-phase shadow, phase-and-zone),
  #518 (function/define/rule bodies), #521 (offers inside move-type/define
  bodies) stand untouched and are re-probed with two tails present.
- **The losing rival, priced:** `peg_origin_of(c : Card, d : Player)` with
  `peg_origin_of(card, dealer) is dealer` at three sites — zero language
  change, resolves clean today (executed), and reads as a tautology on
  the page; the dealer is the decoding KEY of the provenance bits,
  constant for the hand, hauled through three clauses and a Python
  signature. Hoisting `dealer` to game state is rejected on the
  load-bearing rule (the game bends to the instrument). An entry-level
  region tail (`... : Player in play reads ...`) is rejected: a new
  production, and inference of bare names up the path — the silent-pick
  reason settled 2026-08-30.
- **The register (Hoyle's sentences; the Architect owns the pins):** outer
  body outside the inner — "`peg_origin_of` reads `seq_bits in play`, so
  it is callable only where `play` runs — this call is in
  `hand_sequence`, which encloses `play` but runs outside it (`play`'s
  state does not stand here); move the call inside `play`, or pass the
  value as an argument" (name the innermost by role and the read that
  binds it; never list both phases as the region); not nested — the
  designed refusal above; the existing ancestor-case misregister ("this
  call is in another phase" for the ENCLOSING phase) fixed in the same
  change ("in `top`, which encloses `outer` but runs outside it").
- **The implementation-order hazard (must-survive):** `_scoped_entry_phases`
  silently `continue`s on a multi-phase entry; lifting the refusal arm
  before containment learns the innermost leaves a two-phase entry
  accepted and UNCHECKED — the worst class this project names. The
  outer-body-outside-inner refusal cell and the sibling-pair refusal are
  authored and committed RED before the arm changes, so the vacuous
  window is never green.
- **Lane:** not A by the letter (no `.lark` production moves) — B by the
  supremum: a sentence the parser already accepts changes meaning, and
  the wall was Hoyle's own. Operator merge.
- **Corpus (measured):** 11 games carry a block; 10 of 10 tailed entries
  name one phase; after the lift exactly one names two — cribbage's
  `peg_origin_of`. One file moves. `cribbage.md` is a link-shape twin;
  its prose naming `peg_origin_of` as the decoder stays true.
- **Prose sites stating the one-phase law (Hoyle's sweep; assume a miss and
  re-sweep after editing):** resolve.py's arm + comment + message
  (~5373-5386); resolve's Contract (~106-116); `_scoped_entry_phases`'
  docstring; `_outside` (~5896-5903); the grammar comment at
  cardlang.lark ~117-122 ("one phase's" -> "a phase's");
  docs/glossary/phase-scoped-read.md line 3 (then `python -m
  tools.glossary_index --write`); tests/test_phase_scoped_reads.py's
  ledger `domain:` and `walls:` rows, its two cells at ~538-567 and floors
  at ~1286-1296; tests/rejections/primitives_scoped_read_two_phases.*
  (a sibling pair — `.expected` re-blessed to the designed refusal, the
  `.cardlang` header rewritten); docs/design-notes/primitive-sidecars.md
  ~332-345; issue #517 closes. Sites that stay true per read: driver.py
  ~113-118, reads.py ~541-548, primitives.py ~88-94, primitives_block.py
  ~497, the reads-clause glossary entry, library.md ~383-390.
- **Misuse sentences, each loud in its layer:** the outer tail read as a
  licence (call from `hand_sequence`'s `before_each`) -> containment
  naming `play`; `dealer in play` -> the wrong-declarer arm ("phase
  `play` declares no state `dealer` — phase `hand_sequence` declares
  it"); the list-scope misreading -> the phase-local arm teaching
  `seq_bits in play`; `dealer in show` with `show` a sibling -> the
  non-nesting refusal; `seq_bits in play in hand_sequence` -> parse;
  `..., dealer in hand_sequence, dealer` -> the repeat guard; `dealer in
  hand_sequence` alone called from `play` -> accept (the existing
  descendant cell).

## The accepted domain (author's derivation; the framing-check diff is appended when it lands)

1. The contract partition: `InvocationContract` members x
   `PRIMITIVE_IMPLEMENTATIONS` rows (derived: `Counter(impl.contract for
   impl in PRIMITIVE_IMPLEMENTATIONS.values())`); consumers —
   `primitives_block.undeclarable_contract` / `DECLARABLE_CONTRACTS`
   (module lines ~236, ~665), resolve's refusal arm (one site), the
   partition pins `test_every_contract_arm_is_used`,
   `test_the_declarable_contracts_are_a_proper_subset`, the regime-product
   renderer's contract handling (~1227-1241), the per-name refusal grid
   `test_an_undeclarable_contract_is_refused_by_name` (derived over the
   refused set — the two cribbage cells vanish by derivation, coup's
   stays), the enum docstring.
2. The dispatch site: five `call()` arms; `_CRIBBAGE_R`; the dispatch-split
   pin (`tests/test_native_dispatch_split.py`); `_bind`.
3. The reads registry: two cribbage rows; `tests/test_primitive_reads.py`'s
   module-source scan and its reconcile carve-out (`_climb_bound_rows` |
   the shared dispatch module's rows, with the assert that no call
   implementation names that module); `NARROWED` / `MIGRATED` /
   `EMITS_TRACE` in `tests/test_primitive_narrowing.py`.
4. The rank-index channel: `EngineFacts.rank_index`; `RANKING_GATED_FUNCS`
   and its derived-readers pin; the ranking gate's diagnostic.
5. The frozen-pile equivalence: site freeze vs bundle materialization —
   the read oracle plus a one-call shape comparison.
6. The corpus: cribbage's five call sites, their phases, the three
   phase-local names and two declaring phases; the twin's link shape;
   the goldens (`cribbage_hands.json`, full width) and the OpenSpiel proof.
7. Prose: every sentence naming the site-read shape, `_CRIBBAGE_R`,
   "pegging call sites", or #473 as a wall (primitive-sidecars.md,
   reads.py's row comment "the auction outcomes and cribbage's
   pegging-scorer call sites", primitives.py's docstrings, the 3b plan's
   closing steps — a dated record, left; the exclusion/contract
   docstrings; `tests/test_primitives_block.py`'s ledger lines naming
   SITE_READ).

### Framing-check diff (fresh-context, 2026-09-04; report attached as a dated record)

Consumers the author's derivation lacked, each now a step or a recorded
decision:

- `tests/test_primitive_narrowing.py::test_engine_core_game_knowledge_is_named`
  hard-codes the dispatch module's row set {bridge, cribbage, pinochle,
  french-tarot} — RED when the cribbage row leaves; both sides derive — the name set from
  `PRIMITIVE_AUCTION_OUTCOMES`, the expected rows from the corpus's
  auction-outcome slots crossed with the shared dispatch module's rows
  (the Architect's ruling; the literal set equals the registry today); its ledger residual (1)
  already names only the auction outcomes.
- `tests/test_primitives_block.py::_LEGACY_HALF_NAME = "cribbage_crib_value"`:
  after cribbage migrates the legacy half is {coup_game_summary}, which is
  EMITTING and undeclarable, so the regime-product cell ("legacy-arm too",
  "block declares it") has NO admissible representative. DECISION: the
  cell becomes `xfail(strict=True, raises=...)` citing #142's coup
  eviction — the legacy axis retires whole with the stage-3 deletion PR;
  the axis is not restated.
- Six cells in `tests/test_zone_family_typing.py` (~423-453) build a
  LEGACY fixture calling `peg_run_points()` / `cribbage_show_value(0)` /
  `cribbage_crib_value()`: the declared-only arm speaks first once the
  names move — the fixture declares its entries (the stud-selectors
  precedent), reads unscoped where the fixture's own declarations are
  game-level.
- `tests/test_trump_slot_class.py::_drive_peg_run_points` calls the pure
  `peg_run_points([cards], order)` — rebuilt on the bundle shape
  (`_drive_president` precedent); `test_every_ranking_reader_has_a_driver`
  keys by name, unchanged.
- `tests/test_primitive_narrowing.py::test_peg_direct_arm_args_are_frozen`
  proves the SITE's freeze with a one-arg monkeypatch — RED under any
  shape of the change; it retires, its claim now owned by the bundle
  immutability grid (d) (the ledger says so), and ledger (d')'s "the two
  cribbage peg arms" half is rewritten.
- `tests/test_cribbage_primitives.py` imports `ROW` — rebuilt through
  `driver.declared_primitives` (the gin precedent).
- `tests/test_playout_cribbage.py` calls the pure cores bare. DECISION:
  the pure cores SURVIVE as helpers (`(seq)` and `(seq, order)` — the
  module docstring promises exactly that unit-testability) beside the
  registered bundled adapters `peg_pair_points(facts, gr)` /
  `peg_run_points(facts, gr)`; the control-pair scrape
  (`peg_pair_points` must name `rank_index` nowhere in its call closure)
  binds the helper split.
- `tests/fuzz/known_findings/cribbage_repeat_until_nonterminate.cardlang`
  is a frozen OLD cribbage calling all five names; once declared-only it
  is refused at resolve and `test_known_findings_still_reproduce` goes
  RED. DECISION: the fixture gains the block (its finding is a playout
  non-termination; resolve acceptance is incidental to the record, and a
  block keeps the reproduction alive) — the finding's classification
  stays true.
- `MIGRATED` gains the two peg names (the property wants every migrated
  name); `NARROWED` drops `cribbage.py::ROW`; `EMITS_TRACE` untouched.
- `tests/test_signatures.py` ledger residual (~30-34) names the peg arms
  as inline arms — rewritten.
- Prose sites (the check's section 7): `primitives_block.py` enum
  docstring ("The other two are refused BY NAME" -> one), `runtime/
  primitives.py` :44-46 and :128-131, `reads.py` :286-287, `cribbage.py`
  :12-19 / :72-76 / :147-150, `resolve.py` :5293 (the citation branch),
  `test_primitive_narrowing.py` ledger (d') and :1476-1479 / :1613-1623,
  `test_signatures.py` :30-34, `test_primitives_block.py` :2382-2384 and
  :651-658, `docs/design-notes/primitive-sidecars.md` :317-327,
  `docs/design-notes/primitive-inventory.md` :343-345 (dated, unmaintained —
  the precedent leaves it), `cribbage.cardlang` :17-18 (the doubled
  word "Primitive primitive", pre-existing, fixed in passing since the file
  moves). Dated plans stay.
- The block loop reports only the FIRST failing entry (a pre-existing
  bound on composite probes; not this change's).
- Confirmed by the check: the frozen-pile equivalence holds today at every
  call across three seeds (site tuple == bundle tuple, same order, same
  element type, rank_index equal) — the substitute for a read oracle on
  the equivalence claim, re-run by the implementer at the new HEAD.

## Steps, each with its proving artifact (the red set is the work list)

1. Normalize the two scorers (`cardlang/runtime/cribbage.py`) and delete
   the two site-read arms + `_CRIBBAGE_R` + the dispatch module's cribbage
   row. Artifacts that REDDEN on this step and are answered in the same
   change: `test_every_contract_arm_is_used` (SITE_READ now unused ->
   retire the member), `test_every_rank_index_reading_primitive_is_ranking_gated`
   (`peg_run_points` now reads `rank_index` -> `RANKING_GATED_FUNCS`
   gains it), the module-source scan for cribbage.py (its row must now
   name what the bodies read — it already does), the dispatch-split pin.
   Commit the reddening state FIRST (the born-green pins' reddening
   mutation, recorded), then the answers.
2. Retire `InvocationContract.SITE_READ`: enum, docstring, resolve's
   citation branch, `PRIMITIVE_IMPLEMENTATIONS` rows -> BUNDLED. Artifact:
   the partition pins green with the member gone; the per-name refusal
   grid derives one cell (coup); the ledger in `tests/test_primitives_block.py`
   names the retirement's reason (a contract no dispatch answers is not a
   contract).
3. The frozen-pile equivalence probe: capture the site's frozen tuple (on
   a merge-base worktree) and the bundle's (`gr.singles["play_pile"]`) at
   the first pegging call of seed 0; assert identical shape, order, and
   element type. Artifact: the probe's output quoted in the PR body /
   Gate 4 record (a scratch instrument, stated as such).
3b. Lift wall #517 for nested phases (per the attached counsels; the
   Architect owns the machinery): `_scoped_entry_phases` yields a set per
   entry; the one-phase arm becomes "the phases of one entry lie on one
   ancestor path, else refused with the empty-region reason";
   `_check_scoped_read_containment`'s region is the innermost phase's
   subtree; the diagnostic names the innermost phase as the region a
   call left; `descendant_redeclarations` still refuses the inner phase
   re-declaring an outer tail's name. Artifacts: the grid in
   `tests/test_phase_scoped_reads.py` gains the phase-set-shape axis
   (one / two nested inner-first / two nested outer-first / two nested with
   a top-level outer — cribbage's own shape / three on a path / two
   siblings / two cousins sharing an ancestor / the inner re-declaring
   the outer tail's name / binder x two phases / two nested beside
   game-level names / the same name under two tails) crossed with
   the call positions (inner body; the inner's qualifier / before_each /
   after_each — accept; a child of the inner — accept; outer body before
   or after the inner — REFUSED; the outer's qualifier / before_each /
   after_each — REFUSED; a sibling of the outer; game level, `winner:`,
   function — #518's cells unchanged; move type offered only inside the
   inner — accept; move type with one offer in the outer-outside-inner —
   REFUSED at that offer; procedure run inside / outside / both), authored RED
   before the arm changes; `test_two_phases_in_one_clause_are_refused`
   inverts into the nested-accept cell plus the sibling-refusal cell;
   the rejection corpus gains the non-path and outer-body sentences;
   #517 closes with cribbage as its witness (PR body: Closes #517).
4. Migrate cribbage per the stage recipe: the block (entry-grain reads
   derived from the bodies; tails per-read; signatures per
   `implementation_sig`), the `ROW` binding and three bundled arms deleted,
   five names to `DECLARED_ONLY_CALL_FUNCS`, consumer sweep (registries by
   name: `RANKING_GATED_FUNCS` per step 1; the joint codec table is not
   involved; `NARROWED`), the twin's prose re-read. The
   `peg_origin_of` clause names two nested phases under the lifted law of
   step 3b. Artifacts: full-width
   goldens byte-identical (`CARDLANG_GOLDEN_SEEDS=full pytest
   tests/test_migration_characterization.py -q`), the read oracle (every
   declared name read, nothing undeclared, planted controls both
   directions), a call census of all five sites under the declared regime,
   `tests/openspiel_ready/test_cribbage.py` untouched and green, the
   regime-product grid deriving five new members (a spelling/assignment
   row answered in the harness if it fails by name).
5. Prose sweep (assume a miss): every site in domain item 7; the enum
   docstring; the reads.py row comment; primitive-sidecars.md; the
   `test_primitives_block.py` ledger. Artifact: the prose-scraper set
   green (`tests/test_glossary.py`, `test_doc_references.py`,
   `test_assert_triage.py`, `test_ledger_referents.py`) plus a repo-wide
   grep for "site read"/"SITE_READ"/`_CRIBBAGE_R`/"pegging-scorer call
   sites" returning only dated artifacts.

## Delivery shape

One PR (operator merge; Codex is the operator's spend): steps 1-5 with
the reddening commit boundary preserved; PR body carries `Closes #473`
and `Closes #517` (commit bodies do not survive a squash) and `Part of
#142`. Chain: opus
implements -> adversarial review (Fable — the change lifts a ruled wall and
retires a partition member; the counsel-round precedent) with the differential
of goldens plus the read oracle reproduced independently -> fix round ->
PR -> CI -> Ben merges. After merge, coup's eviction is the last holdout
before the legacy-table deletion PR.

## Hoyle's counsel (2026-09-04) — lift the one-phase wall for NESTED phases (issue #517), Cribbage the witness (issue #473)

**Headnote.** One game, Cribbage, arrives at the wall Hoyle kept standing on 2026-08-30 with exactly the sentence that wall named as its unblocking witness, and the ruled sentence is, verbatim: `peg_origin_of(c : Card) : Player reads play_pile, seq_bits in play, seq_len in play, dealer in hand_sequence` — two phases in one reads clause, one nested inside the other, the entry callable only where the inner one runs. The law in the designer's words: *the phases a clause names must nest, one inside the next; the entry is callable only where the innermost of them runs* — no cap on depth, no meaning in the order the tails are written. The losing rival is the argument: `peg_origin_of(c : Card, d : Player)` with `peg_origin_of(card, dealer) is dealer` at three call sites — it needs no language change and resolves clean today (executed), and its cost is a phase constant hauled as an argument through three clauses that read as tautologies ("the origin of the card, given the dealer, is the dealer"). No grammar production moves, so this is not Merge Lane A by the letter — it is Lane B (resolve, glossary, a re-blessed rejection) with a Lane C corpus edit riding; Hoyle sits because a sentence the parser already accepts changes meaning, and the wall was Hoyle's own. Corpus: one game file moves — cribbage — witness-named; measured today, 10 of 10 tailed entries across 5 of the 11 block-carrying games name one phase each and none of them moves; after the lift 1 of 11 names two. One settled commitment is cut, by its own terms: the "at most one phase" wall falls for nested phases; its non-nested half stays as a designed constraint ("no place in the game runs both"), not a deferral, and the three neighbouring walls (a name the game and a phase both declare; function, define and rule bodies; offers from inside a move type or define) stand untouched. Information sets do not move — the tail is declaration-only, nothing new is emitted — proven by cribbage's full-width per-seed goldens byte-identical and its OpenSpiel proof module untouched. Hoyle's verdict: lift it, nested only, in the same change that migrates cribbage; the strongest reason against is that the nested case is easy precisely because it buys little — the outer tail carries no containment information, only which declaration `dealer` is, so the whole yield on the page is one declared word against three passed arguments — and its cost is a second clause in the law, a longer diagnostic, and an implementation-order hazard where lifting the arm before containment learns the innermost leaves a two-phase entry accepted and unchecked. What the operator must decide on the language half: whether the non-nesting refusal closes as a designed constraint with no issue, as counseled. The bottom line is the Architect's to write.

### 1. The sentences

In situ. `docs/games/cribbage.cardlang` gains its block (entry-grain reads derived from `cardlang/runtime/cribbage.py:167-180` and the authored row at `cardlang/runtime/reads.py:262-268`; the migration derives its sets from the module, never from this counsel):

```
primitives {
  peg_pair_points()  : Integer reads play_pile
  peg_run_points()   : Integer reads play_pile
  peg_origin_of(c : Card) : Player
      reads play_pile, seq_bits in play, seq_len in play, dealer in hand_sequence
  cribbage_show_value(p : Player) : Integer reads played[p], starter
  cribbage_crib_value() : Integer reads crib, starter
}
```

Read aloud: "peg_origin_of of a card is a Player; it reads the play pile, seq_bits and seq_len in play, and the dealer in hand_sequence." The three calls (lines 106, 117, 136) read `move all cards from play_pile where peg_origin_of(card) is dealer to played[dealer]` — "where who played the card is the dealer" — and all three sit inside `phase play` (65-149), which sits inside `phase hand_sequence repeat until ...` (53-150). `hand_sequence` declares `dealer` (55); `play` declares `seq_bits`, `seq_len` (69-70) and does not re-declare `dealer`.

**The law of the clause, as the designer reads it.** *The phases an entry's `reads` clause names must nest, one inside the next; the entry is callable only where the innermost of them runs.* Each read keeps its own tail — the tail still says which declaration is meant, per read, and the per-read spelling does not change; the innermost tail is the one that sets where the entry may be called. "Nest" rather than "any set, region = intersection, empty refused": the two are one rule — nested subtrees intersect in the innermost subtree, non-nested ones in nothing — but the designer reads the phase tree as nested braces and checks "do these nest" on the page by eye, while "intersection of regions" is the engine's derivation and belongs in resolve's Contract. Both sentences land, each in its home. Three on a path: the same sentence, no cap — a cap is a number with no witness — and the three-deep synthetic cell plays. Order: none. Executed 2026-09-04, both spellings of the cribbage entry (inner-first as above; outer-first `reads play_pile, dealer in hand_sequence, seq_bits in play, seq_len in play`) are refused today by the same arm with identical text, because `tailed` at `resolve.py:5378` is a set and `_phase_list` sorts — so order carries no meaning now and must carry none after. Recommend the inner-first spelling above (the game's own order: the pile, the provenance bits, the parity key); do not legislate it; the accept cells run both.

**Alternatives weighed and set aside.**

- *The argument (the rival):* `peg_origin_of(c : Card, d : Player) : Player reads play_pile, seq_bits in play, seq_len in play`; calls `peg_origin_of(card, dealer) is dealer`. Executed under the block regime: resolves clean — the only diagnostics left are #473's two SITE_READ refusals. Aloud: "where the origin of the card, given the dealer, is the dealer" — `dealer` twice in one clause, the decoded value compared against the very value passed in. The dealer is the decoding KEY of the provenance bits (`cribbage.py:174-180`, bit 1 = dealer), constant for the whole hand, not a per-call variable; passing it hauls a phase constant through three call sites and a Python signature. This is #517's own test — "passing the outer value as an argument reads worse than declaring it" — met on the page.
- *An entry-level region tail:* `peg_origin_of(c : Card) : Player in play reads play_pile, seq_bits, seq_len, dealer` — "runs in play; names resolve as a statement in play would". Coherent (it mirrors the runtime's innermost walk), but a new production (Lane A), and it trades the declaration model for a position model: bare names resolved up the path is inference, rejected 2026-08-30 for the silent-pick reason; the reader loses which declaration each name means; the IR row, the twin-facts tuple and the grid are all built per read. No witness wants it.
- *Hoist `dealer` to the game's `state { }`:* one phase in the clause, no lift. For cribbage specifically it is behavior-neutral — `hand_sequence` is a top-level phase entered once (`driver.py:346-347`), and `_declare_state` runs once per `run_phase` (455-457) before the repeat loop, so `dealer` already persists across hands — but it is the game bending to the instrument: `dealer` is the hand rotation's own state and the file says so ("the deal alternates", line 62), and the edit would owe a proof that the frame merge into the information state is unchanged by moving a name between frames. Rejected on the load-bearing rule.

Adjacency: nothing new — the production does not move; `, dealer in hand_sequence` is comma-delimited like every tail; `in play in hand_sequence` is the existing doubled-tail parse reject.

### 2. Precedent

- **The wall itself.** `resolve.py:5373-5386` — the per-entry arm, its comment ("One entry, one containment region ... Two regions would have to be intersected, which is issue #517") and its message. Hoyle's 2026-08-30 counsel kept it as one of three walls "each with a named unblocking witness" (`docs/plans/2026-08-30-phase-scoped-reads.md`, Headnote and section 6); #517's body names the witness — two phases on one ancestor path, argument reads worse. Cribbage is that sentence. The wall falls by its own terms, not by re-litigation.
- **The containment rule as ruled** (plan, "The construct, as ruled"): region = the declaring phase's subtree, `inside = {id(node) for node in _walk(phase)}` at `resolve.py:5843`. For nested phases the inner subtree IS the intersection; the rule generalizes with no new concept: region = the innermost named phase's subtree.
- **The ONE path-aware walk.** `primitives_block.py:447-478` `_phase_state_decls` yields the PATH of every declaring phase, and the module Contract (47-58) makes it the only walk that answers ancestry. "The tailed phases nest" is: their declaring paths are prefix-ordered; the innermost is the longest path. No second walk; the Contract forbids one.
- **The fourth predicate** `descendant_redeclarations` (511-533) is per read and per phase, and is what makes the innermost frame walk (`state.py:428-436`) correct under two tails: no named phase's name is re-declared below it, so from the innermost region every named name resolves to its declared frame. Unchanged.
- **Explicit tails, no inference** — settled 2026-08-30 (sibling phases may legally declare one name). Unchanged: a bare `dealer` beside `seq_bits in play` still meets the phase-local arm (5457-5472), which teaches `dealer in hand_sequence`.
- **The runtime is already multi-phase.** `declared_primitives` classifies each read with its own phase (`driver.py:129`) and carries `scopes` per read (158); `_scoped_state` (`reads.py:535-560`) renames a miss per name and phase. No runtime line assumes one phase per entry. The one engine site that does is `_scoped_entry_phases` (`resolve.py:5686-5714`): `dict[str, str]`, and `if len(named) != 1: continue` — a silent skip (section 6, the third against).
- **Glossary.** [[phase-scoped-read]] states the wall inside its definition ("one entry names at most ONE phase ... callable only where that phase runs"); the naming rules bind the rewrite; [[reads-clause]] and [[primitives-block]] are per read and stay true.

**What stays walled, and what each is.**

- *Two phases not on one path* (siblings; cousins sharing an ancestor) — a DESIGNED constraint, not a wall: `run_phase` pops a phase's frame when it ends (`driver.py:507`), so no place in the game runs both, and an entry reading from both could never be called anywhere. Nothing anyone would build makes it callable, so no issue; it records at the construct with a teaching reason (section 4).
- *The same phase twice on ONE read* (`x in play in play`) — the grammar's `[_IN_KW NAME]` admits one tail; the `doubled-tail` parse cell owns it; unchanged. *The same phase on two reads* (`seq_bits in play, seq_len in play`) — executed control: accepted today; unchanged, and now the ordinary shape. *The same NAME under two tails* (`trump_suit in outer, trump_suit in inner`) — executed: the repeat guard (5364-5372) speaks first, "reads `trump_suit` more than once"; correct to refuse (the bundle is keyed by bare name — `gr.state[name]` holds one value); its wording "names each declaration at most once" is slightly off for two declarations ("each spelling") — a message, not a law; the Architect's.
- *The inner phase re-declaring a name the outer tail names* — executed: today the per-entry arm fires first and the descendant arm never speaks. After the lift `_check_read_tail` runs per read (5454) and the descendant arm (5553-5562) fires for `trump_suit in outer`: "phase `inner` inside `outer` declares `trump_suit` too — at run time the innermost frame wins ... rename one of the two" — which reads right with two phases in play because it is about one read. The grid carries this cell red-first: it is refused today for the wrong reason, and its accept twin (the re-declaration removed) plays.
- *#516* (game-and-phase shadow, phase-and-zone) — per read at 5404-5453, ahead of the tail arms; unchanged; re-probe each WITH two tails present. *#518* (function, define, rule bodies) — `_CONTAINMENT_BY_GAME_FIELD` (5653-5685) is about the call's container, not the region; unchanged. *#521* (offers from a move type's or define's body) — `_UNPOSITIONED_CONTAINERS` (5760-5767); unchanged. The ledger says so in words.

### 3. Corpus impact

Derived 2026-09-04 over every `primitives { }` block in `docs/games/*.cardlang` (11 games carry one: belote, canasta, five-hundred, french-tarot, gin-rummy, holdem, holdem-heads-up, pinochle, seven-card-stud, skat, tichu). Tailed reads: canasta (4 names, all `in hand`, over 5 entries), french-tarot (`taker`, `bid_level` `in hand_sequence`, 1 entry), holdem (`in_hand`, `committed`, `folded` `in play`, 1 entry), pinochle (`trump_suit in hand_sequence`, 1 entry), seven-card-stud (`folded`, `committed`, `in_hand` `in play`, 2 entries) — the thirteen phase-declared names of the #504 rows, confirmed; 10 of 10 tailed entries name exactly one phase. Belote, five-hundred, gin-rummy, holdem-heads-up, skat, tichu carry no tail. After the lift exactly one corpus entry names two phases: cribbage's `peg_origin_of`. Lockstep: ONE game file moves. `cribbage.md` is a link-shape twin with no fence (no code fence in the file; `test_twin_block_agrees_with_the_cardlang` pairs fenced twins only), and its prose (31-33) naming `peg_origin_of` as the decoder stays true. The remainder of the change is #473's own: the two SITE_READ scorers normalized onto `impl(facts, gr)`, the `_CRIBBAGE_R` row and the three `runtime/primitives.py` arms (126-153) deleted, the `reads.py` rows at 262-268 and 293-297 gone with them — the Architect's and the 3b recipe's.

Prose sites stating the one-phase law — every site the sweep found (grep over `cardlang/`, `docs/`, `tests/` for "at most one phase", "one phase's", "not one place", "two phases", "callable only where that phase runs"); assume a miss and re-sweep after the edit:

1. `resolve.py:5373-5386` — the arm, its comment and message.
2. `resolve.py` Contract 106-116 — "one entry's clause names at most one phase, and every call of that entry sits inside the named phase's subtree" -> "the phases one entry's clause names nest, and every call sits inside the innermost's subtree".
3. `resolve.py:5686-5714` — `_scoped_entry_phases` docstring, "the ONE phase its reads clause scopes to".
4. `resolve.py:5896-5903` — `_outside`, "callable only where that phase runs — this call is in another phase" (the register, section 4).
5. `cardlang/grammar/cardlang.lark:117-122` — comment "a clause legitimately mixes game-level names with one phase's" -> "with a phase's" (it describes the per-read rationale; after the lift "one phase's" reads as the law).
6. `docs/glossary/phase-scoped-read.md` line 3 — "one entry names at most ONE phase. In exchange the entry is callable only where that phase runs" -> the nest-and-innermost sentence; `docs/glossary.md:134` regenerates from it.
7. `tests/test_phase_scoped_reads.py` — ledger `domain:` (100-104, "two distinct phases in one clause"), `walls:` (131-136: #517 leaves DEFERRALS; the non-nesting refusal joins DESIGNED with its reason), the two cells at 538-567 (the sibling pair stays a refusal with a new expected text; the nested pair becomes an accept cell that PLAYS), the floors at 1286-1296.
8. `tests/rejections/primitives_scoped_read_two_phases.{cardlang,expected}` — a sibling pair (`outer`/`later`): the `.expected` re-blesses, the `.cardlang` header comment (1-3) rewrites; `tests/test_rejections.py:107`'s case list stays true.
9. `docs/design-notes/primitive-sidecars.md:332-345` — "commits the entry to being called only where that phase runs" (singular; exploratory lane, reword when touched).
10. Issue #517 — closes with the change; its "callable wherever BOTH phases are running" is the innermost region in other words.

Sites that stay true per read and need no edit: `driver.py:113-118` and `reads.py:541-548` ("the declaring phase's subtree" — true of each tail, since the innermost region lies inside every named phase's subtree); `primitives.py:88-94` (`Declared.scopes`); `primitives_block.py:497` ("a tail names one phase" — name uniqueness, not the clause law); `docs/glossary/reads-clause.md`; `docs/library.md:383-390`. `decisions.md` and `CLAUDE.md` carry no site.

### 4. The totality edge

The grammar accepts nothing new; what changes is which parsed clauses resolve. Axes for the Architect to derive in code:

- **Phase-set shape** (per entry): one (the existing grid, unchanged) | two nested, inner-first | two nested, outer-first | two nested where the outer is a top-level phase (cribbage's own shape) | three on a path | two siblings | two cousins (share an ancestor, neither inside the other) | two nested, the inner re-declaring the outer tail's name | binder x two phases (`stage[p] in play, dealer in hand_sequence`) | two nested beside game-level names | the same name under two tails.
- **Call position x the nested pair:** inner body (accept) | inner's qualifier, `before_each`, `after_each` (accept — `run_phase` pushes and declares before any of them, 446-457) | a child of the inner (accept) | outer body, before or after the inner (refuse) | outer's `before_each`, `after_each`, qualifier (refuse) | a sibling of the outer (refuse) | game level, `winner:`, function (refuse — #518's cells, messages unchanged) | move type offered only inside the inner (accept) | move type with one offer in the outer-but-outside-inner (refuse at that offer) | move type offered inside the inner AND in the outer's body (refuse at the outer offer) | procedure run inside the inner (accept) | run in the outer-outside-inner (refuse) | run both sides (refuse at the outside run).
- **The standing arms x two tails:** #516's shadowed pair, the phase-and-zone pair, the pure-entry guard, the repeat guard — each re-probed with two tails present so the lift cannot loosen them silently.

Accept cells PLAY (cribbage carries the corpus accept; the synthetic nested probe on `pinochle_meld_value` carries the rest, the borrowing precedent); every refusal ships with its accept twin.

**Misuse sentences a designer would actually write, each loud in its layer:**

1. `reads dealer in hand_sequence, seq_bits in play`, called from `hand_sequence`'s `before_each` — the outer tail read as a licence -> containment (resolve), naming `play` and the read that binds it.
2. `reads seq_bits in play, dealer in play` — the plausible guess -> the wrong-declarer arm (5540-5551): "phase `play` declares no state `dealer` — phase `hand_sequence` declares it".
3. `reads seq_bits, seq_len, dealer in hand_sequence` — the list-scope misreading -> the phase-local arm teaches `seq_bits in play`.
4. `reads seq_bits in play, dealer in show`, `show` a sibling of `play` -> the non-nesting refusal.
5. `reads seq_bits in play in hand_sequence` -> parse (doubled tail).
6. `reads seq_bits in play, dealer in hand_sequence, dealer` -> the repeat guard.
7. `reads dealer in hand_sequence` alone, called from `play` — accept (the existing descendant-phase cell; unchanged).

**The register** (proposed sentences; the Architect owns the pins):

- *Outer body outside the inner:* "`peg_origin_of` reads `seq_bits in play`, so it is callable only where `play` runs — this call is in `hand_sequence`, which encloses `play` but runs outside it (`play`'s state does not stand here); move the call inside `play`, or pass the value as an argument." Name the innermost phase by role and the read that binds it; never list both phases as if both were the region.
- *Not nested:* "`pinochle_meld_value` reads `trump_suit in outer` and `extra in later`, and `outer` and `later` do not nest — no place in this game runs both, so the entry could never be called; keep one, and pass the other value as an argument or declare it in the game's `state { }`." Drop today's "split the entry": for siblings the split is no fix, since the caller needs both values in one place that does not exist.
- *Wrong order:* no sentence, because no order is wrong.
- Executed on the existing `ancestor-phase` cell: a ONE-phase entry called from the parent phase is told today "this call is in another phase, which runs outside it" — a misregister for the enclosing case already. Fix it in the same change: "in `top`, which encloses `outer` but runs outside it".

### 5. The info-set bound

The tail is declaration-only surface; the lift changes which programs are accepted, not what any accepted program emits. No observation site touches a `reads` clause; the IR row (`ir.py:174-177`) already carries `phase` per read and its shape does not change. Proof: `CARDLANG_GOLDEN_SEEDS=full pytest tests/test_migration_characterization.py -q` byte-identical on `tests/golden/cribbage_hands.json` (a change under `docs/games/` sweeps full width and regenerates nothing), and `tests/openspiel_ready/test_cribbage.py` untouched. The migration half re-routes `peg_pair_points`/`peg_run_points` from the site-read arm to the bundle — same zone, same freeze; the goldens are the proof, and a read the declaration omits fails typed (`PrimitiveReadError`) in the playout rather than silently. No debt to record.

### 6. Counsel

**For:** the witness meets the wall's own unblocking sentence exactly; the lift adds no concept — region = the innermost subtree, the same `_walk(phase)` — and the runtime needs no line changed; the sentence reads as the game ("who played the card is the dealer"); the reads clause stays the coupling declaration (`dealer` IS read, and the block says so); explicit tails stand; every neighbouring wall stands.

**Against, strongest:** the nested case is easy precisely because it buys little. The outer tail carries no containment information — only which declaration `dealer` is — so the entire yield on cribbage's page is one declared word (`dealer in hand_sequence`) against `, dealer` at three call sites and one Python parameter; the rival is zero language change and resolves clean today. Second: the wall was one clause ("at most one phase"); the rule becomes two ("nest; innermost"), and a designer can misread the outer tail as a licence to call from the outer phase — the register answers it, at the price of a longer diagnostic and one more glossary sentence. Third, the implementation-order hazard: `_scoped_entry_phases` skips a multi-phase entry silently (5703-5704); lift the arm at 5379 before it returns the innermost and a two-phase entry passes containment vacuously — accepted and unchecked, the worst class this project names. The outer-outside-inner refusal cell, authored red first, is what closes it.

**What Hoyle would do:** lift the wall for nested phases only, by the nest-and-innermost law, in the same change as cribbage's migration (witness-in-change; the construct never exists corpus-unused); keep the non-nesting refusal as a designed constraint with the "no place runs both" reason and no issue; keep #516, #518 and #521 standing and re-probe each with two tails; rewrite the ten prose sites, re-bless the two-phases rejection, and fix the ancestor-case register while there; hand the Architect the axes above with the accept cells playing and the nested-redeclaration cell red-first; close #517 with the change.

### 7. Must-survive facts (Hoyle's seat)

The ruled sentence: `peg_origin_of(c : Card) : Player reads play_pile, seq_bits in play, seq_len in play, dealer in hand_sequence`. The losing rival: `peg_origin_of(c : Card, d : Player)` with `peg_origin_of(card, dealer) is dealer` at three sites. Lane: not A by the letter (no `.lark` change) — B by the supremum. Corpus: one game file moves, cribbage, witness-named; 10 of 10 tailed entries elsewhere stay as they are. Commitment cut: the one-phase wall, for nested phases, by its own named witness; its non-nested half becomes a designed constraint. Info sets: do not move — cribbage's full-width goldens and its untouched OpenSpiel proof. The operator decides, on the language half, only whether the non-nesting refusal closes without an issue; the bottom line is the Architect's.

## The Architect's counsel (2026-09-04 — issues #473 and #517, one change; composes with Hoyle's counsel of the same date, which binds the language half throughout)

**Headnote.** The decision is narrower than "lift the wall": it is what data structure carries an entry's scope once it can name more than one phase, where the question "do these phases nest, and which is innermost" is answered, and in what order the refusal, the containment analysis and the grid land so that no state of the tree ever accepts a two-phase entry unchecked. The settled law, in plain words: scope facts are the resolver's and are settled before procedures are spliced; the one path-aware walk over the phase tree lives in the block's registry module and nobody else may walk for ancestry; the runtime resolves a name against the innermost standing frame and stays that way because a descendant re-declaring a scoped name is refused at compile; a refusal arm no input can reach is a check that cannot fail; and a wall's "at most one phase" was written with its own escape clause — the region was always "the named phase's subtree", and two nested subtrees intersect in a subtree of a named phase, so the rule generalizes with no new concept. Executed today: cribbage's provenance state sits on one path (the dealer one level up, the sequence bits one level down); both spellings of cribbage's entry are refused by one arm with identical text, so order carries no meaning now and must carry none after; every one of the 10 of 10 tailed entries across 5 of the 11 block-carrying games names one phase, and each stays exactly as it is; with the refusal arm lifted and NOTHING else changed, a two-tail entry called inside the inner phase resolves, plays, and receives both names in its bundle, a three-deep chain plays, and calls from the inner phase's own hooks play — the runtime needs no line — while a two-tail entry called from the outer phase's body, from the outer phase's hooks, or a sibling-pair entry called anywhere, all check CLEAN and then crash at playout inside the runtime's shadow guard naming resolve as the owner: the accepted-then-crashes class, reachable by any designer, which is why the containment analysis must learn the innermost before the arm moves and why the outer-side refusal cells are committed red first. The option recommended: one predicate beside the walk answers nesting and innermost for any phase set, the one-phase entry becoming the degenerate chain rather than a special case; containment's region is the innermost's subtree; the non-nesting set is refused at entry grain after every tail has validated, with Hoyle's "no place in this game runs both" sentence and no issue, because the runtime pops a phase's frame when the phase ends and nothing anyone would build makes such an entry callable — one born-green pin on that pop turns the comment the constraint rests on into a checked fact; the outer-side diagnostic names the phase the call sits in and derives "encloses" from the same paths, which also fixes the existing misregister for a call in an enclosing phase. Rejected: intersecting per-read regions inside the resolver (a second ancestry derivation, an empty region for the sibling case that names no place to move to), and landing the lift before containment learns the innermost (the vacuous window, now executed). For #473's engine half: the site-read contract retires with its cells and the enum's prose stops counting; the pure scorers survive as cores beside registered bundled adapters so the known-hand tests stay callable and the rank-index control pair holds by construction; the equivalence between the site's frozen pile and the bundle's held at 176 of 176 pegging calls at seed 0 (the framing check's 648 of 648 across 3 seeds), and cribbage played through the block, with both halves of the change simulated, matched the legacy path at 5 of 5 seeds and 62 of 62 per-hand score vectors — after the merge the site no longer exists, so the goldens at full width and the bundle-immutability grid own the claim going forward, and the read oracle runs once as a scratch instrument because the module-union scan cannot see a per-entry over-declaration. Two plan corrections found by execution: the ranking gate already lists the run scorer and its derived-readers pin already counts it, so the plan's "gains" and its step-one reddening claim are false; and the engine-core pin's literal name set equals the auction-outcome registry today, so both its sides derive rather than being re-typed. Newly impossible, for designers: an entry naming phases that do not nest, and a call of a nested-scope entry anywhere outside the innermost phase's extent (the enclosing phase's own body and hooks included); newly required, for the implementer: the cells red before any resolver edit, the innermost learned before the arm moves, two takes recorded, and one pin on the frame pop. Information sets do not move — declaration-only surface, nothing new emitted; the full-width goldens and the untouched proof module are the proof. Precedent standing: every citation below is established (P2, P6, P7, P9, P11, P13, and P1 for the one pin); no unverified lead is relied on. Bottom line: lift it as Hoyle ruled, on the machinery ruled here, in the same change as cribbage; the strongest reason against, from Hoyle's seat and carried here, is that the nested case is easy because it buys little — one declared word against three passed arguments — and its price on this side is a nesting predicate, a phase-path table for every phase, an enclosure-aware diagnostic, and a grid, all for one corpus entry; the seats agree on every material point, and the operator decides one thing: that the non-nesting refusal closes as a designed constraint with no issue.

### 1. The decision

Not whether the wall lifts, nor what the sentence means — Hoyle ruled both. The engine choices:

(a) After `tailed` at `resolve.py:5378` stops being a singleton, what carries an entry's scope; where "nest, and which is innermost" is answered (the Contract at `primitives_block.py:47-58` already forbids a second ancestry walk); and the red-first order that closes the window in which `_scoped_entry_phases` (`resolve.py:5686-5714`) silently skips a multi-phase entry.
(b) What data the outer-side diagnostic carries, and where "encloses" comes from — including the existing misregister for a call in an ENCLOSING phase.
(c) Whether any runtime line assumes one phase per entry, and whether every ancestor frame is live when the innermost runs.
(d) The fourth predicate (`descendant_redeclarations`, `primitives_block.py:511-533`) and the repeat guard under two tails.
(e) #473's engine half: the contract retirement, the frozen-pile equivalence's owner, the helper split, the five consumer pins the framing check surfaced, and the ranking gate.
(f) The grid's derivation and its two-take record.
(g) The Contract lines that change.

### 2. The law

- **resolve's Contract** (`resolve.py:106-116`): a phase-scoped read is "a SCOPE fact, not a type fact, so it is settled here; and necessarily before `expand`". The clause that moves is its own: "one entry's clause names at most one phase, and every call of that entry sits inside the named phase's subtree". Read with the containment code (`inside = {id(node) for node in _walk(phase)}`, `resolve.py:5843`), the region was defined as a subtree; for phases on one path the intersection of their subtrees IS the innermost's subtree, so the law extends by its own terms. Not re-litigated.
- **primitives_block's Contract**: "the one path-aware walk is here"; illegal after it, "any consumer walking phase state blocks itself to answer a scope or ancestry question". This decides WHERE nesting is answered. Executed: `_phase_state_paths(cribbage)` yields `('hand_sequence',)` for `dealer` and `('hand_sequence', 'play')` for `seq_bits`/`seq_len` — the prefix order is the nest.
- **The four rulings of 2026-08-30** (my own; `docs/plans/2026-08-30-phase-scoped-reads.md`): the phase rides as a field and a classifier parameter, never a `ReadKind`; the containment guard is resolve's own check after block validation and before expand; `rs.get`'s innermost walk is unchanged and correct under the fourth predicate; the premise pin over `move_type_index` readers prices the runtime premise. All four stand; the lift touches none of them.
- **decisions.md, "Closed-domain completeness"**: a refusal arm no input can reach is a check that cannot fail (the contract member); "vacuously green" ranks with "accepted-but-ignored"; `xfail(strict=True, raises=...)` over `skip`; the grid's expected column authored red before the implementation; "Prose names the registry, never the cardinality" (the enum docstring counts today — "The other two are refused BY NAME").
- **decisions.md, "Reachability ranks the work"**: the vacuous window is R2 — a designer writing the outer-body call meets a checker-green sentence that crashes — which is why it may not exist on any commit, not merely on the merge.
- **reads.py's Contract** and `_scoped_state` (`reads.py:535-560`): the scoped miss is a Shadow Guard naming resolve's containment check as Owner. Executed under the shim: the window's failure lands in exactly that channel — "phase `inner` is not running here, which resolve's containment check ... is the Owner Guard for".
- **The runtime fact the designed constraint rests on**: `run_phase` (`driver.py:446-507`) pushes, declares, runs qualifier/hooks/body, and pops in a `finally`; a phase's frame does not outlive its extent, so no position runs two phases that do not nest.
- **The frozen-pile boundary**: the narrowing ledger's (d') clause names the two peg arms as direct sites; `test_peg_direct_arm_args_are_frozen` proves the SITE's freeze and cannot survive the change.

### 3. Precedent

- **P2** (materialize in the owning pass): the chain and its innermost are derived once, in the leaf, and stamped on the scoped-entry record resolve carries — no consumer re-derives which phase is the region.
- **P6** (blessed snapshots): three fixtures re-bless — `primitives_scoped_read_two_phases` (the designed refusal), `primitives_scoped_read_called_outside` (the phase named), and the new outer-body sentence.
- **P7** (addressee, span, applicability): the outer-side refusal names the phase the call is IN and the read that binds the region; span at the call.
- **P9**: no grammar production moves; the position taxonomy's derived pins stand untouched.
- **P11** (an oracle is trusted after it catches a planted fault): the two-take record's second take is the vacuous state itself, and the outer-side cells must be red in it for the right reason.
- **P13**: declared-once, emitted-uniformly is untouched — the tail emits nothing.
- **P1** (a contract that matters is a checked artifact): the "no place runs both" sentence is a comment on `run_phase` today; the one pin below is the rung above a comment. Not a standing tension — the law and the pin agree.
- House precedent: the 2026-08-30 grid's two-take docstring record; `test_state_default_scope`'s played-cells lesson; `_scoped_entry_phases`' own assert ("that two walks agree is the argument FOR asserting it, not for assuming it"); the reconcile carve-out's per-row derivation (3b).

### 4. The options

**(a) The containment machinery.**

*A — counseled.* In `primitives_block`: one recursion over the phase tree yields `(path, phase)` for EVERY phase, declaring or not; three views derive from it — `phase_paths(game) -> dict[str, tuple[str, ...]]`, `phase_names` (its key set; today a separate recursion, retired), and `_phase_state_decls` (the declaring subset, unchanged in shape). Beside it, `phase_chain(game, phases: frozenset[str]) -> tuple[str, ...] | None`: the phases ordered outer to inner when their paths are prefix-ordered, `None` otherwise; `()` for the empty set, `(p,)` for a singleton. In `resolve._check_primitive_reads`: `tailed` is built AFTER the per-read loop from the reads whose tails validated (the collision arms and `_check_read_tail` already `continue` per read; a flag records whether every tailed read passed), and the entry-grain arm becomes: `phase_chain(game, tailed) is None` -> Hoyle's refusal, listing the reads by phase (`_phase_list` stays as the renderer; sorted order is fine in a designed refusal). The arm moves from before the per-read arms to after them because a misspelled tail has no path — asking "nest?" first would co-report. `_scoped_entry_phases` returns `dict[str, _ScopedEntry]`, a frozen dataclass of `chain` (outer to inner), `region` (`chain[-1]`), and `binding` (the first read in clause order whose tail is the region — clause order for determinism, carrying no meaning); it skips an entry exactly when the arm refused it or a tail failed (the co-report rule, unchanged), by asking the SAME predicate, so the arm and the analysis cannot disagree — the existing assert's argument. The region is `_walk(region)`. No `len == 1` branch survives: the 10 of 10 one-phase entries run the same path as cribbage's. Executed under the shim: the nested pair, the three-chain and the inner hooks all play with no runtime edit (B1, B3, B4).

*B — rejected: intersect per-read regions in resolve* (`inside = intersection of _walk(p)`). It computes the same set for a nest, but it is a second ancestry derivation in the wrong module; for a sibling pair it yields an EMPTY region, so every call is refused with "callable only where X runs" naming no place the designer can move to — the wrong register; and the message cannot name the innermost without deriving it anyway.

*C — rejected: lift the arm and let `_scoped_entry_phases` keep skipping.* Executed (B2, B5, B7): the outer-body call, the outer-hook call and the sibling pair each check CLEAN and crash at playout in the shadow guard's channel. The defect class this project names as its worst; it may not exist on any commit.

**The red-first order.** (0) The new cells committed red against main: the nested-accept cells (refused today by the old arm), the outer-body and outer-hook refusal cells with the new fragments (the old message lacks them), the sibling cell with the "do not nest" fragment, the inner-re-declares cell with the descendant arm's fragments (today the per-entry arm speaks first — A7), and a two-tail co-report cell (one tail misspelled -> one diagnostic, never "do not nest"). (1) `phase_paths`/`phase_chain` land with their unit cells. (2) `_scoped_entry_phases` becomes chain-aware — the arm still refuses, so nothing observable changes and the cells stay red on the old message. (3) The arm is replaced by the nest arm after the per-read loop; `_outside` gains the enclosure data; the cells flip. Step (3) before (2) is the forbidden order. The take-2 measurement is taken in the working tree between (0) and (2) by lifting the arm alone; it is quoted dated in the module docstring and is never a commit.

**(b) The diagnostics' data.** *A — counseled.* `_check_scoped_read_containment` builds once, beside `_statement_owners`, a position attribution `phase_of_node: dict[int, str]` — for each phase in tree order, every node of `_walk(phase)`, deeper phases overriding — which is a position question (resolve's, like `inside`), not an ancestry one. The ancestry is asked of `phase_paths`: for a call in phase Q outside the region R, "in `Q`, which encloses `R` but runs outside it (`R`'s state does not stand here)" when Q's path is a proper prefix of R's, else "in `Q`, which runs outside it". `_outside` gains the binding read and the region: Hoyle's sentence, "reads `seq_bits in play`, so it is callable only where `play` runs". This is what fixes the ancestor misregister (executed A5: "this call is in another phase" for the enclosing phase) — the same data answers both. The offer and run-site messages keep their shape (`reads state declared in phase R` is true, and R is the region), fed from the same `_ScopedEntry`, and the nested-pair offer cells prove the phase they name is the innermost. Non-declaring ancestors are the reason the walk must yield every phase's path: in the existing ancestor cell `top` declares nothing. *B — rejected: keep "in another phase".* The misregister stands and gets worse with an enclosing phase in play.

**(c) The runtime.** Read and executed: `rs.get` (`state.py:428-436`) walks frames innermost-first per name; `run_phase` pushes and declares before the qualifier and hooks and pops in `finally`, nesting through Python recursion, so when the innermost runs every ancestor's `run_phase` is still on the stack with its frame pushed; `declared_primitives` (`driver.py:129, 158`) classifies and scopes per read; `_scoped_state` renames a miss per name and phase; `narrowing.bind` passes `scopes` through. No line assumes one phase per entry. Correctness under two tails is the fourth predicate applied per read: an intermediate phase on the path re-declaring the outer tail's name is a strict descendant of the outer phase and is refused, so each tailed name resolves to its own declaring frame. Unchanged and said so: the IR row (`ir.py:174-177`, `phase` per read), `_block_facts` (per-read tuple carries the tail), the premise pin (about move-type bodies, untouched), `Declared.scopes` (per read). Aside the change does not own: `GameResult.hands_played` reads 0 for cribbage in BOTH regimes while `hand_end` fires ~12 times per game (62 over 5 seeds) — two counters disagreeing, for triage, not this PR.

**(d) The fourth predicate and the repeat guard.** Executed: today the per-entry arm speaks for the inner-re-declares case (A7); with the arm lifted the descendant arm speaks with the right sentence (B6) — the cell is authored red against the fragments "inner", "declares `trump_suit` too", and at take 2 it flips green because its owner is the per-read arm, which the record says. Add its converse as an accept cell that PLAYS: the tail names the descendant and an ANCESTOR also declares the name — the innermost walk returns the descendant's value, matching the declaration, and the ancestor's variable stays readable by an entry callable outside the descendant (unlike the game-level pair, which is why #516 stays refused). The same NAME under two tails is the repeat guard by name (A6); its wording changes to "names each spelling at most once — the bundle is keyed by bare name, so two declarations of one spelling cannot both be carried; keep one". Law unchanged; the cell pins "more than once".

**(e) #473's engine half.**

- *The contract retirement.* The enum member goes; `undeclarable_contract` and `DECLARABLE_CONTRACTS` are unchanged in code; resolve's citation branch collapses to the EMITTING citation (#142); the per-name refusal grid derives one cell (coup); `test_the_declarable_contracts_are_a_proper_subset` stays non-vacuous through EMITTING and reddens the day coup is evicted — the right red, at which point the allow-list is total and the arm retires with it. The enum docstring stops counting: "every member outside `DECLARABLE_CONTRACTS` is refused BY NAME at resolve" — the registry, not "one".
- *The frozen-pile equivalence.* Executed by me at seed 0 (176 of 176 calls, site tuple equal to bundle tuple, same type) and by the framing check (648 of 648, 3 seeds). After the merge the site does not exist, so no pin can compare against it; the standing owners are `CARDLANG_GOLDEN_SEEDS=full` over `cribbage_hands.json` (outcome, 50 seeds) and the bundle-immutability grid in `test_primitive_narrowing.py` (shape and freeze, by derivation once the two are ordinary bundled Primitives). The one-call probe is a dated measurement in the PR body. The read oracle is owed once, as a scratch instrument: `_declared_for_module` compares the module-wide UNION, so a per-entry over-declaration (#534's class) is invisible to it, and the oracle's per-entry run is the only instrument that sees it. `test_peg_direct_arm_args_are_frozen` retires with the site; ledger (d')'s "the two cribbage peg arms" half rewrites.
- *The helper split.* The registered attributes are the registered names — `peg_pair_points(facts, gr)` and `peg_run_points(facts, gr)` — each spelling `gr.singles["play_pile"]` literally (the module-source scan keys on the literal) and the run adapter passing `facts.rank_index`; the cores keep their pure signatures under new names (`peg_pairs(seq)`, `peg_run(seq, order)` or the like — not registered names), and each adapter calls its own core. `_rank_index_readers` walks the call closure by bare name within the home module over `inspect.getsource`, a substring match over docstrings included: the pair adapter and its core name `rank_index` nowhere, docstring included, and the two adapters share no helper that names it — that is what makes the control pair (`test_the_rank_index_scrape_sees_a_reader_and_separates_two_file_mates`) hold by construction rather than by luck. `tests/test_playout_cribbage.py` and `_drive_peg_run_points` rebuild: the former on the cores, the latter on the bundle shape (`_drive_president`'s precedent) so the adapter's pass-through of `facts.rank_index` is what reaches `rank_strength`'s typed refusal.
- *The ranking gate.* Executed (A8): `peg_run_points` is ALREADY in `RANKING_GATED_FUNCS` and ALREADY in `_rank_index_readers()`; `peg_pair_points` is in neither. The plan's Gate 2 "gains `peg_run_points`" and its step-1 claim that the derived-readers pin reddens are both false — strike them; the membership is unchanged and the only pin that can redden on this axis is the control pair, under a wrong helper split.
- *`_LEGACY_HALF_NAME`.* Executed (A9): the legacy half after migration is exactly `{coup_game_summary}`, whose signature is `() -> Integer` (the same shape the cells render today). The representative becomes that name (the literal-plus-guard design stands; its guard reddens when coup leaves). The cell `("legacy-arm too", "block declares it")` has no admissible representative: `xfail(strict=True, raises=DiagnosticError)`, reason naming the contract refusal and the reddening event — coup's eviction under #142 empties the half, `_homes()` derives no cells, and `test_the_legacy_half_representative_still_has_a_legacy_arm` reddens, which is when the legacy axis retires whole. The plan's decision, ruled; restating the axis for a state the deletion PR ends is rejected.
- *`test_engine_core_game_knowledge_is_named`.* Executed: `_ENGINE_CORE_GAME_KNOWLEDGE == PRIMITIVE_AUCTION_OUTCOMES` today, and the corpus games whose `AuctionRound.outcome_fn` names a member are exactly bridge, french-tarot and pinochle. Derive both sides: the name set from `PRIMITIVE_AUCTION_OUTCOMES`; the expected row set from the corpus's auction-outcome slots crossed against the rows whose module is the shared dispatch module. The vacuous shape to refuse: rows compared with rows.
- *The fuzz fixture.* The finding is the deleted pegging move, not the regime; the frozen file gains the block (with the two-tail entry — the fixture depends on this same change) and a present-tense header line stating the block is the declared regime's requirement and the reproduction is the missing move. Retiring the finding is rejected: it is the non-termination class's only carrier.
- *The six zone-family cells and the primitives test.* The stud-selectors precedent (the fixture declares its entries, with a `play_pile` zone so the declaration is honest); `test_cribbage_primitives.py` binds through `driver.declared_primitives` (the gin precedent). `MIGRATED` gains the two peg names; `NARROWED` drops `cribbage.py::ROW`.

**(f) The grid frame.** Two derived axes and one authored crossing. The **phase-set-shape axis** derives in code from an AUTHORED path table of the synthetic fixture (top > outer > inner, with `later` a sibling of outer and `cousin` under `later` — independent of `primitives_block`'s walk): every subset of at most three phases, classified chain / not-chain by prefix order, is run through the resolver, and every accepted subset PLAYS with the call in its innermost; the pin asserts the set of isomorphism classes those subsets realise equals the classes Hoyle's authored shape rows name (singleton, adjacent pair, skip-level pair, top-level-outer pair, three-chain, sibling pair, cousin pair, mixed triple) — the derivation that keeps the authored list checkable. The **position axis** is the existing containment taxonomy (its `n.Game`-field and `PhaseItem` pins already derive total); it is crossed in full with cribbage's shape (nested pair, top-level outer): inner body, inner qualifier/before_each/after_each, a child of the inner, outer body before and after the inner, outer qualifier/before_each/after_each, sibling of the outer, game level, function, move type offered only inside the inner, one offer outside, offers both sides, procedure run inside/outside/both; and sampled at inner and outer for the three-chain. Composition rows ride beside: binder x two phases, two nested beside game-level names, the same name under two tails, the inner re-declaring, the ancestor also declaring (accept), the two-tail co-report; the standing arms (#516's pair, phase-and-zone, the pure guard, the repeat guard) re-probed with two tails. Witnessed by cribbage: the corpus accept, the outer-is-top-level shape, three call sites inside the innermost, the show entries reading no phase name. Born green with named reddening mutations: the class-derivation pin (red under adding a fourth level to the fixture table without a shape row), the `phase_paths` non-declaring-ancestor pin (red under deriving paths from the declaring walk alone), and the frame-pop pin (red under dropping `run_phase`'s `finally: pop_frame`). The full played product over the fixture (roughly 234 cells) is rejected on proportion — this is Hoyle's against-case priced in test time — and a hand-listed shape axis with no derivation is rejected as the axis that goes stale silently. **The two-take record**, dated in the module docstring: take 1, the new cells against main (accepts red as refused; refusals red on the old message); take 2, the arm lifted alone in the working tree (accepts green; outer-side and sibling refusals red as DID NOT RAISE — the proof they see the window; the inner-re-declares cell green, its owner being the per-read arm).

### 5. What becomes illegal after — the Contract deltas

- **resolve** (`Now illegal`, the phase-scoped clause): "...no STRICT DESCENDANT of it re-declares the name, the phases one entry's clause names lie on ONE ancestor path — their subtrees nest, and the entry's region is the innermost's subtree, the intersection of the named subtrees — and every call of that entry sits inside that region, or in a game move type every offering mention of which does, or at a `run` site that does". `runtime/driver` may therefore assume every named phase's frame stands, and holds its name, at every admitted call. Illegal after: an entry whose tails name phases not on one path reaching containment; containment deciding the region from anything but the leaf's chain.
- **primitives_block** (`Establishes`): "the ONE path-aware walk of the phase tree (`phase_paths`), from which the phase attribution, the ancestry predicate and the nesting question (`phase_chain`) derive". (`Now illegal`): "any consumer walking the phase tree itself to answer a scope, ancestry or nesting question — the one path-aware walk is here"; a position attribution (which phase's extent holds a node) stays resolve's, via `_walk`. The `InvocationContract` docstring: the registry sentence above, no count. The partition pins re-derive with the member gone.
- **reads.py**: unchanged in law; `_scoped_state`'s docstring may say "inside every named phase's subtree" — true per read either way.
- **driver**: `declared_primitives`' totality claim stays true ("every call of an entry with an `in <phase>` tail sits where that phase's frame stands" — per tail); `run_phase`'s order comment gains nothing but a pin citing it: after `run_phase` returns, `len(rs.frames)` equals its value before the call.
- **ir.py, `_block_facts`, `Declared.scopes`, the premise pin**: unchanged, and the ledger says so in words.
- **Prose**: Hoyle's ten sites plus, from this seat, the enum docstring's count, ledger (d') in `test_primitive_narrowing.py`, `_scoped_entry_phases`' docstring, and `_outside`'s sentence; the two `.expected` files re-bless; `docs/glossary.md` regenerates from the entry.

### 6. Counsel

**For.** The rule generalizes on its own terms — the region was a subtree and stays one — so the lift adds one predicate where the walk already lives, retires a special case rather than adding one, and changes no runtime line (executed, not argued). The witness is the corpus game the wall named, the cells play rather than resolve, and the whole change was run end to end today: cribbage through the block, both halves simulated, identical to the legacy path at 5 of 5 seeds and 62 of 62 hands, with all five names dispatched through the declared route and the two-tail entry carrying both scopes.

**Against, strongest.** Hoyle's, carried: the nested case is easy because it buys little — the outer tail carries no containment information, only which declaration `dealer` is — so the yield is one declared word against three passed arguments and a Python parameter, and the rival resolves clean today. From this seat the price is concrete: a phase-path table for every phase, a nesting predicate, an enclosure-aware diagnostic with its own attribution map, a scoped-entry record, and a grid with a derived shape axis — machinery whose second corpus user does not exist. Second: the designed constraint's premise (a frame never outlives its phase) is a comment today; without the one pin it is a claim, and the reopening event would be silent.

**What the Architect would do.** Take option A throughout; commit the cells red before touching the resolver; teach `_scoped_entry_phases` the chain before the arm moves; take and record both takes; add the three born-green pins; keep the cores beside the adapters with the closure rule stated at the adapters; derive both sides of the engine-core pin; strike the two false plan lines; mark the orphaned regime cell as ruled; give the fuzz fixture its block; run the read oracle once and quote it; sweep the full-width goldens and leave `tests/openspiel_ready/test_cribbage.py` untouched; and close #517 and #473 in the PR body.

### THE BOTTOM LINE (written once for the sitting)

**Verdict.** Lift the one-phase wall for nested phases only, by the nest-and-innermost law Hoyle ruled, on the machinery ruled here — one predicate beside the one walk, the region the innermost's subtree, the non-nesting set refused at entry grain after the tails validate, the outer-side diagnostic naming the phase the call is in — in the same change that normalizes cribbage's two scorers, retires the site-read contract, and migrates cribbage as the witness.

**The strongest against, from either seat, and its cost.** Hoyle's: the nested case is easy because it buys little — one declared word against three passed arguments — and the rival needs no language change. Its cost on the language side is a two-clause law and a longer diagnostic; on the engine side a nesting predicate, a full-phase path table, an enclosure-aware message, a scoped-entry record and a derived grid, for one corpus entry today. The hazard both seats name — a two-phase entry accepted and unchecked if the arm lifts before containment learns the innermost — is real and was executed here (compile-clean, crash at playout, three shapes); the red-first order and the take-2 record are what close it, and they are mandatory, not advisory.

**Divergences.** None material. One refinement of placement, consistent with Hoyle's phrasing: the non-nesting refusal sits among the tail-validation arms at ENTRY grain, after every per-read tail has validated, not inside the per-read `_check_read_tail` — a per-read arm cannot see the set. Two corrections to the plan, not to Hoyle: the ranking gate already lists `peg_run_points` (the "gains" line and the step-1 reddening claim are struck), and the engine-core pin derives both its sides.

**Consensus.** The seats agree on every material point: nested-only; nest-and-innermost; no order meaning; no depth cap; the non-nested pair a designed constraint with the "no place runs both" reason and no issue; #516, #518 and #521 standing and re-probed with two tails; the ten prose sites plus this seat's additions; the two-phases rejection re-blessed; the ancestor-case register fixed from the same paths; the implementation-order hazard closed by red-first order; information sets unmoved. Per the operator's standing instruction, implementation begins.

**What the operator decides.** One thing, Hoyle's ask, which this seat joins: that the non-nesting refusal closes as a designed constraint with no issue — recorded at the arm, in the glossary sentence and in the rejection fixture, with its premise pinned by the one-line frame-pop test rather than left as a comment.

## Framing check (2026-09-04, fresh-context over the contract partition — attached as a dated record)

# Framing check — cribbage pegging scorers off the dispatch site (#473)

Definition sources read wholesale: `cardlang/primitives_block.py`, `cardlang/runtime/{primitives,reads,narrowing,cribbage,driver,evaluate,mechanics(268-283)}.py`, `cardlang/builtins/{functions,signatures}.py`, `resolve.py` (contract arm 5244-5301, reads arm 5330-5420, declared-only arm 7775-7797, Contract 80-100), `typecheck.py` (160-230, 570-590, 975-1110, 2615-2640), `ir.py` (82-89, 154-158), `state.py` (375-389), `docs/games/cribbage.{cardlang,md}`, `primitive-sidecars.md` §2/§5, glossary index + the five primitive entries, issue #473 (+ #517, #474, #535, #142), and every test module `rg` names (list below). Probes executed with `.venv/bin/python`.

## 1. The `InvocationContract` partition

**Members and populations (executed):** `Counter(impl.contract ...)` = `BUNDLED 38, PURE 4, EMITTING 1, SITE_READ 2`. SITE_READ = {`peg_pair_points`, `peg_run_points`} (`primitives_block.py:221-222`); EMITTING = {`coup_game_summary`} (:201); PURE = the four ladders (:205-207, :227). `DECLARABLE_CONTRACTS = {BUNDLED, PURE}` (:236-238). Enum at :137-167; SITE_READ docstring :162-166 cites #473.

**Consumers of the member set, and what each does at zero members / after deletion:**

| consumer | site | zero SITE_READ members | member deleted |
|---|---|---|---|
| `test_every_invocation_contract_has_a_member` | `tests/test_primitives_block.py:479-486` (`used == set(InvocationContract)`; red-under: "add an arm with no row") | **RED** — this is exactly its named mutation | green |
| `test_the_declarable_contracts_are_a_proper_subset` | `:489-500` (proper subset + some refused member exists) | green via EMITTING | green via EMITTING |
| `test_an_undeclarable_contract_is_refused_by_name[<name>]` | `:2093-2107`, parametrized over `contract not in DECLARABLE_CONTRACTS` | the two `peg_*` cells vanish; `coup_game_summary` cell stays | same |
| `test_every_declarable_contract_has_a_reads_shape_cell` / `_READS_SHAPE_CELLS` | `:1218-1272` | unaffected (declarable side only) | unaffected |
| resolve refusal arm | `resolve.py:5287-5295`; message `'#142' if contract is EMITTING else '#473'` (:5293) | else-branch unreachable — a conditional with a dead arm | else-branch must go (only EMITTING remains) |
| `undeclarable_contract` | `primitives_block.py:660-667` | unchanged | unchanged |
| `driver.declared_primitives` | `driver.py:156` `bundled=impl_ref.contract is InvocationContract.BUNDLED` | unchanged | unchanged |
| `test_signatures._declared_facts` | `tests/test_signatures.py:287-315` (`[None, None] if BUNDLED else []`) | unchanged | unchanged |
| enum docstring | `primitives_block.py:143-144` "The other **two** are refused BY NAME" | false | must say one |
| ledger referents | `tests/test_ledger_referents.py` | no ledger row names `SITE_READ`/`_CRIBBAGE_R` (rg over tests/ + docs/ minus plans: 0 hits) | nothing reddens |
| IR | `ir.py` emits no contract | n/a | n/a |

Non-vacuity per member: `:479-486` asserts every member is used (a pin that is born green and whose red-under is precisely this change's intermediate state); no pin asserts a member is declarable-AND-populated per member beyond `:489-500`.

**Probe (today's diagnostic):** a cribbage block with `peg_pair_points() : Integer reads play_pile` → `cribbage.cardlang:33:5: error: \`peg_pair_points\`'s implementation does not answer the declared Primitive contract (it is site_read), so a \`primitives\` entry cannot bind it — see issue #473`. Same for `peg_run_points`, and for `reads play_pile, rank_index` (the contract arm speaks before the engine-fact refusal).

**Observation (probe E):** the block loop reports only the FIRST failing entry — a valid entry followed by two bad ones yields one diagnostic (`_check_primitive_reads` returns after its first `bag.error`, and the entry loop stops at the first name refusal). Not this change's defect; it bounds what any composite probe proves.

## 2. The dispatch site

- `call`'s arm set (executed, `PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS`): `coup_game_summary, cribbage_crib_value, cribbage_show_value, peg_origin_of, peg_pair_points, peg_run_points` — matches `runtime/primitives.py:120-153` exactly. Pinned by `tests/test_native_dispatch_split.py:196-216` (`primitives_arms == PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS`) and per name by `:184-193`. **Consequence:** any arm deleted forces its name into `DECLARED_ONLY_CALL_FUNCS` (`functions.py:255-297`) in the same edit; `tests/test_signatures.py:461-473` (`set(facts) == set(CALL_SIGS)`) says the same thing from the arity side.
- `_bind` (`primitives.py:53-57`): used by the coup arm and the three bundled cribbage arms. The two site-read arms bypass it (`:132-134`, `:138-141`): `reads.deep_freeze(reads.single(ctx.rs, _CRIBBAGE_R, "play_pile").cards)` and `reads.deep_freeze(ctx.rs.rank_index)`.
- Module-keyed rows: `_BRIDGE_R/_CRIBBAGE_R/_PINOCHLE_R/_TAROT_R` (`:47-50`) bound AT IMPORT via `reads.row`; registry rows `reads.py:288-307`. Deleting the cribbage row without the binding crashes `cardlang.runtime.primitives` at import for EVERY game (`reads.row` raises `PrimitiveReadError`, `reads.py:319-331`) — the coupled-edit hazard the 3b recipe step 3 records for game modules applies here to engine core.
- Reconcile carve-out: `_walled_binder_rows` (`tests/test_primitives_block.py:2374-2389`) = `_climb_bound_rows()` ∪ rows whose module is `_SHARED_DISPATCH_MODULE` (:2337); backing assert `:2442-2446` (no implementation names that module). After the cribbage row leaves, the shared half is the three auction rows; `test_the_walled_exemption_names_the_rows_the_binders_bind` (:2496-2508) asserts `shared` non-empty → still holds. **Prose naming cribbage by name:** `_walled_binder_rows` docstring `:2382-2384` ("serve the auction outcomes and cribbage's pegging call sites"); `reads.py:286-287`; `primitives.py:44-46`, `:128-131`.
- **Pin that hard-codes the row set:** `tests/test_primitive_narrowing.py:1613-1633` `test_engine_core_game_knowledge_is_named` asserts primitives.py's rows == `{bridge, cribbage, pinochle, french-tarot}` → **RED** when the cribbage row leaves; and its ledger residual (1) `:113-121` names only the auction outcomes (already inconsistent with the set it pins).
- **Legacy-half representative:** `_LEGACY_HALF_NAME = "cribbage_crib_value"` (`tests/test_primitives_block.py:658`), pinned by `:661-671` to still have an arm. If cribbage adopts the block, the legacy half becomes `{coup_game_summary}` — which is EMITTING, hence undeclarable — so the regime-product cell `("legacy-arm too", "block declares it") = True` (`:784-791`, `:806`) has NO admissible representative. That cell's outcome must be re-decided (xfail citing #142's coup eviction, or the axis restated), not just the name swapped.
- `test_signatures.py:440-458` inline-helper list `["card_points","error","team_of"]` unaffected; ledger residual `:30-34` names "peg_pair/run_points" as inline arms → goes false.

## 3. The rank-index channel

- `EngineFacts.rank_index: Mapping[str,int]` exists (`narrowing.py:91-92`), sourced `rs.rank_index` (`:125`), deep-frozen (`:130`); pinned `_FACT_SOURCES` `tests/test_primitive_narrowing.py:778-785`, consumers `_FACT_CONSUMERS` `:791-798` (salvo/president/cribbage show already spell `facts.rank_index`), identity-copy pin `:1010-1030`.
- Gate: `peg_run_points` ∈ `RANKING_GATED_FUNCS` (`typecheck.py:206-214`; census comment `:171-205` lists it and lists `peg_pair_points` as a NON-member "rank equality only"). Gate fires by NAME regardless of regime (`:2628-2638`, condition `e.func not in env.functions and not env.has_ranking`). Diagnostic (pinned `tests/test_zone_family_typing.py:423-427`): `peg_run_points() reads a card's rank strength from ranking:, but the game declares no ranking: — declare one, or declare a \`trick_order { }\` with a \`card_strength:\` row and name highest_by_trick_order`.
- Derived-readers pin: `_rank_index_readers` (`tests/test_primitives_block.py:412-420`) walks the implementation's call closure for the substring `rank_index` → `peg_run_points` reading `facts.rank_index` in its own body STAYS a reader (gate membership unchanged); control pair `:460-476` requires `peg_pair_points` NOT to name `rank_index` (its `facts` parameter must stay unused of that field, and no shared helper it calls may name it).
- **Cells that move when the five names become declared-only:** `tests/test_zone_family_typing.py:423-453` (six cells) build a LEGACY fixture (`_game`, `:97-121`) calling `peg_run_points()`/`cribbage_show_value(0)`/`cribbage_crib_value()`; resolve's declared-only arm (`resolve.py:7775-7797`) then speaks first → `_rejects(..., "reads a card's rank strength")` and `_accepts` both **RED**. Baseline run today: 23 passed. No `salvo_combos` precedent exists there (declared-only members are gated only through the driver grid). `tests/test_trump_slot_class.py:915-920` `_drive_peg_run_points` calls `cribbage.peg_run_points([cards], _PARTIAL)` → **RED** on the signature change (rebuild as `_drive_president`'s bundle shape, `:948-975`); `test_every_ranking_reader_has_a_driver` (:992-999) keys the driver by name, unchanged.

## 4. Frozen-pile equivalence (executed)

Three seeded playouts, wrapper on `primitives.call` capturing both shapes at every call: `{'pair': 324, 'run': 324, 'nonempty_calls': 648, 'mismatch': 0, 'types': {('tuple','tuple')}, 'elem_types': {('Card',)}, 'identity_shared': 0, 'rank_mismatch': 0, 'rank_types': {('mappingproxy','mappingproxy')}}`; scorer values equal under both inputs at every call. Site = `deep_freeze(list)` → tuple of rebuilt `Card`; bundle = `deep_freeze({n: list(single(...).cards)})["play_pile"]` (`reads.py:634-641`) → same tuple, same order, same depth; `rank_index` both `MappingProxyType`, equal.

Pins that would catch a divergence: the per-seed golden `tests/golden/cribbage_hands.json` (**50 seeds**, per-hand score vectors — pairs/runs feed `score`, so a wrong zone/order/row moves it; `tests/test_migration_characterization.py:249, 963-1016`; sampled by default, `CARDLANG_GOLDEN_SEEDS=full` for the sweep); `tests/test_playout_cribbage.py:70-86` (50 seeds invariants); grid (d) in `tests/test_primitive_narrowing.py` (bundle immutability); `test_peg_direct_arm_args_are_frozen` (`:1476-1508`) proves the SITE's freeze and calls `stdlib.call("peg_pair_points", [], ctx)` with a 1-arg monkeypatch → **RED under any shape of this change** (no arm, or 2-arg bundled call, or `_bind` needing `seq_bits/seq_len/dealer` the fixture never declares). No read oracle exists in the tree (PR #536/#561's were scratch instruments).

## 5. The READS registry

- Rows: `reads.py:262-268` (cribbage.py: state `seq_bits, seq_len, dealer`; family `played`; singles `play_pile, starter, crib`) and `:293-297` (primitives.py: single `play_pile`). Cell `test_registry_row_agrees_with_game_declarations[primitives:cribbage.cardlang]` (`tests/test_primitive_reads.py:174-186`) vanishes with the row.
- Module-source scan (`:235-331`): keys accessor literals `reads.single(ctx.rs, _CRIBBAGE_R, "play_pile")` and `reads.row("…primitives.py","cribbage.cardlang")` (both in primitives.py) and `gr.<half>["name"]` subscripts on a parameter spelled `gr` (`:224`, `:298-330`). Expected per module = rows ∪ blocks via `_declared_for_module` (`:340-393`, classifies block reads WITH their tails). Consequences: `[primitives.py]` requires arm + row deleted together; `[cribbage.py]` requires the new bodies to spell `gr.singles["play_pile"]` literally and the module-wide union to equal {state seq_bits/seq_len/dealer, family played, singles play_pile/starter/crib} whether declared by row (contract-only change) or by block (rows deleted, `ROW` binding at `cribbage.py:43` deleted — precedent: skat/belote/canasta). Under-declaration in a block (probe G: `peg_origin_of … reads play_pile, seq_bits in play, seq_len in play` without `dealer` checks CLEAN) is caught by this scan statically and by the typed bundle miss (`reads.py:441-449`) at playout.
- `NARROWED` (`tests/test_primitive_narrowing.py:386-449`) lists `cribbage.py::ROW` + the five funcs; sites derive from arm imports ∪ index (`:258-284`) — once the arms go, `cribbage.py::ROW` is no longer a site and `NARROWED <= sites` (`:517`) → **RED** until dropped. `MIGRATED` (`:452-502`) holds `peg_origin_of, cribbage_show_value, cribbage_crib_value` but NOT `peg_pair_points`/`peg_run_points`; MIGRATED gates only `EMITS_TRACE` cells and `test_no_unlisted_migrated_primitive_emits_traces` (`:1588-1599`, skips non-MIGRATED names) — adding the two is what the property wants. `EMITS_TRACE = {coup_game_summary}` (`:505-509`), untouched.
- `tests/metamorphic/rename.py:137-163` `_coupled_names` = block reads ∪ rows for the game file — correct under either shape.
- `tests/test_cribbage_primitives.py:22-29, 108, 138, 161, 180` import `ROW` and bind with it → **RED** if `ROW` goes (post-migration precedent `tests/test_gin_primitives.py:41-45` binds through `driver.declared_primitives`). `tests/test_playout_cribbage.py:63-67` calls `peg_pair_points([...])`/`peg_run_points([...], _ORDER)` bare → **RED** on the signature change unless the pure cores survive as separate functions (the module docstring `cribbage.py:12-15` promises exactly that unit-testability).

## 6. The corpus

- Call sites (all inside `phase play` ⊂ `hand_sequence`): `peg_pair_points` :101, `peg_run_points` :103, `peg_origin_of` :106, :117, :136, `cribbage_show_value` :144, :146, `cribbage_crib_value` :148.
- Classification (executed): `play_pile/starter/crib` SINGLE_ZONE, `played` ZONE_FAMILY, `score` game-level INDEXED_STATE_VAR; `seq_bits, seq_len` phase-local to `play`; `dealer` phase-local to `hand_sequence`; `phase_local_state_names = {active, dealer, gos, last_played, seq_bits, seq_len, total}`. Row ∩ phase-local = `{dealer, seq_bits, seq_len}` → **cribbage is a member of the #504 phase-local cohort class**, which the 3b plan's cohort table (`docs/plans/2026-08-29-primitives-block-stage3b.md:60-69`) files only under #473.
- `peg_pair_points`/`peg_run_points` owe NO tail (`reads play_pile`, game-level zone). **`peg_origin_of` needs `seq_bits in play, seq_len in play, dealer in hand_sequence` → refused by the one-phase rule** (`resolve.py:5374-5386`, issue #517, R3 `blocked:needs-witness`): executed → `\`peg_origin_of\` reads state from phases \`hand_sequence\`, \`play\` — one entry's \`reads\` clause names at most one phase … split the entry, or pass the second value as an argument`. #517's own witness sentence ("one phase is an ancestor of the other … passing the outer value as an argument reads worse than declaring it") describes cribbage exactly. So the contract normalization alone does not let cribbage declare a block; a second wall stands, unnamed in #473 and in the sidecars note. Executed residue probes (peg_* calls stripped so the contract arm is silent): dealer hoisted to game-level state + `dealer` untailed → ACCEPTED; as-is game + both tails → REFUSED (#517); dealer-as-argument shape → the shape check compares against `implementation_sig` = `CALL_SIGS` (`typecheck.py:1051-1061`), so that route changes `CALL_SIGS:115`, the Python signature, and three game-text call sites.
- Twin: `cribbage.md` is in `PROSE_ONLY_TWINS` (`tests/test_typecheck_corpus.py:51`); link-shape, no fenced block, no lockstep pin (`:148-210` run over an empty set). Convention only: migrated twins mention the block in prose (`gin-rummy.md:92`, `holdem.md:51`).
- Goldens: cribbage is NOT goldenless — `cribbage_hands.json` (50 seeds); no IR golden; IR emits a `primitives` key for a declared game (`ir.py:82-89`), schema already pinned (`tests/test_ir_schema_version.py:80,103`). `tests/openspiel_ready/test_cribbage.py` (depth 4, observation derivation) is declaration-independent. PR #536/#561's substitute instruments (differential + read oracle) were for goldenless games; here the full-width golden is the proof, and the game-file rule (`CARDLANG_GOLDEN_SEEDS=full`) applies if `cribbage.cardlang` changes.
- **Fuzz fixture:** `tests/fuzz/known_findings/cribbage_repeat_until_nonterminate.cardlang` is a frozen OLD cribbage (no block; calls all five names at :99,:101,:104,:115,:134,:142,:144,:146); checks CLEAN today (executed); `test_known_findings_still_reproduce` (`tests/fuzz/test_fuzz.py:272-300`) asserts it PASSES the pipeline and crashes at playout. Once the five names are declared-only it is refused at resolve → **RED**, and the finding's classification (`findings.py:101-121`, "accepted-then-crashes-at-playout") goes false.
- `tests/test_piece_content_guards.py:515-520` probes every DECK_ONLY member (incl. the four cribbage names) in a legacy piece game; the flavor arm runs before the declared-only arm (`resolve.py:7785-7789`) → unaffected.

## 7. Prose that goes false

`primitives_block.py:143-144, 162-166`; `runtime/primitives.py:1-12` ("arms below are the LEGACY dispatch seam" stays true), `:44-46`, `:128-131`; `reads.py:286-287`, `:293-297`; `cribbage.py:12-19` ("the ctx adapters pass `rs.rank_index`"), `:72-76` (`run_score`: "`ctx.rs.rank_index` from cribbage.cardlang"), `:147-150`; `narrowing.py:38-39` (assumes "the primitive's module has a `PRIMITIVE_READS` row", #535); `resolve.py:5293`; `tests/test_primitive_narrowing.py:100-112` (ledger (d'): "the direct sites … the two cribbage peg arms and the trick `outcome_fn`", "captured at the peg and outcome sites"), `:1476-1479`, `:1613-1623`; `tests/test_signatures.py:30-34`; `tests/test_primitives_block.py:2382-2384`, `:651-658`; `docs/design-notes/primitive-sidecars.md:317-327` (§5 3b "blocked on the two cribbage pegging primitives that read at the dispatch site (issue #473)", "the dispatch-site reads (issue #473)"); `docs/design-notes/primitive-inventory.md:343-345` ("`runtime/primitives.py` holds rows of its own for … cribbage's pegging call sites"). Dated artifacts (journey, not owed): `docs/plans/2026-08-29-primitives-block-stage3b.md:67, 116-119, 223` (counsel: "the survivors are three auction-outcome rows and one pegging-scorer row"), `docs/plans/2026-09-02-collection-parameter-spelling.md:444, 603`. Stays true: `library.md:393-402, 925-942`; `kernel-migration.md:414-425, 458-461`; `functions.py:205-209` comments; `glossary/primitive.md:3` ("one hand-written arm per name; that arm count is the elimination metric") while coup's arm remains.

## 8. Other dispatch-site reads (not SITE_READ)

None in `PRIMITIVE_IMPLEMENTATIONS`, so the enum's stated domain ("a closed domain over `PRIMITIVE_CALL_FUNCS`", `primitives_block.py:140`) is fully served by retirement; `call` keeps one arm (`coup_game_summary`, BUNDLED+EMITTING). Outside the domain, site reads remain: the three auction outcomes read `reads.state(rs, _X_R, …)` inside `primitives.py:377-464` (walled namespace, hold `ctx`; narrowing ledger residual (1)); the uniform-contract trick winners get `deep_freeze(state["played"])` + `deep_freeze(ctx.rs.rank_index)` at `mechanics.py:275-283` (Builtins, `winners.py`); climb queries are bundle-bound with the hand/standing `Play` frozen at the site (`mechanics.py:266-272`); `builtins.py:84, :317` read `ctx.rs.rank_index` directly. Prose claiming the wider set: only narrowing ledger (d') — its "trick `outcome_fn`" half survives.

## 9. Unsure

- Whether the change is one PR (contract + row deletion + block) or two; the block half meets #517 (above) and needs an operator decision among: lift #517 for the nested-ancestor case (cribbage is the named witness shape), hoist `dealer` to game level (a game-text change; `hand_sequence` runs once so init semantics are identical, but "the game does not bend to the harness" wants the reason stated), pass `dealer` as an argument (Sig + CALL_SIGS + game text), or split the entry.
- The regime-product cell with no admissible legacy representative (§2) — outcome undecided; may be an issue rather than a mark.
- Whether `peg_pair_points`/`peg_run_points` keep pure cores (`(seq)`, `(seq, order)`) beside bundled adapters — decides the fate of `tests/test_playout_cribbage.py:63-67`, `tests/test_trump_slot_class.py:915-920`, and the control-pair scrape (a shared helper naming `rank_index` would pull `peg_pair_points` into the reader set).
- `_declared_for_module` (`tests/test_primitive_reads.py:340-393`) compares the module-wide UNION, so per-entry over-declaration (issue #534) is invisible to it — the plan's reads clauses need review eyes, as PR #536 recorded.
- `narrowing.py:38-39` / `tests/test_primitive_reads.py:434` (#535) — the closing-PR rider; this change makes cribbage one more instance.
- `cribbage.cardlang:17-18` "the `peg_origin_of` Primitive primitive" (doubled word) — pre-existing, in the file the change edits.
- The `EngineFacts` half stays whole (#474): `peg_run_points` reading `facts.rank_index` is undeclared by design; nothing pins that a declared entry's reads are sufficient (grid `does not prove:` row, `tests/test_primitives_block.py:203-210`).

## Gate-4 addendum (2026-09-04, measured at implementation — recorded, not rewritten)

Where the derived domain differed from this plan's statement. The counsels
bind where they speak; these are the plan's own lines, and each is left above
with its correction here.

1. **The show entries' call positions.** "The block" section says the show
   entries sit "inside `hand_sequence`'s body". Measured: all five call sites
   sit inside `phase play` — the show calls are the last statements of that
   phase's body, not of its parent's. Consequence: none. The show entries
   carry no tail, so they enter no chain and the containment analysis never
   judges them; the sentence was about where they happen to be written.
2. **When the two site-read arms delete.** Step 1 says the arms delete at
   normalization. Executed in two moves instead: at normalization they are
   REWRITTEN to bind cribbage's own row (`peg_pair_points(*_bind(ctx, ROW))`),
   and they delete with the other three at the migration. Deleting them at
   step 1 would leave a legacy-regime corpus game whose calls reach no arm —
   either a playout crash or, with the names moved early, a corpus game
   refused at resolve. The step's own reddening artifact is unchanged and was
   committed red: the contract partition pin, on exactly its recorded
   mutation.
3. **`RANKING_GATED_FUNCS`.** Re-executed: `peg_run_points` is already a
   member and already a derived reader; `peg_pair_points` is neither. The
   Architect's correction stands and Gate 2's "gains" line is false.
4. **The classifier's question in `_scoped_entry_phases`.** Not stated
   anywhere above, and load-bearing: the classifier is asked per READ against
   that read's OWN tail, never against the region. Asked against the region,
   `dealer in hand_sequence` classifies as nothing under `play`, cribbage's
   entry drops out of the scoped table, and every one of its call sites goes
   unjudged — the vacuous window surviving the arm's replacement.
5. **A negative assertion that would have gone vacuous.**
   `test_a_wrong_tail_and_a_wrong_call_site_report_once` asserted the absence
   of "callable only where that phase runs". The new sentence interpolates the
   phase name, so that literal cannot appear in any diagnostic and the
   assertion could never fail again. Re-anchored on "callable only where".
6. **The enclosure branch needs a pair.** Both the ancestor and the sibling
   containment cells named only the entry and the region, so both would pass a
   guard that said "encloses" of every phase outside the region. The ancestor
   cell gains the fragment and a cell beside it asserts its absence for the
   sibling.
7. **The rejection corpus.** Step 3b says it gains "the non-path and
   outer-body sentences". The non-path sentence is the existing
   `primitives_scoped_read_two_phases` re-blessed; the outer-body one is new
   (`primitives_scoped_read_in_the_enclosing_phase`).

Measurements taken at implementation, all dated 2026-09-04:

- The grid's two takes: 53 failed / 76 passed against the one-phase arm; 30
  failed / 99 passed with that arm lifted alone, 27 of the 30 DID NOT RAISE.
  Both are quoted in the grid module's own record.
- Between the cells and the arm's replacement, four cells of the nested
  crossing flip green: with `_scoped_entry_phases` chain-aware and the old arm
  still refusing, containment runs for an entry the arm also refuses, so the
  leaked-offer and leaked-run messages appear beside it. More diagnostics,
  never fewer; it ends when the arm is replaced.
- The frozen-pile equivalence at the first pegging call of seed 0: site tuple
  and bundle tuple identical in container, order and element type, with the
  same 13-entry `rank_index` mappingproxy.
- The read oracle over 20 seeds: every declared name read, nothing
  undeclared; a planted over-declaration reported, a planted under-declaration
  refused at playout.
- The call census over 20 seeds: 6813 dispatches, all through
  `call_declared`, none through the legacy arm.
- The full-width per-seed goldens byte-identical, nothing regenerated;
  `tests/openspiel_ready/` unchanged against `origin/main`.
