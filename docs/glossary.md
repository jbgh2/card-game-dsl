# Glossary

The glossary of OpenRegel's shared language — one entry per concept, one spelling per
concept. (DDD calls this the "ubiquitous language"; this file is named for the word
people can actually remember — "vocabulary" belongs to the DSL itself; see its entry.)
`principles.md` already holds this rule for the DSL surface ("A second spelling is a
defect"); this file extends it to the implementation. When code, docs, or diagnostics
need a word for one of these concepts, use the term in the left column. When a word
appears in the reserved-words table below, do not use it unqualified.

Three usage rules bind every term in this file:

1. **Full phrase, always.** A multi-word term is never truncated — Owner Guard, not
   "owner"; truncation is how overloads regrow.
2. **Title Case in prose.** A glossary term is capitalized wherever it appears in
   comments, docstrings, docs, and issues — the capital marks "this is a Name, not
   two English words" and distinguishes the term sense from the ordinary word
   (the Author of a failure vs the author of a paper). Code identifiers keep their
   language's casing. (This is also DDD's own convention for ubiquitous-language
   terms.) Body prose is recased term-by-term as entries split into per-term files.
3. **One name, one shape.** A spelling shared across sibling modules claims
   identical meaning, return shape included — two functions named `deck_suits`
   returning an ordered tuple in one module and a frozenset in another is the
   witness defect.

Companion: `design-notes/glossary-findings.md` records where current code diverges
from this file, with evidence. Divergences below are marked (→ F-n).

Definitions of the game model itself stay in `model.md`; bounded contexts stay in
`design-notes/domain-map.md`. This file is the *naming* authority: what each thing is
called, and what each name may mean.

---

## Using this vocabulary

Two full phrases and a test-freeze word carry the whole taxonomy. Timing (static vs runtime) is never part
of a term — it's visible from where a guard lives, and both roles exist at both times.
Per the preamble rules: always the full phrase, always Title Case — never "owner"
(that's the zone-family owner) or "shadow". Bare "guard" is the family noun in prose
only; "check" stays the fully generic word for any validation. Never names for a guard, and none of them a retired spelling: *wall*, *backstop*,
*gate*, *sweep*, *twin*, *mirror*, *copy*, *sibling*. Every one has a life of its
own here — Quoridor's walls delete edges, a `max_length` backstop is a real
termination bound, a game's readable twin is its prose counterpart, the merge gate
is CI, a class gets swept. So none takes a `retired_spellings` entry, and none may
be rewritten out of those uses; what is retired is the guard sense alone. Freeing the word:
`MoveTypeDef.guard` → `.when` (a convergence rename the audit already mandated) rides
the migration.

These words currently carry 4–9 meanings each (see findings). In new code, comments,
docs, and diagnostics, always qualify them:

Interop is an anti-corruption layer (`domain-map.md`), so OpenSpiel's words legitimately
differ from ours. The translation is part of the vocabulary — keep it explicit:
The encoding's flattened move-type × parameter-domain cross-product is the
**offering block**. Inside `cardlang/openspiel/`,
OpenSpiel's senses of `action`, `player`, `state`, `observation` win; outside it,
ours do.

How work flows through agents and the operator. Mechanics live in `harness.md`;
these entries own the names.

## The game model and the runtime

| Term | Definition | Home |
|---|---|---|
| [Actor](glossary/actor.md) | The seat currently acting: the `actor` pronoun, `as` rebinding. Prefer "actor" over "current player" / "decider" / "acting seat"; `Ctx.current_player` is the surviving old spelling and converges when-touched. | `state.Ctx` |
| [Builtins](glossary/builtins.md) | Generic native functions the language ships: declared in `cardlang/builtins/` (`BUILTIN_*`), implemented in `runtime/builtins.py`. Distinct from the **stdlib** (written in the language — functions migrate builtins→stdlib as expressibility grows) and from **Primitives** (game-local). | `runtime/builtins.py` |
| [Candidate](glossary/candidate.md) | One concrete legal option at a decision point: a `(move type, bound parameter)` pair or a card/subset. The thing rules filter and the encoding numbers. Prefer over "option"/"legal move"/"concrete move" (→ F-19). | `mechanics.py` |
| [Card / Piece](glossary/card-piece.md) | The individuated content of zones; a card is the deck specialization of a piece (`model.md`). Runtime represents both as `Card` (→ F-16). | `values.Card` |
| [Card Points](glossary/card-points.md) | The per-rank points a game assigns its cards, declared by the game's `card_points { }` clause (rank-keyed rows, optional `else:` row; unlisted ranks read 0) and read by the `card_points(card)` Builtin and the driver's card-point census. One source — a deck carries composition only, never points. Never bare "value(s)" (reserved). | `n.CardPointsTable` |
| [Chooser](glossary/chooser.md) | The decision seam: the callable that resolves a player choice. A **decision point** is one call site of it in the interpreter (currently 7, unnamed — → F-20) — the *static* concept; the *dynamic* occurrence (a game state where a seat must choose) is a decision node, one of the [[game-tree-node-kinds]]. | `state.Chooser` |
| [Component Set](glossary/component-set.md) | The pack a game selects with `cards:`/`pieces:` — either flavor. A **deck** is specifically the card-flavored component set. `Game.deck` currently holds either (→ F-16). | `values.ComponentSet` |
| [Context](glossary/context.md) | `Ctx`: the immutable evaluation context threaded through the interpreter (actor, locals, pronoun bindings, chooser, tracer). | `state.py` |
| [Form](glossary/form.md) | A round form's hook bundle (`TrickForm` / `AuctionForm` / `ClimbForm`) behind the `DecisionForm` protocol. Prefer "form" over "mechanic"; the accumulator dict is the [[round-state]]. `turns` is a form too (decisions.md, "The `turns` form") but not a ROUND form — the turn loop beneath the round family, its own statement, running no hook bundle and never reaching `run_decision_round`. So "form" alone means a round form; qualify when `turns` is in scope. | `mechanics.py` |
| [Game](glossary/game.md) | The root unit: one `game { }` plus its supporting definitions. Not "program", "spec", or "source" except when meaning the file/text itself. | `n.Game` |
| [Hand](glossary/hand.md) | One deal-to-scoring cycle of a game (`skip to next hand`, `hands_played`) — one pass through the [[hand-loop]], distinct from the *hand zone*; qualify either when ambiguity is possible. The loop itself has no structural marker in the language (→ F-6). | `driver.py` |
| [Hand Loop](glossary/hand-loop.md) | The repetition a game's hands are iterations of — what `skip to next hand` advances to the next pass of, and what deckcheck's per-hand capacity window is measured over. One pass through it is a [[hand]]; the loop is the construct, the hand is the cycle. The language never declares it: `SkipToNextHand` continues the enclosing `repeat until`, and `hands_played` counts phases literally named `scoring`, so a game naming its scoring phase otherwise reports none (→ F-6). | `driver.py` |
| [Instantiate Lesson](glossary/instantiate-lesson.md) | The standing rule that the language keeps no escape hatch to a lower-level API: a hand-written mechanic bypasses info-set derivation, so any future hatch is info-set *debt* against the OpenSpiel target rather than a finished solution. Named for the deleted `instantiate` construct, which handed a game Python the kernel could not see; the corpus proved the kernel holds every mechanic without it. Cited by name where a new construct has to show which side of it the construct falls on. | `principles.md` |
| [Kernel Tables](glossary/kernel-tables.md) | The kernel's registry data: zone types + projections + capacities, board families, round-state fields, move types, enum namespaces — one module each under `stdlib/`, and everything there except `rules.cardlang` and its loader, which are the [[stdlib]] proper. Not library, not builtins — engine spec data, staged toward `cardlang/kernel/` at the second-family extraction (issue #203). | `stdlib/*.py` (interim) |
| [Library](glossary/library.md) | A family library: a `library { }` file a game `uses`. The stdlib rules fragment is *not* a library. | `n.Library` |
| [Loser](glossary/loser.md) | The game-level `loser:` clause — a player expression. Asymmetric with `winner:` by design. | `n.Loser` |
| [Mode](glossary/mode.md) | A condition the game is in, existing to change which rules are active: entered by `transition_to`, body is configuration only (`active_rules:`, `transition_to:` — being in it *is* its behavior), and an empty mode is the terminal default: no delta, no exits. Modes are INDEPENDENT conditions, not an exclusive state machine: several may hold at once and their deltas stack. Each is exactly one side of one condition — the **before** side, which declares the transition, or the **after** side, which a sibling names; both-or-neither is rejected. The config-only class is grammar-owned. | `n.Mode` |
| [Move](glossary/move.md) | One played instance of a Move Type, bound to its Parameters. A Move may perform zero, one, or many Transfers: a pass is a Move with none, a card play one, a capture two. The struct is card-shaped today (`(card, actor)`); the concept already covers `step(from, to)` (→ F-16). | `state.Move` |
| [Move Type](glossary/move-type.md) | A named, parameterized player action with a `when:` guard and an effect. Keyword and term settled: with "move" owning the player-action family, `move_type` reads as compositional English; `action_type` would manufacture an Interop false friend. | `n.MoveTypeDef` |
| [Native Code](glossary/native-code.md) | Python the DSL can call, either half — a [[builtins]] (generic, ships with the language) or a [[primitive]] (game-local). The union noun: `CALL_FUNCS` is `BUILTIN_CALL_FUNCS | PRIMITIVE_CALL_FUNCS`, and a **native call** is a call into either, resolved by name against that union. Use it when the half genuinely does not matter; name the half when it does. Never "stdlib" for any of this — the [[stdlib]] is written in the language, not in Python. | `cardlang/builtins/` |
| [Observation Event](glossary/observation-event.md) | An event appended to a player's observation log (`chose`, `announce`, `move`, `reveal`). | `observe.py` |
| [Offering](glossary/offering.md) | The declared menu of moves a construct presents to a decider: `round offering [ ]`, an `offer` statement's list. Replaces every code use of "vocabulary"; the ActionSpace's flattened move-type x parameter-domain block is the **offering block**. Distinct from a phase's `legal_moves:`, which is availability, not presentation. Retired: `vocab block`, `auction vocabulary`. | `n.AuctionRound`, `n.Offer` |
| [Outcome](glossary/outcome.md) | The tagged result a decision construct yields: a phase's `-> outcome { }`, a `define`'s case set, an auction's result. Declared as an **outcome type** of **outcome cases**; carried as a `(tag, payloads)` value. This is the word's only meaning. The player a trick/climb yields is the **winner**. | `n.Phase`, `n.DefineDef` |
| [Phase](glossary/phase.md) | A step in the game's sequential program: phases run in declaration order, and a phase ends when its work completes (the sense MTG taught every designer). This is the keyword's sole meaning — the rule-swapping flavor is a **mode** (→ F-8). | `n.Phase` |
| [Player](glossary/player.md) | The participant occupying a seat. In today's engine seat and player coincide (`Player = int`); keep the two words distinct anyway — `domain-map.md` lists "seat vs agent identity" as a future forcing point. | `values.Player` |
| [Position Domain](glossary/position-domain.md) | An integer or named-member index domain from `positions { }` or minted by `board:` (`cell`). The board's other minted domain, `dir`, is NOT one: `board_domains.directions_of` is a sibling of `position_domains_of`, and `dir` never enters `Game.positions`. | `board_domains.py` |
| [Primitive](glossary/primitive.md) | Sanctioned game-local Python (a trick-winner function, a climb query, a call function). Its inputs are the [[primitive-bundle]]. Declared in `cardlang/builtins/` (`PRIMITIVE_*`); dispatch seam `runtime/primitives.py` — its arm count is the elimination metric; inventory + roadmap in `design-notes/primitive-inventory.md`. | `runtime/primitives.py`, `cardlang/builtins/` (`PRIMITIVE_*`) |
| [Primitive Bundle](glossary/primitive-bundle.md) | The pair every Primitive receives: the **facts** (`EngineFacts`) and its declared **reads** (`GameReads`). Named because it is one thing passed together, restated as `(facts, gr)` at every primitive signature; it becomes a NamedTuple when the sidecar design lands, and the two halves keep their own names either way. | `narrowing.py`, `reads.py` |
| [Projection](glossary/projection.md) | The per-observer rendering of a zone (`identity`, `count_by_type`, …). "Visibility" is the *declaration*; "projection" is the derived view. | `stdlib/zones.py` |
| [Round](glossary/round.md) | The kernel decision loop: the `round` keyword and its three **forms** — **trick form**, **auction form** (which also serves betting), **climb form**. "Round" never means "a round of the game"; that concept is a [[hand]]. The forms are distinct AST nodes — `TrickRound` / `AuctionRound` / `ClimbRound`, each carrying only its own form's clauses. Surface keyword unchanged; a surface word for trick stays parked on the second family. | `mechanics.py` |
| [Round State](glossary/round-state.md) | What a running round publishes under the `state.` pronoun — the round's accumulator fields (`stdlib/round_state.py`), not state variables. | `round_state.py` |
| [Rule](glossary/rule.md) | A named constraint on a move type (`constrains` / `applies_when` / `demands` / `exempts` / `if_impossible`). A **rule template** is a parameterized rule; instantiation substitutes arguments. | `n.RuleDef` |
| [Seat](glossary/seat.md) | A player *position*: an index `0..players-1` into the turn ring. What zones are keyed by, what OpenSpiel calls a player. | `domains.Role.PLAYER` |
| [State Variable](glossary/state-variable.md) | A declared `state { }` variable, lexically scoped to its phase. Never call anything else "state" unqualified — [[state]] is reserved. | `n.StateDecl` |
| [Stdlib](glossary/stdlib.md) | The standard library: the layer **written in the language itself** — `stdlib/rules.cardlang` and what grows beside it, sitting between the grammar and the engine. This is the word's only meaning, and the tree now says so (#331). Generic native functions are **[[builtins]]**; game-local native code is a **[[primitive]]**; either half, or the union, is **[[native-code]]**; registry data are **[[kernel-tables]]**. The directory `cardlang/stdlib/` still holds the kernel tables beside `rules.cardlang` — that physical split is issue #203, not a naming question. | `cardlang/stdlib/` |
| [Sub-phase](glossary/sub-phase.md) | A nested phase inheriting the parent's rules — a step, not a condition. Retired: **rule-delta sub-phase**, the config-only child that just edited `active_rules:`; that is a **Mode**. | `active_rules.py` |
| [Team](glossary/team.md) | A named grouping of seats — the word everywhere, surface included: the game clause is `teams:`, the same noun the quantifiers range over (`all teams where …`), exactly as `players:` is for seats. Retired: `partnership`, `partnerships:`. | `Role.TEAM` |
| [Trace Event](glossary/trace-event.md) | One `(event name, payload)` emission from a primitive or the engine. | `narrowing.py` |
| [Transfer](glossary/transfer.md) | The zone-relocation *statement*. Its verbs — `deal`/`draw`/`move`/`burn`/`muck`/`transfer` — are sugar over the one primitive; future families mint their own (`place`, `capture`). Never "a move"; the surface verb `move` is native English (in solitaire the verb and the Move coincide), the engine word is Transfer. Flip/orient are not Transfers — nothing changes zones. Retired: `Movement`, `MoveParam`. | `n.Transfer` |
| [Trick](glossary/trick.md) | One trick: the thing the trick form plays out. Canonical concept name even though the surface keyword is `round` (→ F-2). | `TrickForm` |
| [Variant](glossary/variant.md) | A rules variant of a game: a sibling game composed from a shared core (`principles.md`), and the future Variant/meta context. Never the tagged union — that is an **outcome type**. Retired spellings for the old sense: `VariantCase`, `TVariant`, `variant_registry`. | docs |
| [Vocabulary](glossary/vocabulary.md) | The word-stock the DSL gives designers — "the vocabulary IS the syntax" (`principles.md`). One sense, the seniormost claim. The project's term catalog is this **glossary**; the encoding's old sense is an **offering**. | `principles.md` |
| [Winner](glossary/winner.md) | The player a decision yields, at either scope: the game-level `winner:` clause (argmax over a state variable), and the player a trick or climb round yields — the trick form's `winner <fn>` clause, the value bound in round bodies, and the function that computes it (**winner function**), carried in `TrickRound.winner_fn`. An auction's tagged result is an Outcome, not a winner, and lives in `AuctionRound.outcome_fn`. | `n.Winner`, `mechanics.py` |
| [World](glossary/world.md) | The live mutable game: zones + frame stack + indexes. The class is still spelled `RuntimeState` and its module `state.py`; both converge on this name when-touched. `rs` stays as the conventional variable — variables are not glossary surface. | `state.py` |
| [Zone](glossary/zone.md) | A named ordered container of cards/pieces. A **zone family** is a zone declared with an index (`hand[player]`); an **instance** is one member; the **owner** is the observer whose key it is. | `state.Zone` |
| [Zone Address](glossary/zone-address.md) | The `(name, key)` pair identifying one zone instance — `("hand", 2)`, or `("deck", None)` for a family-less zone. Named because it is one identity, not two arguments: its label form (`hand[2]`) is currently formatted at three separate sites. Becomes a dataclass when-touched, which collapses that triplication. | `state.ZoneStore.locate` |

## The compiler

| Term | Definition | Home |
|---|---|---|
| [Binder](glossary/binder.md) | A name introduced by a construct (`let`, loop variables, parameters, quantifier nouns). Resolve's `ref_kind` for one is `local`; prefer "binder" in prose. | `resolve.py` |
| [Domain](glossary/domain.md) | A quantifiable domain: a row of `domains.DOMAINS` (player/team/suit/rank), plus position domains. Every other use of "domain" must be qualified — see the approved compounds below (→ F-4). | `domains.py` |
| [IR](glossary/ir.md) | The resolved AST rendered as JSON-able dicts; the `kind` key is the node tag and is reserved for that (→ F-9). | `ir.py` |
| [Namespace](glossary/namespace.md) | One of the closed set of name pools a bare name resolves against (state, zone, phase, function, …). Prefer over "category" / "bucket". | `resolve.py` |
| [Parameter](glossary/parameter.md) | The named, typed slot of a declaration — one shared node across move types, functions, procedures, and rules. Per-construct admissible-type constraints live in each construct's Owner Guard, not the node. Tripwire: splits only if the four uses ever need different fields. Full word, not "Param" — new names follow the full-word pattern; the abbreviation keeps (`Ctx`, `Expr`, `Stmt`) are grandfathered, not precedent. | `n.Parameter` |
| [Pipeline](glossary/pipeline.md) | extract → parse → resolve → typecheck → expand → check_capacity → emit. Use these seven stage names, nothing else. Expansion follows typecheck deliberately: a procedure's parameter types can only be enforced while its `run` site still exists (`pipeline.py`). | `pipeline.py` |
| [Pronoun](glossary/pronoun.md) | A magic contextual name: `actor`, `action`, `winner`, `state`, `active_rules`. | `resolve.py` |
| [ref_kind](glossary/ref-kind.md) | The classification resolve stamps on a `NameRef` (`local`, `state_var`, `zone`, `enum_value`, `pronoun`, `function`, `null`, `bool`). | `n.NameRef` |
| [Resolve](glossary/resolve.md) | Name resolution: classifying every name and checking structural references. A `_resolve_*` name is legal only for a function that classifies names or resolves them; a validator is `_check_*`, and a function that mints a domain says `_mint_*`. Applied when-touched — the surviving `_resolve_*` validators in `resolve.py` rename as their sites are next edited. | `resolve.py` |
| [Splice](glossary/splice.md) | Bringing a library's or template's definitions into a game. Prefer over "inject"/"provide"; **mint** stays for `board:` creating a domain no one declared. | `resolve.py` |

## The OpenSpiel boundary

| Term | Definition | Home |
|---|---|---|
| [Game Tree Node Kinds](glossary/game-tree-node-kinds.md) | OpenSpiel calls it **decision node** / **terminal node** / **chance node**. Replay reifies the first two as `DecisionNode` / `TerminalNode`. Exactly one chance node exists, at the root, implicit in `CardlangState` (`_seed is None`); its outcomes are seeds that drive every rng draw. A future native simultaneous-move export would add `SimultaneousNode`. Not "Terminal" bare — that word is grammar/lexer vocabulary. — translated in `replay.py`, `game.py`. | `replay.py`, `game.py` |
| [Observation Log](glossary/observation-log.md) | OpenSpiel calls it **information state** string (perfect recall). "Information state" is the per-player artifact; "information set" is the equivalence class it induces — don't interchange them (→ F-14) — translated in `infostate.py`. | `infostate.py` |
| [Shuffle Seed](glossary/shuffle-seed.md) | OpenSpiel calls it the root **chance** node (4096 sampled seeds) — translated in `game.py`. | `game.py` |

## Check vocabulary

| Term | Definition | Home |
|---|---|---|
| [Author](glossary/author.md) | The person who can act on a failure — whose artifact (game file, library, or engine) must change. Every failure is reported to its author: span in their file, message in their vocabulary, through a channel they'll actually see. Always the author of the *faulty artifact*, never of the diagnostic; in practice compound it: game author, library author, engine maintainer, primitive maintainer (`PrimitiveReadError`), and — for the engine's own data files, which load from the checkout — whoever installed it (`InstallationError`). Retired: "the game's currency" and "the library's currency", which named the addressee (→ F-23). The word's other sense — how a layer reports, not who it reports to — is the [[failure-channel]]; the two are independent, and a guard can use the right channel while naming the wrong Author. |  |
| [Failure Channel](glossary/failure-channel.md) | How a layer reports a failure, fixed by the layer: the compile stages fail as diagnostics carrying a span and a designer-readable message, the runtime fails as typed exceptions, the proofs fail with a witness. An [[owner-guard]] speaks its own layer's channel; loud-but-wrong-layer ranks with silent. Distinct from the [[author]], who the failure is addressed to — a guard can use the right channel and still name the wrong person. | `cardlang/runtime/errors.py`, `cardlang/diagnostics.py` |
| [Game Description Error](glossary/game-description-error.md) | A runtime refusal naming an illegal game description: `GameDescriptionError` (`cardlang/runtime/errors.py`), the base a harness catches. The base says WHAT is wrong; the subtype says which role caught it — an [[owner-guard]] raises `OwnerGuardError`, a [[shadow-guard]] raises `ShadowGuardError`. The base therefore reaches engine gaps too, which is why a harness catching it must not treat a `ShadowGuardError` as merely a bad game. | `cardlang/runtime/errors.py` |
| [Owner Guard](glossary/owner-guard.md) | The authoritative guard for a defect class: it lives at the single layer that *owns* the class (the earliest that can decide it), is total over the class, is tested, fails in its layer's channel (diagnostic / typed exception / witness), and is addressed to the Author of the faulty artifact — usually the game author, in their language. Every defect class has exactly one Owner Guard. Runtime Owner Guards exist (capacity, phantom-key writes) and address the game author like any other. Never a name for this role: `wall` (→ F-19) — the word has its own life (Quoridor's walls delete edges), so what is retired is the guard sense, not the spelling. |  |
| [Permissive Top](glossary/permissive-top.md) | The type checker's top, `TAny`: compatible with every type in both directions, propagating through every operation without error rather than refusing (`types.py`). It means the TOP and never a failed lookup — a lookup miss raises at its producer instead of decaying into it (decisions.md, "`Any` means the top, never a failed lookup"). The **permissive-top gap** is the defect named after it, not another name for it: a value reaching the top silently satisfies every guard downstream, so an unrefined `infer` arm exempts the expression it types. | `cardlang/types.py` |
| [Pin](glossary/pin.md) | A test that freezes an invariant (goldens, registry equality, a guard's totality). |  |
| [Shadow Guard](glossary/shadow-guard.md) | A deliberately redundant guard standing behind an Owner Guard it names; unreachable if that Owner Guard is correct. Its firing is always an engine gap: it addresses the engine maintainer, and its message leads with the Owner Guard that leaked, game context second. Code artifact: runtime Owner Guards raise `OwnerGuardError`, Shadow Guards raise `ShadowGuardError`, both subtypes of `GameDescriptionError` (`cardlang/runtime/errors.py`) — the base names what's wrong (catch it in harnesses), the subtype names the role that caught it, and any `ShadowGuardError` raised anywhere in the suite is a failure (Pinned in `tests/conftest.py`). Where each class sits is itself Pinned, in `tests/test_failure_taxonomy.py`. Never names for this role: `backstop`, `twin` (→ F-19). Both have their own lives — a `max_length` backstop is a real termination bound, and a game's readable twin is its prose counterpart — so what is retired is the guard sense, not the spelling. |  |

## The Operating Harness

| Term | Definition | Home |
|---|---|---|
| [Architect](glossary/architect.md) | Hoyle's engine-side counterpart, named **Foster** ("according to Foster"): the persona consulted on engine-structural questions (passes and Contract blocks, types, IR, runtime, diagnostics machinery, testing strategy, observability). Cites its sourcebook and principles note; standing tensions with settled law are filed, never normalized. Advises, never merges. Contrast the [[language-owner]], who owns the language's taste. | `harness.md` |
| [Brief](glossary/brief.md) | The closing section of persona counsel, written last: the counsel's verdict, the strongest case against it and its cost, and the operator's decision, in plain words with the measured numbers kept and the citations dropped. Condenses the counsel and never previews it; introduces nothing the counsel does not say. Closes counsel at the table, heads counsel in a record. Contrast the counsel proper — the [[language-owner]]'s or the [[architect]]'s cited analysis — which is the record's and the implementer's currency. Always "the brief" of a counsel, never a bare adjective for a short document. | `harness.md` |
| [Language Owner](glossary/language-owner.md) | The persona that owns the language's taste, named **Hoyle** ("according to Hoyle"): consulted on every Merge Lane A change and any design that would create one, supplying details — worked alternatives, precedent, corpus impact — to the operator's decision. Advises, never merges; not a Standing Role (consulted, not scheduled). Charter lives in its skill. | `harness.md` |
| [Lease](glossary/lease.md) | The atomic public take of an issue: the branch `claude/issue-<N>`. Creating it takes the issue; merge or deletion releases it; staleness is derived and reaped conservatively. Distinct from the Claims line of a PR description (`cardlang-pr-description`). | `harness.md` |
| [Merge Lane](glossary/merge-lane.md) | Who may perform a merge, decided by change class. Earlier letter = more authority: Merge Lane A (deity merge — the grammar alone, the operator ruling with Language Owner counsel), Merge Lane B (operator merge), Merge Lane C (reviewed agent merge), Merge Lane D (clean-pass agent merge); later letters append as delegation earns granularity. The merge gate itself is lane-invariant. Never bare "lane". | `harness.md` |
| [Operating Harness](glossary/operating-harness.md) | The process layer that moves work: Merge Lanes, the work graph and Ready Front, Leases, Standing Roles. The compound that qualifies the reserved word [[harness]] for the process sense. | `harness.md` |
| [Ready Front](glossary/ready-front.md) | The derived set of issues an agent may take without asking — open issues surviving the disqualifier list, computed by `tools/ready-front.sh`. An issue on it "is Ready". | `harness.md` |
| [Standing Role](glossary/standing-role.md) | A named, recurring, unattended agent charter, versioned as a skill (`role-<name>`) and invoked on a schedule. Always the full phrase — bare "Role" is the seat/team enum (`domains.Role`). | `harness.md` |

## Reserved words — never use unqualified

These carry several meanings each; always qualify them. The ones that also name a concept of their own keep their entry in a section above as well.

| Word | Approved compounds |
|---|---|
| [action](glossary/action.md) | OpenSpiel action id (Interop only) · the `action` pronoun (the candidate Move under consideration — kept deliberately small so the Interop translation stays one-directional) |
| [block](glossary/block.md) | fenced block (markdown) · `Block` node (synthetic) · braced body — say which |
| [channel](glossary/channel.md) | failure channel · scoring channel · observation channel · communication channel · a library's feeding channel |
| [check](glossary/check.md) | a `_check_*` pass · the `is …` predicate is an **is-check**, not "a check" |
| [direction](glossary/direction.md) | turn direction (the `direction:` clause, `clockwise`) · **seat direction** (the `SeatDirection` enum, `left/right/across/hold`: a relative direction around the seating ring, fed to `offset_by`; `hold` is the identity offset — Hearts table-talk; "pass direction" is ordinary prose for Hearts' variable, not a term) · board direction (`dir`/`TDir`) (→ F-15) |
| [Domain](glossary/domain.md) | quantifiable domain · parameter domain · position domain · choose range |
| [Hand](glossary/hand.md) | hand zone · one hand (this cycle) · hand loop (the repetition it is one pass of) |
| [harness](glossary/harness.md) | the shared proof harness (`tests/openspiel_ready/`) · the LLM harness (`experiments/llm_eval/`) · the [[operating-harness]] (process; `harness.md`) |
| [index](glossary/index.md) | definition index (name→def) · rank index (rank→strength) · zone index (the keying domain) · subscript |
| [kind](glossary/kind.md) | IR node tag (reserved) · AST discriminators (rename per node when touched — → F-9) |
| [Library](glossary/library.md) | family library · the stdlib is not a library |
| [Outcome](glossary/outcome.md) | one meaning only: the tagged result. The player sense is **winner** / **winner function**. Reserved as a declaration name even though no pronoun claims it (`resolve._KEYWORD_RESERVED`); `AuctionRound.outcome_fn` is the tagged sense, qualified because the bare word belongs to the designer's clause |
| [Round](glossary/round.md) | the round statement/forms · (a "round of the game" is a *hand*) |
| [Rule](glossary/rule.md) | game rule (`RuleDef`) · grammar rule (production) · never "checking principle" |
| [state](glossary/state.md) | state variable · round state · world (`rs`) · info-state string · `state { }` block |
| [type](glossary/type.md) | struct type · zone type · move type (not a type) · the checker's `Type` |
| [value](glossary/value.md) | card points (the `card_points { }` clause — see its entry) · enum value · RHS/initializer · literal payload |
