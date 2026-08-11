# Spec: belief-calibration eval — stated beliefs scored against proof-derived ground truth

**Purpose.** The over-accusation finding says the models challenge on an
uninformative feature (the opponent's "lying history") while under-using the
evidence that settles the question (their own hand). That finding is about
*behavior*. This eval measures the *beliefs*: at challenge windows, elicit the
model's probability that the claim just made is false, and score it against
references derived from the engine's certified information partition. It
separates two hypotheses the behavioral data cannot: **wrong beliefs** (the
model misjudges P(lie)) versus **right beliefs, wrong policy** (it estimates
well and challenges anyway). Nobody else can run this eval, because nobody
else has the partition as a checkable object.

**Claim shape (the paragraph this buys).** The stimulus shown to the model is
a pure function of the proven information-state string, so its elicited belief
is a belief about exactly the information it is entitled to — inherited from
the same proofs as the play harness. The references it is scored against are
functions of that same information state (enforced by test, see §5), so the
comparison is belief-vs-belief at identical access, never belief-vs-oracle.

**Where it lives.** `experiments/llm_eval/` — new modules beside the existing
ones (suggested: `elicit.py`, `references.py`, `score_beliefs.py`, a
`belief_eval:` config section). Zero changes to `cardlang/`, `tests/`, the
grammar, or any closed registry. All conventions of the base spec and the
repo apply unchanged: mypy strict, offline unit tests with the fake provider
only, results promoted deliberately into the archive, every rate reported
with its denominator, a rate over zero opportunities is `null` never `0.0`,
and the README section this adds says what IS.

**Discovery, not assumption.** This spec does not know exact import paths.
The window/claim structure is parsed by `infostate.py` (the provable-lie
machinery); replays come from `referee.replay_views`; the entitlement
analysis lives in `tests/openspiel_ready/worlds.py`. Use what exists — do not
build a parallel pin derivation or a parallel replay path. If `worlds.py`
needs a generalization it cannot express (§6), record it as a finding in the
README rather than silently absorbing it, and put the thin extension in
`experiments/` importing the original unchanged.

**Staging.** Two stages, shippable independently. Stage A needs no new
engine-side machinery and delivers the headline result. Stage B builds the
policy-aware reference and is also engine-side research progress (it is the
paired-history direction of `docs/open-questions/structural-infoset-proofs.md`
made executable). Do not let Stage B block Stage A.

---

## 1. The stimulus bank (no new games)

Archived transcripts are replayable to byte-identical views
(`referee.replay_views`, pinned by `test_game.py`), so the existing archive is
the stimulus set. No new game-play runs.

- **Primary windows:** every challenge opportunity the LLM seat actually
  faced in the archived control matchups (`*_rendered_bluffer` families).
  These pair each elicited belief with the model's *archived action* at the
  same information state.
- **Breadth windows (supplementary):** challenge opportunities faced by the
  rule seat in `rule_vs_random` (N=100, no API cost to have generated).
  No action pairing — calibration data only, cheap and plentiful.

A window record is `(matchup, seed, step, observer)`; everything else is
recomputed from `(seed, history)` at scoring time. Selection is deterministic
given the archive: enumerate all qualifying windows, then subsample to budget
with a fixed recorded seed. Log what was dropped — a silent cap reads as
"covered everything".

## 2. Elicitation

**Prompt purity, same bar as the play harness.**
`build_belief_prompt(rules: str, infostate: str, boilerplate: str) -> str` —
strings in, string out, enforced by signature. The claim under question is
already in the information state (the observation log carries it); the prompt
must not restate it from referee ground truth. A purity test mirroring
`test_prompt_purity.py` is mandatory: determinism, distinguishability,
verbatim pass-through of the raw state string, an `ast`/import scrape keeping
`cardlang` and `pyspiel` out of the elicitation modules.

**The question.** One scalar, primary: *"What is the probability that the
claim just made is false?"* Response JSON: `{"p_false": <0..1>, "reasoning":
"<one or two sentences>"}` — the bounded reasoning string stays, because the
neutral-arm result showed removing the container lets deliberation escape the
envelope. Parse-failure policy identical to the play harness (one retry with
a per-arm note, then a logged fallback); **fallback rate above ~2% of
elicitations is the same publication gate**. A `p_false` outside [0,1] is a
parse failure, not a clamp.

**Exploratory second question (separate call, sampled subset only):**
per-opponent rank-count beliefs ("how many Kings could seat 2 hold —
min/max/best guess"), scored against the Tier-1 support (§4). Keep it out of
the primary endpoint.

**Elicitation-invariance check (small, mandatory before quoting pairings).**
The pairing of elicited belief with archived action assumes asking doesn't
move the decision. Test it at the window level: for ~30 primary windows, ask
the *action* question alone (the play harness prompt, verbatim) and the
action+belief joint form; report action agreement between the two and against
the archived action. High disagreement doesn't kill the calibration result —
it kills the belief-action *coupling* claims, and the README must say which.

## 3. Reference predictors

Score the model against references of increasing strength. Every reference
must be a **function of the observer's information state only** — that is the
property that makes the comparison fair, and it is enforced by test (§5).

- **R0 — the declared prior.** The opponents are `RuleAgent(bluff_prob=b)`
  with `b` in the config; R0 is the constant prediction derived from the
  matchup's declared parameters (forced-lie windows handled per the metrics
  definitions). This is "what a reader of the config would predict."
- **R1 — Tier-1 support (provability).** The existing provable-lie criterion
  (`infostate.py`, both the hand-only and widened forms): when the claim is
  provably false from entitled information, the reference is 1.0; otherwise
  R1 abstains (it is a partial function; report its coverage). R1 is already
  infostate-measurable and already execution-oracle-tested — reuse, don't
  re-derive.
- **R2 — the policy-aware posterior (Stage B).** P(claim false | information
  state, opponents' declared policies), computed by enumerating/sampling
  worlds consistent with the observer's information state and weighting by
  the likelihood of the observed public line under the known `RuleAgent`
  policy. This is the optimal predictor at the model's access level; its
  Brier score is the irreducible floor. It is exact-in-principle because the
  testbed's opponents have dispositions we set — the same property that made
  the disposition-attribution finding measurable.

**The deal-space note.** References are computed in the idealized deal space
(uniform over consistent deals). The adapter samples the root chance node
(`referee.NUM_SEEDS = 4096` addressable deals); that is a uniform subsample
and is the same idealization the readiness proofs run under. State it in the
README; do not attempt to condition on it.

## 4. The decode-pin trap (why R2 is Stage B)

`worlds.py` derives pins for a **fixed history**: any card named by an action
id in the history is decode-pinned, *including hidden played cards no
observer ever saw*. That is correct for the indistinguishability proof (the
replay must stay legal) and **fatally wrong for a posterior**: enumerating
worlds under a fixed history conditions on the actual identity of the played
cards, so "P(claim false)" collapses to the ground-truth 0 or 1 — the
reference would leak the answer it exists to predict.

The observer's true information set varies `(deal, history)` **jointly**: a
world where different physical cards were played under the same public claims
is reached by a *different* action-id line that renders byte-identically to
this observer. So the Stage B sampler must resample identities for every slot
the observer never saw — deal positions *and* unrevealed play choices —
subject to consistency, then **replay the resampled history and assert the
observer's information state is byte-identical to the original and the pause
offers the same legal actions**. That assert-backed shape is the same safety
net `worlds.py` uses: a wrong sampler fails loudly, never silently certifies
a wrong world. Flip-revealed cards, pickups into the observer's own hand, and
projection-pinned identities stay fixed; `RuleAgent` likelihoods come from
reconstructing each opponent's view along the resampled line (one replay per
sampled world serves every window on that line — batch accordingly).

Sampling is Monte Carlo with a recorded seed, recorded sample count, and a
split-half convergence check reported per window class. Budget guidance: a
replay is seconds, so R2 runs on a *recorded subset* of primary windows (~30
is enough for the floor comparison), never on the full bank.

What Stage B buys the engine, independent of this eval: it is the first
executable instance of history-varying indistinguishable-world construction —
the machinery `structural-infoset-proofs.md` names as the generalization the
constructive generator still needs. Build it in `experiments/` first; whether
it graduates into the proof harness is a separate, later decision.

## 5. Machinery correctness obligations

The rigor rules from the repo apply to this measurement code — a reference
that silently reads ground truth is exactly a "vacuously green" instrument.

- **Infostate-measurability test (kills the decode-pin leak).** For a set of
  window pairs whose observer information states are byte-identical but whose
  ground truths differ (construct them with the Stage B sampler; hand-build
  two tiny lines if Stage A ships first), assert every reference emits the
  same value on both. R0/R1 pass trivially by construction; R2 fails this
  test if the sampler conditions on anything decode-pinned-but-unobserved.
- **Brute-force oracle for R2.** On a tiny constructed position (few cards,
  short line), enumerate the consistent `(deal, history)` set exhaustively
  and assert the sampler's estimate converges to the enumerated value.
- **Provable-subset pin.** On windows where R1 fires (claim provably false),
  R2 must return 1.0 exactly — every consistent world has the claim false.
- **Scoring independence.** `score_beliefs.py` recomputes every reported
  number from elicitation records plus `(seed, history)` replays, sharing no
  aggregation code with the collection path — the `verify.py` pattern. Output
  is AUDIT-style: every rate as `numerator / denominator`.

## 6. Endpoints (pre-registered, before the first API call)

**Primary:** Brier score of elicited `p_false` against the referee's
ground-truth label, compared against R0's Brier, on the primary windows —
one number per model. The question it answers: *does the model's stated
belief beat the prior a config-reader would hold?* Secondary, same
registration: elicited `p_false` on the R1-provable subset (target 1.0 —
"does it know what it can prove?"), and the calibration curve in the standard
reliability-diagram bins.

**Belief-action coupling (secondary):** on paired windows, whether the
archived challenge decision is monotone in elicited `p_false` (report the
ranking statistic with its n), and the cross-tab of elicited belief against
the reasoning's history-citation flag from the reason-first analysis — this
is the direct quantification of the disposition-attribution finding.

**Stage B addendum:** model Brier vs R2's Brier (distance from the floor),
and R0-vs-R2 gap (how much policy-aware inference was even available — if
the gap is small, "the model ignores evidence" is not distinguishable here
and the README says so).

Everything else is exploratory and marked `~`. The confound conventions from
the README carry over verbatim: elicited beliefs are a separate measurement
from the archived decisions (state the pairing assumption and the §2
invariance result next to every coupling number), and any claim resting on
what the model *says* is weaker than one resting on what it *does*.

## 7. Budget

One elicitation ≈ one decision call at the archive's measured per-call cost
(≈$0.005 cheap, ≈$0.027 frontier at ~5k input tokens; prompts grow with the
observation log, so re-run `--estimate`-style extrapolation on 5 windows
before committing). Planning envelope: ~100 primary windows per model per
matchup family, plus ~200 breadth windows on the cheap model only —
low tens of dollars end to end. The smoke ladder from the base spec applies
(fake provider → cheap N=5 → cheap full → frontier). R2's cost is CPU, not
dollars; it is bounded by the §4 subset rule. Hard caps in the config; the
runner stops cleanly and records partial N and the reason.

## 8. Out of scope

Second-order beliefs (beliefs about opponents' beliefs); adaptive or learning
opponents; online inference across hands (the k-hand instrument); free-text
belief grading; any live game-play runs; prompt iteration beyond the
fallback gate; mini-Cheat; receipt packaging; any change to `cardlang/` or
`tests/`; graduating the Stage B sampler into the proof harness.

## 9. Acceptance

1. Offline end-to-end: fake provider over `rule_vs_random` breadth windows
   from a fresh checkout produces elicitation records, scores, and the
   figure, no API key.
2. Purity, infostate-measurability, provable-subset, and (Stage B)
   brute-force-oracle tests exist and pass offline; mypy strict-clean.
3. The invariance check (§2) has run and its agreement rates are in the
   README next to the coupling numbers.
4. A completed cheap-model elicitation run over the primary windows, scored,
   with the calibration figure and an AUDIT-style listing in the archive.
5. The README section states the claim paragraph, the pre-registered
   endpoints with their results, honest status (including Stage B's, even if
   "not started"), and the pairing caveat — what IS, nothing about what was
   planned.
