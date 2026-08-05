# For a reviewer: what was measured, and how to check it

Start here. [`README.md`](README.md) says how to run the harness and
[`BUILDLOG.md`](BUILDLOG.md) is the full build log; this is the short version,
and every number it quotes can be recomputed on your machine in about a minute
with no API key, no credentials, and nothing installed.

---

## The claim

**Three games reach OpenSpiel through one adapter, with each player's
information set *derived* — from declared zone visibility and emitted
observation events — rather than hand-authored per game.** A frontier LLM then
plays each of them through those derived information sets, seeing only what the
rules entitle its seat to see.

That is the claim worth checking, because it is the one the language exists to
support. The three games are chosen so that each is measurable in a way the
others are not:

| | what makes it worth running | what it can measure |
|---|---|---|
| **Cheat** (4p, standard deck) | no solution exists | deception behaviour, against a hand-written baseline |
| **Kuhn poker** (2p, 3-card deck) | **solved** | distance from optimal, in chips per hand, against a floor of zero |
| **Heads-up limit Hold'em** (2p) | neither solved nor deception-shaped | what a *third* game costs once the seam exists |

The harness itself is one implementation: the referee, the providers, the
budget, the run layout, the response arms, and the leak-freeness pins are shared,
and `DecisionView` is game-neutral. What a game adds is its rules text, its
information-state parser, its baseline, and its metrics.

**What a game costs.** Kuhn needed **zero new DSL lines** — it was already in the
corpus and compiled to OpenSpiel with correct information sets on first load —
plus ~1,400 lines of harness, of which about 60% is verification rather than
experiment. Hold'em needed a new 256-line corpus game plus a 548-line harness
module. Neither touched the shared seam.

---

## What each game found

### Cheat — the models discriminate lies, and still lose every game

| | Haiku 4.5 | Sonnet 5 |
|---|---|---|
| detects a **provable** lie | 74/129 = 0.574 | 87/111 = 0.784 |
| detects a merely **improbable** lie | 43/135 = 0.319 | 24/118 = 0.203 |
| discrimination ratio | 1.80x | **3.85x** |
| challenge precision | 0.532 | 0.464 |
| games won (of 10) | **0** | **0** |

Both detect provable lies well above their improbable-lie rate — they are not
challenging at random — and both lose every game, because a wrong accusation
costs the whole pile and they make four to five times as many as the baseline.

**Asking the model to reason *before* choosing made it accuse more, not less.** A
pre-registered A/B on the response format alone: the control asks for
`{"action": i, "reasoning": s}`, and because JSON is emitted in key order the
model commits before writing a word of justification; the arm reverses the two
fields. Challenge rate 0.470 → **0.798**, wrong accusations per game 10.3 →
25.1. All **10 of 10** paired deals moved the same direction, exact two-sided
sign test **p = 0.00195**. The registered prediction was the opposite direction,
which is why the tail is two-sided.

### Kuhn — the models reach the ceiling on non-randomising play

Kuhn is solved, so the baseline is the exact equilibrium and the metric is
**exploitability**: chips per hand a best-responding opponent extracts, zero for
an equilibrium player. **N = 1500 per matchup**, pre-registered.

| | Haiku 4.5 (raw) | Haiku 4.5 (rendered) | Sonnet 5 |
|---|---|---|---|
| exploitability | 0.323 | **0.167** | **0.164** |
| best a *pure* strategy can do | 0.167 | 0.167 | 0.167 |
| gap above that bound | 0.156 | **0.000** | **−0.003** |
| dominated actions taken | 52 / 200 | **0 / 200** | **0 / 200** |
| chips per hand vs equilibrium | −0.157 | −0.072 | −0.018 |

Sonnet and rendered-Haiku land on 0.1667, which is exactly the least any
non-randomising policy can concede — computed by exhausting all 2⁶ pure
strategies per seat. They never take a dominated action (folding a King to a bet,
calling one with a Jack) in 200 opportunities. **They never bluff**, in either
place equilibrium requires it. The whole remaining gap is the failure to mix.

Three hypotheses were registered before any model was called. Two held and **one
was falsified**:

- **The endpoint held overwhelmingly.** Reason-first cut dominated actions from
  52/200 to 0/74; paired sign test **52 down, 0 up, 22 tied, p = 4.4 × 10⁻¹⁶**.
  Note this is the *opposite* direction from the same manipulation in Cheat.
- **A point prediction held.** Exploitability sits on the pure-strategy bound
  within ±0.02 as registered: −0.0026 and 0.0000.
- **The purity claim failed for Sonnet.** It was predicted pure at every
  information set with ≥30 visits; it plainly mixes at two — and mixes exactly
  where equilibrium is *pure*, while playing deterministically in both places
  equilibrium requires randomisation. The corrected claim is not "these models
  cannot randomise" but "they do not randomise where it pays".

### Hold'em — what a third game costs, and two claims that survive

Neither solved nor deception-shaped, and there on purpose. Mean net chips per
hand, seats alternating; intervals are 95%.

| matchup | N | chips/hand | *t* |
|---|---|---|---|
| rule vs random | 400 | **+1.35** ± 0.80 | **+3.31** |
| Haiku 4.5 vs random | 200 | +0.41 ± 0.78 | +1.02 |
| Haiku 4.5 vs rule | 200 | +0.68 ± 0.86 | +1.54 |
| Sonnet 5 vs rule | 200 | **+1.21** ± 0.96 | +2.47 |

**Two claims survive their intervals, and only two.** The rule baseline beats
random. Sonnet's edge over that baseline is *marginal* (p ≈ 0.014 two-sided) and
was **not pre-registered**, so it is suggestive rather than established.
Everything else — Haiku against either opponent, and Sonnet against Haiku — sits
inside noise. **Haiku did not establish an edge over random** is the sentence to
use, not "Haiku lost".

Read chips, not win rate: heads-up with two forced blinds, a player can win a
minority of hands and finish ahead. There is deliberately **no deception metric**
— Cheat's `provably_false` works because a claim is checkable against the
observer's own cards, and a raise has no such check.

---

## Check it yourself

Transcripts of every game are committed, gzipped. The analysis code reads them
with the standard library only.

```bash
git clone <repo> && cd card-game-dsl

# Cheat — recompute every rate above from the committed transcripts
PYTHONPATH=. python3 -m experiments.llm_eval.verify

# Kuhn — every rate, plus the pre-registered sign test
PYTHONPATH=. python3 -m experiments.llm_eval.verify_kuhn

# Hold'em — `--game` is REQUIRED for a non-Cheat transcript
PYTHONPATH=. python3 -m experiments.llm_eval.verify \
  --game cardlang_holdem_heads_up --dir experiments/llm_eval/results_holdem/transcripts
```

Tested against a Python 3.11 with **no packages installed at all**.

Three further checks, each answering a different objection:

```bash
# "Is the analysis marking its own homework?"
#   verify.py and verify_kuhn.py deliberately do NOT call the metrics layer.
#   They re-derive every statistic with their own arithmetic. Kuhn's additionally
#   cross-checks the solver against the ENGINE's recorded returns on all 9000
#   games — separate code paths, so agreement is evidence.

# "Are the transcripts internally consistent?"  (needs the openspiel extra)
PYTHONPATH=. python3 -m experiments.llm_eval.verify --deep

# "Did the Cheat A/B actually manipulate anything?"
PYTHONPATH=. python3 -m experiments.llm_eval.verify --order \
  --matchup llm_cheap_rendered_bluffer --matchup llm_cheap_reason_first_bluffer
#   json.loads discards key order, so both arms parse identically — the
#   manipulation exists only if the model really generated the fields in the
#   order asked for. Control 0/1235, arm 1572/1572.
```

`results*/AUDIT.txt` are the pre-computed outputs, each with a SHA-256 manifest.

**Re-running is not replication.** Model responses are not deterministic, so
re-running draws a fresh sample rather than reproducing these numbers. The
transcripts are the record, not a cache.

---

## Why the measurement is trustworthy

**The prompt is a pure function of four inputs** — static rules text, the
engine's information-state string for that seat, the string renderings of that
seat's legal actions, and the arm's static response instruction. Enforced by
signature, not convention: `build_prompt` takes strings, and the two that vary
with the game arrive in a `DecisionView` carrying only the acting seat's
information-state string, its legal actions, and its own seat number. There is no
game state in scope to leak from.

**That argument is made once and inherited.** `DecisionView` is game-neutral —
Cheat's decision-shape classifier lives in `infostate.decision_kind`, not on the
shared type — so adding a game does not restate the guarantee. Pinned by
`tests/test_prompt_purity.py`: byte-exact agreement between what the provider
receives and `build_prompt`'s output, an `ast` scrape proving `LLMAgent.choose`
reads no attribute outside `DecisionView`'s fields, and a `grimp` import scrape
over the transitive closure of what a decision executes, proving none of it
imports the engine or `pyspiel`.

**The information state is itself derived**, and each game carries its own
indistinguishability certificate in `tests/openspiel_ready/`: two worlds differing
only in hidden content produce byte-identical information states for every
observer, and identical legal actions for the observer to move. Kuhn's is
unusually strong — every node of every one of its six deals, both players'
strings, legal actions and returns compared — because the tree is small enough to
exhaust. Cheat's strongest line is constructive rather than sampled but is a
per-line certificate over a recorded seed set, **not** a proof over all worlds.
The standing caveats are in `docs/open-questions/structural-infoset-proofs.md`.

**Seat fairness is exact, and was not always.** A Kuhn run once reported a model
*beating* an opponent that is provably unbeatable: seat rotation and the deal were
both functions of the game index, and the adapter's seed-to-deal map is not
parity-balanced. `experiments/llm_eval/tests/test_seat_fairness.py` now asserts, for every game in the
registry, that balanced seating deals every roster position an identical multiset
of hands — exact, playing no games, needing no opponent of known value. It also
asserts the unbalanced scheme genuinely differs, so it is a filter and not a
tautology.

**Nulls are calibrated before they are used.** Exploitability of an *estimated*
policy is biased upward, so a player exactly at equilibrium still measures above
zero over finitely many hands. Measured before spending: a real equilibrium agent
scores 0.0297 at N = 1500, 0.0099 at 6000, 0.0031 at 24000 — converging to zero.
Every exploitability figure is reported beside that floor.

---

## What is *not* established

- **No IS-MCTS baseline.** OpenSpiel's `ISMCTSBot` needs `resample_from_infostate`,
  which this adapter cannot implement: its state is `(seed, history)` and the deal
  is a pure function of the seed, so the observer's hand cannot be held fixed
  while opponents' are permuted. Rule-based and equilibrium baselines are
  substituted, and the limitation is recorded as an executable check that fails
  the day the adapter gains that method.
- **Sample sizes differ by an order of magnitude between games**, because episode
  costs do. Cheat is N=10 per matchup — enough for a paired sign test on a
  per-decision endpoint, not for win rates, which are 0/10 everywhere. Kuhn is
  N=1500. Hold'em is N=200–400.
- **Hold'em is not the ACPC configuration** — the big blind cannot raise a limped
  pot (issue #237). Anyone who knows the benchmark will read "heads-up limit
  Hold'em" as the standard rules, so the deviation is stated here rather than only
  in the README.
- **The Hold'em archive predates balanced seating.** The confound is structurally
  present in that game and its magnitude was bounded below detection by three
  probes; re-measuring the free baseline under balanced seating gives +1.14 ± 0.54
  against the published +1.35 ± 0.80 — same conclusion, tighter interval, point
  estimate inside both. Future runs are balanced by construction.
- **Two models throughout**, Haiku 4.5 and Sonnet 5. Opus was configured but never
  run at scale.
- **Exploratory rates are labelled `~`, not `*`.** Only pre-registered endpoints
  carry `*`. Kuhn's largest effect — rendering the information state as English
  halved exploitability — is deliberately *not* promoted to a registered
  hypothesis, because it was found by looking.
- **None of this is a capability claim about the models.** It is about what the
  harness can measure.

---

## Where the detail lives

| | |
|---|---|
| How to run it, and what a game costs to add | [`README.md`](README.md) |
| Kuhn: full result, the falsification, per-information-set policy | [`REPORT_KUHN.md`](REPORT_KUHN.md) |
| Kuhn: what was registered, before the data | [`PREREGISTRATION_KUHN_REPLICATION.md`](PREREGISTRATION_KUHN_REPLICATION.md) |
| Full build log, every decision and defect | [`BUILDLOG.md`](BUILDLOG.md) |
| Pre-computed audits + transcript manifests | `results*/AUDIT.txt` |
| Committed transcripts | `results*/transcripts/*.jsonl.gz` |
| Matchups, models, budget caps | `config.yaml`, `config_kuhn.yaml`, `config_holdem.yaml` |
| Offline tests (no network) | `tests/` |
