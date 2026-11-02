---
term: Region Verb
definition: A board Builtin that answers a collection of cells named by the board rather than by a predicate -- `home(p)`, `far_row(p)`, `neighbors(c)` -- typed `Collection<Cell>`. Read from the board entry (`BOARD_VERB_NEEDS` names what each reads); the [[set-form]] is the predicate-named collection of the same type.
layer: kernel
status: canonical
reserved: false
home: `builtins/signatures.py` (`home`, `far_row`, `neighbors`)
see: [Set Form]
retired_spellings: []
findings: []
---

**Kernel.** A Region Verb's answer is a tuple in the board entry's order, which need not be the board's cell order (`neighbors` lists adjacency as the entry records it).
