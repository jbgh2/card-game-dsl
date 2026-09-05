# The last emitter leaves, and the legacy dispatch seam retires with it (epic #142, stage 3 closing)

Operator go: Ben, 2026-09-04 ("When it completes you can move on to the
last game") — coup is the last legacy holdout after cribbage (PR #575,
merged 2026-09-05; branch point `bb92178`).
Merge Lane: not A (no grammar surface); engine + registries + corpus +
harness — operator merge, and the stage-3 box of #142 is the operator's
tick "on full elimination" (docs/plans/2026-08-29-primitives-block-stage3b.md,
"Closing steps"). The Architect's counsel attaches below (single-persona
sitting: no surface moves, Hoyle does not sit).

## Why this is one change and not two

`coup_game_summary` is the last call-namespace row in `PRIMITIVE_READS`,
the last `case` arm in `runtime/primitives.py::call()`, and the only
`InvocationContract.EMITTING` implementation. Evicting it leaves: `call()`
with no arms (the dispatch-split pin's legacy side empty); EMITTING with
no member (`test_every_invocation_contract_has_a_member` red);
`DECLARABLE_CONTRACTS` equal to the whole enum (its proper-subset pin
red — the allow-list is total and its refusal arm can no longer fire);
the regime-product grid's legacy axis with no representative
(`_LEGACY_HALF_NAME`'s guard red). Those reds are the stage-3b plan's
closing step arriving: the legacy seam retires whole — `call()`/`_bind`
and the module-keyed legacy plumbing, `CALL_SIGS`' Primitive half moved
to the `implementation_sig` column (the designed one-site seam),
`PRIMITIVE_READS` reduced to the walled rows (three climb, three
auction), the contract partition reduced to the dispatch shapes both
declarable — with #535's two module-grain sentences riding. The
eviction IS full elimination; the plan treats it as the closing PR
unless the Architect rules a two-PR sequence with the intermediate reds
marked `xfail(strict)`.

## Acceptance criteria (bind the change)

1. **Runs** — coup plays with no primitive at all (its one call was a
   dead `let`); every declaring game plays through the declared route
   unchanged; the harness still asserts coup's two conservation totals
   (50 coins, 15 influence cards) and the characterization vector.
2. **Regression-clean** — bare `mypy`; CI's three checks; playout goldens
   byte-identical at full width. Coup's per-seed golden
   (`tests/golden/coup_scores.json`) is CAPTURED FROM the `coup_game`
   trace event today (`tests/test_migration_characterization.py` ~1143),
   so the eviction moves the golden's SOURCE: the harness derivation must
   reproduce the identical values, and the golden stays byte-identical
   (the stage-1 precedent — "values produced BY the emitters, reproduced
   by the derivation on every suite run"). No IR golden for coup.
3. **Info sets derive** — the eviction removes a TRACE emission (the
   harness's channel), never an observation: per-observer observation
   streams are byte-identical with the dead `let` removed (the proof:
   observation-event hashes before/after; `tests/openspiel_ready/
   test_coup.py` untouched). Whatever channel the harness derives coins
   and censuses from must not be a new per-observer observation unless
   the Architect rules it one — a state-assignment trace kind, if minted,
   rides the tracer, not the observer.

**Corpus lockstep** (operating rule 2): `docs/games/coup.cardlang` loses
the dead `let summary = coup_game_summary()` and its comment; `coup.md`'s
prose about the summary re-read; `docs/library.md`, `docs/kernel-migration.md`,
`docs/design-notes/primitive-sidecars.md` section 5 (stage 3b closes;
stage 4 next), `docs/glossary/primitive.md` ("one hand-written arm per
name; that arm count is the elimination metric" — the metric reaches
zero; the sentence rewrites), `docs/design-notes/primitive-inventory.md`
(dated, left). #142's third box and its stage-3 box: the operator's tick.

**Witness:** coup, in-change (the harness derivation runs on every suite
run through the golden and the invariants).

## Gate record (cardlang-planning)

- **Gate 1 (owners):** #142's third residual and stage-3 box (the epic's
  own text); the stage-1 precedent (PR #81: emitters evicted, facts
  derived from observation events in `tests/playout_trace.py`, grid +
  ledger in `tests/test_trace_emitter_eviction.py`, whose `residual:`
  row names exactly this step and cites #142); the stage-3b plan's
  closing step (the `implementation_sig` seam — the Architect's own
  ruling); decisions.md "Closed-domain completeness" (an allow-list that
  admits everything is a refusal that cannot fire; a domain that shrinks
  to nothing retires with its cells and their reason); "Knowledge,
  visibility, and the projection model" (what an observation is — the
  line a harness-only trace kind must not cross). Engine-structural
  (the observability model: how integer state and zone censuses reach
  the harness without an emitter) -> the Architect. No glossary mint
  expected; `primitive.md`'s elimination-metric sentence rewrites.
- **Gate 2 (classification):** runtime (coup.py loses the function;
  primitives.py loses its last arm, `_bind`, and the module-keyed legacy
  plumbing — the auction outcomes and their rows STAY, they are a walled
  namespace; evaluate.py's EMITTING tuple split retires with the
  contract), native registry (PRIMITIVE_IMPLEMENTATIONS loses one row
  and gains the signature column; CALL_SIGS loses its Primitive half;
  PRIMITIVE_CALL_FUNCS == DECLARED_ONLY_CALL_FUNCS — one of the two
  retires or the pin says why both stand; EMITTING retires;
  DECLARABLE_CONTRACTS retires or stays per the Architect), reads
  registry (the last call row goes), resolve (the contract refusal arm
  retires — no input can reach it), typecheck (`native_call_sigs` /
  `_check_primitive_signatures` read the column), harness
  (`tests/playout_trace.py` gains the coup derivation), corpus game
  (coup), tests/goldens (the eviction grid extends; the regime-product
  legacy axis retires; #535's sentences). Closed-domain mechanisms shrink
  to empty: the audit fires at each — Gate 4 applies.
- **Gate 3.5 (reachability):** #142 stage 3 is the workstream's own
  closing step (R2 by the stage's reachability: every migrating
  designer met the coexistence regime); the design step is small in
  code and large in doctrine (which channel carries state to the
  harness); the retirement is mechanical and closes the coexistence
  window the 3a plan opened as a CHECKED regime. Proportionate: it is
  what the stage exists to finish. Nothing edits doctrine.
- **Gate 4:** the framing check runs fresh-context over the trace
  channel, the emitting contract's plumbing, the legacy seam, the
  reads registry, the goldens, and the prose (report attached); its diff
  against the author's derivation is recorded below; the grid is red
  before implementation.

## The Architect's rulings (2026-09-04; counsel attached below — binding on the implementer)

- **The channel (a):** the harness reads `coins`, `treasury` and `alive`
  off the terminal world — `play_game(..., on_first_decision=hold)` hands
  the live `rs`; the `game_end` trace fires after the last phase and
  before the game-level frame pops (`driver.py` ~346-354, 387), which is
  the terminal position — exactly `cardlang/cli.py` ~222-240's idiom. The
  reader in `tests/playout_trace.py` (a general `TerminalState`, or a
  `CoupSummary`) captures `rs.get("coins")`, `rs.get("treasury")`,
  `rs.get("alive")` at `game_end` and takes the card total from the same
  payload's census; `total_coins` is computed at the harness. Its
  docstring cites `tests/test_cli_surface.py::test_play_reaches_a_terminal_position`
  as the Owner of the emit-before-pop premise and names the promotion
  event (a second consumer of terminal state, or a decision-free game
  needing it, promotes the fact to a return value on `GameResult`).
  REJECTED: a state-assignment trace or observation kind; a kernel coin
  invariant; a harness re-simulation of the coin economy as the golden's
  source (offered as a later differential oracle only); a return-value
  seam now (declined on proportion).
- **The shape (b): TWO changes, stacked, one merge sequence.** Change 1
  (this branch): the eviction + the harness reader + every pin whose
  premise the eviction kills (measured: 18 sites on a scratch copy —
  none an uncovered cell) + `EMITTING` retired with `DECLARABLE_CONTRACTS`,
  `undeclarable_contract`, resolve's contract arm, the proper-subset pin
  and the emptied per-name refusal grid (the chain runs on its own:
  no member -> no refused contract -> the allow-list equals the enum) +
  the three contract comparison sites converted to a structural `match`
  ending in `assert_never` (`driver.py` ~156, `tests/test_signatures.py`
  ~308, `resolve.py` ~5394 — the allow-list moves to the type checker's
  rung) + `test_every_invocation_contract_has_a_member` KEPT as the
  registry-side reconciliation + the two live-row fixtures made synthetic
  (`tests/test_primitive_reads.py` ~550 `_COUP_ROW`, `tests/test_primitive_
  narrowing.py` ~1240 — the synthetic-row rule) + the stage-1 grid
  extended + the new-source playout invariants and characterization
  capture + `_bind`/`_emit`/`TraceEvent`/the `traced` scrape branch
  retired + `EMITS_TRACE` and its two cells retired (its guarantee is
  grid (b)'s `ctx.trace` column) + the regime-product legacy axis and
  `_LEGACY_HALF_NAME` retired whole + `MIGRATED`/`NARROWED` dropping coup
  + the prose sweep. Change 2 (stacked on change 1, armed behind it, its
  end-state pins authored RED in its first commit against change 1's
  tip): `call()` and `native_call`'s legacy Primitive fall-through gone;
  `DECLARED_ONLY_CALL_FUNCS` retired and resolve's declared-only arm
  keyed on `PRIMITIVE_CALL_FUNCS`; `CALL_SIGS`' Primitive half moved to
  `Implementation.sig` (an AUTHORED `Sig` field — deriving it from
  annotations is rejected on a measured fact: `_python_type` maps
  Player/Team/Integer all to `int` and skips collections), with
  `implementation_sig` reading the column and every consumer re-pointed
  (`native_call_sigs`, `TypeEnv.call_sigs`' default, `test_permissive_top`'s
  equality becoming `set(CALL_SIGS) == BUILTIN_CALL_FUNCS`, the
  `test_signatures` reconciliations over the union, `_entry_and_body`, the
  freeze plant re-keyed to the index); `reads.py`'s docstring restated
  for the two walled namespaces; a positive born-green pin `{(module,
  game_file)} == _walled_binder_rows(PRIMITIVE_READS)` (red under adding a
  call-namespace row — the tick's executable form); #535's two sentences.
  Merge Lane B, both; Hoyle does not sit.
- **"Full elimination" for the stage-3 tick, concretely:** (1) no `call`
  in `runtime/primitives.py` and no legacy Primitive fall-through in
  `native_call`; (2) no `DECLARED_ONLY_CALL_FUNCS`; (3) `set(CALL_SIGS) ==
  BUILTIN_CALL_FUNCS` and every `Implementation` carries its `sig`; (4)
  every `PRIMITIVE_READS` row a walled binder's, pinned positively; (5)
  `InvocationContract == {BUNDLED, PURE}` with no allow-list. (4) and (5)
  land in change 1; (1)-(3) in change 2. **The operator decides one
  thing:** that the tick means change 2's end state, not change 1's —
  and whether the two changes are reviewed as two PRs (counseled) or
  change 2's commits ride change 1's branch (one review; identical
  sequence).
- **The golden and proofs:** `tests/golden/coup_scores.json` byte-identical
  from the new source at its own 40-seed width; `tests/test_playout_coup.py`
  asserting 50 and 15 from the reader over 40 seeds; `tests/openspiel_ready/
  test_coup.py` untouched; the write-time differential (reader against the
  live emitter, 40 of 40, dated) recorded in the eviction grid's ledger
  `sampled:` row as stage 1 recorded its own. A gain to quote: coup's six
  coupled names leave `tests/metamorphic/rename.py::_coupled_names`' exclusion
  set — run the rename metamorphic on coup and report.

## The design step (the Architect rules; options priced in the counsel)

The emitter computes at game end: `total_coins = treasury + sum(coins)`,
`total_cards = |court_deck| + sum(|influence[p]| + |revealed[p]|)`, the
`coins` vector, the `alive` vector. Card censuses are zone contents —
derivable from movement views at the harness (the stage-1 mechanism).
Coins and treasury are INTEGER STATE, and `alive` a Boolean state vector:
whether any stream the kernel emits carries state assignments decides the
shape — (i) a state-assignment TRACE kind on the tracer (harness-only;
not an observation), (ii) the harness reading the final `RuntimeState`
(omniscient; abandons "derived from views"), (iii) a kernel-level
conservation invariant, (iv) a DSL construct (Hoyle's; not this change).
The counsel below rules it and names what the goldens must show.

## The accepted domain (author's derivation; the framing-check diff is appended when it lands)

1. The trace channel: every `kind` the tracer emits and its payload; the
   observer channel and its difference; `tests/playout_trace.py`'s
   derivations (CoupReveals, TichuHands); the `coup_game` payload's four
   facts and which stream carries each.
2. The emitting contract's plumbing: `evaluate.native_call`'s tuple
   split; `narrowing.TraceEvent`; `EMITS_TRACE` (test_primitive_narrowing
   ~505, pinned both ways); resolve's refusal arm and its #142 citation;
   the enum member and docstring; the per-name refusal grid (one cell:
   coup); `test_the_declarable_contracts_are_a_proper_subset`.
3. The legacy seam: `call()`'s arms (one), `_bind`, the module-keyed
   rows (auction rows STAY — walled), the dispatch-split pin
   (`primitives_arms == PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS`
   — both sides empty), the regime-product grid's legacy axis
   (`_homes()`, `_LEGACY_HALF_NAME`, the legacy-arm cells), `MIGRATED` /
   `NARROWED` / `EMITS_TRACE`, `test_engine_core_game_knowledge_is_named`.
4. `CALL_SIGS`' Primitive half and its consumers (derive by grep:
   `native_call_sigs`, `_check_primitive_signatures`, the boundary
   probes re-pointed in #561, `test_permissive_top`'s
   `CALL_SIGS ⊇ CALL_FUNCS`, the arity pin, the name-set reconciliation,
   `test_helper_annotations_agree_with_call_sigs`).
5. The reads registry at the end state: six walled rows; the reconcile
   pin whose carve-out becomes the whole set (what it then proves); the
   module-source scan's domain; #535's two sentences.
6. Goldens and proofs: `coup_scores.json` (source moves; values identical);
   `tests/openspiel_ready/test_coup.py` (observation channel only —
   untouched); `tests/test_playout_coup.py`'s invariants re-sourced.
7. The corpus: coup.cardlang line 88 and its comment; coup.md; no other
   caller (derived).
8. Prose: `docs/glossary/primitive.md`'s elimination metric; kernel-
   migration.md's coup/emitter lines; library.md; primitive-sidecars.md
   sections 2 and 5; the enum docstring; primitives.py's "LEGACY dispatch
   seam" docstring; narrowing.py's EMITS_TRACE sentence; the eviction
   grid's `residual:` row (closes); the 3b plan (dated, stays).

### Framing-check diff (fresh-context, 2026-09-04; report attached as a dated record)

Executed facts that settle the design step's domain:

- **Which stream carries what** (40 seeds): `total_cards` equals the
  tracer's `game_end` payload `total` (`driver._final_card_census`) —
  40/40; `alive` equals `GameResult.scores` (coup's `winner: highest
  alive` makes the driver return the alive vector) — 40/40;
  `total_coins`, `coins`, `treasury` ride NO stream — no trace kind and
  no observation kind carries an integer state value. They are
  reconstructible by holding `rs` from the `on_first_decision` seam and
  reading it at the `game_end` trace — the standing convention of
  `cli.py:224-235`, `tests/test_playout_canasta.py`, `tests/test_playout_
  five_hundred.py` — 40/40 on every fact. An observation-stream
  derivation of coins was NOT executed: it would mirror the game's own
  coin rules (the treasury clamps), the duplicated-computation class.
- **The golden reproduces**: `coup_scores.json` rebuilt at full width
  (40 seeds) from rs-capture (`coins`) + `GameResult.scores` (`alive`)
  + the observation stream (`reveals`) is `json.dumps`-byte-identical.
- **Info sets**: per-player observation streams byte-identical over 40
  seeds with the dead `let` removed; the adapter installs no tracer;
  `test_trick_order_migration` already rules the trace channel
  harness-only.

Consumers and pins the author's derivation lacked, with what each does
at eviction (the "red set", derived):

- **Collection failures, not reds** (each blocks a whole module):
  `test_an_undeclarable_contract_is_refused_by_name` parametrized over
  an EMPTY refused set (`pyproject: empty_parameter_set_mark =
  fail_at_collect`); `test_tracing_primitive_returns_events` over an
  empty `EMITS_TRACE` (kills `test_primitive_narrowing.py`);
  `_homes()`/`_entry_and_body` reading `CALL_SIGS[name]` inside a
  parametrize once the name leaves the table (deselects the whole regime
  grid); `tests/test_primitive_reads.py:550 _COUP_ROW = reads.row(...)`
  at module import (`PrimitiveReadError` — the module's accessor matrix
  and misuse probes are ALL keyed to coup's row and need a new exemplar,
  synthetic per the narrowing ledger's precedent); `tests/test_signatures.
  _facts_in` `next(node ... node.name == "call")` -> StopIteration if
  `call()` leaves `primitives.py`; `test_trace_emitter_eviction.py::
  test_implementing_symbol_gone` imports `cardlang.runtime.coup` ->
  ModuleNotFoundError if coup.py is deleted.
- **Jointly unsatisfiable at zero EMITTING members**:
  `test_every_invocation_contract_has_a_member` (red while EMITTING stays
  in the enum) and `test_the_declarable_contracts_are_a_proper_subset`
  (red once it is deleted, and its "some refused member exists" half red
  either way) — which survives is a decision, not a cell (the Architect's).
- **Reds**: `_LEGACY_HALF_NAME`'s guard (legacy half empty); `MIGRATED`
  <= known (holds the name); `NARROWED` <= sites (`coup.py::ROW`,
  `coup.py::coup_game_summary`); the dispatch-split pin born VACUOUS
  (`empty == empty`); `test_dispatcher_home[call]` and its sibling if
  `call()` is deleted (they need a module-level `call` with a `match`);
  `test_trace_emitter_eviction.py::test_shadow_wall_still_guards_
  registered_names` uses `coup_game_summary` as its CONTROL row (moves
  to a still-registered name); its `test_prose_has_no_reference` sweeps
  `docs/library.md` (reddens until :1008 is edited).
- **A silent-pass hazard**: `test_call_funcs_are_dispatchable` swallows
  any non-`AssertionError` — a fallthrough re-channelled to
  `ShadowGuardError` would pass it silently; the pin's assertion narrows
  in the change.
- **The legacy REGIME after eviction**: `DECLARED_ONLY_CALL_FUNCS ==
  PRIMITIVE_CALL_FUNCS` (two authored copies of one set;
  `functions.py:252-254` anticipates the inversion); `call_namespace(
  LEGACY) = CALL_FUNCS` while a no-block game can call NO Primitive
  (every call meets the declared-only arm) — admits-then-refuses; whether
  the legacy namespace becomes the Builtins and the declared-only arm
  retires changes the diagnostic a designer meets copying a Primitive
  call into a blockless game (R2). The Architect rules it.
- **`CALL_SIGS` consumers by half** (derived): Builtin-only readers
  (`_FRAME_CALL_FUNCS`, evaluate's declared branch, typecheck 1105/2380/
  2457, the movement/trick-order/trump/card-points tests, the boundary
  probes already reading the Primitive half via `implementation_sig`);
  Primitive-half readers (`primitives_block:701`, `_entry_and_body`, the
  freeze plant keyed to `CALL_SIGS["pinochle_meld_value"]` whose
  red-under becomes meaningless, `test_signatures._declared_facts`,
  `test_primitive_narrowing:1448`); whole-table readers (evaluate's legacy
  branch — only Builtins reach it after; `TypeEnv.call_sigs`;
  `test_signatures` 80/464/467-521; `test_permissive_top:232`;
  `test_trace_emitter_eviction:123`).
- **`tests/metamorphic/rename.py::_coupled_names`**: coup's six names
  leave the exclusion set (the rename domain widens; no pairing witness).
- **Prose going false** (the check's section 7, verbatim list attached):
  `coup.py`'s docstring; `primitives.py` 6-12/28-30/44-46/52-64/126-139;
  `builtins.py` 19-30; `evaluate.py` 23-40; `narrowing.py` 26-39 and the
  `TraceEvent` docstring (already false — it names emissions no
  primitive makes); `reads.py` 3-28/30-53/579-582; `state.py` 377-383;
  `driver.py` 100-103; `holdem_heads_up.py` 18-19; `primitives_block.py`
  1-10/105-107/147-171/238-243/686-701; `functions.py` 188-254/443;
  `signatures.py` 112; `typecheck.py` 1096-1105; `resolve.py` 88-96/
  5292-5299/7913-7920; glossary `primitive.md` (the arm-count metric
  sentence already contradicts `primitives.py`), `trace-event.md`,
  `primitive-bundle.md`, `primitives-block.md`, `native-code.md` (quotes
  a dead message); `primitive-sidecars.md` sections 1/2/5 and stage 5;
  `kernel-migration.md` 35-36; `library.md` 820-834 and 1003-1011;
  `primitive-inventory.md` (dated, left); the test ledgers listed in
  the report; #142's body (cites retired modules).

## Steps (each with its proving artifact; the red set is the work list)

1. The harness derivation of coup's four facts from the channel the
   Architect rules, proven equal to the live emitter by a differential
   BEFORE the eviction (the stage-1 shape: run the derivation beside the
   emitter over N seeds in the grid module; the differential is the
   born-red-then-green cell). Artifact: the eviction grid extended
   (`tests/test_trace_emitter_eviction.py`: the name joins the evicted
   set; its non-membership cells red first); `coup_scores.json`
   byte-identical from the new source; `test_playout_coup`'s invariants
   green from the derived facts.
2. The eviction: coup.py's function and ROW; the game's dead `let` and
   comment; the registry rows (functions.py, signatures.py,
   primitives_block.py); the last `call()` arm. Artifact: the rejection
   pair `call_evicted_trace_emitter_coup_game` (the unknown-call
   diagnostic — the stage-1 precedent); `EMITS_TRACE` empty or retired
   with its pin's reason.
3. The retirement (per the Architect): `call()`/`_bind`/legacy plumbing
   deleted (auction machinery stays); EMITTING retired (enum, docstring,
   refusal arm — no input can reach it — and its cells); DECLARABLE_
   CONTRACTS retired or kept per ruling; CALL_SIGS' Primitive half moved
   to the `implementation_sig` column with every consumer re-pointed;
   PRIMITIVE_CALL_FUNCS vs DECLARED_ONLY_CALL_FUNCS resolved; the
   regime-product legacy axis retired (the `xfail` cell citing #142
   fires — its reddening event — and retires with the axis); the
   reconcile pin's statement at the end state; the dispatch-split pin
   retired or restated. Artifacts: every partition/split pin re-derived
   and green with a stated domain; `test_signatures`' reconciliations
   over the column; the boundary probes over the column (already the
   union); the born-green pins' reddening mutations named.
4. Prose (assume a miss): domain item 8, then the repo-wide grep for
   "legacy", "LEGACY dispatch", "coup_game", "EMITTING", "emitter",
   "elimination metric", "#142" — every hit triaged; `python -m
   tools.glossary_index --write`; the prose-scraper set green.
5. #535's rider: `tests/test_primitive_reads.py` ~434 and
   `cardlang/runtime/narrowing.py` ~39 rewritten to the end state.

## Delivery shape

One PR (operator merge; Codex the operator's spend): the stage-3 closing
PR. Body: `Closes #535`; `Part of #142` with the stage-3 and third-residual
boxes named for the operator's tick (the epic's boxes are his). Chain:
opus implements (differential-before-eviction, grid red first) ->
adversarial review (Fable: the observability ruling and the closed-domain
retirements) -> fix round -> PR -> CI -> Ben merges and ticks. After it:
stage 4 (co-location) and #232 in parallel.

## The Architect's counsel (2026-09-04 — issue #142's third residual: evicting `coup_game_summary`, and the stage-3 legacy-table deletion that follows it)

**Headnote.** The decision is narrower than "how do we evict the last emitter": it is which channel carries three public facts once the only Python that reported them is gone, and whether the tables that existed to dispatch such Python leave in the same change or the next. The settled law, in plain words: every state variable is public to every observer and is never carried by an observation event — the information state reads it straight off the live world — while hidden information lives only in zones and reaches observers through movement views; a refusal arm no input can reach is a check that cannot fail; an empty grid is refused at collection in this house, not skipped; and a live registry row may not serve as a test fixture, because the rows are what the corpus is migrating off. Executed today: the emitter's card total is the driver's own terminal census, already emitted for every game (15 of 15 on all 40 seeds), so that half was always a second derivation of a kernel fact; its coins and alive vector equal the one frame standing at the terminal moment on 40 of 40 seeds, and treasury plus coins is 50 there on all 40; the pinned golden reproduces byte-for-byte from that frame plus the census plus the reveal derivation stage 1 already owns; and the command-line player already reads the terminal world exactly this way, through two seams that exist and are pinned. Removing the dead `let` leaves every per-observer stream, every other trace, and every result identical on 40 of 40 seeds. On a scratch copy with only the eviction applied, 18 sites go red or uncollectable, and every one of them has a dead premise — a legacy call-namespace member exists, an emitting contract has a member, coup's row exists — none is an uncovered cell; the chain from "no member" through "no refused contract" to "the allow-list equals the enum" runs on its own, so the contract partition's allow-list retires inside the eviction, not after it. After the eviction and nothing else: 0 of 44 Primitives keep a legacy arm, 6 of 6 authored reads rows are the walled binders' own, the dispatcher has no arm, and the contract populations are 40 bundled, 4 pure, none emitting. Recommended: the harness reads the terminal public state where the information state and the command line already read it, through the existing first-decision handle at the existing terminal moment, with no engine line added; the eviction ships as one change that also retires every premise-dead pin and the emitting contract with its allow-list; the table deletion — the dispatcher, the declared-only set, the signature table's Primitive half moving to a column on the implementation index, the reads registry's contract — is a second change stacked on the first and armed behind it, so the mechanical re-derivation is reviewed on its own diff and main carries the dead dispatcher only for the window between two merges. Rejected: a new state-assignment trace or observation kind (a firehose for three terminal values, and an observation kind would move every game's proof), a kernel coin invariant (the kernel has no notion of which integers are money), and a harness re-simulation of the coin economy as the golden's source (a second copy of the rules, which conserves even when it drifts — it is offered as a later differential, never as the source). Newly impossible after the pair: a Primitive with a hand-written arm, a Primitive reached in any regime but by declaration, a Primitive signature outside the implementation index, a call-namespace reads row, and an implementation contract no dispatch site handles; newly required, for whoever adds a Primitive: one index row carrying its module, attribute, contract and signature, beside its name in the names registry. Information sets do not move — a trace emission leaves, no observation site changes, proven by the 40-of-40 stream identity and the untouched proof module. Precedent standing: every citation below is established; no unverified lead is relied on. Bottom line: evict now on the terminal-state read, retire the emitting contract and every dead-premise pin in the same change, stack the table deletion behind it, and tick the stage-3 box on the second merge; the strongest reason against is that the two-change shape lets main carry an armless dispatcher and a set equal to its own registry for the length of one merge window, and that the terminal read rests on the driver's ordering — emit before the pop — pinned today by one command-line test; the cost is a stated citation of that pin as the reader's owner and a window measured in minutes, not a return-value seam nobody else needs yet. The operator decides one thing: that "full elimination" for the stage-3 tick means the second change's end state — no arm, no declared-only set, no Primitive in the signature table, no call-namespace row, no allow-list — and not the first change's, which already empties the legacy half.

### 1. The decision

Not whether to evict (the epic ruled it) and not how the block reads (no surface moves). The engine choices:

(a) Which channel carries `coins`, `treasury`, `alive` and the two conservation totals once `cardlang/runtime/coup.py` is gone, and what the goldens and proofs must show.
(b) Whether the eviction and the legacy-table deletion are one change or two, in what order, and what "full elimination" means concretely in the tree.
(c) The shape of the signature column on `PRIMITIVE_IMPLEMENTATIONS`, its consumers, and what becomes illegal.
(d) What becomes of `DECLARABLE_CONTRACTS` and its refusal arm when the allow-list equals the enum.
(e) What `PRIMITIVE_READS` and its two pins say when every surviving row is a walled binder's, and issue #535's two sentences.
(f) The Contract deltas, the pins that redden, and the grid frame.
(g) The info-set verdict.
(h) The Merge Lane, and whether Hoyle sits.

### 2. The law

- **decisions.md, "Hidden information lives only in zones; state is public."** "Every `state` variable ... is public to every observer, always"; an observer's knowledge is "their zone projections plus the public state and public move history". The observation vocabulary is `EVENT_TYPES = {chose, announce, move, reveal}` (`cardlang/runtime/observe.py:47`) and no event names a state variable (measured: none over 40 seeds). `cardlang/openspiel/infostate.py:54-69` renders public state by merging `rs.frames` — the information state reads state off the live world by design. This decides (a): a public state variable is read where it is produced, not reconstructed from a stream that does not carry it.
- **decisions.md, "Closed-domain completeness."** "Vacuously green" ranks with accepted-but-ignored; a check no input can reach is a check that cannot fail; `xfail(strict=True, raises=...)` over `skip`; an undecided cell is an open question, never a mark. "Allow-list, never deny-list" and "Enforcement follows the domain's visibility to the type checker: where a closed domain is a Python union, the allow-list is a type error: every consumer dispatches with a structural `match` ending in `typing.assert_never`." "Prefer the guard you cannot need": a pin whose fact could have been a type is built on the wrong rung. This decides (d).
- **pyproject.toml:126, `empty_parameter_set_mark = "fail_at_collect"`.** A derived grid with no members is a collection error. Executed: with the eviction alone, `tests/test_primitives_block.py` fails to collect on `test_an_undeclarable_contract_is_refused_by_name` (line 2211) — the refused-contract set is empty. This is the house saying an emptied refusal grid may not stand.
- **The synthetic-row rule**, `tests/test_primitive_narrowing.py:888-916`: "A live registry row cannot serve — the rows are the thing the corpus is migrating off, so any one of them can be deleted by a migration that has no reason to look here." Two module-level fixtures violate it today — `_COUP_ROW` at `tests/test_primitive_reads.py:550` and `tests/test_primitive_narrowing.py:1240` — and both take their module down at collection on the eviction. The rule the narrowing module wrote for itself binds its sibling.
- **The cribbage plan's settled reasoning for SITE_READ** (`docs/plans/2026-09-04-cribbage-nested-phases.md`, Gate 1 and option (e)): "a refusal arm no input can reach is a check that cannot fail ... The member retires with its refusal branch and its cells; the partition re-derives." Ruled by doctrine, not counsel, and it applies to `EMITTING` by the same words. My own line there stands: the proper-subset pin "reddens the day coup is evicted — the right red, at which point the allow-list is total and the arm retires with it".
- **The 3b plan's closing step** (`docs/plans/2026-08-29-primitives-block-stage3b.md`, "Closing steps"): `PRIMITIVE_READS` loses its last call-namespace row only when every wall has fallen; `CALL_SIGS`' Primitive half is deleted and the signature moves to a column on `PRIMITIVE_IMPLEMENTATIONS` with `implementation_sig` the one-site seam; "the box is the operator's tick, on full elimination, never on the wave alone." Not re-litigated; (b) and (c) execute it.
- **resolve's Contract** (`cardlang/resolve.py:88-96`): the declared-only arm refuses "a call, in a game that writes no `primitives { }` block, to a Primitive that has no legacy dispatch arm"; `runtime/primitives.py`'s `call` fallthrough is its Shadow Guard. **primitives.py's Contract** (`cardlang/runtime/primitives.py:19-26`): "a value for every game-local call, or the loud refusal below"; "the metric is the REGISTRY ... never the count of arms". **primitives_block's Contract** (`cardlang/primitives_block.py:26-76`): a front-end leaf, "names and classifications only, never types (`typecheck.type_from_name` is the one conversion site)" — yet `implementation_sig` (686-701) already returns a `Sig` from it. **reads.py's Contract** (`cardlang/runtime/reads.py:30-53`): every name-keyed read is declared in `PRIMITIVE_READS` or a block, and fails typed. **typecheck's Contract** (`cardlang/typecheck.py:19-40`): the one sanctioned materialization is `declared_primitive_sigs`.
- **CLAUDE.md, "Prose states what is"** and decisions.md "Prose names the registry, never the cardinality": every sentence that today says "the one member", "arms below", "one hand-written arm per name" is a present-tense claim that goes false.

### 3. Precedent

- **P2** (Area 1, nanopass — materialize in the owning pass, never re-derive downstream): the card census is the driver's fact (`cardlang/runtime/driver.py:354, 393-410`); the emitter re-derived it. The terminal public state is likewise the driver's — read at its site.
- **P9** (Area 4 — one source, every scrape derived and pinned): the total-cards fact has one source after the eviction; the coins fact has one source (the frame), read by the information state, the command line, and now the harness.
- **P11** (Area 5 — an oracle is trusted after a planted fault, and never calls the code it judges): the harness reader's write-time differential against the live emitter (below, 40 of 40) is its admission test; a harness re-simulation of the coin economy would be an independent derived oracle — which is exactly why it is not the golden's source but a later differential.
- **P13** (Area 6 — declared-once, emitted-uniformly): the eviction removes the last per-game trace emission from a Primitive; nothing per-game is added anywhere.
- **P1** (Area 1 — a contract that matters is a checked artifact): the reader's premise, "the driver emits `game_end` after the last phase and before it pops the game-level frame", is a comment in `cardlang/cli.py:228-233` pinned by `tests/test_cli_surface.py::test_play_reaches_a_terminal_position` (line 331). A second consumer cites that pin as its Owner; if it wants a rung higher, the promotion is a return value (option A'' below), not another comment.
- Area 5's oracle taxonomy (Barr et al.): the golden is a regression pin, not an oracle; the invariant test is a restated-invariant oracle over public facts — its value is that the 50 and the 15 are the test's numbers, not the engine's.
- House precedent: stage 1's derivation (`tests/playout_trace.py`); the `hand_end` trace (`driver.py:504`); the command line's terminal read (`cli.py:222-240`); `_BUNDLE_ROW`'s synthetic-row rule; the SITE_READ retirement; my 3b counsel's row-grain carve-out (`tests/test_primitives_block.py:2495-2508`).

Standing: every citation established; no unverified mark relied on.

### 4. The options

**(a) The channel.** Executed (`.venv/bin/python`, 40 seeds): the kernel emits exactly two trace kinds for Coup, `coup_game` and `game_end`; observation kinds are `move`, `chose`, `announce`, `reveal`; no observation event mentions `coins`, `treasury` or `alive`. At `game_end` exactly one frame stands (depth 1), holding `alive`, `coins`, `treasury` — the emitter's whole input. The emitter's `total_cards` equals `game_end["total"]` (15) on 40 of 40; its `coins`/`alive` equal the frame on 40 of 40; `treasury + sum(coins)` is 50 on 40 of 40; `GameResult.scores` is the alive vector (`winner: highest alive`); and `{reveals, coins, alive, winner}` rebuilt from the frame, the census and `CoupReveals` equals `tests/golden/coup_scores.json` on 40 of 40. So the facts split by the law: the zone censuses are zone facts and were never the emitter's — the driver's terminal census already carries the total and observer 0's count views carry the per-zone counts; `coins`, `treasury`, `alive` are public state, carried by no observation and readable off the world by every observer.

- *(i) A state-assignment trace kind* — rejected. A per-assignment trace is a firehose answering a question nobody asks (only terminal values are needed); as an observation kind it would enter every game's observation stream and move every proof module, for three numbers at one moment.
- *(ii) The harness reads the final `RuntimeState`* — **counseled**, through the two seams that exist: `play_game(..., on_first_decision=hold)` hands the harness the live `rs`; the `game_end` trace fires after the last phase and before the game frame pops (`driver.py:346-354, 387`), which is the terminal position. `cardlang/cli.py:222-240` does exactly this today to render the terminal information state. The harness reader (`tests/playout_trace.py`, a `CoupSummary` or a general `TerminalState`) captures `rs.get("coins")`, `rs.get("treasury")`, `rs.get("alive")` at `game_end`, and the census from the same payload; `total_coins` is computed at the harness. This is not an omniscient oracle: it reads what the law makes public, where the information state reads it. Cost, honestly: the reader's correctness rests on the emit-before-pop ordering, pinned only by the command-line test, and the hook never fires for a game with no decision (none in the corpus). The reader's docstring cites `test_play_reaches_a_terminal_position` as its Owner, and names the promotion event: a second consumer of terminal state, or a decision-free game needing it, promotes the fact to a return value.
- *(ii') `game_end`'s payload gains the game-level frame*, or *(ii'') `GameResult` gains a `state` field* — the promotions of (ii). Both are one kernel line and uniform; (ii'') is the higher rung (a return value cannot be read at the wrong time). Neither is needed by this change, and the eviction's engine diff should stay a deletion. Recorded at the reader, not as an issue — the trigger is named.
- *(iii) A kernel coin invariant* — rejected. The card census is already a kernel invariant because it counts every zone; a coin census needs the kernel to know which Integer state is money, and no declaration says so — Coup models coins as Integer state by its own text, not as a `Resource` zone. Either a game-text change for the harness's convenience (the game bending to the instrument) or a kernel guess.
- *(iv) Invariants stated in the DSL* — Hoyle's; no construct exists; named as the long-run home, not this change's.
- *A harness re-simulation of the coin economy from the announce/reveal/move streams* — every outcome is publicly observable (challenges announced, proofs revealed, flips public), so coins are publicly derivable; but as the golden's source it is a second copy of the rules that conserves even when it drifts. Offered as a later differential oracle (P11, Area 5), never as the reproduction.

What the goldens and proofs must show: `tests/golden/coup_scores.json` byte-identical from the new source at its own width (40 seeds — the golden's width, which is also the regeneration width); `tests/test_playout_coup.py` asserting 50 and 15 from the reader over 40 seeds; `tests/openspiel_ready/test_coup.py` untouched; the write-time differential (reader against the live emitter, 40 of 40, dated) recorded in the eviction grid's ledger as stage 1 recorded its own.

**(b) The retirement's shape.** Executed on two scratch copies of HEAD with the eviction applied (game line 88, `coup.py`, the arm, the names-registry row, the flavor row, the signature row, the index row, the reads row) — one keeping `EMITTING`, one retiring it. First run, 16 modules: 6 failed, 9 errors, 582 passed — with two of the six fails scratch artifacts (the classification-prose pin walks `git ls-files` and the copy had no index; indexed, both pass). The errors were three collection failures: the two live-row fixtures, and the emptied refusal grid. With those three neutralized, the second run over the five affected modules: 13 failed of 1111 with `EMITTING` kept, 12 of 1111 with it retired — and every red has a dead premise:

- the legacy-half representative (`_LEGACY_HALF_NAME`, `tests/test_primitives_block.py:658-672`) and the three legacy-axis cells of the regime product (they die on a `KeyError` in `CALL_SIGS`, not the designed `DiagnosticError`, so the strict mark cannot even hold them) — the legacy axis retires whole, as ruled at cribbage;
- `test_the_declarable_contracts_are_a_proper_subset` — red in BOTH copies: its second assertion ("some registered Primitive carries a refused contract") dies on the eviction alone; `test_every_invocation_contract_has_a_member` — red with `EMITTING` kept, green with it retired. The chain is measured: eviction -> a member with no population -> retire the member -> an allow-list equal to its enum -> retire the allow-list and its pin;
- `test_an_empty_block_refuses_a_legacy_primitive_call` — its message lost the block hint because the name is no longer a Primitive; re-derive the representative from the declared-only set;
- `EMITS_TRACE`'s two cells and `test_progress_registries_name_real_things` (`NARROWED`/`MIGRATED` name coup) — the (e) grid's registry empties, and an empty registry under `fail_at_collect` cannot stand: it retires, its guarantee already held by grid (b)'s `ctx.trace` column over every module;
- `test_probe_stale_registry_entry_fails_the_source_pin` scans `coup.py` — re-anchor on a surviving module;
- `test_shadow_wall_still_guards_registered_names` and `test_implementing_symbol_gone[coup_note_reveal]` in the stage-1 grid — the control re-points at a declared-only name; the symbol cell becomes a module-absent cell;
- `test_playout_coup.py` and the coup characterization capture — the design step.

Nothing in that list is an uncovered cell to mark `xfail`; each is a pin whose premise the eviction falsifies, and each is answered in the eviction. So: **the eviction change carries every premise-dead pin, the `EMITTING` member, `DECLARABLE_CONTRACTS` with `undeclarable_contract` and resolve's contract arm (`resolve.py:5287-5295`), `_bind`/`_emit`/`TraceEvent`/the `traced` scrape branch (`tests/test_signatures.py:269, 355-377, 504-516`), the two fixtures made synthetic, the stage-1 grid extended, the harness reader, the new-source playout and capture, and the prose sweep.** After it, measured on the copy: `PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS` is empty (0 of 44), `primitives.call` has zero literal arms, `PRIMITIVE_READS` has 6 rows and all 6 are `_walled_binder_rows`, contract populations 40/4/0, and `CALL_SIGS` still carries the 44 Primitive rows.

What the eviction leaves green but vacuous: an armless `call()` behind `native_call`'s legacy fall-through; `DECLARED_ONLY_CALL_FUNCS` equal to its registry (an authored copy of a derived fact); the dispatch-split grid's "primitives" home comparing empty to empty; the signature table's Primitive half with `implementation_sig` its one reader. None reddens; all are the "check that cannot fail" shape. **Ruling: two changes, stacked, one merge sequence.** The eviction is a design step (the channel) plus deletions; the table deletion is a mechanical re-derivation across `primitives_block.py`, `signatures.py`, `functions.py`, `typecheck.py`, `evaluate.py`, `primitives.py`, `reads.py` and about nine test modules. Folding them buries the one design decision under thirty registry hunks (the merge-by-diff lesson); deferring the second to the tracker leaves vacuous machinery on main with no trigger. So the second is opened stacked on the first and armed behind it, its end-state pins authored red in its first commit against the first's tip. If the operator prefers one review, the second's commits move onto the first's branch unchanged — the sequence is identical, only the review boundary moves.

"Full elimination", concretely in the tree, for the stage-3 tick: (1) `runtime/primitives.py` has no `call` and `evaluate.native_call` has no legacy Primitive fall-through — the Builtins arm or the declared table, nothing else; (2) `DECLARED_ONLY_CALL_FUNCS` is gone, resolve's arm keys `PRIMITIVE_CALL_FUNCS`; (3) `set(CALL_SIGS) == BUILTIN_CALL_FUNCS` and every `Implementation` carries its `sig`; (4) every `PRIMITIVE_READS` row is one a walled binder binds, pinned positively; (5) `InvocationContract` is `{BUNDLED, PURE}` with no allow-list beside it. (4) and (5) land in the eviction; (1)-(3) in the closing change. The box ticks on the second merge.

**(c) The signature column.** `Implementation` gains a required field `sig: Sig`, authored beside `module`, `attribute`, `contract`; `implementation_sig(name)` returns `PRIMITIVE_IMPLEMENTATIONS[name].sig` (None for an unregistered name — its signature does not move, so its consumers do not: `_check_primitive_signatures` (`typecheck.py:1054`), `tests/test_native_call_boundary.py:70-89`, the element allow-list pin, the collection-return pin). Deriving the column from Python annotations is rejected on a measured fact: `_python_type` maps `Player`, `Team` and `Integer` all to `int` and skips collections and `TAny` — the annotation cannot state a DSL type, so the `Sig` is authored and the annotation pin stays as the cross-check of two independent statements, iterating `CALL_SIGS` for Builtins and the index for Primitives. The leaf's "never types" sentence rewrites to what it will be: names, classifications and each implementation's STATED signature as data; conversion from a spelling stays typecheck's. Consumers of the Primitive half, by grep: `native_call_sigs` (`typecheck.py:1096-1106`; the LEGACY branch returns `CALL_SIGS`, which is then Builtins only — correct, since a legacy game's Primitive call is refused at resolve); `TypeEnv.call_sigs`' default (577); the registry-divergence assertion's comment (700-703); `evaluate.native_call` (44, 52: `CALL_SIGS.get` serves Builtins only after); `tests/test_permissive_top.py:229-232` (`set(CALL_FUNCS) == set(CALL_SIGS)` becomes `set(CALL_SIGS) == BUILTIN_CALL_FUNCS`, with the Primitive side's reconciliation already the index's import-time assert); `tests/test_signatures.py` (the union in `_call_dispatch_facts`, `_declared_facts` reading `impl.sig`, the arity and annotation pins over the union; its ledger's "every name in a tabled registry has a signature row" names the column as the Primitive table); `tests/test_primitives_block.py` (`_entry_and_body` and the collection-signature cell read `implementation_sig`; the freeze cell plants into the index's entry instead of `CALL_SIGS`); `tests/test_trace_emitter_eviction.py::test_not_in_signature_table` checks both tables. Illegal after: a Primitive name keyed in `CALL_SIGS` (pinned both ways); an `Implementation` with no signature (unrepresentable — rung 1); a `Sig` for a Primitive built anywhere but the index or `_param_type`.

**(d) The contract partition.** With `EMITTING` gone the enum is `{BUNDLED, PURE}` and `DECLARABLE_CONTRACTS` equals it: `undeclarable_contract` returns None for every input, resolve's arm is unreachable, the refusal grid is empty and refused at collection, and the proper-subset pin is false by design. Keeping the allow-list "as the guard a future contract would have to join" keeps a frozenset a test compares — rung 2 — when the domain is a Python enum the checker can see. The deny-list shape is real and lives elsewhere: `driver.py:156` (`bundled=impl_ref.contract is InvocationContract.BUNDLED`), `tests/test_signatures.py:308` (the same test) and `resolve.py:5394` (`is InvocationContract.PURE`) each treat every non-named member as the other one, so a third member would silently dispatch as pure with no allow-list left to stop it. **Ruling:** retire `DECLARABLE_CONTRACTS`, `undeclarable_contract`, the resolve arm, the proper-subset pin and the emptied grid; keep the enum as the dispatch-shape partition; convert those three comparison sites to a structural `match` ending in `assert_never`, so a third member is a `mypy --strict` error at every consumer — the allow-list moved to rung 1, per "Enforcement follows the domain's visibility to the type checker"; keep `test_every_invocation_contract_has_a_member` as the registry-side reconciliation (an arm with no member reddens), which is what makes "a new contract arrives with its witness" a checked fact. The reads-shape cross (`_READS_SHAPE_CELLS`) derives over the enum instead of the allow-list; its cells do not change.

**(e) The reads registry.** After the eviction the six rows are bigtwo, president, tichu (the climb binder's, `primitives.climb_row`) and bridge, pinochle, french-tarot (the auction outcomes' rows in the shared dispatch module) — all six walled (measured). `reads.py`'s docstring (1-28) states the pre-block world — "the single registry of every zone/state name each primitive module reads" — and rewrites to what it is: the declaration for the two namespaces the block does not cover, whose binders bind a module row at load; the accessors and `game_reads` serve both those rows and the block-derived rows. Its Contract's `establishes` is already true and stays. Issue #535's two sentences: `narrowing.py:38-39` ("the primitive's module has a `PRIMITIVE_READS` row") becomes "a row — the entry's own, built from its declaration, or a walled binder's authored one"; `tests/test_primitive_reads.py:433-434` ("a module with no registry rows must make no accessor reads at all") becomes "a module with no rows and no declaring game makes no reads; a module whose reads are declared in blocks is held to those blocks' union". The reconcile pin's claim (3) is not vacuous: its row plant (`test_reconciliation_reddens_on_a_dual_definition_site`) proves it still reddens on a call-namespace row for a declared game, which is exactly the regression it guards; what it proves at the end state is "no authored row states a coupling any block states". Add the positive form as a born-green pin: `{(r.module, r.game_file) for r in PRIMITIVE_READS} == _walled_binder_rows(PRIMITIVE_READS)` — red under adding a call-namespace row — the tick's executable form. Both halves of the exemption stay non-empty (3 climb rows, 3 auction rows), so `test_the_walled_exemption_names_the_rows_the_binders_bind` keeps discriminating. The module-source scan's domain is unchanged: rows union blocks per module; `coup.py` leaves the glob.

One gain to quote in the eviction's PR body: `tests/metamorphic/rename.py::_coupled_names` (137-163) derives its exclusions from the rows, so Coup's six coupled names (`influence`, `revealed`, `court_deck`, `coins`, `alive`, `treasury`) become renamable under the rename metamorphic — run it on Coup and report.

**(f) The grid frame.** Extend `tests/test_trace_emitter_eviction.py` — the stage-1 shape is the right one: `EVICTED` gains `("coup_game_summary", "cardlang.runtime.coup")`; `test_implementing_symbol_gone` splits into a symbol cell and a module-absent cell (the file does not exist and the import fails); the shadow control re-points at a derived declared-only name; `test_not_in_signature_table` reads both tables; the ledger's `residual:` row is dropped (nothing remains — the format says omit), `sampled:` records the 2026-09-04 differential (reader against the live emitter, 40 of 40) and names the standing witnesses (the golden at its 40-seed width; the invariant test on the reader); the rejection corpus gains `call_evicted_trace_emitter_coup_summary` on the stage-1 pattern (the dead `let`, refused as an unknown function). The closing change's end-state pins are re-derivations inside the modules that own them (the dispatch-split grid's homes become {builtins, declared}; the permissive-top and signatures reconciliations; the positive reads pin) — no new module.

**(g) Information sets.** Do not move: a trace emission leaves the harness channel and no observation site changes — executed, 40 of 40 seeds identical in every per-observer stream hash, every non-`coup_game` trace, and the result, with the dead `let` removed; `tests/openspiel_ready/test_coup.py` untouched.

**(h) Sequencing and lane.** No grammar moves and no accepted sentence changes meaning; the `EMITTING` refusal's retirement changes only which arm speaks for a name that no longer exists — `primitives { coup_game_summary() : Integer }` is refused today by the contract arm and after by the unimplemented arm, the same verdict — so Hoyle does not sit. By `docs/harness.md`'s table the eviction touches `cardlang/runtime/**`, `cardlang/builtins/**`, `cardlang/primitives_block.py`, `cardlang/resolve.py`, a corpus file and tests with behavior claimed: **Merge Lane B, operator merge**, both changes. The stage-3 tick is the operator's on the second.

### 5. What becomes illegal after — the Contract deltas

- **runtime/primitives.py** (eviction): `_bind`, `_emit` and the coup arm go; the docstring's "arms below are the LEGACY dispatch seam" paragraph and the "metric is the registry, never the count of arms" sentence rewrite to the declared route; `Establishes` becomes "a value for every declared call (`call_declared`); the walled dispatchers keep their arms". (closing): `call` goes; illegal after: any arm for a call-position Primitive.
- **runtime/evaluate.py** (closing): `native_call`'s legacy branch falls from the Builtins arm to the same `ShadowGuardError` the declared branch raises, naming resolve's arms.
- **runtime/narrowing.py** (eviction): `TraceEvent` and its paragraph retire; the Contract's `assumes` line is #535's rewrite; illegal after: a Primitive returning events.
- **runtime/reads.py** (eviction): the coup row goes. (closing): the docstring's world statement per (e); illegal after: a call-namespace row.
- **primitives_block.py** (eviction): `EMITTING`, `DECLARABLE_CONTRACTS`, `undeclarable_contract` retire; the enum docstring stops counting. (closing): `Implementation.sig`; `implementation_sig` reads the column; the leaf sentence per (c); illegal after: a consumer comparing a contract by `is` outside an exhaustive `match`; a Primitive signature outside the index.
- **resolve.py** (eviction): the contract arm (5287-5295) retires. (closing): the declared-only arm keys `PRIMITIVE_CALL_FUNCS`; the Contract clause at 88-96 rewrites to "a call, in a game that writes no block, to any Primitive"; `_undeclared_primitive_hint` unchanged.
- **typecheck.py** (closing): `native_call_sigs`, the `TypeEnv.call_sigs` default and the divergence comment per (c); `Now illegal` gains "a Primitive `Sig` read from `CALL_SIGS`".
- **builtins/functions.py** (eviction): the name leaves `PRIMITIVE_CALL_FUNCS` and `ANY_FLAVOR_CALL_FUNCS`. (closing): `DECLARED_ONLY_CALL_FUNCS` retires with its comment block (241-254, which already names this inversion); illegal after: a Primitive reached by any route but declaration.
- **builtins/signatures.py** (eviction): the row goes. (closing): the Primitive half goes; illegal after: a Primitive key.
- **driver.py**: no runtime line moves in either change; the `bundled=` site becomes a `match` (d).
- **Corpus and prose**: `docs/games/coup.cardlang:88`; `docs/library.md:1003-1011` (the entry goes; Coup then "carries no module", the Schnapsen sentence); `docs/kernel-migration.md:36` ("Coup's in-game scans and trace emitters" is false after); `docs/design-notes/primitive-sidecars.md` item 3 of section 1, the emitters bullet of section 3, stage 1's residual and stage 3b's status in section 5; `docs/glossary/primitive.md` line 3 ("one hand-written arm per name; that arm count is the elimination metric" — false after the closing change; regenerate `docs/glossary.md`); `tests/test_primitives_block.py`'s ledger sentences on the legacy half and `_NO_REPRESENTATIVE`; `tests/test_primitive_narrowing.py`'s ledger rows (e) and the `EMITS_TRACE` registry line; `tests/test_signatures.py`'s ledger; the coup capture's provenance comment in `tests/test_migration_characterization.py:1118-1128` gains the same sentence for coins and alive. Dated plans and the dated inventory stay as written.

### 6. Counsel

**For.** The channel needs no engine line: the law already makes the facts public, the driver already emits the terminal moment, the command line already reads it, and the golden reproduces byte-for-byte on every seed it holds. The eviction's engine diff is pure deletion, and the pins it reddens are all dead-premise pins the change answers — measured, not argued. The contract allow-list retires onto a rung the type checker holds, which is where the doctrine says a closed enum's consumers belong. After the two changes a Primitive is added in exactly two places — its name and its index row — and reached by exactly one route.

**Against, strongest.** Two-fold. The terminal read composes two seams for a purpose neither was built for, and its premise — emit before pop — is a comment pinned by one command-line test; a return-value seam would be unrepresentably safe, and this counsel declines it on proportion. And the two-change shape lets main carry an armless dispatcher, a set equal to its registry, and a table half with one reader for the window between two merges — green, vacuous, and named; the single-change alternative buys a clean main at the price of a review that cannot see the design step under the plumbing.

**What the Architect would do.** Land the eviction on the terminal-state reader with the differential quoted and dated; retire `EMITTING`, the allow-list, its arm and its pins in the same change with the three comparison sites converted to exhaustive matches; make the two live-row fixtures synthetic; extend the stage-1 grid; sweep the prose sites named above assuming a miss; run the rename metamorphic on Coup and quote the gain; open the closing change stacked on it with its end-state pins authored red in its first commit; arm the second behind the first; and hand the operator the tick on the second merge.

### THE BOTTOM LINE

**Verdict.** Evict now: the harness reads `coins`, `treasury` and `alive` off the terminal world through the existing first-decision handle at the existing `game_end` moment — the command line's own idiom — and takes the card total from the driver's census it always duplicated; the golden reproduces on 40 of 40 seeds and the streams are identical on 40 of 40. The eviction change carries every pin whose premise it kills — measured at 18 sites, none an uncovered cell — including the `EMITTING` member, `DECLARABLE_CONTRACTS`, its arm and its two pins, with the three contract comparison sites promoted to exhaustive matches. The legacy-table deletion — the dispatcher, the declared-only set, the signature half moving to `Implementation.sig`, the reads registry's contract, #535 — is a second change stacked on the first and armed behind it. Merge Lane B, both; Hoyle does not sit.

**The strongest against, and its cost.** The terminal read rests on the driver's emit-before-pop ordering, pinned by one command-line test, and the stacked shape lets main carry vacuous plumbing for one merge window. The cost is a citation of that pin as the reader's Owner with the promotion event named at the reader, and a window measured in minutes; the alternative — a return-value seam and a single thirty-hunk change — buys nothing this change needs.

**What the operator decides.** One thing: that "full elimination" for the stage-3 tick is the second change's end state — no `call`, no `DECLARED_ONLY_CALL_FUNCS`, no Primitive in `CALL_SIGS`, every reads row a walled binder's, no contract allow-list — and not the first change's, which already empties the legacy half. If he prefers one review instead of two, the second change's commits ride the first's branch unchanged, and the tick is that merge.

## Framing check (2026-09-04, fresh-context over the trace channel, the emitting contract, the legacy seam, the reads registry, the goldens and the prose — attached as a dated record)

# Framing check: eviction of `coup_game_summary` — derived domain

Baseline: `origin/claude/cribbage-nested-phases` @ 9044736 (PR #575 head), read detached; main checkout restored to 11d0d557 (detached, as found). All probes below ran on that baseline with `.venv/bin/python`; scripts in the scratchpad (`probe_a.py`, `probe_b.py`, `probe_golden.py`, `probe_rename2.py`).

Control: the pins this change touches are green today — `pytest tests/test_trace_emitter_eviction.py tests/test_native_dispatch_split.py tests/test_signatures.py tests/test_primitive_reads.py` → `229 passed`; `test_primitives_block.py -k "contract or regime or legacy or …"` → `150 passed, 1 xfailed`; `test_primitive_narrowing.py -k "emits or progress or engine_core or …"` → `8 passed`.

## 1. The trace channel

**Every `ctx.trace` emitter in `cardlang/`** (grep `\.trace(` over the package):

| kind | site | payload shape | stream |
|---|---|---|---|
| `game_end` | `runtime/driver.py:354` | `_final_card_census(rs)` → `{"total": int, "hands_with_cards": int, "total_value": int}` (`driver.py:378-394`; `hands_with_cards` keys on the magic `hand` family → 0 for coup) | tracer; emitted BEFORE `rs.pop_frame()` (`cli.py:227-235` relies on this) |
| `hand_end` | `driver.py:504` | `dict(rs.get(score_var))` | tracer; only inside a PHASE-level `repeat until` qualifier with a score var — coup's repeat is a statement inside `phase play`, so never emitted (probe A: `hand_end_seen 0/40`) |
| `decision` | `runtime/mechanics.py:130` | `(actor, choice)` | tracer; round forms only (coup has none) |
| `play` / `trick_end` / `trick` | `mechanics.py:247`, `:259-261` (`{"early","trump"}`), `:287` (`(winner, [cards])`) | trick form only |
| `bridge_contract` / `pinochle_contract` / `tarot_contract` | `runtime/primitives.py:356,380-389,413,416-418,431,434` | dicts | tracer; auction outcomes hold `ctx` directly (narrowing residual (1)) |
| `coup_game` | `runtime/coup.py:41-49`, emitted by `primitives.py:59-64 _emit` from the arm at `:119-124` | `{"total_coins", "total_cards", "coins": {p:int}, "alive": {p:bool}}` | tracer; the ONLY emission that rides a returned `TraceEvent` tuple |

- Tracer plumbing: `Ctx.tracer`/`Ctx.trace` `runtime/state.py:473, 489-491`; type `Callable[[str, Any], None]` `driver.py:239`. Consumers: `cli.py:227-235` (`game_end` only), tests (`tests/test_playout_*.py`, `test_migration_characterization.py`, `test_bridge_scoring.py`, `test_round_execute.py`, `test_lifecycle_hooks.py`, `test_card_points.py`, `test_stud_allin_ante.py`, `test_winner_target.py`). **Not the adapter**: `cardlang/openspiel/replay.py:259-265` calls `play_game` with `chooser`/`observer`/`on_first_decision` and no tracer; grep over `cardlang/openspiel/*.py` for `tracer` → only a comment at `game.py:93`.
- Observation channel: `runtime/observe.py:47 EVENT_TYPES = {chose, announce, move, reveal}`, shapes `:7-25`; sites `observe.choice/announce/movement`, `execute.py:200,224,272,305,512(reveal),713-714,826,857`, the replay chooser's `chose`; corpus sweep `tests/test_observe.py:146-175` (coup at depth 14). Ruling that the two channels are distinct: `tests/test_trick_order_migration.py:47-50` ("the trace channel is HARNESS-only and distinct from `observe`").
- **State assignments**: no trace kind and no observation kind carries an integer state value. Announces carry rendered decisions only (probe A seed 0: `('announce', 0, 'steal(2)')`, `('announce', 1, 'challenge')`).
- **What the harness derives today** (`tests/playout_trace.py`): `CoupReveals` (`:57-77`, observer 0's `move` events with dst `revealed[`) and `TichuHands` (`:80-139`) — observation stream only; docstring `:1-17`.
- **Probe A** (40 seeds, tracer+observer+`on_first_decision`): trace kinds coup emits = `{coup_game: 40, game_end: 40}`; obs kinds seed 0 = `announce 124, move 68, chose 31, reveal 8`. Reconstruction of the payload from what exists without the emitter:
  - `total_cards` == `game_end["total"]`: **40/40** (tracer stream alone).
  - `alive` == `GameResult.scores` (`driver.py:365-367`, `dict(rs.get("alive"))` since `winner: highest alive`): **40/40** (driver return alone).
  - `total_coins`, `coins`, `treasury`: in **no stream**. Reconstructible by holding `rs` from the `on_first_decision` seam and reading it at the `game_end` trace (the convention of `cli.py:224-235`, `tests/test_playout_canasta.py:52-64`, `tests/test_playout_five_hundred.py:375`): `rs_capture_total_coins 40/40, rs_capture_coins 40/40, rs_capture_alive 40/40, rs_capture_total_cards 40/40`.
  - Not executed: deriving coins from the observation stream (announce/move/reveal). Coup's coin economy is public, so it is derivable in principle, but only as a mirror of the game's own coin rules (the treasury clamps at `coup.cardlang:208,245,268,312`) — a second copy of the rules, the class the Hold'em memory warns about.

## 2. The EMITTING contract, end to end

- Enum member `cardlang/primitives_block.py:167-171` (docstring: "Not declarable: the one member is a trace emitter … issue #142"); row `:206`; `DECLARABLE_CONTRACTS` `:241-243` with the allow-list comment `:238-240`; `undeclarable_contract` `:711-718`; enum docstring `:150-155`.
- **Tuple split is NOT in `native_call`**: `runtime/evaluate.py:23-64` coerces (`:44-46`, `:52-54`) and chains `builtins.call → primitives.call`; the split is the arm `primitives.py:119-124` (`total, events = coup_game_summary(*_bind(ctx, ROW)); _emit(ctx, events); return total`). `_bind` `:52-56`, `_emit` `:59-64` — both have this one caller. `call_declared` `:96-113` has no EMITTING shape: `Declared.bundled: bool` `:84-86`; `driver.py:156 bundled=impl_ref.contract is InvocationContract.BUNDLED`.
- `TraceEvent` `runtime/narrowing.py:58-69`. Its docstring is already false ("emit the engine's own `play`/`trick`/`trick_end`" — no primitive has since #250 PR 5; `EMITS_TRACE` holds one name). Consumers: `primitives.py:59`, `coup.py:19,26,41`, `tests/test_signatures.py:509` (`tuple[narrowing.TraceEvent, ...]`), `docs/glossary/trace-event.md` (home `narrowing.py`, "from a primitive or the engine"), `docs/glossary.md:113`.
- Resolve refusal arm `cardlang/resolve.py:5292-5299` (message "(it is {contract.value}) … see issue #142"). At zero members `undeclarable_contract` is constant `None` → an arm that cannot fire.
- Pins naming EMITTING / the member, and what each does at zero members (executed where marked):
  - `tests/test_primitives_block.py:479-486 test_every_invocation_contract_has_a_member` (`used == set(InvocationContract)`): **RED while EMITTING stays in the enum** (probe C: contracts used after = `{bundled, pure}`).
  - `:489-500 test_the_declarable_contracts_are_a_proper_subset` (`DECLARABLE < set(enum)` AND some refused member exists): **RED once EMITTING is deleted** (probe C: `False`) and its second assert is RED either way. The two pins are jointly unsatisfiable at zero members — the "right red" the cribbage plan predicted (`docs/plans/2026-09-04-cribbage-nested-phases.md:654`).
  - `:2211-2226 test_an_undeclarable_contract_is_refused_by_name` parametrized over `contract not in DECLARABLE_CONTRACTS` → empty → **collection error** (`pyproject.toml:126 empty_parameter_set_mark = "fail_at_collect"`, verified on a scratch test).
  - `:785-802 _NO_REPRESENTATIVE` and the xfail reason `:829-836` ("the legacy half's one member answers the EMITTING contract … the cell empties with coup's eviction (issue #142)").
  - `tests/test_primitive_narrowing.py:513-517 EMITS_TRACE`; `:526-532` (`EMITS_TRACE <= known`, fine when empty); `:1531-1556 test_tracing_primitive_returns_events` parametrized over `EMITS_TRACE` → empty → **collection error for the whole module**; `:1559-1571 test_no_unlisted_migrated_primitive_emits_traces` (stays, becomes the only direction); ledger `:35`, `:119` "(e) EMITS_TRACE two ways".
  - `tests/test_signatures.py:269 _DispatchFact.traced`, `:355-376` (the tuple-unpack arm parser), `:504-515` (traced branch) — dead code after; `mypy --strict` still types `:509`.
  - `test_the_declarable_contracts…`'s sibling `_READS_SHAPE_CELLS` `:1246-1300` (declarable side) unaffected.

## 3. The legacy seam after #575

- `call()` `primitives.py:116-139`: exactly one arm (coup) + the `case _` fallthrough (Shadow Guard comment `:126-131`, message "unknown legacy native function"). Executed: `PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS == ['coup_game_summary']`; contract census `bundled 40, pure 4, emitting 1`; `len(PRIMITIVE_IMPLEMENTATIONS) 45`, `len(CALL_FUNCS) 66`.
- After eviction `DECLARED_ONLY_CALL_FUNCS == PRIMITIVE_CALL_FUNCS` (probe C: `True`) — two hand-authored copies of one set. `functions.py:252-254` anticipates it ("Stage 3b inverts the set … the legacy arms go with the window"). Consumers of `DECLARED_ONLY_CALL_FUNCS`: `resolve.py:7904-7930` (the declared-only Owner Guard, message "declare it in one to call it"; Contract prose `:88-96`), `test_native_dispatch_split.py:172,204-216`, `test_signatures.py:211,304`, `test_primitives_block.py:667,806-819`, prose in `test_canasta_guards.py:18,38,65`, `test_jointly_selection.py:76`, `tests/rejections/primitives_declared_only_no_block.*`, `primitives.py:137` (the fallthrough message).
- Dispatch-split pin `tests/test_native_dispatch_split.py:196-216`: `primitives_arms == PRIMITIVE_CALL_FUNCS - DECLARED_ONLY_CALL_FUNCS` → `∅ == ∅`, born-vacuous for the primitives half; `:184-193` per-name cells (coup's vanishes); `DISPATCHER_HOMES["call"] = "both"` `:93-103` → `test_dispatcher_home[call]` `:219-230` and `:233-240` **redden if `call()` is deleted** (`_name_dispatchers` `:115-151` needs a `match name:` in a module-level `call`).
- `tests/test_signatures.py:318-326 _facts_in`: `next(node … node.name == "call")` → **StopIteration (harness crash, not design-red) if `call` leaves `primitives.py`**; `:170-222 test_call_funcs_are_dispatchable` asserts every declared-only name falls through with the AssertionError text at `:215` — and swallows any non-AssertionError (`:221-222`), so a fallthrough re-channelled to `ShadowGuardError` (MRO: `GameDescriptionError → Exception`, not `AssertionError`; probe C) would pass this cell silently. Probe F: today a legacy-regime call of `gin_deadwood` → `AssertionError: unknown legacy native function …`; a declared-regime miss → `ShadowGuardError`.
- Regime product `tests/test_primitives_block.py`: `_LEGACY_HALF_NAME = "coup_game_summary"` `:658`; `:661-671` **reddens** (probe C: legacy half `[]`, and its own message's `sorted(legacy_half)[:3]` is `[]`); `:675-683`, `:2169-2179` written at that name (the latter's counterfactual — "this same call in a game with no block RESOLVES" — becomes false for every Primitive); `_homes()` `:806-819` returns the name unconditionally and `_entry_and_body` `:771-773` reads `CALL_SIGS[name]` inside the parametrize → **KeyError at collection, whole module deselected** once the name leaves `CALL_SIGS` (probe C executed; the `_homes` docstring `:810-813` predicts exactly this); ledger `:49`, `:78-86` ("sampled at one named member of the legacy half").
- `Regime` `primitives_block.py:98-141`: `LEGACY` docstring "the hand-authored `PRIMITIVE_CALL_FUNCS` namespace, shared corpus-wide"; `call_namespace(LEGACY) = CALL_FUNCS` — after, a no-block game can call NO Primitive (all refused by the declared-only arm), so the legacy namespace admits-then-refuses. Consumers of the regime: `resolve.py:5134`, `:7906`; `typecheck.py:1096-1105` (`native_call_sigs`: LEGACY → `CALL_SIGS` whole); `evaluate.py:41-49`; `state.py:377-383`; `driver.py:100-103`; `test_primitives_block.py:635-640` (`call_namespace == CALL_FUNCS`); `test_typecheck_corpus.py:155-160`; `test_phase_scoped_reads.py:198,1864`.
- Reconcile carve-out `test_primitives_block.py:2408-2720`: `_reconcile` `:2478-2560`; after coup, every remaining row is walled (rows executed: `bigtwo/big-two {opened}`, `president ∅`, `tichu ∅`, `primitives.py × {bridge, pinochle, french-tarot}`), so claim (3)'s non-exempt set is empty by construction on the corpus; the plants `:2630-2718` are what keep it non-vacuous; `:2613-2627` needs both halves non-empty (still true). `test_engine_core_game_knowledge_is_named` `test_primitive_narrowing.py:1590-1620` compares primitives.py's rows to games naming an auction outcome — unaffected (green in control).
- `MIGRATED` `test_primitive_narrowing.py:452-502` (holds the name → `:520-525 MIGRATED <= known` **RED**); `NARROWED` `:386-449` (`coup.py::ROW`, `coup.py::coup_game_summary` → `NARROWED <= sites` **RED**); `_GAME_IMPLS` 63 → 61, `_SITES` 59 → 57 (coup contributes `Impl(ROW)` + `Impl(coup_game_summary)`), floor `> 50` `:368-375` holds; `_FACT_CONSUMERS["seating"]` `:800-807` keeps readers (`cribbage.py:193`, `holdem.py:62`, `holdem_heads_up.py:54`, `stud.py:70,80,109`) — not red.
- **`CALL_SIGS` consumers by half** (grep-derived; the 3b closing step moves the Primitive half behind `implementation_sig` `primitives_block.py:686-701`):
  - Builtin half only: `resolve.py:241` (`_FRAME_CALL_FUNCS`), `evaluate.py:52` (declared branch's non-entry names), `typecheck.py:1105`, `:2380`, `:2457`, `tests/test_movement_verbs.py:494-503`, `test_trick_order.py:1209,1256,1271`, `test_trump_slot_class.py:12,24,832`, `test_card_points.py:197-211`, `test_signatures.py:243-248`, `test_native_call_boundary.py:80` (deliberately, the Primitive half via `implementation_sig` `:83`).
  - Primitive half: `primitives_block.py:701`, `test_primitives_block.py:771-773` (`_entry_and_body` over `DECLARED_ONLY`), `:2284-2316` (freeze plant keyed to `CALL_SIGS["pinochle_meld_value"]`, red-under "point `native_call`'s declared branch at `CALL_SIGS.get(name)`" — meaningless once the half is gone), `:2953`, `:2993`, `test_signatures.py:306` (`_declared_facts`), `test_primitive_narrowing.py:1448` (`CALL_SIGS["canasta_stage_ok"]`).
  - Both halves / whole-table: `evaluate.py:44` (legacy branch; after eviction only Builtins can reach it), `typecheck.py:577` (`TypeEnv.call_sigs` default), `:701` comment, `:1104`, `test_signatures.py:80,464,467-521`, `test_permissive_top.py:232`, `test_trace_emitter_eviction.py:123`, `test_primitives_block.py:2798` (census grep pattern), `test_primitive_narrowing.py:1442`.
  - `implementation_sig` consumers: `typecheck.py:1054` (shape check), `test_native_call_boundary.py:83`, `test_primitive_narrowing.py:1422`, `test_primitives_block.py` element allow-list pin (`:2987`, per `primitives_block.py:298-300`).

## 4. The reads registry after the last call row

- Remaining rows (executed above): three climb rows + three auction rows; zero call-namespace rows; zero rows carrying `zone_families`/`single_zones`/`arrival_zones`. `reads.py:249-296`; the `_BY_KEY` assert `:301-304` (in the guard-witness band, `test_registry_guard_witnesses.py:698`) unchanged.
- `reads.py` docstring `:3-28` claims that go false: `:9-10` names `coup.py` as the example; `:14-16` "`PRIMITIVE_READS` is the single registry of every zone/state name each primitive module reads"; `:24-28` "at which point this table derives from the game files instead of being authored here" (after: the table stays authored, for walled namespaces only). Contract `:30-53`; `game_reads` `:579-582` "The legacy binders pass none" (after: only the climb binder — `mechanics` via `primitives.climb_row` — and no `call` binder).
- `narrowing.py:37-39` `assumes … the primitive's module has a PRIMITIVE_READS row` (#535) — false for every call-position Primitive after; Scope `:26-35` ("per-MODULE for a game that declares none, where `PRIMITIVE_READS` is the declaration") describes a regime with no member.
- `tests/test_primitive_reads.py`: `:433-434` "a module with no registry rows must make no accessor reads at all" (#535); **`:550 _COUP_ROW = reads.row("cardlang/runtime/coup.py", "coup.cardlang")` at module import → `PrimitiveReadError` → the whole module fails to collect** (`:571-624` accessor matrix, `:635-655`, `:711-720` probes all keyed to coup's row / `coup.cardlang` / `coup.py`); `_row_problems` zone arms `:150-153` run over no authored instance after; module-source scan `:429-464` over the runtime glob `:104` (coup.py's deletion shrinks the axis); ledger `:46-52` names `stdlib.py` (already stale).
- `tests/metamorphic/rename.py:137-163 _coupled_names`: coup's six names leave the exclusion set. **Probe E** (row removed, let-less coup, seeds `[0,1,2]` × both policies): `excluded_coupled = []`, renamed set 9 → 15, pairing witnesses **none**. The T2 domain widens by six names; `tests/metamorphic/test_rename.py:27-49` residual (3) prose.
- `docs/library.md:820-834` ("A game that writes no block is coupled to the `PRIMITIVE_READS` registry") — true only for walled rows after.

## 5. Goldens and proofs

- `tests/golden/coup_scores.json`: 40 seeds × `{reveals (obs stream), coins (coup_game trace), alive (coup_game trace), winner (GameResult)}`. Source: `test_migration_characterization.py:1129-1157 _COUP_CAPTURE` reads `coup_game`; prose `:1117-1128`. **Probe D**: rebuilt on the let-less source from rs-capture (`coins`) + `GameResult.scores` (`alive`) at the golden's full width → `mismatching seeds: []`, `json.dumps` byte-identical. `CAPTURE_GOLDENS` `:250`; the dial (10) vs width (40) → `CARDLANG_GOLDEN_SEEDS=full` applies (`coup.cardlang` changes). `_HASHSEED_CAPTURE` `:469-499` records every tracer event (one fewer after) — an in-run comparison, no stored golden; docstring `:456-460` names the three channels.
- IR: no `coup.ir.json` (`tests/golden/` listing); the `let` node's removal changes coup's IR unpinned; `ir.py:82-89` emits `primitives` only for a declared game.
- `tests/openspiel_ready/test_coup.py`: reads `obs_logs`, `rs`, `information_state` only; no tracer reaches the adapter (§1) — unaffected.
- `tests/test_playout_coup.py:22-41`: `total_coins`/`total_cards` from `coup_game`; after, `total_cards` from `game_end["total"]` or rs-capture, `total_coins` from rs-capture only (probe A).
- `tests/test_trace_emitter_eviction.py`: ledger residual `:47-55` names the emitter; `EVICTED` `:97-100` — adding coup makes `:135-137 test_implementing_symbol_gone` import `cardlang.runtime.coup` → **ModuleNotFoundError if coup.py is deleted** (harness crash); `:186-193 test_shadow_wall_still_guards_registered_names` uses `coup_game_summary` as the CONTROL row → must move to a still-registered name; `:148-152 test_prose_has_no_reference` sweeps `docs/games/*.md` + `docs/library.md` → `library.md:1008` reddens until edited; `:126-132`, `:140-145`.
- `tests/test_procedures.py:73-77` ("Coup's trace golden … coins, alive vector") — the "trace" attribution goes false.

## 6. The corpus

- `docs/games/coup.cardlang:88 let summary = coup_game_summary()` — bare, no comment; header `:9-10` "runs fully on the kernel". No other `.cardlang`/fixture/experiment calls it (repo grep: only `coup.cardlang`; `experiments/green-lane/variants/*` do not; `tests/rejections/call_evicted_trace_emitter_coup.cardlang` calls `coup_note_reveal`).
- `coup.md`: no summary/trace prose (grep none); in `PROSE_ONLY_TWINS` (`test_typecheck_corpus.py:47-60`).
- No unused-`let` guard in resolve (grep `unused|never read` → none). **Probe B**: `check_dsl` of the let-less source OK, `primitives` stays `None` (coup stays a LEGACY-regime game with zero Primitive calls, like hearts); over 40 seeds the observation stream hash, the trace stream minus `coup_game`, `GameResult`, and `decisions_made` are identical; trace count differs by exactly 1.

## 7. Prose asserting the emitter / contract / seam

- `cardlang/runtime/coup.py:1-14` (whole docstring); `primitives.py:6-12` ("The arms below are the LEGACY dispatch seam … the metric is the REGISTRY … never the count of arms"), `:28-30` ("two arm counts independently readable"), `:44-46`, `:52-64`, `:126-139`; `builtins.py:19-30`; `evaluate.py:23-40`; `narrowing.py:26-35, 37-39, 58-69`; `reads.py:3-28, 30-53, 579-582`; `state.py:377-383` ("puts it on the legacy dispatch"); `driver.py:100-103`; `holdem_heads_up.py:18-19` ("as a legacy game's plain call does"); `primitives_block.py:1-10, 105-107, 147-171, 238-243, 686-701` ("`CALL_SIGS` is that statement today … when 3b deletes the Primitive half"); `functions.py:188-190, 204, 241-254, 443`; `signatures.py:112`; `typecheck.py:1096-1105`; `resolve.py:88-96, 5292-5299, 7913-7920`.
- Glossary: `docs/glossary/primitive.md` ("`runtime/primitives.py` holds one hand-written arm per name; **that arm count is the elimination metric**" — already contradicts `primitives.py:10-12` and `builtins.py:26-30`; home `runtime/primitives.py`); `trace-event.md`; `primitive-bundle.md` ("per-module for one without"); `primitives-block.md` ("without one it keeps the hand-authored `PRIMITIVE_CALL_FUNCS` registry"); `native-code.md` quotes a `primitives.py` message that no longer exists ("unknown native function — neither a Builtin nor a Primitive"; the live text is `:133`); index `docs/glossary.md:102,103,113,136`. `tests/test_glossary.py` checks links resolve (`:347-368`), not that a `home:` file still carries the term.
- `docs/design-notes/primitive-sidecars.md:46-53` (§1 item 3), `:155-170`, `:211-220`, `:252-258`, `:309-327` (3b status; the "which games have migrated is a query" paragraph `:319-327`); stage 5 `:353-368` ("third dispatch route" becomes the only route). `docs/kernel-migration.md:35-36` ("Coup's in-game scans and trace emitters" — "in-game scans" already retired, `coup.py:9-11`); `:495-499` stays true. `docs/library.md:1003-1011` (the entry), `:820-834`. `docs/design-notes/primitive-inventory.md:30-31` ("the honest (f) residue is `coup_game_summary` and the codecs"), `:50` (coup.py row, "83" lines), `:368`. `docs/design-notes/kernel-extensibility.md:382` (`"coup_reveal"`, dated analysis).
- Tracker: issue #142 body, third box (open; body still cites `runtime/sidecar.py`/`runtime/stdlib.py`, both retired — the 2026-08-05 comment notes the latter); #535 (rider for `narrowing.py:38-39` + `test_primitive_reads.py:434`). Plans (dated, not owed): `docs/plans/2026-08-29-primitives-block-stage3b.md:66-69, 223-231` (closing steps: "coup (the eviction)"; "the legacy-table deletion … the box is the operator's tick, on full elimination"); `docs/plans/2026-09-04-cribbage-nested-phases.md:113-116, 343-349, 654-658, 709-712, 728-733, 773-778`.
- Test ledgers/prose: `test_trace_emitter_eviction.py:47-55`; `test_primitive_narrowing.py:35,119,414-415,477,513-517`; `test_primitives_block.py:49,78-86,652-671,794-802,829-836,2173-2177`; `test_signatures.py:269,359-361,504-515`; `test_native_call_boundary.py:75-77`; `test_primitive_reads.py:406,433-434`; `test_migration_characterization.py:1117-1128`; `test_procedures.py:73`; `tests/metamorphic/rename.py:148`, `test_rename.py:27-49`; `test_registry_guard_witnesses.py:684-695`; `test_phase_scoped_reads.py:198,1864`; `test_typecheck_corpus.py:155-160`.

## 8. The info-set axis

Nothing moves, executed: probe B (§6) — per-player observation streams byte-identical over 40 seeds with the call removed; the adapter installs no tracer (`replay.py:259-265`); `information_state` renders public state from `rs`, not from traces; `test_trick_order_migration.py:47-50` already rules the trace channel harness-only. `coins`/`treasury`/`alive` are public state variables (`coup.cardlang:52-56`), so a formal observer could carry the totals — but no stream does, and the proof modules never read them from one.

## 9. Unsure

- Whether `coup.py` is deleted (→ `test_trace_emitter_eviction.py:135-137` shape, `_GAME_MODULES`/glob axes shrink, `test_primitive_reads.py:550` import) or kept empty.
- Whether `primitives.call()` is deleted or kept as an armless `case _` (→ `test_native_dispatch_split.py:93-103,219-240`, `test_signatures.py:318-326`, `test_assert_triage.py:218-227` floor for `primitives.py` still met by the other `raise AssertionError` sites; `test_call_funcs_are_dispatchable`'s swallow at `:221-222`).
- Whether `Regime.LEGACY` survives as a regime whose call namespace admits-then-refuses every Primitive, or `call_namespace(LEGACY)` becomes the Builtins and the declared-only arm retires — this changes the diagnostic a designer meets copying a Primitive call into a blockless game (R2), and `test_primitives_block.py:635-640`.
- Whether `DECLARED_ONLY_CALL_FUNCS` is retired now that it equals `PRIMITIVE_CALL_FUNCS` (consumers §3), or kept until the CALL_SIGS column lands.
- Whether the `CALL_SIGS` Primitive-half → `implementation_sig` column move rides this change or the operator's tick; either way the Primitive-half consumers in §3 (`test_primitives_block.py:771-773, 2284-2316, 2953`, `test_signatures.py:306`, `test_primitive_narrowing.py:1448`, the `set(CALL_SIGS)==set(CALL_FUNCS)` pins at `test_signatures.py:80`, `test_permissive_top.py:232`) are the domain.
- Whether `EMITS_TRACE`/`TraceEvent`/`_emit`/`_DispatchFact.traced` retire wholesale (zero producers) — `narrowing.py:59-69` then describes a class with no member.
- The harness derivation's channel: rs-capture at `game_end` (executed 40/40, matches the `cli.py`/canasta convention) versus an observation-stream derivation of coins (not executed; a rules mirror). `playout_trace.py:1-17` currently claims its facts derive from observation events only.
- `test_primitive_reads.py`'s accessor matrix and misuse probes need a new exemplar row (the synthetic-row route `test_primitive_narrowing.py` ledger `:38-45` took) — or the zone-kind arms of `_row_problems` go instance-less on the corpus.
- `test_every_invocation_contract_has_a_member` vs `test_the_declarable_contracts_are_a_proper_subset`: jointly unsatisfiable at zero members; which survives is a decision, not a cell.
- Issue #143's ordering text was not read; `#142`'s body still names `cardlang/runtime/sidecar.py` and `cardlang/runtime/stdlib.py`.

## Gate-4 addendum (2026-09-04, recorded at implementation — the derived domain against the plan's statement)

The plan's ruling (a) and the counsel's precedent P1 name
`tests/test_cli_surface.py::test_play_reaches_a_terminal_position` as the
Owner of the reader's emit-before-pop premise. It is not: that cell asserts
`returns`, `decisions` and `seed` in the `play` summary line, all printed by
`cli._summary` wherever the trace fires, so moving the emit past the pop
leaves it green. The pin that reddens under that mutation is
`tests/test_cli_surface.py::test_info_state_carries_the_state_variables`,
whose own docstring states the fact: "This is the pin on the one thing the
snapshot site depends on beyond the trace event existing: WHERE it fires."
`TerminalState` cites that cell as its Owner. Recorded rather than rewritten
above: the ruling's substance — read the terminal world at the existing
moment, cite the pin that holds the ordering — is unchanged.

Three further facts the derived domain adds to the red set the plan measured,
each answered in the change rather than marked:

- `tests/test_primitives_block.py::test_a_declared_game_cannot_reach_another_
  games_primitive` was written at the legacy-half name for a counterfactual
  the eviction removes ("this same call in a game with no block RESOLVES").
  It derives its representative and states what it now proves.
- `tests/test_signatures.py`'s `_facts_in` handled a STARRED argument for the
  one arm that wrote `*_bind(ctx, ROW)`. With that arm gone no producer
  remains, and treating a star as one skipped position would line every later
  argument up against the wrong declared type, so the shape is refused rather
  than left as dead code.
- `_HASHSEED_CAPTURE`'s comment claimed its record sits at or below the grain
  of every golden in its domain. Coup's coins now ride no channel it records;
  the comment says which divergence is the golden's to catch instead.

## Gate-4 addendum (2026-09-05, recorded at the closing change — the derived consumer set against the counsel's statement)

The counsel's (c) lists the `CALL_SIGS` consumers to re-point and the
framing check's section 3 splits the table by half. Two derived facts the
lists do not carry, each answered in the change rather than marked:

- **The dispatchability pin's channel.** `test_call_funcs_are_dispatchable`
  swallowed any non-`AssertionError` to mean "reached real code past the
  match" (`tests/test_signatures.py`, the framing check's silent-pass
  hazard). Re-channelling `native_call`'s refusal to `ShadowGuardError`
  makes that swallow accept the refusal itself, so the cell would have gone
  green while proving nothing. It asserts the refusal's own channel AND its
  message text, and carries `expects_shadow_guard` — the house's mark for a
  Shadow Guard exercised on purpose. The ledger says what the green proves:
  the refusal discriminates a Primitive from a Builtin, never that a
  designer reaches it.
- **What replaces `set(CALL_FUNCS) == set(CALL_SIGS)`.** That one line
  pinned "every call name has a signature". At the end state the fact has
  two carriers, and the ledger sentence names both: the index's import-time
  `frozenset(PRIMITIVE_IMPLEMENTATIONS) == PRIMITIVE_CALL_FUNCS` for
  existence, and `sig` being a required field of `Implementation` for
  shape — rung 1, since an implementation with no signature does not
  construct. Naming only the first would over-credit it: it says nothing
  about shape.

And one measured fact the counsel's (c) relies on without stating: the two
halves of the call registry are disjoint (`BUILTIN_CALL_FUNCS &
PRIMITIVE_CALL_FUNCS` is empty), which is what makes `set(CALL_SIGS) ==
BUILTIN_CALL_FUNCS` a statement that no Primitive is keyed there rather than
one an overlapping name could satisfy while remaining in both tables.

The transcription of the 44 signatures was crossed against `CALL_SIGS` row by
row while both statements stood, under an assert that shipped in the commit
adding the column and left with the table half it crossed: `mypy --strict`
catches a missing signature, and nothing but that assert could catch a wrong
one.
