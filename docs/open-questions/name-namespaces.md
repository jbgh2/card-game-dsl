# One spelling, several namespaces: what a bare name means

**Tier 2 — high impact, blocked on a design decision rather than a data point.**
Not urgent (every known instance is now walled), but it is the shared root of
several defects that each looked local when found, and it will keep generating
them.

## The situation

A bare `NAME` in this language can denote any of six things:

| namespace | example | where it lives at runtime |
|---|---|---|
| a lexical binder | `let g = …`, `for each player p`, a `move_type` / `procedure` parameter | `ctx.locals` |
| a state variable | `state { turn : Player = 0 }` | `rs.frames` (persistent) |
| a zone | `hand`, `deck` | `rs.zones` |
| a deck value | `hearts`, `Q` | its own string |
| a pronoun | `actor`, `state`, `outcome` | the call-site `Ctx` |
| a function | `pending`, a stdlib name | the function index |

`resolve._classify` picks between them **by precedence** — binders first, then
state variables, then zones, then values, then pronouns. Nothing in the surface
distinguishes them, so shadowing is silent by construction: a `let hearts = …`
shadows the deck value, a parameter named `turn` shadows the state variable, and
the program still reads perfectly.

decisions.md blesses part of this deliberately ("Reserved words and shadowing":
`card` and `player` are established lexical shadow idioms, always scoped strictly
narrower than an outer declaration). The question is whether the *general* case
should be, and what the surface should do about it.

## Why it is a question and not a bug

Every defect below was reported as its own thing. They are one thing.

- **Reads and writes disagreed.** A read resolved binders before state variables;
  a write went to state *regardless*. So `let turn = …` followed by `turn := 1`
  wrote the state variable while every `turn` around it meant the binder — one
  name, two things, silently. **Closed**: a write target is a `NameRef` now, so it
  classifies like a read, and "a binder is not assignable" is one rule
  (decisions.md "Mutation semantics").
- **The round's state was a second store under the same spelling.** `state.led_suit`
  (the round frame) and a phase-declared `state { led_suit }` are two disjoint
  stores separated by one dot, and a form's *private working memory* was reachable
  through the first — `state.idx` type-checked, ran, and silently changed the game.
  **Closed**: a round publishes a declared, typed field set and the checker rejects
  the rest (`cardlang/stdlib/round_state.py`).
- **Substitution could only see half the names.** `substitute` matches `NameRef`s,
  and several name-bearing AST fields were bare strings — so procedure expansion
  rewrote reads of a parameter and left writes of the same name pointing at a
  global. **Closed** for the two scope-participating fields; the rest are registry
  keys (`Call.func`, `Produces.define`, `Round`'s zones) which cannot be shadowed.

Each fix is a wall around a *consequence*. None of them changes the thing that
produces the consequences: one syntactic form, six namespaces, precedence rules
instead of distinctions.

## The question

**Should shadowing across namespaces be legal at all, and should the surface say
which namespace a name is in?**

Three coherent answers, and the corpus does not yet force one:

- **Keep precedence, wall each seam as it appears.** What we have. Cheap, and each
  wall is individually defensible — but the seams are found by defect, not by
  enumeration, and the walls accumulate. It also leaves a real asymmetry standing:
  a parameter may *shadow* a state variable for reads (legal) while an assignment
  to it is rejected (illegal), which is coherent but not obviously *intended*.
- **Forbid cross-namespace shadowing.** A binder may not take the name of a state
  variable, a zone, or a deck value. One rule, checkable in `_rewrite` where the
  scope is already known, and it makes the precedence order unobservable — which is
  the real prize, since a precedence order nobody can observe is a precedence order
  nobody can get wrong. Cost: it would reject programs that read fine today, and it
  has to carve out the `card` / `player` idioms decisions.md already blesses.
- **Distinguish in the surface.** A sigil or a keyword for persistent state
  (`$turn`, or `state.turn` uniformly, which would also fold in the round-state
  seam above). Most honest, most invasive, and the biggest change to how every
  game file reads — which is a real cost in a language whose acceptance test is
  "a non-player can read a game file cold".

## What would settle it

A corpus game that *wants* to shadow — where the natural name for a binder is
also the natural name for a state variable — would argue for keeping precedence.
Nothing in the current 18 does; every shadow found so far has been a defect. A
second seam appearing (a third store, or a construct that needs to rewrite names
and hits the same blindness) would argue for the surface distinction.

Related: [decisions.md](../decisions.md) "Mutation semantics" (what a write target
may be), "Round-internal state lives inside the round" (the published-field
registry), "Reserved words and shadowing" (the blessed `card` / `player` idioms);
[round-state-in-information-states](round-state-in-information-states.md) (the same
seam, seen from the encoding side).
