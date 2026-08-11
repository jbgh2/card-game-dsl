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

Before #207 this class was ~40 bare `RuntimeError`s, distinguished from engine bugs
only by the repeated phrase "in the runtime's currency" (→ F-19, F-23) — the reason
the concept needed a name and a type rather than a convention.
