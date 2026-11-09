# ADR-0018: A Codex review counts as the review on Merge Lanes C and D

- **Status:** Accepted
- **Date:** 2026-11-02
- **Ruled by:** the operator, on the question PR #1032 put to the operator
- **Record:** issue #1030 (the review-on-record merge gate); PR #1032, which lands it
- **Governs:** harness.md, "The Merge Lanes"; harness.md, "Arming is merging"

## Context

Issue #1030 had the merge gate fail a Lane C or D pull request with no
review on record at the merging head, and said either a `cardlang-code-review`
Review Record or a Codex review would do. The same issue said the lane
definitions would not change, and those definitions named a
`cardlang-code-review` pass as the requirement on both lanes. The two
sentences disagreed. PR #1032 first built the reading that held under both,
treating a completed Codex review as evidence only, and asked the operator
to choose.

## Decision

"Codex counts as a review on c or d lanes." A review Codex has completed at
the merging head counts as that lane's review on record without a Review
Record. On Lane C it meets the tier floor that otherwise needs a Standard or
Thorough record. Codex's findings are review threads, and the gate's thread
clause owns them. A Codex review never clears a Review Record's findings at
the same head, and the gate refuses a Codex state it cannot read or one
still running at the head.

## Alternatives

- **Codex as evidence only, with the Review Record required.** Lost.
  Every agent merge would have needed a run of this repository's own
  review, even on a head the bot had already reviewed. Codex already
  reviews every pull request when it opens or is marked ready.
- **Codex counts on Lane D only.** Not chosen. The ruling names both lanes.
- **Reading the marker's `has_unresolved_findings` flag as a refusal.**
  Not built. On PRs #945 and #996 the flag stayed `true` after every Codex
  thread was resolved, so it would refuse findings that had already been
  refuted or filed. The thread clause reads the threads themselves.

## Consequences

The lane definitions in `docs/harness.md` name a Codex review beside the
`cardlang-code-review` pass. After a fix push, the Dispatcher may request
Codex (`@codex review`) instead of re-running the review skill.
`tests/test_review_record.py` crosses the Codex review state (none,
completed at the head, completed at an older head) with the record grid.
The gate trusts the bot's report that it reviewed the head. Nothing in the
gate checks what Codex read, and the completeness ledger names that
residual. A Codex arm that stops reviewing, for example when it asks for an
environment instead, leaves the Review Record as the only arm.
