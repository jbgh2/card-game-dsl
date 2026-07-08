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

## Tier 1 — High impact, enough data to commit now

- [move-parameter-domains](move-parameter-domains.md) — a bounded-`Integer`
  parameter/`choose` domain, whose bound can be runtime-computed (Oh Hell's
  `hand_size`), reconciled against OpenSpiel's fixed action space (retiring
  the `_MAX_CHOOSE` magic constant); Ninety-Nine's stress-sweep nullary
  explosion and Oh Hell's `_MAX_CHOOSE` are its data points.

## Tier 2 — High impact, blocked on a data point

These questions need one more game in the corpus before committing to a
design. The data point is named in each file.

- [structural-infoset-proofs](structural-infoset-proofs.md) — replace the
  empirical simulate-and-perturb readiness harness with a *structural* proof of
  the derived info-set properties (construct indistinguishable worlds from the
  projection lattice + observation-emission sites, not swap-and-replay); two
  distinct harness misfits already exist (Bridge/Tarot driver-exploration, Go
  Fish world-generator), so the strategy is whack-a-mole; blocked on the first
  compound hidden-function probe that defeats any simple swap axis.
- [turn-loop-form](turn-loop-form.md) — a `turns` form beneath the three
  round forms (rotation, participant filtering, termination owned by the
  kernel); seven stress-sweep games hand-rolled the same scaffolding;
  blocked on a corpus-quality anchor game (President or Gin Rummy).
- [meld-groups](meld-groups.md) — a card-group construct with joint
  validity predicates; Pinochle + Gin + Canasta are the three data points;
  blocked on a rummy-family game entering the corpus properly.

## Tier 3 — Medium impact, narrow scope

These don't block other work but resolving them improves specific corners
of the language.

- [move-level-visibility](move-level-visibility.md) — override-replace vs
  override-merge.
- [rule-scope-beyond-trick-play](rule-scope-beyond-trick-play.md) — rules apply
  only at the trick form's card-decision site; `actions where` demands and
  rules constraining non-trick move types are validated but unenforced. Where
  (if anywhere) should declarative rules bind outside a trick round? Data
  point: the first game needing a reusable non-trick constraint.
- [zone-access-syntax](zone-access-syntax.md) — `zone[chain]` vs
  `chain.zone` for complex receivers.
- [optional-window-moves](optional-window-moves.md) — `may submit X`
  for non-mandatory moves during a window (Tichu calls).
- [round-config-factoring](round-config-factoring.md) — folding a repeated,
  parameterized `round` block (a list/`for each in [...]` loop over Stud's five
  betting streets) into one body; the within-round predicate duplication is
  already resolved with named functions, so this is the residual block-level
  repetition, and the second-instance data point is Hold'em.
- [single-actor-binding](single-actor-binding.md) — an `as <player> { ... }`
  block for one-player decisions, replacing the `for each player p: if p ==
  X` loop-and-skip idiom that six games now use.

## Tier 4 — Low impact, defer until forced

These have known scope and aren't blocking anything. Adopt when convenient
or when a game forces the issue.

- [memory-event-syntax](memory-event-syntax.md) — declaration syntax for
  custom memory-affecting events.
- [knowledge-events](knowledge-events.md) — observer-dependent phase
  outcomes.
- [special-cards-declaration](special-cards-declaration.md) — `specials:`
  block and contextual-rank cards (Tichu's Mahjong, Dog, Phoenix, Dragon).
- [out-of-turn-moves](out-of-turn-moves.md) — `out_of_turn_legal`
  vs permitting-rules vs phase-level lists (Tichu bombs).
- [phase-legal-moves](phase-legal-moves.md) — what `legal_moves:` is for
  (derived from the body vs explicit) and whether to statically check it
  against what the body offers, now that `offering` also declares a vocabulary.

## Tier 5 — Cosmetic, no design risk

Naming and aesthetic choices. Pick when convenient.

- [move-type-naming](move-type-naming.md) — `move_type` vs `action_type`
  vs `operation` vs `move`.
- [hearts-sub-phase-shape](hearts-sub-phase-shape.md) — `first_trick` as
  sibling vs nested sub-phase of `play`.
