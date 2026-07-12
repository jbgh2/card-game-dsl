# Family libraries: an import tier between game-local and stdlib

**Tier 2 — high impact, blocked on a data point: the second poker-family
game.** The sharing model today is a two-tier dichotomy: a definition is
either game-local or promoted to the stdlib at its third corpus instance.
A family of related games breaks that dichotomy. Seven-Card Stud's betting
machinery — `pot_share`, `bring_in_seat`, `first_to_act_seat`, the
`check`/`bet`/`call`/`raise`/`fold` move vocabulary, the
`can_act`/`owes`/`pending` ring predicates — is shared across every poker
variant but has no business being universal. Without a middle tier, family
code either gets pasted per game (the shape that left `MustFollowSuit`
restated in seven files) or pollutes the stdlib with domain knowledge
(the boundary [design-notes/primitive-sidecars.md](../design-notes/primitive-sidecars.md)
exists to defend).

The data point is guaranteed to arrive: the OpenSpiel target ships Kuhn
poker, Leduc poker, and universal_poker, so "support what OpenSpiel
supports" forces a poker family. Kuhn and Leduc are also small enough that
a shared-betting corpus would be testing the *sharing mechanism*, not the
games. The same tier serves other families as they form: climbing games
(Big Two and Tichu already hold deliberately game-local combination
engines awaiting a third instance), rummy/meld games
([meld-groups](meld-groups.md)), and trick-family rule cascades beyond the
universal ones.

## The shape being asked for

A **library** is a file containing exactly the definition forms games
already contain — move_types, rules, functions, a `primitives { }` block
([design-notes/primitive-sidecars.md](../design-notes/primitive-sidecars.md)),
procedures when they exist — with no new content forms. A game names what
it uses:

```
game TexasHoldem {
  uses poker_betting
  ...
}
```

Resolution is flat and two-level: game → named libraries → stdlib. No
library-imports-library until something forces it. Imports are pure name
resolution — front-end only, no info-set or runtime implication.

Two constraints the design must satisfy:

- **The read-cold test refines rather than breaks.** The acceptance test —
  a non-player reads the file cold and can play a hand — strains under
  imports until one notices rulebooks import by name too: "betting
  proceeds as in standard poker" is Pagat's own practice. The readable
  unit becomes the game file plus its *named* libraries, and the `uses`
  line must read like the rulebook sentence it is — carrying information
  to a human reader, not just the resolver.
- **The nameability dependency.** An import system is only as good as what
  can be named. Shared rule definitions and named procedures are
  prerequisites, not siblings: importing from a library presupposes the
  definition forms exist to put in one.

## The options

- **Named libraries with explicit two-level resolution** (the shape
  above). Direct; keeps the stdlib game-independent; gives families one
  home per definition. Design cost: where library files live, whether
  `uses` imports a whole library or names definitions, and collision
  rules — all small, all needing a real second game to pin down.
- **Namespaced stdlib promotion** (`stdlib.poker.*`). Rejected in
  discussion: it relocates the boundary problem instead of solving it —
  the stdlib is maintained with the language, family libraries are
  maintained with the corpus, and merging them re-blurs exactly the
  boundary the sidecars note separates.
- **Textual include.** Rejected: no checked interface, no declared
  provenance, collision-prone — the accepted-but-ignored defect class
  waiting to happen at file granularity.
- **Defer.** Correct today by the corpus-first gate (one poker game is one
  instance), untenable once a second lands: pasting a betting engine
  across Kuhn, Leduc, and Stud would be the seven-file rule paste at ten
  times the size.

**Current recommendation: defer until the second poker-family game enters
the corpus (Kuhn or Leduc as stress-scale anchors, Hold'em as the
full-scale one), then design the minimal named-library mechanism against
it.** Sequence behind shared rule definitions and procedures, which it
presupposes.

One boundary to draw deliberately at design time: import-with-override is
naturally adjacent to the variants-as-deltas promise in
[principles.md](../principles.md) ("variants as small deltas on a base
game"), which still has no mechanism. Decide whether imports and variant
deltas are one mechanism or two *before* building either — composition
over inheritance says be careful that imports do not quietly become
inheritance.

Related: [design-notes/primitive-sidecars.md](../design-notes/primitive-sidecars.md)
(the sealed-primitive interface and co-location this tier would organize);
[meld-groups](meld-groups.md) (the rummy family, a second customer);
[games/_candidates.md](../games/_candidates.md) (the poker-family anchor
candidates).
