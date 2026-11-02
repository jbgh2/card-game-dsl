# ADR-0016: An operator ruling is recorded as an Architecture Decision Record in `docs/adr/`

- **Status:** Accepted
- **Date:** 2026-11-01
- **Ruled by:** the operator, on the harness desk's proposal
- **Record:** the PR that lands `docs/adr/` (its number is in the merge commit)
- **Governs:** maintaining.md, "A ruling's record is its ADR"; CLAUDE.md, "Prose states what is; the journey lives in dated artifacts"

## Context

CLAUDE.md names the dated artifacts the journey lives in — the commit, the
PR body, the issue, the report — and a ruling had no member on that list.
So rulings landed in three places by accident: an issue's `## Ruling`
section, the operator's words quoted in a PR body, and one machine's
session memory, which became the index because nothing else indexed them.
ADR-0008 had moved state out of memory; rulings were the load-bearing
class that remained. A reader of `decisions.md` could not learn why a
sentence reads as it does or which alternative lost. The operator asked
for more formal ADRs to remove the load-bearing nature of the memory
system.

## Decision

An ADR is the dated artifact for an operator ruling and nothing else: one
numbered, immutable file per ruling under `docs/adr/`, carrying the date,
the status, the ruling in the operator's words where given, the
alternatives that lost and the measurement that killed each, the
consequences, and the issue and PR that hold the act and the counsel. The
issue's `## Ruling` section remains the act; the record is the tree's
index of it. The spec states the rule in present tense and cites the
record in one sentence where re-litigation would otherwise follow; a change
inside a ruling cites the record, a change against it lands a superseding
record. Memory afterwards holds how the operator wants the desk to work,
and pointers.

## Alternatives

- **Rulings as wall sentences in `decisions.md`.** Lost: the spec is
  present-tense and cannot hold the dated record — context, options
  rejected, consequences — without breaking "spec, not history".
- **Rulings on their issues alone.** Lost: an issue is the act, not an
  index; a reader of the law cannot find it from the sentence it rules.
- **Memory as the index.** Lost: one machine, and it decays (ADR-0008).
- **A status workflow and a many-section template.** Not built: two
  statuses and four sections are the whole shape.

## Consequences

`tests/test_adr_records.py` pins the shape, the numbering and every
`ADR-NNNN` mention to a record that exists; `docs/adr/**` is Merge Lane B;
the fifteen rulings before this one are backfilled from their artifacts on
this date, and the memories that carried them retire or slim to the desk's
manner toward the operator. A ruling found later without a record is
recorded at the next number with its own date.
