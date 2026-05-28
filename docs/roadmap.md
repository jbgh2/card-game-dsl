# Roadmap

What's explicitly deferred, and the suggested order of next steps.

## Explicitly deferred

Things we have noted but consciously not designed yet:

- **CCG-style card effects** (Magic, Yu-Gi-Oh!). Out of initial scope. The
  Forge text-DSL pattern (one mini-language per card) is the reference if/when
  we tackle this.

- **Detailed melding logic.** Pinochle's meld phase is hand-waved as a
  mechanic. Real melding (combinations, scoring, conflicts) is its own design
  exercise.

- **Solitaire and positional zones.** CardStock excludes spatially-dependent
  layouts. We don't, but we haven't implemented one yet. Klondike or FreeCell
  will be the test case.

- **OpenSpiel compilation.** The DSL design is independent of the target
  runtime. Compilation will be a downstream pass once the surface stabilizes.

- **Auto-derivation of `information_state_tensor`.** This is the prize for
  OpenSpiel integration but depends on zone visibility being airtight.
  Deferred.

- **Determinization as a compiler pass.** For IS-MCTS support. Deferred.

- **Bidding sub-language.** Bridge bidding systems are a domain unto
  themselves. The current `submit_bid` move type is enough for Spades/Oh
  Hell/Pinochle-style bidding; Bridge will need more.

- **The meta-DSL for "X is Y but with deltas".** We discussed this as the
  natural way the literature describes variants. The current design supports
  it implicitly (a variant adds/removes rules and phases from a base game)
  but doesn't have explicit syntax for it. Worth revisiting after Pinochle.

## Suggested next steps, in order

The [open-questions/_index.md](open-questions/_index.md) orders open
questions by impact × actionability; Tier 1 there are the questions ready
to commit now. This section adds the context the open-questions list
doesn't carry: which next game would unblock Tier 2, and the meta-level
work (OpenSpiel compilation, dealer promotion) that lives outside the
open-question framing.

1. **Resolve Tier 1 open questions — they're unblocked.**

   - [sub-phase-rule-syntax](open-questions/sub-phase-rule-syntax.md) —
     commit the provisional `+ X` / `- X` / `override X` form.
   - [mechanic-internal-legality](open-questions/mechanic-internal-legality.md) —
     decide between promoting internal state to a queryable interface
     versus accepting some legality as mechanic-internal.
   - [actor-vs-chooser](open-questions/actor-vs-chooser.md) — commit the
     zone-level `choices_made_by:` declaration. The provisional fix in
     Bridge has been load-bearing for several iterations.

   These three can be tackled in any order; none depends on the
   others.

2. **Pick a sixth game to unblock Tier 2.** The Tier 2 questions
   ([triggered-scoring](open-questions/triggered-scoring.md),
   [bidding-meaning](open-questions/bidding-meaning.md),
   [structured-score](open-questions/structured-score.md),
   [mechanic-phase-unification](open-questions/mechanic-phase-unification.md),
   [simultaneous-body-grammar](open-questions/simultaneous-body-grammar.md))
   each need one more data point. Game candidates ordered by how many
   Tier 2 questions they'd unblock:

   - **Cribbage** — pegging events would unblock "Triggered Scoring"
     (third data point) and probably "Structured Score" (third
     structured-score shape, after Bridge and Stud). Highest leverage.
   - **Oh Hell / Wizard** — unblocks "Bidding Meaning" (third data
     point after Spades and Pinochle/Bridge). Also a chance to validate
     the `BridgeAuction` → `Auction` shared mechanic story.
   - **Whist with a dummy** — second data point on actor vs chooser
     (though "Actor Vs Chooser" is already Tier 1 and could be
     committed before this game).
   - **Klondike or FreeCell** — first solitaire; tests positional
     zones and the `expose_top` operation. Doesn't directly unblock
     a Tier 2 question.
   - **Diplomacy or any negotiation-heavy game** — would unblock
     "Simultaneous Body Grammar" if its simultaneous-resolution step
     naturally requires control flow or intermediate state inside
     the simultaneous block. Lower priority unless the CCG /
     non-standard-deck scope is expanded.

   Recommended: **Cribbage**. Two-question unblock with one game.

3. **Resolve [triggered-scoring](open-questions/triggered-scoring.md)**
   once Cribbage gives the third data point. Commit to (a) `triggered_by:`
   clauses on components, or (b) a distinct trigger category.

4. **Resolve [bidding-meaning](open-questions/bidding-meaning.md)**
   once Oh Hell or Wizard is in the corpus.

5. **Resolve [structured-score](open-questions/structured-score.md)**
   if Cribbage's pegging board does turn out to be a third
   structured-score shape; otherwise wait for a clearer third data
   point.

6. **Address Tier 3 questions when their corner of the language
   gets exercised.** [routing-as-constraint](open-questions/routing-as-constraint.md)
   waits for a second routing-override game; the resource/visibility
   refinements ([typed-amount-syntax](open-questions/typed-amount-syntax.md),
   [move-level-visibility](open-questions/move-level-visibility.md),
   [transfer-failure](open-questions/transfer-failure.md)) wait for a
   second resource-using game.
   [zone-access-syntax](open-questions/zone-access-syntax.md) waits for
   a game whose natural notation puts a complex relational chain in
   subject position.

7. **Pin down [memory-event-syntax](open-questions/memory-event-syntax.md)**
   when three or four examples exist beyond stdlib operations. Stud is
   the first; no second example yet.

8. **Adopt Tier 4 cleanups when convenient.**
   [counters](open-questions/counters.md) and
   [dealer-promotion](open-questions/dealer-promotion.md) are pure
   readability/code-reduction wins; neither blocks anything.

9. **Defer Tier 5 cosmetic questions** until a real preference
   emerges from corpus pressure.

10. **Begin sketching the OpenSpiel compilation pass.** The
    [decisions.md](decisions.md) "Knowledge, visibility, and the
    projection model" section establishes perfect-recall-by-default;
    [decisions.md](decisions.md) "State scoping" establishes lexical
    scoping compiles to standard activation records; the
    knowledge-projection model gives OpenSpiel's
    `information_state_tensor` the per-observer event stream it
    needs. The compilation story has substantial scaffolding now.
