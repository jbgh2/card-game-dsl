# Undertow — probe report

What the pipeline says about [DESIGN.md](DESIGN.md)'s 3½-rule trick-taker.
The brief inverted Green Lane's: a state space too large to solve
(~5.4 × 10²⁸ deals before a card is played), chosen on purpose, with the
evaluation downgraded from *prove* to *probe*. `PYTHONHASHSEED=0`; adapter
registration samples 2048 deal seeds; scripts in `analyze_undertow.py`.

## 1. Shape (random rollouts, n=300)

Exactly 52 decisions per game (13 tricks × 4 plays), ~70 ms/game through
the re-simulation adapter. Seats balanced under random play (mean tricks
3.18–3.30 against the 3.25 ideal — the 2♣ lead confers no measurable seat
edge at this sample).

## 2. The razor metric: decisions stay live

Share of plies offering a genuine choice (≥2 legal actions), by trick:

| trick | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| live share | .92 | .90 | .89 | .89 | .85 | .84 | .83 | .80 | .79 | .79 | .78 | .78 | 0 |
| mean branching | 5.7 | 5.4 | 5.3 | 5.0 | 4.7 | 4.6 | 4.2 | 3.8 | 3.4 | 3.0 | 2.4 | 1.8 | 1.0 |

This is the number Green Lane failed on (its post-token tail was provably
decision-free) and the reason this design exists: **~4 in 5 plies still
hold a choice in trick 12**; the only forced trick is the last card. The
follow-suit constraint thins options gradually instead of a resource
cliff killing them — and the twist means even a 1-of-2 "dead" follow still
steers the tide.

## 3. The tide is a real channel (random play, 400 games / 4,800 tricks)

- **Tide-steal rate 16.9%**: one trick in six has its next-trump set by an
  off-suit card — a void player's sluff redirecting the future — even when
  nobody is trying. The control channel the design bet on is active, not
  theoretical.
- **P(win next trick | you set the tide) = 0.272** vs 0.25 baseline: under
  random play the steering wheel confers only a whisper of an edge —
  expected, since random hands don't aim it.
- The tide-setter almost never wins the same trick (3.1%) — the two
  currencies (winning now with high cards, steering next with low ones)
  are cleanly separated, as designed.

The decisive question — does *trained* play pull the tide lever harder
than random play? — is §4's job: if learning widens the 0.272-vs-0.25 gap,
the twist is a lever skill actually uses, not decorative chrome.

## 4. Learned play (outcome-sampling MCCFR) — attempted, and the honest lesson

The 60k-iteration MCCFR run was killed after two hours at under 10k
iterations (>700 ms/iteration). The arithmetic is structural, not bad
luck: one outcome-sampling iteration walks one 52-decision trajectory,
every state query re-simulates its whole prefix through the adapter
(O(length²) ≈ 1,350 replays per trajectory at ~1 ms each), and the
replay memo that made Green Lane's solves fast is defeated here by
design — 2,048 sampled deals × 52 plies shatter prefix sharing, which
is precisely what "large state space" means. For calibration, the same
algorithm on Green Lane's full game (2 players, 24 decisions, heavy
prefix reuse) ran at 13–21 ms/iteration and finished 120k in 42 minutes.

Consequence for the pipeline (folded into
`../game-to-artifact-plan.md`'s risk ledger): at this game size,
training-based probes need engine throughput work first (an incremental
stepping driver, or a fixture-pinned fast simulator). The trained-play
tide-amplification question (§3) passes to a training-free instrument —
the determinized-search (PIMC) opponent below.

## 5. PIMC: the fast twin answers what MCCFR couldn't

The pipeline plan's response to §4, built and measured (`fast_sim.py`,
`pimc.py`, `results_pimc.json`):

- **The drift barrier first.** `fast_sim.py` is a hand-written fast engine;
  its only authority is the DSL runtime, enforced by differential fixtures
  exported from the adapter: **120 complete games / 6,240 steps with
  identical legal sets, trick winners, tide cards, and returns**
  (`export_fixtures.py`). The artifact's JS engine passes the same 120-trace
  bar (0 failures, re-runnable from the page console).
- **Strength** (400 games, seats rotated): PIMC with 16 worlds × 3 rollouts
  scores **5.40 mean tricks against three random seats** (baseline 3.25,
  consistent 5.31–5.58 across seats) at **7.4 ms/decision** — roughly the
  cost of a *single* adapter query, which is the whole engine-throughput
  argument in one number. Cross-checked through the real runtime: **5.55**
  over 40 adapter games — the bot integrates against the actual DSL engine
  at full strength.
- **The tide is a skill lever — the §3 question answered.** Under PIMC
  self-play (150 games / 1,950 tricks): P(win next trick | you set the
  tide) = **0.312** vs 0.272 under random play vs 0.25 baseline — competent
  play widens the steering edge ~2.3×. And the tide-steal rate rises from
  16.9% to **26.2%**: skilled players fight over the rudder half again as
  often. The twist is not chrome; it is where the skill goes.

## 6. The playable artifact

`play/undertow.template.html` — a bright-nautical table (regatta cream,
tide dial, ship's log): three PIMC deckhands (24 worlds × 4 rollouts) or an
LLM playing East by relay (the briefing carries exactly East's information:
own hand plus the public table). The page's engine is the fixture-pinned
port above; testing surfaced and fixed one real concurrency defect (a
NEW-VOYAGE mid-game left the old async chain alive and driving stale cards
— now a generation guard, plus `apply()` failing loud on illegal cards
instead of corrupting silently).

## Honesty ledger

- No exploitability number exists or will exist at this size; nothing here
  is an equilibrium claim. MCCFR at this budget on a 52-decision 4-player
  game is a *shallow* learner — its numbers are directional.
- The tide probes parse public observation events only (plays, the
  tide-marker move, the gather), reconstructing 12 of each game's 13
  tricks (terminal states carry no logs; the last trick drops out).
- Human fun remains unmeasured by construction; what §2–§4 certify is that
  the decisions exist, persist, and connect to outcomes.
