## Move, Transfer, and what `move_type` is called

A **Move** is one played instance of a Move Type bound to its Parameters; a
**Transfer** is one relocation between zones. They are independent, and the
trick game hid that by making them coincide: a card play is one of each. A
capture is one Move and two Transfers, a pass is one Move and none, and setup
is Transfers with no Move at all — so a single fused word cannot describe a
board game. The cardinality table is in [model.md](../model.md), "Moves and
Transfers".

The keyword stays **`move_type`**. With "move" owning the player-action family
it reads as compositional English, and `action_type` would manufacture a false
friend against the Interop sense of "action" — the translation to OpenSpiel
stays one-directional, which is what keeps `action` usable as the scoped
pronoun for the candidate Move under consideration.

The surface verb `move` also stays, and is deliberately not the engine word for
a Transfer: in solitaire the verb and the Move genuinely coincide, and the
surface reads like the rulebook. The engine word is Transfer; its verbs
(`deal`/`draw`/`move`) are sugar over the one primitive, and a future board
family mints its own (`place`, `capture`) as registry rows rather than as new
syntax.

**A move type is played only where it is offered.** A game's own move type
that no reachable `offer` presents is refused: no seat can ever play it, so
it is a declaration nothing reads. A game importing a library need not
present every move type the library defines. A move type the library
contracts for (`requires { fold : Move }`) is the game's own and is held to
the same rule: the library's offer of it reaches the game only where the
game runs the procedure holding it, so a game that defines it and runs no
such procedure is refused like any other.
