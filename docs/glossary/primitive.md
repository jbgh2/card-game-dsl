---
term: Primitive
definition: Sanctioned game-local Python (a game-local trick-winner function such as Tarot's, a climb query, a call function). Its inputs are the [[primitive-bundle]]. Declared in a game's [[primitives-block]], or — for a game that writes none — in `cardlang/builtins/` (`PRIMITIVE_*`), whose dispatch seam `runtime/primitives.py` holds one hand-written arm per name; that arm count is the elimination metric, and a declared Primitive has no arm at all. Inventory + roadmap in `design-notes/primitive-inventory.md`. Home is classification, never syntactic position: the two standard trick winners are [[builtins]] though named in the same `winner` slot.
layer: kernel
status: canonical
reserved: false
home: `runtime/primitives.py`, `cardlang/builtins/` (`PRIMITIVE_*`)
see: []
retired_spellings: []
findings: []
---
