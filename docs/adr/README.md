# Architecture Decision Records

One dated record per operator ruling. The spec states the rule, in present
tense, where the rule belongs (`decisions.md`, `harness.md`, `CLAUDE.md`,
a skill); the record states what was decided, what lost, the measurement
that decided it, and where the act and the counsel live. The record is the
dated artifact a ruling gets (CLAUDE.md, "Prose states what is; the journey
lives in dated artifacts"), the one place in the tree besides a
direction-review verdict and a completeness ledger where chronology is
legal — so a reader of the law can learn why a sentence reads as it does
and which alternative lost without opening the tracker or one machine's
session memory.

## What is recorded

An **operator ruling**: a decision the operator made between stated
options — on an issue's `## Ruling` section, on a design that creates
grammar (every Merge Lane A ruling has a record), on a doctrine change the
operator ordered. The issue's `## Ruling` section remains the **act**; the
record is the tree's **index** of it. The two say the same thing in two
registers and neither replaces the other.

Not a record: a plan (it lives on its issue — issue #908); a
direction-review verdict (its own dated file under
`docs/superpowers/direction-reviews/`); an engineering lesson (doctrine, or
the thread's memory); project state (the tracker). An agent's own design
choice inside a ruled design is not a ruling and gets no record.

## The shape

File name: `NNNN-<slug>.md`, four digits, numbered contiguously from `0001`
in the order the records are written (within one backfill, in the order
the rulings were made). The title is the conclusion, written so a reader
who sees only the index knows what was decided. The header is five lines
and the body four sections, in this order:

```text
# ADR-NNNN: <the decision, as a sentence>

- **Status:** Accepted | Superseded by ADR-NNNN
- **Date:** YYYY-MM-DD (the day of the ruling)
- **Ruled by:** the operator, and on whose counsel
- **Record:** the issue holding the act and the counsel; the PR(s) that land it
- **Governs:** the spec section(s) stating the rule, quoted so the citation is checked

## Context       — what forced the decision, and the measurement in hand
## Decision      — the ruling, in the operator's words where they were given
## Alternatives  — each option that lost, and the measurement or reason that killed it
## Consequences  — what becomes required or illegal, the units it spawned, what is deliberately not decided
```

A record is short. The counsel that argued the options stays on the issue;
the record names where it is.

## The rules

- **A record is written when the ruling lands** — in the PR that lands the
  doctrine or the implementation, or in the harness desk's PR when the
  ruling has no code. Backfilled records say so in their Context.
- **A record is never edited after it lands**, except its Status line. A
  record found wrong is superseded by a new one that says why; the old
  record's Status names its successor.
- **The spec cites the record, the record never carries the rule.** Where
  omitting the losing alternative would invite re-litigation
  (maintaining.md, "When history earns its place"), the spec's section
  carries one sentence naming the record (`ADR-NNNN`). A change inside
  what a ruling decided cites that record; a change that reverses or
  narrows it lands a superseding record (maintaining.md, "A ruling's record
  is its ADR").
- **Merge Lane B.** `docs/adr/**` merges by the operator's hand: the
  record says what the operator decided, and the operator reads it before
  it stands.

`tests/test_adr_records.py` holds the shape, the numbering, and every
`ADR-NNNN` written anywhere in the repo to a record that exists. Whether a
record states its ruling truly is the operator's read at the merge.
