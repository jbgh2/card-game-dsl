---
term: Hand Loop
definition: One deal-to-scoring cycle, as a construct rather than as a count — what `skip to next hand` skips to and what `hands_played` counts. The compound that qualifies the reserved word [[hand]] for the iteration sense, against the *hand zone*. It has no structural marker in the language: a phase-name string literal stands in for it, so a game whose scoring phase is named anything else reports zero hands played (→ F-6).
layer: kernel
status: canonical
reserved: false
home: `driver.py`
see: []
retired_spellings: []
findings: [F-6]
---

The loop has no structural marker: `driver.py` counts hands by testing a
phase-name string literal, so a game whose scoring phase is named otherwise
reports none. That defect is F-6's, not this entry's.
