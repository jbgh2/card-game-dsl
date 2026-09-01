---
term: Reads Clause
definition: The `reads <name>, …` tail of a [[primitives-block]] entry: the state variables and zones that [[primitive]]'s implementation may see, and no others. A bare name grants the whole declaration (`reads hand` — every seat's hand); an indexed one narrows to the instance the CALL names (`reads hand[p]`, keyed by a parameter of the same entry). Each name denotes exactly ONE declaration: the clause reads a single flat namespace where the game's syntax keeps four (the game's `state { }`, a phase's, an indexed `zones { }` declaration, an unindexed one), so a name the game declares in two of them is refused rather than classified by whichever the classifier consults first, and a name only a PHASE declares is refused unless the read NAMES that phase (`reads trump_suit in hand_sequence`, a [[phase-scoped-read]]) — the row is materialized on every call, while a phase's frame stands only while that phase runs, so the tail is both which declaration is meant and the promise that the entry is called only where it stands. It bounds the name-keyed half of the [[primitive-bundle]] — an undeclared name is ABSENT from what the implementation receives, and reading one fails as a typed `PrimitiveReadError` naming the clause to extend, not merely unfetched — and makes hidden-zone reads visible to the checker instead of to a reviewer. The engine-structural half (`EngineFacts`) is not spellable here and arrives whole (issue #474).
layer: compiler
status: canonical
reserved: false
home: grammar `primitive_reads`, `cardlang/runtime/reads.py`
see: [primitives-block, primitive-bundle, primitive, phase-scoped-read]
retired_spellings: []
findings: []
---
