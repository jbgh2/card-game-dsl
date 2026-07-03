# Roadmap

What's explicitly deferred, and the suggested order of next steps.

## Explicitly deferred

Things we have noted but consciously not designed yet:

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

- **Detailed melding logic.** Pinochle's meld phase is hand-waved as a
  mechanic. Real melding (combinations, scoring, conflicts) is its own design
  exercise.

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
  it), and adapters for the games whose logic still lives in concrete mechanics.
  Enabling the `openspiel` extra in CI to run the adapter tests is a small
  follow-up.

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
  move vocabulary); typed outcomes and definition-composition; and the `auction` /
  `challenge` / `block` / `climb` standard-library vocabulary. Seven games
  (Schnapsen, Pinochle, Skat, Tarot, Cribbage, Tichu, Coup) still
  hold their decision logic in concrete per-game runtime
  mechanics; lifting each into the kernel + DSL standard library (promoting a
  definition at ~3 examples) closes the spec-vs-runtime gap. The bidding
  sub-language, detailed melding, and strict-trick legality noted on this list
  are subsumed by this work. The game-by-game execution order, the per-game
  scope, and the language-gap checkpoints are in
  [kernel-migration.md](kernel-migration.md).

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
  **Stage 3 is built:** phase `→ outcome { … }` + `produces:` on phases and on
  `instantiate`d mechanics (a mechanic raises the same `_ProduceSignal`, adopted
  by its enclosing outcome-declaring phase), the imperative arm vocabulary
  `continue to <phase>` / `skip to next hand`, and nullable variant payload types
  (`Suit?`) — reusing the Stage-2 `produces:` consumer and `TVariant`
  (`decisions.md` "Typed phase outcomes"). **Bridge** (auction:
  `contract_finalized | all_pass`) and **Schnapsen** (settlement: `claimed |
  talon_closed | open_play`) are migrated off their Boolean gates onto it.

  The remaining typed-outcome migrations stay deferred because their decision is
  not at a clean DSL/mechanic boundary: **Pinochle** (`declare_trump`),
  **French Tarot**, and **Skat** fuse their auctions into Python monoliths whose
  extraction is the interactive-decision-kernel work; **Getaway**'s two-way
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

  Deferred checker coverage (from Stage 1 review): BinOp operand compatibility
  (`hearts == 5` currently passes), movement `amount` must be Integer, rule
  `demands`/`applies_when` conditions, and constraining `loser.selection` to
  `Player`. Stage 2 types `produces:` arm binders (its scoped consumer walk), but
  the other binders — `for each` / lambda / comprehension / quantifier /
  player-query — still infer `TAny` today (deliberately, to avoid false
  positives), so binder-typed mistakes there are missed.

- **`scoring_component` / triggered components (runtime).** The design is settled
  (decisions.md "Scoring composition" and "Triggered scoring components"), but the
  runtime folds scoring inline / into per-game mechanics and has not built the
  component subsystem. Build it when a game needs cross-hand triggered scoring
  that inline computation can't express.

- **Representative playouts.** The runtime's random chooser exercises invariants
  but never reaches skill-gated branches (Spades' +500 win, bridge slams,
  Schnapsen false claims are implemented but unexercised). A light "rational-ish"
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
  points), Spades' nil and bag-overflow score branches, and Coup's challenge
  resolving to the correct loser. (The Bridge analogue — a full scoring recompute
  — is done.)

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

## Suggested next steps, in order

The [open-questions/_index.md](open-questions/_index.md) orders open
questions by impact × actionability; Tier 1 there are the questions ready
to commit now. This section adds the context the open-questions list
doesn't carry: which next game would unblock Tier 2, and the meta-level
work (OpenSpiel compilation, dealer promotion) that lives outside the
open-question framing.

1. **Tier 1 is empty.** All four original Tier 1 questions have
   been resolved into decisions.md:
   - `sub-phase-rule-syntax` → "Sub-phase rule and legal-move deltas"
   - `triggered-scoring` → "Triggered scoring components"
   - `actor-vs-chooser` → "Delegated play"
   - `mechanic-internal-legality` → folded into "State scoping (lexical)"
     (a still-Python mechanic's state is in scope for rules via standard
     lexical nesting). Stud's betting legality later moved onto the kernel
     `round`'s move-type `when:` guards over phase state, not rules.

2. **Tier 2 is empty.** All Tier 2 questions resolved. The remaining
   open questions are Tier 3 (medium impact, narrow scope) and below;
   each is a small targeted question that can be tackled when its
   corner of the language gets exercised. The full candidate pipeline
   lives in [games/_candidates.md](games/_candidates.md).

   Triggered-scoring was unblocked by Cribbage, bidding-meaning by
   Oh Hell, and structured-score landed in decisions.md after Skat
   confirmed the per-game pattern (see decisions.md "Scoring
   composition"). Coup, the second resource-using game, resolved
   the resource amount and transfer-failure questions (see decisions.md
   "Resource amount syntax" and "Resource transfer failure").

   Headline recommendations from the pipeline:

   - **The `climb` kernel migration** — the immediate next step.
     **Big Two** has landed as the **second combination-climbing
     instance** after Tichu (`cardlang/runtime/bigtwo.py`,
     `docs/games/big-two.cardlang` — a concrete mechanic, like Tichu's),
     so the WS3 migration is now unblocked
     ([kernel-migration.md](kernel-migration.md), "Workstream 3"): the
     `climb` kernel `round` construct and the combination queries are
     co-designed against Tichu *and* Big Two (its engine adds flushes,
     quads, and suit-tie-breaks over `combinations.py`), then both
     monoliths are deleted. **President**
     ([games/_candidates.md](games/_candidates.md), "Climbing &
     shedding") is the simpler third climbing instance after that.
   - **Klondike or FreeCell** — first solitaire; tests positional
     zones. Doesn't directly unblock a Tier 2 question but forces a
     deferred design decision.
   - **Doppelkopf** — the highest-value in-scope candidate: a verified
     forcing function for *both* `zone-access-syntax` (Fox/Charlie/Re
     scoring read a multi-hop relational chain over who holds the ♣Q)
     and `optional-window-moves` (the Re/Kontra/no-90 ladder is an
     off-the-clock declaration on a personal hand-size threshold). See
     [games/_candidates.md](games/_candidates.md).
   - **Klondike** / **Hanabi** — would each force a different deferred
     design corner (positional zones; the partial-identity hint that
     `memory-event-syntax` was waiting for). Hanabi is a dedicated-deck
     game, so it's gated on a scope decision. Both are bigger swings
     than the trick-and-bidding games we've been doing. (Coup, a former
     candidate here, is now in the corpus; it exercised the
     knowledge-event and challenge-mechanism corners and confirmed the
     simultaneous-body-grammar boundary.)

3. **Address Tier 3 questions when their corner of the language
   gets exercised.** Coup, the second resource-using game, resolved
   the resource amount and transfer-failure questions (now in
   decisions.md). The remaining resource/visibility refinement,
   [move-level-visibility](open-questions/move-level-visibility.md),
   is still open: Coup used only zone-default projections and never
   needed a move-level override, so the override-replace-vs-merge
   question awaits a game that does.
   [zone-access-syntax](open-questions/zone-access-syntax.md) waits for
   a game whose natural notation puts a complex relational chain in
   subject position.

4. **Pin down [memory-event-syntax](open-questions/memory-event-syntax.md)**
   when three or four examples exist beyond stdlib operations. Stud is
   the first, Coup the second (its challenge-defense composes stdlib
   ops rather than declaring a custom event — see the open-question
   file); one or two more before pinning the syntax.

5. **Tier 4 cleanups landed.** Counters and dealer-promotion are
   both resolved — counters as inline expressions or per-game
   helpers (see decisions.md "Scoring composition"); dealer as a
   stdlib state variable (see library.md "Stdlib state").

6. **Defer Tier 5 cosmetic questions** until a real preference
   emerges from corpus pressure.

7. **Build the parser + static checker first.** Before the
    OpenSpiel compilation pass, the near-term tooling milestone is a
    grammar and a static checker that force the spec to be precise,
    with the corpus as the test suite. See
    [implementation.md](implementation.md).

8. **Begin sketching the OpenSpiel compilation pass.** The
    [decisions.md](decisions.md) "Knowledge, visibility, and the
    projection model" section establishes perfect-recall-by-default;
    [decisions.md](decisions.md) "State scoping" establishes lexical
    scoping compiles to standard activation records; the
    knowledge-projection model gives OpenSpiel's
    `information_state_tensor` the per-observer event stream it
    needs. The compilation story has substantial scaffolding now.
