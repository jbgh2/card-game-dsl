# Salvo — round-1 triage report

Instrument: `triage.py` (policy arena over `salvo.cardlang` via the replay
core; no solvers yet). Data: `results_triage.json` — 8 pairings, 1000
games each (500 seeds, both seatings), PYTHONHASHSEED=0. Policies:
`random`; `blind` (greedy on the shared value core, sees no opponent
zone, never holds voluntarily — the commit-max hypothesis as a player);
`sighted` (same value core plus per-location race weighting from public
opponent state: overkill and lost-cause discounts, urgency boost, holds
on waste); `sighted_nohold` (sighted's weighting, blind's never-hold).
The design questions are DESIGN.md's evaluation plan; the double-
solitaire question was posed directly by the designer.

## 1. It runs, and the mirror is pinned

The game file passed the front end on the first attempt and plays
end-to-end through the runtime. A hand-audited seed-0 trail confirmed
the round structure: alternating initiative, windows closing at two
commits, holds legal, staged piles flipping public at round end,
settle math as designed. Every playout asserts the **mirror pin**:
locations won and grand totals recomputed by the harness's Python value
function from the last pause's world must equal the DSL's terminal
returns. It failed once during bring-up (a reconstruction bug in the
harness, not the game — the final pending pick was dropped when the
game uses the global card block) and has been green across all 8000
games since. The DSL's settle arithmetic and the harness agree exactly.

Cost note: ~36 ms per game through the re-simulating replay core; the
full arena is ~5 minutes. Playout-scale triage needs no memo and no
pyspiel.

## 2. Not double solitaire: opponent state is worth +18 points of win rate

The controlled comparison holds the value function fixed and varies
only opponent information:

| pairing | win rate | n |
|---|---|---|
| sighted vs blind | **68.0% / 31.8%** (0.2% draw) | 1000 |
| sighted_nohold vs blind | **69.0% / 30.8%** | 1000 |

A crude race-weighting heuristic beats the identical heuristic minus
opponent input by ~37 points of net win rate (stderr ~1.5pp). The
divergence probe agrees: on 16-21% of decisions, the sighted player
chooses differently than its blind twin would in the same position —
one decision in five or six is opponent-contingent even at this
heuristic's crudity. Mutual adaptation shows in the margins: mean
final per-location margin is 22.0 in blind-vs-blind but 11.4 (median
8) in sighted-vs-sighted — races tighten when both players read the
board. Corroborating: sighted beats random 98.8% while blind manages
only 90.8% — overkill stacking loses to accidental spreading often
enough to matter.

Verdict: the Blotto skeleton is doing its job. Allocation is
genuinely interactive; the sighted-vs-blind gap is a *lower* bound on
the value of opponent information, since both policies are crude.

## 3. The commit-count axis is dead (as predicted on paper)

DESIGN.md records the risk: under the all-positive curve (every commit
scores at least +1, eleven cards against twelve slots), committing the
maximum should be near-dominant. Confirmed:

- **sighted vs sighted_nohold: 48.3% / 49.7%** (2.0% draws) —
  statistically indistinguishable. Holding adds nothing.
- sighted_nohold-vs-blind equals sighted-vs-blind (69.0 vs 68.0): the
  entire sighted edge is *redirection* (where), none of it restraint
  (whether/how much).
- Blind's 1.0 mean holds are exactly the forced hold (hand empty in
  the last window). Sighted's tuned hold threshold fires ~0.1 extra
  holds per game and buys nothing.

So the WHERE axis carries the game; the HOW-MANY axis is fake under
this curve. The design fork (designer's call, both recorded in
DESIGN.md): (a) adopt the zero-centered curve (base value 6 minus
distance; far commits score negative) and re-run this same arena —
holding and hand-digging should come alive; or (b) accept commit-max,
simplify the rules to "stage exactly two" (or "exactly one"), and let
allocation be the whole game. Option (b) is a smaller game but an
honest one; option (a) is the richer design and now has empirical
motivation, not just the on-paper argument.

## 4. Location liveness is healthy

Unclaimed-tie rate per location: 2.5-2.7% for non-adapted play, rising
to 7.6% under mutual adaptation (tight races produce exact ties;
2% of sighted-mirror games end drawn). No sign of the degenerate
abandonment script the Blotto family risks — margins stay contested
(sighted-mirror median 8 points) rather than collapsing into
concede-one-crush-two patterns. Finer per-location stats (contest
depth by target extremity, initiative effects) are a round-2 probe.

## 5. Honesty ledger

- **Heuristics, not solvers.** All verdicts are playout-scale. The
  double-solitaire verdict is robust (a lower bound argued from a
  controlled pair); the dead-commit-axis verdict is strong but could
  in principle be overturned by a policy that holds *cleverly* (e.g.
  sandbagging to win the last-flip information race). The mini +
  exact tier remains the ground-truth instrument.
- **No combos, no jokers yet** (round-2 scope, recorded in the game
  file header). Combos are self-synergy and would, if anything,
  soften the interaction verdict's margin — they cannot rescue a
  double-solitaire core, which is why the base game was tested first.
- **Sighted's knobs are hand-tuned** (WON/LOST margin 25, opponent
  staged card estimated at 9.5, hold threshold 7). No sweep was run;
  the controlled comparisons are knob-for-knob identical between the
  compared policies, so the verdicts do not ride the tuning.
- **Mirror-match rows pool both seats** under one label (an artifact
  of same-name seating in the arena table); their win_rate column
  reads as "either seat", and only margins/commits/draws are
  meaningful there.
- The staged-alternating encoding means strict simultaneity is
  approximated by hidden staging with public counts (DESIGN.md,
  information structure). The interaction verdict includes whatever
  value the count channel carries; separating that channel's worth is
  a mini-tier question.

## 6. Next probes, in order

1. **Curve A/B**: zero-centered variant file through this same arena —
   does holding come alive (sighted vs sighted_nohold separates), does
   the sighted-blind gap grow, do margins stay healthy? → run; see
   section 7. **Refuted on both counts.**
2. **Per-location liveness**: contest depth vs target extremity (are
   edge targets knife-fights and mid targets volume wars, as
   designed?).
3. **salvo-mini + exact tier**: equilibrium mixing at the first
   committer's staging, value of the count channel, per DESIGN.md.
4. Combos + jokers (needs the stdlib combo primitive decision).

## 7. Round 2 — the zero-centered curve A/B (hypothesis refuted)

Variant: `variants/salvo-zc.cardlang` (base value 6 minus distance,
range -6..+9; the sole diff from the main file). Instrument: the same
arena with per-curve tuning (`--curve zc`; knobs rescaled, controlled
pairs still knob-identical; mirror pin green on the variant, including
negative totals). New policy `blind_hold`: own-value restraint with
zero opponent state. Data: `results_triage_zc.json`, 10 pairings, 1000
games each; side-by-side via `compare_curves.py`.

The zero-centered curve was the recorded fallback for the dead
commit-count axis. It does not fix it, and it costs interaction:

- **Holding still worthless.** sighted vs sighted_nohold: 50.2/48.8.
  blind_hold vs blind: 50.4/49.1. Both indistinguishable. Hold usage
  barely moved (~1.1 vs the forced 1.0): the hold trigger almost
  never fires.
- **The interaction gap SHRANK.** sighted vs blind fell from 68.0/31.8
  to 56.8/42.5; decision divergence fell from 16-21% to 11-12%. The
  compressed value range (spread 15 points vs 8) flattens army
  differences: margins halve everywhere (blind mirror 22.0 to 10.1,
  sighted mirror 11.4 to 7.8), unclaimed ties rise in non-adapted play
  (random mirror 2.7% to 5.8%). Less texture, more coin-flip, less
  room for the opponent-reading that made round 1 encouraging.
- Blind punishes random harder (90.8% to 97.0%) — negative values
  penalize random's bad commits — but that is value-hygiene, not
  interaction.

**Diagnosis: the axis is dead for a structural reason the curve cannot
reach.** A commit chooses the best of THREE locations, so a card must
be far from every target at once (and off-suit near the close ones)
before holding beats committing — with targets spread over the rank
line, the max-of-three value is almost always comfortably positive.
Meanwhile committing has **no opportunity cost**: eleven cards, twelve
slots, so playing a card never forecloses anything. No value curve
makes "how many" a decision while slots outnumber cards and every
commit is free.

**Live fix candidates, for the designer** (all cheap in this harness;
all change rules, not numbers):

- **(c) Recon draw** — commits and draws trade off: a round in which
  you commit fewer than two earns an extra draw. Holding buys card
  advantage; restraint becomes an economy, not a value judgment. The
  standard-deck-native answer to Snap's energy ramp.
- **(d) Per-location capacity** — Snap's four-card cap per side per
  location. Creates slot scarcity (9-12 capped slots against 11
  cards), kills dump-ground piles, and makes committing to a
  location spend one of ITS scarce slots.
- **(e) Total commit budget** — e.g. eight commits per game across
  all locations: every commit forecloses another; interacts with the
  per-round reveal order (late commits are better informed), so it
  likely needs (d) or a per-round cap alongside to avoid everyone
  sandbagging to the end.
- **Combos** (already scheduled) — held cards gain option value
  (keep the 7 hoping to pair it later), a softer, texture-first
  pressure on the same axis.

The zero-centered curve remains available as value *texture* (it does
change which commits are mistakes), but it is no longer a candidate
fix for the commit-count axis, and on this evidence the all-positive
curve's wider spread serves the interactive core better.
