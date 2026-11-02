# ADR-0009: The Operator's Milestone slot may hold an Operator's Swarm — several milestones one controller drives, counted as one unit

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator, on the harness desk's three options
- **Record:** PR #957 (merged 2026-10-25); the options on the desk's thread, summarized in the PR body
- **Governs:** harness.md, "The Ready Front"

## Context

The operator wanted to test one controller thread driving several
milestones at once through the agents it spawns, with the board ladder as
the work. Under ADR-0005 the cap is three open milestones, so a controller
holding three rung milestones is five open milestones, and a single Boards
milestone cannot hold the rungs because a milestone holds one epic. The
desk put three options: widen the cap for everyone; make the ladder one
milestone with the rungs as its parts; or let the operator's slot hold
several milestones as one unit. Backfilled on 2026-11-01 from the PR and
the session record.

## Decision

The operator: "Option C, I agree. Let's add the limited change and then if
it works we can look into rolling it out more."

The slot may hold an Operator's Swarm: several milestones opened together
for one controller thread, each in the shape of any milestone and named
`Operator's Swarm` in its description's first line. The controller Leases
every swarm epic in the act of opening, so the Ready Front offers none of
them to the fleet; the swarm is the operator's one unit for the cap, which
now counts units in flight rather than open milestones; a swarm epic that
waits on another's work is blocked-by it. The review reads a swarm as it
reads the Operator's Milestone, epic by epic, and the controller records on
each epic it closes how long the unit's PRs waited on the runner — the
measurement that decides whether the shape spreads beyond the operator's
slot. A controller keeps its own thread name.

## Alternatives

- **Widen the cap for everyone.** Lost: the cap exists to keep the loose
  Priority Tier band reachable, and the measurement that would justify
  widening it did not exist yet.
- **One milestone with the rungs as parts.** Lost: a rung is an epic with
  parts and a finish line of its own, which a part cannot carry.

## Consequences

The first swarm is milestones 21 to 24 — issue #953's units and the hex,
nine men's morris and english draughts rungs — opened 2026-10-25 while
milestone 20 was the operator's open milestone, a dated departure from the
cap recorded on #961 and #953 for verdict 16 to read. Neither the cap nor
the Dispatcher's charter widens on this ruling; the gate-queue measurement
lives on the closed epics.
