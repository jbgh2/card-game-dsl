## Mutation semantics

**Only a declared state variable can be written.** `x := …`, `x += …`, and `rotate x
through […]` all write persistent state, and persistent state is the only thing they
can write. A write target is an ordinary name, resolved exactly like a name in any
other position — so "what may I write to?" is not a separate rule with its own
vocabulary, it is the ordinary answer to "what is this name?", filtered to one
kind. A binder (a `let`, a loop or query binder, a `move_type` or `procedure`
parameter), a zone, a deck value and a pronoun are all *values*, not variables:
readable, passable, not writable. A name that resolves to none of them is unresolved,
which makes the ordinary typo — `totaly_score := 1` — a compile error like any other
misspelling, rather than a runtime one.

**A write fits the shape of what it writes.** `+=` and `-=` add to an Integer; an
`Integer?` reads as its base, and adding to its `none` is refused at play, since what
it holds is a fact of play. An index (`score[p] := …`) writes one value of a variable
kept per seat or team, so a variable holding one value takes no index, and a variable
kept per seat needs one to add to. `rotate` cycles a variable holding one value
through values it can hold. Each mismatch is refused at the write, naming the
spelling that fits: `flag := true` rather than `flag += 1`, and a seat moved with
`p := p offset_by left` rather than `p += 1`.

That uniformity is the point, and it is worth saying why. A **read** resolves lexical
binders *before* state variables. If a write target were not resolved the same way,
a binder shadowing a state variable would make one name mean two things — a read of
`x` finding the binder while `x := 1` wrote the state variable, with nothing to
notice. Resolving the target makes that shape *impossible* rather than merely
detected: the target resolves to the binder, and a binder is not writable. (This is
one seam of a larger question about what a bare name may denote —
[open-questions/name-namespaces.md](../open-questions/name-namespaces.md).)

**Sequential mutation within a phase body.** `:=` (assign) and `+=` /
`-=` (accumulate) statements execute in order. A statement sees the
writes of all earlier statements in the same body. A rule's
`applies_when:` and `demands:` are evaluated against the current
state at the moment the rule is consulted — meaning the rule sees the
writes of every preceding statement in the enclosing phase, plus
mutations triggered by intervening moves. No transactional isolation,
no copy-on-write, no implicit ordering tricks.

**Scoring writes are ordinary sequential writes.** A scoring phase is
statements like any other: a contract's arithmetic, then a threshold test on
what it wrote, then the bonus the test earns. Bridge's game bonus is an `if`
on `below_current[dteam] >= 100` in sequence after the contract score, its
coupled reset is one assignment per team, and its rubber bonus is a nested
`if` on `games_won` — all in `docs/games/bridge.cardlang`. There is no
batched scoring mode ("Scoring has no constructs of its own"); the language's
one batched-write context is the simultaneous block ("Simultaneous moves and
atomic effect"), whose reads see pre-block state for a reason of its own.

**Event-driven sub-phase transitions are not a third mutation mode.**
Hearts' `transition_to: hearts_broken when play_to_trick where
action.card.suit is hearts` is *phase entry/exit* triggered by the
move-emitted event.
The implied state change (the `NoLeadingSuitUntilBroken(hearts)` rule
becomes inactive) happens because the active rule set changes when
the phase changes, not because a `hearts_broken` boolean was written.

**Bulk write syntax.** Setup phases regularly do `tricks_won := 0 for
each team and player`. Generalized form: `var := initial for each
index`. The single-cell write `score := 0` and the indexed form
`score[t] := 0 for each team t` desugar to the same loop.

**Coupled resets and modulus accumulation are explicit statements.**
Bridge's "below-line resets for both sides when either side wins a game" is
two assignments, one per team, inside the game-bonus branch. Spades'
bags-modulus reset is a `repeat until (all teams where bags[team] < 10)`
around a per-team `if`. There is no language-level "coupled variables" or
"wrapping accumulator" construct; the explicit statements read correctly.

**Phase-outcome destructuring** (Bridge's `bidding produces:
contract_made(c, d): contract := c; declarer := d; ...`) is just
ordinary sequential assignment — the destructuring binds locals; the
assignments are imperative writes following the same rules.
