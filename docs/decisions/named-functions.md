## Named functions

A game factors an expression it would otherwise repeat with a **named function** —
a parameterized expression callable wherever an expression appears:

```text
function <name>(<param> : <type>, …) = <expr>
```

declared at the top level alongside the `move_type`s. A call `<name>(<arg>, …)`
evaluates the body with the parameters bound to the arguments. Seven-Card Stud's
betting ring uses three: `can_act(p)` (not folded, still holds chips), `owes(p)`
(still owes the standing bet), and `pending(p) = can_act(p) and (not acted[p] or
owes(p))` (the ring/termination predicate). The `over` filter and the `until`
terminator both name `pending(player)`, so they cannot drift out of step — a
correctness property, not only brevity.

`acted[p]` is the turn taken *within* the round, and **a forced post placed
before the round begins is not one: the posting seat stays pending until it
acts.** Hold'em's big blind and Stud's bring-in poster match the standing bet
without having spoken, so `pending`'s `not acted[p]` arm is what keeps them in
the ring — keyed on debt alone it would deal the hand out around a live seat.
The same reading decides which moves are legal and not only who is asked:
`poker_betting`'s `raise` is offered against a standing bet only to a seat that
has not taken a turn since a full wager last re-opened the betting, which is
Pagat's option for the big blind — *"The big blind player acts last, and may
raise even if no one else has done any more than call."* Stud's bring-in poster
holds no such later right: its post is short of a full bet, it takes the
street's first decision, and called around nothing re-opens the betting to it —
Pagat, *"Only if someone completes the bet are later players allowed to
raise."*

The body is **hermetic**: it reads only its parameters and game/phase state (read
at call time), never the caller's local binders or call-site `actor` / `action` /
`outcome`. A function that needs a player takes it as a parameter. It is
**non-recursive** — the call graph must be acyclic. Both are enforced at compile
time, with the ordinary checks: a call to an unknown function, a wrong argument
count or type, a body name that is neither a parameter nor a binding the body
itself introduces (`number of players where …`), and a call cycle are each a loud
error. The body's type is inferred — a function whose body is a `Player` used
where a `Boolean` is expected is caught at the call site — and a function may call
another (`pending` calls `can_act` and `owes`).

A function's name is its own. It may not take a native function's name — a call
would type-check against the native signature and run the function instead — nor
the name of a native callback one of the game's round slots names (`winner`,
`early`, or a registered engine's `combinations` / `follows` query), since that
slot always runs the language's own and never calls a function. A climbing
round's `follows` slot names a game function where it names a catalogue
beside it ("Combination Catalogues"). Both are refused at the definition. A family library cannot know which
game's rounds will name a slot callback, so its functions and its `requires`
function rows may take no slot callback's name at all.

Four names are the game's to take: `is_trump`, `follow_class`,
`card_strength` and `card_points` are Kernel Definition Contracts ("Trick
Order"), and a game function by one of those names answers the contract,
typed against the kernel's row. A family library may not define one; it
writes the contract's row in its `requires` instead.

This is a deliberate, authorized general construct: factoring predicates is a need
the corpus has as games grow more advanced, not a Stud-only convenience. It
resolves the *named-predicate* half of
[open-questions/round-config-factoring.md](../open-questions/round-config-factoring.md);
the *street-loop* half (folding a repeated parameterized `round` block into one
loop) remains open.
