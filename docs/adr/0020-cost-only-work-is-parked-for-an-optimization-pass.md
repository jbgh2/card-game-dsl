# ADR-0020: Cost-only work is parked for an Optimization Pass, under one `optimization` label

- **Status:** Accepted
- **Date:** 2026-11-08
- **Ruled by:** the operator, on the board ladder close-out thread's measurement of issue #965
- **Record:** issue #965 (the measurement and the detach from milestone 21); issue #953 (the epic it left); the PR that lands this record
- **Governs:** CLAUDE.md, "The tracker" ("three **modifiers**, `blocked:needs-witness`, `needs-triage` and `optimization`"); harness.md, "The Ready Front" ("it carries `optimization` — parked for the Optimization Pass")

## Context

Issue #965, the per-enumeration memo of pure function calls, was the last
open part of milestone 21. Its witness clause asks for a rung whose harness
time is dominated by per-candidate function evaluation. The morris
measurement on #965 (2026-11-01) meets the clause: 96% of one line's
user-function calls repeat a key the enumeration already answered. A scratch
memo measured on 2026-11-08 saved 50% of a morris differential line, 7% of
four draughts playouts, and 26% of the morris and draughts test modules'
wall time, with every outcome identical. Across the whole suite that is a
few percent. Nothing plays wrong without the memo, so the work is cost
alone. Building it then would have been machinery done to close a container.
CLAUDE.md had rejected area labels: "semantic issue search covers retrieval,
so wait for the problem before adding a label". A batched pass is that
problem, because it needs a complete set and a search returns a sample.

## Decision

#965 is detached from milestone 21 and parked. Work whose fix changes only
cost (harness or runtime time and memory) and no answer a designer or a
proof sees carries the modifier `optimization`. An `optimization` issue is
off the Ready Front until the operator opens the Optimization Pass as a
milestone. Then its members are worked together, as one unit, against
their recorded measurements.

## Alternatives

- **Build #965 now.** Lost: R3 harness time with no wrong answer. The
  measured saving is a few percent of the suite.
- **Detach #965 and rely on search to find it later.** Lost: a pass
  needs the whole class, and a semantic search is not a superset.
- **Keep #965 under `blocked:needs-witness`.** Lost: the witness the
  clause names is already recorded, so the label would claim a blocker
  that no longer holds.
- **An area-label family (performance, runtime, testing).** Not taken:
  the rejection of area labels stands. This is one label for one kind
  of deferral, and the Ready Front reads it.

## Consequences

- The Ready Front's sweep, `tools/ready-front.sh`, gains the parked
  bucket after the witness-gated one.
- Filing an `optimization` issue requires its pricing measurement, dated
  and with its command.
- The pass's membership is the derived query `--label optimization`.
- Deliberately not decided: when the pass opens, and in what order its
  members are worked. The direction review weighs that like any other
  unit.
