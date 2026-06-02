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

1. **Tier 1 is empty.** All four original Tier 1 questions have
   been resolved into decisions.md:
   - `sub-phase-rule-syntax` → "Sub-phase rule and legal-move deltas"
   - `triggered-scoring` → "Triggered scoring components"
   - `actor-vs-chooser` → "Delegated play"
   - `mechanic-internal-legality` → folded into "State scoping (lexical)"
     (mechanic state is in scope for rules via standard lexical
     nesting; Stud's BettingRound legality was lifted to rules in
     the same commit).

2. **Pick the next game to unblock remaining Tier 2.** The remaining
   Tier 2 questions
   ([mechanic-phase-unification](open-questions/mechanic-phase-unification.md),
   [simultaneous-body-grammar](open-questions/simultaneous-body-grammar.md))
   each need one more data point. The full candidate pipeline lives in
   [games/_candidates.md](games/_candidates.md), with a coverage table
   mapping each open question to the games that would unblock it.

   Triggered-scoring was unblocked by Cribbage, bidding-meaning by
   Oh Hell, and structured-score landed in decisions.md after Skat
   confirmed the per-game pattern (see decisions.md "Scoring
   composition").

   Headline recommendations from the pipeline:

   - **Klondike or FreeCell** — first solitaire; tests positional
     zones. Doesn't directly unblock a Tier 2 question but forces a
     deferred design decision.
   - **Klondike** / **Hanabi** / **Coup** — would each force a
     different deferred design corner (positional zones,
     higher-order knowledge, knowledge events). All are bigger
     swings than the trick-and-bidding games we've been doing.

3. **Address Tier 3 questions when their corner of the language
   gets exercised.** The resource/visibility refinements
   ([typed-amount-syntax](open-questions/typed-amount-syntax.md),
   [move-level-visibility](open-questions/move-level-visibility.md),
   [transfer-failure](open-questions/transfer-failure.md)) wait for a
   second resource-using game.
   [zone-access-syntax](open-questions/zone-access-syntax.md) waits for
   a game whose natural notation puts a complex relational chain in
   subject position.

4. **Pin down [memory-event-syntax](open-questions/memory-event-syntax.md)**
   when three or four examples exist beyond stdlib operations. Stud is
   the first; no second example yet.

5. **Tier 4 cleanups landed.** Counters and dealer-promotion are
   both resolved — counters as inline expressions or per-game
   helpers (see decisions.md "Scoring composition"); dealer as a
   stdlib state variable (see library.md "Stdlib state").

6. **Defer Tier 5 cosmetic questions** until a real preference
   emerges from corpus pressure.

7. **Begin sketching the OpenSpiel compilation pass.** The
    [decisions.md](decisions.md) "Knowledge, visibility, and the
    projection model" section establishes perfect-recall-by-default;
    [decisions.md](decisions.md) "State scoping" establishes lexical
    scoping compiles to standard activation records; the
    knowledge-projection model gives OpenSpiel's
    `information_state_tensor` the per-observer event stream it
    needs. The compilation story has substantial scaffolding now.
