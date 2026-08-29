---
term: Reads Clause
definition: The `reads <name>, …` tail of a [[primitives-block]] entry: the state variables and zones that [[primitive]]'s implementation may see, and no others. A bare name grants the whole declaration (`reads hand` — every seat's hand); an indexed one narrows to the instance the CALL names (`reads hand[p]`, keyed by a parameter of the same entry). It bounds the name-keyed half of the [[primitive-bundle]] — an undeclared name is ABSENT from what the implementation receives, not merely unfetched — and makes hidden-zone reads visible to the checker instead of to a reviewer. The engine-structural half (`EngineFacts`) is not spellable here and arrives whole (issue #474).
layer: compiler
status: canonical
reserved: false
home: grammar `primitive_reads`, `cardlang/runtime/reads.py`
see: [primitives-block, primitive-bundle, primitive]
retired_spellings: []
findings: []
---
