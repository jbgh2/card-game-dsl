---
term: Priority Tier
definition: The direction review's triage weight on an issue — `priority:P1` (taken next) or `priority:P2` (after every P1); no tier means the issue ranks by reachability alone. Set only by the direction review, never at filing; `tools/ready-front.sh` sorts the [[ready-front]] by it, a blocker inheriting the tier of what it blocks. Distinct from the reachability label, which says who can meet a defect (decisions.md, "Reachability ranks the work"), and from a review finding's P1/P2 badge, which is a severity within one review.
layer: process
status: canonical
reserved: false
home: `harness.md`
see: ["ready-front"]
retired_spellings: []
findings: []
---
