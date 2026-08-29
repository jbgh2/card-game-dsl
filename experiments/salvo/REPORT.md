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
- **No combos and no jokers in the games measured here** (they arrive
  in round 5). Combos are self-synergy and would, if anything,
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

## 8. Round 3 — capacity 4 (adopted) + recon draw: the axis comes alive

Designer decisions after round 2: candidate (d), the per-location
capacity of four (staged plus flipped, per player), goes into the BASE
game — `salvo.cardlang`'s commit guards; candidate (c), the recon
draw (commit fewer than two in a round, draw one extra at round end),
tested as `variants/salvo-recon.cardlang`. Configs `cap` and `recon`
in the arena; knob-identical to round 1; hold-threshold sensitivity by
`--hold-below N --probes-only`. Data: `results_triage_cap.json`,
`results_triage_recon.json`, plus `_hb9/11/13` probe files.

**The recon draw makes commitment count a real decision, and the
capacity-only control proves the attribution.** Own-value restraint
(`blind_hold` vs never-holding `blind`, knob-identical) across hold
thresholds:

| hold threshold | capacity only | capacity + recon |
|---|---|---|
| 7 (default) | 48.4 / 51.0 | 54.1 / 45.4 |
| 9 | 48.2 / 51.3 | 55.3 / 44.3 |
| 11 | 43.3 / 56.4 | **57.9 / 41.8** |
| 13 | — | 20.0 / 80.0 |

Without recon, holding loses at every threshold, monotonically worse
the more you hold — there is nothing to buy. With recon, the same
policies win with an **interior optimum** around thresholds 9-11, and
over-digging (13: 7.2 commits/game) crashes to 20/80 — a dose-response
curve with a sweet spot and a punishment for overdose, which is
exactly what "the count is a decision" looks like. Opponent-aware
restraint says the same: sighted vs sighted_nohold under recon is
56.2/42.3 at the default threshold and 61.6/37.1 at 11, against a
flat null under capacity-only (50.3/48.5 and 48.4/50.4).

**An honest side effect: capacity compresses the crude-heuristic
skill gap.** sighted vs blind fell from 68.0/31.8 (round 1) to
48.1/51.3 under capacity (53.1/46.3 with recon). The cap performs
sighted's signature move — overkill avoidance — for both players by
rule, and forces blind's dumps to diversify; round 1's gap was partly
built on exploiting a pathology the cap now outlaws. Two reads, both
recorded: (1) decision divergence holds at 14-19% (round-1 level), so
choices remain opponent-contingent — the game did not slide back
toward solitaire; (2) the sighted heuristic's race knobs
(won/lost margin 25) were calibrated to uncapped margins (~22 mean)
and rarely fire at the capped scale (~9 mean) — under capacity,
sighted approximately equals blind_hold, consistent with its weights
being stale rather than the reading layer being dead. Re-tuning
sighted for the capped game (or graduating to the mini + solver) is
the follow-up instrument; until then the capacity skill-gap number is
a floor, not a measurement.

Margins tighten under capacity everywhere (blind mirror 22.0 to 9.3
mean; medians 5-8), unclaimed ties sit at 4-6%: tight races, no
runaway dumps, liveness intact.

**Recommendation to the designer**: adopt the recon draw into the
base game (it is the tested answer to "commitment number must
matter"), keep hold-threshold texture in mind for combos (held cards
already gain option value in round 4's combo work), and treat the
sighted re-tune as the next instrument work before reading any more
skill-gap numbers off the arena.

## 9. Round 4 — recon adopted; the re-tuned instrument and the
## adopted game's scoreboard

The designer adopted the recon draw; `salvo.cardlang` now carries
capacity + recon and the tested variant file is retired. The arena
gained per-seat knob dicts (a candidate can face a FIXED reference),
and `tune_sighted.py` swept the sighted knobs in two stages (200
seeds/cell vs fixed `blind_hold(10)` and `blind`; data:
`results_tune.json`).

**A note on which deals these numbers come from.** The sweep selects the
knobs on seeds 0-199, so reporting the winner on a range that also starts
at 0 would score the choice on deals it was chosen from. Every number
below is measured on seeds 200-699 instead — disjoint from the sweep, and
recorded as `seed_start` in both artifacts. The correction is worth about
1-2 points: it moved every pairing involving the tuned policy DOWN, and
left `blind_hold vs blind` — the one pairing using no tuned knob — up
0.5, which is noise and is the control that says the effect was the
policy's and not the seed range's.

**Tuning result.** Winner: `hold_below 11, urgency_w 1.0,
opp_staged_est 11` — margins stay at 25 (the round-3 "stale knobs"
hypothesis was wrong in an instructive way: TIGHT margins collapse
outright — won/lost 8 scores 0.09-0.11, the weights fire constantly
and strangle commitment — while the wide originals were near-optimal;
the urgency boost was mildly harmful; the real gains were the hold
threshold and respecting unseen staged cards). Tuned-vs-old-knobs:
58.8/40.6.

**The adopted game's scoreboard** (`results_triage_base.json`, tuned
knobs, 1000 games/pairing):

| pairing | win rate | reading |
|---|---|---|
| sighted vs blind | **64.1 / 35.8** | full skill vs commit-max |
| sighted vs sighted_nohold | **60.8 / 39.1** | holding, given sight |
| sighted vs blind_hold | 55.0 / 44.5 | sight, given holding |
| blind_hold vs blind | 58.4 / 41.1 | holding, blind |
| sighted_nohold vs blind | 50.8 / 48.8 | sight alone, no holding |

Two axes, both load-bearing, and a profile shift worth naming: in
round 1 the entire skill was WHERE (redirection 69/31, holding nil);
in the adopted game redirection alone is nearly neutral (51/49 —
capacity now does crude redirection by rule) while the
commitment-count axis carries the head of the skill (holding worth
+17 net points blind, +22 sighted), and opponent-reading stacks
another +10 on top of restraint (55.0 vs blind_hold). Tuned play uses
~9.3 commits and ~2 holds per game — the recon dial is exercised, not
maxed. Divergence holds at 16-22%; margins 9-16 mean; unclaimed ties
1-4%. The designer's requirement — commitment number must matter — is
now the game's strongest measured skill axis, with location-reading
second and both above chance.

Caveats, standing: all numbers are heuristic-tier lower bounds (the
sweep is coarse, one knob family, references are simple policies);
the exact-tier mini remains the ground-truth instrument for
equilibrium questions, and combos/jokers (round 5) will move every
number.

One caveat is specific and bounded: the ADOPTED game's scoreboard above
is measured on deals disjoint from the tuning sweep, but rounds 1-3's
numbers are not — each round selected knobs and reported on ranges that
both start at seed 0. Those rounds are left as recorded, deliberately:
they are a log of what was measured when the decision was taken, and
re-running them would rewrite the history rather than correct the live
claim. Read them as carrying the same optimistic tilt this round
measured at 1-2 points, and read only the adopted scoreboard as clean.

## 10. Location liveness by target extremity (evaluation question 3)

Instrument: `probe_liveness.py` — 1000 mirror playouts per policy on
the adopted base game, over seeds 200-1199 (the sighted policy carries
the tuned knobs, so the probe starts past the sweep's range for the same
reason §9 does; `seed_start` is recorded in the artifact), each location binned by its target's distance
from rank 7 (mid: targets 6-8, near: 4-5/9-10, edge: A-3/J-K; the
bins naturally appear in 22/31/47% of location slots). Data:
`results_liveness.json`.

Under tuned sighted play:

| bin | cards | card-distance | affinity | margin | unclaimed | least-contested (vs share) |
|---|---|---|---|---|---|---|
| mid | 6.11 | 1.84 | 48.5% | 14.5 | 5.0% | 16.6% (22.0%) |
| near | 5.91 | 1.77 | 47.1% | 15.0 | 4.4% | 28.0% (31.1%) |
| edge | 5.44 | 1.92 | 39.9% | 16.6 | 2.5% | 55.4% (47.0%) |

**The designed personalities are real.** Edge targets are precision
fights: skilled play commits FEWER cards there but keeps them just as
close to the target (distance ~1.9 — against random's 5.3, the
repricing does enormous selective work), with affinity mattering
less. Mid targets are volume wars: more cards, more affinity rescue.
The gradient is modest but consistent, margins stay flat-ish across
bins (14.5-16.6), and unclaimed ties are low everywhere.

**The Blotto abandonment watch comes back healthy.** Edge locations
are the game's thinnest battlefield somewhat more often than chance
(55.4% least-contested against a 47.0% appearance share, ratio 1.18)
— a lean, not a script. Instructively, BLIND play is scriptier
(71.0%, ratio 1.51): opponent-awareness softens abandonment rather
than amplifying it, because sighted players contest an edge the
opponent under-commits to. No concede-the-edge degenerate pattern
under any policy. Question 3 closes positive.

## 11. Exact tier, fixed deals: staging MIXES at equilibrium

Three curated fixed-deal salvo-mini solves (seeds 0 mixed / 3 mid-pair
/ 14 edge-pair; CFR+ to exploitability under 0.02 on the +/-48
differential scale; `results_mini_seed{0,3,14}.json`):

- **40-42% of all reached decision infosets play MIXED strategies** in
  every deal — the staged-concealment game demands randomization at
  equilibrium, Green Lane's "measurably interesting" bar met at ground
  truth rather than inferred from arenas.
- **The very first decision bluffs.** The round-1 opener — whose
  placement the second committer will see as a staging count before
  acting — mixes its location 75/25 (seed 0) and 78/22 (seed 3):
  textbook unpredictability against a count-reading opponent, the
  construct the staged-alternating design existed to produce. The
  edge-pair deal (14) opens pure — extreme targets can force the
  opening — with its mixing living deeper in the tree (40% overall).
- **Values (+1.0 / +2.0 / +4.0 for the round-1 initiative holder)
  fold dealt-hand asymmetry into themselves** — fixed deals cannot
  separate "initiative is worth something" from "P0 drew better." The
  deal-sampled game is the instrument that isolates the structural
  initiative and count-channel value; it remains HELD pending the
  designer's go.
- **Instrument economics, corrected**: ~23 s per CFR+ iteration on one
  deal's 20k-decision tree (about 100 iterations to converge, ~40 min
  per deal). A 64-seed sampled game at full-tree CFR+ extrapolates to
  roughly a day per hundred iterations — NOT an overnight run. Before
  the sampled solve is greenlit it needs one of: fewer seeds (8-16 is
  3-8 hours), outcome-sampling MCCFR (the probe-tier tool), or an
  Undertow-style fast-sim speed twin with an adapter crosscheck. The
  long-run contract's calibration-first discipline earns its keep here.

## 12. Round 5 (combos + jokers) — implemented; the measurement is open

Expressing the combo bonus table requires combinatorial-structure
queries over a zone (same-rank groups, runs, flushes) that the language
does not have. The blocking question was not whether to write that in
Python but under what discipline: another entry in a corpus-wide
registry is the pattern this experiment exists to surface, not extend
(designer's call, on review). The hole is the language's largest
recurring one — five shipped witnesses already pay for it in Python
(cribbage's show, Stud's entire showdown, the climbing vocabularies,
Gin's melds, Canasta's melds) — and its characterization and option
space live in `docs/design-notes/combination-scoring.md`.

What answered it is the `primitives { }` block
(`docs/design-notes/primitive-sidecars.md`): the game declares
`salvo_combos` itself, with its typed signature and the three army
families it reads, so the borrowing is visible in the game file and
belongs to no other game's namespace. The joker half needed no
language decision (joker cards, rankings, and filtered deals all
exist) — only the `standard54` deck row, which the same change adds.

Both are in the game file and the rigs. The arena run and its verdicts
are what this round still owes: the point values are DESIGN.md's
starting values, and question 4 (combo incidence) is the instrument
that moves them.
