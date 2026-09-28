---
term: Stake
definition: What a [[move-type]] declares that taking it risks — the optional row under its name, one of [[wager]] or [[concession]]; a move type with no row is plain. Static game text read by a [[seat-policy]] from the checked game, never by the runtime, the encoding or an information state. A rules fact, never play advice.
layer: kernel
status: canonical
reserved: false
home: `n.MoveTypeDef.stake`, `n.STAKES`
see: [move-type, wager, concession]
retired_spellings: []
findings: []
---

The row stands under the move's name and before its `when:`, because it says
what the move is rather than when it is legal (decisions.md, "A move type's
stake"). It lives on the move, not at the [[offering]] that presents it: the
same move stakes the same thing at every site it is offered from.

The row never states an amount. What a Wager is worth is computed by the
scoring that settles it, the one place the amount lives.
