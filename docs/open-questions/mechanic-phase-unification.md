# Mechanic-phase unification

**Tier 2 — high impact, blocked on a data point.**

`Auction` (callback-style outcome), `Trick` (outcome parameter),
and `BettingRound` (typed structural outcome) all resolve to
typed values; phases also resolve to typed outcomes (see
[decisions.md](../decisions.md), "Typed phase outcomes"). Unifying
these into one mechanism — mechanics-as-phases or
phases-as-mechanics — would simplify the model.

**Blocker:** Need a seventh game where this pattern shows up
distinctively to validate that the four constructs really are
special cases of one thing, rather than four similar-shaped
constructs that happen to look like each other in the current
corpus.
