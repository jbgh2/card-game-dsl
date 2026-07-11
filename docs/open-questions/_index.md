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

None commit-ready right now — the last Tier 1 question (the integer `choose`
domain, half of move-parameter-domains) is settled in
[decisions.md](../decisions.md) "Declared parameter domains". Its residual (the
signed bounded-`Integer` *parameter* domain) now waits on a corpus game, so it
sits in Tier 2.

## Tier 2 — High impact, blocked on a data point

These questions need one more game in the corpus before committing to a
design. The data point is named in each file.

- [move-parameter-domains](move-parameter-domains.md) — a bounded-`Integer`
  *move-parameter* domain (a single move type carrying a small **signed**
  integer, e.g. Ninety-Nine's `play_card(delta : Integer)`), so authors need
  not hand-compile one nullary move type per value. The `choose` half — a
  bounded integer bid with a declared static ceiling — is settled
  ([decisions.md](../decisions.md) "Declared parameter domains"); the signed
  parameter case fits neither that id scheme nor any corpus game yet, so it
  waits on a game to force it.
- [structural-infoset-proofs](structural-infoset-proofs.md) — replace the
  empirical simulate-and-perturb readiness harness with a *structural* proof of
  the derived info-set properties (construct indistinguishable worlds from the
  projection lattice + observation-emission sites, not swap-and-replay); two
  distinct harness misfits already exist (Bridge/Tarot driver-exploration, Go
  Fish world-generator), so the strategy is whack-a-mole. The file also carries
  the certification checklist any resolution must satisfy — both failure
  directions (leak and over-hiding), recall, seed/rng non-observability,
  legal-action agreement, adapter agreement — with today's coverage per item.
  The actionable checks are built as per-game proofs over the empirical
  harness; only the constructive world generator is blocked, on the first
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
- [round-config-factoring](round-config-factoring.md) — folding a repeated,
  parameterized `round` block (a list/`for each in [...]` loop over Stud's five
  betting streets) into one body; the within-round predicate duplication is
  already resolved with named functions, so this is the residual block-level
  repetition, and the second-instance data point is Hold'em.
- [single-actor-binding](single-actor-binding.md) — an `as <player> { ... }`
  block for one-player decisions, replacing the `for each player p: if p ==
  X` loop-and-skip idiom that six games now use.
- [unbounded-lines-and-max-length](unbounded-lines-and-max-length.md) —
  two games now have legally unbounded lines (Coup's exchange-forever
  table; Tichu's always-calling table, which drifts away from 1000
  forever), so the `max_length` backstop can fire on a legal line and
  raise instead of ending the game; raise-as-bug vs graceful terminal vs
  per-game opt-in is undecided.

## Tier 4 — Low impact, defer until forced

These have known scope and aren't blocking anything. Adopt when convenient
or when a game forces the issue.

- [memory-event-syntax](memory-event-syntax.md) — declaration syntax for
  custom memory-affecting events.
- [knowledge-events](knowledge-events.md) — observer-dependent phase
  outcomes.
- [round-state-in-information-states](round-state-in-information-states.md) —
  active `round` state (`state.x` mid-round) appears in no information state;
  harmless while round state stays derivable from the observation log, but
  nothing enforces that. Data point: the first round state written from
  hidden contents.
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
