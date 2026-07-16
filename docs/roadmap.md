# Roadmap

What's explicitly deferred, and the suggested order of next steps.

## Explicitly deferred

Things we have noted but consciously not designed yet:

- **Named procedures — deferred cells.** Every one is a loud wall today, never a
  silent acceptance; the ledger is `tests/test_procedures.py`. (a) **`Zone`
  parameters.** The design note expected the corpus to need them; it does not — a
  `Player` parameter already carries its zone (`influence[victim]`), so the domain
  is `Player` / `Rank` / `Rank?` and every other spelling is rejected. `Rank?`
  rather than `Rank` is the form the corpus forces: there is no flow narrowing, so
  a bare `Rank` parameter would reject `block_claim` at the very sites that must
  pass it. (b) **A `round` in a procedure body.** It binds its own, round-local
  `outcome`, and the body's pronoun wall cannot yet tell that from the caller's
  call-site `outcome`; rather than accept a `round` you may run but whose winner
  you may not route, the form is rejected whole. This is what Tichu's and Skat's
  round shapes would need before they could adopt procedures. (c) **A `produces:`
  over a PHASE OUTCOME in a body** — its consumer must be an earlier-executed sibling
  of the producing phase, and must be the only one; both are facts about *where the
  statement sits*, and a splice moves it. (A `produces:` over a `define` is fine: a
  define is invoked fresh at each site, with no ordering or uniqueness rule.)
  (d) **A procedure running another procedure** — expansion is a single splice, not a
  call graph.
  (e) **Non-local control flow in a body** (`produce`, `continue to`, `skip to
  next hand`): inline text targets exactly one enclosing construct, and a body may
  be spliced into two different ones.

  These are one class, not five accidents: a procedure body may not hold a statement
  whose VALIDITY depends on where it sits, because the checker sees the body once, at
  its declaration, and the spliced copies are never re-checked (expansion runs after
  typecheck, which is what makes the parameter types enforceable). The class is closed
  by enumerating the position-dependent CHECKS — `_check_outcome_scope`,
  `_check_single_outcome_consumer`, `_check_misplaced_produce`, and outcome binding —
  rather than by intuition. The two other position-sensitive passes, deck-capacity and
  the OpenSpiel action space, both run after expansion and see the real tree.

  Note what is NOT on this list: argument capture, actor capture, and a body
  binding leaking into the caller. Those were walled in the first implementation
  and are now impossible by construction — arguments are evaluated once, by value,
  in the caller's context, and the body runs in a block (decisions.md "Named
  procedures").

- **The deck-capacity gate does not see move-driven draws.** Its domain is the
  scripted deals in phase bodies (`cardlang/deckcheck.py`, module docstring):
  a draw inside a MOVE effect — reached through `offer` or a `round` — is not
  counted, because a move can fire arbitrarily many times per hand, which is
  the same not-statically-boundable currency as a deal inside `repeat until`.
  The gate stays sound for its contract (it never rejects a valid game); the
  limit matters only for a future draw-heavy game (Rummy-style stock draws),
  where the honest options are a declared per-hand draw bound on the move
  type or a runtime refusal with a designer-facing message rather than an
  exhausted-deck crash. Revisit when such a game enters the corpus.

- **Which round FRAME a `state.` read sees.** The *name* axis is closed — a round
  publishes a declared, typed set of fields and the checker rejects everything
  else, so a form's private working memory is not reachable from the DSL
  (`cardlang/stdlib/round_state.py`, ledger `tests/test_round_state_registry.py`).
  The *frame* axis is not: a reference is not statically attached to a form —
  `MustFollowSuit` lives once in `stdlib/rules.cardlang` and games activate it in
  context — so the checker validates against the UNION of the forms' published
  sets and cannot prove that the round actually running publishes the field read.
  `state.shed_first` (a climb field) inside a trick phase type-checks. The runtime
  wall is that a read with no live or just-completed frame now fails loudly rather
  than returning a stale one from a different form. The design seam is
  [open-questions/round-state-in-information-states.md](open-questions/round-state-in-information-states.md).

- **Packaging the corpus for distribution.** The whole project runs from a
  checkout: every `.cardlang` is loaded from `docs/games/` by repo-relative path
  (tests, CLI, and the OpenSpiel adapter's `hearts_game()` loader), and the
  corpus *is* the living spec (`docs/games/` per CLAUDE.md). A wheel install
  ships only `cardlang*` + the grammar, so `docs/games/*.cardlang` would be
  absent and any runtime that parses a corpus file would fail. This only matters
  once the project is distributed as a wheel (not a current goal); the fix is a
  project-level decision — ship the corpus as package data and load it via
  `importlib.resources` — not an adapter-local patch (patching only the adapter
  while the rest stays checkout-relative would be inconsistent). Flagged by
  Codex on the OpenSpiel-adapter PR.

- **CCG-style card effects** (Magic, Yu-Gi-Oh!). Out of initial scope. The
  Forge text-DSL pattern (one mini-language per card) is the reference if/when
  we tackle this.

- **Detailed melding logic.** Pinochle's meld phase is a flat Counter-based
  tally (`pinochle_meld_value`, a game-local stdlib primitive — the DSL body
  itself is fully migrated). Real melding as a reusable combination model
  (shared conflict resolution across arbitrary meld categories, not just the
  one hand-picked trump-run-subsumes-marriage overlap) is its own design
  exercise.

- **Grammar surface deferred by the checker.** Grammatically valid forms are
  statically rejected until a game needs them (decisions.md "Surface
  totality": rejected loudly rather than silently ignored). Movements: the
  `in <zone>` form (the verb implying its destination — `muck one cards in
  discard`), the per-movement `visibility =` override (visibility derives from
  the declared zone types; the override's semantics is
  [open-questions/move-level-visibility.md](open-questions/move-level-visibility.md)),
  and resource movements (`move 2 chips …` — the corpus keeps chips/coins as
  Integer state; moving resources through zones is undesigned). Elsewhere:
  `override` rule deltas in `active_rules:`, `before_each`/`after_each` on a
  phase with no iteration, transition events other than `play_to_trick`, a
  trick round naming a move type its form cannot run, duplicate
  `state { }` blocks, and named call arguments (`f(x = 1)` — rejected until
  a game needs the surface; positional arguments are the implemented form).
  Counting is the card-query form (`number of cards in … [where <pred>]`);
  the retired `count over` comprehension (whose body was silently
  discarded) does not parse.
  Rule-template parameters (`rule X(suit: Suit)`) support the Suit domain
  only, and one instantiation per rule name per game — both rejected loudly,
  lifted when a game needs more. Quantifier / `for each` roles are the closed
  set player/team/suit/rank; `each … simultaneously` is player-only.
  Value-domain-indexed state (`state { seen[rank] : Integer = 0 }` as a
  per-rank tally) is rejected: a zone or state index must be a
  `zone_key_of` domain (player/team — `cardlang/domains.py`), because the
  runtime keys those stores by an observer-anchored member set. A per-value
  tally is expressible today as per-player state plus a query; lift the wall
  when a game genuinely wants the store (the runtime's key-set plumbing
  already reads the domain table, so the extension is a table row plus an
  observation-encoding decision, not a rewrite). Rules that the runtime cannot yet enforce at all are a
  named open question, not a rejection —
  [open-questions/rule-scope-beyond-trick-play.md](open-questions/rule-scope-beyond-trick-play.md).

- **`active_rules:` remove-reachability is cluster-precise, not fully
  runtime-precise.** `-X` is walled (`_check_remove_reachability`,
  cardlang/resolve.py) to require `X` added by a `plain`/`add` reference in
  the same runtime-consulted scope: a phase's own `active_rules:`, or that
  list unioned with one direct rule-delta sub-phase's own list —
  `runtime/phases.py`'s `compute_active_rules` shape. Two narrower gaps are
  accepted, both unexercised by the corpus (no game uses `-X` at all): the
  check does not model order WITHIN one list (an add-then-remove of the same
  name earlier in a parent's own list still counts as "added" for a later
  delta-child cluster check, even though the runtime would have already
  removed it before any delta child runs), and it does not distinguish two
  SIBLING rule-delta sub-phases (a remove in one referencing a name added
  only by the other passes this check, even though only one of a
  "before"/"after" pair is ever active at a time, so the reference is a
  runtime no-op regardless of what this check says). Tighten if a game ever
  needs the precision.

- **`ranking:` coverage is unchecked.** Wall: `_resolve_ranking`
  (cardlang/resolve.py) rejects a `ranking:` entry that names no rank of the
  declared deck, and a repeated entry, but does not require every deck rank
  to be present — a game's `ranking:` may legitimately be a PARTIAL
  permutation, pinned as a deliberate feature by
  `tests/test_action_space_multiparam.py::test_rank_domain_sourced_from_game_ranking_not_deck`,
  which narrows the `Rank` move-parameter domain this way on purpose.
  A card whose rank falls outside a partial `ranking:` still crashes
  `rank_value`'s `ctx.rs.rank_index[...]` lookup at runtime
  (`cardlang/runtime/stdlib.py`) instead of erroring at resolve time — this
  residual half has no pinning test (no corpus game exercises it: every
  `docs/games/*.cardlang` ranking today happens to be a full permutation of
  its deck).

- **Solitaire and positional zones.** CardStock excludes spatially-dependent
  layouts. We don't, but we haven't implemented one yet. Klondike or FreeCell
  will be the test case.

- **OpenSpiel compilation (general pass).** A per-game *runtime adapter* now
  validates the target: Hearts is a registered `pyspiel.Game` passing OpenSpiel's
  consistency tester (see decisions.md "OpenSpiel compilation"). What remains is
  the general, all-corpus path: a game-agnostic action/information-state encoder
  (the Hearts adapter's encoder is hand-written), explicit per-deal chance nodes
  (the adapter fixes a deal from a finite seed set), performance (the adapter
  re-simulates per query — O(n²); a real pass or a snapshot/restore path removes
  it). Every corpus game is registered — no concrete mechanics remain.

- **Auto-derivation of `information_state_tensor`.** This is the prize for
  OpenSpiel integration but depends on zone visibility being airtight. The Hearts
  adapter provides information-state *strings* only; tensors are deferred.

- **Grow the interactive-decision kernel and migrate the corpus to it.** `offer`
  and the `round` construct are built, and every trick game (Hearts, Spades,
  Getaway, Bridge, Oh Hell) now plays on the kernel `round` — the built-in `Trick`
  mechanic is retired, with `round` carrying rule-delta transitions (Hearts/Spades)
  and early-termination (Getaway). The rest of the decision sublanguage
  (decisions.md "Interactive decisions: a kernel and an in-DSL standard library")
  is the major in-flight work: the remaining `round` axes (accumulator, order,
  move vocabulary); typed outcomes and definition-composition; and promoting
  shared `auction` / `betting` / `challenge` / `block` definitions to the
  standard library at their third instances. The corpus migration itself is
  COMPLETE: every game runs on the kernel, no per-game runtime mechanic
  remains, and the `instantiate` construct is deleted. Coup runs at real
  interactive scope (challenges, blocks, claimed characters, and targets
  are announced player decisions; a proven challenge's card is publicly
  revealed). The remaining scope of work is Tichu's call windows and
  Dragon routing — a behaviour change with its own sign-off, in
  [kernel-migration.md](kernel-migration.md), Workstream 5.

- **Typed outcomes: Stages 1–3 built; remaining corpus migrations + checker coverage.**
  Stage 1 is built: `cardlang/typecheck.py` is a real type checker (a `Type`
  model, expression inference, and checks for assignment compatibility, stdlib
  argument types, subscript legality, and Boolean conditions — the
  `decisions.md` "Typed object model" subset, with the corpus as its test net).
  **Stage 2 is built:** user-defined `type` structs (`TStruct`: declared fields,
  `derived` fields, field-access typing, construction via `Name { … }`, and
  runtime struct values) and param-light `define` variant outcomes (`TVariant`:
  `produce` / `produces:` with exhaustiveness, payload typing, and scoped
  payload-binder typing), running end to end through the tree-walking runtime.
  **Stage 3 is built:** phase `→ outcome { … }` + `produces:` on phases (an
  auction round raises the same `_ProduceSignal`, adopted
  by its enclosing outcome-declaring phase), the imperative arm vocabulary
  `continue to <phase>` / `skip to next hand`, and nullable variant payload types
  (`Suit?`) — reusing the Stage-2 `produces:` consumer and `TVariant`
  (`decisions.md` "Typed phase outcomes"). **Bridge** (auction:
  `contract_finalized | all_pass`) and **Schnapsen** (settlement: `claimed |
  talon_closed | open_play`) are migrated off their Boolean gates onto it.

  The remaining typed-outcome migrations stay deferred because their decision is
  not at a clean DSL/mechanic boundary (Pinochle's own `declare_trump` decision
  cleared this bar — it is now a
  plain one-draw DSL round, no typed outcome needed: `bid_abandoned` is an
  ordinary Boolean state var, like the games above it; **French Tarot**'s
  whole hand, not just its auction, cleared it too — the chien discard, the
  eighteen tricks, and the scoring are all plain DSL now, no typed outcome
  beyond the auction's own `taken | thrown_in`; **Skat** cleared it the same
  way — the Reizen threads `working_bid`/`passer` phase state and the scoring
  writes `score` directly, no typed outcome anywhere): **Getaway**'s two-way
  resolution now lives in its `round` body (`if state.trick_terminated_early`), so
  a typed outcome there would mean the `round` itself producing a tagged
  pickup-vs-discard result rather than the body branching on round state.

  Deferred from Stage 2: union-typed and refinement-typed struct fields
  (`suit : Suit | NT`, `Integer in 1..7`); param-full `define` (parameters +
  invocation-as-expression) until the challenge/block/auction stdlib reaches
  three corpus instances; forward references between struct types resolve to
  `TAny` (structs are built in source order). Struct literals are validated in
  statement position only — state-decl defaults are *not* expression-checked, so
  `deal : Contract = Contract { level: 1 }` (omitting a field) is accepted by the
  checker and fails only at runtime on field access.

  Deferred checker coverage: movement `amount`, when an expression rather than
  `all`/`one`, is walled structurally (call arity, subscript legality, every
  BinOp/aggregation/IsCheck operand wall recurses into it) but nothing pins
  its own type to Integer. Rule `applies_when` predicates are walled the same
  structural way but not top-level Boolean-asserted (a whole predicate that
  is itself non-Boolean, e.g. a bare Integer, would pass); rule `demands` is
  a card-*set* expression (`cards in hand where …`), not a Boolean predicate,
  so a Boolean wall does not apply to it at all — a category, not a gap.
  Constraining `loser.selection` to `Player` is unwalled. Every binder — `for
  each`/quantifier/player-query/card-query/comprehension roles, and the
  Movement/EpistemicOp `where`-filter's implicit `card` — is typed by role or
  source (`_role_type`, the aggregation source's element type,
  `_check_stmt_exprs`'s `card: Card` binding), and the operator/predicate-
  context walls over those typed positions (`OP_CLASSES`'s `_check_binop`
  dispatcher, `_check_bool` on every predicate/filter/body position,
  `_check_card_source`) are in `tests/test_operator_walls.py`,
  `tests/test_aggregation_walls.py`, and `tests/test_context_walls.py`.

  **Action-field typing beyond the universal card/actor pair.** Wall:
  `ACTION_FIELDS` (cardlang/typecheck.py) types `action.card` (Card) and
  `action.actor` (Player) — the two fields the runtime `Move` payload
  (cardlang/runtime/state.py) carries for every move type — and nothing
  else; it is a closed registry by design, not an oversight. Move-type-
  specific params reachable only as `action.<param name>` (`action.amount`,
  `action.card_count` — named in the grammar comment at
  cardlang/grammar/cardlang.lark:320) stay `TAny`, pinned by
  `tests/test_zone_family_typing.py::test_unknown_action_field_stays_permissive`
  and `tests/test_operator_walls.py::test_ordering_accepts_gradual_any`
  (the statement shape itself is exercised more broadly in
  tests/test_construct_combination_validity.py). Full move-type-aware
  typing of `action` (a per-move-type field registry, keyed off the move's
  declared params) is its own design exercise, deferred until a `demands:
  actions where` clause with a non-card field actually gates a move at
  runtime — today `runtime/rules.py` skips move-shape demands entirely
  (`if rule.demands is None or rule.demands.kind != "cards"`), so the
  surface typechecks but nothing yet consumes it.

  **Zone-family index strictness (deferred re-audit).** Wall (leaky by
  design): a zone-family subscript's index (`hand[p]`, `captured[t]`) is
  checked with `types.assignable` against the zone's declared role
  (Player/Team), which — by the same pre-existing rule that lets
  `dealer : Player = 0` default a state var — accepts a literal Integer
  standing for the identity. This means `hand[0]` typechecks, pinned by
  `tests/test_zone_family_typing.py::test_accepts_an_integer_literal_zone_family_index`.
  gops.md's asymmetric two-hand setup
  (`move ... to hand[0]` / `hand[1]`, `reveal one card from bid[0]` /
  `bid[1]`, `captured[0]` / `captured[1]` routing) is the corpus's one user
  of this shape and has no symbolic alternative in a setup phase (no `for
  each` binder to name "the clubs player" by role). A stricter rule —
  zone-family indices must be exactly Player/Team-typed, never a bare
  Integer — was considered and rejected for this pass because it would make
  gops.md inexpressible without a rewrite; revisit if a future game's needs
  (or a deliberate decision to rewrite gops.md's setup) make the stricter
  rule worth its corpus cost.

- **`scoring_component` / triggered components (runtime).** The design is settled
  (decisions.md "Scoring composition" and "Triggered scoring components"), but the
  corpus scores through inline statements plus game-local stdlib primitives, and
  the runtime has not built the
  component subsystem. Build it when a game needs cross-hand triggered scoring
  that inline computation can't express.

- **Representative playouts.** The runtime's random chooser exercises invariants
  but never reaches skill-gated branches (Spades' +500 win and bridge slams
  are implemented but unexercised). A light "rational-ish"
  policy plugged into the `chooser` seam would make playouts representative and
  surface bugs the conservation invariants structurally cannot.

- **`RuntimeState` config-into-constructor.** The driver sets ~ten config fields
  on the instance *after* construction, so an under-initialized state fails deep
  in evaluation rather than at construction. Deferred until a *second*
  construction site that doesn't go through `play_game` exists to design the shape
  against (required constructor kwargs vs a frozen `GameConfig`).

- **Test-depth regression nets.** Conservation invariants catch *leaks* but not
  *mis-allocation or wrong amounts*. Add independent-recompute checks when those
  games are next touched: Schnapsen's six-way settlement amount (1/2/3 game
  points — its kernel migration pinned the per-hand `game_score` vector golden, a
  characterization that localizes a divergence but does not independently
  recompute the tiers), Spades' nil and bag-overflow score branches, and Coup's
  challenge resolving to the correct loser. (The Bridge analogue — a full scoring
  recompute — is done.)

- **Determinization as a compiler pass.** For IS-MCTS support. Deferred.

- **Bidding sub-language.** Bridge bidding systems are a domain unto
  themselves. The current `submit_bid` move type is enough for Spades/Oh
  Hell/Pinochle-style bidding; Bridge will need more.

- **First-player / opening-seat syntax.** Coup is the first game whose
  opener is neither dealer-derived nor rule-derived — it's an arbitrary
  runtime seed. A dedicated way to specify the starting player
  (including programmatic randomization) is deferred until more such
  games arrive to show the shape. The turn-order start is
  runtime-supplied in the meantime (see library.md "Stdlib state").

- **The meta-DSL for "X is Y but with deltas".** We discussed this as the
  natural way the literature describes variants. The current design supports
  it implicitly (a variant adds/removes rules and phases from a base game)
  but doesn't have explicit syntax for it. Worth revisiting after Pinochle.

- **Quantifier productions are not registry-derived.** The quantifiable-domain
  registry (`cardlang/domains.py`) is the one table behind binder typing,
  iteration, actorhood, member enumeration, and the move-parameter/action-space
  domains: a new domain row arrives with every one of those *semantic* columns
  already green. The **grammar surface does not follow**. `cardlang.lark` still
  hardcodes the 8 quantifier productions (`any player where` / `all suits where`
  / …) and the player/card query families as literal nouns, so a 5th row would
  type, iterate, bind and enumerate correctly and still have no `any <noun>
  where` production. The wall is loud (a syntax error on the unknown noun, not a
  silent acceptance), so this is a scope limit rather than a defect — but until
  the productions are generated from the registry, "a new domain registers
  itself" is true of the semantics and false of the syntax. Ledger:
  tests/test_domain_registry.py.

- **Collection facets vs nominal kinds — the promotion tripwire.**
  `TCollection` stands in for several runtime kinds (a `Zone`, a computed
  card list, a keyed map, a player set), distinguished by two facets
  (`key`, `zone` — `cardlang/types.py`) that the walls consume: zone
  positions require the `zone` marker, keyed maps check their key domain on
  read/write and reject `in` as ambiguous. The walls are the right shape —
  one predicate/fact each, several consumers — but the facet *mechanism*
  carries a wrong-level smell: the facts ride ON a structural type, so every
  site that constructs or rebuilds a `TCollection` must remember to preserve
  them. That obligation already produced one regression (`unify` rebuilt
  collections bare and dropped both facets; fixed and pinned in
  tests/test_let_typing.py). The higher-level form is nominal kinds in the
  closed `Type` union (`TZone`, `TMap<K,V>`), where preservation is free by
  construction and new consumers are forced by exhaustiveness — but the
  split hides a real design question: a zone must stay readable AS a card
  collection (`card in hand[p]`, aggregation sources), so `TZone` needs a
  subtype relation to `Collection<Card>`, and this type system deliberately
  has coercions, not subtyping. Deferred until any ONE of three named
  triggers fires, at which point the subtyping question must be answered
  anyway and the refactor pays for itself:
  (1) a third facet is proposed for `TCollection`;
  (2) a second facet-preservation bug appears (a construction site
  forgetting `key`/`zone`);
  (3) a surface operation lands that needs per-kind RESULT semantics, not
  just per-kind legality (sort/filter/take as expressions over
  zone-vs-list-vs-map).

- **Semantic invariance is pinned per instance, not in general.** The engine
  must not attach meaning to things the spec says are meaningless — a name's
  spelling, declaration order, a suit's identity, the `run`/inline
  distinction — but today only single witnesses pin this (the by-value
  expansion regression test; the goldens' byte-stability). The general form
  is a metamorphic suite: transform every corpus game in a spec-meaningless
  way, replay both variants, require trace agreement. The implementation
  plan — the four transforms, the pairing harness over the existing
  driver/trace seams, and the acceptance criteria — is
  [design-notes/metamorphic-suite.md](design-notes/metamorphic-suite.md).

- **Surface totality is probed by hand, not mechanized.** Misuse-probe
  rejection tests cover the wrong sentences someone thought of; nothing
  sweeps the sentences nobody did. The general form is fuzzing behind one
  oracle — every input passes the pipeline or fails as a located diagnostic;
  anything else is a wrong-currency finding — over corpus mutants first,
  then grammar-directed generation, with shrunken findings feeding the
  rejection corpus. Sequenced after the metamorphic suite. The
  implementation plan is
  [design-notes/grammar-fuzzing.md](design-notes/grammar-fuzzing.md).

## Suggested next steps, in order

[open-questions/_index.md](open-questions/_index.md) orders the open
questions by impact × actionability and is the authority on question
priority. This section adds what that list doesn't carry: the cross-cutting
work that isn't an open question, and which next game unblocks what.

1. **Add the `as <player> { … }` block**
   ([open-questions/single-actor-binding.md](open-questions/single-actor-binding.md),
   now Tier 1). It is the one outstanding item that fixes a *silently wrong*
   program rather than an awkward one: `for each player p: if p is actor` — the
   only way the language can say "one named player decides" — is true for every
   `p`, because the loop rebinds the acting player and `actor` reads it. Named
   procedures walled the trap at their own boundary and, in doing so, proved it
   exists; the idiom written inline is still unguarded, and six games use it. The
   runtime plumbing (`ctx.acting_as`) is already there. Rewrite the corpus uses in
   the same change (French Tarot's chien, Cribbage's crib, Schnapsen's answer,
   Coup's influence loss), per the lockstep rule.

2. **Pick the next game for its unblocks.** The full pipeline is
   [games/_candidates.md](games/_candidates.md); several candidates each
   unblock more than one open question:

   - **500 or Belote** — the unequally-observed phase outcome that
     [knowledge-events](open-questions/knowledge-events.md) awaits (500's
     open misère reveal; Belote's in-play declarations), and plausibly also
     the compound hidden-function probe that blocks
     [structural-infoset-proofs](open-questions/structural-infoset-proofs.md)'
     constructive world generator — one game, two unblocks.
   - **President** — the corpus-quality anchor
     [turn-loop-form](open-questions/turn-loop-form.md) is blocked on, and
     the third climbing instance that triggers promoting a shared
     combination model to the standard library.
   - **Gin Rummy** — the other turn-loop-form anchor, and the rummy-family
     game [meld-groups](open-questions/meld-groups.md) is blocked on.
   - **Klondike or FreeCell** — first solitaire; forces the deferred
     positional-zone design rather than an open question.

3. **Address Tier 3 questions when their corner gets exercised.**
   [move-level-visibility](open-questions/move-level-visibility.md) awaits
   the first game needing a move-level projection override. When these
   land, the partition checks are their acceptance bar: new visibility
   surface arrives with derived partition coverage, not bespoke tests.

4. **Pin down [memory-event-syntax](open-questions/memory-event-syntax.md)**
   when three or four examples exist beyond stdlib operations (Stud and
   Coup are the two so far; both composed the closed vocabulary without
   needing a declaration).

5. **Defer Tier 5 cosmetic questions** until a real preference emerges
   from corpus pressure.
