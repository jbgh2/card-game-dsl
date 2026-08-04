# Pre-registration — Kuhn poker A/B

**Written 2026-08-03, before any model was called on this game.** Nothing below
was chosen after seeing data; the only Kuhn transcripts in existence when this
was committed are `nash_vs_nash` and `nash_vs_random`, which involve no model.

The point of writing it down first: ten rates tested at 0.05 give roughly 40%
odds of at least one false positive. Exactly one endpoint carries `*`. Everything
else is a hypothesis generator, reported with its interval and marked `~`.

---

## The manipulation

The same experiment the Cheat harness ran, on a game where the right answer is
known. Control and arm differ in **one config key** — the response format — and
in nothing else: same seeds, same opponent, same model, same sampling
parameters, same rules text.

| | control | arm |
|---|---|---|
| matchup | `llm_cheap_control_nash` | `llm_cheap_reason_first_nash` |
| response arm | `reasoning` | `reason_first` |
| reply shape | `{"action": i, "reasoning": s}` | `{"reasoning": s, "action": i}` |

JSON is emitted in key order, so the control commits to an action before writing
a word of justification and the arm does not. `json.loads` discards key order, so
the two parse identically — the manipulation exists only if the model really
generates the fields in the order asked for.

## Primary endpoint

**`dominated_action_rate`** — the fraction of decisions offering a dominated
action at which one was taken.

A dominated action in Kuhn is folding a King to a bet, or calling a bet with a
Jack. A King wins every showdown and a Jack loses every showdown, so folding the
King returns −1 where calling returns +2, and calling the Jack returns −2 where
folding returns −1 — against **every** opponent strategy. No belief, no read, no
equilibrium reasoning is needed to call these errors, which is why this is the
endpoint rather than a frequency that has to be compared against an equilibrium.

It is also per-decision, so it pairs by seed across the two arms and supports an
exact sign test on the paired differences.

### Registered prediction

**Reason-first LOWERS `dominated_action_rate`.**

Rationale: a dominated action is exactly the error that stating your reasoning
first should catch — "I hold the King, the best possible hand" is the sentence
that makes folding it obviously wrong, and in the control that sentence is
written only after the fold is already committed.

This prediction is the opposite direction from what the Cheat experiment found
for its endpoint, where reason-first made behaviour *worse*. Recorded as a
directional prediction; the test reported is **two-sided** regardless, so a
result in either direction is reportable at the same threshold.

## Secondary, exploratory (`~`, never `*`)

`exploitability`, `exploitability_above_floor`, `chips_per_hand`, `bluff_rate`,
`infoset_coverage`, `win_rate`, `fallback_rate`, per-information-set action
frequencies. Bonferroni over these is 0.05/8.

## Stopping rule

N = 300 games per arm, fixed in `config_kuhn.yaml` before the first call. No
interim look, no extension on a near-miss. If the budget stops a run short, the
partial N is reported as partial and the pairing is restricted to seeds both arms
completed.

## What would make the result unusable

Declared in advance, so it cannot be rationalised afterwards:

- `fallback_rate` above 2% in either arm — the Cheat harness's `neutral` arm died
  this way, at 22%, and was reported as unusable rather than dropped.
- `infoset_coverage` below 1.0 in either arm, since an exploitability number over
  partial coverage is substantially a statement about the fill rule.
- Any difference in the treatment record between the arms other than `arm:`.

## The floor, and why the raw number is not the claim

Exploitability is a non-negative functional of an **estimated** policy, so
sampling noise pushes it up: a player who is exactly at equilibrium still
measures above zero over finitely many hands. Every exploitability figure is
therefore reported beside `exploitability_noise_floor` — the value a
true-equilibrium player would have measured **at the same per-information-set
visit counts**, obtained by resampling from the exact equilibrium. The claim is
the difference, never the raw number.

Measured before any model ran: at 600 games the floor is ≈0.028 chips/hand, and
a real `NashAgent` scored 0.064 against it — inside the null's 95th percentile,
which is what a correct agent looks like at this sample size.
