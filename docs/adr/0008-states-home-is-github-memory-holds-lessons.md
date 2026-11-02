# ADR-0008: State's home is GitHub; memory holds lessons, and a thread retires its own STATE before it archives

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator
- **Record:** PR #959 (the goodbye skill's close-out rule); PR #960 (working rules folded from memory into doctrine); issue #958 (the leftovers that fit no issue)
- **Governs:** the `goodbye` skill (`.claude/skills/goodbye/SKILL.md`); CLAUDE.md, "Prose states what is; the journey lives in dated artifacts"

## Context

Session memory on one machine carried project state — what was in flight,
what was ruled, what was left over — and working rules agents followed,
which no other machine, cloud session or reviewer reads. A present-tense
memory line is a query result with its query discarded: it decays silently
and misleads the next thread. Backfilled on 2026-11-01 from the PRs and the
session record.

## Decision

State is preserved in GitHub where possible — on its issue or PR as a
comment, or on a new issue when nothing holds it — and a thread cleans up
its state before it archives: it retires or refreshes every STATE memory
it wrote, once that state is on GitHub. A STATE memory holds only what no
public artifact can — spend, a plan to contact someone, the operator's own
machine. A working rule the doctrine can hold folds into the doctrine every
thread loads, in the section a thread reads when the rule applies.

## Alternatives

- **Memory as the project's state store, kept current by each thread.**
  Lost: it reaches one machine, and it decays.
- **A handoff document.** Already lost (ADR-0006).

## Consequences

The goodbye skill's close-out; ten memories retired on PR #960's merge and
their lessons placed in CLAUDE.md, decisions.md, harness.md, maintaining.md
and the hoyle skill. ADR-0016 moves the last load-bearing class — rulings —
out of memory as well.
