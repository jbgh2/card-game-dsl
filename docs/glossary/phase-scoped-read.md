---
term: Phase-Scoped Read
definition: A [[reads-clause]] entry that names the [[phase]] whose own `state { }` declares it — `reads hand[p], trump_suit in hand_sequence`. It is what lets a [[primitives-block]] entry read phase-local state at all: the tail says which of the game's declarations is meant, since sibling phases may legally declare the same name, and it carries the entry's call-position constraint to the reader of the block. The tail is per READ, so one clause mixes game-level names with one phase's; one entry names at most ONE phase. In exchange the entry is callable only where that phase runs — inside the phase's own subtree (its qualifier, `before_each`, `after_each`, body and nested phases), from a [[move-type]] every offering mention of which sits inside it, or at a `run` site that does; a function, define, rule, trick-order row or game-level expression is refused, as is a move type nothing offers. Declaration-only surface: nothing new is emitted and no information set moves — a scoped name materializes through the same innermost-frame walk as a game-level one, which is correct by construction because a strict descendant of the named phase re-declaring the name is refused at compile.
layer: compiler
status: canonical
reserved: false
home: grammar `primitive_read`, `cardlang/resolve.py` (`_check_read_tail`, `_check_scoped_read_containment`)
see: [reads-clause, primitives-block, primitive, phase]
retired_spellings: []
findings: []
---
