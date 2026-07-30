# Move-level visibility

**Tier 3 — medium impact, narrow scope.**

Zone declarations set default projections; move clauses override.
Override semantics is "the move's clause replaces the zone
projection for this event only." Cases like "downgrade further but
keep the zone's projection for everything not mentioned" might
want different semantics.

## The witness is now in the corpus

Texas Hold'em ([games/holdem.md](../games/holdem.md)) is in the corpus, and it
carries the rule this question has been waiting for: **"show one, show all"** —
at a contested showdown, a player who exposes part of their hand may be required
to expose the rest, but "if only a portion of the hand has been shown, there is
no requirement to show the unseen cards" (Robert's Rules of Poker §6). That is a
per-observer, per-event override naming *some* cards and *some* observers while
everything unmentioned stays at the zone default — which is the
replace-vs-merge sub-question stated as a rule rather than as a hypothetical.

The rule is deliberately NOT modelled: `holdem.cardlang`'s showdown reveals every
contender's hole cards, and the `.md` declares that simplification. So the
question is unblocked, not resolved.

Where it would bind, concretely: the showdown block's

```text
move all cards from hole[p] to shown[p]
```

is the event whose projection would carry the override. Today `shown[p]` is a
`PublicHand` and the move inherits identity-to-all; the rule needs that one
movement to project identity to a *named subset* of observers while the same
zone's other events keep the declared default. Stud's showdown is the same
movement shape (`hole[p] -> upcards[p]`), so whichever semantics is chosen has
two corpus call sites to answer to on the day it lands, not one.

What still has to be decided is unchanged, and the witness does not settle it: a
partial reveal is *by construction* the case where some of a zone's contents are
named and the rest are not, so replace-semantics has to say what happens to the
unnamed cards — inherit the zone default (merge) or fall to the override's level
(replace). Both readings are defensible on this rule, which is why it is the
sharp witness rather than the answer.
