# First-class meld groups

**Tier 2 — high impact, blocked on Canasta (the remaining data point).**

The *formation* half of the original question is settled:
[decisions.md](../decisions.md) "Joint-predicate selection" gives movements a
joint mode — `move chosen some cards from <zone> where jointly <pred>` binds
`cards` (the candidate set) and selects one satisfying subset as a single
decision. Gin Rummy anchors it: the showdown arrangements are joint
selections, the "these K cards together form a valid run" test is a joint
predicate, and the OpenSpiel action space takes the subset universe from a
registered per-predicate codec (the 329-meld universe of standard52).

What remains open is melds as first-class *objects*:

- **Shared, growing, keyed groups.** Canasta's melds are team-owned piles
  keyed by rank — a `(team, rank)`-indexed zone family (zone families take
  exactly one index today) — that grow across turns under wild-card
  composition rules checked at every extension, not only at formation.
  Gin's bounded three-slot zones (`meldA/B/C[player]`) deliberately do not
  model this: they hold a one-shot arrangement, revealed once and extended
  only by layoffs whose legality is a plain per-card predicate.
- **Per-group scoring.** Canasta scores each meld by its composition
  (natural vs mixed canastas); Pinochle's meld tally still runs on a flat
  Counter primitive (`pinochle_meld_value` — the repetition
  [library.md](../library.md) flags). A group object with declared validity,
  owner, projection, and comprehension access would subsume both.

**Current recommendation: design the group object against Canasta when it
enters the corpus** — the joint-selection primitive plus bounded meld zones
carried Gin without it, so the forcing function is genuinely the shared
growing-pile shape, not the rummy family per se.

Related: [decisions.md](../decisions.md) "Joint-predicate selection" (the
settled half); [games/_candidates.md](../games/_candidates.md) (canasta);
[library.md](../library.md) (Pinochle's flagged meld repetition).
