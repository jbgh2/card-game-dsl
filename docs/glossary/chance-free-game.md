---
term: Chance-Free Game
definition: A [[game]] that consumes no randomness: nothing in its text shuffles a zone or selects at random, so its whole trajectory is a function of the actions taken. Derived from the checked tree by `runtime.chance.chance_sites`, which names every drawing site and refuses a construct its tables do not know rather than reading it as non-drawing. The claim is guarded at run time by a generator that refuses every draw, and the OpenSpiel tree of such a game carries no root chance node — see [[game-tree-node-kinds]], [[shuffle-seed]].
layer: kernel
status: canonical
reserved: false
home: `runtime.chance`
see: [Game Tree Node Kinds, Shuffle Seed]
retired_spellings: []
findings: []
---

**Kernel.** A [[game]] that consumes no randomness: nothing in its text
shuffles a zone or selects at random, so its whole trajectory is a function of
the actions taken. Derived from the checked tree by
`runtime.chance.chance_sites`, which names every drawing site and refuses a
construct its tables do not know rather than reading it as non-drawing. The
claim is guarded at run time by a generator that refuses every draw, and the
OpenSpiel tree of such a game carries no root chance node — see
[[game-tree-node-kinds]], [[shuffle-seed]].
