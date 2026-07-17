# Lexical cleanup: one register, completed domains

*Status: the analysis that produced the register decision — kept for the
evidence and the rejected alternatives. The rulings themselves are spec:
[decisions.md](../decisions.md) "The expression register" (the register, the
word/symbol line, equality, the card queries and aggregations, the rank/suit
value rules) and [principles.md](../principles.md) "One spelling per concept"
(the two-audience rationale). Everything here was implemented as
parser/stdlib/corpus work, semantically neutral by construction — the trace
goldens were byte-identical through the whole migration.*

## 1. The problem: the DSL was barely denser than English, and read worse

A corpus-wide comparison of each game's tight English summary (the prose head
of its `.md`) against its `.cardlang` found the formal files barely denser
than the prose — and sometimes longer (Seven-Card Stud: ~1,200 md words →
~1,800 cardlang words). The gap had one root cause in two forms: English
names a pattern once ("follow suit", "the winner leads next", "count your
hearts") and never repeats itself, while the DSL had to either **re-derive**
patterns from primitives or **re-paste** text it had no way to name and
reuse.

The re-derivation costs clustered into a small number of measurable idioms:

- `sum over <zone> as c: if <pred> then 1 else 0` — then the only correct way
  to count matching cards — 33 uses across 8 games;
- `rule MustFollowSuit { … }` pasted verbatim into 7 game files under a
  header *calling* it a "standard library rule";
- `for each player p: if p == X { … }` single-actor binding — 10+ uses,
  now settled as the `as` block ([decisions.md](../decisions.md) "Single-actor
  decisions: the `as` block");
- Coup's three unnamed statement blocks (influence loss ×14, challenge
  window ×8, proven-claim swap ×7) — most of a 522-line file;
- `0 - 200`, `0 - 1` for negative values; `c.rank == "K"` string comparison
  for ranks; `the player where player != dealer` (15 uses) for "the
  opponent"; four-way `or` chains over suits where a quantifier was missing.

Separately, the surface had drifted into **two registers**: the statement
layer was English-shaped (`deal 13 cards from deck to each hand`) while the
expression layer was programming-shaped (`hand.where(c => c.suit != hearts)`),
mixed line by line. The register question was resolved in favor of English —
the statement layer already had it, so this finished the language's existing
direction rather than picking a new one.

## 2. What landed, and where it lives

- **The English expression register** — `is`/`is not`, the card queries,
  `sum of`/`highest`/`lowest … or <default>`, implicit-binder quantifiers,
  membership `in`, `repeat until`, lambda-free filters — spec'd in
  [decisions.md](../decisions.md) "The expression register"; the method
  register, lambdas, explicit binders, `==`/`!=`, and the
  `count`/`max`/`min` comprehension spellings are retired (the checker
  rejects `==`/`!=` by name; the rest no longer parse).
- **Shared rule definitions** — the bodies live in
  `cardlang/stdlib/rules.cardlang`; games activate by name, templates
  instantiate with arguments ([library.md](../library.md) "Rules").
  `MustFollowSuit` folded six byte-identical pastes;
  `NoLeadingSuitUntilBroken(suit)` folded the Hearts/Spades pair. French
  Tarot's follow rule genuinely differs (`tarot_led_suit()`) and keeps its
  own name (`MustFollowEffectiveSuit`) — shadowing a library name is
  rejected.
- **Domain completion** — negative Integer literals; deck-derived rank
  values with the enum-comparison wall; suit/rank quantifier and `for each`
  domains; membership `in` with list literals
  ([decisions.md](../decisions.md) "The expression register",
  [roadmap.md](../roadmap.md) for the walls).
- **The `count`-body defect** — closed first, independently (the evaluator
  discarded a `count` body silently); the whole aggregator class was swept
  and the retired spelling is now unparseable.

## 3. Findings that changed the plan (kept as the record)

- **The auction promotion was investigated and rejected.** The three-instance
  rule seemed to demand a shared `auction` configuration (Bridge, Pinochle,
  Tarot, Skat). A corpus comparison found the four share only the kernel
  auction-form `round` itself: accumulator variables, ring topology
  (continuous / shrinking / two-seat-twice), bid vocabulary, and outcome
  mechanism (named function vs inline survivor; Skat uses the outcome-less
  betting form) all genuinely diverge. A promoted configuration would
  abstract over instances that agree on nothing it could parameterize —
  the shared thing IS the kernel form. Recorded in
  [library.md](../library.md) "Mechanics".
- **Bare rank literals cannot cover the rank domain uniformly.** The domain
  includes numeric ranks ("10", "1", "21" — Doppelkopf, Tarot) that can
  never be bare literals (a bare `10` is an Integer). The resolution:
  name-form ranks are bare enum values, numeric ranks keep the string
  spelling *validated against the deck*, and the checker rejects every
  silently-false shape (Rank vs Integer, name-form-in-string, unknown
  values, cross-enum). One spelling per rank, loud walls between them.
- **Nested card queries surfaced a binder-capture limit.** Exactly one
  nesting level can use the implicit `card`; go-fish's per-rank book counts
  needed the outer card's rank inside an inner count. The register-pure
  resolution: pass the outer value into a named function
  (`rank_count(p, card.rank)`) or restructure with a value-domain quantifier
  (`any rank where …`) — both used in the corpus. The strict-trick
  over-trump demands deliberately shadow one level (the inner aggregation's
  `card` is the pile card), which reads as the rule states.
- **A noun-sugar counting tier** (`count hearts in hand`, `number of Kings
  in hand[p]`) was considered and **deferred**: it needs suit/rank plural
  nouns, and it can only ever be sugar over the query form.
- **The English `offset_by` replacement** is a decided *direction* whose
  spelling is still open — `offset_by` remains the surface operator,
  documented as such in [library.md](../library.md) "Types" (`Seating`).

## 4. The work this analysis motivated — all four landed

1. **Named procedures.** The one definition-form gap with a forcing corpus case
   (Coup ×29). Spec: [../decisions.md](../decisions.md) "Named procedures";
   the design conversation and the two hygiene walls it did not anticipate are in
   [procedures.md](procedures.md). Coup: 521 → 375 lines, 29 pasted blocks → 3.
2. **The `state.` pronoun split.** This was mis-triaged here as ergonomics ("a
   real semantic distinction with no surface cue... not blocking anything"). It
   was a correctness hole. A round's frame is *also* its working memory, and
   nothing separated the two or checked the field name — so `state.idx`, the
   trick form's private ring cursor, type-checked, ran, and silently changed the
   game (in Hearts it moved the winner), while a typo reached the runtime as a
   bare `KeyError`. The resolution was neither of the two this note offered: not
   a rename (there are *two* owners, trick and climb, so `trick.led_suit` alone
   was wrong) and not a documented convention, but a declared, typed **published
   set** per form, with the checker rejecting everything else. Spec:
   [../decisions.md](../decisions.md), "Round-internal state lives inside the
   round".
3. **Coup's integer-valued flags.** `alive[p]` is a Boolean; `block_claim`, a
   `String` that held a rank name all along, is a `Rank?`. The trace-golden
   sign-off found that the goldens *could not have caught this*: they compared
   parsed JSON, and in Python `False == 0`. They compare types now.
4. **The quantifiable-domain registry.** `cardlang/domains.py` — one row per
   domain, replacing two half-tables that used different key namespaces
   (`player` vs `Player`) and did not know about each other. The seat/value
   asymmetry (`for each player` rebinds the acting player; `for each suit` does
   not) is now a `binds_actor` column rather than an if-chain, so a new domain
   arrives with its semantic column green. The *grammar* does not yet follow —
   the quantifier productions are still hardcoded nouns — which is the recorded
   residual in [../roadmap.md](../roadmap.md), and the thing the board-game
   expansion would need.

Two findings from that work are worth keeping, because both are cases where the
plan was wrong in the same direction — it predicted a shared abstraction that the
evidence did not support:

- The **`Zone` procedure parameter** [procedures.md](procedures.md) §4 expected
  the corpus to need never appeared: a `Player` parameter already carries its
  zone (`influence[victim]`).
- The **`trick.` rename** item 2 proposed would not have fixed anything —
  `trick.idx` would still have been readable. The surface cue was never the
  problem; the missing wall was.
