# ADR-0006: A plan or a ruling lives on the issue it serves; the tree holds spec, never plans or handoffs

- **Status:** Accepted
- **Date:** 2026-10-18
- **Ruled by:** the operator; the handoff half ruled 2026-08-02 in session
- **Record:** PR #908 (merged 2026-10-18)
- **Governs:** CLAUDE.md, "Prose states what is; the journey lives in dated artifacts"; the `cardlang-planning` skill

## Context

The planning skill said a plan that warrants a standing artifact lands in
`docs/plans/`, and twenty-four dated plan files accumulated under two
directories that nothing owned once their PR merged. The same concern had
already retired end-of-session handoff documents on 2026-08-02: the state
was in memory, on the tracker and in PR bodies as the work happened, and a
fourth copy was a worse one that drifted. Backfilled on 2026-11-01 from the
PR and the session record.

## Decision

A plan that warrants a record lives on the issue it serves, as comments; a
ruling is a `## Ruling` section and a comment there; nothing is written to
the tree until the implementation lands. The two plan directories are
removed and every citation of a plan file is re-pointed at the PR or issue
that carries the ruling, which the git history still holds in full. No
handoff documents: the test is that `gh issue view <N>` plus the issue's
comments is enough to resume, and if it is not, the missing fact belongs on
the issue, in the PR body or in memory, not in a document.

## Alternatives

- **Keep plan files as dated artifacts under a scraper exemption.** Lost:
  nothing owns them after merge, and the journey already has its homes —
  the commit, the PR body, the issue, the report.

## Consequences

The lane table and the two scrapers that walked the directories
(`_SNAPSHOTS` in `tests/test_audit_trigger_agreement.py`, `EXCLUDED_DIRS`
in `tests/test_doc_references.py`) no longer name them. ADR-0016 adds the
one tree-held artifact a ruling gets — the record of a ruling made, written
when it lands, never a plan.
