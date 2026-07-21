# Roadmap

What's explicitly deferred, and the suggested order of next steps.

## Explicitly deferred

Things we have noted but consciously not designed yet:

- **Named procedures — deferred cells.** Every one is a loud wall today, never a
  silent acceptance; the ledger is `tests/test_procedures.py`. (a) **`Zone`
  parameters.** The design note expected the corpus to need them; it does not — a
  `Player` parameter already carries its zone (`influence[victim]`), so the domain
  is `Player` / `Rank` / `Rank?` / `Integer` and every other spelling is rejected.
  `Rank?` rather than `Rank` is the form the corpus forces: there is no flow
  narrowing, so a bare `Rank` parameter would reject `block_claim` at the very
  sites that must pass it. `Integer` was on this deferred list until
  `poker_betting`'s `open_street(bet_size)` forced it — the five street resets
  across Leduc and Stud being one shape differing in one integer — which is the
  corpus-first rule working rather than a hole closing. (b) **A `round` in a procedure body.** It binds its own, round-local
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

- **An empty `type X = { }` is declarable but not constructible.** `type_def`
  takes `struct_field*` (zero or more) while `struct_lit` requires at least one
  field, so an empty struct type parses, resolves, and can never be written as a
  value. It is the declaration/use symmetry that `STRUCT_TYPE_NAME` enforces on
  the NAME axis, unenforced on the arity axis. Harmless today — an empty type is
  inert, so nothing can depend on one silently doing something — and the fix is
  a one-token grammar change (`struct_field+`) plus a diagnostic for the games,
  none of which declare one. Left for whoever next touches `type_def`, recorded
  so the surrounding ledger in tests/test_game_clause_walls.py does not read as
  claiming it.

- **Family libraries — unchecked residuals in the `requires` contract.** Two,
  both of them the contract promising less than a reader might assume.

  *The declaration need not be in SCOPE where the library runs.* `_check_requires`
  proves that exactly one declaration of a required name exists somewhere in the
  game, at the right arity and type. It does not prove the library's definitions
  can read it where they run: move Kuhn's `limit` into `phase deal` while the
  imported `bet` runs in `phase betting` and resolve passes, typecheck passes,
  and the playout dies on a bare `KeyError` out of `runtime/state.py`. The root
  cause is NOT the import tier — a plain game with no library reproduces it, one
  phase declaring what another reads — so the fix is use-site scope reachability
  for state generally, and the contract must not be dressed up as standing in for
  it. Narrowing the contract to game-level declarations would not close it and
  would reject Seven-Card Stud, which declares all seven requirements inside
  `phase play`.

  The DECLARE-TIME slice of that class is closed
  (`resolve._check_state_default_scope`, decisions.md "State scoping (lexical)"):
  a `state { }` default now reaches only what is declared before it, so the
  `KeyError` can no longer arrive while the block is being built. What remains
  open is the PLAY-TIME half described above — a body reading, at some later
  point in the game, a variable whose phase is not active. Do not read the
  declare-time wall as covering it: the two share a symptom and nothing else.

  *A name held as a bare string is not classified.* The contract IS checked to be
  sufficient for every name the resolver classifies: free names, calls and card
  literals are checked against the library alone, so a body cannot reach past
  `requires` into the importing game through any of them
  (`resolve._check_library_encapsulation`, ledger
  `tests/test_family_libraries.py`). The check is built on the `NameRef` pass, so
  it is blind to every AST slot that holds a name as a plain `str` — the same
  blindness `resolve.py`'s `again` handling already documents for `Winner.target`.
  Confirmed reachable from a library, by namespace:

  - state — `turns … again <var>` (`Turns.again`);
  - zones — `round … source <zone> into <zone>` (`Round.source_zone`, `play_zone`);
  - types — `StructLit.type_name`, `StructField.type_name`,
    `VariantCase.payload_types`;
  - definitions — `constrains:`, `run <proc>()`, `produces <define>`,
    `offer […]`, `Round.move_types`.

  Two consequences worth naming. A library reading a state variable through
  `again` leaks it exactly as the wall's own docstring describes; and putting
  that name in `requires` instead does not help either, because `state_reads`
  also accumulates only from `NameRef`s, so the minimality check
  (`test_every_library_contracts_for_exactly_what_it_reaches`) would call the
  entry dead. The slot has no correct spelling today. The two halves are
  independent code paths — teaching `state_reads` about `again` would fix the
  minimality trap on its own and could not make a leak easier to ship — but
  neither is patched here for the same reason: a hand-added arm for one slot is
  precisely the by-luck hand-list this residual exists to avoid, and the slot
  registry below closes both at once.

  The residual is bounded on one side: a slot naming something that exists
  NOWHERE is already rejected, so what is unchecked is the narrower case of a
  library naming something only the importing game provides. The fix is a
  reference-slot registry — one table saying "this field holds a name drawn from
  that namespace", total over every `str`-typed field of every `n.Node` (94 of
  them today, so the table must be derived and pinned, not hand-listed) — which
  several passes would share. Build it before a second family library lands; the
  one-library corpus is what makes it currently harmless.

- **Library-vs-library cross-kind name clashes are not walled.**
  `_check_library_shadows_game` refuses a library injecting a name the GAME
  already uses, and `_check_library_collisions` / `_check_state_claims` refuse
  two libraries colliding on the SAME kind (both define `foo`, both provide
  `foo`). What neither covers is two libraries whose names clash across KINDS —
  library A provides state `foo` while library B defines `function foo` — which
  resolves today with no diagnostic. It is unreachable in the current corpus (no
  game `uses` two libraries; there is only one), which is why it is recorded
  rather than walled. The honest fix is not a third bolt-on comparison but the
  shared name registry the `requires`-contract residual above already wants:
  fold every library's injected names into one pool and check that pool against
  itself and the game in a single sweep. Build it when a second library lands —
  the same event that first makes this reachable.

- **A game may still reuse ONE name across its OWN namespaces.** The base
  language accepts `state { pile }` alongside `zones { pile }`, a state variable
  spelled like a suit (`state { hearts }`), or a function named after a rank —
  `_classify`'s precedence silently resolves the bare reference (state variable
  wins over zone, which wins over deck value, which wins over function), so the
  loser is unreachable by that spelling with no diagnostic. This is deliberately
  NOT walled: the author wrote both declarations and can see both, which is the
  ordinary block-shadowing every language allows, and a game-level uniqueness
  rule would be a much larger, higher-risk change than the corpus has forced.
  It is recorded here, not silent, because the LIBRARY face of the same clash IS
  walled (`resolve._check_library_shadows_game`, decisions.md "Family libraries")
  precisely on the visibility asymmetry — a library injects a name the game's
  author cannot see. If a designer is ever surprised by their own cross-namespace
  shadow, the fix is to lift the same sweep to the game's own declarations and
  measure the corpus cost; do not conflate it with the library wall, which turns
  on invisibility and would be wrong to apply to names the author wrote.

- **A game-local BINDER may shadow a provided state name.** The read-only wall
  (`resolve._check_provided_readonly`) refuses a game WRITING provided state, and
  `_check_library_shadows_game` refuses a library injecting a name the game
  already binds at declaration level. What neither covers is a binder or
  parameter the game introduces — `for each player limit:`, `function
  f(limit : Integer)`, a comprehension or quantifier binder — spelled like a
  provided variable: inside its scope the bare name is the binder, not the
  provided read, with no diagnostic. It is the binder face of the same
  visibility asymmetry the injection wall turns on (the author cannot see that
  `limit` is provided), and it is genuinely open — `_check_reserved_binders`
  refuses only `RESERVED_VALUE_NAMES`, whose carve-out is justified by "a binder
  is always scoped strictly narrower than a same-named outer declaration the
  author WROTE", which does not hold for a declaration in a file they never open.
  Severity is low: it needs a binder named exactly after a provided variable AND
  an intent to read the provided one inside that scope. Wall it by extending the
  binder-introduction sweep (`_introduced_binders` / `_BINDER_SCOPE_FIELDS`) to
  refuse a provided name, the same registry the reserved-binder check already
  walks — a bounded change, deferred only because no corpus game names a binder
  after a library variable. The WRITE case is already safe: `let limit = 5` then
  `limit := 6` is refused.

- **The inline-vs-`run` metamorphic transform does not cross the import
  tier.** T3 (`tests/metamorphic/test_inline.py`) splices every `run` site
  with its procedure's body, reimplemented at SOURCE-TEXT level so it is
  independent of `cardlang.expand`. That reads one file, so a game whose
  procedure body lives in a family library is outside its domain: Kuhn, Leduc
  and Seven-Card Stud all `run open_street(...)` from
  `docs/libraries/poker_betting.cardlang`, and T3's property is genuinely
  unchecked for the three. Also reading the library file would NOT fix it —
  the game still `uses` that library, so the then-uninvoked library procedure
  is a resolve error and the spliced text would not compile; the splice would
  have to rewrite the `uses` line and the library together. The gap is pinned
  as a named list (`test_the_library_procedure_games_are_pinned_as_uncovered`)
  so it cannot shrink or grow silently. Worth closing when a second library
  lands, since the shape generalizes rather than being poker-specific.

- **Family libraries — zones and phases are not forced YET.** A library holds
  definitions and state (decisions.md "Family libraries"). Two things it still
  cannot hold, and the negative on both is weak — "no family has forced it",
  not "settled no":

  *Zones.* `poker_betting`'s state surface names none, and that is a real signal
  for the poker family rather than an accident: its zone-touching move (`fold`)
  is exactly the one that stayed game-local, because which cards a fold disposes
  of is a property of the table. But the smuggling survey below found zones in
  the irreducible shared material, so the next family may well force them.

  *Phases.* Neither family forced one. Poker's shared phase material reduced to
  statements a parameterized procedure covers (`open_street`), and so did the
  smuggling family's.

  The smuggling evidence (`experiments/green-lane/`) carries a caveat that
  limits how far it travels: those variants are a DELTA LATTICE — v4 is v1
  composed with v3, each delta editing disjoint rule text — so they share a
  great deal by construction. A family of siblings rather than deltas may share
  a differently-shaped body of material and need not reproduce the
  zones-and-state signal. Do not promote either negative to a decision on this
  evidence; wait for a family that forces the question, and name it.

- **A `state { }` default is not checked against its declared type.** An
  accepted-but-ignored hole, found by sweeping `n.Expr` in default position
  while walling declare-time scope, and NOT closed by that wall. `v : Integer =
  "s"`, `v : Integer = false`, `v : Boolean = 7` and `v : Integer = all players`
  are all accepted today; the declared `type_name` reaches `typecheck` only as
  the variable's type for later reads, and the default expression is never
  compared against it. No corpus game trips it — every default is an integer or
  an enum literal of the right type — which is exactly why it survived. The fix
  belongs in the type layer, not in `resolve._check_state_default_scope`: that
  wall's property is declare-time reachability, and stretching it to types would
  put the rule where nobody would look for it. It is also the wall the
  `AllPlayers` row of `tests/test_state_default_scope.py`'s ledger is waiting
  for — that row is currently a residual with a record and no wall, the one
  place that ledger does not meet the surface-totality gate.

- **A `state { }` default may not call a function.** A deliberate narrowing, not
  an unimplemented case, and recorded here so it is reopened on evidence rather
  than by accident. A default runs while its block is still being declared, and
  a callee's state reads live in a body the default's own tree does not contain
  — so honouring a call would mean a declare-time reachability analysis through
  every function a default can reach, including nested and mutually recursive
  ones. The measured price of refusing instead is zero: an AST scan of every
  `state` default across `docs/games/` and `docs/libraries/` finds `IntLit` and
  `NameRef` only, spelled `none`, `false`, `true` and `hold` — not one default
  reads a state variable, let alone calls anything. Reopen when a game wants a
  computed initial value that a phase cannot set, and name the game.
  (decisions.md "State scoping (lexical)"; ledger
  `tests/test_state_default_scope.py`.)

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
  observation-encoding decision, not a rewrite).
  The `turns` form has no `direction` override clause (rotation follows the
  game's declared direction; not grammar until a game needs a mid-game or
  per-loop override). Joint-predicate selection: `jointly` under a `random`
  or dealt selection is rejected (a subset decision needs a decider; a
  uniform-random satisfying subset has no corpus user), `some` without
  `jointly` is rejected (nothing owns the size), `jointly` with `to each`
  is rejected (each destination seat would become its own subset decider —
  a real semantic no game has asked for; note the pre-existing non-joint
  `chosen … to each` DOES reassign the decider per parcel the same way,
  unexercised by the corpus and undocumented — the same decision awaits
  whichever game first wants either shape), and the subset enumeration
  refuses source pools past 16 cards at runtime rather than hanging
  (`cardlang/runtime/execute.py`, `_JOINT_ENUMERATION_BOUND`). Movement
  amounts: negative is a typed runtime error everywhere and a zero `chosen`
  amount is refused as a vacuous decision (`_check_count`), while a zero
  dealt/`random` amount stays an accepted no-op (a computed "deal what
  remains" may legitimately be zero). On the
  OpenSpiel side, a joint predicate must root in a call with a registered
  subset codec (`cardlang/runtime/stdlib.py`, `joint_codec_function` — the
  climb-codec pattern); an inline or unregistered predicate, a game mixing
  climb and joint selections, or two joint predicates wanting different
  codecs are each a loud `NotImplementedError` at action-space
  construction, lifted when a game forces the composed-combo-block design.
  Joint selections on a deck with duplicate identical cards (pinochle48,
  doppelkopf48, coup15, canasta108) are refused there too: the combo block
  canonicalizes subsets by frozenset, which collapses copies — {K♠, K♠}
  would collide with {K♠} — so the encoding needs a multiset-safe
  canonicalization no game has forced (Canasta, the first duplicate-deck
  melding game, deliberately encodes melds per card through the card block
  instead — copies share an id soundly there, since identical cards are
  interchangeable).

- **Unanchored inline keywords are a fused-typo misparse class.** Under the
  dynamic lexer an inline string keyword can match as a PREFIX of an
  identifier, so a fused typo gets a real second parse and may compile
  (`onecards` as `one cards`). The members this change anchored (whole-word
  negative lookahead): `turns`, `again`, the `amount` position's `all`/
  `one`/`some`, `jointly` (plus the earlier `as`/`is`/`not`). The REMAINING
  unanchored members are recorded, not fixed: `round`/`offer`/`reveal one
  card`/`all players`/`for each`… — every other inline keyword adjacent to
  a NAME. `allplayers` (with a same-named variable declared) is a live
  silently-misresolved example (`_ambig`, the all-players reading wins).
  The class fix is mechanical (anchor every inline keyword, or move to a
  contextual-keyword lexer callback); sweep it as its own change with the
  corpus ambiguity gate as the net.
  Rules that the runtime cannot yet enforce at all are a
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

- **500's lead-time joker nomination.** Pagat's no-trump-family rule lets an
  un-nominated joker be *led* with a lead-time suit nomination (naming a suit
  not previously led, which the others must follow; the lead is illegal once
  all four suits have been led, except to the last trick). The corpus file
  keeps the restriction and drops the nomination: an un-nominated joker may
  be led only as its holder's last card
  ([games/five-hundred.md](games/five-hundred.md), "Chosen ruleset"); the
  wall is `five_hundred_lead_ok` filtering the lead out (never
  accepted-but-ignored — the move is simply not offered). The declarer's
  start-of-play nomination, the strategically load-bearing form, is modelled
  in full. Revisit if a game forces play-time suit nomination as a
  first-class decision — the same contextual-declaration surface Euchre's
  bower work ([open-questions/special-cards-declaration.md](open-questions/special-cards-declaration.md))
  may grow.

- **Positional zones — walled residuals.** Positional layouts are live
  ([decisions.md](decisions.md) "Position domains and positional zones";
  Klondike and FreeCell are the corpus anchors). Four cells of the position
  design stay deferred, each behind a wall:
  - `for each <position>` iteration and position-indexed `state` stores —
    both rejected at resolve with diagnostics
    (tests/rejections/positions_for_each,
    positions_state_indexed_by_position); no corpus game addresses columns
    by loop or keeps per-column scalar state (guards + parameters cover
    both games). Implement when a game needs one.
  - A **positional slice movement** ("card X and everything above it" as
    surface). Klondike's run move is denoted by a rank filter because a
    cascade's face-up run is rank-monotone (the run invariant); Spider's
    mid-game deals break that monotonicity, so Spider is the forcing
    candidate ([games/_candidates.md](games/_candidates.md)). Until then a
    non-denotable unit move simply has no sentence that expresses it —
    grammatically inexpressible, not accepted-and-dropped.
  - `top_of`/`bottom_of` in a move **guard** over a zone the decider
    cannot see would make legality depend on hidden state. No static wall
    exists (guards may legitimately read any expression); the per-game
    openspiel_ready legal-action-agreement proofs are the police, as for
    every other guard read (tests/test_positions.py names this residual).
  - The canonical **gather** over a position family is order-preserving
    per the canonical zone-collection rule but has no corpus witness
    (single-deal games never gather); sampled, stated explicitly in
    decisions.md rather than assumed.

- **Doc-snippet fragment kinds with no cheap wrapping harness.**
  `tests/test_doc_snippets.py` pipeline-checks every `cardlang`/
  `cardlang-fragment` block in decisions.md/library.md/model.md, but a
  `cardlang-fragment` block needs a registered recipe embedding it in a
  minimal game; some fragment shapes have none and are tagged `text`
  instead (residual, not silently skipped — see that module's docstring
  ledger for the full list and why each is uncheckable today):
  phase-outcome pattern matches (`produces:`/`continue to`, which need a
  sibling phase's declared variant set plus game-specific tag vocabulary);
  `legal_moves:` with `+`/`-`/`override` deltas (the grammar has no such
  production — only `active_rules:` does); user-facing
  `Zone<ContentType> { composition: ... }` declarations (no such
  production exists — projection is the closed `ZONE_PROJECTIONS` Python
  registry, cardlang/stdlib/zones.py); `type` fields with a range, union,
  or type-parameter shape (`Integer in 1..7`, `Suit | NT`,
  `type X<Layer: Integer> = ...` — `struct_field`/`type_def` only support a
  bare, optionally-`?`, type name); the retired `choose <Type> with
  <constraint>` statement and `<actor> chooses <description>` expression
  forms (superseded by `round offering [...]` and plain function calls);
  and the old `move_type X { source: ... destination: ... emits: ... }`
  shape (superseded by `when:`/`effect {}`). Resource-zone movements and
  the `override` rule-delta are the same residual class but already
  recorded above under "Grammar surface deferred by the checker"; `apply_components`
  the same but already recorded under "`scoring_component` / triggered
  components (runtime)".

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
  revealed). The challenge window now has its SECOND instance — Cheat
  ([games/cheat.cardlang](games/cheat.cardlang)), whose claim vocabulary is
  open (all 13 ranks) where Coup's is five characters, and whose window is
  the same game-local procedure shape as Coup's (rotate from the claimant's
  left, first challenge closes) — so a third instance triggers the
  `challenge` promotion; the shared shape to lift is the
  window-plus-verdict procedure, with the verdict predicate (Coup's
  has-the-claimed-character proof, Cheat's all-cards-match-the-claim flip)
  as the game-supplied parameter. The remaining scope of work is Tichu's
  call windows and Dragon routing — a behaviour change with its own
  sign-off, in [kernel-migration.md](kernel-migration.md), Workstream 5.

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

- **The runtime-assert triage scrape stops at the runtime packages.** The
  mechanized write-time-triage gate (`tests/test_assert_triage.py`) enumerates
  every `assert`/`raise AssertionError` in `cardlang/runtime/` and
  `cardlang/stdlib/` and requires each to name its triage class. The compile
  passes (`cardlang/parse.py` … `ir.py`, `openspiel/`) are outside its domain:
  their failure currency for game-description defects is the bag-collected
  diagnostic, and their internal asserts are pass invariants governed by the
  `Contract` blocks in their module docstrings — a blanket scrape would
  mis-rank those sites. Extending the gate there needs its own convention
  (which comment tags mark a pass invariant) before it can be mechanical.

- **`loser:` player-ness is checked at the driver, not statically.** The
  wall for a non-player `loser:` selection is a typed RuntimeError at the
  driver (`cardlang/runtime/driver.py`; pinned by
  `tests/test_fail_loud.py::test_a_non_player_loser_selection_raises_a_typed_error`),
  because the expression's type is often gradually `TAny`. When the checker
  can infer a concrete non-player type for the selection, it could reject at
  compile time; today it only validates the expression's names.

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

- **Semantic invariance: three of four transforms landed; suit relabeling
  (T4) is deferred.** `tests/metamorphic/` (design plan:
  [design-notes/metamorphic-suite.md](design-notes/metamorphic-suite.md))
  runs T1 (the pairing harness), T2 (α-rename), T3 (inline-vs-`run`), and T5
  (declaration reorder) over the corpus, each with its own completeness
  ledger. Landing them surfaced two real findings in `cardlang/` behavior
  (out of scope for the suite itself), both since resolved. (1) Game-local
  runtime primitives read zone/state names as Python string literals
  invisible to the pipeline — **closed as a class** by the declared-reads
  registry (`PRIMITIVE_READS`, `cardlang/runtime/reads.py`): every
  primitive read goes through typed accessors, the registry is pinned two
  ways by `tests/test_primitive_reads.py` (against each game file's
  declarations and against each module's accessor-call literals), a
  drifted name fails a static test — or, past that, a typed
  `PrimitiveReadError` — instead of a playout `KeyError`, and the rename
  transform derives its exclusions from the registry. The kernel's own
  literal reads (`cardlang/runtime/rules.py::legal_cards`,
  `cardlang/runtime/mechanics.py::param_domain`) are the language-wide
  magic `hand` name, spec'd in decisions.md "Declared parameter domains" —
  a documented rule, not latent coupling. (2) A gather's event order
  tracked zone DECLARATION order — resolved: `execute.py::_gather`
  collects in canonical sorted-name order (decisions.md, "Loop lifecycle:
  `before_each` and `after_each`"), and the reorder transform's zones axis
  now covers every corpus game.

  **T4 (suit relabeling) is explicitly deferred**, not attempted: unlike the
  other three, it cannot be a pure `Game -> Game` AST transform — a suit's
  actual card membership comes from `cardlang.runtime.values.DECKS` (and the
  parallel `cardlang.stdlib.values._DECK_SIZE` table), a Python registry
  keyed by the `deck:` NAME, not from anything the parsed tree carries; a
  sound implementation needs a permuted deck registered at test time, a
  chooser whose sort key is permutation-equivariant (or the two variants'
  greedy playouts diverge in STRUCTURE, not just labels, the first time a
  suit-dependent decision breaks a tie), and a trace-rename hook covering
  both raw suit names (`submit_bid(hearts)`) and `Card.__str__`'s suit
  SYMBOLS (♣♦♥♠★☆) — three compounding sources of risk in one transform, on
  top of the same hardcoded-suit-name landmines finding (1) above predicts
  for trump-handling primitives specifically. Revisit if a second
  procedure-using corpus game or a suit-relabeling need makes the investment
  clearly worth it; until then this is a bounded, understood gap, not a
  silent one.

- **Mechanized surface totality: corpus mutation landed (T1-T3); grammar-
  directed generation (T4) and shrinking (T5) are deferred.** `tests/fuzz/`
  (design plan:
  [design-notes/grammar-fuzzing.md](design-notes/grammar-fuzzing.md)) runs
  the oracle (T1, `tests/fuzz/oracle.py::run_oracle`: every input either
  passes `check_dsl` or fails as a `DiagnosticError`; anything else is a
  finding) over five corpus-mutation operators (T2,
  `tests/fuzz/mutate.py`: delete a line, duplicate a declaration, swap
  adjacent tokens, rename one identifier occurrence, truncate a block) and
  a bounded random playout for every pipeline-passing mutant (T3,
  `run_playout`: termination or a clean cutoff, a non-empty legal set at
  every decision, terminal-score reconciliation against the declared
  `winner:`/`loser:`). A discovery sweep — 18 corpus games x 5 operators x
  5 seeds, 450 mutants — found 6 crashing triples, all under
  `delete_line`: one wrong-currency crash (`cardlang/parse.py`'s `game()`
  transform validates a missing `cards:`/`players:` clause with a bare
  Python `assert` rather than a `DiagnosticError`, so Lark's `VisitError`
  escapes `check_dsl`) and five accepted-then-crashes-at-playout findings
  (a mutant passes every static wall but breaks a runtime-net invariant —
  a hand drained faster than the loop reading it, a non-terminating
  `repeat until`, a short trick). All six are recorded, not fixed, in
  `tests/fuzz/findings.py`'s `KNOWN_FINDINGS` ledger — concurrent work was
  touching resolve/typecheck when this landed — and pinned loud (a
  dedicated test replays each frozen minimal repro and fails if the crash
  stops reproducing); each migrates to `tests/rejections/` once it is
  actually fixed, per that module's feed-forward rule.

  **T4 (grammar-directed generation walking `cardlang.grammar` productions
  directly) and T5 (mechanized delta-debug shrinking) are deferred**, not
  attempted: T1-T3 took the full budget to land cleanly with a verified,
  CI-budgeted sweep (`tests/fuzz/test_fuzz.py`'s `MUTATION_SEEDS`, ~45-55s);
  every `KNOWN_FINDINGS` entry above was shrunk by hand instead of
  mechanically. Revisit once a wider mutation sweep
  (`FUZZ_BUDGET_SECONDS`, the local/scheduled mode) suggests operator-level
  coverage has plateaued.

## Suggested next steps, in order

[open-questions/_index.md](open-questions/_index.md) orders the open
questions by impact × actionability and is the authority on question
priority. This section adds what that list doesn't carry: the cross-cutting
work that isn't an open question, and which next game unblocks what.

1. **Take the family-library tier to its second family.** The `uses
   <library>` mechanism is built and settled ([decisions.md](decisions.md)
   "Family libraries"): grammar surface, library loading, the flat two-level
   splice, the three-way collision walls, the `requires` contract, PROVIDED
   state and its read-only rule, and the totality artifacts in
   `tests/test_family_libraries.py`. Its poker anchors
   are landed — Seven-Card Stud as the full-scale consumer, and **Kuhn** and
   **Leduc** as the two that make the tier non-vacuous, since a library with
   one consumer is indistinguishable from game-local code. All three share
   `docs/libraries/poker_betting.cardlang` verbatim and each defines its own
   `fold`. Both edges the anchors existed to check came out clean, and are
   now pinned by their proof modules rather than assumed: an
   imported-but-unoffered move type (Kuhn's `raise`) mints no action id,
   because the action space is derived from the `offering`/`offer` lists and
   never from the game's move-type table; and `raise_cap` carries a real
   family difference (Leduc 2, Stud 3) entirely in each game's declared
   state, with neither the library nor the `uses` line mentioning it. The
   per-STREET bet size does not: `limit` is provided state that the library's
   `open_street(bet_size)` sets, since no single declaration can carry a value
   that varies within a game (decisions.md, "Family libraries").

   What is still unmeasured is whether that parameterization scales. Both
   anchors vary only in *scalars* on required state; the next customer is the
   smuggling family
   (`experiments/green-lane/`), whose five sibling rulesets share ~90% of
   their text and are kept aligned by hand-diffing — the copy-drift the tier
   removes, and the case that will test whether parameterization can keep
   riding on required state or genuinely needs a `with` clause.

2. **Pick the next game for its unblocks.** The six-game wave (Cheat, 500,
   Belote, Canasta, Klondike, FreeCell) cleared the candidates that each
   unblocked a Tier 2 question; the full pipeline is
   [games/_candidates.md](games/_candidates.md). The candidates that still
   each unblock an open question:

   - **Euchre** — the bowers are the sharpest witness for
     [special-cards-declaration](open-questions/special-cards-declaration.md)'s
     contextual-rank axis (rank *and* effective-suit remap, keyed to a
     runtime-chosen trump). 500's joker and bowers were carried by game-local
     primitives, leaving the *declarative* bower surface unforced — Euchre is
     that forcing function.
   - **Hold'em** — the "show one, show all" showdown rule is the per-observer
     move-level override that
     [move-level-visibility](open-questions/move-level-visibility.md) awaits
     (exercisable in the existing poker corpus), and it would be the poker
     family's fourth `uses poker_betting` consumer — the first whose betting
     structure (blinds, a four-street board) differs from Stud's streets and
     the toys' single-card hands ([decisions.md](decisions.md) "Family
     libraries").
   - **Spider** — the third positional game and the forcing candidate for the
     deferred positional slice movement ("Positional zones — walled
     residuals", above): its mid-game deals break the run-monotonicity that
     let Klondike denote runs with a rank filter.

   Not game-gated: the
   [structural-infoset-proofs](open-questions/structural-infoset-proofs.md)
   residual is generalizing the constructive world generator (first instance
   landed with Cheat) across the corpus via per-game emission-site analysis —
   no new game needed. And
   [knowledge-events](open-questions/knowledge-events.md) is narrowed by 500
   and Belote to awaiting only an out-of-scope dedicated-deck game (Mascarade
   / Love Letter).

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
