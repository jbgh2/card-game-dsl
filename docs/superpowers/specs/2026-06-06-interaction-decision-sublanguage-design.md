# Interaction-decision sublanguage — design

**Date:** 2026-06-06
**Status:** Approved design; ready for implementation planning.
**Scope:** A sublanguage for expressing players' *decisions and their resolution*
(actions, bidding, betting, challenges, blocks, climbing) in the DSL itself,
replacing the per-game Python mechanics that currently hold that logic.

> Syntax in this document is **illustrative**. The concrete surface grammar is
> finalized during implementation planning; what is fixed here is the
> architecture, the constraints, and the discipline.

## 1. Problem

The corpus is meant to be the living embodiment of the spec — a reader plays the
game from the `.cardlang` file. For trick-taking + scoring that holds. But the
*interactive decision logic* of nine of thirteen games lives in concrete Python
mechanics (`SchnapsenHand`, `PinochleHand`, `BridgeAuction`, `SkatHand`,
`TarotHand`, `CribbageHand`, `StudHand`, `TichuHand`, `CoupGame`), with the
`.cardlang` reduced to scaffolding plus `instantiate XxxHand()`. For those games
the machine-checkable file does **not** describe the rules; the prose `.md`
does, and the static checker — the project's forcing function — covers none of
where the real complexity lives.

The decision logic across all nine collapses into four recurring shapes:
1. **Single in-turn choice** among heterogeneous moves → typed outcome (Coup
   turn, Schnapsen lead, contract declaration).
2. **Sequential round** around participants that reads prior choices, accumulates
   round-state, and ends on a predicate (auctions, Stud betting, Cribbage
   pegging, Tichu climbing).
3. **Response windows** — offer a reaction to the *other* players, first commit
   binds, typed outcome branches the original action (Coup challenge/block,
   Bridge double, foreign-aid block).
4. **Call-and-response** (two-party) — Skat's Reizen; a degenerate case of (2).

Shapes (3) and (4) are (2) with different parameter values, so the irreducible
core is two things: a single decision, and a sequence of decisions.

## 2. Goals, ranking, non-goals

Drivers, in priority order (user-ranked):
1. **Fidelity** — the `.cardlang` fully and readably describes the game; no Python
   delegation; a reader understands it without knowing hidden engine semantics.
2. **Checkability** — the static checker analyzes the decision logic (typed
   outcomes handled exhaustively, statically-resolvable legal sets, resolved
   references).
3. **IR / OpenSpiel** — the decision logic lives in the serializable IR and drives
   OpenSpiel as information-set decision nodes.

(3) is treated as a **hard gate, not a soft optimization**: if a fidelity or
checkability choice cannot lower to an OpenSpiel-drivable decision tree, back up
and rework it.

**Non-goals / out of scope (by construction — see §3):** games with a
runtime-extensible action vocabulary or mutable rules — Mao, Nomic, Fluxx,
CCG card-text (Magic/Yu-Gi-Oh!/etc.). Free-form binding negotiation. Continuous
or very large action spaces (no-limit bet sizing) without action abstraction —
deferred, not part of this design.

## 3. Invariant #0 — the OpenSpiel anchor

> Every decision is a choice from a set that is **finitely enumerable from
> current state**, drawn from a **move-type vocabulary fixed at
> game-definition time** (instances may carry state-dependent typed parameters
> and be generated from a fixed grammar). Rule *activations* (forced-coup, the
> Mahjong wish, follow-suit) are state-driven selections from a fixed rule set;
> they constrain the legal set, they do not extend the vocabulary.

This is not a convenience of the sublanguage — OpenSpiel **requires** a finite,
enumerable action space (`NumDistinctActions`). So the constraint is inherited
from the target. Any game needing a runtime-extensible vocabulary or mutable
rules cannot be an OpenSpiel game without a meta-representation layer, and is
therefore out of scope necessarily, not by preference. The IR gate of §2
auto-enforces this boundary.

## 4. Architecture — three layers

1. **Kernel** (fixed, engine-level, lowers to OpenSpiel): the irreducible
   primitives. Small and closed. §5.
2. **Interaction vocabulary** (written *in* the kernel, in the DSL —
   game-local, promoted to a shared stdlib by the §7 rule): `lose_influence`,
   `challenge`, `block`, `trick`, `auction`, `betting_round`, `climb`. Readable
   definitions, not engine magic.
3. **The game**: composes the vocabulary; reads like the rulebook because the
   words are the game's words.

Everything in layers 2 and 3 lowers to the layer-1 decision node (+ chance
nodes). The engine surface never grows; richness is library code in the
language.

## 5. The kernel (fixed primitives)

The one semantic primitive is the **decision node**: a participant chooses one
action from a statically-enumerable legal set; the action has an effect; it may
yield a typed outcome. Plus **chance nodes** for shuffles/deals. The kernel
exposes:

- **`offer`** — one decision. A participant chooses one of a set of move-types
  (filtered to legal instances by the rules engine); the chosen move's effect
  runs; an outcome value may be produced. (Shape ①.)
- **`round`** — a sequence of decisions over participants. (Shape ②, and ③/④ as
  parameterizations.) Varies only along a **closed axis set**:
  1. **participants** ∈ {actor, others, ring, explicit-list}
  2. **order** ∈ {turn-from ⟨seat⟩, priority, simultaneous}
  3. **accumulator** — typed round-state threaded across steps
  4. **termination** ∈ {all-but-one-pass, N-consecutive-pass, first-commit,
     predicate, exhausted}
  5. **outcome** — the typed value produced
  A new *value* in an axis is a parameter (free). A new *axis* is a major change
  requiring sign-off (it means a genuinely new interaction topology none of the
  thirteen games had).
- **Effect verbs** — the existing statement vocabulary (`transfer`/`move`/
  `deal`/`reveal`/`shuffle`/`choose`/state assignment, etc.), the body of any
  effect.
- **Typed outcomes** — a construct produces one of a closed set of named
  outcomes; consumers must branch exhaustively.
- **Legal-set filter** — the existing `rule`/`demands`/`active_rules`/
  `legal_moves` engine, generalized from "legal cards for `play_to_trick`" to
  "legal instances of any move-type." This is how the statically-enumerable
  legal set of §3 is computed.

## 6. The definition mechanism (the "mini internal DSL")

A game (or the stdlib) defines named interactions in kernel terms. A definition
is a **typed function**: parameters in, a typed outcome out, a body that lowers
to kernel constructs. Definitions may call other definitions.

**The hard line that preserves §3 and checkability:** *definitions may only name
and compose over the fixed kernel — they add words, not semantics.* No new
control primitives, no reflection, no runtime rule-mutation. This is exactly the
power needed for `challenge`/`block`/`trick`/`auction` and no more, so everything
still lowers to a finite, OpenSpiel-drivable action space, and the checker
verifies user definitions the same way it verifies the kernel.

This is the line between Coup (definable: `challenge` is a `round` over the
others) and Mao (not definable: it would require redefining the kernel at
runtime).

## 7. Construct discipline & stdlib promotion (corpus-first)

The engine surface is fixed and tiny; the construct-sprawl risk moves to the
library, where it is governed like any code:

- **Implement interaction vocabulary inline, per game.** Do not design a shared
  stdlib upfront.
- **Promote a definition to the shared stdlib only when ~3 games exhibit the
  same shape.** Until then it stays game-local. (Same corpus-first rule the rest
  of the project follows: abstract at the third example, not the first.)
- Promotion criteria, when the ~3 examples exist: the shape recurs structurally
  (same axes, differing only in values/parameters), and a shared name buys
  reading + a checkable typed-outcome/legality invariant.
- Adding a new *axis* to `round` (not a new value) is the only change that
  touches the kernel and requires explicit sign-off.

Expected promotions over the corpus: `trick` (Hearts/Spades/Getaway + every
trump game — promotes almost immediately), `auction` (Pinochle → Bridge → Skat →
Tarot), `challenge`/`block` (Coup, with Bridge's double as a second instance —
may or may not reach three). `betting_round` (Stud) and `climb` (Tichu) likely
stay game-local unless a future candidate game reuses them.

## 8. Checkability obligations

The checker, over kernel uses and definitions alike, verifies:
- every definition/use lowers to decision + chance nodes (no un-lowerable
  construct exists);
- every typed outcome is handled exhaustively by its consumer;
- every decision's legal set is statically resolvable to a finite enumeration
  over the fixed vocabulary (§3);
- all references resolve (move-types, characters, characters' claims/blocks,
  rule names, outcome branches).

## 9. IR & OpenSpiel lowering

Each decision node lowers to an IR decision node carrying: the acting
participant (its information set), the enumerable legal-action set, and per-action
successor. Chance events (shuffle/deal) lower to chance nodes. `round`/`offer`/
definitions desugar to trees of these before IR emission, so the IR consumer (the
OpenSpiel adapter) sees a uniform decision/chance tree regardless of which
surface construct produced it. This is the gate of §2/§3: lowering *is* the
definition of every sugar, so nothing in layers 2–3 can fail to lower.

## 10. Worked example — Coup

Vocabulary, defined once in game terms (illustrative syntax):

```
define lose_influence(p) {
  let card = p chooses one of influence[p]
  reveal card to all
  move card from influence[p] to revealed[p]
  when influence[p] is empty: move all coins[p] to treasury      // exiled
}

define challenge(claimant, character) -> upheld | refuted {
  any other living player may challenge:                         // round over others, first-commit
    when claimant has character:
      claimant reveals character, shuffles it back, draws a replacement
      challenger loses an influence
      result upheld
    otherwise:
      claimant loses an influence
      result refuted
  if nobody challenges: result upheld
}

define block(action, by blockers, with characters) -> blocked | allowed {
  any blocker may block:
    let c = blocker claims one of characters
    when challenge(blocker, c) is upheld: result blocked          // a block is itself a claim
    otherwise: result allowed
  if nobody blocks: result allowed
}
```

Characters and actions then read like the reference cards, every word lookup-able:

```
action tax by Duke {
  when challenge(actor, Duke) is upheld:  gain actor 3 coins
}
action assassinate(target) by Assassin {
  actor pays 3 coins
  when challenge(actor, Assassin) is upheld:
    unless block(this, by [target], with [Contessa]) is blocked:
      lose_influence(target)
}

character Duke       { enables tax;         blocks foreign_aid }
character Assassin   { enables assassinate }
character Captain    { enables steal;       blocks steal }
character Ambassador { enables exchange;    blocks steal }
character Contessa   { blocks assassinate }
```

**Unification bonus:** the existing `Trick` mechanic (currently opaque Python)
re-expresses as a `trick` definition — a `round` where each participant plays one
card under a follow rule, with an outcome function. Old built-ins and new
vocabulary de-magic into the same kernel + library scheme.

## 11. Rollout plan (corpus-first)

1. **Kernel first.** Build `offer`, `round` (closed axes), typed outcomes, the
   generalized legal-set filter, and effect verbs through the full pipeline
   (grammar → AST → resolver → checker → IR → runtime). Validate by
   re-expressing `trick` as a definition and running the existing Hearts/Spades/
   Getaway playout tests unchanged (diff against current behavior).
2. **Convert games incrementally**, replacing each Python mechanic with in-DSL
   definitions, game by game, keeping each game's playout test green throughout.
   Suggested order, easiest interaction first: trick family (already validated)
   → auctions (Pinochle, Bridge, Skat, Tarot) → windows (Coup) → the singletons
   (Cribbage pegging, Stud betting, Tichu climbing).
3. **Promote at ~3 examples** (§7): `trick` early; `auction` at the third auction
   game; `challenge`/`block`, `betting_round`, `climb` as the corpus warrants.
4. The existing Python mechanics remain until each game is converted — no
   big-bang rewrite; the corpus stays green at every step.

## 12. Risks & open design points

- **Kernel expressiveness is the hard part.** The kernel must be rich enough that
  `challenge`/`block`/`trick`/`auction` are all cleanly *writable* in it, yet
  constrained enough that the checker sees through definitions to verify §3.
  Getting this boundary right is the central design work, deferred to the
  implementation plan with the corpus as the forcing function.
- **Concrete syntax is unfinalized.** All syntax here is illustrative; the surface
  grammar (how `round`'s axes, accumulators, and typed outcomes are written; how
  `offer`/`when`/`result` read) is decided in the plan, validated against the
  games.
- **Rules-engine generalization.** Extending `demands`/`active_rules` from
  card-plays to arbitrary move-types (with rank comparison and trick-pile / round
  inspection) is its own sub-design.
- **Legal-set static resolvability.** The checker must prove every legal set is
  finitely enumerable; pinning exactly what makes a definition statically
  resolvable needs care.

## 13. Integration with the project's docs

This is a forward-looking design artifact, so it lives under
`docs/superpowers/specs/`, not in `docs/` (which is current-language spec — "spec,
not history"). As pieces land, settled decisions are promoted into
`docs/decisions.md` in spec voice, and any genuine open questions into
`docs/open-questions/`, per the project's maintaining rules.
