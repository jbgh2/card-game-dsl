---
term: Resolve Step
definition: One stage of the [[resolve]] pass's sequence: a module of the resolve package whose entry `resolve()` calls in order, reading the tree the steps before it left. Each states its own Contract Block; a check lives in the step that calls it, and a step imports only the shared modules, never another step. Not a pipeline stage: the pipeline's stages are the passes, and resolve is one of them.
layer: compiler
status: canonical
reserved: false
home: `cardlang/resolve/__init__.py` (`resolve`)
see: ["resolve"]
retired_spellings: []
findings: []
---
