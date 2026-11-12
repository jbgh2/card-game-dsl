## Loop termination semantics

A `repeat until <pred>` clause on a phase (or `repeat until <pred>`
on a phase-body block) is **continuously evaluated**: the loop
terminates as soon as the predicate becomes true, including
mid-iteration. When the loop terminates mid-iteration, every nested
phase, mechanic instance, and inner loop that was active is
abandoned in turn.

This matches standard activation-record semantics — when an outer
scope exits, every inner scope exits with it — and means most games
get mid-phase termination for free. Cribbage is the canonical case: a
peg-out can occur mid-hand, during pegging or during the show, and the
game stops the instant either score reaches 121 — expressed by an
`if game_over() { skip to next hand }` guard at each scoring point,
which unwinds the active pegging loop and show statements to the
enclosing `phase hand_sequence repeat until (any player where score[player]
>= 121)`, whose predicate then ends the game at the hand boundary.

Games where the termination predicate can change only at iteration
boundaries (Hearts: scoring is end-of-hand only) get the same
semantics; the continuous-evaluation rule degenerates to
"checked at iteration boundary" because that's the only time the
predicate could flip.

A `round`'s optional `early` predicate does provide *trick-level*
termination on game-state-free conditions (Getaway's tochoo ends the
trick the moment a void player plays off-suit). It is not for
game-ending; game-ending is the `repeat until` clause's job.
