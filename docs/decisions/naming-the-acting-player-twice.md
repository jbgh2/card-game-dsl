## Naming the acting player twice

A construct that binds a seat *and* makes that seat the acting player gives the
same player two names: its own binder, and the `actor` pronoun. Inside such a
body the two are interchangeable, so an equality comparison between them is a
constant — `p is actor` always true, `p is not actor` guarding a body that never
runs. **Both operands naming the acting player is refused at resolve time.**

The rule is about *provable identity*, not about the `for each` spelling, so it
covers every construct that binds the acting player to a name — `for each` over a
seat role (the `binds_actor` column of the domain registry), `turns`, `each …
simultaneously`, and `as <name>` — and the transitive `let me = actor`, which
merely adds a third name for the same seat. Both equality operators and both
operand orders are refused alike, since the degeneracy is in the operands rather
than in the spelling.

Binding is the only thing that grants a name, and it is also the only thing that
takes one away: a name rebound by an inner construct — a query binder, a
`produces:` arm's payload, a `let` assigning it something else — stops denoting
the acting player from that point, and comparing it becomes ordinary again. A
binding's right-hand side is read *before* it takes effect, as everywhere else
in the language, so `let p = p` re-binds `p` to the player it already named and
keeps the comparison refused.

The **innermost** binding is the one that counts, and that is what keeps the
useful idioms legal:

```cardlang-fragment actor_alias
let w = actor
for each player p:
  if p is w { result[p] := 1 } else { result[p] := -1 }
```

Capturing the acting player *above* the loop is the way to compare against them
*inside* it: `w` is bound before the rebind, so it still names the player who
acted while `p` walks the seats. Written inside the loop the same `let` would
name whichever seat the loop had just bound, and the comparison would be refused
along with the direct one. Symmetrically, a nested rebind frees the outer
binder — inside `for each player p: as <someone> { … }`, `actor` is that someone,
so `p is actor` is an ordinary contingent test again.

Two boundaries are deliberate. A **state variable** is never treated as provably
the actor, even directly inside `as taker { … }`: the body may reassign it, so
the comparison can genuinely differ, and the guard refuses only what it can prove.
And a merely **redundant** read is not an error — `hand[actor]` where `hand[p]`
would do is accepted, because it does exactly what it says. The defect being
refused is a comparison whose answer is fixed before the game runs, not a
roundabout way of writing a correct one.
