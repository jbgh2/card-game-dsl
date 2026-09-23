# A rule that reads concealed cards is refused — epic #312, issue #281

**Date:** 2026-09-23. **Lane:** B (`cardlang/resolve.py`,
`cardlang/stdlib/zones.py`, `cardlang/builtins/functions.py`,
`tests/openspiel_ready/harness.py`). **Counsel:** Foster, sitting
2026-09-22; the block attaches to the PR. **Operator rulings:** 2026-09-19
(the wall lands in #281, phase gate first) and 2026-09-23 (below).

## The decision, as narrowed

Under Honest Play (decisions.md, "Honest Play is assumed, so a rule reading
concealed cards is mis-modelled") a stage or rule that turns on another
seat's concealed cards is a mis-modelled rule, and its refusal names the
announcement the real rules have. The question this unit answers is how the
checker learns what an expression reads: one reader of expression reads,
built once in resolve, judged by two verdicts.

## The operator's rulings

- **2026-09-19.** The wall lands in #281; its first member is the phase gate.
- **2026-09-23, asked at pickup.** The wall reaches the whole class in this
  unit:
  - **no seat deciding** (verdict: every seat can check it) — the
    `phase … when` gate, the `phase … repeat until` condition, and a mode's
    `transition_to` trigger;
  - **a seat deciding** (verdict: the deciding seat can check it) — a
    legal-action predicate (a move type's `when:`, a rule's clauses), and a
    chosen movement's amount, source pool, `where` and destination.

  A chosen pick from a pool the chooser cannot see (Old Maid's blind draw) is
  refused until a pick-by-position spelling exists; that spelling is a Merge
  Lane A unit on its own issue, the operator's.

Foster counselled the seat-deciding verdict as a successor unit; the operator
ruled it into this one. The reader's shape, the placement, the tables and
the harness order below are Foster's counsel unchanged.

## Acceptance criteria

1. **Runs.** Every corpus game checks and plays as before.
2. **Regression-clean.** Bare `mypy`, full `pytest`, the LLM rig suite; the
   per-seed goldens swept at full width, byte-identical — no game moves.
3. **Info sets derive.** No emission changes. For a walled sentence the
   unsound partition never comes to exist; the proof harness can now fail
   for the class wherever a checker-accepted game reaches it.

**Corpus lockstep:** none expected — no phase qualifier or transition reads a
zone, and every seat-deciding hidden read but one is provably the decider's
own (measured 2026-09-22 at `ad96537c`). The exception, Bridge's
`play_source_for`, is a delegated decision whose Owner Guard is the runtime's
`check_decider_sees`; its static cell is a Shadow naming that guard. If any
corpus file is refused, the unit stops and the finding goes to the operator:
the game does not bend to the wall.

**Reachability:** R2 — the refused sentences read exactly like every other
predicate a designer writes, and nothing warns today.

## The work, in order, each step with its proving artifact

1. **The proof harness compares every blind decision** (Foster's H1).
   `ReplayChooser` records the legal pool at each recorded pick; at every
   pick whose decider is blind to both swapped cards the proof compares
   decider and pool across the two worlds, and a recorded pick that becomes
   illegal at a blind decider fails the proof instead of dropping the pair.
   Swap pairs spread across distinct opponent cards. *Artifacts:* the seeded
   witness games (a gate at the pause, in the prefix, rerouting; a rule
   `applies_when` over another hand, at the pause and in the prefix; the
   blind draw), each red in the proof at a quoted seed and cap before the
   wall exists; the corpus manifest green; the coverage record gains the
   blind-node count. Lands before the wall, because a walled sentence can no
   longer reach the proof through the checker.
2. **Two closed tables and their pins.** `PROJECTION_LEVELS` in
   `cardlang/stdlib/zones.py` (decisions.md's lattice, ordered, with the
   `reveals(level, need)` comparison), pinned against every
   `ZONE_PROJECTIONS` value; and the Builtin zone-read partition in
   `cardlang/builtins/functions.py` (reads its arguments / reads nothing /
   reads every hand implicitly), pinned total against `BUILTIN_CALL_FUNCS`.
   *Artifacts:* the two pins, each with its reddening mutation.
3. **The grid, authored red** (surface-totality audit, Step 1). Axes derived
   in code: the expression-bearing position (every AST field typed `Expr`,
   each bucketed no-seat / seat-deciding / out of domain, an unbucketed field
   failing the build); the read's need (count, existence, identity, order);
   the zone type (`LIBRARY_ZONE_TYPES` over `ZONE_PROJECTIONS`); the route (direct,
   `let`, designer function, Primitive `reads`, Builtin partition row, bare
   family); and, for seat-deciding positions, the index's relation to the
   decider (own by construction, the decider's pronoun or binder, a State
   Variable decider, a delegated decider, another seat, computed). The
   framing check runs over the whole `cardlang/` package before the expected
   column is authored. *Artifact:* the grid module, its designed-to-flip
   cells `xfail(strict=True, raises=AssertionError)`, run red.
4. **The reader and the no-seat verdict** in resolve, after
   `_classify_names`, `_check_functions`, `_validate_refs` and
   `_check_primitive_reads`, with its "Now illegal" sentence in resolve's
   Contract. *Artifacts:* the no-seat grid cells green; the gate witnesses
   become rejection tests with pinned messages.
5. **The seat-deciding verdict** over the same reader, at the positions the
   grid buckets seat-deciding. *Artifacts:* those grid cells green; the rule
   and blind-draw witnesses become rejection tests; misuse probes
   (surface-totality audit, Step 2) as rejection tests.
6. **Spec and records.** decisions.md, "Honest Play is assumed", names the
   positions the refusal reaches and the registry that lists them; the
   glossary gains any term the unit mints; `docs/open-questions/structural-infoset-proofs.md`
   and `docs/kernel-migration.md` are updated where the proof's caveats
   change; the pick-by-position spelling is filed as its own issue.

## What the proof's reach does not include

The control positions — an `if`, a round's participants, a State Variable
assignment — are outside the ruled class: they decide who is asked or what
everyone is told, and the corpus's hidden reads there are followed by the
reveal that makes them honest (Coup's challenge, Go Fish's ask). A State
Variable written from a hidden zone is an announcement to every seat, so a
gate reading it is sound.
