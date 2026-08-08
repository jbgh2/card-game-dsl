# Glossary findings (vocabulary audit, 2026-07-30)

2026-07-30. Companion to `docs/glossary.md`; the findings below are what that file's
(→ F-n) markers point at. Six parallel readers covered the grammar and game corpus, the
frontend (`parse`/`ast`), `resolve`/`domains`, `typecheck`/`types`/`ir`, the runtime and
both stdlibs, and the OpenSpiel layer plus docs. Claims marked **[verified]** were
re-checked against source by hand; the rest carry the surveyors' file:line evidence.

The headline: `principles.md` states "one spelling per concept — a second spelling is a
defect", and the lexical cleanup enforced it on the DSL surface. The implementation
vocabulary was never held to the same rule. The result is the mirror-image defect class:
one spelling, several concepts. The worst words (`state`, `outcome`, `domain`, `hand`,
`kind`, `value`, `index`) each carry four to nine meanings, and the places where that
has already produced bugs (the `state.` seam, the `player`/`Player` key namespaces)
were fixed as one-off walls without treating the vocabulary as the root cause.

Section D lists what is already known or deliberate; nothing there is re-litigated.

---

## A. Overloads — one word, several meanings

**F-1 · `outcome` means five things.** The designer-facing senses are split: the
trick-winner function slot is `winner <fn>`, and the pronoun bound to the trick or
climb winner is `winner`. One internal use remains: the `DecisionForm.outcome` hook
(mechanics.py), which additionally pops the mechanic stack as a side effect — issue
#205's slice 3. The surviving legitimate senses are a phase's outcome type
(`-> outcome {A|B}`), the auction result function, and `rs.phase_outcomes` — all the
tagged `(tag, payloads)` reading.

**F-2 · "trick" has no name.** The central concept of the corpus has no surface or
code noun: it is spelled `round … source … into …` and carried only by `TrickPile`
and user names. And `round` never means a round of the game — that concept is a hand
(F-6). The internal names leak nowhere ("auction", "climb" appear in no surface
keyword), so grammar-rule names and keywords have drifted apart across the whole
statement layer (also `epistemic_op` for `shuffle`/`reveal`, `agg_order` for
`highest`/`lowest`, `phase_repeats` for `repeat until`).

The AST half of this finding is closed: the three grammar rules build three nodes
(`TrickRound` / `AuctionRound` / `ClimbRound`), each carrying only its own clauses.
What is left is the naming, which waits on the second family.

**F-3 · `state` carries at least seven referents.** The module `runtime/state.py`; the
live world `RuntimeState`; the round accumulator `mechanics.State = dict[str, Any]`;
declared `state { }` variables; the `state.` pronoun (which reads the accumulator, not
the variables); `reads.state()` (which reads the variables, not the accumulator); and
the info-state string's `state:` segment (state variables only, infostate.py:69).
`EngineFacts` exposes both `round_state` and `last_round_state` and its docstring must
warn "Distinct from `last_round_state` — see that field" (sidecar.py:91). The
`state.`-pronoun collision already caused a real bug (silent `state.idx` write) and was
walled (`open-questions/name-namespaces.md` defect 2) — but the wall fixed the seam,
not the vocabulary that produced it.

**F-4 · `domain` has nine senses.** Quantifiable domain (the `domains.py` registry);
move-parameter domain (`resolve.py:4463`); position domain (`:2855`); the direction
domain (`board_domains.py:38`); index domain (slot namespace `:399`);
procedure-parameter domain — explicitly documented as a *different* concept
(`:4069`); rule-parameter domain (`:2070`); "closed domain" as a methodology word for
any swept set (`:218`); and `Choose.domain == "integer"` (a keyword slot, `:437`).
`_reserved_domain_names` (`:2818`) returns a set three-quarters of which are not domain
names. The registry module itself excludes three domain kinds the language enumerates
(`Card`, declared positions, `dir`) — the module named `domains` is not the registry of
domains (`domains.py:62`, `:453`, `:483`).

**F-5 · `move` spans the verb and the action.** `Movement.verb` may literally be
`"move"` (the transfer statement) while `move_type` names the player action, and the
grammar has to disambiguate in prose: "`action` is the move instance … never the
zone-movement verb `move`" (grammar:456). `state.Move` is a played `(card, actor)`;
`concrete_moves` returns neither `Move`s nor movements but `(name, param)` pairs
(mechanics.py:274). Five `move_*` grammar productions serve the action; one serves the
transfer; `MoveParam` is also the parameter node for functions, procedures, and rules
(nodes.py:977, 997, 940), where a "move param" has nothing to do with moves.

**F-6 · `hand` is a zone, an iteration, and a poker ranking — and the iteration is
identified by a string literal. [verified]** `driver.py:337`:
`if phase.name == "scoring": hands.value += 1` — `GameResult.hands_played` counts
phases *literally named* `"scoring"`. A game whose scoring phase is called anything
else reports zero hands played. `SkipToNextHand` names a construct (the hand loop) the
language never declares; deckcheck's per-hand capacity window rests on the same
unnamed loop. `driver.py` binds both senses of `hands` within 60 lines (`:173`,
`:231`).

**F-7 · Field-name grab-bag: `value`, `index`, `target`, `op`, `kind`.**
`target` alone spans six meanings and four types (write lvalue, rotate var, a zone
expression, two phase names, a state-var name — nodes.py:528, 421, 404, 569, 839,
1073). `op` covers a binary operator, an assignment operator, shuffle/reveal, and a
rule-list delta (nodes.py:142, 530, 403, 810). `index` is a role-name string on
declarations but an expression on subscripts, plus `rank_index` (rank→strength) and
the definition indexes (`rule_index`, name→def, state.py:261). Nine independent
`kind` enums share the field name with no shared value space.

**F-8 · `phase` means both a sequential stage and a state-machine mode.** Hearts
declares `phase hearts_not_broken` / `phase hearts_broken` — the latter with an empty
body, existing only as a `transition_to` target (hearts.cardlang:82-89) — in the same
list as real stages like `phase scoring`. `model.md:39-53` acknowledges the duality
("phases are not synonyms for state-machine states, but they are state-machine
states"); the vocabulary just has no word to tell a designer which flavor a given
`phase` is.

## B. Cross-layer renames and IR hazards

**F-9 · The IR reserves `kind` for the node tag, then collides with itself.
[verified]** `"kind": "if"` is emitted for both `IfStmt` (ir.py:324, statement lists)
and `IfExpr` (ir.py:536, expression arms) — an IR consumer dispatching on `kind`
cannot distinguish them by tag. Every AST `.kind` discriminator is renamed at
emission (`check`, `quant`, `query`, `qualifier`, `form`) — three different AST
`kind`s all become `"query"`. The IR key `"type"` has three shapes (dict, bare
string ×2 — ir.py:185, 202, 152), `"index"` two (role string vs expression dict), and
the same resolved write target emits as `"name"` for assign but `"var"` for rotate
(ir.py:359, 306).

**F-10 · Internal spellings contradict deliberate surface decisions.** The grammar
comment records that the phase qualifier deliberately matches `repeat until`, "not
third-person `repeats`" (grammar:186) — yet the AST stores `kind="repeats"`
(parse.py:561), so the *rejected* spelling is the internal one. Likewise `highest`/
`lowest` become `agg="max"/"min"` while the same token is stored verbatim in
`Winner.rank_dir`; `is`/`is not` become `==`/`!=`, which the surface rejects; and the
typechecker re-synthesizes surface spellings for diagnostics by hand
(typecheck.py:1490, 1822).

## C. Synonym sprawl — several words, one concept

**F-11 · The acting player:** `actor` (pronoun), `Ctx.current_player`, `next_actor`,
"decider" (driver.py:151), "participant" (`Round.participants`), and `seat` — which is
load-bearing in comments and the OpenSpiel layer ("the challenger's seat",
`_score_key_by_seat`) but is neither a surface word nor a code type. `seat` vs
`player` vs `actor` deserve the three distinct meanings the glossary assigns them.

**F-12 · The Boolean sub-expression field:** `filter`, `pred`, `cond`, `guard`,
`where`, `termination`, `expr`, `selection` — eight field names across the AST for
"a predicate", with no rule for which construct gets which (nodes.py:200, 218, 456,
960, 833, 633, 916, 1084).

**F-13 · `partnerships:` vs `team`.** The surface clause is `partnerships:`; every
other artifact says team (`Team`, `team_of`, `TeamPile`, `Role.TEAM`,
`captured[team]`). `model.md:17` declares the alias, and then `appendix.md` mixes
`tricks_won[team]` (:69) with `tricks_taken[partnership]` (:82) in one table — the
exact "second spelling" `principles.md:79` calls a defect, in the docs that state the
principle.

**F-14 · "information state" vs "information set".** Six spellings across code and
docs (`information set`, `info set`, `info-set`, `infoset`, `information state`,
`info state`), used interchangeably — `domain-map.md` mixes them within one file
(:18, :39, :87). They are distinct game-theory terms: the *state* is the per-player
artifact `infostate.py` builds; the *set* is the equivalence class it induces. For a
project whose research moat is "derived information sets", this is the one place the
distinction should be crisp.

**F-15 · `Direction` names three disjoint concepts.** The `direction:` clause
(`clockwise`/`counterclockwise`), the `Direction` payload enum (`left/right/across/
hold`, values.py:17) — disjoint value sets, one name — and the board direction
domain `dir`/`TDir` (types.py:80, whose docstring already has to disclaim both
others).

**F-16 · `deck`/`Card` absorb the piece flavor.** `Game.deck: str` holds a piece-set
name in piece games (nodes.py:1151, "for both content flavors"); `Card` represents
pieces (values.py:319 "represented the same way"); `TCard` types pieces, and the
member wall prints "Piece has no field …" off a `TCard` (typecheck.py:2176). The
model doc says a card *is* a piece specialization, so the runtime representation is
defensible — but the *names* invert the hierarchy: the general thing is named after
the special case. `ComponentSet.axes` is (suit-slot, rank-slot) while `Deck.cards`
is (rank, suit) — opposite orders connected only by prose (values.py:53 vs :38).

**F-17 · Names that lie (verified sample).**
- **[verified]** `Ctx.active_rules` reads as context-wide; it is populated only by
  the trick form (`compute_active_rules`'s sole call site is mechanics.py:131) —
  everywhere else the pronoun sees the default `()`.
- **[verified]** `runtime/combinations.py` is the *Tichu* combination engine
  (its only importer is tichu.py); Big Two and President carry duplicate private
  copies (bigtwo.py:68, president.py:61). Three structural `Play` classes satisfy an
  unwritten protocol consumed via `getattr(play, "ends_trick", False)`
  (mechanics.py:576).
- **[verified]** resolve's `_KNOWN_ROLES = ZONE_INDEX_ROLES` (resolve.py:120) makes
  the diagnostic at :2994 report `unknown index role 'suit'` for a role the system
  knows perfectly well — it is known but not zone-indexable.
- `runtime/phases.py` runs no phases (active-rule computation only; the phase runner
  is in driver.py). `runtime/sidecar.py` is the interim narrowing, not the sidecar
  design it is named for (reads.py:22). `chooser.py` holds one function; the chooser
  machinery lives in driver.py:128-166.
- `types.unify` is a join/LUB, not unification; `assignable` is a coercion check
  used symmetrically by its own callers (typecheck.py:1524), not a subtype relation.
- `DecisionForm.next_actor` reads as a query but mutates the cursor — calling it
  twice skips a player (mechanics.py:154, 372, 539). `AuctionForm.init` clears
  another form's residue (`last_round_state = None`, :339).
- `GameResult.scores: dict[Player, int]` / `winner: Player` may be team-keyed —
  known as issue #154; `Player = int` makes the type unable to say so.
- Stale scope claims: `runtime/__init__.py` "(Hearts vertical slice)",
  `state.py:256` points at `run_trick`, which no longer exists.

**F-18 · Module-name collisions.**
- `values` ×2 (`runtime/values.py` value objects, `types.py` the type model).
- `rules` ×3 (legal-move engine / parsed stdlib rules / the DSL source); neither
  rules module owns `RULE_ENFORCED_MOVE_TYPE` — it lives in `stdlib/moves.py:49`.
- `run_body` ×2 in one package: driver.py runs phase items, execute.py runs
  statements; the driver imports the other under an alias (`run_stmts`,
  driver.py:23).

**F-19 · The legal option:** `candidates`, `legal_cards`, `legal_moves`, `options`
(`bigtwo_lead_options`), `universe` (`climb_universe_function`), "vocabulary" — six
names for the thing a decision selects among. The glossary picks **candidate**.

## D. Unnamed load-bearing concepts

**F-20 ·** DDD's other failure mode: concepts everyone talks about with no name in the
code. The strongest cases, each currently expressed as repeated prose or a raw tuple:

- The **decision point** — `ctx.chooser(...)` called inline at 7 sites, each
  re-implementing the non-emptiness contract and observe pairing.
- The **wall / backstop / twin** roles (66 "wall" mentions in typecheck alone) — no
  marker distinguishes a live check from a backstop; the choke-point exemption is a
  magic comment string (`# choke-point-exempt`) enforced by grep.
- The **tagged variant** `(tag, payloads)` — four spellings (`_ProduceSignal`,
  `phase_outcomes` values, `Outcome`'s second arm, `AuctionOutcomeFn`); `TVariant`
  exists statically, nothing at runtime.
- The **primitive bundle** `(EngineFacts, GameReads)` — restated in ~120 game-module
  signatures as `def f(facts, gr, …)`.
- The **zone address** `(name, key)` — a raw tuple whose label formatting is written
  three times (execute.py:138, :462, observe.py:129).
- The **game-description error** — ~40 bare `RuntimeError`s distinguished from engine
  bugs only by the repeated phrase "in the runtime's currency".
- The **hand loop** (F-6) — no structural marker; a phase-name string literal stands
  in for it.

**F-21 ·** The check vocabulary itself sprawls (wall / gate / sweep / backstop / pin /
twin / mirror / copy / sibling, with no defined distinctions); the glossary §5 fixes
meanings for six and retires the rest.

**F-22 ·** `_resolve_*` vs `_check_*` in resolve.py are interchangeable —
`_resolve_max_length` resolves nothing (two presence errors); `_resolve_board`
actually *mutates* (mints and appends a `PositionDecl`) while its neighbors validate.

**F-23 ·** "currency" is coined, load-bearing, and used in four incompatible senses
with no definition site (whose file a span points at; diagnostic-vs-assert; message
vocabulary; compile-vs-runtime). The glossary fixes one sense.

## E. Already known or deliberate — not re-litigated

- **Bare-name namespaces and silent shadowing** — `open-questions/name-namespaces.md`,
  Tier 2, every known instance walled. This audit's F-3 is the vocabulary-level view
  of the same seam.
- **`move_type` keyword naming** — open-questions Tier 5. One note: `action_type`,
  listed as a candidate there, would worsen the DSL↔OpenSpiel `action` collision.
- **The lexical-cleanup rulings** (English register, retired spellings, `offset_by`
  spelling still open) — settled spec; nothing here reopens them.
- **Interop word divergence** (`action`, `player`, `state` meaning OpenSpiel's things
  inside `cardlang/openspiel/`) — correct anti-corruption-layer behavior per
  `domain-map.md`, recorded as an explicit translation table in the glossary §4.
- Tracked issues touching naming: #112 (quantifier productions hardcoded), #123
  (`TZone`/`TMap` promotion — would resolve the `TCollection` facet flags), #139
  (combo-block deferrals), #153/#154 (winner/scores keying), #97 (corpus not in
  wheel). The `action`-fields-stay-`TAny` trap is ledger-owned by design.
- `model.md`'s primitives table predates the kernel (no `round`, `kernel`, `chance`,
  `offer` — 0 hits) while CLAUDE.md routes "how do phases/rules/moves fit together?"
  to it; and encoding.py's `SP1`/`SP6`/`Pillar 2` citations resolve to nothing in
  docs/. Both are doc-freshness problems adjacent to, but bigger than, vocabulary.

## F. What to actually do

Adopt `docs/glossary.md` and apply it *when touching code* — no big-bang rename; the
goldens and 700-odd tests make opportunistic renames cheap to verify, and most of the
cost here is in future misreadings, not current behavior. Three items are worth fixing
on their own because they are latent defects rather than reading hazards: the IR
`"if"` tag collision (F-9 — any IR consumer dispatching on `kind` mis-handles one of
the two), the `hands_played` phase-name literal (F-6 — silently wrong for any corpus
game without a phase named `scoring`), and the `unknown index role 'suit'` diagnostic
(F-17 — actively misleads the designer it is addressed to). The unnamed concepts
(F-20) are the highest-leverage naming work: naming the decision point, the tagged
variant, and the primitive bundle would each collapse repeated prose contracts into a
symbol the language of the codebase can then use.
