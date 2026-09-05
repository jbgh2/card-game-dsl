---
term: Primitive
definition: Sanctioned game-local Python (a game-local trick-winner function such as Tarot's, a climb query, a call function). Its inputs are the [[primitive-bundle]]. Declared in a game's [[primitives-block]], which is a Primitive's only route to its Python: `runtime/primitives.py` holds no hand-written call arm, and the dispatch derives from the declaration. The elimination metric is the registry `PRIMITIVE_CALL_FUNCS` (`cardlang/builtins/`), whose members leave as the constructs replacing them land in the language. Inventory + roadmap in `design-notes/primitive-inventory.md`. Home is classification, never syntactic position: the two standard trick winners are [[builtins]] though named in the same `winner` slot.
layer: kernel
status: canonical
reserved: false
home: `runtime/primitives.py`, `cardlang/builtins/` (`PRIMITIVE_*`)
see: []
retired_spellings: []
findings: []
---
