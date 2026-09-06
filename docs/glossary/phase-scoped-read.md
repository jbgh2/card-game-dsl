---
term: Phase-Scoped Read
definition: A [[reads-clause]] entry that names the [[phase]] whose own `state { }` declares it — `reads hand[p], trump_suit in hand_sequence`. It is what lets a [[primitives-block]] entry read phase-local state at all: the tail says which of the game's declarations is meant, since sibling phases may legally declare the same name, and it carries the entry's call-position constraint to the reader of the block. The tail is per READ, so one clause mixes game-level names with a phase's; the phases one entry names must NEST, one inside the next. In exchange the entry is callable only where the INNERMOST of them runs — inside that phase's own subtree (its qualifier, `before_each`, `after_each`, body and nested phases), from a [[move-type]] every offering mention of which sits inside it, or at a `run` site that does; a function, define, rule, trick-order row or game-level expression is refused, as is a move type nothing offers, and so is an enclosing phase's own body and hooks, where that phase's frame stands and the innermost one's does not. Phases that do NOT nest are refused outright: a phase's frame is popped when the phase ends, so no place in the game runs both and the entry could never be called anywhere. Declaration-only surface: nothing new is emitted and no information set moves — a scoped name materializes through the same innermost-frame walk as a game-level one, which is correct by construction because a strict descendant of the named phase re-declaring the name is refused at compile.
layer: compiler
status: canonical
reserved: false
home: grammar `primitive_read`, `cardlang/resolve.py` (`_check_read_tail`, `_check_scoped_read_containment`)
see: [reads-clause, primitives-block, primitive, phase]
retired_spellings: []
findings: []
---
