# A reusable combination model for melding

**Tier 4 — low impact, defer until forced.** Melding works in the corpus, but
each game's meld scoring is a game-local Primitive rather than a shared
model, and the one place two meld categories genuinely overlap was resolved by
hand rather than by a rule the language owns.

Pinochle's meld phase is a flat `Counter`-based tally
(`pinochle_meld_value`, a game-local Primitive — the DSL body itself is
fully migrated, so this is a missing abstraction, not migration debt). Canasta
scores its melds through zone censuses over the meld zones themselves
(`canasta_canasta_bonus`, and the group *is* the zone — decisions.md "Joint
formation legality"). Neither shares anything with the other.

## The question

Should the language carry a **combination model** — a declarative way to say
"these card sets score, and here is how overlapping categories resolve" —
rather than each melding game hand-writing its tally?

The load-bearing half is not the tally; it is **conflict resolution**. Pinochle
has exactly one overlap that matters (a trump run subsumes the trump marriage
inside it), and `pinochle_meld_value` resolves it with a hand-picked
subtraction. A real model would resolve arbitrary category overlaps —
which categories are mutually exclusive, which nest, which may double-count,
and whether a card may serve two melds at once — from a declaration rather
than from one primitive's arithmetic.

## Why it is deferred rather than designed

Two corpus games meld, and they meld differently enough that a model derived
from both would be fitted to a sample of two. Pinochle's melds are scored from
a hand that is never moved; Canasta's are scored from zones the player builds
during play, with legality (not scoring) carrying the interesting rules.
Generalizing across those two would produce a model whose overlap semantics are
exercised by exactly one game's single overlap.

## The data point that would force it

A third melding game whose categories overlap in a way Pinochle's subtraction
does not cover — most plausibly a Rummy-family game where a card may be read
into more than one combination and the scorer must choose the best partition
(the classic "optimal meld decomposition" problem), or a game whose meld
categories are declared per-variant. Bezique and Sixty-Six sit in the same
family as Pinochle and would likely reproduce its shape rather than stress it;
a Rummy scorer would not.

Related: [decisions.md](../decisions.md) "Joint formation legality" (how meld
*legality* is already modelled, and why Canasta stages per card rather than
selecting subsets); [decisions.md](../decisions.md) "Scoring composition" (the
`scoring_component` design this would compose with, itself unbuilt — issue
\#115); [games/_candidates.md](../games/_candidates.md) (the game pipeline).
