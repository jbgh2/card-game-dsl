# The convention gap, mirrored on Cheat — what three models read at the challenge window

The `cheat_gap` study: [`PREREGISTRATION_CHEAT_GAP.md`](PREREGISTRATION_CHEAT_GAP.md)
is the contract (written 2026-09-12, before any model was called), the
archive is `results_cheat_gap/`, and every number below is read from the
audits under `results_cheat_gap/derived/`, which
`verify_cheat_gap.py` recomputes from the committed records with no shared
code. Cells were run 2026-09-15 and 2026-09-16; the three registered cells
ran at their registered N.

The study mirrors the Hanabi "convention gap" (Fukushima, Xiong & Moradi Pari,
arXiv 2609.11489) on an adversarial game. At every challenge window an
observer sees a standing claim and calls "Cheat!" or lets it go; the
referee holds the truth whether or not anyone called. The **literal
posterior** is P(lie | the observer's information state) under uniform
hidden card choice; the **gap** of a set of windows is its lie rate minus
its mean literal posterior; and the registered statistic, the **selection
contrast**, is the gap over the windows a seat challenged minus the gap over
every window it faced — zero in expectation for a challenger that cannot see
the cards, whatever the reference's calibration. The primary subset is
**R1-abstains**: the windows where the claim is not provably false from
entitled information, the analogue of the paper's unhinted-card cell.

---

## The headline

**The registered hypothesis — that the models are card-blind challengers on
the windows where the literal channel is silent, contrast indistinguishable
from zero — is rejected in all three cells, and in the negative direction.**
The plays each model chose to challenge were *less* often lies than the plays
it faced, while both card-blind references sit within a few points of zero:

| seat, R1-abstains within depth 250 | selection contrast | 95% CI (bootstrap over games) | sign test across games |
|---|---|---|---|
| **Haiku 4.5** (`llm_cheap_table`, N=20) | **−13.18 pp** | [−25.54, −4.26] | 3 pos / 15 neg of 18, p = 0.0075 |
| **Sonnet 5** (`llm_mid_table`, N=20) | **−21.01 pp** | [−28.28, −13.43] | 3 / 17 of 20, p = 0.0026 |
| **Opus 5** (`llm_frontier_table`, N=10) | **−7.65 pp** | [−13.92, −0.31] | 2 / 8 of 10, p = 0.109 |
| null control (`rule_table`, four rule seats) | +6.46 pp | [−7.18, +19.64] | 22 / 19 of 41, p = 0.76 |
| second reference (`rule_vs_random`, random seats) | +2.62 pp | [−2.40, +8.38] | 13 / 7 of 20, p = 0.26 |
| in-cell nulls (each cell's own rule seats) | +6.95, +4.16, +7.09 pp | every interval covers zero | p = 0.17, 0.82, 1.00 |

Two cells reach the registered threshold on both the interval and the exact
sign test. The frontier cell's interval clears zero but its sign test does
not: the preregistration registers that at N = 10 the test reaches p < 0.05
only at 9 of 10 games, and 8 of 10 is what it got.

The paper's AI-AI cell is −0.7 pp — AI pairs reading nothing beyond the
literal content — and its human cells are +26 pp and +46 pp, humans acting on
more than the channel carries. These three models are neither. They
condition on something, and it points the wrong way.

## What they condition on

One exploratory cut explains most of the sign. Challenge rate rises steeply
with the number of cards claimed, and against these opponents the lie rate
falls with it:

| cards claimed (R1-abstains) | true lie rate, cheap / mid | Haiku challenges | Sonnet challenges | memoryless policy reference | literal reference |
|---|---|---|---|---|---|
| 1 | 0.53 / 0.56 | 17% | 9% | 0.57 | 0.92 |
| 2 | 0.26 / 0.32 | 32% | 46% | 0.55 | 0.99 |
| 3 | 0.47 / 0.45 | 41% | 52% | 0.70 | 1.00 |
| 4 | 0.21 / 0.12 | 86% | 100% | 0.59 | 1.00 |

A bluffing `RuleAgent` lies mostly when forced, one card at a time, and
announces four of a rank only when it holds four. The models apply the
human-plausible prior that a big claim is suspicious, and against this table
that prior is exactly wrong. The frontier seat is the same shape: it
challenged 61% of its abstains windows and its challenged windows were lies
30% of the time against 36% over all it faced.

This cut is exploratory — made after the contrasts were seen — and it is
the interpretive centre of the result, so it is stated with its rank.

## Two references, and what neither explains

**The literal reference is saturated.** Under uniform hidden card choice a
standing claim is a lie in about 96% of the worlds consistent with the log
whoever made it (mean 0.954–0.974 across cells), against true lie rates of
0.36–0.45. That is why the raw gap (−45 to −60 pp in every seat, card-blind
ones included) is a property of the reference and the contrast is the
statistic. The preregistration says so in advance.

**The memoryless policy-aware reference does not absorb the contrast
either.** Built after the cheap and mid cells were scored (exploratory, `~`,
recorded as a dated addendum), `gap_policy.reference` is P(lie | the
observer's hand, the flip record, the claimant's hand size before the play,
the claim, and the claimant's declared `bluff_prob`) — the claimant's hand as
a uniform draw from the cards the observer cannot place, weighted by the
`RuleAgent` count policy's likelihood of the observed count, that likelihood
read off the agent's own method rather than restated. It is exact, engine-free,
and 1.0 wherever provability fires. Scored against it the contrast stays
negative and clear of zero: **−8.88 pp** [−20.53, −0.55] (cheap), **−17.13 pp**
[−23.49, −10.06] (mid), **−9.57 pp** [−16.04, −2.13] (frontier).

The table above shows why. The memoryless reference is nearly flat in claim
count (0.54–0.71) where the truth swings from 0.53 down to 0.12. A reader
who knows the opponents' policy but keeps no memory of the game does *not*
predict that four-card claims are almost always honest; that regularity
comes from the line — what a seat has picked up and claimed before. So the
open question is no longer "reading versus policy inference" in the abstract:
it is whether any reasoner without memory of the line gets this right, and
only the full line-conditioned posterior (R2, [issue
#707](https://github.com/jbgh2/card-game-dsl/issues/707)) can answer it.
A reweighting of the literal sampler's worlds cannot serve, because the rule
agents' card choices are deterministic given the hand and the effective
sample size collapses; the determinism has to live in the proposal.

## The secondaries (`~`)

1. **The deceiver's side** — the gap over the windows a seat allowed minus
   the gap over every window it faced: **+4.86 pp** (cheap), **+9.37 pp** (mid),
   **+12.03 pp** (frontier). The plays these models let pass were more often
   lies than average, the mirror of the primary result.
2. **R1-fires** — where the claim is provably false and the gap is pinned to
   zero, the live quantity is the challenge rate: **Haiku 36%** (21 of 59 in
   the scored set; 35% over all 63 in-bound), **Sonnet 70%** (43 of 61),
   **Opus 100%** (26 of 26). A rule agent challenges every one. The cheap model
   lets most catchable lies go while challenging honest four-card plays.
3. **The in-cell null** — each cell's own rule seats, scored on the same games
   and budget: +6.95 pp [−4.66, +17.79], +4.16 pp [−7.20, +15.48], +7.09 pp
   [−4.56, +19.18]. Three more card-blind challengers at or near zero, on the
   LLM seats' own lines.
4. **The capability gradient** — per-game contrast paired by seed across
   cells on seeds 0–9, exact two-sided sign test: cheap → mid 4 up / 6 down,
   p = 0.75; cheap → frontier 6 / 4, p = 0.75; mid → frontier 8 / 2, p = 0.109.
   No cell separates from another at the Bonferroni level (0.0083). The most
   capable model is perfect on the deductive part (R1-fires) and still carries
   the same mis-set prior on the inductive part.
5. **Window position** — the corpus serializes the challenge race clockwise
   from the claimant's left, so a contrast that varied by position might be
   measuring the serialization. It does not: the contrast is negative at
   every position in every cell (cheap −12.8 / −5.8 / −21.7 pp at positions
   0 / 1 / 2; mid −19.6 / −17.2 / −26.7; frontier −8.8 / −9.1 / −5.8).
6. **The four-LLM exploratory cell** was not run.

## Why the numbers are trustworthy

**Every gate the preregistration declared in advance was met.**

| cell | games | truncated | fallback rate | LLM windows in bound | converged | in-cell null converged | replay checks |
|---|---|---|---|---|---|---|---|
| cheap | 20 / 20 | 0 | 0.0085 | 467 (404 abstains, 63 fires) | 449 / 467 = 0.962 | 590 / 600 = 0.983 | all passed |
| mid | 20 / 20 | 1 | 0.0000 | 492 (431, 61) | 489 / 492 = 0.994 | 598 / 600 = 0.997 | all passed |
| frontier | 10 / 10 | 0 | 0.0000 | 242 (216, 26) | 242 / 242 = 1.000 | 586 / 600 = 0.977 | all passed |

The gates: fallback rate under 2%, every window replayed against its own
recorded game digest, convergence of at least 95% of the LLM seat's in-bound
windows at the registered budget, and no replay-check failure — a sampled
world that did not replay to its window would have halted scoring. The
scorer refuses a statistic below the convergence floor and pools converged
records only; it did not have to.

**The null was measured before spending.** The floor above (+6.46 pp, half-width
≈ 13 pp at 46 challenged windows) sized the cells: N = 20 was registered to
reach ≈ ±6 pp and N = 10 ≈ ±9 pp on the primary endpoint, which is what they
delivered (half-widths 10.6, 7.4 and 6.8 pp).

**One cell was resumed, before any window was scored.** The cheap cell's
first invocation stopped at 5 of 20 games on a token backstop left at its
pre-cache value while the dollar spend was $1.52 of $40. It was resumed to
20 through the rig's own resume path, which replays the same seeds and seat
rotation a single run would have used; the only figures read before the
resume were the summary's game count, fallback rate, cache share and cost.
The preregistration's amendment records the stop and the resume.

**The subsample is a function of each cell's own windows.** A review found
that the posterior's per-cell subsample was drawn from one generator advanced
across cells in sorted order, so a cell scored alone drew a different sample
than the same cell scored from the full archive. Fixed by seeding per cell;
replaying the selection against every committed record showed the null
control's and both LLM cells' samples unchanged and only the smoke cell's
R1-fires draw moved, which was regenerated (the preregistration carries both
figures with their dates).

**The scorer shares no code with the producers.** `verify_cheat_gap.py`
imports nothing from the sampler, the window enumerator or the engine, pinned
by an AST scrape; its arithmetic is checked against a hand-computed fixture.
`gap_policy.py` is pinned the same way, and its count law is held to the
agent's own method by simulation over every holding and hand size.

## What is not established

- **The opponent is one policy.** A bluffing `RuleAgent` lies mostly when
  forced and never over-claims past one card; the anti-correlation between
  claim size and lying is an artifact of that policy. A different opponent
  could reverse it, and with it the sign of the contrast. The finding is
  about these models against this table.
- **The reference is literal, not optimal, and the policy-aware reference is
  memoryless.** Whether the contrast survives a line-conditioned posterior is
  the decisive unmeasured quantity (issue #707).
- **Everything is inside the depth bound.** Windows past decision 250 are
  outside the instrument (issue #662), and every number is a statement about
  the early part of a line.
- **The dropped windows in the cheap cell are not random.** All 18 are seed
  4's windows after the LLM seat's own successful challenge at step 90, each
  rejected on one constraint at every proposal — the sampler's model of that
  line, not depth ([issue #696](https://github.com/jbgh2/card-game-dsl/issues/696)).
  The 95% gate absorbed it; the scored set for that cell is short of the
  in-bound set by an event-dependent slice.
- **There are no human cells**, and the prompt's section order changed before
  any registered cell ran (the event log ahead of the table view, for the
  prompt cache — recorded as a dated amendment; the treatment record moved
  with it). Any sentence placing these contrasts beside the paper's +26 pp, or
  beside the earlier Cheat study's challenge rates, compares across testbeds.
- **The cells ran under the engine that preceded the `asked` observation
  event.** The engine now logs, for every decision, the question the seat
  was put, and the prompt guide explains that event, so a cell run or
  replicated today shows the model a different stimulus and is a different
  treatment from these three. A resume of one of these cells is refused on
  the changed treatment fingerprint; only `--accept-changed-treatment`
  appends new-stimulus games to them, and records that it did. Checked
  2026-09-22 against main at
  `8b283099`: every audit here recomputes byte-identically from the
  committed records, and the logs differ from the ones the models saw only
  by the `asked` events.
- **The exploratory cell** (`llm_cheap_four`) was not run; nothing here
  speaks to a table of four models.

## Cost and time

| cell | per-game estimate | cell cost | wall clock |
|---|---|---|---|
| cheap (Haiku 4.5) | $0.36 | $6.78 (two invocations) | 5 games in 20 min, then 15 in ~1 h |
| mid (Sonnet 5) | $0.85 | $22.78 | ~2.5 h |
| frontier (Opus 5) | $1.51 | $21.24 | ~1.5 h |

Estimates are one game each, on this account; cells ran longer than their
estimate game. The study's model spend, estimates included, is about $61
against a planning envelope of $118–158 — because the prompt is cached. Before
that, one uncached estimate game cost $7.69: the prompt carries the seat's
whole event log, so each call's prompt grows with the line and a game's cost
is quadratic in its length. Putting the log ahead of the table view and
cutting the request into cache blocks (a change to billing and to section
order, not to content) served 80–93% of input tokens from the cache.
Scoring is CPU only: about an hour per cell for the two posteriors.

## Reproduce it

```bash
# Windows, every cell, each replayed against its recorded digest.
python -m experiments.llm_eval.gap_windows \
  --dir experiments/llm_eval/results_cheat_gap/transcripts --out windows.jsonl

# The LLM seat's posterior for one cell (and --observer-agent rule --per-cell 600
# for its in-cell null); the committed records under derived/ are what these
# commands produce.
python -m experiments.llm_eval.gap_posterior \
  --windows windows.jsonl --out posterior_llm_cheap_d250.jsonl \
  --observer-agent llm_cheap --per-cell 2000 --subsample-seed 0 \
  --ess-floor 200 --min-proposals 2000 --max-proposals 32000 \
  --max-depth 250 --check-count 1

# Every number above, from the records, no engine.
python -m experiments.llm_eval.verify_cheat_gap \
  --windows windows.jsonl --posterior posterior_llm_cheap_d250.jsonl

# The memoryless policy-aware reference, scored by the same command.
python -m experiments.llm_eval.gap_policy \
  --windows windows.jsonl --out policy_llm_cheap_d250.jsonl \
  --observer-agent llm_cheap --max-depth 250
```

## Defects these runs found that the suite did not

**A growing prompt billed quadratically.** The planning figure came from a
study whose games ran half as long; the first cached-off estimate game cost
seven times it. The fix was in the rig, not the study.

**A token backstop stopped an affordable cell.** `max_input_tokens` counts
cached tokens too and was never re-priced; five games hit it at $1.52 spent.
The backstops now sit above the dollar cap and the config says why.

**A "deterministic" subsample depended on the file it was drawn from.** One
generator advanced across cells (above). Seeded per cell; every committed
sample replayed.

**A second promotion emptied the archive summary of its earlier cells.**
`promote` rebuilt the summary from the runs named on its command line; the
free cells vanished the moment the cheap cell was promoted. It now describes
the whole archive.

**The sampler drops a line's windows after the observer's own successful
challenge** (issue #696) — a signature the depth bound does not explain,
found because the log names the constraint that rejected every proposal.

**The declared prior is keyed on a roster name, not a kind** ([issue
#708](https://github.com/jbgh2/card-game-dsl/issues/708)), found by the
fresh-context enumeration that preceded the policy reference.
