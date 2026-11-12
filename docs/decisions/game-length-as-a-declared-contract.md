## Game length as a declared contract

Every game declares `max_length: <n>`, a positive bound on the number of
picks a run makes. A pick is one decision in the game tree: an `offer`'s
move, a `choose`, one card of a chosen movement, one play in a round. That is
OpenSpiel's own unit for a game's length, the decision nodes a line visits,
and the adapter advertises the declared number as `max_game_length`.
`max_length` is required, not defaulted: the resolver rejects a game with no
declaration, or with a non-positive one, as a diagnostic error before anything
runs, because how long a game can legitimately run is a question its author
answers on purpose.

**A game that reaches its bound ends there: a Length Stop.** Every pick is
counted once, where it is recorded (`chooser.decide`, the one route from a
decision site to the Chooser), and a pick is admitted only while the count is
below `max_length`. The pick that would exceed it ends the game before it is
asked. So a run that stops has made exactly `max_length` picks on every route:
a multi-pick call the bound cuts short is the same length whether its Chooser
answers all its picks at once or one at a time, and applies none of them,
because a decision site applies a call only once every pick is in. The game is
read at the position standing at the stopped pick: no statement past it runs,
no `after_each`, and every phase frame stands.

**A stopped game is scored by its Stop Result**, the game clause written
beside its bound ("Game result: `winner:` and `loser:`"), and a game that
declares none is a **tie**: every seat a winner, no loser, every seat's return
0. The `loser:` selection is never read at the stop: a stopped position is one
no rule ended, and a selection asked there would name a seat nobody's play
made the loser. A ranking read at the stop reads its target from the
game-level frame, the one declaration a result clause may name, so a phase
frame standing at the stop and shadowing it is never read.

The result says how the game ended, in every channel. `GameResult.ended_by` is
a closed pair, `rules` or `length`; the adapter's terminal node and a live
line's end carry the same field, a registered game's pyspiel State answers it
at a terminal (`ended_by()`, since the returns alone cannot tell the bound's
tie from one the rules declared), the playtest report counts length stops
apart and credits no seat a finish for one, and the readiness battery's
coverage record carries it beside `terminal`. `cardlang demo` leads its summary with the stop,
in the uniform-random voice, and exits 1: the sizing rule below says
uniform-random play ends by the rules, so the game file is where to look. `cardlang play` says the game is over, names the stop in the table's
voice with who chose for each seat, and exits 0: the people at the table
played it there, and the game finished.

**A loop that makes no picks is still refused.** The four loops whose
`until` can fail to hold -- the phase-level `repeat until`, the
statement-level `repeat until`, the `turns` ring, and a climbing round's ring
-- each count, at their head once the `until` has been read false, the bodies
they have completed with no pick made in them, starting again whenever a body
makes a pick; past `max_length` such bodies they refuse, as the author's
defect (`OwnerGuardError`) and in words naming the loop and how many bodies it
completed. A loop whose `until` holds after its last body is never refused,
however many bodies it ran. A loop that makes picks cannot be refused for
running long: its picks reach the bound first. The decisionless loop
(`repeat until false {}`) is the shape no pick count sees, and nothing else
bounds it; the four loops are the closed set of sites of the one guard that
counts them (`state.SpinSite`), each a row of `tests/test_length_stop.py`'s
grid.

**The adapter's length is a promise every registered game keeps.**
`is_terminal()` holds after at most `max_length` non-chance actions on every
line, every non-terminal state has a legal action, and a recorded history
longer than the line it replays is refused as a `HistoryMismatch` addressed to
whoever supplied it.

**The stop is common knowledge.** It is a function of how many picks the line
has made, and every pick a call applies reaches every seat: an `offer`'s move
and a `choose` are announced to every seat, a round's plays are announced or
land in a pile every seat sees, and a chosen movement reaches every seat that
sees either side of it. A chosen movement's source is a zone its decider can
see ("Knowledge, visibility, and the projection model"), and every zone type
that shows its owner identity shows every other seat at least a count
(`tests/test_zone_projections.py`), so no applied pick is invisible to a
bystander. The picks of a call not yet applied reach only their decider, and
no other seat decides until the call is done: a call the stop cuts short
reaches only its decider and ends the game, so no seat is ever asked without
knowing the count.
The stop emits no event of its own, and information sets do not move: two
worlds a seat cannot tell apart reach the stop together, which the swap
proof's terminal assertion (`harness.replay_pair`) holds.

**Corpus values are sized under the game's reference playout policy**, uniform
random unless the game's twin names another, from measured playouts: a
per-game number generous enough that the policy's lines, the long tail of
multi-hand, score-race and elimination games included, never approach it,
while far tighter than one constant sized for the corpus's longest game.
A **rules-bounded game** is the exception: its `max_length` is a fact of its
rules rather than a measured allowance. Hex places one stone per pick on 121
cells and always has a winner when the board fills, so 121 bounds every line,
and a line that fills the board ends by its rules exactly at it. Such a game
declares that fact as its bound, and its lines end by their rules at or
before it. Because reaching the bound is an end rather than a refusal, what
tells a looping `until` in a corpus game from a long one is that measurement,
made a pin: every registered game, on every seed of the coverage manifest,
ends by its rules under its reference policy, with headroom under its bound,
or at or before it for a rules-bounded game, where the pin checks `ended_by`
alone (`tests/test_length_registry_pin.py`). A game whose rules let a table play on
without end -- Coup when every seat takes the first pick, Tichu under a uniform
draw -- meets its bound on those lines, and the pin asserts them as Length
Stops.

A per-game declaration that a game's lines are legally unbounded, switching
the bound from a refusal to an end, is rejected: the engine cannot check it
(non-termination is undecidable), so a designer could write it to silence a
looping `until`, and the registry pin makes the same distinction as a
measurement. A turn cap written into a game whose published rules have none is
rejected too: it states a rule nobody plays ("The game does not bend to the
harness"), and a turn costs more than one pick, so it never fires before the
bound. A draw rule the published rules do state is a counter in `state` read
by the loop's `until`, and ends the game by its rules.

`max_length` is the bound the engine stops a game at, not a value a rule can
read: a rule naming it is refused with the two spellings a designer means -- a
turn count in a state variable compared to a number, or the Stop Result. The
declaration takes a number and nothing more; a clause after it is a syntax
error that names the Stop Result.

Static bounds derived from a game's own structure (e.g. card-conservation
arguments for trick-taking games) could tighten the declared value further,
checked against it; no game requires one.
