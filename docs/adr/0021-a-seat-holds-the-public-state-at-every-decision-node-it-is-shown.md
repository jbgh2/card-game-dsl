# ADR-0021: A seat holds the public state at every decision node it is shown, and every seat's log records each node's State Delta

- **Status:** Accepted
- **Date:** 2026-11-09
- **Ruled by:** the operator, on the Architect's counsel (Hoyle stood down: no Merge Lane A surface)
- **Record:** issue #1041 (the defect, the measurement and the ruling comment); the options report `experiments/infoset_proofs/2026-11-07-issue-1041-options.md`; the PR that lands this record
- **Governs:** decisions.md, "Hidden information lives only in zones; state is public" ("**A seat holds the public state at every decision node it is shown.** Public means shown to every seat at each decision node, not announced at each write.")

## Context

A State Variable written from something some seat cannot see, shown to that
seat at a decision and overwritten before its next decision, made the seat
forget it. An assignment emitted no observation event, and the information
state rendered only the current value, so two deals the seat told apart at
its first decision rendered alike at its second. That is imperfect recall,
and decisions.md names `forget` as its only source. Two witnesses reached it:
an assignment whose value reads a concealed hand, and an `if` on a concealed
hand choosing which constant to write. On 2026-11-07 the measurement over the
37 corpus games found the following:

- 16 games assign a value that reads something some seat cannot see.
- 3 more reach such a write only through hidden control.
- No sampled corpus line forgot.
- Canasta, cribbage, french-tarot and skat publish an unrevealed pile into a
  cumulative score, which is the shape in which the gap bites.

## Decision

At every decision node, every seat's log receives the public State Variable
slots that changed since the previous decision node, each with the rendering
it had there, emitted from the route that delivers `asked`. A seat holds the
public state at every position it is shown it, and a value written and
overwritten between two decision nodes is heard by no one.

## Alternatives

- **Refuse the flow** (judge `AssignStmt.value` as a no-seat read). It would
  refuse all 16 games, Hearts among them, and in 12 of those the published
  value is derivable. The remedy it would name, a `reveal` first, cannot
  reveal a hand. It misses the implicit flow.
- **Log only the writes that read hidden content.** It is sound only under a
  static taint that must cover the value, every enclosing control position, a
  `produce` arm, a move type's effect under its offering control, a
  Primitive's state reads, and the offer and trick-round control rows. The
  measurement found each of these outside a nesting walk, and a position the
  taint missed would be a silent recall break.
- **Log every write, to every seat.** This is the literal reading of "an
  assignment is an announcement". It added about 2.0 million events against
  about 0.3 million for the State Delta, and it moved the first-decision
  information state in 26 of 37 games against none. It needs one door for
  State Variable writes first, because an indexed assignment writes its slot
  in place. It also refines the partition where a transient value is not
  otherwise derivable, which moves more than the games that forget.
- **A delta only at the seat's own decisions.** OpenSpiel's perfect-recall
  contract is per player at every state, non-acting players included, so a
  per-decider delta fails it.

## Consequences

- `observe.EVENT_PAYLOADS` gains the `was` kind and `observe.state_delta`
  is its one emitter, called by `chooser.decide` before the `asked`.
  `observe.public_state` is the one reading of the public state, and the
  information state renders it. A `was` event emitted anywhere else is
  illegal (chooser.py, Contract).
- The proofs:
  - perfect recall over Constructed Worlds holds every registered game at
    every earlier decision of the asking seat (`_check` in
    tests/openspiel_ready/test_ismcts.py), reddened by both witnesses with
    the emission removed;
  - tests/test_state_recall.py runs one cell per write door.
- The information-state strings move at every decision node after the first
  where a slot changed. The first decision node of a run delivers no delta,
  so `tests/golden/infostate_format.json` is unchanged, and the per-seed
  score goldens are byte-identical, since no rng draw and no choice moves.
- Not decided here:
  - whether a game should publish a concealed fact into state at all
    (issue #471);
  - whether the four games scoring an unrevealed pile reveal it under their
    rules (a rules read against Pagat);
  - the zone half of recall, which rests on every zone change being observed
    (epic #999).
