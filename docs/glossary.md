# Glossary

The glossary of OpenRegel's shared language — one entry per concept, one spelling per
concept. (DDD calls this the "ubiquitous language"; this file is named for the word
people can actually remember — "vocabulary" belongs to the DSL itself; see its entry.)
`principles.md` already holds this rule for the DSL surface ("A second spelling is a
defect"); this file extends it to the implementation. When code, docs, or diagnostics
need a word for one of these concepts, use the term in the left column. When a word
appears in the "reserved words" table at the end, do not use it unqualified.

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

## 1. The game model (designer's world)

| Term | Meaning | Home |
|---|---|---|
| **Game** | The root unit: one `game { }` plus its supporting definitions. Not "program", "spec", or "source" except when meaning the file/text itself. | `n.Game` |
| **Library** | A family library: a `library { }` file a game `uses`. The stdlib rules fragment is *not* a library. | `n.Library` |
| **Stdlib** | The standard library: the layer **written in the language itself** — `stdlib/rules.cardlang` and what grows beside it. This is the word's only meaning; endpoint is `cardlang/stdlib/` holding only `.cardlang` files + loader, pinnable. Native functions are **builtins**; game-local native code is a **Primitive**; registry data are **kernel tables**. Spec: issue #203. | `cardlang/stdlib/` |
| **Phase** | A step in the game's sequential program: phases run in declaration order, and a phase ends when its work completes (the sense MTG taught every designer). This is the keyword's sole meaning — the rule-swapping flavor is a **mode** (→ F-8; spec: issue #208). | `n.Phase` |
| **Mode** | A condition the game is in, existing to change which rules are active: entered by `transition_to`, body is configuration only (`active_rules:`, `transition_to:` — being in it *is* its behavior), and an empty mode is the terminal default: no delta, no exits. New keyword; the config-only class is grammar-owned. | `n.Mode` (planned) |
| **Sub-phase** | A nested phase inheriting the parent's rules. A **rule-delta sub-phase** is the config-only child that just edits `active_rules:`. | `phases.py` |
| **Round** | The kernel decision loop: the `round` keyword and its three **forms** — **trick form**, **auction form** (which also serves betting), **climb form**. "Round" never means "a round of the game"; that concept is a *hand* (below). The forms are distinct AST nodes — `TrickRound` / `AuctionRound` / `ClimbRound` (spec: issue #210; code still has a single field-sniffed `n.Round` pending migration). Surface keyword unchanged; a surface word for trick stays parked on the second family. | `mechanics.py` |
| **Trick** | One trick: the thing the trick form plays out. Canonical concept name even though the surface keyword is `round` (→ F-2). | `TrickForm` |
| **Hand** (the iteration) | One deal-to-scoring cycle of a game (`skip to next hand`, `hands_played`). Distinct from the *hand zone*; qualify as "hand loop" / "hand zone" when ambiguity is possible. The hand loop currently has no structural marker in the language (→ F-6). | `driver.py` |
| **Seat** | A player *position*: an index `0..players-1` into the turn ring. What zones are keyed by, what OpenSpiel calls a player. | `domains.Role.PLAYER` |
| **Player** | The participant occupying a seat. In today's engine seat and player coincide (`Player = int`); keep the two words distinct anyway — `domain-map.md` lists "seat vs agent identity" as a future forcing point. | `values.Player` |
| **Actor** | The seat currently acting: the `actor` pronoun, `Ctx.current_player`, `as` rebinding. Prefer "actor" over "current player" / "decider" / "acting seat" in new code. | `state.Ctx` |
| **Team** | A named grouping of seats — the word everywhere, surface included: the game clause is `teams:` (spec: issue #211; the corpus still spells it `partnerships:` pending migration). Retired: `partnership`, `partnerships:`. | `Role.TEAM` |
| **Component Set** | The pack a game selects with `cards:`/`pieces:` — either flavor. A **deck** is specifically the card-flavored component set. `Game.deck` currently holds either (→ F-16). | `values.ComponentSet` |
| **Card / Piece** | The individuated content of zones; a card is the deck specialization of a piece (`model.md`). Runtime represents both as `Card` (→ F-16). | `values.Card` |
| **Zone** | A named ordered container of cards/pieces. A **zone family** is a zone declared with an index (`hand[player]`); an **instance** is one member; the **owner** is the observer whose key it is. | `state.Zone` |
| **State Variable** | A declared `state { }` variable, lexically scoped to its phase. Never call anything else "state" unqualified (reserved word, §6). | `n.StateDecl` |
| **Round State** | What a running round publishes under the `state.` pronoun — the round's accumulator fields (`stdlib/round_state.py`), not state variables. | `round_state.py` |
| **Position Domain** | An integer or named-member index domain from `positions { }` or minted by `board:` (`cell`, plus the direction domain `dir`). | `board_domains.py` |
| **Move Type** | A named, parameterized player action with a `when:` guard and an effect. Keyword and term settled: with "move" owning the player-action family, `move_type` reads as compositional English; `action_type` would manufacture an Interop false friend. | `n.MoveTypeDef` |
| **Move** | One played instance of a Move Type, bound to its Parameters. A Move may perform zero, one, or many Transfers: a pass is a Move with none, a card play one, a capture two. The struct is card-shaped today (`(card, actor)`); the concept already covers `step(from, to)` (→ F-16). | `state.Move` |
| **Transfer** | The zone-relocation *statement* (spec: issue #209; code still says `Movement` pending migration). Its verbs — `deal`/`draw`/`move`/`burn`/`muck`/`transfer` — are sugar over the one primitive; future families mint their own (`place`, `capture`). Never "a move"; the surface verb `move` is native English (in solitaire the verb and the Move coincide), the engine word is Transfer. Flip/orient are not Transfers — nothing changes zones. | `n.Transfer` |
| **Candidate** | One concrete legal option at a decision point: a `(move type, bound parameter)` pair or a card/subset. The thing rules filter and the encoding numbers. Prefer over "option"/"legal move"/"concrete move" (→ F-19). | `mechanics.py` |
| **Offering** | The declared menu of moves a construct presents to a decider: `round offering [ ]`, an `offer` statement's list. Replaces every code use of "vocabulary"; the ActionSpace's flattened move-type x parameter-domain block is the **offering block**. Distinct from a phase's `legal_moves:`, which is availability, not presentation. | `n.Round`, `n.Offer` |
| **Vocabulary** | The word-stock the DSL gives designers — "the vocabulary IS the syntax" (`principles.md`). One sense, the seniormost claim. The project's term catalog is this **glossary**; the encoding's old sense is an **offering**. | `principles.md` |
| **Rule** | A named constraint on a move type (`constrains` / `applies_when` / `demands` / `exempts` / `if_impossible`). A **rule template** is a parameterized rule; instantiation substitutes arguments. | `n.RuleDef` |
| **Outcome** | The tagged result a decision construct yields: a phase's `-> outcome { }`, a `define`'s case set, an auction's result. Declared as an **outcome type** of **outcome cases**; carried as a `(tag, payloads)` value. This is the word's only meaning. The player a trick/climb yields is the **winner**. | `n.Phase`, `n.DefineDef` |
| **Variant** | A rules variant of a game: a sibling game composed from a shared core (`principles.md`), and the future Variant/meta context. Never the tagged union — that is an **outcome type**. Retired spellings for the old sense: `VariantCase`, `TVariant`, `variant_registry`. | docs |
| **Winner** | The player a decision yields, at either scope: the game-level `winner:` clause (argmax over a state variable), and the player a trick or climb round yields — the trick form's `winner <fn>` clause, the value bound in round bodies, and the function that computes it (**winner function**). The winner function is still carried in `Round.outcome_fn`, the field shared with the auction form, until the node splits (issue #210). | `n.Winner`, `mechanics.py` |
| **Loser** | The game-level `loser:` clause — a player expression. Asymmetric with `winner:` by design. | `n.Loser` |

## 2. The compiler

| Term | Meaning | Home |
|---|---|---|
| **Pipeline** | extract → parse → resolve → expand → typecheck → check_capacity → emit. Use these seven stage names, nothing else. | `pipeline.py` |
| **Resolve** | Name resolution: classifying every name and checking structural references. `_resolve_*` functions that only validate are misnamed (→ F-22). | `resolve.py` |
| **Namespace** | One of the closed set of name pools a bare name resolves against (state, zone, phase, function, …). Prefer over "category" / "bucket". | `resolve.py` |
| **ref_kind** | The classification resolve stamps on a `NameRef` (`local`, `state_var`, `zone`, `enum_value`, `pronoun`, `function`, `null`, `bool`). | `n.NameRef` |
| **Binder** | A name introduced by a construct (`let`, loop variables, parameters, quantifier nouns). Resolve's `ref_kind` for one is `local`; prefer "binder" in prose. | `resolve.py` |
| **Pronoun** | A magic contextual name: `actor`, `action`, `winner`, `state`, `active_rules`. | `resolve.py` |
| **Domain** (registry sense) | A quantifiable domain: a row of `domains.DOMAINS` (player/team/suit/rank), plus position domains. Every other use of "domain" must be qualified: *parameter domain*, *position domain*, *choose range* (reserved word, §6; → F-4). | `domains.py` |
| **Splice** | Bringing a library's or template's definitions into a game. Prefer over "inject"/"provide"; **mint** stays for `board:` creating a domain no one declared. | `resolve.py` |
| **Parameter** | The named, typed slot of a declaration — one shared node across move types, functions, procedures, and rules (spec: issue #209; code still `MoveParam` pending migration). Per-construct admissible-type constraints live in each construct's Owner Guard, not the node. Tripwire: splits only if the four uses ever need different fields. Full word, not "Param" — new names follow the full-word pattern; the abbreviation keeps (`Ctx`, `Expr`, `Stmt`) are grandfathered, not precedent. | `n.Parameter` |
| **IR** | The resolved AST rendered as JSON-able dicts; the `kind` key is the node tag and is reserved for that (→ F-9). | `ir.py` |

## 3. The runtime

| Term | Meaning | Home |
|---|---|---|
| **World** | The live mutable game: `RuntimeState` (`rs`). Zones + frame stack + indexes. | `state.py` |
| **Context** | `Ctx`: the immutable evaluation context threaded through the interpreter (actor, locals, pronoun bindings, chooser, tracer). | `state.py` |
| **Chooser** | The decision seam: the callable that resolves a player choice. A **decision point** is one call site of it in the interpreter (currently 7, unnamed — → F-20) — the *static* concept; the *dynamic* occurrence (a game state where a seat must choose) is a **decision node** (§4). | `state.Chooser` |
| **Form** | A round form's hook bundle (`TrickForm` / `AuctionForm` / `ClimbForm`) behind the `DecisionForm` protocol. Prefer "form" over "mechanic"; the accumulator dict is the **round state** (§1). | `mechanics.py` |
| **Primitive** | Sanctioned game-local Python (a trick-winner function, a climb query, a call function). Its inputs are the **facts** (`EngineFacts`) and its declared **reads** (`GameReads`); the pair is the primitive's *bundle*. Declared in `cardlang/builtins/` (`PRIMITIVE_*`); dispatch seam `runtime/primitives.py` — its arm count is the elimination metric; inventory + roadmap in `design-notes/primitive-inventory.md`. | `reads.py`, `sidecar.py` |
| **Builtins** | Generic native functions the language ships: declared in `cardlang/builtins/` (`BUILTIN_*`), implemented in `runtime/builtins.py`. Distinct from the **stdlib** (written in the language — functions migrate builtins→stdlib as expressibility grows) and from **Primitives** (game-local). | `runtime/builtins.py` |
| **Kernel Tables** | The kernel's registry data: zone types + projections + capacities, board families, round-state fields, enum namespaces. Not library, not builtins — engine spec data, staged toward `cardlang/kernel/` at the second-family extraction (issue #203). | `stdlib/*.py` (interim) |
| **Trace Event** | One `(event name, payload)` emission from a primitive or the engine. | `sidecar.py` |
| **Projection** | The per-observer rendering of a zone (`identity`, `count_by_type`, …). "Visibility" is the *declaration*; "projection" is the derived view. | `stdlib/zones.py` |
| **Observation Event** | An event appended to a player's observation log (`chose`, `announce`, `move`, `reveal`). | `observe.py` |

## 4. The OpenSpiel boundary (Interop)

Interop is an anti-corruption layer (`domain-map.md`), so OpenSpiel's words legitimately
differ from ours. The translation is part of the vocabulary — keep it explicit:

| Ours | OpenSpiel's | Where translated |
|---|---|---|
| candidate | **action** (a global integer id) | `encoding.ActionSpace` |
| move type | **verb** (encoding-granularity name; `<card>`/`<int>`/`<combo>` sentinels) | `encoding.verb_of` |
| seat | **player** | `replay.py`, `game.py` |
| observation log | **information state** string (perfect recall). "Information state" is the per-player artifact; "information set" is the equivalence class it induces — don't interchange them (→ F-14) | `infostate.py` |
| winner/loser + scores | **returns** vector | `replay.returns_for` |
| shuffle seed | the root **chance** node (4096 sampled seeds) | `game.py` |
| the game tree's node kinds | **decision node** / **terminal node** / **chance node**. Replay reifies the first two as `DecisionNode` / `TerminalNode` (spec: issue #212; code still `Pause`/`Terminal` pending migration). Exactly one chance node exists, at the root, implicit in `CardlangState` (`_seed is None`); its outcomes are seeds that drive every rng draw. A future native simultaneous-move export would add `SimultaneousNode`. Not "Terminal" bare — that word is grammar/lexer vocabulary. | `replay.py`, `game.py` |

The encoding's flattened move-type × parameter-domain cross-product is the
**offering block**. Inside `cardlang/openspiel/`,
OpenSpiel's senses of `action`, `player`, `state`, `observation` win; outside it,
ours do.

## 5. Check vocabulary

Two full phrases and a test-freeze word carry the whole taxonomy. Timing (static vs runtime) is never part
of a term — it's visible from where a guard lives, and both roles exist at both times.

| Term | Meaning |
|---|---|
| **Owner Guard** | The authoritative guard for a defect class: it lives at the single layer that *owns* the class (the earliest that can decide it), is total over the class, is tested, fails in its layer's channel (diagnostic / typed exception / witness), and is addressed to the Author of the faulty artifact — usually the game author, in their language. Every defect class has exactly one Owner Guard. Runtime Owner Guards exist (capacity, phantom-key writes) and address the game author like any other. |
| **Shadow Guard** | A deliberately redundant guard standing behind an Owner Guard it names; unreachable if that Owner Guard is correct. Its firing is always an engine gap: it addresses the engine maintainer, and its message leads with the Owner Guard that leaked, game context second. Code artifact: runtime Owner Guards raise `OwnerGuardError`, Shadow Guards raise `ShadowGuardError`, both subtypes of `GameDescriptionError` (`cardlang/runtime/errors.py`) — the base names what's wrong (catch it in harnesses), the subtype names the role that caught it, and any `ShadowGuardError` raised anywhere in the suite is a failure (Pinned in `tests/conftest.py`). Where each class sits is itself Pinned, in `tests/test_failure_taxonomy.py`. |
| **Pin** | A test that freezes an invariant (goldens, registry equality, a guard's totality). |
| **Author** | The person who can act on a failure — whose artifact (game file, library, or engine) must change. Every failure is reported to its author: span in their file, message in their vocabulary, through a channel they'll actually see. Always the author of the *faulty artifact*, never of the diagnostic; in practice compound it: game author, library author, engine maintainer, primitive maintainer (`PrimitiveReadError`), and — for the engine's own data files, which load from the checkout — whoever installed it (`InstallationError`). Retired: `currency` (and its verb "denominated") (→ F-23); comment-only migration rides the alignment pass's docstring phase (issue #214); the "runtime's currency" raise-site cluster is absorbed by the exception-hierarchy rework (spec: issue #207). |

Per the preamble rules: always the full phrase, always Title Case — never "owner"
(that's the zone-family owner) or "shadow". Bare "guard" is the family noun in prose
only; "check" stays the fully generic word for any validation. Retired: *wall*,
*backstop*, *gate*, *sweep* (mechanism words — how a guard checks is implementation),
*twin* (a pinned Shadow Guard), *mirror*, *copy*, *sibling*. Freeing the word:
`MoveTypeDef.guard` → `.when` (a convergence rename the audit already mandated) rides
the migration.


## 6. Reserved words — never use unqualified

These words currently carry 4–9 meanings each (see findings). In new code, comments,
docs, and diagnostics, always qualify them:

| Word | Approved compounds |
|---|---|
| **state** | state variable · round state · world (`rs`) · info-state string · `state { }` block |
| **outcome** | one meaning only: the tagged result. The player sense is **winner** / **winner function**. Reserved as a declaration name even though no pronoun claims it (`resolve._KEYWORD_RESERVED`); `Round.outcome_fn` is a legacy code site, qualified, until the node splits (issue #210) |
| **domain** | quantifiable domain · parameter domain · position domain · choose range |
| **hand** | hand zone · hand loop / one hand |
| **round** | the round statement/forms · (a "round of the game" is a *hand*) |
| **value** | card points (`Deck.values`) · enum value · RHS/initializer · literal payload |
| **index** | definition index (name→def) · rank index (rank→strength) · zone index (the keying domain) · subscript |
| **kind** | IR node tag (reserved) · AST discriminators (rename per node when touched — → F-9) |
| **type** | struct type · zone type · move type (not a type) · the checker's `Type` |
| **action** | OpenSpiel action id (Interop only) · the `action` pronoun (the candidate Move under consideration — kept deliberately small so the Interop translation stays one-directional) |
| **rule** | game rule (`RuleDef`) · grammar rule (production) · never "checking principle" |
| **check** | a `_check_*` pass · the `is …` predicate is an **is-check**, not "a check" |
| **direction** | turn direction (the `direction:` clause, `clockwise`) · **seat direction** (the `SeatDirection` enum, `left/right/across/hold`: a relative direction around the seating ring, fed to `offset_by`; `hold` is the identity offset — Hearts table-talk; "pass direction" is ordinary prose for Hearts' variable, not a term) · board direction (`dir`/`TDir`) (→ F-15) |
| **block** | fenced block (markdown) · `Block` node (synthetic) · braced body — say which |
| **library** | family library · the stdlib is not a library |
