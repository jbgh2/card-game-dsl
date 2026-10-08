---
term: Destination
definition: A finished state of the project, stated in the present tense in `roadmap.md` ("Destinations") with the query that reads today's distance from it. Every unit of work names the Destination it advances — a milestone in the first line of its description, a #143 row beside its title — or `Upkeep` when it advances none, and at most one open milestone is Upkeep. The direction review reads the distances each run (`python -m tools.destinations`) and promotes the next unit of a Destination no unit has advanced. Only the operator adds or retires one. Distinct from an [[active-epic]], which is a unit, and from a Priority Tier, which orders loose issues.
layer: process
status: canonical
reserved: false
home: `roadmap.md` ("Destinations")
see: ["active-epic", "priority-tier", "ready-front"]
retired_spellings: []
findings: []
---
