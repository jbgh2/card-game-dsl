---
name: cardlang-planning
description: "MANDATORY planning gate for this repo — invoke BEFORE exploring, brainstorming a design, or entering plan mode for ANY new feature, construct, guard, registry, game, or machinery change. Orders the planning motions: derive the issue's class and open its recipe (bug, feature, game, language, machinery, other), find the decision's owner, classify the change, name the existing definition that already covers it (reuse first), state the acceptance criteria, and (for audit-triggering work) run the surface-totality-audit's Step 1 inside planning so the grid exists red before implementation. Every plan step names the artifact that proves it; the third instance of a class is filed against its Destination, not fixed at its site."
---

# Cardlang planning

Plans in this repo fail in a specific way: not by omitting steps, but by
inheriting the implementation's frame before any gate can see it. The
permissive-top branch scoped a five-position type-name axis to the two
positions its plan happened to guard — and every downstream gate then
audited the narrowed frame faithfully. The planning stage is where the
frame is set, so it is where the frame must be checked. This skill orders
the motions; the content lives with its owners (CLAUDE.md, decisions.md,
the audit and review skills) — this skill routes, it does not restate.

## Gate 0 — Derive the issue's class, open its recipe

Every item is one of six classes, and the class is DERIVED from facts the
thread already holds, never chosen: a chosen class is the hole the Gate 2
tie-breaker exists to close, moved to the top of the process. The facts,
in the order they decide:

1. `tools/lane-of.sh` on the files the issue names or the fix will touch.
   Any Merge Lane A file -> **language**, and a fleet thread stops here
   (docs/harness.md, "The Ready Front": a Lane A part is the operator's).
2. The issue's kind label and body. `bug`, or any issue with a witness
   sentence that misbehaves (a probe, a playout, a seed) -> **bug**. A
   defect is a bug whatever label it was filed under.
3. The files are the game's: `docs/games/`, `docs/libraries/`, and the
   pins and goldens the `cardlang-new-game` skill has the game join (its
   proof module under `tests/openspiel_ready/`, its rules differential,
   its per-seed goldens, the hand-authored tables keyed by its name) ->
   **game**. A game that also edits `cardlang/` has found a gap, and the
   gap is filed and classed on its own.
4. The fix touches `cardlang/`, `tools/` or `tests/` with no new
   designer-facing capability -> **machinery**.
5. A new designer-facing capability with no grammar change -> **feature**.
6. Nothing above -> **other**, and the plan header says so and why. Other
   is where circling hides, so it is loud: the direction review lists the
   window's `other` PRs, and three of one shape is a recipe missing.

The class is stated in the plan's header with the facts it came from
(`Class: bug — lane C, witness: seed 17 of hearts`) and repeated as one
line in the PR body (`cardlang-pr-description`); the review's Phase 0
derives the class again from the diff and reports a disagreement first.
One spine for every class — Lease, this skill's gates, build, audit where
triggered, review, PR, close — and the class changes only the recipe the
plan must follow and the artifacts it must name:

- **bug**: the witness FIRST, as a test that fails on main (a seed, a
  probe through `check_dsl`, a differential line); then the class sweep
  (the other members of the same closed domain, decisions.md
  "Closed-domain completeness") before the instance is touched; then the
  grid or the class ledger with its `why missed:` row
  (`surface-totality-audit`, Step 2b); the fix is the LAST step. Gate 3.5's
  third-instance rule applies: the third site of one class is filed, not
  fixed.
- **feature**: Gate 2.5 reuse-first before any definition; Hoyle's
  counsel if the probe fails on grammar (which makes it **language**);
  the grid authored red before implementation (Gate 4); the Destination
  it advances named in the plan header, or `Upkeep`.
- **game**: the `cardlang-new-game` skill end to end for a game added or
  corrected; it returns here for every gap it files, each gap re-deriving
  its own class. A library-only change is `game` by its files and stays
  in these gates, as that skill's head says: Gate 2.5 with the library as
  the reuse, and the full-width goldens sweep of its consumer games.
- **language**: the operator's with Hoyle (`.claude/skills/hoyle`): the
  library-first proof, the counsel block, the grid; a fleet thread files
  and parks.
- **machinery**: the Architect's counsel (`.claude/skills/architect`)
  where the change is engine-structural; a completeness ledger for any
  closed domain it touches; the Destination it advances, or `Upkeep`.
  Harness and tooling changes are machinery too, and a harness change
  is tested on its witness before it lands (the doctrine-tested-on-the-
  witness method, docs/harness.md).
- **other**: Gates 1 through 5 plain, nothing skipped, and the header's
  reason for `other` is the first line of the PR body.

## Gate 1 — Find the decision's owner before forming an opinion

Every design question in this repo has a home. Before proposing anything,
locate it:

- settled -> decisions.md (search the section titles first)
- named -> docs/glossary.md (every concept's one spelling; the preamble's
  usage rules bind new names — a plan that needs a word the glossary
  lacks mints the entry as a plan step)
- open -> docs/open-questions/_index.md, then the named file (cite by slug)
- sequenced -> the GitHub tracker; issue #143 orders the cross-cutting work
- sketched -> docs/design-notes/ (proposals, not settled spec)
- witnessed -> docs/games/ (which corpus games exercise the area today)
- surface -> Hoyle, the Language Owner (`.claude/skills/hoyle`): any
  Merge Lane A change, or a design that would create one, consults at
  planning time and attaches the counsel block to the change before the
  operator rules (docs/harness.md, "The Language Owner")
- engine-structural -> the Architect (`.claude/skills/architect`): pass
  architecture and Contract blocks, the type system, IR and runtime
  shape, diagnostics machinery, testing strategy, the observability
  model — consulted at planning time, counsel attached to the change
  (docs/harness.md, "The Architect"); a change with both faces takes
  both counsels

A plan that contradicts an owner is wrong before it starts; a plan that
re-derives one is losing information — the planning-stage form of
decisions.md write-time triage. If the work touches a pipeline pass, read
that pass's `Contract` block before planning around it.

## Gate 2 — Classify the change

Classify exactly as the review skill's Phase 0 will at the other end:
grammar surface, parse builder, AST, resolve, typecheck, IR, runtime,
native registry, kernel table, corpus game, docs, tests/goldens. The classification
decides which gates the plan must SCHEDULE — if the change adds or
extends surface, an Owner Guard, a diagnostic, a registry, or any closed-domain
mechanism, the surface-totality-audit fires and Gate 4 applies. It fires
just as hard when the work ANSWERS A REVIEW FINDING on such a mechanism:
that path is where the gate has actually been skipped, because a finding
names a line and the line reads as the whole job (see the audit's
"class ledger" step).
Misclassifying here is how audit-triggering work ships ungated — so the
tie-breaker is fixed: when unsure whether the trigger matches, it
matches. Unsure is a legal state throughout this process (decisions.md
"Closed-domain completeness"); what is never legal is resolving it with
a silent guess.

## Gate 2.5 — Reuse first: name the definition that already covers it

Before the plan names any new definition — a function, a procedure, a
library entry, a native, a checker arm, an engine table — it names the
existing one that covers the need, or the probe that shows none does.
The search is concrete: the stdlib (`cardlang/stdlib/*.cardlang`), the
family libraries (`docs/libraries/*.cardlang`), the corpus games' own
definitions (`docs/games/*.cardlang`), and the Builtin registries
(`cardlang/builtins/functions.py`), each read for the SHAPE the need
has, not its name. The probe is the sentence written over what exists
and checked (`cardlang.pipeline.check_dsl`); a probe that checks ends
the gate with "reuse: <definition>", and a probe that fails names the
one capability missing, which is then the thing the plan builds — never
the mechanic that wanted it. This is the Language Owner's library-first
proof (`.claude/skills/hoyle/SKILL.md`) applied to every change, not
only to grammar: the grammar pass measured the library tier at a third
of the grammar's size and found the corpus copying what it could not
name, and a plan that writes the copy is how that ratio stays.

Its converse binds in the same gate. When the plan would write the
THIRD copy of a shape the corpus already holds twice (`docs/principles.md`,
"Three implementations before abstracting"), the plan extracts the
definition inside this unit and the three sites use it; the copy census
is the grammar report's seventh finding, and a third copy left standing
is the construct the next game will ask the grammar for.

## Gate 3 — State the acceptance criteria before the task list

Three, always, in the plan's header (CLAUDE.md, load-bearing section):

1. Runs.
2. Regression-clean — mypy + full pytest, byte-identical goldens where
   neutrality is claimed.
3. **Info sets derive** — the criterion generic planning always forgets
   and the reason this language exists. A mechanic that runs but emits no
   observations is incomplete; the plan says so up front, not the review.

Plus the **corpus-lockstep list** — name every game in docs/games/ that
must move in the same change (operating rule 2) — and the **witness
question**: if no corpus game exercises the touched construct end to end,
a minimal witness fixture is a plan step, not a hope (decisions.md
"Closed-domain completeness"). If the plan reaches for a Python escape
hatch, recording the info-set debt in kernel-migration.md is part of the
plan; the kernel path is the default (CLAUDE.md).

## Gate 3.5 — Who reaches it, and is the fix proportionate?

Before the task list: state the change's reachability (R1–R4, decisions.md
"Reachability ranks the work") — who meets the defect it fixes or the
surface it adds — and check the effort against it. An R1/R2 defect
justifies what it costs. An R3/R4 whose fix is more than small routes to
record-and-file: the guard, the marked cell naming its reason, and the
record its tag calls for — an issue for R3, the mark's reason alone for a
non-rigor-critical R4 (decisions.md, "Reachability ranks the work") — not
the fix. An approved issue's R-tag is authority to do the work; it is
never evidence that the work still in front of you is proportionate. A
stage of a large R3/R4 issue is measured against what that issue has cost
so far, not against the stage.

This gate exists because locally-correct choices compound: each finding
honestly pursued, each class honestly swept, and the portfolio quietly
reallocates itself toward the machinery and away from the games. The
plan is where that gets caught, because no later gate sees more than one
change.

Four shapes end the planning turn and surface to the operator instead of
proceeding — not because the work is forbidden, but because the decision
is not the implementing context's to make:

- the plan edits doctrine — decisions.md's completeness sections,
  CLAUDE.md's load-bearing section, or a skill;
- the plan adds enforcement scaffolding whose expected findings are all
  R4 (decisions.md, "The machinery is guarded once");
- the plan reverts or overrides a settled decision;
- the plan's only justification is that a gate requires it, with no R1/R2
  defect anywhere in sight.

**Class over site, once the class exists.** A finding met inside a unit
is fixed at its site once and twice. At the THIRD instance of one class
— the same guard missing at another position, the same refusal landing
in the wrong file, the same raw exception escaping another builtin — the
plan stops fixing sites: it files the class as a sub-issue of the epic
whose Destination owns it (`docs/roadmap.md`, "Destinations"; the
parts-join rule in `docs/harness.md`, "The Ready Front"), names the
machinery part that closes it by construction, and leaves the remaining
sites to that part. The review window of 2026-10-01 to 2026-10-16 is the
measurement: nine issues of one class closed across seven PRs by hand,
every one of them closed by construction by the instantiation trace
that was filed last. A fix that could have been a table row or a
rewrite rule is the tell; the audit's class ledger (`why missed:`) is
where the plan writes which part.

## Gate 4 — For audit-triggering work, the audit's Step 1 happens NOW

Planning is when the surface-totality-audit's Step 1 runs, not
pre-commit: derive the axes in code, run the fresh-context framing check
(the definition sources only — grammar, AST unions, and the registry
modules wholesale; the plan is exactly the conditioning that check exists
to escape), author the expected-outcome column, and run the grid red.
The plan's task list begins with the grid; the red set IS the work list.
The author's derivation is PROVISIONAL input to the framing check, not a
violation of it — the check works by diffing lists, and the accepted
domain statement is what survives the diff. The failure mode this gate
exists for is freezing the domain, or authoring any expected outcome,
without the check having run.

## Gate 5 — The plan contract: every step names its proving artifact

A cardlang plan is a list of red things to make green. Each step names
the artifact that proves it — a grid row, a rejection golden, a proof
module, a byte-identical trace, a guard plus a tracker record (issue #N) for
anything deferred — and where the artifact can exist at plan time, it exists and
is red (`xfail(strict=True)` for grid cells, a failing test for
behavior). A step with no named artifact is not a plan step; it is a
hope. "Done" is defined before work starts, so the review's merge-base
check has a claimed delta to diff against. A counsel's "newly illegal" and
"newly required" lines are plan steps like any other: each names the
guard, test, Contract line or issue that will prove it before the PR
merges. A counsel line with no artifact is a rule nobody will keep.

## Composition

Discuss the design in prose first — trade-offs explained, not asked as
multiple-choice. This skill then shapes the plan; enter plan mode (when
used) already holding Gates 0–3. A change that adds or corrects a corpus
game runs the `cardlang-new-game` skill, which orders the game path
(the read, the twin, the libraries, the proofs) and returns here for
any language gap it files. An interactive thread working a tracker
issue also retitles itself as it moves — `Issue #<N> - <status>`, the
closed status set in docs/harness.md, "Thread titles" — with the first
retitle, to `building`, landing alongside the Lease. A plan that warrants a standing record
lives on the issue it serves — the ruling and the plan are comments
there — and no plan document is written to the tree; the red grid and
the proof artifacts Gates 4 and 5 have a plan author are the change's
own files and land with it. The tree holds spec, never plans. The audit and review skills own their stages — this
skill only guarantees they fire at the right moment, with an unframed
domain.

Ordering across changes is not this skill's call either: issue #143 owns
the sequence, and the direction review (the `cardlang-direction-review`
skill) owns rebalancing it. A plan that would change the ordering argues
to the review, not around it.
