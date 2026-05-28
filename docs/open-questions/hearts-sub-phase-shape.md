# Hearts sub-phase shape

**Tier 5 — cosmetic, no design risk.**

Hearts models `first_trick` as a top-level phase sibling to `play`.
Alternative: a sub-phase of `play` that fires only on the first
iteration. Sibling reads more cleanly but loses the "all play
happens inside `play`" property. Cosmetic but worth resolving.
