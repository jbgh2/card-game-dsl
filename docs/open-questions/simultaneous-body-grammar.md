# Simultaneous body grammar

**Tier 2 — high impact, blocked on a data point.**

The `simultaneously:` block (see [decisions.md](../decisions.md),
"Simultaneous moves and atomic effect") currently permits a restricted
body: moves ([library.md](../library.md) "Move types"), memory
operations ([library.md](../library.md) "Memory operations"), and
`choose` steps. The full grammar of permitted body statements is open.

Specifically: should the body admit state writes (`:=`, `+=`),
control flow (`if`, `for each`), or `let` bindings? Hearts'
passing and the sketched Catan trade don't need any of these.
But a future simultaneous step with intermediate computation
might — for example, a simultaneous step where each participant
contributes an amount derived from a per-participant condition.

The question has real compilation implications:

- A move-only body needs no new mutation-mode infrastructure
  ([decisions.md](../decisions.md), "Mutation semantics" already has
  the batched-write mode used by `apply_components:`).
- An open body — one that includes state writes or control flow
  inside the block — would need a third mutation mode beyond the
  two defined in "Mutation semantics": sequential and batched. The
  semantics of "batched-with-control-flow" isn't obvious (which
  branch's effects participate? does a write inside a branch
  participate in the batch?).
- OpenSpiel event emission stays clean under move-only bodies
  (one coalesced event per observer per block). An open body
  with branching could emit multiple events conditionally,
  raising information-state-tensor questions.

**Blocker:** A corpus game whose natural rulebook reading
includes substructure inside a simultaneous step beyond
move-emission. Until such a game exists, broader body grammar
would be speculation; committing to it now risks an
infrastructure investment with no validating use case.
