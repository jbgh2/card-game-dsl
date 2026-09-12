# Pre-registration — the convention gap on Cheat

**Status: DRAFT on a branch. This is not yet a pre-registration.**

Drafted 2026-09-12 from `belief-calibration-spec.md` and Fukushima, Xiong and
Moradi Pari, *The Convention Gap: Towards Measuring Implicit Communication in
Cooperative AI Evaluation* (arXiv:2609.11489, code at
`github.com/dockmfgit/hanabi-convention-gap`, doi:10.5281/zenodo.21975884).

It becomes a pre-registration when the three decisions in §0 are resolved and
the file lands on `main` ahead of the first run. Nothing below has been run.
Everything below is a proposal to be edited, not a commitment already made.

The existing Cheat archive predates this document and was collected for the
play harness and the over-accusation analysis. Re-using it is legitimate for
the breadth windows, and it is **not** clean for the primary endpoint. See §6.

---

## 0. Open decisions, to resolve before this binds

Each one changes the endpoints. Two of the three are good questions to put to
the authors.

**0.1 — Which decision is scored.** Their actor is uncertain about its own
card. In Cheat the claimant knows exactly what it played, so the uncertain
party is the challenger. The proposal below scores **the challenge window
decision** (call or pass) and not the claim. Scoring the claim would make the
baseline a statement about the challengers' dispositions, which is
policy-dependent and therefore not their construct.

**0.2 — Unrevealed passes.** Their step 1 asks for decisions "whose success is
observable". In Cheat, a lie that draws no call is never found out, so a pass
on an unchallenged lie has a ground truth in the referee's books and no public
resolution. Scoring only windows that someone challenged selects on the
challenge event and biases the sample hard. The proposal is to score every
offered decision against referee ground truth, and to report the
challenged-only subset beside it so the size of the difference is visible.
**Ask the authors which they consider in-construct.**

**0.3 — N, and which matchups.** Fixed in config before the first call, per
the house rule. Left open here because it depends on how fast the sampler in
§3 turns out to be.

## 1. The measurement

Their gap is the mean literal-information failure probability minus the
observed failure rate, over decisions. Transferred to a challenge window:

Let `q` be the literal-baseline probability that the claim just made is false,
computed from the deciding player's information state alone (§3). For one
offered decision:

- `p̂ = q` if the player passed. Passing fails when the claim was in fact false.
- `p̂ = 1 − q` if the player challenged. Challenging fails when the claim was
  in fact true.
- `y = 1` if that decision turned out wrong, `0` otherwise.

`convention_gap = mean(p̂) − mean(y)` over the scored decisions.

A player using only entitled information sits at zero. A player extracting
something real from the public line beats the baseline and scores positive. A
player acting on a feature that carries no information scores **negative**,
which is the direction the archived over-accusation result predicts and is a
case their three Hanabi corpora do not contain.

Every rate is reported as numerator over denominator. A rate over zero
opportunities is `null`, never `0.0`.

## 2. Arms

Three rule arms and the model arms. The rule arms exist to validate the
instrument and are generated offline at no API cost.

| arm | challenger policy | opponent | registered expectation |
|---|---|---|---|
| `L0_literal` | call iff `q > 0.5` | `RuleAgent(bluff_prob=b)`, i.i.d. | gap within the §5 noise floor |
| `L1_history` | `L0` plus the claimant's observed catch rate | `RuleAgent(bluff_prob=b)`, i.i.d. | gap within the floor |
| `L2_positive_control` | `L0` plus the claimant's observed catch rate | a **state-dependent** bluffer whose lie rate varies with a publicly visible feature | gap **above** the floor |
| model arms | the LLM seat | as archived | primary endpoint, §4 |

`L1` is the honest null. Against an i.i.d. bluffer the claimant's history
carries nothing about this claim, so a policy that reads it should not beat
`L0`. That is the same shape as the over-accusation finding, reproduced with a
policy whose information use is fixed by construction.

`L2` is the one arm where beyond-literal information genuinely exists. Without
it the instrument is only validated at zero, and a null on the model arm would
be uninterpretable. This is the local stand-in for their off-belief-learning
ladder, which supplied a designed dose-response their metric could be checked
against.

## 3. The baseline predictor

The literal baseline is **uniform over worlds consistent with the deciding
player's information state, with no weighting by any opponent policy**. It sits
between two predictors the belief-calibration spec already defines. It is
stronger than `R1`, which abstains wherever the claim is not provably false,
and weaker than `R2`, which weights by the known `RuleAgent` likelihood.
Policy weighting is exactly the partner-behaviour feature their step 3 ablates
on purpose, so `R2` is not the right instrument here.

Mechanically this is the Stage B sampler of `belief-calibration-spec.md` §4
with the likelihood term removed, and it inherits that section's trap in full.
Enumerating worlds under a fixed history conditions on the identity of cards
nobody saw, which collapses the baseline to ground truth. The sampler must
resample identities for every slot the deciding player never saw, deal
positions and unrevealed play choices jointly, then replay and assert the
information state is byte-identical and the pause offers the same legal
actions.

Correctness obligations, all from `belief-calibration-spec.md` §5, all required
before any number is quoted:

- **Infostate-measurability.** On window pairs whose information states are
  byte-identical and whose ground truths differ, the baseline emits the same
  value. This is the test that kills the decode-pin leak.
- **Brute-force oracle.** On a tiny constructed position, exhaustive
  enumeration of the consistent `(deal, history)` set, and the sampler
  converges to it.
- **Provable-subset pin.** Wherever `R1` fires, the baseline returns exactly
  `1.0`.

## 4. Primary endpoint

Exactly one endpoint carries `*`.

**`convention_gap` for the frontier model challenger, reported as its distance
from the §5 noise floor, on the i.i.d.-bluffer matchups.**

### Registered prediction

**Negative.** The archived behavioural finding is that the models challenge on
the claimant's lying history while under-using their own hand. If that holds at
the level of outcomes and not only of stated reasons, they fail more often than
their entitled information predicts.

Recorded as a directional prediction. **The test reported is two-sided**, so a
result in either direction is reportable at the same threshold. A gap at the
floor is the interesting negative result and gets the same billing.

## 5. The floor, and why the raw gap is not the claim

A challenger that uses only entitled information does not measure exactly zero
over finitely many decisions. `convention_gap_noise_floor` is the value such a
challenger measures **at the same window counts**, obtained by resampling
outcomes from the baseline itself with a recorded seed.

Every gap is reported beside the floor. The claim is the difference, never the
raw number. Their paper read `+1.57 pp` at its convention-free level and
treated it as approximately zero without publishing a floor. Publishing one is
cheap here and is worth raising with them.

## 6. Secondary, exploratory (`~`, never `*`)

Gap by claim count, the local analogue of their hint-count localisation, since
claims of one card and claims of four carry different literal constraint. Gap
on the `R1`-provable subset, where the baseline is `1.0` and any pass is an
outright error. Gap split by whether the deciding player has eaten the pile,
since that player holds strictly more information than the others at the same
table. The challenged-only subset of §0.2. Per-seat gaps. Bonferroni over
whatever this list is when the file lands.

The archived transcripts were collected before this document existed, for a
different analysis, and the over-accusation finding is already known. That
makes any model number computed from them a **hypothesis check, not a clean
test**. Clean model arms require a fresh run under this registration. If the
budget only permits the archive, the README says so in those words.

## 7. What would make the result unusable

Declared in advance, so it cannot be rationalised afterwards.

- The `L0_literal` arm sitting outside the noise floor's interval. The
  instrument is then wrong and nothing else is reportable.
- The `L2_positive_control` arm not clearing the floor. The instrument cannot
  detect beyond-literal information, so a null on the model arm says nothing.
- The infostate-measurability test failing at any sample count. That is the
  baseline reading the answer it exists to predict.
- `fallback_rate` above 2% in any model arm, the standing house gate.
- Any difference in the treatment record between arms other than the arm key.

## 8. Out of scope

Any change to `cardlang/`, `tests/`, the grammar, or any closed registry. The
cooperative construct in a partnership trick-taker. Visibility ablation, which
recompiles the game with the claim history coarsened. Hanabi, which needs a
language operation for a chosen partial fact about another player's cards and
does not have one. Human play, of which there is no Cheat corpus. Graduating
the §3 sampler into the proof harness.
