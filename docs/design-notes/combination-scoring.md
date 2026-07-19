# Combination structure over cards — the language's largest recurring hole

Status: exploratory analysis (proposal, not settled spec). Provenance: the
Salvo experiment (`experiments/salvo/`) reached its combos-and-jokers round
and stopped, by design review, rather than add another per-game stdlib
primitive. This note characterizes what the language cannot currently say,
how often the corpus has already paid for that in Python, and the option
space for closing the hole. Nothing here is decided.

## The hole, stated

The language has no way to ask a zone about the COMBINATORIAL STRUCTURE of
its contents: which same-rank groups it holds and how large, its longest
run of consecutive ranks, its largest same-suit group, whether a subset
sums to a target, how one structured set compares to another. Per-card
predicates (`where card.suit is spades`), counting (`number of cards in Z
where ...`), and per-card aggregation (`sum of f(card) over cards in Z`)
all exist; anything requiring GROUPING or ADJACENCY across cards does not.
Every game that needed it got a registered Python primitive.

## The witnesses (five shipped, one blocked)

| witness | what it recognizes | where the Python lives |
|---|---|---|
| Cribbage's show | fifteens (subset sums), all pairs, runs with multiplicity, flushes, his nobs | `runtime/cribbage.py` (`cribbage_show_value`, `cribbage_crib_value`) |
| Seven-Card Stud's showdown | full poker ranking, best five of seven | `runtime/` stud module (`pot_share`) |
| Climbing vocabularies (Big Two, Tichu) | singles, pairs, triples, full houses, straights, pair sequences, bombs — enumerated AND compared | `runtime/combinations.py` (`_combos`, `_legal_follows`) |
| Gin's melds | sets (of-a-kind) and suited runs; arrangement validity; deadwood | `gin_valid_meld`, `gin_arrange_ok`, `gin_shown_points` and kin |
| Canasta's melds | rank groups with wild participation, naturalness, canasta size | seven `canasta_*` signatures |
| **Salvo (blocked)** | best-instance pair/trips/quads, longest run of 3+, largest flush of 3+, per-location bonus table, jokers excluded | — stopped here |

Five independent Python islands implement overlapping recognizers; the
climbing engine's are not even reachable from scoring code in the same
runtime. The stdlib call registry carries roughly ninety-five signatures,
a large share of them game-named; this family is its biggest single
cluster. The repo's own promotion doctrine triggers at the second
instance of a pattern — this one is at its fifth, held down only because
each instance arrived inside a registered primitive rather than as a
surface request.

Why this matters beyond tidiness: primitives are opaque to the totality
checker (nothing enumerates what a Python function accepts or ignores),
invisible to designers (adding a combo means a repo commit, not a game
file edit), and each new one deepens the pattern the kernel migration
existed to reverse. Scoring primitives carry no info-set debt — they are
pure functions at settle — so this is an EXPRESSIVENESS hole, not a
correctness one; the cost is who gets to define games, and how completely
the machine can check them.

## What varies across the witnesses (the design dimensions)

- **Structures**: same-rank groups; consecutive-rank runs (suited or
  not); same-suit groups; subset sums (fifteens); composite lexicographic
  rankings (poker); "full house"-style products of simpler structures.
- **Counting mode**: best-instance-once (Salvo); every-instance-with-
  multiplicity (cribbage counts each pair and each run reading); maximal
  only (longest run); validity (gin's melds); enumeration of playable
  sets (climbing); comparison/beats (climbing, poker).
- **Output shape**: an integer score; a boolean; a chosen card set; a
  ranking usable in a comparison.
- **Adjacency source**: the declared `ranking:` (whose list is
  strongest-first — any run construct must define its reading direction
  and whether the ends wrap; no witness wraps today).
- **Wilds**: excluded entirely (Salvo's jokers), or participating as
  substitutes with naturalness limits (Canasta's wilds); Tichu's
  Phoenix-as-wild is a recorded omission in the climbing engine.

## Options

**A. Combination queries** — a small family of zone/collection
expressions: `largest same-rank group in Z`, `longest run in Z`,
`largest same-suit group in Z` (each an Integer; possibly collection-
valued variants later). Game code maps sizes to bonuses with ordinary
if-chains. Smallest new surface; covers Salvo outright and gin-style
validity partially; does not cover fifteens, poker ranking, or
multiplicity counting. Totality burden: each query total over collection
expressions, with the run query's adjacency pinned to the declared
ranking and its orientation stated.

**B. Declared combination tables + one kernel evaluator** — a game-level
block naming patterns from a closed pattern algebra (of_a_kind(n),
run(n), suited_run(n), flush(n), sum_to(k), ...) with per-pattern values
and a counting mode; one expression form evaluates a zone against the
declared table. The recognizer is shared kernel code, the game content is
data — the same shape as the climbing vocabularies and the discipline the
capstone's location effects will eventually need. Covers Salvo, cribbage
(fifteens included via sum_to), melds; poker's composite ranking needs a
ranking mode or stays out. Larger surface: the pattern algebra is a new
closed domain with full enumeration obligations.

**C. Unify with the climbing vocabulary** — promote
`runtime/combinations.py`'s play kinds into a declared pattern registry
referenced by BOTH move vocabularies and scoring queries, so "a pair"
means one thing everywhere and the beats-relation and the bonus table
read the same structures. Deepest consistency (pure functions + closed
verbs, per the generalization-path doctrine); largest design and
migration cost; touches the climbing games' encodings.

**D. Status quo** — another registered primitive per game. Rejected as
the default by this review's mandate: it is precisely the pattern the
experiment existed to surface. Recorded because it remains the fallback
if the hole is deliberately deferred — in which case each new primitive
is logged as expressiveness debt at its birth, not silently.

## The joker sub-question (mostly not a hole)

Joker CARDS are already first-class: three decks carry `("Joker",
"joker")` cards (their own rank and suit), rankings may list `Joker`
explicitly (Five Hundred's does), `card.suit is joker` predicates and
filtered movements (`move one card from deck where card.suit is not
joker`) are ordinary surface. Salvo's joker rules are expressible TODAY
except for two items:

1. **No standard-52-plus-two-jokers deck exists.** A `standard54`
   registry row is data, not an escape hatch — but the sharper question
   is whether decks should be DECLARABLE from game files at all (the
   family-library `uses` tier on its unmerged branch reportedly
   introduces small declared decks for Kuhn/Leduc; reconcile with that
   work rather than beside it).
2. **Wild participation in combinations** belongs to whichever option
   above wins (exclusion is Salvo's need; substitution is Canasta's) —
   a wilds clause in the pattern algebra, or per-query filters.

## Recommendation

Treat option A as the floor and option B as the target: A's three
queries are the smallest honest closure of Salvo's need and two of
gin's, and they are forward-compatible with B (a declared table can
compile to the same recognizers). Decide B's pattern algebra against
the full witness table, not Salvo alone, and fold the wilds clause in
from the start because Canasta is already waiting. Option C stays the
long-run pull; poker ranking stays out of scope until a second ranking
witness appears. Whatever is chosen goes through the surface-totality
gate as a genuinely new closed domain.

Until the decision: Salvo's combos-and-jokers round is BLOCKED and says
so in its report; no new per-game primitive ships for it.
