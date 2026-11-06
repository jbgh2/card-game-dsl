# ADR-0019: A review's findings are review threads, whichever reviewer found them

- **Status:** Accepted
- **Date:** 2026-11-05
- **Ruled by:** the operator, on the harness desk's proposal in the thread that built PR #1032
- **Record:** issue #1030 (the review-on-record merge gate); PR #1032, which lands it
- **Governs:** harness.md, "Review threads"; harness.md, "Arming is merging"

## Context

Codex posts each finding as an inline review thread. The thread rule
requires every thread to get a disposition reply and be resolved, and
the merge gate refuses a pull request while any thread is unresolved. A
`cardlang-code-review` pass instead posted one comment, the Review Record,
with its findings written in its body. A standalone comment has no
resolved state, so this repository's own findings never passed through
the thread rule. The record had to carry their dispositions itself, as a
hand-typed list of filed issues, and that left one rule held only by the
skill's instructions: findings short of CONFIRMED get filed. The operator
asked whether the review posts its findings the way Codex does, and
chose to make the two reviewers behave the same.

## Decision

A `cardlang-code-review` pass posts each CONFIRMED and PLAUSIBLE finding
as one review thread at the head it read. Its Review Record follows as a
comment. Both go through one writer, `tools/review_record.py post`,
which takes the CONFIRMED count from the same findings list. A finding's
disposition belongs to its thread, as it does for a Codex finding, so the
record carries a head, a tier, a count and an artifact-gate verdict, and
no dispositions.

## Alternatives

- **The findings stay in the record's text.** Lost: the record has no
  resolved state, so its findings bypass the thread rule, and the filed
  list is a claim typed by hand.
- **Threads, with the filed list kept in the record.** Not built: the
  record is written when the review ends, before any finding is filed,
  so keeping the list current means editing the record afterwards, and
  the thread already holds the disposition.
- **Gate-checked thread count.** Not built: the gate could check that
  the threads named in a record exist, but that cross-read is
  machinery on machinery. The writer, as the one owner of both posts,
  holds the pairing instead.

## Consequences

The `filed` field leaves the record's vocabulary. The gate no longer
judges Lane C's filed list; the thread clause holds every finding's
disposition instead, on both lanes. Lane D still refuses any CONFIRMED
finding at the head. A finding about a file outside the diff is anchored
on the diff's first file, because GitHub accepts review comments only on
changed files. GitHub's REST review endpoint takes no file-level comment,
so the writer adds every thread to a pending review through GraphQL and
submits the review only once all of them are in; a failed post deletes
the pending review and leaves no thread behind. The record's marker is
`cardlang-review-record:v2`, since its vocabulary changed. A record written by hand still parses, and the review
skill's "Output" is what keeps reviews on the writer.
