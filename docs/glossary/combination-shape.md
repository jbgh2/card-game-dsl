---
term: Combination Shape
definition: A [[combination-catalogue]] row's phrase — one part, or two parts over disjoint ranks joined by `with`, then its qualifiers. The parts are a count and a noun (`1 card`, `N cards`, `N of a kind`, `N in sequence`, the last read against the game's [[rank-sequence]]); the qualifiers narrow a single-part row (`, all one suit`, `, not all one suit`, `, not in sequence`). A play's `.shape` is its row's label.
layer: kernel
status: canonical
reserved: false
home: `cardlang/catalogue.py`, `SHAPE_PARTS` / `SHAPE_QUALIFIERS` / `SHAPE_FORMS`
see: ["combination-catalogue", "rank-sequence", "combination", "reject-with-replacement-twin"]
retired_spellings: []
findings: []
---

**Kernel.** The phrase of one [[combination-catalogue]] row. A shape is one part, or two parts joined by `with` over disjoint ranks (`3 of a kind with 2 of a kind`, a full house), then its qualifiers. A part is a count and a noun: `1 card` and `N cards`, any cards; `N of a kind`, cards of one rank; `N in sequence`, cards whose ranks are consecutive places of the game's [[rank-sequence]]. The qualifiers — `, all one suit`, `, not all one suit`, `, not in sequence` — narrow a single-part row. The vocabulary is `catalogue.SHAPE_PARTS`, `SHAPE_QUALIFIERS` and `SHAPE_FORMS`, each pinned to the grammar's aliases.

A count agrees with its noun and names a play the deck holds; a qualifier is said once. Every phrase a growth game needs and the vocabulary lacks is refused by its [[reject-with-replacement-twin]] citing the issue that holds it. The play a row names reads its label as `play.shape`.
