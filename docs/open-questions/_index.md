# Open questions

Designs that aren't yet committed. Each linked file is a real design
decision the language will eventually have to make; the file's body gives
the current best understanding of the tradeoffs.

Questions are ordered by impact × actionability. Tier 1 questions are
high-impact AND have enough data to commit to a design now; Tier 5
questions are cosmetic and carry no design risk. Within a tier, ordering
is rough — adjacent items can be tackled in either order.

When a question resolves, move its content to [decisions.md](../decisions.md)
(rewriting from question-voice into spec-voice), delete the file in this
folder, and remove the entry from this index. See
[maintaining.md](../maintaining.md) for the full hygiene rules.

**Tier 1 is currently empty** — all four original Tier 1 questions
have been resolved into [decisions.md](../decisions.md). Tier 2
items may be promoted to Tier 1 as further corpus data arrives.

## Tier 2 — High impact, blocked on a data point

These questions need one more game in the corpus before committing to a
design. The data point is named in each file.

- [bidding-meaning](bidding-meaning.md) — Auction should declare what the
  bid value targets. Blocker: a third bidding game.
- [structured-score](structured-score.md) — generalize Bridge's
  above/below-line and Stud's pots-with-eligibility into one shape, or
  let each game declare. Blocker: a third structured-score game.
- [mechanic-phase-unification](mechanic-phase-unification.md) — unify
  mechanics-with-outcomes and phases-with-outcomes into one construct.
  Blocker: a seventh game.
- [simultaneous-body-grammar](simultaneous-body-grammar.md) — should the
  `simultaneously:` body admit state writes, control flow, `let`?
  Blocker: a game whose natural rulebook reading needs them.

## Tier 3 — Medium impact, narrow scope

These don't block other work but resolving them improves specific corners
of the language.

- [typed-amount-syntax](typed-amount-syntax.md) — `{ wood: 2 }` vs `2 wood`
  vs `wood × 2`.
- [move-level-visibility](move-level-visibility.md) — override-replace vs
  override-merge.
- [transfer-failure](transfer-failure.md) — partial-fulfillment primitive
  or game-level only.
- [zone-access-syntax](zone-access-syntax.md) — `zone[chain]` vs
  `chain.zone` for complex receivers.
- [optional-window-moves](optional-window-moves.md) — `may submit X`
  for non-mandatory moves during a window (Tichu calls).

## Tier 4 — Low impact, defer until forced

These have known scope and aren't blocking anything. Adopt when convenient
or when a game forces the issue.

- [memory-event-syntax](memory-event-syntax.md) — declaration syntax for
  custom memory-affecting events.
- [higher-order-knowledge](higher-order-knowledge.md) — "does P know that
  Q knows X?".
- [knowledge-events](knowledge-events.md) — observer-dependent phase
  outcomes.
- [special-cards-declaration](special-cards-declaration.md) — `specials:`
  block and contextual-rank cards (Tichu's Mahjong, Dog, Phoenix, Dragon).
- [out-of-turn-moves](out-of-turn-moves.md) — `out_of_turn_legal`
  vs permitting-rules vs phase-level lists (Tichu bombs).

## Tier 5 — Cosmetic, no design risk

Naming and aesthetic choices. Pick when convenient.

- [move-type-naming](move-type-naming.md) — `move_type` vs `action_type`
  vs `operation` vs `move`.
- [hearts-sub-phase-shape](hearts-sub-phase-shape.md) — `first_trick` as
  sibling vs nested sub-phase of `play`.
- [phase-legal-moves](phase-legal-moves.md) — derive from `active_rules`,
  state explicitly, or hybrid.
