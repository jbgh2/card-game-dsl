# Kuhn poker — the Cheat experiment, run on a game with a known answer

The [Cheat evaluation](REVIEWER.md) measured deception-relevant behaviour through
the engine's *derived* information sets. It could not say how well the models
actually played, because Cheat has no solution: its baseline was a hand-written
heuristic, and every metric was a behavioural proxy.

Kuhn poker is solved. Six deals, five lines, thirty leaves. So the baseline is
the exact equilibrium, and "how well did it play" becomes a number in chips per
hand with a floor everybody can check.

**N = 1500 games per matchup**, 9000 games total. This is the confirmatory run
registered in [`PREREGISTRATION_KUHN_REPLICATION.md`](PREREGISTRATION_KUHN_REPLICATION.md);
an earlier N = 300 run
([`PREREGISTRATION_KUHN.md`](PREREGISTRATION_KUHN.md)) generated the hypotheses
and is superseded by everything below.

---

## The headline

**Both models reach the ceiling on non-randomising play — and that ceiling is
1/6 of a chip per hand short of optimal, because Kuhn has no deterministic
optimum.**

| | Haiku 4.5 (raw) | Haiku 4.5 (rendered) | Sonnet 5 |
|---|---|---|---|
| chips per hand vs equilibrium | **−0.157** | −0.072 | −0.018 |
| exploitability | 0.323 | **0.167** | **0.164** |
| best a *pure* strategy can do | 0.167 | 0.167 | 0.167 |
| gap above that bound | 0.156 | **0.000** | **−0.003** |
| dominated actions taken | 52 / 200 | **0 / 200** | **0 / 200** |
| bluffs a Jack, first to act | 0.000 | 0.000 | 0.000 |
| bluffs a Jack after a check | 1.000 | 0.000 | 0.000 |
| *equilibrium plays these at* | *0.167 / 0.333* | | |
| fallback rate | 0.0043 | 0.000 | 0.000 |

Opponent throughout is the exact equilibrium at α = 1/6. Zero truncated games.

Exploitability is zero for an equilibrium player and rises with what a
best-responding opponent can extract. Sonnet and rendered-Haiku both land on
**0.1667**, which is exactly the least any non-randomising policy can concede —
computed by exhausting all 2⁶ pure strategies per seat (1/9 at seat 0, 2/9 at
seat 1, averaged over a rotating roster). They are not making mistakes. They have
reached the ceiling on deterministic play, and the whole remaining gap is the
failure to mix.

### Sonnet's measured policy, against equilibrium

| information set | n | Sonnet | equilibrium (α = 1/6) |
|---|---:|---|---|
| J, first to act | 257 | check 1.000 | check 0.833, **bet 0.167** |
| Q, first to act | 241 | check 1.000 | check 1.000 |
| K, first to act | 252 | bet 1.000 | check 0.500, bet 0.500 |
| J, checked to | 181 | check 1.000 | check 0.667, **bet 0.333** |
| Q, checked to | 169 | check 0.686, bet 0.314 | check 1.000 |
| K, checked to | 235 | bet 1.000 | bet 1.000 |
| J, facing a bet | 47 | fold 1.000 | fold 1.000 |
| Q, facing a bet (seat 0) | 162 | fold 0.031, call 0.969 | fold 0.500, call 0.500 |
| Q, facing a bet (seat 1) | 92 | call 1.000 | fold 0.667, call 0.333 |
| K, facing a bet | 26 | call 1.000 | call 1.000 |

It never folds a King and never calls with a Jack — the two dominated actions —
in 200 opportunities. It plays its value hands correctly. **It never bluffs**, in
either place equilibrium requires it, and it calls Queens far too often. Those
are the leaks a best responder takes 1/6 of a chip a hand through.

(Seat 0 holding a King and facing a bet never occurs: it always bets its King
first, so it is never checked-then-bet-at.)

---

## The three registered hypotheses

Registered before any model was called, with the direction fixed by the N = 300
run so this confirms rather than re-discovers.

### H1 — the endpoint. **Confirmed, overwhelmingly.**

`dominated_action_rate` is lower under `reason_first` than under `reasoning`.

| | control | reason-first |
|---|---|---|
| dominated actions taken | **52 / 200** = 0.260 | **0 / 74** = 0.000 |
| paired units (deal x seat) | 1500 | 1500 |
| units where both faced the choice | 74 | 74 |
| paired sign test | **52 down, 0 up, 22 tied** | |
| exact two-sided p | **4.4 x 10⁻¹⁶** | |

Every one of 52 discordant pairs moved in the registered direction; none moved
against it. At N = 300 this rested on 8 pairs and p = 0.0078. The registered
one-sided p is 2.2 x 10⁻¹⁶.

**Fallback sensitivity.** 7 of the control's 1627 decisions fell back to uniform
random after two parse failures, and a random choice facing a bet with a J or K
takes the dominated action half the time — so fallbacks inject dominated actions
that are not the model's decision. Excluding them: **47 / 193 = 0.244** against
0.260 as registered. The arm is 0 / 74 either way. The conclusion does not move.

### H2 — the point prediction. **Confirmed.**

`exploitability_above_pure_bound` within ±0.02 of zero for both Sonnet and
rendered-Haiku. Measured: **−0.0026** and **0.0000**. This was a point
prediction with a stated tolerance, made before the data existed and able to fail
in either direction. It did not.

### H3 — purity. **FALSIFIED for Sonnet, confirmed for rendered-Haiku.**

Predicted: both models' policies are pure at every information set with at least
30 visits.

- **rendered-Haiku: 9 of 9 pure.** Confirmed.
- **Sonnet: 8 of 10 pure, 2 mixed.** Falsified. It mixes at "Queen checked to"
  (check 0.686 / bet 0.314, n = 169) and marginally at "Queen facing a bet"
  (fold 0.031 / call 0.969, n = 162).

At N = 300 Sonnet looked pure everywhere but one thin information set, and that
is exactly the claim the extra data was bought to test. It does randomise.

**What makes this interesting rather than merely wrong:** H2 still holds. Sonnet
mixes, and its mixing buys it essentially nothing — it lands 0.0026 *below* the
pure-strategy bound, a gain of a quarter of a hundredth of a chip per hand. And
it mixes in the wrong place: equilibrium plays "Queen checked to" as a pure check,
so Sonnet is randomising exactly where it should not, while playing deterministically
in the two places equilibrium requires randomisation. The corrected claim is not
"these models cannot randomise" but "these models do not randomise where it pays".

---

## Finding 2 — what reason-first actually traded

It removed a class of blunder outright and did **not** make the model good.

| Haiku 4.5 | control | reason-first |
|---|---|---|
| dominated actions | 52 / 200 | **0 / 200** |
| exploitability | 0.323 | 0.314 |
| bluffs a Jack, first to act | 0.000 | **0.996** |
| chips per hand | −0.157 | −0.049 |

It stopped calling with Jacks and started bluffing them **almost every time**
(0.996 where equilibrium says 0.167). A perfectly predictable bluffer is as
exploitable as a perfectly predictable honest player, which is why exploitability
barely moved while chips per hand improved: it is beating *this* opponent's
folding frequencies, not playing well.

**This is the opposite of what the same manipulation did in Cheat**, where
reason-first raised the challenge rate 0.470 → 0.798 and wrong accusations per
game 10.3 → 25.1. The two are consistent if deliberation-before-committing buys
*checking a fact about your own hand* and costs *restraint about acting on a
suspicion*. Kuhn's endpoint is the first kind; Cheat's was the second.

## Finding 3 (exploratory, `~`) — presentation halved exploitability

Same model, same information, same seeds; the only change is whether the model
reads the engine's raw information-state string or an English rendering of it
produced by a pure function of that string.

| Haiku 4.5 | raw | rendered |
|---|---|---|
| exploitability | 0.323 | **0.167** |
| dominated actions | 52 / 200 | **0 / 200** |
| chips per hand | −0.157 | **−0.072** |

Rendering took the model from "makes blunders" to "plays the optimal pure
strategy". It is the largest effect in the study and it is a presentation change,
not a capability one. Deliberately **not** promoted to a registered hypothesis:
it was found by looking, and promoting it on the strength of the look is what
pre-registration exists to prevent. It stays `~` until a run registers it in
advance.

---

## Why the numbers are trustworthy

**The baselines behave as theory requires.**

| | chips/hand | exploitability | dominated |
|---|---|---|---|
| equilibrium vs itself | 0.0000 | at its noise floor | 0 / 400 |
| equilibrium vs random | **+0.130** | at its noise floor | 0 / 427 |
| random | −0.130 | 0.489 | 72 / 147 |

**The solver is checked against the engine, not against itself.** Every reported
game is replayed through the payoff table and compared with the DSL runtime's own
`returns()` — 9000 games, zero mismatches. Separately, the equilibrium constants
are checked by computing their exploitability with the brute-force best response
and asserting it is zero across the whole α family.

**The null was calibrated before spending.** Exploitability of an *estimated*
policy is biased upward, so a player exactly at equilibrium still measures above
zero over finitely many hands. Measured offline first: a real `NashAgent` scores
0.0297 at N = 1500, 0.0099 at 6000, 0.0031 at 24000 — converging to zero and
tracking its own resampled floor. The instrument is sound.

For the models the floor is not the right benchmark and this matters: their
policies are near-pure, so almost nothing about them is estimated. The correct
benchmark is the pure-strategy bound, which is what the headline uses.

**The coverage caveat is discharged, not waived.** Coverage runs 0.83–0.92, and
the pre-registration called that unusable if the fill were load-bearing. It is
not: `exploitability_fill_sensitivity` is **0.00000** for every model measured,
because each unvisited information set is unreachable under that model's own
policy — and a set the fixed player cannot reach, a best responder cannot reach
either. For the *mixing* Nash baseline the same quantity is non-zero (up to
0.206), so the check is not vacuous.

**Seat fairness is exact.** Balanced seating from the start, so every roster
position sits in every seat of every deal exactly once. Pinned by
`tests/test_seating.py` as an identical multiset of dealt hands, verified by
planting the defect.

## What is not established

- **Two models**, Haiku 4.5 and Sonnet 5. Opus was configured but not run.
- **One opponent.** α = 1/6 is one member of the equilibrium family; a model's
  best response to a different member could differ.
- **Not a capability claim.** This is about what the harness can measure and what
  these policies look like, not about how good the models are at poker.
- **Re-running is not replication.** Model responses are not deterministic. The
  transcripts are the record.

---

## Cost and time

| | |
|---|---|
| **New DSL written** | **0 lines** |
| DSL this stands on | `kuhn-poker.cardlang` 134 lines + `poker_betting.cardlang` 142 shared |
| games played | 9000 (6 matchups x 1500) |
| API spend, this run | **$18.59** (Sonnet $10.63, Haiku $7.95) |
| wall clock | ~2 h 10 min, two parallel streams |
| cumulative spend, both runs | ~$25 |

The Cheat experiment cost roughly $90. A Cheat hand is ~210 sequential API calls
with prompts that grow with the observation log; a Kuhn hand is ~1.2 calls at
~1.9k tokens.

## Reproduce it

```bash
# baselines, no API key, ~1 minute
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_kuhn.yaml --matchup nash_vs_random

# every number above, recomputed from the committed transcripts, and the A/B
python -m experiments.llm_eval.verify_kuhn
```

`verify_kuhn` extracts the policies and re-derives every rate with its own
arithmetic rather than calling `kuhn.aggregate`. It shares the solver
deliberately — reimplementing a best response to check a best response checks
nothing — and instead cross-checks the solver against the engine's recorded
returns on every game.

---

## Defects these runs found that the suite did not

Every one came from executing the experiment; none from inspection.

**A model beat an opponent that cannot be beaten.** Seat rotation and the deal
were both functions of the game index, and the adapter's seed-to-deal map is not
parity-balanced, so the model held a King 112 times to the baseline's 97. Fixed
by balanced seating, which plays every deal in every seating; Cheat keeps the old
scheme deliberately, and is measured unaffected (issue #233).

**A metric moved with the opponent rather than the player.** The bluff rate
pooled a dominated action into its numerator and let the opponent's betting
frequency move its denominator: the identical equilibrium policy scored 0.187
against itself and 0.144 against a random opponent.

**The pre-registered test ran on half its data.** The paired analysis keyed on
the deal seed, but balanced seating plays each seed once per seating, so a dict
keyed on the seed silently kept one — 150 of 300 games, every survivor in the
same seat. The unit is now (deal, seat).

**The published archive 404'd on a fresh clone.** Its `summary.json` was promoted
by hand-copy, so every transcript pointer still named the gitignored run
directory it came from. Reported by Codex on #234. The same hand-copy also left
behind the sidecars that name the game, so a game-agnostic audit tool fell
through to its Cheat default and printed a real Kuhn win rate beside a Cheat
metric reading `None` — exit 0. Both are the same root cause: promotion is a
command typed by hand rather than a function, so it carries some of what the run
recorded. Handed to the Hold'em workstream, which owns the shared audit path.
