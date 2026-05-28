# Counters

**Tier 4 — low impact, defer until forced.**

"Cards worth points when captured" is universal in point-trick
games: Hearts has hearts (1pt each) and queen of spades (13pt);
Pinochle has A/10/K (10pt each); Skat has A=11, 10=10, K=4, Q=3,
J=2. Currently each game's scoring phase iterates the captured
pile and computes points inline.

Counters could be declarable on the card definition:

```
cards {
  ...
  counters: { A: 10, 10: 10, K: 10 }
}
```

Then scoring computations refer to `counter_value(card)` rather
than inlining the table. Readability win; no urgency.
