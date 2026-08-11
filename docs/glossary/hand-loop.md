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

Naming the loop is not fixing it. F-6 is the defect — `driver.py` counts hands by
testing `phase.name == "scoring"` — and it stays F-6's, tracked on its own terms;
this entry exists so the concept has one spelling to be discussed under. The
structural-marker question (what construct, if any, should mark the loop) belongs
to that finding, not here.
