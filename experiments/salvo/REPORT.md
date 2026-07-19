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
   the sighted-blind gap grow, do margins stay healthy?
2. **Per-location liveness**: contest depth vs target extremity (are
   edge targets knife-fights and mid targets volume wars, as
   designed?).
3. **salvo-mini + exact tier**: equilibrium mixing at the first
   committer's staging, value of the count channel, per DESIGN.md.
4. Combos + jokers (needs the stdlib combo primitive decision).
