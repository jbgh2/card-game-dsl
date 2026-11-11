## Named procedures

A game factors a *statement sequence* it would otherwise repeat with a **named
procedure** — the statement layer's sibling of the named function above:

```text
procedure <name>(<param> : <type>, …) { <statement>* }
```

declared at the top level, and invoked as a statement: `run <name>(<arg>, …)`.
A keyword leads the invocation, because the statement layer has no
expression-statement form and that absence is worth keeping — statement-hood
stays visible.

Reuse is a **splice**: the expander replaces each `run` with the procedure's body
and consumes the procedure, so no `run` and no `procedure` survives the front end.
This is what makes the construct safe against the invariant that governs everything
here — *the observation events a procedure contributes, and therefore the
information sets derived from them, are exactly what the written text emits*,
because a procedure does not exist at the layer where observations are emitted. It
is the opposite of the retired `instantiate` escape hatch, which injected Python
the kernel could not see; a procedure injects only DSL the kernel already
interprets. Coup is the forcing case: three blocks pasted 29 times, most of a
521-line file, now written once.

A `run f(a, b)` becomes one block:

```text
block {
  let @f.p = a            // each argument evaluated ONCE, in the caller's context
  let @f.q = b
  <the body, reading @f.p and @f.q>
}
```

The block is a real construct in the tree, not an `if true { … }` standing in for
one, and the difference is not cosmetic: an `if` tells every downstream pass that
the body *may be skipped*. The deck-capacity gate believed it — it carries the worst
case across a conditional — so a procedure that refilled the deck failed to reset the
gate's running total, and the very same program was accepted written inline and
rejected written as a `run`. That is precisely the property a procedure exists to
guarantee, so the tree has to say what is true. (The statement layer has no block
form and needs none: nothing but expansion creates one.)

Two properties, and each is load-bearing rather than cosmetic:

**Arguments are evaluated once, by value, before the body runs.** A by-name splice
— copying the argument *expression* to every place the body reads its parameter —
is silently wrong in three ways, and all three are reachable. `run
bump(choose integer in 0 .. 1)` is ONE decision in the written text; by name it
becomes one decision *per read*, polled independently, so two reads can get two
different answers and credit two different players. A parameter read zero times
drops the argument, and its decision, entirely. And an argument naming state the
body then assigns denotes a different value on its second read than its first. The
first of those changes the game's *decision count* relative to what the designer
wrote, which is exactly the thing the OpenSpiel target cannot tolerate. Binding
each argument up front makes a call read the way it looks.

**The body's bindings scope to the body.** That is what the block is for. State
assignments and card transfers persist, of course — a procedure acts on the game.
Only its `let`s are local, which is the whole difference between a procedure and a
paste: without it, a body that binds `target` would silently capture a caller's own
`target`, read *after* the `run` site.

Together these mean the caller cannot corrupt the body and the body cannot corrupt
the caller, *by construction* — so there is no capture guard to remember, and none
to get wrong. One guard does remain, because expansion cannot fix it: a body binder
sharing a **parameter's name** is ambiguous at classification time (both are local
binders), so substitution cannot tell them apart. That is rejected.

Expansion runs **after typecheck**, not beside rule-template instantiation in
resolve. That is forced by the parameter types: they can only bite while the `run`
site still exists to check its arguments against, and expanding earlier would leave
them parsed and ignored — the accepted-but-ignored class.

The body is **hermetic**, in the same sense a function body is: it reads only its
parameters, the binders it introduces, and game/phase state — never the caller's
locals, and never the call-site pronouns `actor` / `action` / `outcome`, so its
meaning cannot depend on where it is run from. A procedure that needs the actor
takes it as a parameter, and because arguments are evaluated in the caller's
context, `run lose_influence(actor)` passes the *move's* actor even into a body
that rebinds the acting player. Coup depends on that at four sites.

Parameter domains are a closed set (`resolve._PROCEDURE_PARAM_DOMAINS`), and
any other domain is rejected. One member is not a value type: a **`Positive`**
parameter takes a whole number of 1 or more, and the `run` passes it as a
written number (`run betting_street(first_actor, 2, 0)`). A computed argument
is refused, not checked at play: expansion binds the argument as a plain `let`
past every check, so a written number is the one form whose membership is
decided before the game runs. The body reads the parameter as an Integer. A
size the rules compute from play is an `Integer` parameter. A procedure may not run another procedure, hold a `round`
(which binds its own `outcome`), or contain non-local control flow (`produce`,
`continue to`, `skip to next hand`), and one that is never run is an error, since
its body would be spliced nowhere and checked by nothing. Every one of those is a
loud guard with a recorded deferral (issue #134); none is silently
accepted.
