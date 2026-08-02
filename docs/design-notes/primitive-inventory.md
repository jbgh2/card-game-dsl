# The primitive ledger: every line of game-specific Python, and what would eliminate it

2026-08-01. Three parallel readers covered all fifteen `runtime/` game modules plus the
dispatch side (the call arms, `builtins/functions.py`'s partition,
`reads.py`'s 19 registry rows, `sidecar.py`'s EngineFacts). Every function received an
expressibility verdict: **(a)** expressible in today's DSL · **(b)** needs
combination/multiset patterns · **(c)** needs contextual ranking · **(d)** needs an
ordered ladder domain · **(e)** other named gap · **(f)** legitimately engine-side.

Read alongside `docs/plans/` specs; this note is the evidence base that re-shapes the
primitive-elimination roadmap (see "How this changes the plan" at the end).

## Headline numbers

~3,480 lines of game-specific Python across 15 modules. 83 of the 99 `call()` arms
(84%) are game-specific; canasta + gin alone are 30 of them. (Both call-arm figures
are as surveyed; §A6 carries the re-measurement.) But the composition is
the story:

- **Zero mutations, zero RNG, zero direct decisions across all fifteen modules.**
  The `deep_freeze` / declared-reads narrowing is structurally airtight — a primitive
  *cannot* mutate. The doctrine's "never mechanics" is holding at the letter.
- **~40% of the meld cluster and a fifth of everything else is expressible today or
  blocked behind one tiny gap** — mostly a missing per-game card-point table.
- **~408 lines (a third of the climb cluster) is hand-maintained action-space
  encoding** — Tichu's 326-line codec, Big Two's and President's universe functions —
  each a *derived duplicate* of enumeration logic it must stay bit-compatible with,
  pinned only by tests.
- **Essentially nothing is inherently engine-side**: the honest (f) residue is
  `coup_game_summary` and the codecs-until-generated.

## The ledger

| Module | Lines | Dominant need | One-line diagnosis |
|---|---:|---|---|
| canasta.py | 517 | groups (b) + collections (e) | typed melds with wild quotas; 12 literal meld zones because no group collections |
| tichu.py | 493 | patterns (b); 326 lines are (f) codec | combination engine + hand-written mixed-radix action codec for a 211M universe |
| gin.py | 296 | groups (b) | partition-minimization deadwood; meldA/B/C triplication (no collections) |
| belote.py | 297 | patterns (b) + ranking (c) | declaration decomposition (10 primitives) + four simultaneous card orders |
| bigtwo.py | 285 | patterns (b) + ranking (c) | two live rank orders + suit order; 65-line duplicate universe |
| five_hundred.py | 269 | ranking (c) + ladder (d) | bowers/joker orders, 2-D bid ladder, misère dead-seat *participation* |
| stud.py | 192 | classify (b) + argmax (e) | poker hand classifier (choose-5-of-7); side-pot accumulator fold |
| cribbage.py | 186 | count-subsets (b) + provenance (e) | fifteens = cardinality of a filtered powerset; seq_bits bit-packing for provenance |
| skat.py | 181 | ranking (c) + ladder (d) | contract-dependent trump SETS and plain orders (Null ≠ Suit); the 62-value Reizen ladder |
| tarot.py | 162 | ranking (c) | Excuse never-wins; effective led suit skips the exempt card |
| president.py | 160 | ranking (c) | transparent threes: a play's strength *inherited from the play it beat* |
| pinochle.py | 73 | catalogue (b-lite) | fixed meld catalogue scored by multiset multiplicity |
| doko.py | 89 | ranking (c) | trump set = Q∪J∪♦∪{♥10}; first-played-wins tie-break (double pack) |
| coup.py | 83 | (a) + ring search (e) | mostly expressible today; the model of what a primitive should shrink to |
| schnapsen.py | 49 | **none** | logic already = stdlib `highest_trump_or_led_suit`; only trace/attribution shell remains — **eliminable now** |

## Doctrine findings

The narrowing works; the leak is at the *decision* boundary, exactly where the
doctrine said "never":

- **Six legality predicates ARE the move filter**: `skat_follow_ok`,
  `five_hundred_follow_ok`, `five_hundred_lead_ok` (+ their pure cores),
  `belote_best_is`. Pure, but they decide.
- **Sharpest breach**: `five_hundred_trick_winner` computes *participation* — it
  removes the misère declarer's partner from the trick order via
  `offset_by(declarer, "across")`. That is table structure, not a value.
- **Guard/candidate coherence is a standing hazard**: gin's docstring records a
  3%-of-seeds crash class from a guard/movement mismatch; gin and canasta
  independently invented the same fix (a *completability* guard: every partial
  commitment keeps a legal completion reachable). Any combination construct must
  derive guard and candidate set from ONE definition, or the class recurs.
- **Engine plumbing hides in game modules**: the pile→seat attribution zip
  (doko/skat/500) — doko's own comment admits it silently mislabels if seating
  direction and `offset_by` disagree. Belongs engine-side regardless of anything else.

## The gaps, ranked

### Tier 0 — quick wins (small additions, large kill counts)

1. **Per-game card-point table on `cards:`** — diagnosed independently in three
   module docstrings. Kills 5 private point tables (gin, canasta, cribbage, tarot,
   tichu) and every sum built on them; `card_value` already exists and dispatches to
   an empty table for standard52.
2. **Ring search** — "the first seat from p in order where P, with default". Kills
   `coup_next_in_game`, `tichu_next_holder`, `player_holding`, and plausibly stud's
   `bring_in_seat`/`first_to_act_seat` (with a compound-key argmax).
3. **Integer `//` / ceiling** — kills `skat_effective_loss`, `five_hundred_bid_level`.
4. **First/last of an ordered zone** — kills `top_of`/`bottom_of` builtins and
   `canasta_pile_rank`-shaped accessors.
5. **~25 already-expressible primitives** (the (a) tier: `tichu_partner`,
   `coup_players_in`, `president_is_top_rank`, `canasta_discard_ok`, `flush_score`,
   `initial_minimum`, …) migrate to DSL functions with no new language at all —
   the builtins→stdlib direction made real.

### Construct C — contextual ranking (31 items, six games; the trick family)

All six trick-winner modules are one program with different constants:
`resolve_trick = argmax TRUMP_ORDER over trumps, else argmax PLAIN_ORDER over the
led class`. The construct must cover **nine dimensions**, each witnessed: trump-set
membership as a computed heterogeneous union (doko: Q∪J∪♦∪{♥10}; skat null: ∅);
trump orders keyed on (rank, suit) with banding; plain orders that are
contract-dependent (skat Null vs Suit — the sharpest refutation of one static
`ranking:`); follow-class as a separate *equivalence* projection (jacks join trump;
500's joker reassignable mid-hand); never-wins / beats-all special positions
(Excuse, un-nominated joker); computed led-class (skip the exempt card); play-order
tie-break (doko's double pack); the ordering *selector* as an expression over
declared state (`_contract`); and plural named orderings per game (belote needs
four at once). President's rank-absorption (a play's strength inherited from the
play it beat) is the same construct's climb-side witness. Skat's contract-dependent
ranking is mode-shaped — a candidate use of the `mode` body's reserved space.

### Construct A — play patterns (the climb shape: tichu, bigtwo, president, stud-classify)

Atomic plays: **enumerate patterns in a hand · filter by legality-vs-standing ·
compare by composite key · classify a given set (stud's direction) · generate the
action space**. Pattern vocabulary is closed and small: n-of-a-kind(n), run(len),
same-suit run, flush(k), group-composites (3+2, 4+1), run-of-groups, wildcard slot,
null/terminator — plus pattern precedence/exclusivity (Big Two's "a monochrome
straight is a straight flush") which is exactly the universe-soundness invariant.
~60% of the Tichu engine is generic machinery; the specific 40% is four declarable
modifiers (wildcards, bombs, off-ladder specials, terminator). **The decisive
payoff: the action space derives from the declaration** — as a list when small
(Big Two 19,898), as an arithmetic codec when not (Tichu 211,204,694) — deleting
408 lines of duplicated encoding and its drift risk.

### Construct B — groups (the meld shape: gin, canasta, pinochle, cribbage)

Different operations from A, proven by the inventory: **multiset-aware** (canasta108's
duplicate cards break set-based codecs — a soundness requirement, not a nicety);
groups as first-class values with **category quotas and wildcard roles** (canasta's
w≤3, joker-vs-deuce value choice); **disjoint-partition enumeration with argmin**
(gin's deadwood); **subset-comprehension with count/sum aggregation** (cribbage's
fifteens); **declared catalogues with copy-multiplicity and overlap rules**
(pinochle); the **completability quantifier** (gin + canasta, independently
invented); and **collections of groups on the table** — dynamic, not twelve literal
zone names (kills canasta's worst-in-registry reads row and gin's A/B/C
triplication). Run/adjacency detection takes its meaning from the declared
`ranking:` — cribbage already parameterizes on it; the right precedent.

### Construct D — ordered ladders (skat, 500, tarot; 9-11 items)

A declared ordered domain with successor, **successor-within-a-projection** (500's
cheapest-bid-above-X-in-strain over a 2-D ladder with off-grid insertions —
ordinal scale ≠ point scale), and per-rung fields (value, level, multiplier — the
div/mod decoding disappears).

### The (e) tail — small, named, separate

Ordered (player, card) trick queries with play-order-first selection (belote, tarot);
suffix folds (cribbage pegging); prefix-scan (skat matadors); accumulator fold over a
derived domain (stud's side pots — the one true loop); provenance-carrying zones
(cribbage's seq_bits bit-packing); positional indexing into derived collections;
half-even rounding (tarot). None belongs inside A–D; each is its own tiny decision.

## How this changes the plan

The two-track framing survives; the spec structure doesn't. Five findings force
revisions:

1. **Tier 0 comes first, and it's bigger than expected.** The point table + ring
   search + arithmetic + the (a)-tier migrations eliminate primitives in ~10 games
   before any hard construct is designed. Cheap, independently shippable, and each
   makes the remaining clusters cleaner to spec.
2. **The combination model is TWO specs, not one.** A (plays: atomic,
   ordered, enumerate/beat) and B (groups: multiset, quotas, partitions,
   completability) share vocabulary but not operations. Folding them produces the
   speculative mega-construct the doctrine forbids.
3. **Action-space generation is a hard requirement on A (and B's codec), not an
   afterthought** — it's where a third of the climb-cluster code and its worst drift
   risk lives, and it must be multiset-aware from day one.
4. **Doctrine tightening is its own small piece**: move the pile→seat attribution
   engine-side; decide explicitly whether the six red legality predicates are
   grandfathered until Construct C or the doctrine's "never decisions" gets a
   carve-out for *pure candidate predicates*; the 500 participation computation
   should move toward the kernel regardless.
5. **The metric starts scoring immediately**: primitive-free games. Schnapsen is
   eliminable today (its logic is already stdlib; the shell is trace/attribution —
   both engine concerns). Coup is one ring-search away. The count is 0/15 now and
   the roadmap should state the expected count per shipped tier.

Suggested spec order: Tier 0 (one spec, many small PRs) → sidecar relocation
(orthogonal, immediate, stops the littering) → Construct C (independent of A/B,
biggest single-construct coverage, informs the `ranking:` surface) → Construct A
(+ action-space generation) → Construct B → Construct D (anytime, small). Each
construct spec inherits its witness list and requirements table from this note —
the primitives are the requirements, already debugged against real games.

---

# Appendix — evidence tables (pickup reference)

Everything below was verified 2026-08-01 by three parallel readers over the actual
modules. **Nothing in this note is ruled** — it is evidence and a recommended order.
A fresh conversation can pick up any single item: Tier 0 entries are individually
shippable PRs; each construct gets a `docs/plans/` spec per convention when its turn
comes; glossary terms (Owner Guard, Transfer, Mode, …) apply throughout. Open
decisions a pickup session should not re-derive: (i) whether the six red-flag
legality predicates are grandfathered until Construct C or the doctrine gets an
explicit *pure candidate predicate* carve-out; (ii) sidecar relocation timing
(design already sketched in `reads.py`'s own docs: a `primitives { }` block in the
game file); (iii) whether contract-dependent ranking rides the `mode` body's
reserved slots.

## A1 — Tier 0 kill lists (named functions per quick win)

- **Per-game card-point table on `cards:`** kills: `gin_card_points` (+`flat_points`,
  `gin_flat_points`, `gin_shown_points`), canasta `card_points` (+`canasta_meld_points`,
  `canasta_hand_points`), cribbage `_VALUE`/`value` (`peg_value`),
  `tarot_card_points`, `tichu_card_points`/`_points`. The existing builtin
  `card_value` already reads `rs.card_values` — empty for standard52; the gap is
  declaration syntax only.
- **Ring search** (`first seat from p in order where P, with default`) kills:
  `coup_next_in_game`, `tichu_next_holder`, builtin `player_holding`; with a
  compound-key argmax/argmin variant also `bring_in_seat`, `first_to_act_seat`
  (stud `_lowest_door`, `_highest_upcards`).
- **Integer `//` / ceiling** kills: `skat_effective_loss`, `five_hundred_bid_level`.
- **First/last of an ordered zone** kills: builtins `top_of`/`bottom_of`,
  canasta `_top_card`/`canasta_pile_rank`.
- **(a)-tier migrations, no new language needed**: `coup_players_in`,
  `tichu_players_holding`, `tichu_partner`, `tichu_opponent_team`,
  `tichu_double_victory`, `tichu_first_out`, `coup_has_char`,
  `president_is_top_rank`, `canasta_discard_ok`, `canasta_red3_bonus`,
  `canasta_black3_ok`, `canasta_add_ok`, `initial_minimum`, `canasta_bonus_for`,
  `nob_score`, `flush_score`, `_pool` (500), tarot `_is_bout` (already duplicated
  in the game file), `tarot_per_opp` (except its half-even rounding). Builtin →
  stdlib candidates: `team_of`, `rank_value`, `card_value`, `strain_index`,
  `suit_of` (caveat: dispatches on Card-or-zone shape). Not migratable: `error`
  (control flow), the six board arms (read `rs.board`).

## A2 — Construct C: the per-game ordering coverage matrix

| game | trump set | trump order | plain order | follow-class remap | special card | led-class | ties | selector |
|---|---|---|---|---|---|---|---|---|
| schnapsen | one suit | = ranking | = ranking | none | none | first card | n/a | turned card |
| belote | one suit | J 9 A 10 K Q 8 7 | ace-ten | none | none | first card | n/a | naming (round 2) |
| doko | Q∪J∪♦∪{♥10} | ♥10 > Qs > Js > ♦ A 10 K 9 | A 10 K 9 minus trumps | none | none | first card | **first played wins** | static |
| skat | J∪trump / J / **∅** | CJ SJ HJ DJ + A 10 K Q 9 8 7 | A 10 K Q 9 8 7 **or** A K Q J 10 9 8 7 (Null) | jacks → "trump" | none | first card | n/a | is_null/is_grand/trump_suit |
| tarot | atouts | 1..21 numeric | K Q C J 10..1 | none | **Excuse never wins** | first **non-Excuse** | n/a | static |
| 500 | trump ∪ left bower ∪ joker / ∅ | joker > RB > LB > A..4 | A..4 over 43-card pack | joker+bowers → "trump"; joker → nominated suit (mid-hand!) | **un-nominated joker beats all** (NT) | follow_class(first) | n/a | trump/misère/joker_suit |

Belote additionally needs FOUR simultaneous named orders (plain, trump, natural
A-K-Q-J-10-9-8-7 for sequence detection, carré strength) plus `_HEIGHT_OF_CLASS`,
a map from declaration class → which order interprets a Rank parameter. Skat's
`_trump_order()` returns the ordering as an explicit list — "ranking as a value"
already exists, in Python. President's transparent threes (a play minted with
`key = current.key` — strength *inherited from the play it beat*) is the climb-side
witness. The shared program: *argmax TRUMP_ORDER over trumps if any, else argmax
PLAIN_ORDER over cards in the led class* — four context-computed slots.

## A3 — Construct A: pattern vocabulary and operations (climb + stud-classify)

| Pattern | Tichu | Big Two | President | Stud (classify) |
|---|---|---|---|---|
| single | ✓ | ✓ | size 1 | — |
| n-of-a-kind 2..4 | pair/triple/bomb(4) | pair/triple | **all n=1..4 parametric** | pair/trips/quads |
| two pair | — | — | — | ✓ |
| full house (3+2) | ✓ | ✓ | — | ✓ |
| run(L), any suit | L **5..14 variable** | L=5, 10 windows incl. wheel | — | L=5 + wheel |
| same-suit run | omitted (scope) | ✓ | — | ✓ |
| flush(5) | — | ✓ | — | ✓ |
| run of pairs | L **2..7** | — | — | — |
| n-kind + kicker | — | quads+lowest spare | — | quads |
| wildcard-completed | Phoenix (pair/triple/FH) | — | — | — |
| null/terminator | dog | — | — | — |

Operations (all witnessed): enumerate-in-hand (with sub-window expansion of maximal
runs); legality-vs-standing (`same shape ∧ higher key`, perturbed by cross-kind
bombs, context-strength wildcards, rank absorption); compare by composite key
(Big Two's lexicographic `(type, top, suit)` tuple; Tichu's **fractional** Phoenix
key `current.key + 0.5`); **classify+score a given set** (stud `_rank5` — the
inverse direction; a model that only enumerates leaves stud untouched);
**pattern precedence/exclusivity** (monochrome straight IS a straight flush — the
universe-soundness invariant "each card-set at most once"); representative-selection
as a *declared policy* (Big Two documents a real coverage hole from it — opening-3♦
multi-card leads); **derive the action space** — enumerate when small, arithmetic
codec when not. The three `Play` dataclasses: climb consumes only `.cards` and
`getattr(play, "ends_trick", False)` (duck-typed, only Tichu defines it); they
disagree on `length` (Tichu: shape length, NOT card count) vs `size` (card count),
and on key type (float / tuple / int). Unified model: call it `shape`, derive count.
Tichu's engine is ~60% generic machinery; the specific 40% is four declarable
modifiers: wildcards, bombs, off-ladder specials, terminator.

## A4 — Construct B: minimum feature set (meld/scoring)

Groups as first-class **multiset** values (canasta108 duplicates break `frozenset`
codecs — soundness); enumeration: subsets of size k, subsets satisfying P, and
**disjoint partitions** of a zone; aggregation over the enumeration: count, sum,
**min/argmin** (gin deadwood = min over partitions; cribbage fifteens = 2 × |{S:
|S|≥2, Σvalue=15}|); declared catalogues with copy-multiplicity + one overlap rule
(pinochle: trump run subsumes its own marriage); category quotas + wildcard roles
with best-value assignment (canasta: w≤3, n≥2, n+w≥3; joker-50 vs deuce-20 can
decide the initial minimum); **completability quantifier** ("∃ a legal completion
of this partial group") — invented independently by gin (`gin_arrange_ok`) and
canasta (`_completable`); **collections of groups on the table** (kills gin
meldA/B/C triplication and canasta's 12 literal meld zones — the reads registry's
two worst rows exist solely for this); run/adjacency meaning taken from the
declared `ranking:` (cribbage already parameterizes on `rank_index` — the correct
precedent); multiset-aware codec generation (replaces the hand-registered
`GIN_MELD_CODEC`, 329 melds = 65 sets + 264 runs). Staging state that exists only
to hold a half-built group (canasta `meld_rank`/`taking_pile`/`stage`, gin `taken`)
dissolves when groups are values.

## A5 — the (e) tail, each with witnesses

Ordered (player, card) trick query, play-order-first (`belote_royal_player`,
`tarot_excuse_player`); suffix folds over an ordered zone (cribbage
`peg_pair_points`, `peg_run_points`); prefix-scan (`skat_matadors` — the corpus's
only inherent loop over a runtime-length ordering); accumulator fold over a derived
domain (stud `_payouts` side pots — the one true iteration); provenance-carrying
zones + index-of + bitwise decode (cribbage `peg_origin`/`peg_origin_of`,
`seq_bits`/`seq_len` state — a temporal contract: must read before the pile drains);
positional index into a derived collection (`belote_decl_slot`); half-even rounding
of a half-integer (`tarot_per_opp`); choose-k subset argmax (stud `hand_rank`,
C(7,5) — the joint-selection bound is 2^n pool-size, NOT choose-k, so it cannot
help); "current winner of the in-progress trick" + actor in `applies_when`
(`belote_opp_winning`).

## A6 — dispatch and registry census

`call()`: 99 arms (98 named + default) as surveyed. Re-measured 2026-08-01 at
the split (issue #201): **100 named + default**, the two added arms being Hold'em's
`holdem_next_entrant` / `holdem_pot_share`. The generic/game-specific line is
unchanged and is now structural — the generic arms are `runtime/builtins.py`, the
game-specific ones `runtime/primitives.py`, and
`tests/test_native_dispatch_split.py` derives both counts from the source rather
than restating them here.

Generic 15: board `lines`, `neighbor`,
`has_step`, `is_diagonal`, `home`, `far_row`; non-board `player_holding`, `team_of`,
`suit_of`, `strain_index`, `error`, `rank_value`, `card_value`, `top_of`,
`bottom_of`. Game-specific 83: canasta 17, gin 13, belote 10, tichu 9, cribbage 6,
five_hundred 6, skat 5, tarot 5, coup 4, stud 3, pinochle 1, bigtwo 1, schnapsen 1,
doko 1, president 1. The `builtins/functions.py` partition (GENERIC 20 / DECK_ONLY 72 /
BOARD_ONLY 6, pinned by tests, never derived by subtraction) classifies by
**flavor, not game**: 15 of the 20 "GENERIC" names are game-named but content-blind.
Other dispatchers, all in `runtime/primitives.py`: `value_function` (5 arms: 2
generic trick winners + tarot/belote
+ default), the climb trio (3 games each), `joint_codec_function`
(gin only), `climb_codec_function` (tichu only), `auction_outcome_function`
(bridge/pinochle/tarot). `reads.py`: 19 rows / 15 games; outliers canasta
(15 zone families + 5 state vars) and gin (6 families) — both symptoms of missing
group collections; `runtime/primitives.py` itself holds 4 rows (three auction
outcomes + cribbage pegging call sites).

## A7 — bounds and performance facts

`_JOINT_ENUMERATION_BOUND = 16` (2^n subsets, pool-size cap — cannot express
choose-k); Tichu universe **211,204,694** plays (straights 208,779,520 = 98.85% —
why it is codec-not-list); Big Two universe 19,898, enumerated and golden-pinned
(codec deliberately `None` to keep pinned ids byte-identical); President universe
195; `ClimbForm` 5000-play non-termination guard; universe soundness invariant
stated twice in code: *supersets safe, collisions fatal* — each card-set appears at
most once, which is what pattern exclusivity buys.

## A8 — doctrine flag roster

**Red (the predicate IS the move filter):** `skat_follow_ok`,
`five_hundred_follow_ok`, `five_hundred_lead_ok` (+ pure cores `follow_ok`,
`lead_ok`), `belote_best_is`. **Amber (decision input / option generation):**
`belote_opp_winning`, `belote_decl_slot`, `tarot_led_suit`, `skat_next_bid`,
`five_hundred_next_bid`. **Structural:** `five_hundred_trick_winner` computes
misère participation (the dead seat) — table structure in a value primitive; the
pile→seat attribution zip (doko/skat/500) is engine plumbing with an admitted
silent-mislabel risk (doko.py ~70-72). **Exemplars of the clean shape:** stud's
`_payouts` ("returns the chip delta rather than mutating a stack" — the DSL
performs the effect) and coup.py throughout.
