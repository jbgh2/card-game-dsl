# ADR-0026: Observation keeps its spelling, builds only the projection levels a game declares, and an Observation Log is one seat's events

- **Status:** Accepted
- **Date:** 2026-11-15
- **Ruled by:** the operator, on the Architect's counsel
- **Record:** issue #999 (the counsel, and the ruling comment its `## Ruling` section links); the PRs closing its parts, issues #1001 through #1004
- **Governs:** decisions.md, "A seat's knowledge, rendered"; decisions.md, "Projections: what visibility controls"; the glossary's Observation Log and Observation Emitter entries

## Context

Epic #999 makes what a seat observes one closed type delivered through one
door. Three of its choices were the operator's before the first part that
moves emission. When `Event` becomes a closed union, does the string OpenSpiel
keys on change? What happens to the three projection levels the spec declares
and no zone type uses? And which sense keeps the name Observation Log, which
its glossary entry gave to the rendered string while every other use in the
tree, the heading designers read in `cardlang play` among them, gave it to one
seat's sequence of events?

The measurements in hand when the operator ruled:

- The rendered string is pinned byte for byte at the first decision of all 37
  corpus games, and along the whole line for 6 of them.
- No `was` event occurs at a first decision.
- 11 of the 13 games that name `reveal` are outside the six whose whole line
  is pinned.
- `ZONE_PROJECTIONS` declares three of the six levels.
- The string is read outside the merge gate: by the LLM evaluation rig's
  cache-shaped prompts, by the tagged studies' rendered prompts, and in the
  authoring guide's worked examples.

## Decision

The operator took the counsel as written: "Yes, as counselled".

- **(a) The spelling holds.** Each event kind spells itself through one
  `spelled()` returning today's tuple, so the information-state string is
  byte-identical. Before any event type is written, a whole-line spelling
  capture of every corpus game is taken on today's tree and planted red under
  one respelled kind.
- **(b) The code builds three levels; the spec keeps six.** The code's
  projection enum is the three levels the engine builds, held by the type
  checker, and a zone type declaring any other is refused when the registry
  loads. The spec keeps its six-level lattice as the model, and records
  `identity_set`, `count_by_type` and `existence_only` as unbuilt until a game
  needs one (issue #1138).
- **(c) Observation Log names the event sequence.** Observation Log is one
  seat's sequence of Observation Events. The rendered string takes its own
  interop entry. The runtime's per-table aggregate is the table's Observation
  Logs and has no name of its own. Observation Emitter is minted for the
  kernel's one door from a deposit, decision or reveal to the observer.

## Alternatives

- **(a) Regenerate the goldens with the dataclass's own spelling.** Lost: the
  information sets would not move, but the string would. Its readers outside
  the gate would break, and comparability with the tagged studies would go.
  It would still need the same capture to prove the change was only a
  respelling.
- **(b) Build all three levels.** Lost: no corpus game declares one, so each
  would be code exercised only by synthetic probes.
- **(b) Cut the three from the spec too.** Lost: it edits settled spec text,
  and it removes the model the spec's resource note and the message-passing
  seat sketch reason with.
- **(c) Name the aggregate Seat Log.** Lost: it leaves the glossary entry
  contradicting its uses, gives the event sequence two names, and names a
  per-table aggregate after one of its members.

## Consequences

- **Part 1 (#1001)** mints Observation Emitter. Its first commit is the
  whole-line capture, planted red, since Part 1 moves the emission of every
  movement and needs the same oracle Part 2 does.
- **Part 2 (#1004)**:
  - it holds the whole-line capture byte-identical;
  - its kinds include `was`;
  - its consumers include the six-game stream digest in
    `tests/test_trick_order_migration.py`;
  - newly illegal after it: an event kind with no spelling, and a consumer
    spelling an event by `repr`.
- **Part 3 (#1002)** splits the Observation Log entry and re-reads every code
  site that means the string. Newly illegal after it: "Observation Log" naming
  the rendered string.
- **Part 4 (#1003)**:
  - shrinks the enum and ends `view_of` in an exhaustive match;
  - moves the read-visibility floor from `existence_only` to `count_only`,
    which changes no answer, since no zone declares `existence_only`;
  - makes the checker's projection wording follow the enum;
  - re-bases the pins on both;
  - adds the spec paragraph marking three levels unbuilt.
- From then on, a projection level arrives with its witness game and its
  probe, never alone (issue #1138).
- Not decided here: the Zone Address rekeying of an event's label (issue
  #666), and Observation's edges in the context registry (issue #991).
