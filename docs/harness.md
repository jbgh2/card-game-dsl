# The Operating Harness

How work flows through this repo: who may take what, who merges which
change, and how the tracker carries the work graph. This file is process
doctrine. The merge *gate* stays in CLAUDE.md ("Verifying changes"); the
vocabulary lives in `docs/glossary.md` (§7); deferred harness *work*
lives in the tracker like all work (epic
[#274](https://github.com/jbgh2/card-game-dsl/issues/274)). Everything
here is public by design — the graph, the doctrine, the roles, and their
history live in the open repo and tracker, never in a sidecar database.

Changes to this file are Merge Lane B by its own table.

## The Merge Lanes

The merge gate — CI green on all three checks (CLAUDE.md, "Verifying
changes") — is lane-invariant. A Merge Lane answers the question the gate
does not: **who may perform the merge**. The earlier the letter, the more
authority it demands; later letters append as delegation earns
granularity, so the alphabet grows at the delegated end and the apex
never renumbers. Four lanes:

- **Merge Lane A — deity merge.** The operator merges, and the decision
  carries the **Language Owner**'s counsel (below), attached to the
  change before the operator rules. Merge Lane A holds exactly the
  grammar and its membership is closed in both directions: no evidence
  promotes the grammar out of it, and no class ever promotes into it —
  the widening and tightening protocols operate strictly below it. The
  language's surface is not an autonomy candidate at any evidence level.
- **Merge Lane B — operator merge.** The operator merges. Agents do
  everything else — implement, review, respond, push — and stop at the
  merge button.
- **Merge Lane C — reviewed agent merge.** Any agent merges once CI is
  green, the full `cardlang-code-review` at the tier its classification
  selects is clean or its findings are filed, and — where the change
  trips the `surface-totality-audit` trigger — that skill's artifacts are
  in the change. One escalation is built in: a review round that finds a
  defect in the fix for a previous finding escalates the PR to Merge
  Lane B. Nth-order findings on an agent's own fix are the operator's to
  adjudicate, never the fixing agent's.
- **Merge Lane D — clean-pass agent merge.** Any agent merges once CI is
  green and one `cardlang-code-review` pass at Quick tier reports no
  CONFIRMED finding. Other findings are filed with their reachability,
  not driven to fix-now.

The lane is decided by the change's **class** from the table below, never
per-PR by preference. Two rules compose the table:

- **Supremum.** A change touching classes in different lanes takes the
  earliest lane letter touched (A over B over C over D).
- **Unsure resolves upward.** The planning-gate tie-breaker, applied to
  merging: when the classification is uncertain, the earlier lane
  applies — stopping at Merge Lane B, because Merge Lane A absorbs no
  uncertainty: its membership is exact (a diff touches `.lark` or it does
  not). Unsure is a legal state; a silent guess is not.

| Change class | Paths | Merge Lane |
|---|---|---|
| Grammar (`.lark`) | `cardlang/grammar/**` | A |
| Parse builders | `cardlang/parse.py` | B |
| AST nodes | `cardlang/ast/**` | B |
| Resolve | `cardlang/resolve.py` | B |
| Typecheck | `cardlang/typecheck.py`, `cardlang/types.py` | B |
| IR | `cardlang/ir.py` | B |
| Runtime (`evaluate` / `execute` / `driver` / `state`, the OpenSpiel adapter) | `cardlang/runtime/**`, `cardlang/openspiel/**` | B |
| Stdlib (`rules.cardlang`, registries, builtins) | `cardlang/stdlib/**`, `cardlang/builtins/**` | B |
| `docs/games/` corpus and family libraries — DSL-only edits, zero engine diff | `docs/games/**`, `docs/libraries/**` | C |
| Docs — the spec and doctrine (top-level `docs/*.md`, `docs/glossary.md`, CLAUDE.md) | `docs/*.md`, `CLAUDE.md` | B |
| Docs — exploratory (`design-notes/`, `open-questions/`, `research/`, `plans/`, `superpowers/`) | `docs/design-notes/**`, `docs/open-questions/**`, `docs/research/**`, `docs/plans/**`, `docs/superpowers/**` | C |
| Tests / goldens — coverage-only additions, no behavior change claimed | `tests/**` | C |
| Tests / goldens — anything else (golden regeneration, proof-harness changes) | `tests/**` | B |
| `.claude/skills/` | `.claude/**` | B |
| `experiments/` rigs | `experiments/**` | C |
| `tools/` harness scripts — mechanical fixes | `tools/**` | C |
| `tools/` harness scripts — semantics (a change to what Ready means is a change to this file) | `tools/**` | B |
| CI and infra (`.github/`, `pyproject.toml`, the runner) | `.github/**`, `pyproject.toml` | B |
| Public-facing (README, LICENSE, licensing and grant artifacts) | `README*`, `LICENSE*` | B |
| Tracker structure (label vocabulary, edge conventions, issue #143) | — | B |
| Revert of a red Merge Lane C/D merge | — | D |
| Docs hygiene — typos, cross-references, register fixes with no semantic delta; `glossary-findings.md` rows; ledger citation fixes | — | D |

The Paths column is machine-read: `tools/lane-of.sh` classifies a diff by
matching every changed file against every row and taking the supremum
lane across all matches — so twin rows sharing a path resolve to their
stricter twin mechanically, and relaxing to the softer twin (a
coverage-only test change, a mechanical tools fix, a hygiene edit) is
judgment the tool never performs and an agent never performs on its own
behalf. A file matching no row is reported unmapped and defaults to
Merge Lane B (the missing-class rule above); rows whose class is
semantic, not path-shaped, carry `—` and bind through judgment alone. An
**agent merge** additionally passes `tools/merge-gate.sh` — base is
main, every check green, zero unresolved threads, mechanical lane C or
D, evidence printed — and hand-classifying around the tools is not a
lane verdict.

The rows through "Tests / goldens" derive from the `cardlang-code-review`
skill's Phase 0 classification, with its "docs prose" and "tests/goldens"
classes each split in two; the remaining rows are the classes that
classification does not carry. A change class missing from this table is
a defect in this table: the change merges at Merge Lane B — unsure
resolution stops there — and the same change fixes the table.

**The pilot posture.** Every language-pipeline class starts at Merge
Lane B — and the grammar lives at Merge Lane A — deliberately: lanes
widen by evidence, never by argument, and Merge Lane A does not widen at
all. A class is delegated one letter at a time (B to C, C to D, and past
D as letters are added) only by editing this table in an operator-merged
change whose body cites the evidence — the merges of that class since the
last assignment and their post-merge defect count. A class moves **up**
the alphabet the moment anyone doubts it: tightening needs no ceremony,
and any agent may do it in the same change as a revert or fix. Tightening
stops at Merge Lane B — Merge Lane A is not a destination, it is the
grammar's birthright and nothing else's.

**The revert rule.** A Merge Lane C or D merge that goes red after merge
— CI, the canary, or a defect witnessed downstream — is revertable by any
agent without asking, and the revert itself is Merge Lane D. What was
learned goes to the tracker before the re-attempt, not into a bigger
second try.

## Review threads

A review thread is feedback in flight, and its resolved state is the only
ledger of what has been handled. Two obligations, lane-invariant:

- **Every thread gets a reply before merge**, and the reply states the
  finding's disposition with its evidence: **fixed** (the commit),
  **filed** (the issue, with its reachability), **refuted** (the executed
  evidence — refutation is constructive, exactly as in the review skill),
  or **escalated** (named to the operator).
- **The responder resolves the thread after replying** — except an
  escalated thread, which stays open until the operator rules. An
  unresolved thread IS the visible flag that feedback still awaits
  someone; resolving without a disposition reply is silencing, not
  handling.

The merge precondition, any lane: **zero unresolved threads**. Top-level
review bodies and standalone PR comments have no resolved state; their
reply is their record. Reviewer-specific protocols (Codex's thumbs
reactions) ride on top as courtesy; the thread reply-and-resolve is this
repo's own record. The check is derived, like everything else:

```bash
gh api graphql -f query='{ repository(owner: "jbgh2", name: "card-game-dsl") {
  pullRequest(number: N) { reviewThreads(first: 100) {
    totalCount nodes { isResolved } } } } }' --jq '
  .data.repository.pullRequest.reviewThreads
  | if .totalCount > 100 then error("capped: \(.totalCount) threads") else . end
  | [.nodes[] | select(.isResolved | not)] | length'
```

Zero is the clean state.

## The work graph

The tracker is the work graph. Three edge kinds, all native, all visible
on the issue:

- **Containment** — sub-issues. An `epic` is a container of sub-issues
  and holds no work of its own (CLAUDE.md, "The tracker").
- **Dependency** — blocked-by edges between issues. An issue with an open
  blocked-by dependency is not workable, whatever its labels say.
- **Witness** — the `blocked:needs-witness` label, for the one blocker
  that is not an issue: the body names the game or data point that
  unblocks (CLAUDE.md, "The tracker").

Ordering stays where it is:
[issue #143](https://github.com/jbgh2/card-game-dsl/issues/143) is the
authority on cross-cutting sequence, and its maintenance contract (in its
own body) says who may reorder it. The graph answers *what is possible*;
#143 answers *what is next*.

### The Ready Front

The **Ready Front** is the derived set of issues an agent may take
without asking. Derived superset-style, like the two sweeps in CLAUDE.md
("The tracker"): an open issue is Ready unless a disqualifier holds, so
the front needs no upstream discipline to be correct.

The disqualifiers, in the order the sweep counts them:

- it is the pinned ordering issue — #143 is a living document, not work;
- it carries `epic` — containers are not work;
- it lacks a kind label or carries `needs-triage` — unclassified;
- it lacks a `reachability:` label — unordered;
- it carries any `blocked:` label — witness-gated;
- it has an open blocked-by dependency;
- it is Leased.

`tools/ready-front.sh` computes the front — the third sibling of the two
CLAUDE.md sweeps. It annotates each Ready issue with its #143 rank where
that body references it; ordering authority stays with #143 and the
operator. The sweep reports, it does not decide, and it never truncates
silently: any capped or partial fetch is a loud failure, and every
excluded issue lands in a counted bucket on stderr.

**Body sufficiency is judgment, deliberately outside the mechanical
definition.** A Ready issue can still be unworkable — Detail too thin to
act on (CLAUDE.md, "The tracker"). The taker's first act after Leasing is
that check, and the bounce on failure is loud and public: comment what is
missing, add `needs-triage`, release the Lease. A bounced issue leaves
the front through its labels, not through anyone's memory.

## Leases

A **Lease** is how an agent takes an issue: create the canonical ref

    claude/issue-<N>

with a create-only operation — the ref-creation API (`gh api -X POST
repos/<owner>/<repo>/git/refs`), whose failure is the mutex: 201 takes
the Lease, 422 "Reference already exists" loses it, at any commit. A
plain `git push` cannot take a Lease, and neither can
`--force-with-lease=<ref>:` — when the ref already exists at the pushed
commit (the dispatch-time norm: every taker starts at main's tip), both
report "Everything up-to-date" and exit 0, so both takers would believe
they won. Server-side creation is the entire concurrency story at this
scale. The Lease is public,
visible in the branch list, and self-releasing: merging or deleting the
branch releases it. The issue's assignee may mirror the Lease for
glanceability; the ref is the authority. Operator branches (`ben/...`)
are not Leases and are never reaped.

**Staleness is derived, like everything else.** A Lease with no open PR
and no commit for 48 hours is stale. The reap is conservative: comment on
the issue first; delete the branch only when it holds no commits absent
from main; a stale branch *with* unique commits is flagged to the
operator instead. Reaping is a Warden chore
([#277](https://github.com/jbgh2/card-game-dsl/issues/277)); until that
Standing Role exists it is anyone's, manually.

## Standing Roles

A **Standing Role** is a named, recurring, unattended agent charter — a
skill under `.claude/skills/` (`role-<name>`), invoked on a schedule
rather than by a human. Role charters are versioned in the repo and
reviewed like code (their lane: `.claude/skills/`, Merge Lane B).

Standing Roles are minted through the tracker. Epic
[#274](https://github.com/jbgh2/card-game-dsl/issues/274) names the first
two: a Dispatcher that works the Ready Front
([#276](https://github.com/jbgh2/card-game-dsl/issues/276)) and a Warden
that runs the sweeps and reaps stale Leases
([#277](https://github.com/jbgh2/card-game-dsl/issues/277)). A role's
charter lives in its skill file; this file stays the map.

## The Language Owner

The **Language Owner** is a persona, not a person and not a Standing
Role: a named character whose charter is the language itself, consulted
at planning time on every Merge Lane A change and on any design that
would create one. The division of labor is fixed. The Language Owner
supplies the details — worked alternative sentences, corpus impact,
precedent from `decisions.md` and the games, the edge a new production
cuts against surface totality — and the operator supplies the decision:
counsel informs intuition and never substitutes for it. The persona
advises; the operator rules. Counsel attaches to the change (PR body or
design note) before the operator merges.

The Language Owner is named **Hoyle** — after Edmond Hoyle, whose name is
the English proverb for rules authority ("according to Hoyle"). The
charter is minted through the tracker
([#284](https://github.com/jbgh2/card-game-dsl/issues/284)) and lives in
its skill file, reviewed like code.

## The physical layer

Two standing facts bind the harness, and one authority stays put:

- CI runs on a self-hosted runner that rides the operator's laptop:
  a closed lid queues every run. Unattended overnight work is gated on an
  always-on runner
  ([#278](https://github.com/jbgh2/card-game-dsl/issues/278)).
- The repo is public with a self-hosted runner: **workflow runs from
  forks are never approved** — not by an agent, not on request, not for a
  plausible-looking contribution. First-contributor runs stay pending
  until the operator has read the diff.
- Spend is the operator's: anything that draws real money — API eval
  runs, new hardware, subscriptions — is proposed, never initiated, by
  agents.
