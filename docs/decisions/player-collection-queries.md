## Player-collection queries

Four expression forms query the player ring by a predicate:

```text
players where <pred>                        // the set of matching players
the player where <pred>                     // the unique matching player (errors if not exactly one)
the first player from <seat> where <pred>   // the ring search: the first satisfying seat of one lap
number of players where <pred>              // how many match
```

The predicate is evaluated once per player with `player` bound to the
candidate, so it reads like the per-player indexing used everywhere else:
`players where not eliminated[player]`, `the player where hand[player] is
not empty`, `number of players where hand[player] is not empty`. The
binder is the fixed name `player` (the canonical seating role), not a
user-chosen variable — these are filters over a single known ring, not
general comprehensions, so there is nothing to name.

Like the quantifier (`any player where …`), aggregation (`sum of … over
… as …`) and integer `choose` forms, a player query sits at the top of the
expression grammar: its `where <pred>` body extends as far right as
possible, giving one canonical parse. To compare a count, parenthesize it:
`(number of players where not eliminated[player]) > 1`.

`the player where <pred>` is the singular selection a `loser:` clause
uses; it is an error at runtime for the predicate to match zero or
several players, since it names exactly one.

**The ring search** scans exactly one lap of the seat ring in the game's
`direction:`, starting AT the named seat — the kernel's own "at or after"
ring-start convention (see "The climbing form of `round`") — and yields the
first seat whose predicate holds: `the first player from leader where
hand[player] is not empty` is Tichu's post-trick lead advance read aloud.
The start is any seat-valued expression, evaluated OUTSIDE the binder
scope; it sits below the query forms in the grammar, so a query used as
the start parenthesizes (`from (the player where …) where …`). The
exclusive variant is spelled by composition — `from dealer offset_by left
where in_hand[player]`, Hold'em's button advance — and because `offset_by`
is a seat direction (absolute), the exclusive spelling composes with the
seat direction that matches the game's turn direction: `offset_by left` in
a clockwise game, `offset_by right` in a counterclockwise one. There is no
default clause and no per-form direction clause; a full lap with no
satisfying seat is a typed runtime error naming the form, exactly as `the
player where` errors off its premise — a game whose ring can legitimately
empty writes the guard it means (`if any player where … { … }`, Tichu's
own post-trick spelling).

`is not empty` is the negation of `is empty` (a zone predicate), paired
for elimination games that select the player who *still* holds cards.
