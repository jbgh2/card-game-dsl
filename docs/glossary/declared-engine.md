---
term: Declared Engine
definition: A climbing round's engine when its slots name the game's own [[combination-catalogue]] and [[follows-function]] — one arm of the closed union `ClimbRound.engine` resolve stamps (the other is a [[registered-engine]]). It offers a seat the catalogue's plays its hand holds that the function admits, in action-id order with the pass after them, and the action space numbers the catalogue's plays.
layer: kernel
status: canonical
reserved: false
home: `cardlang/ast/nodes.py`, `DeclaredEngine`; `cardlang/runtime/declared.py`, `DeclaredClimbEngine`
see: ["registered-engine", "combination-catalogue", "follows-function", "combination", "play-identity"]
retired_spellings: []
findings: []
---

**Kernel.** A climbing round's engine when its `combinations` slot names the game's [[combination-catalogue]] and its `follows` slot the game's [[follows-function]]. Resolve stamps every climbing round's engine once (`ClimbRound.engine`), as this or a [[registered-engine]], and every later reader dispatches on the stamp, never on the slot names; a round pairing one engine's slot with another's is refused.

At each ask it offers the plays of the seat's hand a row names and the function admits against the standing play, in action-id order, each moving its cards in card-id order, with the pass after them at a follow. Its candidates are generated per row from the hand, never by walking the hand's subsets, and its follows answers are cached for the game on what the function reads (`DeclaredEngine.state_reads`, `zone_reads`, `cacheable`). The action space numbers the catalogue's plays by their [[play-identity]].
