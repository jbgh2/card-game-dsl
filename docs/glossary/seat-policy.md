---
term: Seat Policy
definition: What answers for one [[seat]] where the game tree has a decision node — handed that seat's [[seat-view]] and the legal OpenSpiel action ids, it answers one of those ids. Its signature is its whole input, so it cannot condition on a card its seat does not see. The sibling of [[playout-policy]] one level up — a Playout Policy is a [[chooser]] resolving [[candidate]]s inside a playout, where a Seat Policy answers with an action id.
layer: interop
status: canonical
reserved: false
home: `seat_policy.py`
see: [seat-view, playout-policy, chooser, game-tree-node-kinds]
retired_spellings: []
findings: []
---

**Interop.** What answers for one [[seat]] where the game tree has a decision
node — handed that seat's [[seat-view]] and the legal OpenSpiel action ids, it
answers one of those ids.

Its signature is its whole input, so it cannot condition on a card its seat
does not see: leak-freeness is a property of the type, as it is of a
rendering's. Every opponent that fills a seat answers through it, and a line of
play replays recorded picks and asks the Seat Policies past them
(`replay.LiveLine`). The uniform opponent (`UniformSeatPolicy`) draws from a
digest of its seed and the view it is handed, so one seed and one history name
one line of play. A perfect-information opponent reads the [[world]], so it is
a type of its own and never this one widened.

It returns an action id, which is why it lives in the Interop package and why
"action id" is in bounds in its vocabulary. A [[playout-policy]] is the level
below: a [[chooser]] resolving [[candidate]] values inside a playout, where a
Seat Policy answers at a decision node in the tree OpenSpiel sees.
