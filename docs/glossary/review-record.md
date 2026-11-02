---
term: Review Record
definition: The PR comment a `cardlang-code-review` pass posts at every tier, whose first line is the `cardlang-review-record:v1` marker naming the head sha reviewed, the tier run, the CONFIRMED count, the issues filed for them, and the Phase-0 artifact-gate verdict. `tools/merge-gate.sh` reads the newest one at the head that would merge, from an author with write access, and fails a Merge Lane C or D PR with none there or one only at an older head (`tools/review_record.py` owns the reading). Distinct from a review thread, which is feedback in flight, and from Codex's review state, which the gate reads as evidence and never as a Review Record.
layer: process
status: canonical
reserved: false
home: `harness.md` ("Arming is merging")
see: ["merge-lane"]
retired_spellings: []
findings: []
---
