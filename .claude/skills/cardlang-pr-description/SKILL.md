---
name: cardlang-pr-description
description: "Use when writing or rewriting ANY pull-request description in this repo. States problem and fix at a high level, no mechanism, aggressively terse — while keeping the two artifacts the review gates read: the Claims line and (when answering a finding) the class ledger. The diff shows the mechanism; the tracker holds the findings; the ledgers hold the completeness record. The description frames."
---

# Cardlang PR descriptions

The reviewer sees the mechanism when they open the files, and in this repo
the review is also mechanized: the artifact gate replays grids against the
merge base and diffs the result against what the change CLAIMS. So the
description's job is narrow — frame the change and state the claims the
gates verify. Every sentence of mechanism pushes that signal down the page,
and every restated rationale is a copy of decisions.md that will drift
(maintaining.md rule 4 binds PR prose too: the durable "why" lands in the
diff's own docs edits, and the body cross-references it).

## Shape

```
<Problem, one sentence — what was wrong or missing, and for whom
(the R-tag when it fixes a defect). The fix, one or two sentences,
no mechanism. Compat/behavior note only if one exists.>

**Claims:** <only what review must verify: byte-identical | behavioral
delta named in one line | goldens regenerated because …>
**Artifacts:** <grid/ledger module paths, named not restated; the class
ledger block verbatim when answering a review finding>
**For the reviewer:** <at most three one-line bullets: a deviation from
plan, a judgment call, a residual worth their priority. Delete if empty.>

Closes #N.
```

## Rules

- One or two sentences per section. State the problem, state the fix, stop.
- No mechanism: no helper names, visited sets, call sites, data-structure
  choices, pass-by-pass walkthroughs. If the reviewer will see it when they
  open the file, it does not belong. Internal names appear only when the
  name itself is the salient point (a surface keyword, a registry a
  designer touches).
- No review-round narratives. The PR conversation and commits already show
  them; the review's own gate verdict is the reviewer's output, not the
  author's preamble.
- No commit tables, file counts, or "what changed where" — the PR UI shows
  this.
- No test plans and no gate tallies. CI is the evidence for green; a gate
  fact appears only as a **Claim** when it is load-bearing for review
  (byte-identity, a golden regenerated with its reason).
- Findings recorded en route are tracker issues with R-tags; the body lists
  the issue numbers, nothing more.
- Design rationale is not restated: the diff's decisions.md / design-note /
  ledger edits carry it; the body points at them.
- **Two exemptions from terseness, both structured:** the class ledger
  (surface-totality-audit Step 2b — keep the block form, verbatim), and the
  Claims line, which the review's merge-base replay diffs against. These
  are artifacts the machinery reads, not prose.
- The test for every sentence: does it change how someone reviews, or does
  it re-explain what they are about to read? Only the first stays.

## Exemplar

> Out-of-range `partnerships:` seats were accepted silently (R2) — the
> declaration clauses bypass the operand choke point. Declaration-site
> seat, team, and score-target values now route through the same domain
> checks as operands. No behavior change for valid games.
>
> **Claims:** behavioral delta = the four rejection cases in the grid; all
> corpus games byte-identical.
> **Artifacts:** grid + ledger in `tests/test_declaration_clauses.py`.
>
> Closes #155, #153, #154, #107.
