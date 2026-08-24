# Folding a repeated, parameterized `round` block

**Tier 3 — medium impact, narrow scope.** Surfaced by the Seven-Card Stud betting
migration ([games/seven-card-stud.cardlang](../games/seven-card-stud.cardlang)),
which writes five near-identical betting `round`s. The *within-round* duplication
(the ring filter named in both `over` and `until`) is now factored with named
functions ([decisions.md](../decisions.md), "Named functions"). What remains is the
*block-level* repetition: the five rounds themselves.

The 3rd street and the four later streets (4th–7th) run the same betting `round`;
the later four differ only in two values — the bet `limit` (5 / 10 / 10 / 10) and
the dealt card's destination (`upcards` face-up on 4th–6th, `hole` face-down on
7th). With no construct to iterate a list of per-iteration parameters, the file
unrolls them into four flat `if (contenders > 1) { … }` blocks.

The kernel `round` is reusable, but the *surrounding street structure* is not. The
grammar offers `repeat until <pred>` (a loop counted by a predicate, no
per-iteration binding) and `for each <type> <var>` (a loop over the player/team
*ring*), but nothing that loops a literal, heterogeneous parameter list such as

```
for each street (limit, face_up) in [(5, up), (10, up), (10, up), (10, down)] {
  burn one card
  deal one card from deck to each non-folded player's (face_up ? upcards : hole)
  … the betting round, reading `limit` …
}
```

The shape recurs in any multi-street betting game; the natural second instance is
Texas Hold'em ([games/_candidates.md](../games/_candidates.md)), whose four
streets are the same pattern at different limits.

## The options

- **Add a list/`for each in [...]` loop** — binds per-iteration parameters from a
  literal list. Folds the four streets into one body. A new control construct;
  needs a value-tuple or parallel-list surface the grammar doesn't have yet.
- **Defer — keep the unrolled form.** It is correct, byte-identical, and readable;
  the repetition is contained to one file and, with the predicate now factored,
  each round is short. No blocking pressure until a second multi-street betting
  game (Hold'em) makes the loop concrete.

**Current recommendation: defer.** The named-function factoring already removed the
duplication that carried a correctness hazard; the remaining block repetition is
cosmetic, and a list-loop is a real new construct best justified by a second
instance. Revisit alongside Hold'em.

Related: [decisions.md](../decisions.md) "Named functions" (the resolved
within-round factoring) and "The auction form of `round`" (the betting form and
the ring it runs on), [games/_candidates.md](../games/_candidates.md) (Hold'em,
the second-instance data point).
