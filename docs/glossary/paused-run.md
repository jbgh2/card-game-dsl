---
term: Paused Run
definition: A line of play held at a decision, so the adapter's next pick on that line advances it instead of replaying the history from the first pick. A bounded pool keeps a few per OS thread; a run is consumed when it is advanced and is never read once it has moved on, and every query it answers is the one the replay of the same history answers. Never the state: an OpenSpiel state stays `(seed, script, history)` — see [[shuffle-seed]], [[game-tree-node-kinds]].
layer: interop
status: canonical
reserved: false
home: `paused.py`
see: [Shuffle Seed, Game Tree Node Kinds]
retired_spellings: []
findings: []
---

**Interop.** A line of play held at a decision, so the adapter's next pick on
that line advances it instead of replaying the history from the first pick. A
bounded pool keeps a few per OS thread; a run is consumed when it is advanced
and is never read once it has moved on, and every query it answers is the one
the replay of the same history answers. Never the state: an OpenSpiel state
stays `(seed, script, history)` — see [[shuffle-seed]],
[[game-tree-node-kinds]].
