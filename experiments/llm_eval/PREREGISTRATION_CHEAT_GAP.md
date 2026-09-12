# Pre-registration — the `cheat_gap` study

**Written 2026-09-12, before any model has been called on this study.** Nothing
below was chosen after seeing model data; the only `cheat_gap` transcripts in
existence when this was committed are the two free cells, `rule_table` and
`rule_vs_random`, which involve no model at all.

One endpoint carries `*`. Everything else is a hypothesis generator, reported
with its interval and marked `~`.

---

## The question, and the paper it mirrors

"The Convention Gap: Towards Measuring Implicit Communication in Cooperative AI
Evaluation" (Fukushima, Xiong & Moradi Pari, arXiv 2609.11489, submitted
2026-09-10) defines the **convention gap** as an observed failure rate minus the
failure probability predicted from the *literal content* of what was
communicated. Computed exactly in Hanabi over ~101,000 actions, it is +26.2 pp
for human-human pairs (hanab.live), −0.7 pp for AI-AI pairs (HOAD) and +16.4 pp
for human-AI pairs (HanabiData), and it concentrates on plays of cards that had
received no hint at all: +46 pp in human pairs. Humans act on more than the
literal channel carries; the AI pairs do not.

This study is the adversarial mirror of that measurement, on Cheat. The unit is
the **challenge window**: a play stands with a claimed rank, one observer decides
call-or-allow, and the referee holds the ground truth for that play whether or
not it is challenged. Three quantities are therefore known at every window, and
having all three at once is what makes the measurement available here: the
observer's **information state** is a certified, leak-free object (`REVIEWER.md`,
the leak-freeness argument; `gap_sampler` reads that string and nothing else),
the observer's **action** is recorded, and the truth is recorded for every
window rather than only the resolved ones — a natural-play corpus gives the
first two and learns the third only where someone challenged.

- **Literal.** The claim plus everything the observer's information state
  entails, formalized as the **literal posterior** `R_literal` = P(the standing
  claim is a lie | that information state) under a uniform deal and uniform
  hidden card choice by every other seat. Public decisions carry no likelihood
  weight, which is exactly what makes it *literal* rather than policy-aware
  (`belief-calibration-spec.md` §3, R2 versus this). `gap_sampler.estimate`
  computes it by importance sampling over the worlds the observer cannot rule
  out.
- **Gap.** For a set of windows: the observed lie rate minus the mean
  `R_literal`, in percentage points.
- **Selection contrast.** The gap over the windows a seat *challenged* minus the
  gap over *every* window that seat faced.

**The literal reference is heavily miscalibrated, by construction, and the raw
gap is not a finding.** Under uniform card choice a standing claim is a lie in
about 96% of the worlds consistent with the log whoever made it, while the true
lie rate at those same windows is 43–50%. Every seat's raw gap is therefore
about −45 to −53 pp, and a challenger that ignores the cards entirely measures
one just as large. That number is a property of the reference, not of the
reader. The **selection contrast** is the statistic, because a challenge
decision independent of the cards leaves the challenged windows a random draw
from all of them: the two gaps agree, the base lie rate cancels, and the
contrast is zero in expectation (`verify_cheat_gap.contrast_stat`). What a
non-zero contrast measures is the part of the challenged windows' excess lie
rate that the literal information at those windows does not explain.

The Hanabi paper's unhinted-card cell — where literal content is silent and any
gap is reading — is the analogue of this study's **R1-abstains** subset: the
windows where the claim is *not* provably false from entitled information
(`belief-calibration-spec.md` §3, R1). That is the primary subset. On the
complement, R1-fires, `R_literal` is exactly 1 and there is nothing for a gap to
measure; the question there is only the challenge rate.

## Cells

All cells draw from the one config-level `seeds.start: 0`, so a per-game
quantity pairs by seed across cells.

| cell | roster | seeds | status |
|---|---|---|---|
| `rule_table` | 4 × bluffing rule (`challenge_prob 0.1`, `bluff_prob 0.4`) | 0–99 | **null control**, run |
| `rule_vs_random` | 1 bluffing rule + 3 random | 0–19 | **smoke** and second null, run |
| `llm_cheap_table` | Haiku 4.5 + 3 bluffing rule | 0–19 | **registered** |
| `llm_mid_table` | Sonnet 5 + 3 bluffing rule | 0–19 | **registered** |
| `llm_frontier_table` | Opus 5 + 3 bluffing rule | 0–9 | **registered** |
| `llm_cheap_four` | 4 × Haiku 4.5 | 0–2 | exploratory, not powered |

The three registered cells differ from one another only in the LLM seat's model
and name and in `n` (pinned by `tests/test_cheat_gap_config.py`), so any
difference between them is attributable to the model. Every cell sets
`rotate: true`, so the LLM seat occupies each table position in turn across
seeds and its windows are not all drawn from one position in the challenge
order — which is what makes secondary 5 separable from the seat's identity.

`rule_table` is the null control on the contrast's own account: a `RuleAgent`
challenges on nothing but `provably_false` and a fixed independent draw, so on
the R1-abstains subset it challenges by a coin flip that cannot see the cards,
and its contrast is zero in expectation. The random seats of `rule_vs_random`
are a second, independently-parameterized card-blind reference.

## Registered parameters

| parameter | value |
|---|---|
| depth bound | 250 decisions (`gap_posterior --max-depth 250`) |
| ESS floor | 200 (`--ess-floor 200`) |
| proposal budget | start 2000, double to at most 32000 (`--min-proposals 2000 --max-proposals 32000`) |
| subsample seed | 0 (`--subsample-seed 0`) |
| population, registered cells | EVERY in-bound window of the LLM seat: `--observer-agent llm_<tier> --per-cell 2000` |
| population, in-cell null | the same cell's rule seats: `--observer-agent rule --per-cell 600` |
| replay checks | 1 per window (`--check-count 1`) |
| bootstrap | 2000 resamples, resampling GAMES, seed 0 (`verify_cheat_gap.BOOTSTRAP_*`) |
| `n` | 20 (`llm_cheap_table`), 20 (`llm_mid_table`), 10 (`llm_frontier_table`) |

`--per-cell 2000` is set to exceed the count rather than to sample it: the
expected in-bound yield is ~23.5 windows per seat per game, so an `n`-20 cell
offers the LLM seat on the order of 470. `gap_posterior` logs
`selected=<taken>/<per_cell>` per cell, so a subsample that failed to take the
whole population is visible in the log rather than silent.

**Why the instrument is depth-bounded.** `gap_sampler`'s proposal settles a
revealed card's journey — hand, pile, the seat that collects the pile — over
exactly ONE pickup, which the observation log pins exactly; a journey needing
two pickups is proposed by luck and rejected when the luck does not hold
(`gap_sampler`, "What rejection costs"). Acceptance therefore falls as a line
lengthens, and the fix is more lookahead rather than more samples
([issue #662](https://github.com/jbgh2/card-game-dsl/issues/662)). Measured on
the free cells, 2026-09-12: unbounded, the sampler converged on 22 of 40
null-control windows; under `--max-depth 250` it converged on 1196 of the 1199
records it produced from 1200 selected windows (one dropped for zero accepted
proposals at the cap, three finishing under the ESS floor, median budget 2000),
and all 1199 replay checks passed. The bound is registered at **250 decisions**.
The deeper half of every line is outside the instrument and no claim is made
about it.

## N per cell, and the power argument

The floor sets the scale. Measured on `rule_table` (2026-09-12, R1-abstains,
depth ≤ 250): 46 challenged windows out of 599, contrast **+6.67 pp**, 95%
bootstrap CI **[−6.98, +19.87] pp** — a half-width of ≈13 pp at 46 challenged
windows.

Yield per LLM game, from the null control's measured window counts and the prior
study's challenge rate: ~23.5 in-bound windows per seat per game, ~21 of them
R1-abstains, and an LLM seat challenges about half of its opportunities
(`REVIEWER.md`, challenge rate 0.470 in the control arm) — so roughly **10
challenged in-bound abstains windows per game**. Scaling the floor's half-width
as one over the square root of the challenged count:

| N | challenged in-bound abstains windows | half-width |
|---|---|---|
| 10 | ~100 | ≈ ±9 pp |
| 20 | ~200 | ≈ ±6 pp |

**Registered: N = 20 for `llm_cheap_table` and `llm_mid_table`, N = 10 for
`llm_frontier_table`, seeds from 0 in every cell.** Seeds 0–9 are therefore
shared by all three, which is what the across-model pairing (secondary 4) runs
on; the two cheaper cells buy the extra within-cell resolution where it is
affordable, and the frontier cell — the most expensive of the three per game, at
~5x the cheap cell's per-game cost — is sized to the shared seeds. So the
primary endpoint is measured at ≈±6 pp in two cells and ≈±9 pp in the third,
against a floor whose own interval is ≈±13 pp. Nothing here has the power to
resolve a contrast of a few points from zero, and that is registered rather
than discovered: the effect this study is sized to detect is a contrast on the
order of the paper's human cells, not one on the order of its AI cell.

The companion sign test is coarse at these sizes and its resolution is
registered with it: an exact two-sided sign test reaches p < 0.05 only at 9 of
10 games (p = 0.0215) or 10 of 10 (p = 0.00195) in the frontier cell, and at 15
of 20 (p = 0.0414) in the other two.

**Cost envelope.** At the measured Cheat figures — ~210 model calls and ~1.05M
input tokens per game, ~$1.10/game on Haiku 4.5 and ~$5.60/game on Opus 5
(`config.yaml`) — the cheap cell is ≈**$22** and the frontier cell ≈**$56**. The
mid model's per-game cost is unquoted there and is treated as lying between the
two, so the planning figure for the mid cell at N = 20 is ≈**$40–80**, to be
confirmed by `run_eval --estimate 5` on this account before that cell runs — and
at the top of that range the mid cell costs more in total than the frontier one
does, which is the price of its larger N and not a mis-sizing. The whole study
is therefore ≈**$118–158**, which exceeds `config_cheat_gap.yaml`'s
`max_cost_usd: 40.0` deliberately: the cap is raised once, explicitly, after
`--estimate` has priced each cell, and never folded silently into a re-run. Wall
clock is the tighter constraint — 7–15 minutes per game makes an N-20 cell
2.5–5 hours and the N-10 frontier cell 1.2–2.5 hours.

## Primary endpoint

**`*` The LLM seat's selection contrast on the R1-abstains subset within the
depth bound**, per registered cell, reported with its 2000-resample bootstrap
95% interval over games, and tested with an **exact two-sided sign test across
games** of the per-game contrast against zero. A game enters the sign test when
it offers the LLM seat at least one challenged and at least one allowed in-bound
R1-abstains window (`verify_cheat_gap.contrast_sign_test`); a game with only one
of the two carries no contrast and is excluded rather than scored as a tie.

### Registered prediction

**No directional prediction. The hypothesis is that the LLM seat's contrast is
indistinguishable from zero** — that these models are card-blind challengers on
the windows where the literal channel is silent.

Two things predict it. The paper's own AI-AI cell is −0.7 pp: the AI pairs read
nothing beyond the literal content. And the prior Cheat study found these models
challenging about half of their opportunities at roughly coin-flip precision
(0.532 and 0.464) — four to five times the baseline's wrong accusations per game
— and found that asking the model to
reason *before* choosing **raised** the challenge rate (0.470 → 0.798, all 10 of
10 paired deals in the same direction, exact two-sided p = 0.00195). A seat that
accuses that freely, and accuses more when given room to talk itself into it, is
conditioning on something other than the cards; the opponent's lying history is
the uninformative feature nearest to hand.

**A rejection in either direction is the finding**, and the test is two-sided. A
positive contrast says the seat selects lies beyond what the literal channel
supports — the adversarial analogue of the human +46 pp. A negative contrast says
it selects *against* them, challenging the windows least likely to be lies, which
would be the mechanism behind the precision number the prior study measured
without explaining.

## Secondary, exploratory (`~`, never `*`)

1. `~` **The deceiver's side.** The gap over the windows the seat *allowed*
   minus the gap over every window it faced.
2. `~` **The R1-fires contrast.** Where `R_literal` is exactly 1 the gap is
   pinned to zero by construction and the only live quantity is the challenge
   rate on provably-false claims.
3. `~` **The in-cell null.** The three rule seats *inside* each LLM cell, scored
   the same way — a card-blind reference measured on the same games, the same
   lines and the same sampler budget as the LLM seat it sits beside.
4. `~` **The capability gradient.** The per-game contrast paired by seed across
   the three registered cells (seeds 0–9), exact two-sided sign test.
5. `~` **Contrast conditioned on window position.** The corpus serializes
   Pagat's real-time challenge race into a clockwise window from the claimant's
   left, so seat order decides first refusal on a catch and a contrast that
   varies with position may be measuring the serialization rather than the
   reader.
6. `~` **The four-LLM exploratory cell**, `llm_cheap_four`, at N = 3.

Bonferroni over these is 0.05/6 ≈ 0.0083.

**`R_policy` − `R_literal` is not reported, because no policy-aware reference
exists.** R2 — P(claim false | information state, the opponents' declared
policies) — is buildable here, since the rule agents' dispositions are set by
config (`belief-calibration-spec.md` §3), and the distance between the two
references is the right way to ask how much of any contrast is policy inference
rather than reading. It is not built, so the question is registered as not
answered rather than answered weakly.

## Stopping rule

`n` is fixed per cell in `config_cheat_gap.yaml` before the first call. No
interim look, no extension on a near miss, no cell re-run at a larger `n` after
seeing its interval. If a budget or wall-clock stop ends a cell short, the
partial `n` is reported **as partial**, and every across-cell pairing is
restricted to the seeds all three cells completed.

## What would make the result unusable

Declared in advance, so it cannot be rationalized afterwards:

- **`fallback_rate` above 2%** in any cell. The Cheat study's `neutral` arm died
  this way, at 22%, and was reported unusable rather than dropped.
- **A `game_digest` mismatch.** Every window is replayed against the digest its
  own transcript records, and `gap_windows` raises `ProvenanceError` on a
  mismatch or on a transcript carrying no digest at all. A transcript whose
  action ids do not name moves the game at HEAD has is not scoreable, and the
  refusal is fatal rather than a warning. (The *other* Cheat archive, under
  `results/`, is recorded against the tag `masf202608`, where a play is capped
  at four cards; it describes a different game and this study does not read
  it.)
- **Convergence below 95%** of the LLM seat's in-bound windows at the registered
  budget. The depth bound is then wrong for that cell, and the cell is reported
  as **unmeasured** rather than scored on the windows that happened to converge.
- **Any replay-check failure.** A sampled world that does not replay to the
  window it was drawn for is an instrument bug: halt, fix it, and quote nothing
  until the checks pass again.

**Truncation is not a gate.** `max_decisions: 1200` cuts long lines — measured
2026-09-12 on the free cells, 10 of 100 `rule_table` games and 5 of 20
`rule_vs_random` games — and the study keeps windows from truncated games. The
unit of analysis is the window, and a window's literal posterior conditions on
its own complete prefix, so a window from a capped game is as valid as any
other. What the cap biases is game-level outcomes — returns, win rates — which
this study does not report. Every cell's `games_truncated` (`metrics.py`) is
reported beside its window counts so the reader sees how many lines the cap
cut.

## The floor, and why the raw number is not the claim

Every contrast in this study is read against the null control's, never against
zero in the abstract. Measured 2026-09-12 on `rule_table`, R1-abstains,
depth ≤ 250, 599 windows of which 46 were challenged:

| | value |
|---|---|
| **CONTRAST** | **+6.67 pp**, 95% CI [−6.98, +19.87] pp |
| raw GAP(challenged) | −46.11 pp, 95% CI [−60.82, −32.01] pp |
| mean `R_literal` | 0.9611 |
| observed lie rate | 0.4341 over all 599 |

The second card-blind reference agrees, on `rule_vs_random`'s random seats
(same date, same bound): contrast **+2.62 pp**, 95% CI [−2.40, +8.38] pp over
222 abstains windows of which 108 were challenged; **+2.35 pp**, 95% CI
[−0.97, +6.01] pp over all 446. Two independently-parameterized card-blind
challengers land within a few points of zero with intervals that cover it.

The raw GAP beside them is the point of the paragraph above: −46 pp from a seat
whose challenge decision reads no card at all. `R_literal`'s miscalibration is a
property of the reference — a claim is a lie in ~96% of consistent worlds under
uniform card choice, against a true lie rate near 43% — and the uniform-choice
assumption is the *definition* of "literal" here, not a claim about how anyone
plays. The claim is the contrast, with its interval, read against this floor.

## What a green does not prove

- **The deal space is idealized.** `R_literal` is uniform over every deal of the
  deck, not over the 4096 deals the adapter's root chance node addresses. That
  is the same idealization the readiness proofs run under, and a reference
  predictor does not condition on it (`belief-calibration-spec.md`, the
  deal-space note) — which is also why a sampled world is replayed by installing
  its deal rather than by hunting for a seed that deals it.
- **The challenge window is serialized.** Real Cheat is a race; the corpus game
  polls observers in clockwise order. Secondary 5 is how that shows up, and it
  does not make it go away.
- **There are no human cells.** The paper's headline is a human-versus-AI
  contrast. This study measures models and card-blind baselines; the human arm of
  the mirror is absent, and any sentence comparing a contrast here to the paper's
  +26.2 pp is comparing across testbeds as well as across populations.
- **The instrument is depth-bounded** at 250 decisions (issue #662). Every
  number is a statement about the early part of a line.
- **The reference is literal, not optimal.** A model could beat `R_literal`
  by policy inference alone, with no reading of anything implicit; separating the
  two needs R2, which is not built.

## Order of running

Free cells first (done), then cheap, mid, frontier — each cell followed by the
same three-stage scoring. The commands, with `llm_cheap_table` as the worked
case:

```bash
# 0. The free cells. No API key; already run and promoted.
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_cheat_gap.yaml \
  --matchup rule_table --matchup rule_vs_random

# 1. Price the cell on this account, THEN raise max_cost_usd deliberately.
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_cheat_gap.yaml \
  --matchup llm_cheap_table --estimate 5

# 2. Run the cell and promote it into the archive.
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_cheat_gap.yaml \
  --matchup llm_cheap_table
python -m experiments.llm_eval.promote \
  --results experiments/llm_eval/results_cheat_gap --run <stamp>

# 3. Enumerate every window in the archive, each replayed against its own
#    recorded game digest.
python -m experiments.llm_eval.gap_windows \
  --dir experiments/llm_eval/results_cheat_gap/transcripts \
  --out windows.jsonl

# 4. The literal posterior over EVERY in-bound window of the LLM seat.
python -m experiments.llm_eval.gap_posterior \
  --windows windows.jsonl --out posterior_llm_cheap_d250.jsonl \
  --observer-agent llm_cheap --per-cell 2000 --subsample-seed 0 \
  --ess-floor 200 --min-proposals 2000 --max-proposals 32000 \
  --max-depth 250 --check-count 1

#    ...and the same cell's rule seats, as the in-cell null (secondary 3).
python -m experiments.llm_eval.gap_posterior \
  --windows windows.jsonl --out posterior_llm_cheap_rule_d250.jsonl \
  --observer-agent rule --per-cell 600 --subsample-seed 0 \
  --ess-floor 200 --min-proposals 2000 --max-proposals 32000 \
  --max-depth 250 --check-count 1

# 5. The independent recomputation: stdlib only, no engine, no sampler. Once
#    per posterior file — the LLM seat's, then the rule seats' in-cell null.
python -m experiments.llm_eval.verify_cheat_gap \
  --windows windows.jsonl --posterior posterior_llm_cheap_d250.jsonl \
  --out experiments/llm_eval/results_cheat_gap/derived/GAP_AUDIT_llm_cheap_d250.txt
```

Then `llm_mid_table` and `llm_frontier_table`, identically.

`windows.jsonl` and the posterior JSONL are regenerated rather than committed —
`results_cheat_gap/.gitignore` excludes `*.jsonl`, and both are pure functions
of the archive, the subsample seed and the sampler seed each record names. What
is committed under `results_cheat_gap/derived/` is the audit text and
`gap_posterior`'s own log, which is where a dropped or unconverged window is on
the record.
