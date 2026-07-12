# Lexical cleanup: one register, completed domains

*Status: design analysis / proposal — not a settled decision. The committed
spec is in [decisions.md](../decisions.md); this note argues a surface-level
direction and records the rulings already made in design discussion. Nothing
here touches the kernel, the projection model, or info-set derivation: every
change is parser, stdlib-catalogue, and corpus work, semantically neutral by
construction.*

## 1. The problem: the DSL is barely denser than English, and reads worse

A corpus-wide comparison of each game's tight English summary (the prose head
of its `.md`) against its `.cardlang` found the formal files barely denser
than the prose — and sometimes longer (Seven-Card Stud: ~1,200 md words →
~1,800 cardlang words). The gap has one root cause in two forms: English
names a pattern once ("follow suit", "the winner leads next", "count your
hearts") and never repeats itself, while the DSL must either **re-derive**
patterns from primitives or **re-paste** text it has no way to name and
reuse.

The re-derivation costs cluster into a small number of measurable idioms:

- `sum over <zone> as c: if <pred> then 1 else 0` — the only correct way to
  count matching cards — 33 uses across 8 games;
- `rule MustFollowSuit { … }` pasted verbatim into 7 game files under a
  header calling it a "standard library rule";
- `for each player p: if p == X { … }` single-actor binding — 10+ uses,
  already tracked as [open-questions/single-actor-binding.md](../open-questions/single-actor-binding.md);
- Coup's three unnamed statement blocks (influence loss ×14, challenge
  window ×8, proven-claim swap ×7) — most of a 522-line file;
- `0 - 200`, `0 - 1` for negative values; `c.rank == "K"` string comparison
  for ranks; `the player where player != dealer` (15 uses) for "the
  opponent"; four-way `or` chains over suits where a quantifier is missing.

Separately, the surface has drifted into **two registers**: the statement
layer is English-shaped (`deal 13 cards from deck to each hand`) while the
expression layer is programming-shaped (`hand.where(c => c.suit != hearts)`),
and the corpus mixes them line by line. This note resolves the register
question and enumerates the cleanup that follows from it.

## 2. The root decision: English-shaped expressions, implicit binders

**Ruling: the expression layer adopts the English register.** The statement
layer already has it; this finishes the language's existing direction rather
than picking a new one. The method register (`.where(…)`, `.cards_of_suit(…)`)
and the lambda syntax (`c => …`) retire from the surface.

The keystone is the **implicit binder**, generalized from the player queries
that already work this way (`players where not passed[player]` — 45 corpus
uses). Cards get the same treatment: inside a card query, `card` is bound
implicitly.

| Today | Proposed |
|---|---|
| `hand.where(c => c.suit != hearts)` | `cards in hand where card.suit is not hearts` |
| `hand.cards_of_suit(state.led_suit)` | `cards in hand where card.suit is state.led_suit` |
| `sum over hand[p] as c: if c.rank == r then 1 else 0` | `number of cards in hand[p] where card.rank is r` |
| `(sum over trick_pile as t: if t.suit == trump_suit then 1 else 0) > 0` | `any card in trick_pile where card.suit is trump_suit` |
| `move … from hand[p] where c => is_pref_discard(c) to …` | `move … from hand[p] where is_pref_discard(card) to …` |

Rule demands become rulebook sentences
(`demands: cards in hand where card.suit is state.led_suit`), and the
movement `where` clause — which today accepts a mix of bare expressions and
lambdas — collapses to one form.

The explicit-binder quantifier spelling (`any player p: <pred>` — 12 uses)
retires in favor of the implicit form (`any player where <pred>`), for the
same reason `==` retires below: one concept, one spelling.

## 3. The word/symbol line

**Ruling: words for logic, equality, membership, and quantification; symbols
for arithmetic, ordering, and state change.** One sentence a designer can
internalize; it is also Python's line, which is why the surface keeps a
familiar feel.

Words — `is`, `is not`, `in`, `not`, `and`, `or`, `any`, `all`,
`number of … where`:

- **`is` / `is not` replace `==` / `!=`.** `is` already exists in restricted
  form (`is none`, `is empty`, `is not none`); the ruling generalizes it to
  ordinary equality (`card.suit is hearts`, `pass_direction is not hold`) and
  the existing forms become ordinary instances. `is not` is a single
  operator — `a is not b` must not parse as `a is (not b)`. The right-hand
  predicate keywords (`empty`, `none`) remain a closed, enumerable set.
  Unlike Python, `is` here simply *means* equality — there is no
  identity/equality split to trip over. `==`/`!=` retire; the checker flags
  them.
- **`in` for membership.** `Q of spades in captured[p]`,
  `card.suit in [hearts, spades]`. The keyword already appears in
  `choose integer in 0 .. 13` and in the card-query form above; the grammar
  owns the three uses (range, query source, membership) explicitly.

Symbols — kept as-is, by ruling: `:=` assignment, `+=`/`-=` increment,
`<` `<=` `>` `>=` ordering, `+` `-` `*` arithmetic. English forms for
assignment (`set … to …`, `add … to …`) were considered and **rejected**:
there is no confusion cost to the symbols, no compact English word for `>=`,
and the per-line verbosity cost would be the largest in the language.

**Ruling: `repeat until` everywhere.** The phase modifier `repeats until`
unifies with the statement form. The phase line reads marginally less like
English ("phase hand_sequence repeat until …"); one lexeme is worth more
than the third-person `s`.

## 4. Counting: the `count` tangle

Three defects are knotted together; the register decision unknots them.

1. **`.count` is documented but does not exist.** `METHOD_SIGS`
   (`cardlang/stdlib/signatures.py`) contains exactly `where` and
   `cards_of_suit`; every other method [library.md](../library.md) lists on
   `ZoneContents` (`count`, `non_empty`, `empty`, `highest_of_suit`,
   `has_card_of_suit`, `highest_by`, the resource ops) is statically rejected
   by `resolve.py`. The failure is loud (totality state 2), but the doc
   presents design intent as current surface. §7 realigns it.
2. **The `count` aggregator is a live accepted-but-ignored defect.** The
   grammar admits `AGG: "sum" | "count" | "max" | "min"`, and the evaluator's
   `count` arm evaluates the comprehension body and **discards it**, returning
   the element count. The corpus only ever writes `count over Z as c: true`
   (2 uses, the zone-size idiom), but nothing rejects a predicate body:
   `count over hand[p] as c: c.suit == hearts` parses, typechecks, runs, and
   silently returns hand size. By [decisions.md](../decisions.md) "Surface
   totality" this is the worst defect class the project defines, and it must
   be closed **independently of everything else in this note** — either the
   body becomes meaningful or non-`true` bodies are statically rejected.
3. **The 33 `sum over … 1 else 0` sites are the workaround**, not a style
   choice: filtered counting is currently inexpressible.

**Proposed resolution.** The counting form is the English query:
`number of cards in <zone> where <pred>`, mirroring the existing
`number of players where <pred>` (30 uses) exactly. The bare form
`number of cards in <zone>` covers the size idiom, retiring
`count over … as c: true`. With that in place the `count` aggregator is
redundant and retires from `AGG`. The genuine sums remain comprehensions in
English shape (`sum of card_value(card) over cards in captured[w]`), and
`max`/`min` become `highest`/`lowest … over …` with an **explicit empty-set
default** (`or <expr>`) — which retires the `else 0 - 1` sentinel hack as a
side effect. `min over` currently has zero corpus uses and, as far as review
found, zero tests: per [decisions.md](../decisions.md) "Closed-domain
completeness" it is the same class as `count` and gets swept in the same
change.

A noun-sugar tier (`count hearts in hand`, `number of Kings in hand[p]`) was
considered and **deferred**: it requires suit/rank plural nouns, which are
blocked on the rank-literal gap (§5), and it can only ever be sugar over the
query form. Revisit once literals land.

## 5. Domain completion: the coverage matrix

The corpus review produced a coverage matrix of constructs × entity domains.
The pattern: the Player column is essentially complete and every other domain
is sparse — the language grew wherever trick-taking pulled it. Counts are
corpus uses; "gap" means the construct exists for other domains but not this
one, with a hand-rolled workaround in the corpus.

**Quantifiers and queries × domain**

| construct | Player | Team | Suit | Rank | Card/zone |
|---|---|---|---|---|---|
| `any` / `all` | 32 | 5 | gap (4-way `or`) | no demand | partial (`is empty`) |
| `for each` | 67 | 7 | gap (enumerated) | no demand | expressions only |
| `the … where` | 19 | no demand | no demand | no demand | partial (move/reveal) |
| `number of … where` | 30 | no demand | gap | gap | gap (sum-over ×33) |

**Literals**

| value | literal exists | corpus workaround |
|---|---|---|
| positive Integer | yes | — |
| negative Integer | **no** | `0 - 200` (×5) |
| Card (`2 of clubs`) | yes | — |
| Suit (`spades`) | yes | — |
| Rank (bare `K`, `Q`) | **no** | `c.rank == "K"` string comparison |

The audit rule: these are **incomplete domains of admitted constructs**, not
new constructs, so filling them is compliant with corpus-first — the gate
governs admission, and it should not be read as licensing a quantifier that
covers players but not suits, any more than surface totality licenses a
clause that parses but does not run. Each filled cell is small and
total-by-construction; each ships with a test derived from the domain's
registry, and ideally one corpus game rewritten to use it.

**The forward-looking version of the same rule:** make "quantifiable entity
domain" itself a registry, so the quantifier/query/counting forms are defined
once over *any enumerable domain*. Then a new domain (and the board-game
expansion will bring several: piece, space, tile, resource — with board
topology as the one genuinely new query family) registers itself and arrives
with its full column green by construction, instead of repeating this
matrix's history. Note also that Suit and Rank are not really first-class
kinds but declared attribute enums on the card type (Tichu's specials and
Tarot's atouts already strain them); the registry framing is where that
generalization would land.

## 6. Definition forms: what can be named and shared

| form | exists | nameable | parameterized | shared across games |
|---|---|---|---|---|
| function (expression) | yes | yes | yes | no — hard ones live in Python |
| move_type | yes | yes | Card/Suit/Player | catalogued, redeclared per game |
| rule | yes | yes | candidate only | **no — pasted ×7 files** |
| procedure (statements) | **no** | — | — | — (Coup pastes ~29 blocks) |
| outcome function | yes | yes | — | stdlib 2, Python 3 |
| mechanic (round config) | 3 forms | stdlib | clauses | not user-definable |
| type / zone type | yes | yes | yes | yes (library types) |

Two rows are actionable now:

- **Shared rule definitions.** `MustFollowSuit` is restated verbatim in 7
  files; Pinochle and Tarot both carry full four-rule cascades.
  [library.md](../library.md) says promotion "waits on a second
  `active_rules` DSL instance" — the gate was met several times over.
  `active_rules: [MustFollowSuit]` should resolve to a library body, with
  the parameterized `NoLeadingSuitUntilBroken(suit)` (already a catalogued
  candidate) folding the Hearts/Spades pair. Nearly pure deletion: ~10
  lines × 7 games, zero semantic change.
- **Named procedures.** A new definition form — a nameable, parameterized
  statement block — is the only fix for Coup-scale duplication, and the
  corpus-first gate is cleared ~29 times over in one file (plus Tichu's poll
  ×3, go-fish's book-completion ×2, Skat's Reizen round ×2). It needs its own
  design conversation: parameter kinds (player/zone at minimum), scoping,
  and — the load-bearing constraint — that a procedure is *pure DSL
  reuse*, expanded before execution, so its body's observation events are
  exactly what inline text would emit. It must not grow into an escape
  hatch; the [principles.md](../principles.md) lesson that retired
  `instantiate` applies in full.

One promotion is overdue by the three-instance rule independent of this
note: the shared **`auction`** configuration of the auction-form `round`
(Bridge, Pinochle, Tarot, and Skat all hand-roll the same accumulator +
vocabulary + ring shape). Betting (Stud only) and the combination engines
(Big Two, Tichu — genuinely divergent) stay game-local, correctly.

## 7. Documentation realignment

Two places where [library.md](../library.md) presents design intent as
current surface; both fixed by editing the doc to match the code and marking
the remainder unbuilt (or deleting it where the English register supersedes
it):

- **`ZoneContents`** (§4.1): of ~10 documented operations, `where` and
  `cards_of_suit` exist. Under this note's register decision most of the
  remainder should never be built as methods — the English query forms
  replace them — so the section rewrites around the query surface.
- **`Seating`**: documented as exposing `partner_of`, `left_of`, `LHO_of`,
  `opposite_of`; the surface reality is `offset_by` (23 uses; `left_of`
  exists only as an internal runtime method). `offset_by` is also the
  clunkiest-reading operator in the language. **Open**: the English
  replacement spelling (`the player to the left of dealer`,
  `dealer's left neighbour`, …) — pick one during implementation; the
  direction (English surface, doc matches code) is decided.

## 8. Small lexical rulings

- **Number words and plural agreement.** `deal 1 cards` sits next to
  `reveal one card`. One rule: digits and number-words both accepted, the
  noun agrees in number (`1 card` / `one card` / `2 cards`).
- **Integer-as-Boolean flags** (Coup's `alive[q] := 0` vs Stud's honest
  `Boolean`s) are corpus hygiene, not grammar: the games double as the
  canonical examples, so the corpus sweep converts flag-shaped integers to
  `Boolean` as it passes. With `is` arriving, `alive[q] is 0` would read
  strangely anyway.
- **The `state.` pronoun split** (round-owned `state.led_suit` vs bare phase
  state) is a real semantic distinction with no surface cue. **Open**:
  either a friendlier owner-name (`trick.led_suit`) or a documented,
  guessable rule. Not blocking anything above.

## 9. Constraints and trade-offs

- **Surface totality is the price of friendliness.** Every English form is
  new grammar surface and pays the [decisions.md](../decisions.md) "Surface
  totality" tax: enumerate composition points, implement or statically
  reject, never silence. This is why the sequencing below leads with
  *sharing* (near-zero new surface) and domain completion (small closed
  surfaces) before the register migration (real matrices: `where` now
  appears in several productions and each must stay unambiguous).
- **Info-set neutrality.** Everything here is surface: same AST shapes, same
  observation events, same projections. The corpus sweep must be
  byte-identical at the trace level, which the existing golden/
  characterization tests already enforce.
- **The corpus stays the test bed.** An audit generates surface no game
  exercises; the mitigation is that every filled cell ships with a
  registry-derived test and the corpus sweep adopts the new forms
  everywhere, so the fifteen games remain the living embodiment of the
  current language ([maintaining.md](../maintaining.md) rule 2).

## 10. The second audience: LLMs read and write this language

The language has two machine audiences, not one. Beyond the OpenSpiel
compilation target, LLMs will consume game files directly — as player seats
comprehending rules they are handed (see
[llm-player-seats.md](llm-player-seats.md)) and as authors writing or
modifying games under a checker loop. The English register affects the two
directions differently, and the difference yields a normative rule for all
future surface work.

**Reading: the English register is a near-pure win.** A model playing a seat,
or reasoning about a game in a prompt, comprehends
`cards in hand where card.suit is hearts` without simulating code — and the
rulebook-shaped surface lets it recruit what it already knows about card-game
convention from real rulebooks. Comprehension error is pure noise in any
downstream measurement built on LLM play; naturalness reduces it.

**Writing: the risk is degrees of freedom, not English-shape.** English
invites paraphrase — a model that has seen `number of cards in hand where …`
will improvise `count of cards in hand of suit hearts`, because its English
prior says those are the same sentence. Code-shaped syntax suppresses this
only by accident, by looking rigid. The failure mode to avoid is the
AppleScript trap: a surface that reads like English implies *any* English
phrasing works, when exactly one does — miserable for human and model
authors alike. The success case is SQL: English-ish but famously regular.

**The rule for future additions — one spelling per concept.** Friendliness
comes from familiar words in regular positions, never from accepting
multiple phrasings because they all sound right. Every ruling in this note
already conforms (retiring `==` alongside `is`, the explicit binder
alongside the implicit, `repeats` alongside `repeat`); every future
construct must too. When a new form is proposed, the test is: does it add a
concept, or a second way to say an existing one? A second spelling is a
defect in this framing — it widens the paraphrase surface a model (or a
designer) can wander into, and it costs a corpus-drift risk on top.

Two existing disciplines are load-bearing for the authoring loop and gain a
second justification here:

- **Surface totality** ([decisions.md](../decisions.md)): LLMs write
  unfamiliar languages well only under generate–check–repair, and that loop
  is exactly as good as the checker's refusals. A loud, specific rejection
  is a usable repair signal; an accepted-but-ignored clause gives the model
  no gradient at all. The defect class is thus doubly ranked.
- **The corpus as few-shot library** ([maintaining.md](../maintaining.md)
  rule 2): the fifteen games are the examples that teach the one true
  phrasing, to models as to designers. A game file using obsolete or
  off-register syntax mistrains every future reader; the lockstep rule is
  what keeps the prompt library canonical. The Lark grammar additionally
  leaves grammar-constrained generation open as a future enforcement layer.

**On implementation, this section graduates.** When the rulings in this note
land, promote the durable parts into the spec so future work stays aligned:
"one spelling per concept" and the two-audience rationale belong in
[principles.md](../principles.md) as a design principle beside "Accepted
means honored"; the word/symbol line (§3) and the register decision (§2)
belong in [decisions.md](../decisions.md) in spec voice; and this note then
shrinks to the exploratory analysis that produced them, per the promotion
rule in [maintaining.md](../maintaining.md).

## 11. Suggested sequence

1. **Close the `count`-body defect** (and sweep its class: `min over`) —
   independent of every other decision; it is a live silent-misread.
2. **Shared rule definitions** + the overdue `auction` promotion — near-pure
   deletion, no new surface.
3. **Domain completion** — negative literals, rank literals, the suit/rank
   quantifier cells, membership `in` — small closed cells, each with tests.
4. **The register migration** — `is`/`is not`, implicit binders, the card
   query forms, `number of cards in … where`, `highest/lowest … over … or
   <default>`, retire lambdas/methods/`==`/explicit binders/`repeats` — one
   grammar change plus a corpus-wide sweep (including the Boolean and
   number-word hygiene), gated on the full `mypy` + `pytest -q` and the
   trace-level goldens.
5. **Procedures** — separate design note first (parameters, scoping,
   expansion semantics, the no-escape-hatch constraint), then Coup as the
   forcing corpus case.
6. **Doc realignment** (§7) lands with whichever step touches each section.
7. **Spec promotion** (§10) — as each ruling lands, move it into
   [decisions.md](../decisions.md) / [principles.md](../principles.md) in
   spec voice, so the register, the word/symbol line, and "one spelling per
   concept" govern future constructs rather than living only in this note.

Steps 2–4 each end with `docs/games/` fully migrated in the same change, per
the lockstep rule. Nothing in this note blocks, or is blocked by, the
workstreams in [kernel-migration.md](../kernel-migration.md).
