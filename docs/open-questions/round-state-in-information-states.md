# Where active round state sits in the information-state encoding

**Tier 4 — low impact, defer until forced.** The derived information state
renders (the observer's zone projections) + (the declared state variables,
merged across scope frames) + (the observation log). It does **not** render
the mechanic-internal round state — the `state.x` values a `round` form
maintains while it runs (`rs.mech_state`; exposed to the surrounding body
after the round as `state.x` via `last_round_state`). A player decision can
pause the game *inside* a round, so at some decision nodes there is live
round state that appears in no one's information state.

The same class extends one layer up: the pause itself is an exception
unwind, and the unwind pops the *phase-local frames* too — so at a decision
node, phase state (window flags, working bids, the turn pointer) is neither
readable from the paused world nor rendered in any information state, for
every game. The derivability argument is identical (phase state is written
by announced decisions and projected movements), and so is the exposure: a
phase variable written from hidden contents would be silently absent rather
than deliberately projected. Witnessed concretely by Coup's window flags
(`tests/openspiel_ready/test_coup.py`, the blocked-foreign-aid test, which
had to assert through the coin economy because `block_stands` is
unreachable at the pause).

[decisions.md](../decisions.md) "Hidden information lives only in zones;
state is public" commits every **declared** `state` variable to being public
and gives the modeling rule ("anything an observer must not know is contents,
not state") — but it speaks of declared variables and does not say whether
mechanic-internal round state is part of the "public state" the encoding must
carry. The omission is currently harmless because today's corpus round state
is *derivable from the observation log*: every round decision is announced or
delivered as a `chose` event, every movement is emitted through the declared
projections, and round-state initializers read public state — so two worlds
agreeing on an observer's log and projections also agree on the round state,
and rendering it would add no partition information. Nothing enforces that
derivability, and the per-visible-fact soundness matrix
(`tests/openspiel_ready/partition.py`) deliberately enumerates declared
frames only.

## The sibling axis: which round FRAME a `state.` read sees

The same construct carries a second undecided axis, on the checker's side
rather than the encoding's. A round publishes a declared, typed set of fields,
and the **name** axis is closed: the checker rejects every name outside that
set, so a form's private working memory is not reachable from the DSL
(`cardlang/stdlib/round_state.py`, ledger
`tests/test_round_state_registry.py`).

The **frame** axis is not. A reference is not statically attached to a form —
`MustFollowSuit` lives once in `stdlib/rules.cardlang` and games activate it in
context — so the checker validates a `state.` read against the UNION of every
form's published set, and cannot prove that the round actually running
publishes the field being read. `state.shed_first` (a climb field) inside a
trick phase type-checks.

The runtime is guarded: a read with no live or just-completed frame now fails
loudly rather than returning a stale one from a different form (the
`AuctionForm` `last_round_state` clear, pinned by
`test_auction_does_not_leave_a_stale_trick_frame`). So this is a static
imprecision with a loud runtime Shadow Guard, not a silent miss — but the
diagnostic a designer wants ("this phase runs a trick, and `shed_first` is a
climb field") is not available, and giving it means attaching references to
forms, which is the same static-context question the encoding axis above turns
on. Settle the two together.

## Why it could bite

Both failure directions become live the moment a round body writes `state.x`
from something an observer is *not* entitled to — e.g. a value computed over
a projection-hidden zone's contents:

- **Render `mech_state`** and that value leaks to every observer (state
  rendering is observer-independent).
- **Keep omitting it** and, if the value is something observers *are*
  entitled to (a public running total that never passes through an announced
  decision), the information state over-hides — the silent defect class the
  partition checks exist to catch, and one no swap probe reaches.

## The options

- **Bless the omission and make derivability the rule.** Spec: round state
  must be a pure function of (announced decisions, projected movements,
  public state at round entry); the encoding rightly omits it as redundant.
  Cheap; matches today's runtime. Wants at least a documented obligation on
  new round axes (each new accumulator/vocabulary axis must announce enough
  for observers to reconstruct what it accumulates).
- **Render `mech_state` in the information state.** Makes "state is public"
  uniform across declared and mechanic state. Requires the modeling rule to
  bind round bodies too (never compute round state from hidden contents), and
  changes every information-state string (golden churn) for no partition gain
  on the current corpus.
- **Project round state per observer.** Rejected on arrival: it reintroduces
  observer-dependent scalar state, which the zones-only boundary exists to
  forbid.

**Current lean: bless the omission with the derivability obligation.** Settle
when forced: the first round axis or game whose round state is not
log-derivable (a hidden-content accumulator, a concealed working value), or
the structural-proof work in
[structural-infoset-proofs](structural-infoset-proofs.md), whose
emission-site obligations must classify round-state writes anyway.

Related: [decisions.md](../decisions.md) "Hidden information lives only in
zones; state is public" (the boundary this sits on);
[structural-infoset-proofs](structural-infoset-proofs.md) (the certification
checklist that would have to cover round state);
[knowledge-events](knowledge-events.md) (the adjacent
observer-dependent-outcome territory).
