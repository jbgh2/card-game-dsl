# ADR-0004: The language is minimal and complete — no synonyms, and no family with a missing member

- **Status:** Accepted
- **Date:** 2026-09-07
- **Ruled by:** the operator, against the Architect's against-case and the scoring-surface review; re-ruled 2026-10-10 on the grammar pass's first step
- **Record:** PR #630 (the subset binder, merged 2026-09-07); issue #835 and PR #838 (merged 2026-10-10), epic #818's first step
- **Governs:** decisions.md, "Surface totality" (the "Minimal and complete" paragraph)

## Context

PR #630 shipped the six folds over a zone's subsets, three of them with no
corpus writer — `all subsets`, `sum` and `lowest` over subsets. The case to
cut them was put twice under corpus-first: the Architect's against-case,
then the dead-surface finding of the scoring-surface review. A month
later, epic #818's first step (issue #835) listed the grammar's writer-less
surface for deletion: a random selection, a visibility override, three
verbs for `move`, two rule deltas, six query arms and a rounded-down
division. Backfilled on 2026-11-01 from the session record and the PRs.

## Decision

2026-09-07, keep the three folds: "the case to remove them is a narrow
reading of the doctrine. They are generally useful and a language with
`highest` and not `lowest` has an obvious hole."

2026-10-10, the rule: the language is **minimal but complete**. It has no
synonyms — a second word the parser reads as the same node is dead surface
the moment it lands, so `burn`, `muck` and `transfer` for `move` go — and
no logical holes: `any` without `all`, `rounded up` without `rounded
down`, `any subset` without `all subsets` are holes, not savings, and a
member of a closed family ships whole with its family, with or without a
corpus writer. A consumerless member carries a sunset the direction review
applies after a stated number of further corpus games. "If we need to
update the doctrine, then we can."

## Alternatives

- **Cut every member no corpus file writes** (strict corpus-first). Lost:
  corpus-first gates which constructs exist, not how completely one works;
  a half-register is an asymmetry a designer meets and the language cannot
  explain. Cutting `lowest` would also have cost a rejection guard on a
  terminal it shares with `highest` — more machinery than the member.

## Consequences

A construct joining a register builds the whole register, and its ledger
says in plain words which members are born consumerless, so the review
decides about a surface whose justification it can read. The dead-surface
report (`python -m tools.dead_surface`) classes every writer-less row as a
sibling kept whole, a placeholder for a pinned message, a reject arm or
dead, and the dead class is pinned empty. The sunset is the review's
instrument; a pre-emptive cut is not offered.
