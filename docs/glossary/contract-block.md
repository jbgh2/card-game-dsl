---
term: Contract Block
definition: The `Contract` section of a module docstring: what the module assumes, what it establishes, and what becomes illegal after it, each Establishes clause naming the [[enforcement-ladder]] rung that holds it (its held-by line). The owning pass's Contract Block decides where a check belongs (decisions.md, "Closed-domain completeness"). Always the full phrase: bare "contract" is a [[definition-contract]] row or a library's `requires`.
layer: check
status: canonical
reserved: false
home: `cardlang/parse.py` through `cardlang/ir.py`, and the runtime and adapter modules
see: [enforcement-ladder, owner-guard, definition-contract]
retired_spellings: []
findings: []
---
