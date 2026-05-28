# Triggered scoring

**Tier 2 — high impact, blocked on a data point.**

Per-hand scoring components compose by summation (see
[decisions.md](../decisions.md), "Scoring composition"). But some
scoring fires when a state threshold is crossed rather than at a fixed
phase: Bridge's GameBonus fires when a partnership's below-the-line
score crosses 100; RubberBonus fires when `games_won` reaches 2;
Spades' bag overflow fires when `bags >= 10`. They currently live as
imperative post-component checks.

Two possible shapes:

(a) **Components grow a `triggered_by:` clause**, analogous to
    rules' `applies_when:`. GameBonus would declare
    `triggered_by: below_line_current_game[winner] crosses 100`.
    Components are unified; what differs is when they fire.

(b) **Two distinct kinds** — per-hand components in the summation,
    and threshold-triggered events invoked independently.

Leaning (a); threshold-triggered firing has the same shape as
sub-phase event transitions.

**Blocker:** Cribbage's pegging events (fifteens, pairs, runs,
thirty-one) are likely the same shape from a third angle. With
three data points, commit to (a) or (b) properly.
