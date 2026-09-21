---
name: cardlang-direction-review
description: "Periodic portfolio review — run every ~10 merged PRs, or when the operator asks where effort is going. Reads the whole tracker and recent PR history, checks the trend lines no single change can see, and outputs a short verdict, the triage pass that sets each arriving issue's Priority Tier, and at most small doctrine amendments. Never outputs new enforcement machinery. This is the outer loop; the audit and review skills are the inner one."
---

# Cardlang direction review

Every gate in this repo evaluates one change. Portfolio drift — locally
correct decisions compounding into a misallocated whole — is invisible to
all of them by construction, and it is the failure mode the repo has
actually had: a finding stream that shifted from designer-reachable
defects to machinery auditing itself, one doctrinally-sound change at a
time. This skill is the context wide enough to see that. It runs cold:
whole tracker, recent PRs, no open diff, no loop being closed.

## The trend checks

Each check names its query so the answer is derived, not vibed:

1. **Finding severity over time.** Classify the last ~15 PRs' recorded
   findings and the issues they filed by severity class (the review
   skill's order) and reachability (decisions.md, "Reachability ranks the
   work"). The healthy shape is R1/R2 findings declining because the
   surface is sound. The drift shape is R4 findings growing because the
   machinery is examining itself. State which shape the window shows.
2. **Machinery vs witness.** Of the window's changes, how many built or
   extended enforcement scaffolding, and how many built execution
   surface — games, differentials, playout reach, proof generality?
   CLAUDE.md's load-bearing section says which way that ratio should lean.
3. **Aging by reachability.** The oldest open R1/R2 issues, by date — and
   age is a flag to read, never a rank. An aged issue is one of three
   things, and only its body read against the tree says which:
   **neglected** (a wrong game behind it while R4 work merges — the
   allocation failure this check exists to catch), **stale** (its premise
   no longer matches the tree — rescope it, don't re-flag it), or
   **correctly parked** (reach without a wrong game behind it; the tag
   ranks reach, not worth). A flagging without the read wastes the
   flagging.
4. **Inflow vs closure, by class.** Issues opened vs closed in the window,
   grouped by the class-closing refactor they belong to (if one is on the
   tracker). A class whose instances arrive faster than its refactor
   advances is a refactor being outrun — say so.
5. **The doctrine's own cost.** Any gate that consumed effort in the
   window without changing an outcome — an audit whose findings were all
   R4, a ledger nobody read back — is a candidate for narrowing. Cite the
   instance; propose the narrowing as a doctrine amendment, not a silent
   lapse.
6. **Surface nobody uses.** `python -m tools.dead_surface` prints every
   grammar rule and keyword that no corpus game, library or stdlib rule
   uses. Each row is a retire-or-keep decision under the orphaned-surface
   ruling, decided here and recorded in the verdict — never a gate, since
   surface may land ahead of its first game. The report is derived on
   demand and is never checked in.

## Output contract

A short verdict (one screen): the shape the window shows, the two or three
reallocation moves with the most leverage, and — only where a trend check
demands it — a doctrine amendment, drafted as the exact edit.

**Then the Active Epics.** The review is the one role that opens or closes
a milestone (docs/harness.md, "The Ready Front"): at most two open at a
time, each holding one epic and its parts, its description the finish
line, and the epic's body naming each part's Merge Lane (`tools/lane-of.sh`
on the files the part touches) so a taker knows before Leasing whether the
unit stops at the operator's button — and no part is Merge Lane A: that
part is done by the operator with Hoyle before activation, or excluded
and queued in #143 as the operator's own unit. Close one only against that sentence,
read against the tree — a
sub-issue count is not it. Open the next from the head of #143 only when one closes, and make a
generator issue (a read, a sweep) blocked-by the epic its pick spawned so
the finding stream drains before it fills again.

**Then triage.** The review is the one role that sets a Priority Tier
(docs/harness.md, "The Ready Front"): every designer-reachable issue filed
since the previous verdict gets `priority:P1` (a silent defect a designer
or corpus game meets, or a corpus game wrong against its source),
`priority:P2` (a loud designer-facing defect), or is left untiered on
purpose; a departure from that default says why on the issue, and a tier
whose reason has gone comes off. Then re-run `tools/ready-front.sh` and
check two things: the top of the front is the work the verdict names,
and every move the verdict names is selectable by the Ready Front (an
epic container, a doc paragraph, and the verdict itself are not). Issue
#143 is the queue of units not yet active: promote its head to a
milestone when a slot opens, and edit it only when the queue changes —
the sweep does not read it, so it ranks nothing. Save
the verdict where the operator will find it and previous verdicts can be
compared.

What this skill must never do: add gates, add machinery, file more than a
handful of issues, or grow its own process. It is the stopping rule, so it
does not get to be a source of work — a direction review whose output is
new obligations has failed at its one job. If a verdict recurs twice
unactioned, that is a conversation with the operator, not a third verdict.
