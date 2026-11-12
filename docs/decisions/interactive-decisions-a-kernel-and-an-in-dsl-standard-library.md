## Interactive decisions: a kernel and an in-DSL standard library

The structure of a game (zones, phases, dealing), trick-taking, and scoring are
directly expressible. The part that resists expression is **interactive decision
logic** — heterogeneous action choice, auctions, betting, challenge/block
windows, combination climbing. These are factored into one semantic primitive
and a small surface, with the richer vocabulary built *in the language* rather
than baked into the engine.

**One primitive: the decision node.** A participant chooses one action from a set
that is *finitely enumerable from current state*, over a move-type vocabulary
fixed at game-definition time; the action has an effect and may yield a typed
outcome. Plus chance nodes for shuffles/deals. Everything below lowers to this.

**The engine's only chance is the shuffle and the random selection.** Both are
named in `runtime/chance.py`. Where a rulebook has a seat choose — a challenge,
a call, a routing, a target — the game offers that choice as a decision node,
so the information state carries it as an announced decision rather than
hiding it in a chance outcome. A mechanic that draws from the World's generator
in place of a seat's decision is a spec regression, never a scope note, and
review refuses it. Review is the refuser by design: no checker can read the
rulebook, so none can tell a seat's choice written as a `random` selection
from the chance the rules themselves call for.

**Two surface constructs.**

- `offer` — a single decision: an acting player chooses one of a set of
  `move_type`s (each a guard plus an effect), and the chosen move's effect runs
  with `actor` bound to that player.
- `turns` — a ring of seats, each taking one turn: a participants predicate
  re-evaluated per turn, a termination predicate checked at every boundary,
  and a body. A ring whose turn is one `offer` is every auction, betting
  street and response window ("Auctions, polls and betting rings are `turns`
  plus `offer`").
- `round` — a sequence of card plays over participants, varying only along a
  *closed* set of axes: participants, order, an accumulator threaded across
  steps, and a termination predicate. The trick and the climb are its two
  forms.

**Richer vocabulary is a standard library written in the DSL, not engine
presets.** `challenge`, `block`, `auction`, `climb`, and `trick` are *definitions*
composed from `offer`/`round` and the effect verbs — readable in the game's own
terms rather than hidden behind keywords. The governing rule: **a definition adds
words, not semantics.** It may name and compose over the fixed kernel (a typed
function: parameters in, typed outcome out, a body that lowers to decision/chance
nodes); it may not introduce new control primitives, reflection, or runtime
rule-mutation. This is the line between a game that *defines* "challenge" (Coup)
and one that mutates its own rules at runtime (Mao), the latter being out of
scope (below).

**Discipline.** Variation lives in *values* along the closed axes (a new bid
step, a different threshold) — never in new constructs. A new *axis* is a major
change requiring sign-off. A definition is promoted from game-local to the shared
DSL standard library only once roughly three corpus games exhibit the same shape
(corpus-first; abstract at the third instance, not the first).

**Anchored to a finite action space.** The "finitely enumerable from current
state, fixed vocabulary" requirement is inherited from the target runtime
(OpenSpiel mandates a finite, enumerable action space), not chosen for
convenience. It is the load-bearing invariant of the whole approach, and it puts
games needing a *runtime-extensible* action vocabulary or mutable rules (Mao,
Nomic, CCG card-text) out of scope by construction rather than by preference.

The kernel's atom (`offer`, parameterized `move_type` definitions, the `actor`
pronoun) and the `round` construct are built. Every trick game (Hearts, Spades,
Getaway, Bridge, Oh Hell) plays on the trick form of the kernel `round`, the
built-in `Trick` mechanic has been retired, and `round` carries the termination
axis (an `early` predicate — Getaway's tochoo) plus round-state exposure. Every
auction, poll and betting ring is `turns` with an `offer` body (see "Auctions,
polls and betting rings are `turns` plus `offer`"): Bridge's, Pinochle's and
Tarot's auctions (Tarot counterclockwise, the ring honouring the game's
`direction`), the poker family's streets through the family library's
`betting_street`, and Skat's Reizen call-and-response as a role-guarded
two-participant ring. The participants predicate is re-evaluated each turn, so
a ring shrinks as players drop out (Pinochle's passed bidders and standing high
bidder, Tarot's seats dropping after one bid). The remaining work (the challenge /
block vocabulary; promoting the shared `auction` definition
at its third instance) is the in-flight build (see issue #140 and
[kernel-migration.md](../kernel-migration.md)).
