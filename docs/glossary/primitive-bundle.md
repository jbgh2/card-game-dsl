---
term: Primitive Bundle
definition: The pair every Primitive receives: the **facts** (`EngineFacts`) and its declared **reads** (`GameReads`), as the NamedTuple `narrowing.PrimitiveBundle`. Named because it is one thing passed together, restated as `(facts, gr)` at every primitive signature; the NamedTuple carries the two halves' names at every site holding the whole thing, and still unpacks positionally. The reads half is per-primitive for a call-position Primitive, whose row is built from its own entry, and per-module for the walled namespaces a block cannot name, whose binders take an authored `PRIMITIVE_READS` row; the facts half is whole either way.
layer: kernel
status: canonical
reserved: false
home: `narrowing.py`, `reads.py`
see: []
retired_spellings: []
findings: []
---
