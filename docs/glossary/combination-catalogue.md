---
term: Combination Catalogue
definition: A climbing game's top-level `combinations <name> { <label>: <shape phrase> … }` block — the card multisets a play may be, one row per [[combination-shape]], each labelled. Its plays are derived whole at check time over the game's deck, and two rows naming one multiset, a row naming none, a qualifier removing nothing, a catalogue no round names and one past `catalogue.ENUMERATED_UNIVERSE_BOUND` are each refused. A climbing round names it with its [[follows-function]] and runs on them as its [[declared-engine]]; the action space numbers its plays.
layer: kernel
status: canonical
reserved: false
home: `cardlang/catalogue_pass.py`; `cardlang/runtime/declared.py`, `universe`
see: ["combination", "combination-shape", "rank-sequence", "follows-function", "declared-engine"]
retired_spellings: []
findings: []
---

**Kernel.** A climbing game declares its plays in a top-level `combinations <name> { … }` block: one row per [[combination-shape]], each labelled, the label naming that row's plays and nothing else of the game. The catalogue's plays are every card multiset of the game's deck a row names, derived whole at check time by the catalogue pass (`cardlang/catalogue_pass.py`) over `runtime/declared.py`, the one home of what a row names.

The pass refuses two rows naming one multiset, with the multiset as witness — an overlap is settled in the rows, never by their order, which carries no meaning — a row naming no play of the deck, a qualifier that removes none of its row's plays, a catalogue no climbing round names, one numbering more plays than `catalogue.ENUMERATED_UNIVERSE_BOUND`, and one over a deck holding cards beyond the standard deck's. A catalogue is written in the game's file, never a library's, and a game runs one. A climbing round names it beside its [[follows-function]]; the pair is the round's [[declared-engine]], and the action space numbers the catalogue's plays by their [[play-identity]].
