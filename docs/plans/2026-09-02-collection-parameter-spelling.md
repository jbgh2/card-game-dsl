# Collection parameters in the `primitives { }` block (issue #472)

Operator go: PENDING — this plan is presented for Ben's Merge Lane A ruling
(docs/harness.md, "The Language Owner"); both counsels are attached below,
produced fresh at planning time 2026-09-02. Stage plan this serves:
`docs/plans/2026-08-29-primitives-block-stage3b.md` (closing steps: gin is
one of the three legacy holdouts). The construct's parent plan is
`docs/plans/2026-08-28-primitives-block-stage3a.md`; the tail's is
`docs/plans/2026-08-30-phase-scoped-reads.md`.

## Acceptance criteria (bind the change)

1. **Runs** — gin-rummy declares its block and plays under the declared
   regime; the six `where jointly` sites PLAY (an executed playout, never a
   resolve-clean fixture), reaching their subset codecs by name.
2. **Regression-clean** — bare `mypy`; CI's three checks; full-width
   playout goldens byte-identical for every golden game
   (`CARDLANG_GOLDEN_SEEDS=full pytest tests/test_migration_characterization.py`).
   Gin carries no per-seed golden and no IR golden, so its neutrality is
   carried by SUBSTITUTE instruments, run twice independently (the
   canasta precedent, PR #536): a main-vs-branch playout differential
   (scores, winner, trace-event SHA-256, per-player observation-event
   SHA-256, with non-vacuity controls) and an instrumented read oracle
   (every declared name read, nothing undeclared touched, planted controls
   both directions) — the review round reproduces the differential in its
   own worktree. The IR emits the declared types as strings today; the
   change keeps the string form, so no existing IR golden moves (verified,
   not assumed, by the review).
3. **Info sets derive** — declaration-only surface over a signature
   `CALL_SIGS` already carries byte-for-byte; the both-ways shape check
   forces the declared `Sig` equal to the implementation's, facets
   included, so `coerce_args` hands `gin.py` the identical frozen element
   tuple under either regime; nothing new is emitted;
   `tests/openspiel_ready/test_gin_rummy.py` untouched and green. No debt
   for `docs/kernel-migration.md`.

**Corpus lockstep** (operating rule 2): `docs/games/gin-rummy.cardlang`
gains the block; its legacy `PRIMITIVE_READS` row, `ROW` binding and ten
dispatch arms delete per the stage recipe (ten names move to
`DECLARED_ONLY_CALL_FUNCS`; gin has no walled-namespace survivor).
`gin-rummy.md` is a prose-only twin (pinned in `PROSE_ONLY_TWINS`) — no
fenced block to keep in lockstep; its "Notes for the executable spec" are
re-read for sentences that go false. Glossary: **Collection Type** minted
(`docs/glossary/collection-type.md`), the `type` reserved-words row gains
`collection type`, and `type.md` / `parameter.md` / `primitives-block.md`
gain the cross-reference. Prose sites that go false and are rewritten in
the change: `primitives_block.UNDECLARABLE_TYPE_CONSTRUCTORS` (the
`TCollection` row leaves; the `TStruct` row's citation is CORRECTED —
issue #473 is cribbage's; the three remaining type walls move to one
sibling issue filed by the change), the `DECLARABLE_BUILTIN_TYPE_NAMES`
comment, `resolve._check_primitives_block`'s "#472" message,
`tests/test_primitives_block.py`'s ledger sentence "a declared Primitive
cannot be a `where jointly` predicate at all", `docs/design-notes/
primitive-sidecars.md` section 2's type list, `n.Parameter` /
`n.PrimitiveDecl` docstrings, and `tests/test_type_name_positions.py`'s
ledger, whose "Nine cells today" / "9 positions x 13" is a stale count
(the scrape derives 11 and 143 on main) — rewritten as the derivation.

**Witness:** gin-rummy, in the same change (witness-in-change — the
construct never exists corpus-unused).

## Gate record (cardlang-planning)

- **Gate 1 (owners):** Hoyle (Merge Lane A, the sentence) and the
  Architect (the type system, the pass Contracts, the IR, the boundary
  pins) — both counsels below. Settled law read: decisions.md "Typed
  object model" (angle brackets are the language's generic convention),
  "Joint-predicate selection" (`cards` is the candidate set; the
  per-predicate codec), "Surface totality", "Closed-domain completeness",
  "Allow-list, never deny-list", "Meld groups: flattened zone families"
  (a `Collection<Card>` state row is cards outside a zone — designed
  refusal at P1/P2), the primitives-block sections. Glossary lacks the
  word: the mint is a plan step. Ordering: #472 sits on the stage-3b
  closing path (#143's 3b line).
- **Gate 2 (classification):** grammar surface (the entry's two type
  slots) + parse builder + resolve (a shape check replacing the name
  check; the entry-only twin; the constructor word reserved) + typecheck
  (the declared-`Sig` derivation gains the element allow-list) + IR (no
  schema change; string form) + runtime pins (re-derived from the declared
  table) + native registry (`DECLARED_ONLY_CALL_FUNCS` gains gin's ten;
  the element registry is minted) + corpus game + tests/grid. The
  surface-totality audit fires; Gate 4 applies.
- **Gate 3.5 (reachability):** #472 is R2 (anyone migrating gin meets the
  refusal by name) and the fix is proportionate — it unblocks 1 of the 3
  legacy holdouts and the stage-3 legacy-table deletion behind them.
  Classes found en route are routed, not absorbed: #539 (a keyed map
  passed to a collection parameter checks clean and the Primitive answers
  on the player ids — bug R2, executed on gin's legacy path, NOT this
  change's to fix), #541 (a struct named after a built-in type is
  accepted and then silently unusable — bug R2, executed; the Architect
  counsels sweeping the class IN this change, since the reservation
  registry is touched anyway for the constructor word and the corpus cost
  is zero; Hoyle offered sweep-or-file; the operator decides), #540 (four
  unpinned copies of `NAME`'s exclusion list — R4; no keyword is minted
  here).
- **Gate 4:** the framing check ran 2026-09-02 fresh-context over the
  whole `cardlang/` package (ten executed probes); its diff against the
  author's provisional twelve axes yielded ~14 cells, recorded in the
  accepted domain below; every expected outcome is authored after that
  diff; the grid is materialized red before implementation.

## The ruled construct (Hoyle's sentence, the operator's to ratify)

```
  primitives {
    gin_valid_meld(cards : Collection<Card>) : Boolean
    gin_arrange_ok(p : Player, cards : Collection<Card>) : Boolean
                                                             reads hand[p], taken[p]
    ...eight scalar siblings, reads derived from cardlang/runtime/gin.py...
  }
```

- `Collection<Card>` in a `primitives { }` entry's two type slots and
  nowhere else — the type's existing name in decisions.md and in every
  diagnostic `typecheck._type_name` prints.
- Element allow-list of one, `Card`, stated as the block's own registry
  beside `DECLARABLE_BUILTIN_TYPE_NAMES` and pinned. `Collection<Player>`
  (the checker mints it for `all players`; no registered signature takes
  one) — wall, `blocked:needs-witness`, reopening on the first signature
  handed a seat set. Other elements, nesting, optional element, optional
  collection, keyed form, zone facet: inexpressible by construction (the
  element slot is a bare NAME; the spelling does NOT reuse the zone
  `type_args` production). "A collection is never optional" is stated at
  the construct as designed (counseled) — the runtime reason: an optional
  wrapper breaks `coerce_args`' dispatch and dies at the boundary.
- The return slot admits the spelling at the gate and the both-ways shape
  check refuses every concrete entry (no implementation returns a
  collection) — the `TCell` precedent, both-slots symmetry kept.
- Every other type position refuses by ONE parse-time
  reject-with-replacement twin ("a collection type (`Collection<Card>`)
  is spellable in a `primitives { }` entry only") — never the "unknown
  type" voice; the phrase form `collection of Card` gets its own teaching
  twin naming the ruled spelling. Positions and verdicts (the derived
  13-position domain — `tests/test_type_name_positions.py`'s eleven plus
  `require_decl` and the zone `type_ref`): P10 primitive parameter
  IMPLEMENTED; P11 primitive return admitted-then-shape-refused; P3 move
  parameter WALL (reopens on Cassino's builds — a set decision that is not
  a transfer); P4 procedure / P5 rule parameters refused by their existing
  allow-list Owner Guards (cited, not re-guarded); P6 function parameter
  WALL (reopens on an encoder-enumerable DSL joint predicate); P7/P8
  outcome payloads WALL; P1 state row / P2 struct field DESIGNED refusal
  for `Card` (the group is the zone); P9 struct-literal head is not a
  type slot (it is where #541 bites); `require_decl` refuses with the
  RIGHT reason (today it parses `Collection<Card>?` and refuses as "a
  state type takes no type argument"); zone `type_ref` (which parses the
  tokens today) stays refused, pinned.
- The constructor word `Collection` is a NAME, not a keyword, not a member
  of `KNOWN_TYPE_NAMES` (bare `Collection` is refused: "takes an element
  type — write `Collection<Card>`"); it is reserved against position
  names, state names and `type` heads in-change (#541 for the class).
- The jointly binder is settled law: `cards` binds `TCollection(TCard())`
  and the ordinary call check applies; the codec is found by name under
  either regime.

## The accepted domain statement (post framing-check diff)

Axes, each with its defining site — the grid derives from these, never
from the Owner Guard's existing coverage:

1. **Type-spelling positions** — every grammar production naming
   `type_name` / `payload_type` (`tests/test_type_name_positions.py`'s
   scrape, widened so a primitive-slot production built beside
   `payload_type` stays visible) plus the two carriers outside it:
   `require_decl`'s own inline `NAME [type_args] ["?"]` and the zone
   `type_ref`. 13 positions x the spelling family.
2. **Spelling family at the entry slots** — bare NAME, `NAME?`,
   `Collection<Card>`, and the reject family: `Cards`, `Collection`,
   `collection of Card`, `Collection<player>`, `Collection<Card>?`,
   `Collection<Card, Card>`, `Collection<Collection<Card>>`,
   `Collection<Suit?>`, `Collection<Player>` (the wall's cell), plus the
   adjacency cells: `>=` fusion at the default twin (`: Collection<Card>=
   0`), `> reads`, `>)`, `>,`, trailing `//`, `Hand<Card>` at a zone.
3. **The constructor partition** — `get_args(types.Type)` x {spelled /
   positively excluded / unclassified}; `TCollection` leaves the exclusion
   table and `_reachable_type_constructors` derives reachability THROUGH
   the spelling (so a future element lands as an uncovered row that fails
   loud); the three walls' rows cite the sibling issue.
4. **The element registry** — the block's `Card`-only allow-list, enforced
   at BOTH sites: resolve's declarable check (now a shape check) and
   `typecheck.declared_primitive_sigs` (whose `TypeEnv` carries no
   structs/directions — an unknown element name would `type_from_name` to
   `TAny`, the permissive-top class at the element position;
   `tests/test_permissive_top.py`'s per-module `TAny()` count is the
   guard).
5. **Consuming layers** — parse builder (`_primitive_decl` selects the
   return type as the one bare string among the children; the string form
   keeps it — Architect); resolve; typecheck (shape check by `Sig`
   equality, facets included); IR (`ir._primitives` emits the string;
   `test_ir_schema_version`'s key/tag scrape untouched); runtime
   (`reads.coerce_args`' `TCollection` arm unchanged); the renderers that
   spell declared types back out (`_render_sig`, the reject twins' quoted
   `return_type`, `_block_facts`' `(name, type_name)` tuple, the
   regime-product harness `_SPELLINGS`/`_ASSIGNMENTS`, and
   `test_every_declarable_type_name_is_spellable_in_both_slots`, which
   gains a shape axis).
6. **Pairwise: value shapes at a collection parameter** — a zone
   (`hand[p]`, zone facet stripped to elements), a card query, a list
   literal, the jointly binder (the four shapes the boundary names); the
   keyed map (#539's cell — `xfail(strict, raises=...)` citing #539, NOT
   this change's fix); the `ChipStack` `Collection<Any>` content
   (recorded: `TAny` element absorbs, #116's class).
7. **Pairwise: a collection RETURN x its consumers** — walled by the shape
   check (no implementation returns one); the wall's cell records the
   fan-out (`tests/test_movement_verbs.py` / `test_cell_queries.py` are
   the precedent for when it opens).
8. **Name-keyed registries a collection entry joins** —
   `DECLARED_ONLY_CALL_FUNCS` (ten names), `joint_codec_function` (by
   name; the ActionSpace cell: a declared game rooting `where jointly` in
   a declared entry builds its space and PLAYS — the 3a ledger's
   "cannot run" cell, now runnable), the flavor partition (`DECK_ONLY`),
   the boundary pins `tests/test_native_call_boundary.py::_ZONE_PROBES` /
   `test_no_native_param_demands_a_zone` and
   `test_primitive_narrowing::test_collection_args_are_frozen_at_the_call_boundary`
   — today derived from `CALL_SIGS`; re-derived from the declared table
   (`implementation_sig`, the column that survives the stage-3 deletion)
   so the first declared-only collection parameter is probed.
9. **The library tier** — a collection spelling in a library item's
   parameter is a `_SlotLeak` (libraries cannot declare blocks): refused,
   cell in `tests/test_family_libraries.py`'s `_SLOT_LEAK` rows.
10. **Reserved words** — no keyword minted; the constructor word reserved
    against positions / state / `type` heads (#541 cited); the
    `STRUCT_TYPE_NAME` list and `_<WORD>_KW` terminals untouched;
    `test_keyword_anchoring` unaffected; the explicit-ambiguity probe on
    the entry's `= expr` twin (an angle-bracket type meeting a following
    comparison — the fused `>=` cell).
11. **Corpus** — gin-rummy only (derived: the `CALL_SIGS` collection census
    is `top_of`, `bottom_of` (Builtins, never declared) and gin's two);
    the ten declaring games re-parse under the widened grammar and
    exercise nothing new; the corpus ambiguity budget stays zero.
12. **Neutrality instruments** — full-width goldens (every other game); the
    substitute differential + read oracle for gin (goldenless).

Recorded, not cells (the framing check's UNSURE items, each with its
home): a declared `Card`/`Collection<Card>` parameter in a PIECE game is
admitted at the block with no flavor check on declared types — the scalar
case is pre-existing; the plan records it for the implementer to confirm
designed-or-not with a probe and file if not; the `_python_type` skip for
collections in `test_signatures` (annotation `list[Card]` vs the tuple
passed) — pre-existing looseness, R4, recorded in the change's ledger;
the argument channel (#471's scope question — a collection ARGUMENT
carries any zone's contents unbounded by the `reads` clause) — a comment
on #471, not this change's; the flavor quirk (a piece game's jointly binder
is `pieces` while the only content type NAME is `Card`) — recorded.

## The grid frame (materialized red before implementation)

Owner module: `tests/test_primitives_block.py` gains the spelling-family x
slot cells, the element cells, the ActionSpace cell and the freeze cell;
`tests/test_type_name_positions.py` gains the `Collection<Card>` column
across its derived positions (its `_outcome` classifier gains the twin's
token); `tests/test_native_call_boundary.py` re-derives its probes from the
declared table; `tests/rejections/primitives_*.cardlang` gains the misuse
probes with their `.expected` twins; `tests/test_family_libraries.py` gains
the library-tier leak row. Born-red set: every accept cell for the two
entries, the ActionSpace cell, the partition pin (reddens when the
`TCollection` row leaves the table), the positions column. Born-green pins
name their reddening mutation. Cells whose outcome is nobody's decision go
to the tracker, never guessed into the grid.

## Delivery shape

**One PR** (Merge Lane A, Ben merges): the surface (the entry-slot type
production and its two twins), the guards (shape check, element registry,
constructor-word reservation, `require_decl`'s right-reason refusal), the
grid and rejection corpus, the glossary mint, the prose rewrites, the
boundary pins re-derived, the sibling issue for the three type walls (with
the `TStruct` citation corrected), the positions ledger's stale count
rewritten — **and gin migrated in the same change** per the stage recipe
(entry-grain reads derived from `cardlang/runtime/gin.py`, never from the
counsel; row/ROW/ten arms deleted; ten names to `DECLARED_ONLY_CALL_FUNCS`;
codecs reached by name; the jointly path played under the declared
regime). Chain: plan doc as the branch's first commit -> Opus implements
red-first -> adversarial review with executed probes (the review reproduces
the gin differential in its own worktree) -> fix round -> PR -> Codex
(Ben's spend) + CI -> Ben's Lane-A merge. Closes #472. Part of #142.

## The operator's decisions (from both seats)

Hoyle's three: (1) the angle-bracket spelling `Collection<Card>` over the
phrase `collection of Card` (counseled: angle brackets); (2) whether the
twelve non-entry positions refuse with the ONE teaching twin (counseled) or
a bare syntax error; (3) whether "a collection is never optional" is a
designed rule stated at the construct (counseled) or an open issue.
The Architect's four rulings (all counseled A): (a) the entry's two slots
take their OWN production family (`primitive_param` / `primitive_type`)
referencing neither shared type production — a shared derivation would be
an Earley ambiguity in the entry's own slot, which rules Hoyle's "build on
`payload_type`" alternative out; the teaching twin lands on BOTH
`payload_type` and `type_name`, the phrase twin on `primitive_type` alone,
no twin on `require_decl` / zone `type_ref` (their refusals are the zone
registry's, pinned as cells); (b) the spelling rides as a STRING on the
existing `Parameter` / `PrimitiveDecl` nodes with ONE decomposition
`(base, optional, element)` owned by the leaf, `_param_type` routing every
host through it, the Type conversion staying at `type_from_name` — a
structured node is rejected (touches the IR value, the twin tuple, and
every bare-name comparison, on a two-entry witness); (c) three pins
re-point in this PR so the next thing lands red: the positions scrape
widens to all three type-carrying nonterminals AND gains the reverse
direction (a gridded production that is not a scraped carrier is red),
its `_outcome` classifier becomes an allow-list that RAISES on an
unrecognized message (today it reads silence as admit), the constructor
partition derives reachability through the block's whole spellable set,
a NEW pin holds the element allow-list equal to the element constructors
derived from `implementation_sig` over `PRIMITIVE_IMPLEMENTATIONS`
(`{TCard}` today), and the boundary-freeze pin reads the Builtin half of
`CALL_SIGS` unioned with `implementation_sig` now, so the stage-3 deletion
changes nothing there; (d) the reserved-name class is SWEPT NOW: `type`
declarations become a fourth reservation site and the constructor word a
registered source. The ActionSpace cell is a SYNTHETIC declared game
rooting `where jointly` in a declared entry that PLAYS to a meld-decided
score (true and false witnesses), beside the corpus proof.

**The operator decides** (the sitting's bottom line, written by the
Architect): sweep-now versus file for the reserved-name class (#541);
the string carrier (counseled) versus a structured type node (rejected,
priced); whether the two instrument repairs — the two-directional scrape
and the allow-list classifier — ride this PR or split out ahead of it;
plus Hoyle's three above. The strongest against-case from either seat is
Hoyle's: a generic with one instantiation, whose next element reopens the
audit at every position the spelling reaches — its cost a five-axis grid,
a reserved constructor word, and a re-parse safe only while a scrape holds
the decomposition to one site.

## Hoyle's counsel (2026-09-02, issue #472 — the collection parameter; attaches per docs/harness.md "The Language Owner")

**Headnote.** Gin Rummy waits on one missing spelling, and the ruled sentence is, verbatim: `gin_arrange_ok(p : Player, cards : Collection<Card>) : Boolean reads hand[p], taken[p]`, with its sibling `gin_valid_meld(cards : Collection<Card>) : Boolean` — a type spelled `Collection<Card>` in the two type slots of a `primitives { }` entry, and nowhere else. It is not a new name: the spec already calls the type `Collection<Card>`, and the checker already prints `Collection<Card>` in its own error messages today, so a designer who reads the diagnostic and writes the declaration writes the same word. The losing rival is the issue's own spelling, `collection of Card` — it reads aloud better, but no declaration in this language spells a type as a phrase, `of` already carries three meanings in expressions, and it would put a second spelling beside the one the checker prints; it earns a rejection that teaches the ruled form, not a life. The cheap rival the operator should see priced is a bare `Cards` name added to a table with no grammar change at all — rejected because `cards` is already a keyword one letter away, a plural-as-type does not compose, and it too is a second spelling. This is Merge Lane A: the grammar widens by one angle-bracket spelling in the entry's two slots plus one reject-with-replacement twin for the phrase form, and every other place a type can be written stays unable to spell it. Corpus: 1 of 31 game files moves (gin-rummy.cardlang, witness-named, landing in the same change as the surface); 10 of 31 games declare a block today and 11 will; gin is 1 of the 3 games still on the legacy table, its block has 10 entries of which 2 need this spelling, and 6 joint-selection sites call them. Two settled commitments are kept and one sentence goes false: both entry slots keep taking the same spellings (the return slot admits it and the shape check refuses it, because no implementation returns a collection — the same treatment a board cell gets today), and the grid's recorded claim that a declared Primitive can never be a joint predicate becomes untrue and is rewritten. One recorded citation is wrong and is corrected: the exclusion table sends the struct wall to the cribbage issue. The element is `Card` alone; a collection of players, an optional collection, a nested one, a keyed one, and a collection stored in state are each refused loudly — walls with a named reopening event, or designed constraints stated at the construct. Information sets do not move: the declared signature is forced equal to the one the legacy table already carries, so the Python receives the identical frozen cards under either regime, nothing new is emitted, and the proofs and full-width goldens for gin stay byte-identical. Bottom line: adopt `Collection<Card>` in the entry's two slots with a one-member element list; the strongest reason against is that this admits the language's first parameterized value type into the declaration register on a witness of two entries in one game — a generic with one instantiation, whose next element reopens the audit at every position the spelling reaches — and its cost is a five-axis grid and a reserved word where a table entry would have done; the operator decides three things: the angle-bracket spelling over the phrase, whether the other type positions refuse it with one teaching message (counseled) or a bare syntax error, and whether "a collection is never optional" is a designed rule (counseled) or an open issue.

### 1. The sentences

The ruled surface in situ — gin's whole block, the two collection entries among their eight spellable siblings, placed beside `card_points` where the other declared games place theirs (`docs/games/pinochle.cardlang` line 45, `canasta.cardlang` line 114):

```
game GinRummy {
  players: 2
  direction: clockwise
  max_length: 30000
  cards: standard52
  ranking: K Q J 10 9 8 7 6 5 4 3 2 A
  card_points { ... }

  primitives {
    gin_deadwood(p : Player) : Integer                       reads hand[p], taken[p]
    gin_can_knock(p : Player) : Boolean                      reads hand[p], taken[p]
    gin_knock_ok(p : Player, discard : Card) : Boolean       reads hand[p], taken[p]
    gin_valid_meld(cards : Collection<Card>) : Boolean
    gin_arrange_ok(p : Player, cards : Collection<Card>) : Boolean
                                                             reads hand[p], taken[p]
    gin_can_declare(p : Player) : Boolean                    reads hand[p], taken[p]
    gin_can_declare_free(p : Player) : Boolean               reads hand[p], taken[p]
    gin_lay_ok_a(card : Card, knocker : Player) : Boolean    reads meldA[knocker]
    gin_lay_ok_b(card : Card, knocker : Player) : Boolean    reads meldB[knocker]
    gin_lay_ok_c(card : Card, knocker : Player) : Boolean    reads meldC[knocker]
  }

  zones { ... }
```

Read aloud: "gin_arrange_ok of a player p and a collection of cards is a Boolean; it reads that player's hand and their taken card." The parameter orders are `CALL_SIGS`'s (`cardlang/builtins/signatures.py` lines 120-135), which the shape check enforces. The reads are illustrative, derived this sitting from `cardlang/runtime/gin.py` (`_hand` reads `hand[p]` and `taken[p]`; the three lay-off guards read one meld family each; `gin_valid_meld` reads nothing — it is pure over its argument, and a reads-less entry is grammatical, `[primitive_reads]` being optional); the migration PR derives them from the module, never from this counsel. The legacy row is module-grain (`reads.py`: `hand, taken, meldA, meldB, meldC`, no state variables), so no entry needs an `in <phase>` tail.

The six call sites the spelling unblocks are already written: `where jointly gin_arrange_ok(actor, cards)` at gin-rummy.cardlang lines 263-271 and `where jointly gin_valid_meld(cards)` at lines 295-303. None changes.

**(a) Rivals weighed, each read aloud:**

- `collection of Card` — "cards, a collection of Card." The issue's own spelling (its Detail), the exclusion table's own reason string (`primitives_block.py` line 305), and the existing pin's probe sentence (`test_a_collection_type_has_no_spelling_at_all`). Rejected: every declaration row in this language spells a type as a Name with `?` or `<…>` (`state_decl`, `struct_field`, `parameter`, `require_decl`, `zone_decl`); `of` is an anchored keyword with three expression senses already (`number of`, `sum of … over`, `<rank> of <suit>`) and a fourth in `offer … one of`; a lower-case `collection` would be the only lower-case type word in the language, and in this language's own conventions a lower-case word in a type slot is an index domain (`Hand<player>`); and the checker prints `Collection<Card>` (`typecheck._type_name`, probe 2026-09-02: "gin_valid_meld() expects Card, got Collection<Card>"), so the phrase would be the second spelling principles.md calls a defect. It is exactly the arrow's case from the 3a counsel — "the spelling the design note sketched before the block had a surface, so it is the first thing a reader of that note writes" — and earns the same remedy: a reject-with-replacement twin naming `Collection<Card>`.
- `Cards` — "cards: Cards." The shortest, and Lane B (one table entry). Rejected: `cards` is already a keyword (`_CARDS_KW`, the content noun and the joint binder), so `Cards`/`cards` would name two things one letter apart, lexed differently by case alone; a plural-as-type does not compose (`Players`? `Integers`?) and is flavor-bound where the type is not (a piece game's noun is `pieces`); and it is a second spelling beside the printed one.
- `Card[]` / `[Card]` — the mainstream array spelling (principles.md, "Mainstream syntax unless the domain pushes back"). Stillborn: square brackets are the index spelling (`index: "[" NAME "]"`; `score[player] : Integer`), so `cards : Card[]` reads as an empty index on a row.
- `Zone<Card>` — the library's own type algebra spells every zone type so (library.md, `type Hand<Owner: Player> = Zone<Card>`). Rejected: it would lie about what arrives. The boundary strips a zone to its elements (`reads.coerce_args`, the `TCollection` arm; the declared facet is `zone=False` by construction), and the joint `cards` binder was never a zone. `Collection` says what the parameter is.
- `ZoneContents` — principles.md lists it among the built-ins. Same objection, and it names no element type.

**Adjacency and shared-delimiter hazards for the misparse prober:** `<` and `>` are the comparison terminals (`COMP_OP`, grammar line 704) — no expression can follow a type in the entry's slots, so no ambiguity there, but the `>=` fusion is live in the one place `=` can follow a type: the default reject twin (`: Collection<Card>= 0` lexes `>=`) must still reject loud, proven on the fused token stream, not only the spaced one. `Collection<Card>?` — the optional collection: made inexpressible (the element slot and the `?` arm do not compose), and DESIGNED, see section 4. `Collection<Card?>`, `Collection<Collection<Card>>`, `Collection<Card, Card>`: inexpressible — the element slot is a bare NAME, and the spelling must NOT reuse the zone `type_args` production (which admits a comma list), so the comma form and every keyed form stay unspellable by construction. `Collection<player>` — the plausible confusion with `Hand<player>`, a lower-case index domain where an element type belongs: refused by name with a message that says the argument is an element type. Bare `Collection` and bare `Cards` — today "may not spell … issue #472" (probes C, D); after, "`Collection` takes an element type — write `Collection<Card>`". `Hand<Card>` at a zone — the reverse confusion — is refused today ("unknown owner 'Card'", probe) and a grid cell pins that it stays so. `> reads`, `>)`, `>,` and a trailing `//` comment after `>` are the boundary tokens to probe. No keyword is minted: `Collection` stays a NAME, `of` already exists anchored, and the keyword-fusion sweep has nothing new to cover.

### 2. Precedent

Extends, by name:

- **decisions.md "Typed object model"** — "User-defined types may be parameterized with the same angle-bracket convention as built-in generics"; `Resource<Type>`, `Zone<Contents>`. Angle brackets are the language's stated generic convention.
- **decisions.md, the `let` bindings paragraph** (line 1269): "a query result or list literal types `Collection<Card>` too" — the spec already names the type by this spelling; **"Boards and cells"** does likewise (`Collection<Cell>`).
- **decisions.md "Joint-predicate selection"** — `cards` is "the candidate set, a card collection"; the per-predicate codec (`joint_codec_function`, keyed by the predicate's root call, `gin_arrange_ok` → the 329-meld universe).
- **`typecheck._type_name`** — the one rendering site, `Collection<{element}>`; and `types.py`'s own docstrings (`Collection<Card>`, `Collection<Integer>`, `Collection<Collection<Card>>`).
- **docs/design-notes/primitive-sidecars.md §2** — "a primitive's signature names value types (`Card`, `Player`, `Integer`, card collections)".
- **The 3a counsel** (docs/plans/2026-08-28-primitives-block-stage3a.md) — the colon-row register, the both-slots symmetry (`test_every_declarable_type_name_is_spellable_in_both_slots`), the reject-with-replacement twin mechanism (colon, arrow, default), and the TCell precedent in the 3a ledger: "reachable at the TYPE-NAME gate and unusable in a concrete entry: no registered implementation takes one, so the shape check refuses every `cell`-typed declaration."
- **The phase-scoped-reads counsel** (docs/plans/2026-08-30-phase-scoped-reads.md) — witness-in-change: the construct never exists corpus-unused.
- **The both-ways shape check** (`typecheck._check_primitive_signatures`) — dataclass equality over `Sig`, facets included: it is the Owner Guard that pins a declared `Collection<Card>` to `TCollection(TCard(), key=None, zone=False)`, and would refuse any spelling that produced another facet.
- **Glossary** — [[primitives-block]] and [[reads-clause]] unchanged in law; [[parameter]] (the node stays one — its tripwire is about fields, and the grammar may grow a sibling production without touching the node); [[zone]] ("a named ordered container", the contrast); [[candidate]] ("a card/subset"); the reserved word [[type]].

**The glossary lacks the word; the change mints it.** Entry: **Collection Type** (the reserved word `type` qualified, per the preamble), with the `type` reserved-words row gaining `collection type` beside `struct type · zone type`. What it may mean: the checker's `TCollection` as a declared type — a value collection of one element type, spelled `Collection<Card>` in a Primitives Block entry and in every diagnostic that prints the type; what a zone's contents, a card query's result, a list literal, and the joint-selection `cards` binder all evaluate to, and what a Primitive's collection parameter receives — the frozen elements, never the Zone that held them; a declared spelling carries no key and no zone facet (the checker's `key`/`zone` bookkeeping is about how a value may be addressed, never about what a parameter receives); `Card` is the one spellable element; a collection is never optional — `is empty` is its absence. Contrast the zone type (`Hand<player>`), whose angle-bracket argument is an index domain, not an element. Home: `types.TCollection`, the new grammar production, the block's element registry.

**Cut against, or going false, all rewritten in the same change (prose states what is):** the 3a grid ledger's domain sentence — "a declared Primitive cannot be a `where jointly` predicate at all … the joint-codec pairing obligation … is 3b's to meet, not a cell this grid can run" (`tests/test_primitives_block.py` lines 106-110) — becomes false and the cell becomes runnable; `UNDECLARABLE_TYPE_CONSTRUCTORS["TCollection"]` leaves the table, and the partition pin (`test_the_type_constructor_partition_is_total`) reddens until `_reachable_type_constructors` derives reachability through the new spelling — the red-first the audit wants; `test_a_collection_type_has_no_spelling_at_all` inverts into the twin's rejection test; `n.Parameter`'s and `n.PrimitiveDecl`'s docstrings describe the type-name string's shape and must describe the new one. **One wrong citation, corrected:** `UNDECLARABLE_TYPE_CONSTRUCTORS["TStruct"]` cites issue #473 — that issue is cribbage's two site-read pegging scorers (`gh issue view 473`, read this sitting); #472's own body owns TStruct, TLine and TDir. The operator's brief relayed the table's claim; the table is wrong.

**The reserved-words check:** no new keyword, so the `_<WORD>_KW` anchoring recipe and `STRUCT_TYPE_NAME`'s exclusion list are untouched. What IS at stake is the constructor word as a NAME in the game's own namespaces. Probed 2026-09-02: `type Collection = { x : Integer }` and `state { Collection : Integer = 0 }` check clean today — and so does `type Card = { x : Integer }`. Built-in type names are reserved against position-domain names (`resolve.POSITION_NAME_SOURCES`, "a built-in type name") but not against `type` declarations. That is a class, not an instance: sweep it (decisions.md "Closed-domain completeness", sweep the class before patching the instance) rather than reserve `Collection` alone — the change either reserves the whole `KNOWN_TYPE_NAMES` set plus the constructor word against `type` and state names, or files the class and reserves the constructor word with a comment naming the issue. It must not leave `x : Collection<Card>` readable two ways in a game that declares `type Collection`.

### 3. Corpus impact

Measured 2026-09-02 from the tree (`ls docs/games/*.cardlang`; `grep -ln "primitives {" docs/games/*.cardlang`; `PRIMITIVE_IMPLEMENTATIONS`; gin-rummy.cardlang):

- 31 game files; 10 declare a block (belote, canasta, five-hundred, french-tarot, holdem, holdem-heads-up, pinochle, seven-card-stud, skat, tichu); gin makes 11.
- Gin is 1 of the 3 games still on the legacy table — gin (#472), cribbage (#473), coup (the `coup_game_summary` eviction) — per the stage-3b plan's closing steps. After this change, 2 remain.
- Gin's 10 registered entries: 8 spellable today, 2 not (`gin_valid_meld`, `gin_arrange_ok`); 6 `where jointly` call sites, 3 per entry, all `chosen some cards` selections in the showdown vocabulary (`declare_meld`, `declare_meld_d`).
- **Lockstep: 1 of 31 files moves** — gin-rummy.cardlang gains the block and its legacy row, `ROW` binding and dispatch arms delete per the stage recipe; gin-rummy.md carries no fenced block (its executable spec is the `.cardlang`), so the twin pin has nothing to compare and the prose note already names both predicates. The surface lands **with gin migrated in the same PR** — the construct never exists corpus-unused.

The witness is forced, not speculative: the issue is R2, the block refuses the two entries by name today, and "a game declares all or nothing" (`primitives_block.regime`) keeps all 10 on the legacy table until the two can be written.

For the walls, the pipeline (docs/games/_candidates.md) names one shape: Cassino's builds — "creating multi-card combinations on the table" — the nearest candidate for a card-set decision that is not a transfer (section 4, the move-parameter wall). No candidate names a Primitive taking a player set, returning a card set, or taking a struct.

### 4. The totality edge

**(b) The positions.** The closed domain is `tests/test_type_name_positions.py`'s derived axis — eleven type-spelling positions (P1 state row, P2 struct field, P3 move parameter, P4 procedure parameter, P5 rule parameter, P6 function parameter, P7 define payload, P8 outcome payload, P9 struct-literal head, P10 primitive parameter, P11 primitive return) plus the library-only `require_decl` and the zone `type_ref`, which that module records as a different domain. The spelling is grammatically reachable today at none of them (every `Collection<Card>` probe at P1-P8 and P10-P11 dies "No terminal matches '<'"; `require_decl` and `type_ref` accept the tokens and resolve refuses — "unknown zone type 'Collection'"). Verdicts, one per position:

- **P10 primitive parameter — implemented.** The witness.
- **P11 primitive return — admitted at the gate, refused by the shape check.** The both-slots commitment is kept (a spelling legal in one slot and not the other is "a surface a designer cannot predict", the 3a test's own words); no registered implementation returns a collection, so `_check_primitive_signatures` refuses every concrete entry — the TCell precedent exactly. The ledger records that no execution witness exists for a collection return; the day an implementation returns one, the witness is owed. Not deferred work, so no issue: an empty registry, not a gap.
- **P3 move parameter — refused, wall with a named reopening event.** A card-set decision is the joint selection's job (`where jointly` is the language's one spelling of "choose a subset"), the action encoding has no subset block outside the joint codec, and `_check_move_params` is an allow-list. Reopens on a game whose set decision is offered as a move and cannot be a transfer — Cassino's builds, named.
- **P4 procedure parameter, P5 rule parameter — refused by their existing allow-list Owner Guards** (`_PROCEDURE_PARAM_DOMAINS`, "extend when a game needs another"; `_check_template`'s Suit-only gate). Cited, not re-guarded (write-time triage: a second check over a condition already checked is the Shadow Guard rule's defect).
- **P6 function parameter — refused, wall.** The one a designer will want first: `function is_meld(cs : Collection<Card>) = …` as `where jointly is_meld(cards)`. Admitting it would give them a function usable everywhere except where they want it — an inline or DSL joint predicate has no registered codec and `ActionSpace.for_game` refuses it ("root the `where jointly` predicate in a registered call"). Reopens on an encoder-enumerable DSL joint predicate — the door roadmap.md already holds.
- **P7, P8 outcome payloads — refused, wall.** No corpus outcome carries a card set.
- **P1 state row, P2 struct field — refused; for `Card` a designed constraint.** decisions.md "Meld groups: flattened zone families": "Storing group state beside the cards would create a second source of truth … the group is the zone." A `Collection<Card>` state variable is cards outside a zone. Stated at the construct; re-asked only if a non-Card element ever lands.
- **P9 — not a type slot** (a struct-literal head names a struct); it is where the reserved-word question of section 2 bites.
- **`require_decl`, zone `type_ref` — unchanged refusals, pinned as cells:** the word gaining a meaning in the entry slot must not admit it here.

**How the eight refuse:** one parse-time reject-with-replacement twin on the shared type productions — "a collection type (`Collection<Card>`) is spellable in a `primitives { }` entry only" — rather than eight resolve arms, and never the "unknown type" currency (`_check_declared_type_names` answers "unknown type 'Cards'" for a bare name today; the positions ledger's own property forbids calling a spelled name unknown). For that to hold, the entry's two slots take their own production, so the twin and the real arm never derive the same string. Two pins to keep honest: `test_the_position_axis_is_the_grammar_s` scrapes carriers by the names `type_name|payload_type` — a new carrier referencing neither is invisible to it, so the scrape widens or the new production is built on `payload_type`; and the positions grid's `_outcome` classifier keys on message substrings ("syntax error", "unknown type", "domain", "may not spell") — the twin's message carries a recognized token or the classifier gains one, else a refusal reads as admit. The production layout itself (a string `type_name` carrying `Collection<Card>` as `Suit?` carries its `?`, versus a structured type node; the IR's `primitive_param.type` string; `_block_facts`' tuple) is the Architect's — Hoyle rules the sentence and the outcomes.

**(c) The facets.** `Collection<Card>` denotes `TCollection(element=TCard(), key=None, zone=False)` — the exact `CALL_SIGS` rows, so the shape check passes for gin and refuses any spelling that yields another facet. The element is an allow-list of one, `Card`, stated as the block's own registry beside `DECLARABLE_BUILTIN_TYPE_NAMES` and pinned (decisions.md "Allow-list, never deny-list"). `Collection<Player>`: the checker mints `TCollection(TPlayer())` for `all players` and `players where` (typecheck lines 658, 727), but no registered signature takes one (`CALL_SIGS`, grepped: the only collection parameters are `top_of`, `bottom_of`, `gin_valid_meld`, `gin_arrange_ok`, all Card) — wall, `blocked:needs-witness`, reopening on the first signature handed a seat set. Integer, Suit, Rank, Team, position and direction elements: no site mints a bare value collection of them (keyed state such as `score` carries a key) — same wall. Nesting, optional element, optional collection, keyed form: inexpressible (section 1). The zone facet is unspellable by construction, and rightly — the boundary's own residual (`test_no_native_param_demands_a_zone`) says a zone-handle parameter is a decision to be made on purpose. At a call, a `Collection<Card>` parameter accepts all four value shapes the boundary names — a zone (`hand[p]`), a query result, a list literal, the joint `cards` binder — because `coercible` compares elements only; nothing about that changes, the same rows type the same calls today.

**(d) The other three walls.** TStruct: no corpus game declares a `type` at all (decisions.md "Typed object model"), so no struct can reach a Primitive — stays walled; its citation moves from #473 to the right home. TLine, TDir: "no board game has a Primitive at all" (#472's body) — stay walled; reopening event, the first board game declaring a block. When gin lands, #472 as titled is closed and the three walls move to one sibling issue (kind `enhancement`; TStruct's witness nameable as a Bridge-style contract snapshot; the board pair's event as above), each reason string in the exclusion table citing the new number, the partition pin keeping them classified.

**(e) The jointly binder** — settled, and the typechecker's already. `cards` binds as `TCollection(TCard())` in the joint arm of `_check_stmt` (typecheck line 2907; resolve's binder registry, `content_noun(plural=node.joint)`), and the predicate's call is checked by the ordinary call check against the entry's `Sig`. Executed this sitting: a declared `gin_valid_meld(c : Card)` under `where jointly` fails "expects Card, got Collection<Card>" (probe K), and the same declaration fails the shape check against the implementation (probe F). The new surface only makes the matching declaration writable. The codec is found by the predicate's root name regardless of regime (`joint_codec_function`, `gin_arrange_ok | gin_valid_meld`), so a declared gin reaches its codec; a declared entry with no codec still meets the loud `ActionSpace` refusal.

**The grid frame** (axes derived in code, cells authored red first): spelling forms at the two entry slots (bare, `?`, `Collection<Card>`, and the reject family above) × slot; the thirteen positions × the spelling; declared shape × implementation shape (the collection param equal; `Card` in its place refused; a collection return against every registered implementation, refused); call positions of a collection entry × the four value shapes × regime (declared; legacy untouched — crossed only where an outcome could differ, and none should); the ActionSpace cell — a declared game rooting `where jointly` in a declared entry builds its space, the 3a ledger's runnable cell; the freeze cell — a declared collection parameter receives frozen elements, never a handle, reconciled against the declared table and not only `CALL_SIGS` (test_native_call_boundary's reconciliation quantifies over `CALL_SIGS`, whose Primitive half 3b deletes — name the registry the pin will read then); the partition pin red-then-green; the reserved-word cells (`type Collection`, `state { Collection }`) with the class finding filed; the adjacency cells of section 1.

**The most plausible misuse sentences, each proven loud in its layer:** `cards : Cards`; `cards : Collection`; `cards : collection of Card`; `cards : Collection<player>`; `cards : Collection<Card>?`; `seats : Collection<Player>`; `function is_meld(cs : Collection<Card>) = …`; `move_type declare(meld : Collection<Card>) { … }`; `state { melded : Collection<Card> = … }`; `cards : Collection<Card, Card>`; a declared `gin_valid_meld(c : Card)` (the shape twin, loud today).

### 5. The info-set bound

**(f) Do not move.** The construct is declaration-only surface over a signature `CALL_SIGS` already carries byte-for-byte: the shape check forces the declared `Sig` equal to the implementation's, facets included, so `coerce_args` freezes and hands `gin.py` the identical element list under either regime; the reads clause declares, entry-grain, what the legacy module row grants today; no zone, movement, or observation changes; nothing new is emitted. Proof, per the stage recipe: `tests/openspiel_ready/test_gin_rummy.py` untouched and the byte-identical full-width playout goldens (`CARDLANG_GOLDEN_SEEDS=full pytest tests/test_migration_characterization.py -q`). No debt to record in `docs/kernel-migration.md`. Two obligations for the implementing change: the entry-grain reads derive from `gin.py` and the migration PR proves them by playout (the 3a ledger's "does not prove" line — sufficiency of a declared read is a fact only running shows); and the joint-selection path is exercised under the declared regime by an executed playout, not a resolve-clean fixture — the accept cell plays.

### 6. Counsel

**For:** the sentence is the type's existing name in the spec and in every diagnostic, so no second spelling enters the language; the machinery beneath it is already total for the shape — the `CALL_SIGS` rows, the `TCollection` arm of `coerce_args`, the native-boundary probes, the jointly binder typing, the codec found by name — so the change is a spelling and a gate, not a mechanism; it lands 1 of the 3 legacy holdouts and puts the road to the legacy-table deletion two games from its end; and the twin turns the issue's own misspelling into a diagnostic that teaches the ruled form.

**Against, strongest:** this admits the language's first parameterized value type into the declaration register on a witness of two entries in one game — a generic with one instantiation. The honest shape of the surface is `Collection<Card>` over an element list of one; that reads as a generic and is not one, and every next element (Player is first in line) reopens the audit at every position the spelling reaches. The cheap rival exists and is real: a bare `Cards` name in a table, zero grammar, Lane B — Hoyle rejects it on the merits in section 1, but the operator should see it priced against a five-axis grid and a reserved word. A second honest against: the surface widens the type register in one construct only, and the eight refusals are walls a designer will stand at — the function over `cards` first — each a deliberate wall with a named reopening, but a wall.

**What Hoyle would do:** rule `Collection<Card>` in the entry's two slots, the element an allow-list of one stated as the block's own registry; keep both slots symmetric, the return refused by shape until an implementation returns one; refuse the other positions by one parse-time twin naming the entry, and give the phrase form its reject-with-replacement twin; state the designed constraints at the construct — no optional collection, no collection state for cards, no key or zone facet — and file the walls with their reopening events (Player and other elements; the move-type parameter, Cassino named; the function and payload parameters, the enumerable DSL predicate named); move the three type walls to one sibling issue with the struct citation corrected; sweep the reserved-name class rather than patch the word; land the surface with gin migrated in the same PR, full-width goldens and the OpenSpiel proofs untouched, the 3a ledger sentence rewritten, the glossary entry minted and the `type` row extended; route the production layout, the AST shape, the positions scrape's widening and the outcome classifier's new token through the Architect; and hand Gate 4 the section-4 frame with the grid red before a line of the implementation exists. Your servant keeps the seat for the Architect's half, which this counsel does not presume to rule.

## The Architect's counsel (2026-09-02, issue #472 -- the collection spelling in the `primitives { }` entry; two-persona sitting, Hoyle's surface rulings bind throughout; this seat writes last)

**Headnote.** Eight engine questions narrow to four rulings, and none of them moves an information set. First, the carrier: `Collection<Card>` rides as a STRING on the same parameter node every other declaration already uses, exactly as `Suit?` carries its question mark -- decomposed in one place, never sliced by the passes that read it. The entry's two slots take their own production, so the teaching refusal in every other type position and the real arm never derive one string; the one instrument that scrapes the grammar for type positions goes blind to the entry the moment that production lands and does not redden, so it widens and gains its missing reverse direction in the same change. Second, the refusal layers: the SHAPE (angle brackets anywhere but the entry; the phrase form; a comma, a question mark, a nested bracket) is the grammar's; the ELEMENT (anything but `Card`) is the resolver's, from a one-member list stated as the block's own registry; the FACETS (a keyed or zone collection) are unspellable by construction, and the declared signature is dataclass-equal to the implementation's only with the default facets -- executed, both directions. Third, three pins re-point so the next thing lands red rather than joining quietly: the constructor partition derives reachability through the block's own spelling set; a new pin holds the element list equal to what registered Python actually takes (one constructor, `Card`, across every registered Primitive today); and the boundary-freeze pin reads the implementation index through its one seam now, so the coming deletion of the signature table's Primitive half changes nothing in it. Fourth, one class swept now rather than filed: a game may declare `type Card = { ... }` today, the checker accepts it, and the struct is then unusable in every type slot -- the built-in wins silently -- so `type` declarations start asking the same reserved-name registry position domains already ask, with the constructor word added as a row. The rejected shape is a structured type node, or an arm on the shared payload production guarded by position at resolve: both are cleaner on paper and each touches the serialized IR, the twin-agreement pin, and every reader that compares a parameter's spelling to a bare name, on a witness of two entries. Newly impossible: a designer spelling a collection anywhere but an entry's two slots, with any element but `Card`, or with any facet; an engine author registering a Python Primitive over a collection of anything else without the element list, and a witness, admitting it first; the type-position classifier reading an unrecognized refusal as an admit. Newly required for the migrating agent: gin's block (2 of its 10 entries need the spelling; 6 joint-selection sites call them), the goldenless substitute differential, and a synthetic declared game that roots a joint selection in a declared entry and PLAYS. Measured: 10 of 31 games declare a block today, 11 after; 1 of 31 files moves; 3 of the 10 block games carry an IR golden and 0 of them move, because the IR already prints the type as a string. Information sets do not move: the same freeze arm hands the same frozen cards to the same Python, and the codec is keyed by the call's name, which no regime changes. Precedent standing: every citation established; no unverified lead is relied on.

**1. The decision.** Not the sentence, the element, or the walls -- Hoyle's, ruled. Four engine choices: (a) how the spelling is CARRIED -- a string on `n.Parameter`/`PrimitiveDecl.return_type` decomposed once, versus a structured node -- and which grammar production family owns the two slots, given that `parameter` and `payload_type` are shared with six other hosts; (b) which layer refuses each wrong thing (shape, element, facet) and in which channel; (c) what three registry-derived pins must quantify over -- the positions scrape, the constructor partition, the boundary freeze -- so a future element, a future constructor, and the 3b table deletion each land red; (d) whether the reserved-name class Hoyle found is swept in this change or filed.

**2. The law.** resolve's Contract: the ONLY pass that classifies names and settles declaration validity; `_check_primitives_block` already owns the entry's type-name gate ("its declared types against the spellable set") in the bag channel, and `_check_declared_type_names`' own docstring refuses to double-guard a host another Owner Guard already gates (move params by `_check_move_params`, procedure params by `_PROCEDURE_PARAM_DOMAINS`, rule params by `_check_template`) -- which is what prices any resolve-side refusal of the spelling at the other hosts. typecheck's Contract: inferred types are ephemeral and "a downstream consumer that needs a type is a signal to materialize it in this pass" -- `declared_primitive_sigs` is that sanctioned materialization, and it routes BOTH slots through `_param_type` -> `type_from_name`, so the block has exactly one Type-from-spelling derivation today; the ruling keeps it one. `primitives_block.py`'s Contract: a leaf holding names and classifications, "never types (`typecheck.type_from_name` is the one conversion site)" -- the element allow-list belongs there as a name registry; the conversion does not. parse's Contract: shape only, and its reject twins name the fix at a span -- the colon/arrow/default precedent. ir's Contract: carries resolve's facts, never re-derives; the `primitives` emitter prints `p.type_name` and `d.return_type` as strings, and the schema pin scrapes keys and kinds, not values (its own ledger records that residual). reads.py's Contract: the freeze is SIGNATURE-DRIVEN -- a `TCollection` param receives elements, deep-frozen; a `TAny` param passes raw. decisions.md "Typed object model": angle brackets are already the language's generic convention (`Zone<Contents>`; "User-defined types may be parameterized with the same angle-bracket convention as built-in generics"). "Joint-predicate selection": the subset universe comes from a per-predicate codec keyed by the predicate's ROOT CALL, loud when absent. "Meld groups: flattened zone families": the group IS the zone -- the designed reason a collection is never state or a struct field. "Surface totality": three states, misuse probes, and composition points enumerated at every consuming pass, pairwise. "Closed-domain completeness": derive, pin, refuse; the channel law; write-time triage; "Allow-list, never deny-list" (a consumer of a closed domain lists what it handles and fails loud on the rest); "Prefer the guard you cannot need" (the grammar refusing a combination outranks a pass refusing it); "Reachability ranks the work" (proportionality is called in planning, out loud). Prior rulings not re-litigated: 3a's front-end-owned derivation (resolve validates, typecheck materializes the Sig, the driver reads `rs.declared_sigs`); 3b-0's `implementation_sig` as the designed one-site seam for the signature table's move; the phase-scoped-reads ruling that `_block_facts` must carry what the twin pin needs to see.

**3. Precedent.** P2 (Area 1, nanopass): a fact materializes in the owning pass and is never re-derived -- the tell this ruling answers is the nine sites that today slice a trailing `?` off a type spelling (measured 2026-09-02: `domains.py` 319, 492; `typecheck.py` 493, 1062, 1501; `resolve.py` 1567, 5036, 6844, 7260), three of which read a block spelling; a second delimiter must not become a tenth slicing site. P4 (Area 2, Breazu-Tannen coherence): `coercible` compares collection ELEMENTS only, so every value shape a call can carry reaches the declared parameter through one relation -- executed below. P6 (Area 3): every new refusal message lands in the blessed-snapshot harness. P7: addressee, span, applicability -- a parse twin carries a span; the resolver's element refusal carries the entry's. P9 (Area 4, grammarware): the grammar is the single source and EVERY scrape of it is derived and pinned -- the positions scrape is such a scrape and is today one-directional. P11 (Area 5): a pin is trusted after it catches a planted fault -- the partition pin reddens first on the overlap, the element pin names its reddening registration, the freeze pin names its reddening deletion. P13 (Area 6): declared-once, emitted-uniformly is untouched -- nothing here emits. House precedent: `Suit?` on `Parameter` (the string carries its combinator; the consumers strip it); `TypeRef`/`type_args` on zones (the language's one structured type node, and why it is NOT reused: it admits a comma list and a VALUE argument, `Hand<player>`, with zone-registry semantics); the TCell precedent in the block grid's ledger ("reachable at the type-name gate and unusable in a concrete entry"); `_check_zone_type_names_are_not_taken` beside `POSITION_NAME_SOURCES` (the type namespace's reservation registry, asked by three of its four declaration sites). All established; no unverified mark relied on. Standing tensions: none live -- the P5/LSP tension is not touched.

**4. The options.**

*(a) The production layout.* **A (counseled): an entry-only production family that references neither shared type production.** `primitive_param: NAME ":" primitive_type` and `primitive_type: NAME "?" | NAME | NAME "<" NAME ">"` written out with their own aliases -- never `primitive_type: payload_type | ...`, because the teaching twin lands ON `payload_type` and a shared derivation would make the entry's own spelling an Earley ambiguity (two derivations of one string, the `q_any_player`/`q_any_domain` class). The entry and its two reject twins (`primitive_arrow_decl`, `primitive_default_decl`) all take `primitive_param`/`primitive_type`, or `gin_arrange_ok(...) -> Boolean` with a collection param dies at `<` instead of reaching the arrow twin's message (Hoyle's "each reject arm's tail admits the well-formed spelling" rule); the shared `_primitive_decl` builder body already makes the three read the same slots. The teaching twin `| NAME "<" NAME ">" -> collection_type_reject` goes on BOTH `payload_type` (reaching P3-P8 through their existing hosts) and `type_name` (P1, P2); the phrase twin `NAME _OF_KW NAME -> collection_phrase_reject` goes on `primitive_type` alone (the issue's own spelling is written where the issue's sentence is). `require_decl` and the zone `type_ref` get NO twin: both already derive `<...>` through `type_args`, so a twin there double-derives; their refusals are the zone registry's (probed 2026-09-02: `extra : Collection<Card>` in `zones { }` fails as `unknown zone type 'Collection'`), pinned as cells citing that Owner. Three consequences, each priced. The SCRAPE: `test_the_position_axis_is_the_grammar_s` collects carriers by `\b(type_name|payload_type)\b`; under A `primitive_decl` stops referencing either, so it drops out of the carrier set -- and the pin asserts `carriers - gridded` only, never `gridded - carriers`, so P10/P11 lose their grammar backing with NO reddening. The scrape widens to the three type-carrying nonterminals and gains the reverse direction (every gridded production, hosts expanded, is a carrier), so a production dropping out of the carrier set is red. The CLASSIFIER: `_outcome` recognizes four substrings and returns `"admit"` on anything else -- a deny-list over an open message space, and the reason Hoyle's twin message (no recognized token) would read as an admit; the grid would still go red for P1-P9 x `Collection<Card>` (the name is absent from `EXPECTED_ADMITS`), but red by the accident of the fallthrough, and P11's shape-check refusal ("is not the signature its implementation takes") would read as an admit by the same accident. Rule: the twin's message carries a token the classifier names (`in a \`primitives { }\` entry only`), the classifier gains it, gains the shape check's sentence as the explicitly-named admitted-past-the-gate outcome, and RAISES on an unrecognized message -- allow-list, never deny-list, applied to scaffolding at its one level. The AMBIGUITY BUDGET: the corpus pin cannot see off-corpus sentences, so the change runs explicit-ambiguity cells on the new forms in both slots -- the phrase twin in the return slot beside the next entry's NAME, `>=` fusion at the default twin (`: Collection<Card>= 0` must reach the default twin's message: the parser expects `>` then `=`, never `COMP_OP`), `>)`, `>,`, `> reads`, and a trailing `//`. **B (rejected): the arm on `payload_type`, admitted at parse everywhere and refused by position at resolve.** Its one real advantage is the channel -- a bag collects several wrong spellings where a parse twin aborts at the first -- and the scrape stays intact. Its cost is the eight arms Hoyle counted, and they are not eight copies of one guard: the three hosts already owned elsewhere (`_check_move_params`, `_PROCEDURE_PARAM_DOMAINS`, `_check_template`) each gain a `<` arm in their own voice, P1/P2 gain new ones, and the string enters every host's AST so every reader of `Parameter.type_name` under those hosts must never meet it -- rung 2 where rung 1 is available ("Prefer the guard you cannot need"). **C (rejected): reuse `type_ref`/`type_args` for the entry slot.** Admits `Collection<Card, Card>` and `Collection<player>` at parse and hands both to resolve, and carries the zone node's semantics into a value declaration.

*(b) The AST shape.* **A (counseled): the string, on the same node, decomposed once.** The entry-slot builder emits `n.Parameter(name, type_name="Collection<Card>")` and `PrimitiveDecl.return_type` likewise, preserving the "one shape for a Primitive's parameters and a move type's" that the grammar comment and the node docstring assert as design. ONE decomposition -- `(base, optional, element)` -- owned by the AST leaf as the node's own structural derivation (the `PositionDecl.members` precedent) or by `primitives_block` beside the element allow-list; the two block consumers that today slice `?` (`resolve` 5036, `typecheck` 1062) read it instead, and `_param_type` (1501) routes every host through it -- the other hosts' spellings can never contain `<` (the twins guarantee it), so their behavior is identical and two of the nine slicing sites retire. The Type conversion stays exactly where it is: `_param_type` -> `type_from_name` on the base, and on the element for the collection form, wrapping in `TCollection(element)` with default facets -- `declared_primitive_sigs` already sends both slots through it, so the block keeps one derivation of Type-from-spelling. Pin (rung 2): a scrape that no module outside the decomposition splits a spelling on `<` or tests for `>`; the `?`-slicing class of nine is named, not swept -- it is uniform and correct today, and this change's proportion is the block. Contract delta below. **B (rejected): a structured type node on `Parameter`.** P2-purer -- the builder holds the structure and flattening it to re-parse is a re-derivation -- but it touches the IR renderer (a string-valued key today), the twin pin's tuple, and every reader comparing a parameter's spelling to a bare name (`encoding.py` 341 and 365, `resolve` `_check_template` 2516 and `_check_delegation` 3436, `_check_move_params`), and it splits `Parameter` from its four other hosts; not priced by a two-entry witness. **C (rejected): a separate `PrimitiveParam` node.** The same split, with the IR gaining a second parameter shape.

*(c) The IR and the twins.* Read: `_primitives` emits `"type": p.type_name` and `"return_type": d.return_type` -- strings -- and the schema pin's domain is tag literals and key literals, so a new string VALUE moves no schema member. Under A, the ten block games' IR goldens (3 of the 10 -- pinochle, french-tarot, seven-card-stud -- carry one) are byte-identical, since none of their strings changes; gin carries no golden of any kind (`tests/golden` holds no gin file), so nothing regenerates. `_block_facts` DOES carry parameter types -- `(p.name, p.type_name)` per parameter plus the return spelling -- so the twin pin already sees a collection spelling as a string and needs no change; gin is in `PROSE_ONLY_TWINS`, so no gin cell runs. Under B both the IR value and the tuple move -- a further cost of B.

*(d) The shape check and the facets.* Executed 2026-09-02: `Sig((TPlayer(), TCollection(TCard())), TBoolean()) == CALL_SIGS["gin_arrange_ok"]` is True; with `zone=True` False; with `key=TPlayer()` False; with element `TPlayer()` False. So a facet fails the shape check by construction, and no spelling can produce one: the element slot is a bare NAME through `type_from_name`, which mints neither a key nor the zone flag. Illegal after: a declared collection parameter with any facet. At the call, `coercible` compares elements only -- executed: a zone-flagged value True, a keyed value True, `Collection<Any>` True, `Collection<Player>` False -- so the zone, the query result, the list literal, and the joint `cards` binder (typed `TCollection(TCard())` at typecheck 2907, default facets) all reach the declared parameter, and a player collection is refused by the existing argument guard. The return slot: admitted at the gate, refused by the shape check -- and if an implementation ever returns a collection, the regime-product renderer's `_spelling_of` asserts loudly ("no spelling for TCollection"), the recorded belote-gaps precedent; a collection RETURN crossing the boundary unfrozen is that day's cell, not this change's.

*(e) The runtime boundary.* `coerce_args`'s `TCollection` arm is unchanged and is the SAME arm the legacy branch runs for gin today (`native_call`: `CALL_SIGS.get(name)` legacy, `rs.declared_sigs.get(name)` declared -- equal Sigs by the shape check), so the Python receives the identical frozen tuple under both regimes; the one behavioral delta is the per-entry row in place of the module-wide one, the delta every migrated game carries and the goldenless substitute differential proves. The freeze pin: `_collection_param_funcs`, `_polymorphic_param_funcs` and `test_no_native_param_demands_a_zone` quantify over `CALL_SIGS`; when 3b deletes its Primitive half, `gin_valid_meld` and `gin_arrange_ok` leave the table while `_ZONE_PROBES` still names them, and the pin goes red -- loud, but for a domain shrink, not a defect. Ruled now: the pin's registry is the Builtin half of `CALL_SIGS` unioned with `{name: implementation_sig(name) for name in PRIMITIVE_IMPLEMENTATIONS}` -- through `implementation_sig`, the designed one-site seam -- landed in gin's PR with the ledger's `registry:` row moved, so the deletion PR changes nothing there. (`test_the_freeze_follows_the_declaration_not_the_registry` plants into `CALL_SIGS` and loses its contrast object at deletion; that is the deletion PR's recorded obligation, already in its does-not-prove line, not gin's.) The joint codec: `ActionSpace.for_game` reads `node.where.func` off the AST (encoding.py 358-361) and `joint_codec_function` is keyed by that name -- regime-blind, no change. The ActionSpace cell: the corpus proofs (`tests/openspiel_ready/test_gin_rummy.py`, the codec cells in `tests/test_jointly_selection.py`) execute under the declared regime the moment gin migrates -- necessary, and the corpus-confound risk exactly: the grid names one SYNTHETIC declared game rooting `where jointly` in a declared `gin_valid_meld` that builds its action space and plays to a score a meld decides (the probe-game contract, a true and a false witness), beside the corpus proof.

*(f) The reserved-name class.* Executed 2026-09-02: `type Card = { x : Integer }` checks clean, and `c : Card = Card { x: 1 }` then fails with "declared Card, but its default has type Card" -- the built-in wins every type slot (`type_from_name` consults scalars before structs), so the struct is constructible and unusable: accepted-but-ignored one step removed, R2, at zero corpus cost (no game declares a `type`). `type Collection` and `type Integer` check clean. `state { Collection : Integer = 0 }` and `state { Card : Integer = 0 }` also check clean -- and are OUT of the class by construction: a state name lives in the value namespace and no type slot reads one; Hoyle's probe is answered as a different class, not a gap. Owner: resolve. The class is "declaration sites that mint a name into the type namespace" (positions, the board-minted cell and dir, `type` declarations) crossed with "the registries already occupying it" (`POSITION_NAME_SOURCES`' rows); three of the four sites ask the whole registry through `_reserved_domain_source`, and the fourth -- `type` declarations -- asks `LIBRARY_ZONE_TYPES` alone. **Counseled: sweep now.** `type` declarations become a fourth `RESERVATION_SITE` asking the same registry minus the one source it IS ("a declared type name" -- the self-pair is `_check_duplicate_names`', cited), and the constructor word joins as a source ("a collection type constructor", the block's own registry beside `DECLARABLE_BUILTIN_TYPE_NAMES`, pinned disjoint from `KNOWN_TYPE_NAMES` and `LIBRARY_ZONE_TYPES`) -- so `type Collection`, `type Card`, and `positions { Collection : 1..4 }` all refuse, and the positions grid's source x site cross widens by one row of its own accord. Proportionality: the sibling guard is touched anyway for the constructor word; the missing cell is R2 with an executed witness; the corpus cost is zero. **Rejected: file the class and list the constructor word beside `LIBRARY_ZONE_TYPES`.** Leaves the `type Card` nonsense standing and adds a second hand-list where a registry exists.

*(g) The partition pin.* `_reachable_type_constructors` runs `type_from_name` over the bare names and cannot see a spelling that is not a name -- correct today, blind tomorrow. Ruled: the derivation enumerates the block's WHOLE spellable set from the block's registries -- bare names x `?` as now, plus `Collection<E>` for every E in the element allow-list -- and runs each through the decomposition and `_param_type` (the site `declared_primitive_sigs` uses), collecting constructors at every depth (the element, not only `.inner`); `TCollection` then leaves `UNDECLARABLE_TYPE_CONSTRUCTORS`, red first on the overlap. The partition is constructor-grain and cannot see a Player element, so a second pin owns element growth: the element allow-list held EQUAL to the element constructors derived from the implementation side -- `implementation_sig` over `PRIMITIVE_IMPLEMENTATIONS`, params and returns (executed today: `{TCard}` and nothing else). A registered Python Primitive over `Collection<Player>` lands red until the list admits it with a witness; a designer spelling it is refused at resolve until then; both directions loud. `TStruct`, `TLine`, `TDir` stay listed with their citations corrected to the sibling issue Hoyle names.

*(h) Information sets.* Do not move -- the same freeze arm, the same frozen tuple, the same codec by name; the declared signature is forced equal to the registry's by the shape check.

**5. What becomes illegal after.** *parse* newly establishes: a `<...>` spelling reaches the AST only from an entry's two slots, single-element, un-nested, un-optional; every other type position and the phrase form meet a span-carrying rejection naming the entry. Illegal after: a `Collection<` string on any `Parameter` outside a `PrimitiveDecl`, or in any `StateDecl`/`StructField`/`OutcomeCase`. *primitives_block* newly establishes: the ONE decomposition of an entry's type spelling, and the element allow-list as a registry pinned to the implementation side. Illegal after: any consumer slicing a block spelling on `<` or `?`, and an element outside the list reaching typecheck. *resolve* newly establishes: every entry's element is in the list; a `type` declaration or position domain never takes a built-in type name, a zone type name, or the constructor word. Illegal after: a declared struct shadowed by a built-in in any type slot. *typecheck* newly establishes: the declared Sig of a collection parameter is exactly `TCollection(element, key=None, zone=False)`. Illegal after: a Sig built from a spelling anywhere but `_param_type`; a declared collection with a facet reaching the runtime. *ir*: nothing -- and that is the claim: the string is the serialized form, and the schema pin holds. *tests/test_type_name_positions.py*: illegal after -- a gridded production that is not a scraped carrier, and an unrecognized refusal message read as an admit. *tests/test_native_call_boundary.py*: illegal after -- the pin's domain naming the signature table's Primitive half. *tests/test_primitives_block.py*: the jointly ledger sentence (lines ~106-110) is a defect the moment the spelling lands and rewrites in the same change; `test_a_collection_type_has_no_spelling_at_all` inverts into the twin's rejection test.

**6. Counsel.** *For:* every fact lands in its owner -- shape at the grammar, element at the resolver, facet at the type pass by construction, the runtime untouched -- and the three pins that would otherwise go quietly wrong (a scrape that cannot see the entry, a partition that cannot see the spelling, a freeze domain about to shrink) are re-pointed in the PR that creates the hazard, not the PR that meets it. The string carrier keeps the IR, the goldens, and the twin pin exactly where they are, which is what lets a two-entry witness pay for the change. *Against, strongest:* the string carrier re-parses a spelling the builder already had structured -- the P2 tell, wearing a house precedent (`Suit?`) as its excuse -- and it is only safe while the decomposition is provably the one site; that safety is a scrape (rung 2), and the day a tenth slicing site lands without tripping it, two readings of one spelling exist again. Second against, from the instrument side: the positions scrape and its classifier were both one wrong reading away from green -- the scrape blind in one direction, the classifier reading silence as admit -- and this change finds them because it happens to redden the cells; a change that did not would have inherited both defects unseen. *What the Architect would do:* take A on all four choices; author the grid red first with the partition pin's overlap as the first red; land the element pin, the widened two-directional scrape, the allow-list classifier, and the re-pointed freeze pin in the same PR as the surface; sweep the reserved-name class now; migrate gin in the same change with the substitute differential and the synthetic declared joint game that plays; and before freezing, have the plan read four Contract blocks -- parse's, resolve's, typecheck's, primitives_block's -- since each gains an Establishes line above.

**THE BOTTOM LINE (two-persona sitting; written once, by this seat).** Verdict: adopt Hoyle's sentence and walls exactly as ruled, carried as a string on the shared parameter node with its own entry-only production family and one decomposition; shape refused by the grammar, element by the resolver from a one-member registry, facets unspellable and shape-checked by construction; the positions scrape widened and made two-directional, its classifier converted to an allow-list, the partition pin re-derived through the block's spelling set, a new element pin tied to the implementation side, and the freeze pin read through `implementation_sig` now. The strongest against-case from either seat is Hoyle's: this admits the language's first parameterized value type into the declaration register on a witness of two entries in one game -- a generic with one instantiation -- and its next element reopens the audit at every position the spelling reaches; its cost is a five-axis grid, a reserved constructor word, and (this seat's addition) a re-parse that is safe only while a scrape holds the decomposition to one site. Where the seats diverge, the divergence is the decision: (1) Hoyle offered "widen the scrape OR build the new production on `payload_type`" -- this seat rules the second impossible (a shared derivation is an Earley ambiguity in the entry's own slot), so the scrape widens, and gains the reverse direction Hoyle did not ask for; (2) Hoyle offered "sweep the reserved-name class or file it" -- this seat counsels sweep-now on an executed R2 witness (`type Card` accepted, the struct unusable) at zero corpus cost, and rules Hoyle's state-name probes out of the class rather than into the file. The operator decides three things: sweep-now versus file for the reserved-name class (Gate 3.5 is the operator's); the string carrier (counseled) versus a structured type node (rejected, priced above); and whether the two instrument repairs -- the two-directional scrape and the allow-list classifier -- ride this PR as scaffolding at one review round, or split out ahead of it.

