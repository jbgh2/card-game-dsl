# ADR-0005: Three open milestones — two the review's, and the third the Operator's Milestone

- **Status:** Accepted
- **Date:** 2026-10-18
- **Ruled by:** the operator, on direction review verdict 14's measurement
- **Record:** PR #914 (verdict 14, the measurement and its uniform-three recommendation); PR #916 (merged 2026-10-18), the doctrine
- **Governs:** harness.md, "The Ready Front"

## Context

Verdict 14 measured the three-milestone experiment: the milestone count
does not bound the fleet's output, but it decides whether the loose
Priority Tier band is ever reached — the Ready Front lists ACTIVE rows
first, and with two or three milestones each holding an unleased part
there is always one on top, so #145, the oldest P1, went untaken across
twenty-five PRs while never being blocked. The verdict recommended a
uniform three milestones from the head of #143. Backfilled on 2026-11-01
from the PR and the session record.

## Decision

The operator: "Let's keep three milestones but let's keep the third for
things like this which are either falling through the cracks, important
but not urgent or just an itch I want to scratch. It'll help us understand
if the main priorities need to change without having the main doctrine
thrash as I change my mind or get a bee in my bonnet."

Two milestones are the review's, opened from the head of #143. The third is
the Operator's Milestone: opened and closed by the operator alone, the
shape of any milestone, named `Operator's Milestone` in its description's
first line, taken by the fleet like any ACTIVE row in due-date order,
outside the one-Upkeep bound and outside #143. The review reads it every
verdict — what it held, how it closed, whether that says the queue is
ordered wrong — and promotes a class that lands there twice into its own
slots.

## Alternatives

- **A uniform three from #143** (the verdict's draft amendment). Lost: the
  operator's own picks would then move the main line's doctrine and #143
  each time the operator changed their mind.
- **Stay at two.** Lost: the loose band stays unreachable while any ACTIVE
  row has an unleased part.

## Consequences

The review never fills the third slot. The slot is an instrument: a class
landing in it twice is a finding about the queue's order. Its first
occupant, milestone 17 (epic #813, the silent class), closed in four days —
verdict 15's reading, which moved the review's second slot to the Priority
Tier. ADR-0009 lets the slot hold several milestones as one unit.
