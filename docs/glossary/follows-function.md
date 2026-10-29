---
term: Follows Function
definition: The game function a climbing round names in its `follows` slot beside its [[combination-catalogue]] — `(play : Combination, standing : Combination?) -> Boolean`, saying whether a play a hand holds may be played over the standing play (`none` at a lead, where it says what may lead). An ordinary DSL function, judged by the Hidden Read Owner Guard at the asked seat, and cached by its [[declared-engine]] on the plays' cards and the values of everything it reads.
layer: kernel
status: canonical
reserved: false
home: `cardlang/runtime/declared.py`, `DeclaredClimbEngine`
see: ["combination", "combination-catalogue", "declared-engine", "honest-play"]
retired_spellings: []
findings: []
---

**Kernel.** The function a climbing round names in its `follows` slot beside its [[combination-catalogue]]. Its signature is `(play : Combination, standing : Combination?) -> Boolean`: a seat is offered every play of its hand the catalogue names and the function admits against the play standing in the trick, then the pass. At a lead `standing` is `none` and the function says what may lead; a lead offers no pass, so one at which it admits no play of the hand is a loud error.

It is an ordinary DSL function. Its reads are judged by the Hidden Read Owner Guard at the asked seat, so the offered list is a function of that seat's hand and what every seat sees. Resolve stamps on the round's [[declared-engine]] every state variable and zone it reads through the functions it calls, and the engine caches its answers for the game on the two plays' cards and those reads' values; a function reading a pronoun, round state or a declared Primitive's `reads` runs uncached.
