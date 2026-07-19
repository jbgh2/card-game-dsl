# Combination structure over cards — the language's largest recurring hole

Status: exploratory analysis (proposal, not settled spec). Provenance: the
Salvo experiment (`experiments/salvo/`) reached its combos-and-jokers round
and stopped, by design review, rather than add another per-game stdlib
primitive. This note characterizes what the language cannot currently say,
how often the corpus has already paid for that in Python, and a two-tier
proposal shaped in review with the designer. It composes with
[primitive-sidecars.md](primitive-sidecars.md), which owns the escape
tier's mechanics. Nothing here is decided.

## The hole, stated

The language has no way to ask a zone about the COMBINATORIAL STRUCTURE of
its contents: which same-rank groups it holds and how large, its longest
run of consecutive ranks, its largest same-suit group, whether a subset
sums to a target. Per-card predicates (`where card.suit is spades`),
counting (`number of cards in Z where ...`), and per-card aggregation
(`sum of f(card) over cards in Z`) all exist; anything requiring GROUPING
or ADJACENCY across cards does not. Every game that needed it got a
registered Python primitive.

## The witnesses (six shipped, one blocked)

| witness | what it recognizes | where the Python lives |
|---|---|---|
| Cribbage's show | fifteens (subset sums), all pairs, runs with multiplicity, flushes, his nobs | `cribbage_show_value`, `cribbage_crib_value` |
| Seven-Card Stud's showdown | full poker ranking, best five of seven | `pot_share` |
| Climbing vocabularies (Big Two, Tichu) | singles, pairs, triples, full houses, straights, pair sequences, bombs — enumerated AND compared | `runtime/combinations.py` |
| Gin's melds | sets and suited runs; arrangement validity; deadwood | `gin_valid_meld` and kin |
| Canasta's melds | rank groups with wild participation, naturalness, canasta size | seven `canasta_*` signatures |
| Pinochle's melds | trump-parameterized marriages, the exact-card pinochle, aces around, double melds | `pinochle_meld_value` ("a hand's meld under trump") |
| **Salvo (blocked)** | best-instance of-a-kind, longest run, largest flush, per-location bonus table, jokers excluded | — stopped here |

Six independent Python islands implement overlapping recognizers; the
climbing engine's are not even reachable from scoring code in the same
runtime. Scoring primitives carry no info-set debt — they are pure
functions at settle — so this is an EXPRESSIVENESS hole, not a
correctness one; the cost is who gets to define games, and how completely
the machine can check them.

## The two-tier shape (the designer's ruling)

Growing one construct toward completeness would build a scoring DSL
inside the game DSL. Instead:

- **Tier 1 — the `combinations` construct** covers the frequency-
  structure core only: the cluster all six witnesses share. Its stopping
  rule is principled: the construct ends where declarations stop reading
  like a rulebook and start being programming.
- **Tier 2 — declared pure-Python sidecars** ([primitive-sidecars.md](primitive-sidecars.md))
  carry every odd case: sealed values-in/value-out interface (no `Ctx`),
  a `primitives { }` declaration block in the game file with typed
  signatures and declared reads, implementations co-located with their
  game. The declaration block doubles as the per-game inventory of what
  the DSL cannot yet say; a shrinking block is the visible score.

Tier 1 exists to make the common cases designer-authorable and
checker-visible. Completeness lives in tier 2, where it is cheap.

## Tier 1: the algebra (frozen core)

Four pattern primitives — a closed registry:

| primitive | matches a set of cards that is... |
|---|---|
| `<n> of a kind` | n cards of one rank |
| `run of <n>` | n distinct consecutive ranks, one card each |
| `flush of <n>` | n cards of one suit |
| `set totalling <k> by <fn>` | a subset whose values under fn sum to k |

Three combinators: intersection (`run of 3, all one suit` — the suited
run), disjoint union (`3 of a kind with 2 of a kind` — the full house),
and rank multiplication (`run of 3, each rank twice` — Tichu's pair
sequence). Two counting modes, carried by the header's English:
`score the largest ... once` (best instance per family) and
`score each ...` (every instance — under which cribbage's trips scoring
as three pairs falls out arithmetically). One exclusion/wilds clause.

**Adjacency correction** (found in review): a run's rank order is its
own declarable order, defaulting to natural ace-to-king, and is NOT the
strength `ranking:` — Big Two's strength order (3 low, 2 high) is not
its straight order. Salvo masked this because its ranking is natural.
No wraparound; a wraparound toggle is deferred behind a wall.

The surface, in the language's register (no indefinite articles — the
corpus's determiners are all semantic: one/all/each/any/the; "of a
kind" keeps its `a` as a lexicalized idiom, and `the` in mode headers
has the same selector force as `the player where`):

```text
combinations salvo_combos {
  counting only cards where card.suit is not joker

  score the largest of a kind once:
    2 of a kind: 4
    3 of a kind: 12
    4 of a kind: 20

  score the longest run once:
    run of 3: 6
    run of 4: 10
    run of 5 or longer: 15

  score the largest flush once:
    flush of 3: 5
    flush of 4: 9
    flush of 5 or longer: 14
}
```

```text
combinations cribbage_show {
  score each set totalling 15 by peg_value: 2
  score each pair: 2
  score each maximal run:
    run of 3: 3
    run of 4: 4
    run of 5: 5
}
```

Query form, in expression position like any aggregation:
`score of army_a[p] under salvo_combos`. The floor queries
(`length of the longest run in Z`, `size of the largest of a kind in Z`)
are sugar for one-row tables — the same evaluator, so the floor can ship
first and grow the declaration surface without a second construct.

Open lexical points, recorded not decided: `with` vs `plus` as the
disjoint-union word; whether `pair` is the single blessed alias for
`2 of a kind` (every alias is surface with totality cost); `totalling`
vs `summing to`.

## Coverage and non-goals (what tier 1 cannot handle, and where each goes)

To tier-2 sidecars, with witnesses already in the corpus:

- **State-parameterized patterns** — Pinochle's royal marriage ("K and Q
  of trump"); any "flush of the affinity suit" bonus.
- **Exact-card patterns** — the pinochle (J of diamonds with Q of
  spades); Doppelkopf's club queens.
- **One-of-each shapes** — aces around (one of every suit).
- **Superlinear multi-instance values** — double pinochle at 30, not 8.
- **Relational joins** — his nobs, flush-with-starter (patterns
  referencing another zone's card).
- **Grouped aggregation** — Scopa's primiera (best card per suit, then
  sum): aggregation, not combination.

To their own constructs or existing surface, not sidecars:

- **Partition/arrangement** — Gin's "hand arranges into melds leaving
  deadwood at most 10", rummy contracts: set-cover over the SAME
  patterns, a future `arranges into` query, recorded.
- **Composite lexicographic ranking** — poker's category-then-kickers:
  deferred until a second ranking witness.
- **Order-sensitive patterns** — cribbage's pegging runs: already
  expressed in-DSL today (`seq_bits`/`seq_len`); stays there.

## The joker sub-question (mostly not a hole)

Joker CARDS are already first-class: three decks carry `("Joker",
"joker")` cards, rankings may list `Joker` explicitly (Five Hundred's
does), `card.suit is joker` predicates and filtered movements (`move one
card from deck where card.suit is not joker`) are ordinary surface.
Salvo's joker rules are expressible TODAY except that no
standard-52-plus-two-jokers deck exists. A `standard54` registry row is
data, not an escape hatch — but the sharper question is whether decks
should be DECLARABLE from game files (the family-library `uses` tier on
its unmerged branch reportedly introduces small declared decks;
reconcile with that work rather than beside it). Wild participation in
combinations belongs to tier 1's wilds clause (exclusion — Salvo) with
substitution (Canasta) walled to of-a-kind families when it lands.

## Sequencing fork (the open decision)

Both tiers pay the surface-totality tax; they can land in either order:

- **Sidecars first** (`primitives { }` block, stage 3 of that note's
  sequence): the smaller grammar change; unblocks Salvo and every odd
  case at once; tier 1 then drains the six-witness cluster out of the
  blocks at leisure.
- **Combinations first**: the higher-value language investment; Salvo
  and cribbage's show become designer-authorable immediately; the odd
  cases keep their current (undisciplined) registry primitives until
  sidecars land.

Either way, no new-style registry primitive ships meanwhile; Salvo's
round 5 stays blocked until one of the two lands.
