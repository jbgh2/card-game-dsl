# Game termination mid-phase

**Tier 3 — medium impact, narrow scope.**

Most corpus games end at a hand boundary: a `repeats until any
score >= N` clause on the outermost loop catches the winning state at
the start of the next hand. Hearts, Spades, Pinochle, Bridge,
Schnapsen, Tichu all work this way.

Cribbage is the first game in the corpus that can end *mid-hand*. A
player who pegs past 120 wins immediately — possibly during the
pegging round, possibly even on the cut (Two for His Heels). The
hand-boundary check on `hand_sequence` catches show-time winners, but
mid-pegging termination needs a separate mechanism.

The provisional surface used in `games/cribbage.md`:

```
mechanic PeggingRound (leader: Player) {
  ...
  early_termination: any score >= 121
  // abandons the round AND signals the enclosing hand_sequence to abandon too
}
```

Design choices:

- **`early_termination:` propagates up** — a sub-construct may declare
  a condition; when it fires, every enclosing `repeat`/`phase` block
  is also abandoned until the condition no longer applies. Matches
  Pagat's framing ("This can happen at any stage").
- **Top-level `game_ends_when:` clause** on the `game { }` header —
  one global predicate evaluated after every state change. Cleaner
  semantics; harder to reason about *when* the check fires.
- **Triggered termination via the scoring components** —
  `triggered_by: score reaches 121` with a special action ("end game,
  active_player wins"). Reuses the triggered-scoring machinery (see
  decisions.md "Triggered scoring components") but conflates scoring
  and control flow.

The Trick mechanic already has an `early_termination:` parameter
that abandons the trick early (Getaway uses it). Extending the same
shape to "abandon enclosing hands/games" is a generalization rather
than a new construct, which favors option 1.

A second mid-phase-terminating game (poker hand ending on fold,
shedding games ending when a player empties hand) would clarify
which form to commit. Until then a Cribbage-specific construct is
fine.
