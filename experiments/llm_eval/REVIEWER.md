# For a reviewer: what was measured, and how to check it

Start here. `README.md` says what the eval is and how to run it, and
`BUILDLOG.md` is the full build log; this is the short version, and every number it quotes can be recomputed on your machine in about a
minute with no API key, no credentials, and nothing installed.

---

## The claim

A frontier LLM plays **Cheat** (four players, standard 52-card deck) through a
game engine that *derives* each player's information set from declared zone
visibility and emitted observation events, rather than having it hand-authored
per game. The model sees only what the rules entitle that seat to see. Against
non-LLM baselines we measure deception-relevant behaviour: how often it lies when
it could have told the truth, how well it distinguishes a provable lie from a
merely improbable one, and how often it calls "Cheat!" wrongly.

Two findings are reported. Neither is a capability claim about the models; both
are about **what the harness can measure**, which is the point of a preliminary
result.

**1. The models discriminate lies, and still lose every game.**

| | Haiku 4.5 | Sonnet 5 |
|---|---|---|
| detects a **provable** lie | 0.574 | 0.784 |
| detects a merely **improbable** lie | 0.319 | 0.203 |
| discrimination ratio | 1.80x | **3.85x** |
| games won (of 10) | 0 | 0 |
| wrong accusations per game | 10.3 | 12.8 |
| *baseline, same table* | *1.4* | *2.5* |

Both models detect provable lies well above their improbable-lie rate — they are
not challenging at random — and both lose every game, because a wrong accusation
costs the whole pile and they make four to five times as many as the baseline.

**2. Asking the model to reason *before* choosing made it accuse more, not less.**

A pre-registered A/B on the response format alone. The control asks for
`{"action": i, "reasoning": s}`; because JSON is emitted in key order, the model
commits to an action before writing a word of justification. The arm asks for the
same two fields reversed. Everything else — seeds, opponents, rendering, model,
sampling parameters — is byte-identical.

| | control | reason-first |
|---|---|---|
| `challenge_rate` (pre-registered endpoint) | 0.470 | **0.798** |
| challenge precision | 0.532 | 0.512 |
| wrong accusations per game | 10.3 | **25.1** |

All **10 of 10** paired deals moved the same direction. Exact **two-sided** sign
test **p = 0.00195**. The registered prediction was the opposite direction, which
is why the tail is two-sided; the eight seeds that did not exist when the endpoint
was registered are 8/8 on their own (one-sided p = 0.00391).

---

## Check it yourself

Transcripts of every game are committed (gzipped, ~1.4 MB total). The analysis
code reads them with the standard library only.

```bash
git clone <repo> && cd card-game-dsl

# Recompute every reported rate from the committed transcripts.
PYTHONPATH=. python3 -m experiments.llm_eval.verify

# The headline A/B, with counts, confidence intervals and exact p-values.
PYTHONPATH=. python3 -m experiments.llm_eval.compare \
  --control llm_cheap_rendered_bluffer --arm llm_cheap_reason_first_bluffer
```

Tested against a Python 3.11 with **no packages installed at all** — no
`pip install`, no virtualenv, no API key. If those two commands print the numbers
in the tables above, the analysis is confirmed end to end.

Two further checks, each answering a different objection:

```bash
# "Is the analysis code marking its own homework?"
#   verify.py deliberately does NOT call metrics.aggregate. It re-derives every
#   statistic with its own arithmetic, so a bug in the metrics layer cannot hide
#   behind a checker that shares its code. Both paths agree to the last digit.

# "Are the transcripts internally consistent?"  (needs the openspiel extra)
pip install -e ".[dev,openspiel]"
PYTHONPATH=. python3 -m experiments.llm_eval.verify --deep
#   Replays each game through the engine from (seed, history) and recomputes
#   every per-decision fact from scratch, asserting the replay matches the
#   recorded transcript at every step.

# "Did the A/B actually manipulate anything?"
PYTHONPATH=. python3 -m experiments.llm_eval.verify --order \
  --matchup llm_cheap_rendered_bluffer --matchup llm_cheap_reason_first_bluffer
#   json.loads discards key order, so the two arms parse identically — the
#   manipulation exists only if the model really generated the fields in the
#   order asked for. Read `reasoning_before_action` in each block: the control
#   is 0/1235, the arm 1572/1572.
```

`results/AUDIT.txt` is the pre-computed output of all of the above, with a
SHA-256 manifest of every transcript.

**Re-running is not replication.** Model responses are not deterministic, so
re-running the experiment draws a fresh sample rather than reproducing these
numbers. The transcripts are the record, not a cache. Re-running costs roughly
$90 and needs an API key; `README.md` has the commands and the budget controls.

---

## Why the measurement is trustworthy

The prompt shown to the model is a pure function of exactly four inputs: static
rules text, the engine's information-state string for that seat at that state,
the string renderings of that seat's legal actions, and the arm's static
response instruction. This is enforced by signature, not convention —
`build_prompt(rules: str, infostate: str, legal_actions: list[str], response: str)`
takes strings, and the two of those four that vary with the game reach it
through a `DecisionView` carrying only the acting seat's information-state
string, its legal actions with the engine's renderings of them, and its own seat
number (the rules text and the response instruction are module constants). So
there is no game state in scope from which hidden information could leak.

The information state is itself derived, and for Cheat
`tests/openspiel_ready/test_cheat.py` **certifies, on recorded lines and seeds,
with the coverage manifest in the proof module**, that two worlds differing only
in hidden content produce byte-identical information states for every observer,
and identical legal actions for the observer to move. The strongest of those
lines is constructive rather than sampled: the pinned card set is derived from
the line itself, the *entire* remaining hidden set is permuted across the other
hands, and the line is asserted to have actually fired Cheat's hidden-content
channel before the certificate counts. That is a per-line constructive
certificate over a recorded seed set — **not** a proof over all worlds, and not
a claim about seeds nobody ran. Every passing run records what it covered
(`CARDLANG_PARTITION_REPORT`); the standing caveats are in
`docs/open-questions/structural-infoset-proofs.md`.

On those lines, two states the acting player cannot distinguish therefore
produce byte-identical prompts: the information states agree, the legal action
ids agree, and their string renderings are a function of the action id and the
game alone (`tests/openspiel_ready/test_action_strings.py`). Any advantage the
model shows there is an advantage over information it is entitled to. The same
holds for the baselines, which decide from the same `DecisionView` — so the
head-to-head is between policies, not access levels.

Pinned by `tests/test_prompt_purity.py`, including byte-exact agreement between
what the provider receives and `build_prompt`'s output on both arms, an `ast`
scrape proving `LLMAgent.choose` reads no attribute outside `DecisionView`'s
fields, and an import scrape over the transitive closure of what a decision
executes — every module reachable from `agents.py` and `prompts.py` by
intra-package import, `render.py` included — proving that none of them imports
the engine or `pyspiel`.

---

## What is *not* established

- **No IS-MCTS baseline.** OpenSpiel's `ISMCTSBot` needs
  `resample_from_infostate`, which this adapter cannot implement: its state is
  `(seed, history)` and the deal is a pure function of the seed, so the observer's
  hand cannot be held fixed while opponents' are permuted. A rule-based baseline
  is substituted. The honest claim is "against rule-based baselines", and the
  limitation is recorded as an executable check that fails the day the adapter
  gains that method.
- **N=10 per matchup.** Enough for the paired sign test on a per-decision
  endpoint; not enough for win rates, which are 0/10 for every model.
- **One model at N=10 for the A/B.** Sonnet has a single game on the arm; it moved
  the same direction and is reported as consistent-with, not as a second result.
- **Exploratory rates are labelled `~`, not `*`.** Ten rates are reported; testing
  all ten at 0.05 gives ~40% odds of a false positive, so only the pre-registered
  endpoint carries `*`. Several `~` rates also carry a confound the flag does not
  describe: challenging more changes the game, so the arm partly manufactured its
  own detection opportunities and its denominators are not the control's.
- **A negative result is included deliberately.** A third arm removed the
  justification field entirely; the model relocated its reasoning outside the JSON
  envelope, the token cap truncated it, and 22% of decisions fell back to random.
  It is reported rather than dropped, and its numbers are marked unusable.

---

## Where the detail lives

| | |
|---|---|
| What it is and how to run it | `README.md` |
| Full build log, every decision and defect | `BUILDLOG.md` |
| Pre-computed audit + transcript manifest | `results/AUDIT.txt` |
| Committed transcripts (gzipped) | `results/transcripts/*.jsonl.gz` |
| Study-level summary, derived from the archive | `results/summary.json` |
| Matchup definitions, models, budget caps | `config.yaml` |
| Offline tests (no network) | `tests/` |
