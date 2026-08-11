---
term: Game Description Error
definition: A runtime refusal naming an illegal game description: `GameDescriptionError` (`cardlang/runtime/errors.py`), the base a harness catches. The base says WHAT is wrong; the subtype says which role caught it — an [[owner-guard]] raises `OwnerGuardError`, a [[shadow-guard]] raises `ShadowGuardError`. The base therefore reaches engine gaps too, which is why a harness catching it must not treat a `ShadowGuardError` as merely a bad game.
layer: check
status: canonical
reserved: false
home: `cardlang/runtime/errors.py`
see: []
retired_spellings: []
findings: []
---
