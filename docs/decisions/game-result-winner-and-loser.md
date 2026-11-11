## Game result: `winner:` and `loser:`

A game declares its terminal result with exactly one top-level clause,
evaluated against the final state when the phase tree finishes:

```cardlang-fragment winner_loser
winner: lowest cumulative_score      // Hearts — rank a score variable
loser:  the player where hand[player] is not empty   // Getaway — select directly
```

The two forms reflect two shapes of game. A *scored* game accumulates a
score each member holds and the result is whoever ranks first by it, so
`winner: <lowest|highest> <score-var>` names the rank direction and the
variable. The variable it names is a game-level `state` declaration
indexed by player or by team (`cumulative_score[player]`) and declared
`Integer` or `Boolean` — a per-member value is what there is to rank, and
those values are what the game hands OpenSpiel as its returns. A
`Boolean` target ranks `true` above `false`, so a game decided by a flag
ranks on it directly (`winner: highest alive`). A target that is scalar,
optional, or of any other declared type is refused at check time with a
diagnostic naming the declaration: an unindexed one has no per-member
value, an optional one may hold `none`, and the rest either cannot be
compared or compare fine and mean nothing (a `Player`-typed target would
deliver seat ids as utilities). The variable is never named for a word a game
clause opens with (`pieces`, `phase`, `at`): the name ends the clause, so a
ranking whose name is left off would otherwise read the next clause's word as
its target; the refusal says to rename the variable. See
[Winner](../glossary/winner.md).

An *elimination* game has no score: players drop out until one
remains, and that survivor is named directly, so `loser: <selection>`
takes a player-valued expression (typically the singular player-selection
`the player where <pred>`) evaluated at game end. It seats at least two
players: a one-seat table's only player is its loser, with nobody left to
win, so `loser:` beside `players: 1` is refused at check time.

`loser:` reads zone state (`hand[player]` non-empty), not phase-scoped
variables, so it resolves at the top level after the elimination phase
has exited. The value it selects must be a seat of the table: anything
else -- a seat number off the table, a Boolean, a card -- is refused when
the game ends, so an elimination game's returns always sum to zero.

A game declares one or the other, never both. `winner:` is not sugar for
`loser:` of the complement: an elimination game may end with several
non-losers whom the rules never rank, so there is no single winner to
name.

**A game may declare its Stop Result; a game that declares nothing is a
tie.** The Stop Result is what a game is worth when the engine stops it at
its bound, a Length Stop ("Game length as a declared contract"), written
beside the bound it qualifies:

```cardlang-fragment stop_result
max_length: 500
at max_length: as it stands      // Coup: `winner: highest alive`, read where the game stopped
```

It has three members: `at max_length: tie`, every seat a winner and every
return 0; `at max_length: as it stands`, the `winner:` clause read at the
stopped position; and `at max_length: highest <variable>` (or `lowest`), a
ranking of a state variable in `winner:`'s own shape. `as it stands` reads the game's `winner:` clause at the stopped position, so
it is refused on a game whose result is `loser:`: an elimination cut short has
not decided its loser, and its selection would name nobody, several seats, or
the wrong one. A ranking takes the target `winner:` takes, refused at check
time on the same terms and in words addressed to the clause, and it may rank
a game whose result is `loser:`, whose stopped result then carries scores and
ranked returns as a `winner:` game's does. A phase's variable is refused as a
ranking's target at either clause: a `winner:` is decided once every phase has
exited, and the bound can stop a game while the declaring phase still runs. A
game's Stop Result matches its written rules where they give a basis for a
standing -- Coup's exiled have lost by the rules, and Tichu's race is measured
by its score, so both stand as they stand -- and is the tie otherwise: an
elimination cut short has no loser, so Getaway declares none. See
[Stop Result](../glossary/stop-result.md).

**The result names a set of winning seats.** A finished game reports its
winners as the set of seats sharing the best score: every seat that ranks
first by the `winner:` target, read once per seat -- its own score for a
target indexed by player, its team's for one indexed by team. So a
team-scored game names both partners of the winning side, a tie names
every tied seat, and a drawn game names every seat. The set is never
empty, and it is exactly the seats OpenSpiel pays the best return, because
the returns are the same per-seat scores. An elimination game's winners
are every seat but the one `loser:` selected -- a reading of the result,
not a ranking of the survivors and not a second declaration. A `winner:`
game also carries its final scores; a `loser:` game carries none, and
names its loser.
