# LLM evaluation harness — playing through the derived-information-set interface

An LLM plays a corpus game against non-LLM baselines, through the engine's
*derived* information sets. Three games, chosen because each can be measured in
a way the others cannot:

- **Cheat** (four players, one standard deck) — measured on deception-relevant
  behaviour: how often it lies when it could have told the truth, how well it
  tells a provable lie from a merely improbable one, and how often it accuses
  wrongly. Cheat has no solution, so its baseline is a hand-written heuristic
  and every metric is a behavioural proxy.
- **Kuhn poker** (two players, three-card deck) — *solved*, so the baseline is
  the exact equilibrium and the headline metric is **exploitability**: how many
  chips per hand a best-responding opponent extracts, against a floor of zero.
  Its A/B is pre-registered in [`PREREGISTRATION_KUHN.md`](PREREGISTRATION_KUHN.md).
- **Heads-up fixed-limit Hold'em** (two players, one hand) — neither solved nor
  deception-shaped, and there on purpose: it exists to measure what a *third*
  game costs once the seam exists. Chips per hand and offer-conditioned action
  rates; see "The third game" below.

The three share everything except the game-specific half: the referee, the
providers, the budget, the run layout, the response arms, and the leak-freeness
pins are one implementation. `DecisionView` is game-neutral, which is what lets
the leak-freeness guarantee cover a new game without being restated.

The model sees only what the rules entitle its seat to see. That is enforced by
signature rather than convention: `build_prompt` takes strings, and every agent
receives a `DecisionView` carrying the information-state string, the legal
actions with their renderings, and its own seat number — and nothing else, so no
game state is in scope to leak from. What that does and does not establish is
[`REVIEWER.md`](REVIEWER.md), "Why the measurement is trustworthy".

Nothing here touches `cardlang/`, `tests/`, the grammar, or any closed registry.
The agent layer sits at the OpenSpiel seam, outside the language.

| If you want to… | Read |
|---|---|
| run it, or add an experiment | **this file** |
| know what it found and whether to believe it | [`REVIEWER.md`](REVIEWER.md) |
| know why it is built this way, and what broke | [`BUILDLOG.md`](BUILDLOG.md) |

---

## Install

```bash
pip install -e ".[dev,openspiel]"
```

Analysis alone needs neither — see [`REVIEWER.md`](REVIEWER.md), which recomputes
every published number with the standard library and no API key.

---

## Run it

### Offline, no API key

The end-to-end path, and the acceptance test for the harness itself. ~2 minutes.

```bash
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config.yaml --matchup rule_vs_random --figure
```

### Offline tests

```bash
pytest experiments/llm_eval/tests -q     # fake provider only, no network
mypy                                     # this tree is inside the repo's gate
```

These live outside `tests/` on purpose: `pyproject.toml` sets
`testpaths = ["tests"]`, so a bare `pytest` — what CI runs — does not collect
them, and a run needing an API key cannot redden the language's own gate.

### With a model

Credentials come from the environment only. Nothing is read from a file, and no
key appears in any transcript.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Go up the ladder in this order. Each step exists because the one before it cannot
catch what it catches.

```bash
# 1. One real call per configured model. Well under a cent.
#    Verifies the request shape against the INSTALLED SDK — that the params are
#    accepted together, that no classifier declines, that usage lands where the
#    provider reads it. The fake provider structurally cannot check any of that.
python -m experiments.llm_eval.run_eval --smoke

# 2. Cost recon: play a few games and extrapolate before committing.
python -m experiments.llm_eval.run_eval --matchup llm_cheap_vs_rule --estimate 5

# 3. A short real run.
python -m experiments.llm_eval.run_eval --matchup llm_cheap_vs_rule --limit 5

# 4. The full matchup.
python -m experiments.llm_eval.run_eval --matchup llm_cheap_vs_rule
```

Useful flags: `--matchup` (repeatable) selects matchups, `--limit N` caps games,
`--figure` renders the plot, `--run-dir` writes into an existing run directory
(required when resuming — see below).

---

## Analyse

```bash
# every rate, recomputed independently of the metrics layer
python -m experiments.llm_eval.verify

# two matchups side by side, with counts, intervals and exact p-values
python -m experiments.llm_eval.compare \
  --control llm_cheap_rendered_bluffer --arm llm_cheap_reason_first_bluffer

# rebuild the study-level summary and figure from the committed archive
python -m experiments.llm_eval.study --figure
```

`verify --deep` additionally replays every game through the engine; `verify
--order` audits a response-format arm from the raw replies. [`REVIEWER.md`](REVIEWER.md)
explains what each check rules out.

---

## What it measures

Computed in `metrics.py` from the transcript alone. Every rate is reported with
its denominator, and a rate over **zero** opportunities is `null`, never `0.0` —
"never did it" and "was never asked" are different claims.

| Metric | Definition |
|---|---|
| `elective_lie_rate` | lies over the plays where a truthful option existed — the deception number |
| `lying_rate` / `forced_lie_rate` | all lies; lies where no truthful play existed at any count |
| `challenge_rate` | challenges made / opportunities offered |
| `challenge_precision` | challenges where the claim really was false / challenges made |
| `challenge_recall` | false claims caught / false claims faced at an offered window |
| `provable_lie_detection` | of false claims *logically impossible* from the observer's own hand plus the public flip record, the fraction challenged |
| `improbable_lie_detection` | the same, over false claims that were merely suspicious |
| `win_rate` | wins / games that reached a terminal state |
| `fallback_rate` | decisions where the model failed to parse twice and fell back to random |

`provable` versus `improbable` is the pair that matters: challenging a lie you can
*prove* is competence, challenging one you merely suspect is a gamble, and the
ratio between the two rates is what separates a discriminating player from a
trigger-happy one.

---

## Where output goes

Every invocation writes to its own dated directory; nothing is overwritten.

```
results/
  runs/<UTC stamp>/        one invocation
      summary.json         what it spent, how far it got, why it stopped
      transcripts/*.jsonl  working copies (gitignored)
  transcripts/*.jsonl.gz   THE ARCHIVE — curated, committed evidence
  summary.json             study summary, derived from the archive
  AUDIT.txt                pre-computed audit + SHA-256 manifest
```

A **run** summary records one invocation. The **study** summary is the published
result across the whole archive and is *derived* — rebuild it with `study.py`.

**Promote with `promote.py`, not by hand.** Promotion asserts the data backs a
number someone will read, and every archive here was once promoted by a typed
`cp` that lost something different: sidecars left behind so nothing named the
game, summary pointers into a gitignored run directory, a missing archive
summary. Same shape each time — the run wrote the fact, the copy dropped it.

```bash
python -m experiments.llm_eval.promote \
  --results experiments/llm_eval/results_holdem --run <UTC stamp>
```

It gzips each transcript, carries its `.treatment.json` across, writes an
archive summary whose pointers are repo-root-relative (the form
`tests/test_layout.py` resolves and checks `git ls-files` against), and
regenerates `AUDIT.txt`. `--run` is
repeatable because one experiment is not always one invocation. It REFUSES a
run whose sidecar is missing, a matchup that appears in two runs, and runs that
name different games — each of which would produce an archive that reads
complete and is not. The property it exists for:
*promote, delete the run directory, and the archive still identifies its own
game* — the state a fresh clone is in.

Transcripts are **not regenerable** — they hold real model responses, which are
not deterministic — so the archive is the record, not a cache.

**Resuming** needs `--run-dir` and a `--matchup`, since `resume_from` appends to a
transcript an earlier invocation wrote:

```bash
python -m experiments.llm_eval.run_eval \
  --run-dir experiments/llm_eval/results/runs/<stamp> \
  --matchup llm_cheap_reason_first_bluffer
```

The runner refuses to overwrite a non-empty transcript for a matchup that is not
resuming, and refuses to append when the **treatment** changed — the arm, the
model, the rendering flag, an opponent's `bluff_prob`. Matching seeds are not the
same thing as the same experiment.

---

## Budget

`config.yaml` carries a `token_budget` (input tokens, output tokens, dollars),
checked between games. The runner stops cleanly and records the partial N plus
the reason. `max_decisions` bounds a single game, because one Cheat episode can
be a material fraction of a budget.

`window:` says how much spend a cap counts. Every billed call is appended to
`<results_dir>/spend/log.jsonl` as it happens, and the window decides which of
those lines the ceiling is measured over:

| `window:` | the cap bounds |
|---|---|
| `invocation` (default) | this process, as the in-memory counters always did |
| `day` | everything the tree billed on this UTC date |
| `<N>h` (`24h`, `720h`) | everything it billed in the last N hours |
| `all` | everything it has ever billed |

So a day's work is boundable, not just one run. The log is re-read before every
game, which is what makes two invocations against one tree share a ceiling
rather than each getting its own — to within one game apiece, since both can
pass a check the pair then crosses (issue #424). It is operational, never evidence.

A cap bounds one log, and the run prints which one it is using. The default is
one per results tree, and a tree is one game's output — so `spend_log:` points
several configs at a single file when what you want bounded is an account
rather than a study. Set it on **every** config in the campaign: one left out
writes to its own tree-local log, which the campaign's ceiling never reads.

The default location is gitignored. A `spend_log:` elsewhere is yours to
place, and this repo is public — the log carries per-model token counts,
dollar figures and timestamps, so put it outside the repo or add your own
ignore rule.

Two things a window does not stop. A matchup whose roster names no model is
never capped, because it cannot spend — which is what keeps `rule_vs_random`
runnable with no key and no credit. And `--smoke` is recorded but not capped:
it is the diagnostic you reach for *because* a ceiling stopped the work.

Four figures name money here, and they are not the same: a matchup block's
`usage` is that matchup's delta, its `run_total` is the model's running total,
`summary.json`'s `run_totals` is one invocation's, and the spend log is the
tree's across all of them.

Read `games_truncated` before quoting a win rate. Truncation is not
missing-at-random: games run long exactly when nobody is shedding.

---

## The third game — heads-up limit Hold'em

The harness plays three games. Everything game-specific lives in a per-game
module (`kuhn.py`, `holdem.py`) reached through two registries: `GAME_TEXT` in
`agents.py` names the rules text and renderer a decision reads, and `GAME_KEYS`
in `metrics.py` maps each registered OpenSpiel short name to its metrics. All the
rest — the referee, the providers, the transcript format, the budget, and the
win-rate/fallback/token statistics — is game-generic and was not touched to add
either the second game or the third.

```bash
# Baseline separation. No API key. ~10 seconds for 400 hands.
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_holdem.yaml --matchup rule_vs_random

# Everything, including the LLM matchups.
python -m experiments.llm_eval.run_eval --config experiments/llm_eval/config_holdem.yaml

# The independent recomputation. `--game` is required for a non-Cheat
# transcript: a game's rate table run over another game's data prints
# `0 / 0 = None` for every rate and reads like a clean audit.
python -m experiments.llm_eval.verify --game cardlang_holdem_heads_up \
  --dir experiments/llm_eval/results_holdem/transcripts
```

**Output goes to a separate tree**, `results_holdem/`. `study.py` and `verify.py`
default to `results/transcripts`, the curated Cheat archive; another game's
transcripts inside that glob would silently fold poker hands into the published
Cheat numbers.

**What is measured, and what is not.** Win rate, mean chip delta, and
offer-conditioned action rates (`fold_rate` is folds over the decisions where
folding was *legal* — over all decisions it would mix "declined to fold" with
"could not fold"). Deliberately **no deception metric**: Cheat's
`provably_false` works because a claim is checkable against the observer's own
cards, and a raise has no such check. A bluff ground truth for poker is separate
work and inventing one here would be a number with nothing behind it.

**Read mean chip delta, not win rate.** Heads-up with two forced blinds, a
player can win a minority of hands and still finish ahead. The first version of
this baseline did exactly that — 33.8% of hands won, +43 chips over 400 — which
is why `tests/test_holdem.py::test_the_baseline_beats_random_on_chips` asserts
the baseline's edge in **chips**, and why win rate alone could not have caught
it.

To add a fourth game: write its module, add a row to `GAME_TEXT` and to
`GAME_KEYS`, and add a config. `game_text` and `game_key` each refuse an
unregistered game rather than defaulting to Cheat's, and
`experiments/llm_eval/tests/test_seat_fairness.py::test_every_harness_game_is_covered` fails if the two
registries name different sets — so a game registered in one and forgotten in the
other cannot run half-configured.

### What it found

One invocation, 2026-08-04T06:09:30Z to 07:11:50Z — **62 minutes**, **$6.33**.
Every rate below recomputes from the committed archive with the command above.

| matchup | N | mean net chips/hand | *t* | win rate | fallback |
|---|---|---|---|---|---|
| rule vs random | 400 | **+1.35** ± 0.80 | +3.31 | 0.513 ± 0.049 | 0.0000 |
| Haiku 4.5 vs random | 200 | +0.41 ± 0.78 | +1.02 | 0.465 ± 0.069 | 0.0000 |
| Haiku 4.5 vs rule | 200 | +0.68 ± 0.86 | +1.54 | 0.505 ± 0.069 | 0.0000 |
| Sonnet 5 vs rule | 200 | **+1.21** ± 0.96 | +2.47 | 0.545 ± 0.069 | 0.0000 |

Intervals are 95%; `t` is over the per-hand chip delta with seats alternating.
No game truncated.

**Two claims survive their intervals, and only two.** The rule baseline beats
random (*t* = 3.31). Sonnet's edge over that baseline is *marginal* (*t* = 2.47,
p ≈ 0.014 two-sided) and was **not pre-registered**, so it is suggestive rather
than established. Everything else — Haiku against either opponent, and Sonnet
against Haiku (+0.53 ± 1.29, both measured on the same baseline) — sits inside
noise.

**Haiku did not establish an edge over random**, which is the sentence to use
rather than "Haiku lost". Its action profile says why: it checks 91% of the
times checking is free and bets 11% of the times betting is available — a nearly
pure check/call posture. Sonnet's is much more balanced (56% check, 53% bet).

**The fallback rate is 0.0000 across all 1,511 model decisions.** No response
failed to parse twice, at either model, on the first version of the rules text —
so nothing here is a comprehension artifact, and the prompt needed no iteration.

**The seating confound (issue #233) is structurally present in this game, and
its magnitude was below detection at these sample sizes.** Two separate facts,
and the archive above rests on the second.

`_build_seats` ties seat parity to seed parity, so where the deal dominates the
outcome one roster position can be dealt systematically better cards. A single
Hold'em hand *is* deal-dominated, so this is the at-risk shape, not the safe one
— and `experiments/llm_eval/tests/test_seat_fairness.py::test_the_unbalanced_scheme_really_does_favour_a_
position[cardlang_holdem_heads_up]` passes, which says exactly that: under the
unbalanced scheme the two roster positions see *different multisets of dealt
cards*. That check is exact and needs no sample size, which is why it settles a
question three statistical probes could only bound.

What the probes bound is the SIZE, and the archive was produced under the
unbalanced scheme, so this is the number that matters for reading it:

| probe | result |
|---|---|
| focus seat wins the showdown on a pure check-down (N=400) | 0.4817 (−0.72 SE) |
| identically-policied random vs random, rotation on (N=800) | −0.415 ± 0.470 |
| identically-policied rule vs rule, rotation on (N=800) | +0.276 ± 0.654 |

The two agent probes point in **opposite** directions and neither reaches 2 SE.
Re-running the free baseline under balanced seating gives **+1.14 ± 0.54,
t = 4.12** against the published **+1.35 ± 0.80, t = 3.31** — same conclusion,
tighter interval, point estimate inside both. So the imbalance is real but too
small to move these numbers at N = 200–800; the published result stands and its
residual is bounded by those probes rather than shown to be zero.

`config_holdem.yaml` now sets `balanced_seating: true`, so every future run is
unbiased by construction instead of by measurement.

### What a game costs to add

The point of the exercise. Split by what a *third* game would and would not pay
again:

| | files | +lines | −lines | paid again per game? |
|---|---|---|---|---|
| corpus game (`.cardlang`, twin, primitive, proof + playout tests, 4 registry rows) | 12 | 932 | 0 | yes |
| harness **seam** (registries, referee/metrics/agents/verify/study, their tests) | 13 | 633 | 57 | **no — one-time** |
| harness **game module** (rules text, infostate parser, baseline, config, its tests) | 4 | 785 | 0 | yes |
| docs | 1 | 61 | 5 | yes |

So a third game costs roughly **1,700 lines** and none of the 633-line seam.

Runtime cost, per matchup rather than blended — the two Haiku matchups differ in
decisions per game, so one figure for "Haiku" would not be comparable to the
`--estimate 5` recon, which was run against `vs_rule` alone:

| matchup | calls | $/game |
|---|---|---|
| Haiku vs random | 450 | $0.0050 |
| Haiku vs rule | 534 | $0.0059 |
| Sonnet vs rule | 534 | $0.0208 |

Against **~$1.10/game for a Cheat episode**: a Hold'em hand is 2–3 model calls
where a Cheat episode is ~210.

Dollars are **tokens × the list-price table in `providers.py`**, not a billing
figure. The $6.33 above is the main invocation; the smoke ($0.0006) and the
`--estimate 5` recon ($0.0264) bring the session to **$6.36**.

## Adding an experiment

Add a matchup to `config.yaml`. To vary the response format, add a `ResponseArm`
to `prompts.RESPONSE_ARMS` (instruction plus its matching retry note, which cannot
vary independently) and name it with `arm:` on the agent. Copy the control's block
verbatim and change one key, so the delta is attributable.

Pre-register the endpoint in `compare.PRIMARY_ENDPOINT` **before** looking at the
data: ten rates tested at 0.05 give ~40% odds of a false positive, so only the
registered endpoint carries `*`.

---

## Layout

Shared — nothing here knows which game is being played:

```
agents.py      Agent protocol + DecisionView; Random, Rule, Nash and LLM agents
prompts.py     build_prompt (pure), response arms, response parsing
providers.py   Model-API abstraction (Anthropic, Fake), usage and pricing
referee.py     Game loop, transcript, replay reconstruction
layout.py      Per-run output directories vs the curated archive
run_eval.py    CLI, config, budget, cost estimation
metrics.py     Per-decision facts + aggregates, dispatched by game
```

Cheat's half:

```
infostate.py   Pure parser over the engine's information-state string
render.py      Information state as English, plus its inverse for round-tripping
verify.py      Independent recomputation; --deep replays, --order audits an arm
compare.py     Two matchups side by side, with the pre-registered endpoint
study.py       Rebuild the study summary + figure from the archive
figure.py      The one matplotlib figure
config.yaml    Matchups, N, seeds, models, token caps
```

Kuhn's half:

```
kuhn.py        Parser, rules text, renderer, the EXACT solver (best response,
               exploitability, the equilibrium family, the noise floor) and metrics
verify_kuhn.py Independent policy extraction + the pre-registered sign test;
               cross-checks the solver against the engine's own returns
config_kuhn.yaml     Matchups, N, seeds, models, token caps
PREREGISTRATION_KUHN.md   Endpoint and prediction, dated before any model ran
```

Hold'em's half:

```
holdem.py      Rules text, information-state parser, a coarse hand read, the
               tight-aggressive baseline, per-decision facts and aggregation
config_holdem.yaml   Matchups, N, seeds, models, token caps
```

**`verify.py` is the single audit entry point for all three games.** It reads the
game off the transcript — the per-record `game` field, the `treatment.json`
sidecar, or the archive's `summary.json` — so the command is the same whichever
archive it is pointed at, and `--game` is only needed for the pre-field Cheat
archive:

```bash
python -m experiments.llm_eval.verify --dir experiments/llm_eval/results_kuhn/transcripts
```

Each game keeps its own output shape rather than being flattened into a shared
one: Cheat and Hold'em report counts then ratios, Kuhn reports exploitability
against the exact equilibrium (delegated to `verify_kuhn`, which also
cross-checks the engine's returns against the solver). `verify_kuhn.py` keeps
its own CLI for the pre-registered A/B, whose Cheat analogue is `compare.py`.

```
tests/         Offline tests (fake provider only, no network), all three games
```

To run Kuhn, point `--config` at its file. The offline acceptance test is

```bash
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_kuhn.yaml --matchup nash_vs_random
```

## License

The pilot evidence (`results/`, `results_kuhn/`, `results_holdem/`) is
CC BY 4.0; the code here stays under the repository license. Terms and
attribution: [LICENSE-pilot-evidence.md](LICENSE-pilot-evidence.md).
