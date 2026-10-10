---
term: Draw Script
definition: The outcomes of a run's first draws, given rather than dealt by the [[shuffle-seed]] — one per draw, as positions in the draw's input (a shuffle's permutation, a random selection's picks). Empty for every state reached from the root chance node; carried by a [[constructed-world]], which no seed deals. Draws past it are the seed's from its first bit.
layer: interop
status: canonical
reserved: false
home: `runtime/chance.py`
see: [constructed-world, shuffle-seed]
retired_spellings: []
findings: []
---

**Interop.** The outcomes of a run's first draws, given rather than dealt by
the [[shuffle-seed]] — one per draw, as positions in the draw's input (a
shuffle's permutation, a random selection's picks). Empty for every state
reached from the root chance node; carried by a [[constructed-world]], which no
seed deals. Draws past it are the seed's from its first bit.
