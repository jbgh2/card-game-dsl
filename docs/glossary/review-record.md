---
term: Review Record
definition: The PR comment a `cardlang-code-review` pass posts at every tier through `tools/review_record.py post`, after that pass's findings as one review thread each, whose first line is the `cardlang-review-record:v2` marker naming the head sha reviewed, the tier run, the CONFIRMED count derived from the findings, and the Phase-0 artifact-gate verdict; each finding's disposition is its thread's, never the record's. `tools/merge-gate.sh` reads every one at the head that would merge, from an author with write access, and fails a Merge Lane C or D PR with no review there, one only at an older head, or one at the head whose findings or artifact gate the lane refuses (`tools/review_record.py` owns the reading). Distinct from a review thread, which is feedback in flight, and from Codex's review state, the other review the gate reads: a Codex review completed at the head is a review on record without a Review Record, never clears one's findings, and fails the gate when unreadable or still running at the head.
layer: process
status: canonical
reserved: false
home: `harness.md` ("Arming is merging")
see: ["merge-lane"]
retired_spellings: []
findings: []
---
