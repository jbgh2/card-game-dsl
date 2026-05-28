# Sub-phase rule syntax

**Tier 1 — high impact, ready to commit.**

Sub-phases need to extend/override parent rule sets. Provisional
syntax used in three games (Hearts, Spades, Pinochle):

```
phase parent { active_rules: [A, B, C] }
phase child  { active_rules: [+ D] }              // extends parent: A, B, C, D
phase child2 { active_rules: [- B] }              // removes from parent: A, C
phase child3 { active_rules: [override A2] }     // replaces A with A2: A2, B, C
```

The provisional syntax has been load-bearing for three games
without surfacing problems. Other possible idioms (explicit listing,
named rule sets) exist but the `+ X` / `- X` / `override X` form
reads cleanly at the call site. Commit unless a concrete alternative
emerges.

**High impact:** every game with sub-phases uses this.
**Ready now:** three data points, all consistent.
