---
term: Primitives Block
definition: The `primitives { }` game clause declaring what a [[game]] borrows from outside the DSL — one colon-row per [[primitive]], carrying its typed signature — the declared type names, and the [[collection-type]] — and its [[reads-clause]] (`pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit in hand_sequence`). Its PRESENCE partitions the game's native-call namespace in both directions: with a block the game names its own entries plus the [[builtins]] and no other game's Primitive; without one it keeps the hand-authored `PRIMITIVE_CALL_FUNCS` registry. An EMPTY block is a declaration ("this game borrows no Python"), not an absence.
layer: compiler
status: canonical
reserved: false
home: `cardlang/primitives_block.py`, grammar `primitives_block`
see: [primitive, reads-clause, primitive-bundle, phase-scoped-read, collection-type]
retired_spellings: []
findings: []
---
