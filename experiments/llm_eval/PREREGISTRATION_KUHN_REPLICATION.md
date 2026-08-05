# Pre-registration — Kuhn replication at N = 1500

**Committed before any model was called for this run, and that is checkable.**
This file arrived in its own commit — two files, the pre-registration and the
config's `n`, and no transcript — authored at **2026-08-05T04:03:59Z**. The A/B
run directory is stamped `2026-08-05T04-04-15Z`: sixteen seconds later.

```bash
# the commit that added this file, and what else was in it
git log --diff-filter=A --format='%h %aI' -1 -- experiments/llm_eval/PREREGISTRATION_KUHN_REPLICATION.md
git show --stat $(git log --diff-filter=A --format=%h -1 -- experiments/llm_eval/PREREGISTRATION_KUHN_REPLICATION.md)
```

Use `%aI` — the **author** date. This branch was rebased onto main, which
rewrites committer dates and makes `git log`'s default view show this commit and
the one carrying the transcripts at the same instant. Author dates survive a
rebase; committer dates do not.

The only Kuhn model transcripts in existence at that point are the N = 300
archive from [`PREREGISTRATION_KUHN.md`](PREREGISTRATION_KUHN.md), whose results
are stated below as the predictions being tested.

**Where that archive is now.** Promoting this run overwrote it — one archive
holds the evidence behind the published number, and keeping both would leave a
reader guessing which. The N = 300 transcripts are therefore not in the working
tree, and every N = 300 figure quoted below is checkable only from history, at
commit `1ea30df`:

```bash
git cat-file -p 1ea30df:experiments/llm_eval/results_kuhn/transcripts/llm_mid_vs_nash.jsonl.gz \
  | gzip -dc | wc -l          # 300
```

This is a **replication**, not a fresh exploration. The first run's job was to
find out whether the harness could measure anything; its answers are now
hypotheses with a direction and, in one case, a value. Registering them as such
is what lets this run confirm rather than re-discover.

## Why it exists

The first run was under-powered for what it claimed:

- the pre-registered sign test rested on **8 discordant pairs**, from only 14
  units where both arms faced the choice;
- "the model plays a pure strategy" leaned on information sets with as few as
  **6 visits**;
- exploitability was a point estimate with no interval, against a noise floor of
  0.11 that was itself a large fraction of the numbers reported.

All three scale away with N, and Kuhn costs ~$0.002 per game. This run is 5x.

It also removes a caveat rather than restating one. `balanced_seating` existed
only *after* the first pre-registration, so that run carried a protocol
deviation. It is on from the start here, so this run has none.

## Design

Identical to the first run except for N. Same opponent (the exact equilibrium at
α = 1/6), same models, same sampling parameters, same rules text, same response
arms, same endpoint.

| | |
|---|---|
| N per matchup | **1500 games** = 750 deals x 2 seatings |
| balanced seating | on, from the start |
| matchups | `llm_cheap_control_nash`, `llm_cheap_reason_first_nash`, `llm_cheap_rendered_nash`, `llm_mid_vs_nash` |
| baselines | `nash_vs_nash`, `nash_vs_random` at the same N, so the noise floor is matched |
| expected spend | ~$21 (Haiku ~$3.30/matchup, Sonnet ~$10.80) |

## Hypothesis 1 — the endpoint, now one-sided

**`dominated_action_rate` is LOWER under `reason_first` than under `reasoning`.**

The first run found 8/38 vs 0/14, exact two-sided sign test p = 0.0078, with
every discordant pair moving the same way. The direction is therefore no longer
in question and this test is **one-sided**, which is legitimate precisely
because the direction was fixed by data this run does not reuse.

Both tails are reported regardless. A reversal would be a more interesting
result than a confirmation and must not be hidden by the choice of tail.

Test: exact sign test over paired units. The unit is **(deal seed, seat the
model sat in)** — not the seed, which under balanced seating names two games.

Expected discordant pairs at 5x: ~40.

## Hypothesis 2 — a point prediction, not a direction

**`exploitability_above_pure_bound` is within ±0.02 of zero for `llm_mid` and
for `llm_cheap` on the rendered arm.**

Both measured *exactly* 0.1667 at N = 300, which is exactly the least a
non-randomising policy can concede in Kuhn (1/9 at seat 0, 2/9 at seat 1). The
claim is that this was not a coincidence of a thin sample: these models reach
the ceiling on deterministic play and stop there.

This is a **point** prediction with a stated tolerance, so it can fail in a way
a directional one cannot. It is registered because the first run makes it, and
because a point prediction that survives 5x the data is worth more than any
number of directional ones.

Falsified if either model lands outside ±0.02, in either direction — below the
bound would mean it randomises usefully somewhere, above would mean it makes
errors a pure strategy need not make.

## Hypothesis 3 — the purity claim, now testable

**Both models' policies are pure at every information set with at least 30
visits.**

At N = 300 the thinnest information set had 6 visits, where 6 of 6 in one
direction is consistent with a true frequency of 0.3 the other way. At 1500 the
thinnest should carry ~30, where it is not.

Reported as the count of information sets that are pure, over those with enough
visits to say — never as a bare "the policy is pure".

## Secondary, exploratory (`~`, never `*`)

`chips_per_hand`, `bluff_rate_first_to_act`, `bluff_rate_after_a_check`,
`infoset_coverage`, `win_rate`, `fallback_rate`, the rendered-vs-raw comparison,
and the per-information-set frequencies. Bonferroni over these is 0.05/8.

The rendered-vs-raw effect was the largest in the first run (exploitability
0.327 to 0.167) and is deliberately **not** promoted to a registered hypothesis:
it was found by looking, and promoting it now on the strength of the look is the
thing pre-registration exists to prevent. It stays `~` until a run registers it
in advance.

## Stopping rule

N = 1500 per matchup, fixed here before the first call. No interim look at
either arm. No extension on a near-miss. If the budget stops a run short, the
partial N is reported as partial and pairing is restricted to units both arms
completed.

Baseline matchups (`nash_vs_*`) involve no model and may be inspected freely —
they are the instrument's calibration, not an arm.

## What would make the result unusable

Declared in advance. Note the third: it is the criterion the first run's
"what would make this unusable" list **omitted**, discovered when the endpoint
came close to flooring out.

- `fallback_rate` above 2% in either arm.
- Any difference in the treatment record between the arms other than `arm:`.
- **Endpoint degeneracy** — fewer than 10 discordant pairs, or a control rate of
  zero. Below that the sign test cannot distinguish "no effect" from "no
  variance", and the honest report is that the endpoint floored out, not that
  nothing happened.
- `exploitability_fill_sensitivity` non-zero for a model whose coverage is below
  1.0 — that is the case where the number is partly a statement about the fill
  rather than about the player.

## What this run cannot settle

- **Two models.** Haiku 4.5 and Sonnet 5. Opus is configured but not run;
  at ~$0.03/game it would be ~$45 for one matchup.
- **One opponent.** α = 1/6 is one member of the equilibrium family. A model's
  best response to a different member could differ.
- **Not a capability claim.** Everything here is about what the harness can
  measure and what these policies look like, not about how good the models are
  at poker in general.
