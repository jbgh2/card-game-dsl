---
term: Game Description Error
definition: A failure whose faulty artifact is the game description, not the engine — the base the runtime raises so a harness can catch "the game is wrong" without catching engine bugs. `GameDescriptionError` (`cardlang/runtime/errors.py`); [[owner-guard]]s raise `OwnerGuardError` and [[shadow-guard]]s raise `ShadowGuardError`, both subtypes, so the base names what is wrong and the subtype names the role that caught it.
layer: check
status: canonical
reserved: false
home: `cardlang/runtime/errors.py`
see: []
retired_spellings: []
findings: []
---
