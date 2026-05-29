# Optional moves during a window

**Tier 3 — medium impact, narrow scope.**

Tichu's `call_tichu` and `call_grand_tichu` are *off-the-clock*
declarations: any player may submit one any time before a personal
threshold (first card played, or ninth card taken). They are not
"turn moves" — the game does not stop and wait for them. They are not
forbidden either; if you don't call, nothing happens.

The provisional surface:

```
phase grand_tichu_window {
  legal_moves: [+ call_grand_tichu]
  each player simultaneously may submit call_grand_tichu
}
```

Existing move types in the corpus are mandatory at their turn
(`play_to_trick`, `submit_bid`) or are a turn-equivalent declaration
(`pass`). There is no "optional move during a window" idiom yet.

Design choices:

- **`may submit X`** as a phase-body verb — explicit "any participant
  may, at any time during this phase, submit this move type."
- **Move-type property** `optional: true` plus a window in which it's
  legal — pushes the "optional" semantics onto the move type rather
  than the phase body.
- **Treat the call as a state write triggered by a player choice**
  outside the move framework — would push it out of the move-event
  stream, which complicates the knowledge model.

Tichu is the only game in the corpus that needs this. A second game
with player-initiated off-the-clock declarations (Schnapsen's
marriage declaration is a candidate, though it fires at a specific
moment; Belote's mid-trick declarations are closer) would clarify
which surface generalizes.

Related: [per-player-sub-phases](per-player-sub-phases.md) —
`call_tichu`'s legality window closes per-player, not globally.
