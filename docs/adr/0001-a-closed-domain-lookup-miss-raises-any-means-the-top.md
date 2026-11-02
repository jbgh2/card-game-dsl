# ADR-0001: A closed-domain lookup that misses raises; `Any` means the top and nothing else

- **Status:** Accepted
- **Date:** 2026-07-20
- **Ruled by:** the operator, on the open question's own analysis and the PR's review rounds
- **Record:** PR #79 (merged 2026-07-20), which promotes and deletes the open question `permissive-any-type.md`; the ledger in `tests/test_permissive_top.py`
- **Governs:** decisions.md, "`Any` means the top, never a failed lookup"

## Context

`TAny` was the type checker's top — compatible with every type in both
directions, every operand guard short-circuiting on it — and it was also
the fallback for a lookup that missed. A value that satisfies every
constraint exempts everything below it from every guard, so one missed
lookup switched off a whole subtree's type checking while the checker
reported success. Two review findings in one cycle had this shape. The
open question proposed a non-permissive sentinel type in the type union.
Backfilled on 2026-11-01 from the PR body and the session record.

## Decision

The two roles are separated at the producers, not in the type. There is
one `Any` and it means the top. A lookup whose domain is closed — binder
roles, native call signatures, zone content types, struct types, operator
result types, `ref_kind` dispatch — raises an `AssertionError` naming the
guard or builder that guarantees it, because resolve has already validated
the name against its registry and a miss is a divergence between two
registries: a compiler bug, not a program error. An environment lookup that
misses raises likewise, and the fix is always to thread the binder, never
to bind `Any` at the failing site. Declared type names are validated where
they are declared, so a move parameter no vocabulary names is gated too.

## Alternatives

- **A `TUnresolved` sentinel in the type union** (the open question's
  proposal). Lost: resolve runs before typecheck, so every lookup miss is
  by construction a compiler bug, and the honest answer to one is to crash
  naming it (rustc's ICE), not to flow a value through the type system. A
  sentinel in the lookup layer would also re-represent a fact resolve had
  already established — the write-time triage tell.
- **Bind `Any` at each failing site as it is found.** Lost: it is the
  defect, one site at a time.

## Consequences

A future LSP mode recovers on the resolve side — resolve runs tolerantly
and stamps unresolved nodes, and the type environment is built complete
with explicit poison entries — so the lookup-miss fallback still never
fires; the mode does not reopen this ruling. The move-parameter domain
gate moved from the offer sites to the declaration (the PR measured 83 of
188 bad spellings silently accepted when gated only from offers, 0 after).
`tests/test_permissive_top.py` pins each closed registry's raise as
unreachable for a well-formed program.
