# Roadmap

What's explicitly deferred, and the suggested order of next steps.

## Explicitly deferred

Things we have noted but consciously not designed yet:

- **A scalar `winner:` target crashes instead of being refused.** `winner:
  highest <var>` names the score variable a game is ranked by, and the runtime
  builds its score dict with `dict(rs.get(target))` — which requires the target
  to be an INDEXED variable (`score[player]`, `score[team]`). A scalar target
  (`state { pot : Integer = 0 }` + `winner: highest pot`) type-checks and then
  dies with a bare `TypeError: 'int' object is not iterable` inside
  `driver.play_game` — a Python error, not a diagnostic, on a game the checker
  accepted. Run and confirmed 2026-07-25. The wall is a checker rule that a
  `winner:` target names an indexed state variable (and the matching
  `loser:`-style message); deferred only because no corpus game writes one, and
  it is a distinct rule from the returns KEYING this class otherwise covers
  (tests/test_openspiel_returns_keying.py).

- **A team-scored game's `winner` is a team index.** `GameResult.winner` is
  typed `Player | None` but is picked out of `scores`
  (`driver.play_game`: `pick(scores, …)`), and `scores` is keyed by the
  `winner:` target's own index domain — so in a team-scored game (bridge,
  spades, pinochle, tichu) the field holds a TEAM index wearing a player's type.
  Nothing reads it as a seat today: the OpenSpiel returns path maps scores
  through `team_of` on the target's declared index
  (`openspiel/replay._winner_target_is_team_keyed`) and never consults
  `winner`, and the characterization goldens only record it. So this is a
  mislabelling, not a wrong answer — but it is the same team-keys-are-not-seats
  confusion that silently paid the wrong seats before that structural read
  landed. Closing it means deciding what a team-scored `winner` should BE (the
  team, a representative seat, or every member) and retyping the field to say
  so; deferred because the answer is a small design question, not a bug, and
  moving it would move the characterization goldens.

- **Unvalidated `partnerships:` list contents.** An integer literal in any
  Player or Team *operand* position -- a subscript, a call argument, a `state`
  default, a scalar `:=`, an `as`/`turns`/`round`/`offer to`/`loser:` seat, a
  struct field, a variant payload -- is range-checked by construction: every
  coercion routes through one operand check (`typecheck._check_operand`), which
  bounds the literal against the seat count (`max_players`) or team count
  (`max_teams`), two-sided (a negative literal rejects too). The wall is closed
  by construction, not by enumerating sites, and pinned: no `assignable(...)`
  coercion in typecheck.py escapes the choke point
  (tests/test_operand_choke_point.py), and every position is a grid row
  (tests/test_player_literal_range.py). The ONE place a raw seat/team integer
  still escapes is the `partnerships:` declaration itself: `partnerships:
  [[0, 5]]` in a four-player game names a non-existent seat 5 (and each bracket's
  position is a team index), but those ints are parsed straight into
  `Game.partnerships` (`tuple[tuple[int, ...], ...]`) and reach the IR and
  deckcheck without ever becoming an operand expression, so `_check_operand`
  never sees them -- and NOTHING else validates their CONTENTS either. Three
  distinct malformations are all accepted silently, the worse kind of residual:
  an OUT-OF-RANGE seat (`partnerships: [[0, 2], [1, 5]]` in a four-player game
  type-checks AND plays to completion, the phantom seat 5 simply never matching),
  a DUPLICATE seat (`[[0, 0]]`), and a seat on MULTIPLE teams (`[[0, 1], [0, 2]]`
  -- seat 0 belongs to two partnerships). Only a NEGATIVE seat is caught, and
  only because the grammar's `INT` terminal has no `-`. The wall would be a
  resolve-time check that every partnership seat is `0 <= s < player_count`,
  appears at most once, and (the game defines it) the teams partition the seats;
  it is deferred because no corpus game writes a malformed partnership, and these
  are declaration integers, not the operand coercions the choke point closes.

- **An acting-player alias created by procedure expansion.** The wall on
  comparing the acting player against a second name for them (decisions.md
  "Naming the acting player twice") quantifies over one declaration body, and
  runs before `expand` splices procedure bodies into their call sites. A
  procedure body cannot read `actor` at all (`resolve._check_procedures`), so
  the pronoun cannot travel across the boundary; what survives is a body
  comparing two of its own parameters (`q is r`) that one call site supplies
  from the same seat — `run f(p, actor)` inside `for each player p`. That
  comparison is a tautology at THAT call site and meaningful at others, so
  catching it means either an interprocedural pass or re-running the sweep on
  the expanded tree; both are more machinery than one exotic shape has earned.
  Recorded, not walled — the grid's ledger
  (`tests/test_actor_alias_comparison.py`) names it as its one residual.

- **Latent holes around the struct paths.** Each was found by adversarial
  review of the lookup-miss walls, each is reachable only through constructs no
  corpus game uses, and each is recorded rather than fixed because closing them
  is a separate change with its own domain. (a) An OPTIONAL struct receiver
  (`r : R?`) disables the struct walls: `r.flag` is accepted whatever `flag`
  is, because the optional wrapper is not a `TStruct` and the field checks look
  through nothing. (b) `_check_produces`
  does not check a produced payload against the variant case's declared payload
  types, so a `produce won(...)` with a wrong-typed argument is accepted.
  (c) The declaration-DAG performance test asserts termination but not time,
  so restoring the exponential `_type_key` — a 620x regression measured during
  review — still passes it; a time bound belongs on that test.

- **Position domains in declared-type positions.** A declared position
  domain (`positions { slot : 1..4 }`) is a legal annotation on a move
  parameter, a procedure-shaped parameter list, a function parameter, and both
  payload positions, where it types as the integer member of the range. It is
  NOT legal as a state-variable type or a struct-field type, and whether it
  should be is undecided rather than settled: semantically such a value is an
  Integer with a declared range (or, for a board's `cell`, a TCell), but no
  game wants one, so the grid (`tests/test_type_name_positions.py`) records
  the cells as residual instead of guessing an expected value nobody has
  chosen. The wall is loud -- the name is rejected, never silently accepted --
  though the message currently spells it `unknown type '<name>'`; naming the
  sharper reason (a position domain is not a declared type in this slot) is a
  message-quality residual, and the grid asserts admit-vs-reject only, not the
  message text.

- **The index position admits different domains per host.** One grammar
  nonterminal (`index`) is reached from three hosts, and they disagree: a ZONE
  family may be indexed by a declared position domain (`pile[slot] :
  Cascade<slot>`), a STATE variable may not (`claimed[slot] : Integer` is
  rejected as "not an indexable role"), and a `let` index is a binder with no
  domain check at all. The exclusion is systematic across two passes —
  `typecheck` gives zone families an explicit positions branch and indexed
  state variables none, and `role_type` raises rather than falling back — so
  relaxing resolve alone would produce a compiler-currency crash, not a silent
  miskey. The divergence is defensible; what is not is that the state-index
  diagnostic speaks only of value domains and never mentions position domains,
  so a designer who hits it is told the wrong thing. Found by the
  framing check over the type-name axes, and hit live while building
  `tests/fixtures/struct_positions_witness.cardlang`.

- **Zone-type names and role ids are not gridded.** The type-name grid covers
  DECLARED type names. Two neighbouring namespaces have their own registries,
  their own walls, and their own raggedness: zone type names (`Hand<player>`,
  walled against `LIBRARY_ZONE_TYPES`) and role/domain ids (the `player` in
  `hand[player]`, `for each player`, walled against various role subsets). The
  framing check enumerated seven such positions. They are a different domain
  rather than a missing part of this one, and gridding them is its own change.
  One member is worth naming: `resolve` reads `ZONE_PROJECTIONS` with a bare
  subscript where the sibling `ZONE_CONTENT` read raises an `AssertionError`
  naming the drift — reachable only if the two zone registries disagree, but
  it would surface as a `KeyError` rather than as the divergence it is.

- **Registry-module manifest for the framing check**
  (surface-totality-audit, Step 1). The fresh-context framing check's
  input set — "the registry modules" — has no defining site in code:
  registries are spread across `cardlang/domains.py`,
  `cardlang/runtime/values.py`, `cardlang/runtime/reads.py`,
  `cardlang/stdlib/signatures.py`, `cardlang/stdlib/zones.py`, and
  author-side selection would reintroduce the exact framing blind spot
  the check exists to remove. Deliverable: a checked-in manifest pinned
  by a scrape test over module-level registry constants (UPPERCASE
  container assignments), so a new registry module fails the pin until
  listed or excluded with a reason. The interim wall, stated in the
  skill: the framing subagent receives the entire `cardlang/` package —
  completeness by superset, never by judgment.

  The same manifest has a second client: the registry→dispatcher pins
  (`tests/test_signatures.py`) reconcile each stdlib name set with the
  runtime dispatcher that serves it, but which dispatcher serves which
  registry is not derivable from code, so each pin names its own
  registry and a NEW name set acquires no pin until someone writes one.
  The manifest's scrape would supply the missing axis — enumerate the
  registries, require a pin or a recorded exclusion per entry. Interim
  wall: every dispatcher ends in a loud `case _`, so an unserved name
  raises at first use rather than resolving to nothing. This is the
  hand-listed-axis shape recorded under "Grid the classes that are
  grid-shaped but ungridded" below, in its name-source form: each pin
  derives from its own registry, and nothing enumerates the pairings.

- **Unresolvable identifiers in prose.** Nothing checks that a backticked
  name in a docstring or a `docs/` page still refers to something real, so
  one naming a deleted or never-built construct reads as authoritative
  indefinitely: `ZONE_METHODS` sat in
  [design-notes/domain-map.md](design-notes/domain-map.md) as a
  registry→dispatcher pin for a registry that existed in no module, beside
  a `zone.method(...)` query surface that decisions.md "The expression
  register" rules out. Both were prose contradicting the spec, invisible
  because prose has no compiler. Deliverable: a scrape over backticked
  UPPERCASE identifiers in docstrings and `docs/`, asserting each resolves
  in `cardlang/` or sits on a declared exception list with a reason —
  the same shape as the registry-module manifest above, one currency over.
  The exception list is load-bearing, not a convenience: prose
  legitimately names constructs that do not exist yet (a deferred
  `CellMismatch` before it landed), and a scrape that cannot express
  "named deliberately, not yet built" would push authors toward deleting
  the forward reference — losing the record the deferral exists to keep.
  Interim wall: doctrine, not mechanism — decisions.md "Closed-domain
  completeness" states the authoring rule (prose names the registry, never
  the cardinality) that keeps new instances out. Naming that honestly
  matters: an authoring rule is enforced by review, which is exactly the
  enforcement this class already escaped, so it bounds new drift rather
  than the existing kind.

- **Grid the classes that are grid-shaped but ungridded.** The general
  finding from six review rounds across PRs #79 and #80: every defect found
  was a partial enumeration of a closed class, and none was a novel bug. The
  classes that HAD a derived grid caught their own defects at write time; the
  ones without needed a reviewer. Two shapes recur often enough to name, so a
  change touching either should arrive gridded rather than waiting to be
  reviewed:

  (a) **A wall that reserves names from a namespace.** Its domain is "every
  source of names this namespace must not collide with", and those sources
  accumulate silently. `_resolve_positions`'s `taken` set now unions three
  (built-in domain ids, `KNOWN_TYPE_NAMES`, the game's own `type`
  declarations) — the third was added only after review found `positions
  { R : 1..4 }` beside `type R` silently reading the struct as an Integer.
  The reconciliation sweep in `tests/test_positions.py` derives from each
  source, but nothing enumerates the SOURCES, so a fourth would be missed the
  same way.

  (b) **A type rule applied across type shapes.** The domain is relation x
  shape, and the shape axis is the `Type` union's CONTAINER constructors, not
  a hand-picked few. `tests/test_permissive_top.py` grids the nominal-struct
  rule over {unify, assignable} x {bare, optional, collection} — and that
  wrapper axis is itself hand-listed, which is the defect it exists to catch,
  one level up. The union has more containers than three, and one is a live
  uncovered cell: two `TVariant` of the same name whose payload snapshots
  disagree compare UNEQUAL, exactly as bare structs did before the nominal
  rule (`unify` returns None, `assignable` returns False). Unreachable today
  only because `variant_registry` is built once from the settled struct
  registry, so both sides always carry the same snapshot — an accident of
  call order, not a wall. `TCollection`'s KEY also carries a `Type` and is
  handled by a different rule (deliberately ignored by `assignable`, merged
  stickily by `unify`), so the axis needs the key cell classified rather than
  assumed.

  Deliverable: derive the shape axis from the `Type` union in code, close or
  wall the `TVariant` cell, and enumerate the name-source axis for (a).

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

  These are one class, not separate accidents: a procedure body may not hold a statement
  whose VALIDITY depends on where it sits, because the checker sees the body once, at
  its declaration, and the spliced copies are never re-checked (expansion runs after
  typecheck, which is what makes the parameter types enforceable). The class is closed
  by enumerating the position-dependent CHECKS — `_check_outcome_scope`,
  `_check_single_outcome_consumer`, `_check_misplaced_produce`, and outcome binding —
  rather than by intuition. The other position-sensitive passes, deck-capacity and
  the OpenSpiel action space, both run after expansion and see the real tree.

  Note what is NOT on this list: argument capture, actor capture, and a body
  binding leaking into the caller. Those were walled in the first implementation
  and are now impossible by construction — arguments are evaluated once, by value,
  in the caller's context, and the body runs in a block (decisions.md "Named
  procedures").

- **The permissive top on a MERGE failure.** The lookup-miss population of
  `Any` is closed — a lookup whose domain is closed raises rather than
  falling back to the top, and every declared type name is validated where it is
  declared (decisions.md, "The permissive top and the lookup-miss walls";
  ledger `tests/test_permissive_top.py`). A second, distinct population
  remains: when `unify` cannot reconcile two types, the result falls to the top
  rather than being rejected. `if c then 1 else hearts` and a mixed
  `[1, hearts]` list literal each type as the top and go permissive from
  there. This is not a missed lookup — both branch types are known — so it
  wants a WALL (the branches of a conditional, and the elements of a list
  literal, must have a common type), not a raise. It is deferred rather than
  written because the wall is a new rejection over an existing surface, which
  needs its own misuse-probe pass over every position a conditional
  expression can appear in. The narrower sibling: `max`/`min` comprehensions
  type as the top although `_check_agg_body` already forces an Integer body, so
  their result type can simply be tightened to `Integer` — a precision fix,
  no new rejection.

- **The Card-vocabulary check is still offer-sited, and double-reports.**
  `_check_move_params` (the move-parameter DOMAIN gate) now runs once per
  DECLARED move type, because a parameter is a property of the declaration.
  Its sibling `_check_card_vocabulary` was left at the `offer` / `round
  offering` call sites, so the halves of one class now sit at two layers.
  The visible cost: "this game declares no `hand[player]`" is a whole-GAME
  fact, so a Card-parameterized move named by N offers reports it N times for
  one defect. Moving it wholesale is wrong, which is why this is deferred
  rather than done — the check is two rules wearing one name. "No
  `hand[player]` to enumerate a Card over" belongs to the declaration; "more
  than one Card-parameterized move in this vocabulary" is genuinely a property
  OF the vocabulary and must stay where it is. Splitting them is the work.
  Pre-existing (the duplication predates the move-parameter change); found by
  the adversarial pass over that change.

- **Struct and function registries are solved by a bounded fixpoint.** Not
  deferred work — recorded because the shape is a trap worth knowing before
  touching `typecheck.struct_and_function_registries`. The two registries
  depend on each other in both directions and at arbitrary depth: a derived
  field's body may call a function, a function's parameters and body may
  mention a struct, and a function's RETURN type may therefore depend on a
  derived field which depends on another function. No fixed pass count is
  enough; a chain of N needs N rounds. Two fixed-pass versions each shipped a
  defect that an adversarial probe caught and a fully green suite did not:
  (a) `TStruct` compares STRUCTURALLY, so two registries disagreeing about one
  derived field produced two unequal copies of one nominal type — diagnostics
  reading `expects R, got R` at eight sites, and well-typed programs made
  unwritable. Closed by comparing structs NOMINALLY (by name) in
  `types.assignable`/`unify`, which is the correct semantics for a declared
  type: identity belongs to the name, and the fields are what the name
  resolves to. (b) A derived field whose type flowed through a function return
  stayed frozen at the permissive top, so `score[p] := s.flag` accepted a
  Boolean into an Integer-declared state variable — a LOST WALL, not an
  imprecision. Closed by the fixpoint. (c) A struct's field map holds a
  SNAPSHOT of each struct-typed field, and reading those snapshots made walls
  decay with traversal depth — a recursive type has no finite unrolled form,
  so `r.copy.copy.copy.flag` reached the permissive top. Closed by resolving
  struct-typed reads through the REGISTRY by name, at both the receiver and
  the result; a bounded comparison depth is NOT a fix, because the path stays
  observable past any cutoff, and it is exponential on a declaration DAG
  besides. (d) The same ambient-environment defect appeared twice, because
  fixing the pipeline's path stopped the fix from exercising `env_from_game`'s
  default branch — there is now ONE construction path, and adding a second is
  the mistake to avoid. A further trap for anyone adding a pass: intermediate
  rounds must report into a scratch `DiagnosticBag`, or every function-body
  diagnostic is multiplied by the round count. The ledger is
  `tests/test_permissive_top.py`.

- **The corpus has no witness for user `type` declarations.** Not a design
  question — a coverage hole, and the highest-value one this file records.
  Every defect listed in the entry above was found by review or adversarial
  probe, never by the suite, and they share one cause: no game in
  `docs/games/` declares a `type` at all, so the entire struct/function
  subsystem is exercised only by unit tests written by whoever last changed
  it. A green suite is therefore not evidence about that code, which is
  exactly the "vacuously green" class decisions.md ranks alongside
  accepted-but-ignored. The fix is corpus-first as usual: a game whose scoring
  or contract state genuinely wants a record type (the Bridge/Oh Hell family's
  `{ tricks_required, tricks_actual } derived { made }` shape is the obvious
  candidate, and already appears in the test fixtures) would put derived
  fields, struct-typed state, and struct-typed function parameters on the
  playout and golden paths. Until then, treat changes under
  `struct_and_function_registries` as unverified by the suite and probe them
  adversarially by hand.

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

- **A `requires` type typo is reported on the game's `uses` line, not the
  library's.** A library's `requires { x : type_name }` is the one type-name
  position not gridded by `tests/test_type_name_positions.py` — it cannot appear
  in a standalone game, so that grid carves it out. Its type is validated
  transitively and loudly: the including game must declare the same name, and
  `_check_requires` rejects a require type that does not match the game's
  declaration, naming the library and quoting the type — so a library-side typo
  (`Integar`) is surfaced, never silently dropped. What is imperfect is only the
  SPAN: the diagnostic lands on the game's `uses` line, so a library author
  fixing their own typo is pointed at a file they did not write. Closing it is
  one library-currency check in `_check_requires`
  (`base_of(req.type_name) not in KNOWN_TYPE_NAMES`, reported in the library
  file, and suppressing the mirror mismatch for that name so it is not reported
  twice). Deferred, not silent — the current diagnostic is loud and names the
  library, so this is a precision fix, not a hole.

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
  `runtime/phases.py`'s `compute_active_rules` shape. Narrower gaps are
  accepted, all unexercised by the corpus (no game uses `-X` at all): the
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
  (`cardlang/runtime/stdlib.py`) instead of erroring at resolve time. No
  corpus game exercises it — every `docs/games/*.cardlang` ranking today
  happens to be a full permutation of its deck — so the residual is pinned
  by a witness fixture instead:
  `tests/test_ranking_wall.py::test_a_rank_outside_a_partial_ranking_fails_in_the_runtime_currency`,
  an `xfail(strict=True, raises=KeyError)`. Giving that lookup the runtime's
  typed currency turns the xfail into an unexpected pass, which fails the
  build and retires this entry in the same change.

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
  Klondike and FreeCell are the corpus anchors). The position design's
  remaining cells stay deferred, each behind a wall:
  - `for each <INTEGER position>` iteration and position-indexed `state`
    stores — both rejected at resolve with diagnostics
    (tests/rejections/positions_for_each,
    positions_state_indexed_by_position); no corpus game addresses columns
    by loop or keeps per-column scalar state (guards + parameters cover
    both games). Implement when a game needs one. Iteration over a board's
    NAMED-MEMBER domain (`for each cell`) is live from rung 2 —
    breakthrough's fixed setup array is the witness that lifted it — and
    the named-member/integer split is exactly what the remaining wall turns
    on (tests/test_cell_iteration.py). A collection-restricted
    `for each cell c in <expr>` form stays grammatically inexpressible: the
    bare role form plus a membership guard (`if c in home(actor)`) covers
    the setup witness. (Quantification over a position domain — `any cell
    where …`, `all columns where …`, `number of cells where …`, and the
    `any line in …`/`all cells in …` collection forms — is a separate
    surface and is live: tests/test_cell_queries.py.)
  - The collection-quantifier noun is fixed to `{cell, line}` at rung 1
    (`cardlang/resolve.py::_COLLECTION_NOUNS`); a future collection-typed
    domain (a region, a hand of pieces) gets no `any <noun> in <expr>
    where …` form until a witness needs one.
  - The collection register has only the boolean `any`/`all` shapes.
    `number of <noun> in <expr> where …` (the collection twin of `number of
    cells where …`) and a bare set-materializing `<noun>s in <expr> where
    …` (the collection twin of `cards in <zone> where …`) are both
    grammatically inexpressible — no production admits `in` after the
    `number of`/bare forms. Numeric aggregation over a line/cell collection
    (`sum of … over cells in <line> where …`) is likewise inexpressible:
    `agg_query` stays fixed to `"sum" "of" expr "over" "cards" "in"
    zone_expr`, never extended to a position collection. Implement when a
    game needs a cell/line count or sum, not a boolean test
    (tests/rejections/cell_count_in_collection_not_admitted).
  - A literal-`k` `lines(k)` call is bounds-checked statically (resolve,
    against the board's own span); a NON-literal `k` (a variable or
    computed expression) has no static check and surfaces an out-of-range
    value as a runtime `RuntimeError` instead
    (`cardlang/runtime/stdlib.py::_lines`). No rung-1 game computes `k`.
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
  - **Cell CONSTANTS are not expression surface.** A `board:` clause mints
    a named-member position domain (`cell`, string members like `a1`), used
    as a zone index and a move parameter; but a bare `a1` in an expression
    is an unknown-name diagnostic, not a cell literal (integer position
    domains have no such gap — an integer literal already denotes an integer
    member). No rung-1 game names a specific cell (parameters and the
    cell/line quantifiers cover placement and win tests); the witness is a
    game whose setup or rules name individual cells (breakthrough). Until
    then it is grammatically un-namable, walled by the name resolver, not
    accepted-and-dropped (tests/test_board_clause.py names this residual).

- **Piece-flavored games — content vocabulary lands; the rule system is
  deferred.** `pieces:` selects a piece-flavored component set (`cardlang/
  runtime/values.py`, `COMPONENT_SETS`), and content-kind agreement is a
  first-class wall: a piece set's own vocabulary binds (the `x`/`o`/`mark`
  axis values, the `side`/`kind` fields, the `piece`/`pieces` movement noun
  and filter binder), and a minimal piece game runs a playout through the
  driver (`component_deck` generalizes the old card-only `DECKS` read;
  `axis_attributes` maps `piece.side` -> `Card.suit`). Card vocabulary in a
  piece game is rejected NAMING THE KIND at the layer that owns it: the
  movement/reveal noun, `.suit`/`.rank` field access, the card-query and
  aggregation forms, `ranking:` (both the enumeration and the convention
  form) and `trump:`, the `suit`/`rank` quantifier and iteration roles, the
  Suit/Suit?/Rank/Card move-parameter domains, the deck-reading stdlib calls
  (`DECK_ONLY_CALL_FUNCS`), and card literals. The flagship ledger is
  tests/test_piece_content_walls.py; the clause structure is
  tests/test_game_clause_walls.py.

  Deferred to a later rung of the board-topology ladder
  ([design-notes/board-topology.md](design-notes/board-topology.md)), and NOT
  yet flavor-walled: (a) a card-content TYPE annotation (`Suit`/`Rank`/
  `Card`) at a declaration site is accepted at the annotation in BOTH flavors
  (the name is a known type); loudness then comes from two places, not a
  silent gap. A state var carries an initializer, and the state-default type
  pass (`typecheck.py` `_check_state_default_type`) rejects a piece value
  under a card-typed var; the initializer-less slots (struct field, function
  parameter, variant case) accept the annotation and fail at every USE in a
  piece game (a card value never resolves in a piece namespace). (b) the
  trick-taking and rule-obligation machinery — a per-round `round ... trump`,
  the `climb`/`combinations`/`follows` forms, `demands:`/`exempts:`/`actions
  where` card predicates, an outcome-function name, and a suit argument to a
  rule template — is card-oriented and reached only through the rule system,
  which a rung-1 board game does not use; a piece game touching it degrades
  through the existing card-zone / name-resolution / deck-only-call walls.
  (c) a piece game that `uses` a family library is unwitnessed (no piece game
  imports one today) and not flavor-walled: the libraries are card-oriented,
  and a piece game importing one degrades loudly through the library's
  `requires` state contract (the missing card-shaped state is reported), not
  through a flavor wall. All get a declaration-site / rule-system / import
  wall naming the kind when a piece game needs the surface.

- **Zone capacity — the `Point` row deferred.** `ZONE_CAPACITY`
  (`cardlang/stdlib/zones.py`) is a total registry column over
  `LIBRARY_ZONE_TYPES`: `Cell` is capacity 1, every other library zone type
  is unbounded, enforced as a runtime wall in the movement executor. The
  `Point` row (an unbounded-height stack) waits on its witness —
  backgammon, the board-topology ladder's chance rung
  ([design-notes/board-topology.md](design-notes/board-topology.md)).

- **Board topology — later-rung surface walled at rung 1.** Rung 1 landed
  the board declaration, the `cell` domain, the cell/line query register,
  `Cell` capacity, and `Card` as the deck specialization of `Piece`
  ([decisions.md](decisions.md) "Boards and cells", "Component sets: cards
  and pieces", "Zone capacity"; tic-tac-toe is the corpus witness). The
  ladder's later rungs
  ([design-notes/board-topology.md](design-notes/board-topology.md)) are
  walled until their witnesses:
  - **Movement-direction domains** — a piece's board orientation, the
    forward/back a draughts man or breakthrough pawn advances along
    (distinct from the seat-relative turn-order `direction:` and the
    passing `Direction` enum, which are unchanged). No rung-1 game moves
    along a board direction, and no board-direction construct exists in the
    surface, so one is un-namable — grammatically inexpressible, not
    accepted-and-dropped. Witness: breakthrough.
  - **The `HiddenCell` zone-type row** — identity to owner, trivial to
    others (a board cell whose very occupancy is the secret, pairing with
    `Cell` as `HiddenStack` pairs with `Cascade`). Absent from
    `LIBRARY_ZONE_TYPES` (`cardlang/stdlib/zones.py`) until its witness; a
    game cannot select a type the registry does not hold. Witness:
    battleship.
  - **Double-indexed zone families** (`ocean[player][cell]` — a board per
    player, where the positions-are-unowned wall gains its amendment that a
    compound index may carry an owner key). Grammatically inexpressible:
    `zone_decl` admits a single `[index]` only
    (`cardlang/grammar/cardlang.lark`), so a second index does not parse.
    Witness: battleship.
  - **In-file board syntax** — a board declared inline (its cells,
    relations, regions) rather than selected from the closed `BOARDS`
    registry, for a Catan-class map no family generates. Grammatically
    inexpressible: the `board:` clause names a registry family with integer
    arguments only, so an inline board does not parse. Witness: a
    Catan-class game.
  - **Adapter root-chance collapse for chance-free games.** A game the
    kernel proves consumes no randomness (tic-tac-toe: no `shuffle`, a
    fixed piece seeding) still compiles to an OpenSpiel tree whose root is a
    chance node sampling a seed — every branch provably identical
    (`tests/openspiel_ready/test_tic_tac_toe.py`'s seed-degeneracy proof).
    Collapsing that degenerate node for a proven-chance-free game is the
    ladder's stage-3 chance workstream, not an info-set gap: the proof
    module records the honest caveat and defers the collapse here.
  - **A decider with men but no legal move.** Breakthrough's `until`
    predicate names the two termini its oracle names (someone has won,
    someone has no men); it does not name "the player to move has men but
    every step is blocked". OpenSpiel's `breakthrough` leaves that state
    non-terminal with an empty action list; the DSL fires the
    no-implicit-actions wall instead
    (`cardlang/runtime/execute.py::_offer`), so the two are broken
    differently rather than agreeing, and no differential walk can reach the
    disagreement. It did not arise in 400 random games — the smallest offer
    ever made was nine steps
    (`tests/test_playout_breakthrough.py`) — so no machinery is built for an
    unreached state, and the game says nothing it cannot back. The forcing
    witness is a game whose rules make blocking ordinary:
    [english-draughts](games/_candidates.md#english-draughts), where a
    player with no move LOSES, and
    [nine-mens-morris](games/_candidates.md#nine-mens-morris), where a
    blocked player is a real position.

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

- **No automated `.md` / `.cardlang` byte-identity check for `docs/games/`
  twins.** Each corpus game is a `.cardlang` formal file plus a `.md`
  readable twin that embeds the same source in a fenced block; the twin's
  block and the formal file are kept identical by review, not by a test.
  `tests/test_doc_snippets.py` pipeline-checks the fenced blocks in the
  three prose specs (decisions/library/model), and the corpus proof
  modules run the `.cardlang` files, but nothing asserts a game's `.md`
  block matches its sibling `.cardlang` byte-for-byte — a stale twin would
  pass CI. The check is cheap (extract the game block, diff against the
  sibling file) and unwritten; recorded so the manual discipline is not
  silent.

- **Some `.md` twins carry no DSL block, so the type-checker corpus net
  skips them.** `tests/test_typecheck_corpus.py` holds every
  `docs/games/*.md` twin that carries a fenced block to the same bar as the
  `.cardlang` files, which is what keeps a twin from rotting into obsolete
  syntax unnoticed (the `hearts.md` case that motivated the gate). The
  twins carrying no block at all are skipped rather than failed. Skipping
  is right — there is nothing to check — but the set is a coverage hole
  that once grew silently behind a hand-written count in prose, so it is
  now pinned by name in that module (`PROSE_ONLY_TWINS`): an addition has
  to be made deliberately, and a twin that gains a block has to be
  removed. Closing the hole means giving those twins DSL blocks, which is
  corpus work, not checker work.

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
  That leniency is now BOUNDED: an out-of-range integer literal (`hand[9]` in a
  four-player game) is rejected by the role-literal range wall
  (typecheck `_check_role_literal`, reached through the operand choke point
  `_check_operand`, tests/test_player_literal_range.py), so only an in-range
  literal coerces, and a computed out-of-range index (`hand[0 + 9]`) is left to
  the runtime key wall. What stays deferred is the
  orthogonal question this residual owns: whether a literal should coerce AT
  ALL, or a zone-family index be required to be exactly Player/Team-typed.
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
  already green. The **grammar surface does not follow** — a 5th row would type,
  iterate, bind and enumerate correctly and still have no dedicated `any <noun>
  where` production. Since the position-domain / cell-line query register (Task
  7, decisions.md "Boards and cells") this is no longer a syntax error, though:
  `any QNOUN where` now parses ANY noun, but for a *different* registry
  (`game.positions`, gating the board/positional-cell forms — not
  `cardlang/domains.py`). A 5th DOMAINS row's `any <noun> where` therefore
  parses, then is rejected by `resolve.py::_check_domain_query` as an "unknown
  position domain" — a diagnostic naming the wrong universe, not the DOMAINS
  rows it was actually competing with. Still loud (a resolve diagnostic, not a
  silent acceptance), so still a scope limit rather than a defect — but until
  the productions are generated from the registry, "a new domain registers
  itself" stays true of the semantics and false of the syntax, and the
  false-of-the-syntax failure is now a misleading diagnostic rather than a
  parse error. Ledger: tests/test_domain_registry.py.

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

- **Semantic invariance: suit relabeling (T4) is deferred.** `tests/metamorphic/` (design plan:
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
  `repeat until`, a short trick). All are recorded, not fixed, in
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

- **Primitive sidecars: stages 2-5 of the migration, and the one remaining
  trace emitter.** Stage 1
  ([design-notes/primitive-sidecars.md](design-notes/primitive-sidecars.md),
  the execution plan in §5) evicted the two pure trace emitters from the
  stdlib registry; the harness derives their facts from observation events
  (`tests/playout_trace.py`, grid and ledger in
  `tests/test_trace_emitter_eviction.py`). Stage 2 is likewise done: all
  fifteen game modules take values rather than `Ctx`, via the binder
  (`cardlang/runtime/sidecar.py`), pinned by the crossed wall
  (`tests/test_primitive_narrowing.py`) with nothing excused. Remaining:
  the `primitives { }` declaration block (stage 3) and co-location
  (stage 4), per the design note's §5.

  Three residuals ride until their own steps. `coup_game_summary` is a
  third dead-`let` trace emitter by call shape, still registered because
  its `coup_game` payload recomputes conservation totals from engine state
  (coins, treasury, zone censuses) rather than from movement views —
  reproducing it at the harness is its own design step, not a mechanical
  repeat of stage 1. The three auction outcomes (`bridge_`/`pinochle_`/
  `tarot_auction_outcome`) are implemented inside `cardlang/runtime/
  stdlib.py`, so the game-module wall does not reach them; stage 4
  (co-location) owns their move. And both bundles the binder hands over
  are module-granular, so a primitive can still see a declared name it
  does not need — the per-primitive `reads` clause of stage 3 is what
  closes that, and it also removes the cost of materializing a whole row
  per call.

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
   Coup so far; both composed the closed vocabulary without needing a
   declaration).

5. **Sharpen the completeness machinery where it is still hand-listed** —
   trigger-based, not blocking. The doctrine (decisions.md "Closed-domain
   completeness", the `surface-totality-audit` and `cardlang-planning`
   skills) is in place and demonstrably works: across six review rounds on
   PRs #79 and #80 every defect was a partial enumeration of a closed class
   and none was a novel bug, and the classes with a derived grid caught
   their own defects while the ungridded ones needed a reviewer. What
   remains is coverage of the machine itself, recorded above under "Grid
   the classes that are grid-shaped but ungridded": derive the type-shape
   axis from the `Type` union rather than hand-listing wrappers (which
   leaves `TVariant` a live uncovered cell, unreachable today only by call
   order), enumerate the name-source axis behind name-reservation walls,
   and build the registry-module manifest the framing check's input set
   needs. The standing trigger: a change touching a name-reservation wall
   or a type rule applied across shapes arrives gridded, rather than
   waiting for review to find the member nobody listed.

6. **Defer Tier 5 cosmetic questions** until a real preference emerges
   from corpus pressure.
