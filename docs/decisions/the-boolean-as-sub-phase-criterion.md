## The boolean-as-sub-phase criterion

A boolean state variable that *gates rules* should be a sub-phase
instead. A boolean that's *purely informational* (read by scoring or
similar end-of-phase logic, not by any rule's `applies_when:` or
`demands:`) stays a variable.

Examples:

- `hearts_broken` in Hearts: gates the `NoLeadingSuitUntilBroken(hearts)`
  rule. Modeled as a sub-phase transition, not a boolean.
- `spades_broken` in Spades: same shape, same treatment.
- `is_first_trick`: gates rules unique to the first trick. Modeled
  as a sibling sub-phase (Getaway's `first_trick`, whose cards go to
  the waste instead of to a winner) rather than a boolean — but only
  where no mode of the later tricks has to watch the first one. A
  mode's transition sees its own phase's instance alone, so Hearts
  plays its first trick as the first pass of `play`'s loop: a
  `first_trick` sibling would leave a heart played there unseen and
  hearts unbroken. A first trick whose only rule is a forced opening
  card needs no phase either — the rule demanding that card is empty
  on every later lead.
- `bid_abandoned` in Pinochle: a candidate boolean that would gate
  scoring branches. Modeled instead as a typed outcome on the
  `declare_trump` phase (see "Typed phase outcomes" above) — the
  phase resolves either to `trump_declared(Suit)` or `bid_abandoned`,
  and enclosing structure routes on the outcome.
- `dummy_revealed` in Bridge: read by zone-routing helper, no rule
  gates on it. Correctly a boolean.
- `pile_frozen` in Canasta: ZONE state (the discard pile is frozen or
  not) rather than phase state, and the criterion carries over unchanged
  — no rule's `applies_when:` reads it; it gates only the take-pile
  move's preconditions, and its operative meaning is per-side anyway (a
  team that has not melded is frozen out regardless, the
  per-player-exception shape below). Correctly a boolean.

The criterion: ask whether any rule reads the boolean in its
`applies_when:` clause. If yes, the boolean is hiding a phase
transition; refactor to sub-phases. If no, it's just data. The subject
of the boolean — a phase fact, a zone fact — doesn't change the test.

**Per-player exception.** A boolean indexed by player (e.g.,
`has_played_yet[player]` in Tichu) that gates only a move's own
preconditions is left as state rather than reified as a per-player
sub-phase. Reifying would require parallel sub-phase instances and
per-instance transition triggers — language surface the corpus has
chosen not to add. The boolean form keeps the gating in the move
type's `preconditions:` block, which is co-located with the move
it's about.
