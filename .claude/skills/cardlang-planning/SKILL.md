---
name: cardlang-planning
description: "MANDATORY planning gate for this repo — invoke BEFORE exploring, brainstorming a design, or entering plan mode for ANY new feature, construct, wall, registry, game, or machinery change. Orders the planning motions: find the decision's owner, classify the change, state the acceptance criteria, and (for audit-triggering work) run the surface-totality-audit's Step 1 inside planning so the grid exists red before implementation. Every plan step names the artifact that proves it."
---

# Cardlang planning

Plans in this repo fail in a specific way: not by omitting steps, but by
inheriting the implementation's frame before any gate can see it. The
permissive-top branch scoped a five-position type-name axis to the two
positions its plan happened to wall — and every downstream gate then
audited the narrowed frame faithfully. The planning stage is where the
frame is set, so it is where the frame must be checked. This skill orders
the motions; the content lives with its owners (CLAUDE.md, decisions.md,
the audit and review skills) — this skill routes, it does not restate.

## Gate 1 — Find the decision's owner before forming an opinion

Every design question in this repo has a home. Before proposing anything,
locate it:

- settled -> decisions.md (search the section titles first)
- open -> docs/open-questions/_index.md, then the named file (cite by slug)
- sequenced -> the GitHub tracker; issue #143 orders the cross-cutting work
- sketched -> docs/design-notes/ (proposals, not settled spec)
- witnessed -> docs/games/ (which corpus games exercise the area today)

A plan that contradicts an owner is wrong before it starts; a plan that
re-derives one is losing information — the planning-stage form of
decisions.md write-time triage. If the work touches a pipeline pass, read
that pass's `Contract` block before planning around it.

## Gate 2 — Classify the change

Classify exactly as the review skill's Phase 0 will at the other end:
grammar surface, parse builder, AST, resolve, typecheck, IR, runtime,
stdlib registry, corpus game, docs, tests/goldens. The classification
decides which gates the plan must SCHEDULE — if the change adds or
extends surface, a wall, a diagnostic, a registry, or any closed-domain
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
module, a byte-identical trace, a wall plus a tracker record (issue #N) for
anything deferred — and where the artifact can exist at plan time, it exists and
is red (`xfail(strict=True)` for grid cells, a failing test for
behavior). A step with no named artifact is not a plan step; it is a
hope. "Done" is defined before work starts, so the review's merge-base
check has a claimed delta to diff against.

## Composition

Discuss the design in prose first — trade-offs explained, not asked as
multiple-choice. This skill then shapes the plan; enter plan mode (when
used) already holding Gates 1–3. Plans that warrant a standing artifact
land in `docs/plans/` (dated, one file per plan); existing plan records
stay where they are. The audit and review skills own their stages — this
skill only guarantees they fire at the right moment, with an unframed
domain.
