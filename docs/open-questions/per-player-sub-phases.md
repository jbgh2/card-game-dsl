# Per-player sub-phases

**Tier 3 — medium impact, narrow scope.**

Tichu's small-Tichu call window is *per-player*: each player may
declare `call_tichu` until *they* play their first combination.
The window doesn't close globally when any player plays — it closes
for that one player.

The provisional surface:

```
phase tichu_window per_player {
  legal_moves: [+ call_tichu]
  transition_to: closed when this player plays their first combination
}
```

Existing sub-phase transitions in the corpus
(`hearts_broken`, `spades_broken`, `first_trick`) fire globally on
the first matching event. There is no per-player mode yet.

Design choices:

- **`per_player` modifier** on the sub-phase, instantiating one
  parallel instance per player. The instance's `transition_to`
  trigger refers to "this player". Per-player state lives in the
  per-player instance.
- **Per-player boolean state** with `applies_when:` gating on the
  move (`applies_when: not state.first_play_made[active_player]`),
  bypassing the sub-phase machinery entirely. Lower-cost but loses
  the "this rule set is active in this window" framing the rest of
  the corpus uses.
- **Treat the window as ordinary state** with a `closed_for[player]`
  Boolean and check it in the move's preconditions.

The boolean form (option 2 or 3) sidesteps the sub-phase syntax. It
might be the right answer; it might just be giving up. The
boolean-as-sub-phase criterion in
[decisions.md](../decisions.md) — "a boolean that gates rules should
be a sub-phase" — would push toward option 1.

Tichu is the only game in the corpus that needs this. A second game
with per-player windows (some bidding variants where each player has
an individual call window) would clarify which form to commit.

Related: [optional-window-moves](optional-window-moves.md) — what's
*available* during the window. This file is about *when* it closes.
