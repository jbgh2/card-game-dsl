# Zone access syntax

**Tier 3 — medium impact, narrow scope.**

The language permits two forms of indexed access: `zone[receiver]`
(bracket form) and `receiver.zone` (dot form).
[decisions.md](../decisions.md) "Typed object model" commits to
the dot form as sugar for the bracket form. In the corpus the
two are used by an implicit discipline:

- Bracket form when the index is a computed expression:
  `hand[player]`, `captured[team_of(outcome)]`,
  `hand[player offset_by pass_direction]`.
- Dot form when the receiver is a simple identifier:
  `p.hand`, `outcome.hand`, `team.score`.

Open whether the dot form should admit complex receivers — e.g.,
`(player offset_by pass_direction).hand` or
`dealer.left.partner.hand`. Both forms are currently grammatical
at the sugar level; the corpus simply doesn't exercise
complex-receiver dot forms outside one hand-waved case.

A second open question is whether the bracket form should be
elevated to *the* canonical form, with the dot form purely
sugar (the current framing), or whether they should be
treated as co-equal in some contexts.

**Data point needed:** a game whose natural notation puts a
complex relational chain in subject position, where the
readability tradeoff between `chain.zone` and `zone[chain]`
becomes concrete.
