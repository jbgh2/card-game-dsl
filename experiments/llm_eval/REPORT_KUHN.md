# Kuhn poker — the Cheat experiment, run on a game with a known answer

The [Cheat evaluation](REVIEWER.md) measured deception-relevant behaviour through
the engine's *derived* information sets. It could not say how well the models
actually played, because Cheat has no solution: its baseline was a hand-written
heuristic, and every metric was a behavioural proxy.

Kuhn poker is solved. Six deals, five lines, thirty leaves. So the baseline is
the exact equilibrium, and "how well did it play" becomes a number in chips per
hand with a floor everybody can check.

Same harness, same leak-freeness guarantee, same response arms, same
pre-registration discipline. Different game, and a much sharper answer.

---

## The headline

**Both models reach the best score a non-randomising strategy can reach — and
that is still 1/6 of a chip per hand away from optimal, because Kuhn has no
deterministic optimum.**

| | Haiku 4.5 (raw) | Haiku 4.5 (rendered) | Sonnet 5 |
|---|---|---|---|
| chips per hand vs equilibrium | **−0.167** | −0.073 | −0.027 |
| exploitability | 0.327 | **0.167** | **0.167** |
| best a *pure* strategy can do | 0.167 | 0.167 | 0.167 |
| gap above that bound | 0.160 | **0.000** | **0.000** |
| dominated actions taken | 8 / 38 | **0 / 38** | **0 / 38** |
| bluffs a Jack, first to act | 0.000 | 0.000 | 0.000 |
| bluffs a Jack after a check | 1.000 | 0.000 | 0.000 |
| *equilibrium plays these at* | *0.167 / 0.333* | | |

N = 300 games per matchup, 600 for each baseline. Opponent throughout is the
exact equilibrium at α = 1/6. Zero parse fallbacks anywhere.

Read the middle three rows together. Exploitability is zero for an equilibrium
player and rises the more a best-responding opponent can extract. Sonnet and
rendered-Haiku both measure **exactly 0.1667**, and 0.1667 is exactly the minimum
any non-randomising policy can achieve — computed by exhausting all 2⁶ pure
strategies per seat (1/9 for seat 0, 2/9 for seat 1, averaged over a rotating
roster). They are not making mistakes. They have reached the ceiling on
deterministic play, and their entire remaining loss is the failure to mix.

Rendered-Haiku's measured policy is strictly pure. Sonnet's randomises at exactly
one information set (Queen after a check, 0.516/0.484) — and gains nothing by it,
landing on the same bound. Mixing helps only where equilibrium mixes, and that is
not one of those places.

That is a cleaner statement than the Cheat experiment could make about anything,
and it is the point of running on a solved game.

### The mechanism is visible per information set

Sonnet's measured policy. The three "facing a bet" rows pool both seats, which
face the same decision; the equilibrium column gives each seat's target where
they differ.

| information set | n | Sonnet | equilibrium (α=1/6) |
|---|---:|---|---|
| J, first to act | 45 | check 1.000 | check 0.833, **bet 0.167** |
| Q, first to act | 55 | check 1.000 | check 1.000 |
| K, first to act | 50 | bet 1.000 | check 0.500, bet 0.500 |
| J, after a check | 40 | check 1.000 | check 0.667, **bet 0.333** |
| Q, after a check | 31 | check 0.516, bet 0.484 | check 1.000 |
| K, after a check | 49 | bet 1.000 | bet 1.000 |
| J, facing a bet | 32 | fold 1.000 | fold 1.000 |
| Q, facing a bet | 54 | call 1.000 | call 0.500 (seat 0), 0.333 (seat 1) |
| K, facing a bet | 6 | call 1.000 | call 1.000 |

It never folds a King and never calls with a Jack — the two dominated actions —
in 38 opportunities. It plays its value hands correctly. **It never bluffs**, in
either of the two places equilibrium requires it, and it calls every Queen where
equilibrium calls between a third and a half. Those are the leaks a best
responder takes 1/6 of a chip a hand through.

(Seat 0 holding a King and facing a bet never occurs: it always bets its King
first, so it never gets checked-then-bet-at. That is why the last row's n is 6.)

---

## Finding 2 — the pre-registered A/B, and it confirmed

Registered in [`PREREGISTRATION_KUHN.md`](PREREGISTRATION_KUHN.md) and committed
before any model was called on this game. Endpoint: `dominated_action_rate`.
Prediction: **reason-first lowers it**.

Control asks for `{"action": i, "reasoning": s}` — JSON is emitted in key order,
so the model commits before writing a word of justification. The arm asks for the
same two fields reversed. Everything else is byte-identical: seeds, opponent,
model, sampling parameters, rules text.

| | control | reason-first |
|---|---|---|
| dominated actions taken | **8 / 38** = 0.211 | **0 / 14** = 0.000 |
| paired units (deal x seat) | 300 | 300 |
| units where both faced the choice | 14 | 14 |
| paired sign test | 8 down, 0 up, 6 tied | |
| **exact two-sided p** | **0.0078** | |

Every one of the eight discordant pairs moved in the registered direction. All
eight blunders were the same error — calling a bet holding a Jack, the card that
loses every showdown.

**This is the opposite of what the Cheat experiment found.** There, reason-first
made behaviour markedly worse: challenge rate went 0.470 → 0.798 and wrong
accusations per game 10.3 → 25.1. Here it removes a class of blunder outright.
The two are consistent if what deliberation-before-committing buys is *checking a
fact about your own hand* ("I hold the worst card") and what it costs is
*restraint about acting on a suspicion* — Kuhn's endpoint is the first kind,
Cheat's was the second.

**It did not make the model good.** The arm's exploitability is 0.315, barely
below the control's 0.327 and nearly double the pure-strategy bound. It traded
one error for another: it stopped calling with Jacks and started bluffing them
**every single time** (rate 1.000 where equilibrium says 0.167 and 0.333). A
perfectly predictable bluffer is as exploitable as a perfectly predictable
honest player.

### Caveats on this test, stated rather than buried

- The sign test runs on the 14 units where **both** arms faced a
  dominated-action choice. Whether one arises depends on how the arm played
  earlier in the hand, so this conditions on a post-treatment variable. The
  unpaired counts point the same way (8/38 vs 0/14).
- The arms' denominators differ (38 vs 14) because they play differently and so
  reach different situations — the same confound the Cheat report flagged for its
  own arm.
- **Protocol deviation.** The pre-registration fixed N = 300 games per arm
  against a config in which 300 games meant 300 distinct deals. Balanced seating
  was added afterwards, to fix the confound described at the end of this file, so
  300 games now means 150 deals played in both seatings. That halves the number
  of independent deals relative to what was registered. The change was made to
  correct a defect rather than to chase a result, and it applies identically to
  both arms — but it is a deviation from the registered stopping rule and is
  recorded as one. The registered *no-interim-look* rule held: the only interim
  analysis was of `llm_mid_vs_nash`, which is not an arm.
- One model, N=300. The effect is a 300-game result on Haiku 4.5, not a claim
  about models in general.

---

## Finding 3 (exploratory, `~`) — presentation halved exploitability

Same model, same information, same seeds. The only change is whether the model
sees the engine's raw information-state string or the same string rendered into
English by a pure function of it.

| Haiku 4.5 | raw | rendered |
|---|---|---|
| exploitability | 0.327 | **0.167** |
| dominated actions | 8 / 38 | **0 / 38** |
| chips per hand | −0.167 | **−0.073** |

Rendering took the model from "makes blunders" to "plays the optimal pure
strategy". Not pre-registered, so it carries `~` and wants a confirmatory run —
but it is the largest effect in the study, and it is a presentation change, not a
capability one.

---

## Why the numbers are trustworthy

**The baselines behave as theory says they must**, which is the acceptance test:

| | chips/hand | exploitability | dominated |
|---|---|---|---|
| equilibrium vs itself | 0.0000 | at its noise floor | 0 / 174 |
| equilibrium vs random | **+0.160** | at its noise floor | 0 / 166 |
| random | −0.160 | 0.480 | 35 / 67 |

**The solver is checked against the engine, not against itself.** Every reported
game is replayed through the payoff table and compared with the DSL runtime's own
`returns()` — 2400 games, zero mismatches. Independently, the equilibrium
constants are checked by computing their exploitability with the brute-force best
response and asserting it is zero across the whole α family. Neither the
constants nor the best response is trusted alone.

**Exploitability of an *estimated* policy is biased upward**, so a player exactly
at equilibrium still measures above zero over finitely many hands. Every figure
is therefore reported beside a noise floor obtained by resampling from the exact
equilibrium **at the observed per-information-set visit counts**. A real
equilibrium agent measured 0.033 against a floor of 0.018 (p95 0.042) — inside
its own null, which is what a correct agent looks like at this sample size.

For the models the floor turns out not to be the right benchmark at all, and this
matters: **their policies are pure**, so nothing about them is estimated. A
deterministic policy measured over any number of hands is exact. The correct
benchmark is the pure-strategy bound, and that is what the headline table uses.

**A coverage caveat I pre-registered, discharged rather than waived.** The
pre-registration said exploitability would be unusable below 1.0 information-set
coverage, and the model runs came in at 0.75–0.92. But every unvisited set was
unvisited *because of the model's own determinism* — a policy that always bets
its King never reaches "checked with a King and got bet at" — and an information
set unreachable under the fixed player's policy is unreachable for a best
responder too. The evidence is direct: filling the gaps uniformly and filling
them with equilibrium play give **identical** exploitability for every model
measured (`exploitability_fill_sensitivity` = 0.00000). For the mixing Nash
baseline the same quantity is non-zero, so the check is not vacuous.

**Seat fairness is now checked for every game, exactly.** The confound below was
found by noticing an impossible result, which only worked because Kuhn's opponent
has a known value. `tests/test_seating.py` replaces that luck with a property:
under balanced seating each roster position sits in every seat of every deal
exactly once, so all positions must see an *identical multiset of dealt hands*.
It is asserted as equality, plays no games, needs no opponent of known value, and
is parametrised off the harness's own game registry — so a game added later is
covered without its author knowing any of this. Verified by planting the defect
and watching both games redden.

**Leak-freeness is inherited, not re-argued.** `DecisionView` carries a seat
number, an information-state string, and the legal actions with their renderings
— nothing else, enforced by type. Cheat's decision-shape classifier moved off it
so the carrier is game-neutral. `kuhn.py` sits on the decision path, so the
existing import scrape (`test_prompt_purity.py`, via `grimp`) covers it: no chain
from a decision reaches `cardlang` or `pyspiel`. Kuhn's own indistinguishability
certificate is `tests/openspiel_ready/test_kuhn_poker.py`, which compares both
players' information-state strings, legal actions and returns at **every node of
every one of the six deals** — stronger than the sampled certificates most corpus
games carry.

## What is not established

- **N=300 per matchup, one opponent.** Enough for the paired sign test and for
  per-information-set frequencies with real denominators; the α=1/6 equilibrium
  is one member of a family, and a model's best response to a different member
  could differ.
- **Two models.** Haiku 4.5 and Sonnet 5. Opus was configured but not run.
- **Exploitability is measured against the empirical policy**, which is the
  model's behaviour under this opponent, not a claim about its behaviour
  everywhere.
- **Re-running is not replication.** Model responses are not deterministic. The
  transcripts are the record.

---

## Cost and time

| | |
|---|---|
| **New DSL written** | **0 lines** |
| DSL this stands on (already in the corpus) | `kuhn-poker.cardlang` 134 lines + `poker_betting.cardlang` 142 shared |
| New harness code | `kuhn.py` 539, `verify_kuhn.py` 292, `test_kuhn.py` 575 — **1406 code lines** (comments and docstrings excluded; 2218 lines as written) |
| Existing harness modified | **+331 / −65** across 7 files |
| Config, pre-registration, this report | 149 + 95 + 278 lines |
| Wall clock, start to finished report | ~2 h 10 min |
| API spend, the reported run | **$3.74** (Sonnet $2.16, Haiku $1.59) |
| API spend, whole session incl. a discarded sweep | **~$6.35** |

Roughly 40% of the new code is the two verification layers — `test_kuhn.py` and
`verify_kuhn.py` — rather than the experiment. That ratio is the point: the
solver has to be checkable against something that does not share its
assumptions, or its numbers are just assertions.

The Cheat experiment cost roughly $90 to run. A Cheat hand is ~210 sequential
API calls with prompts that grow with the observation log; a Kuhn hand is 1.2
calls at ~1.6k tokens. Kuhn buys about 30x the games for about 1/20th the money,
which is why it can report per-information-set frequencies where Cheat could only
report N=10 win rates.

## Reproduce it

```bash
# baselines, no API key, ~30 seconds
python -m experiments.llm_eval.run_eval \
  --config experiments/llm_eval/config_kuhn.yaml --matchup nash_vs_random

# every number above, recomputed from the transcripts, and the A/B
python -m experiments.llm_eval.verify_kuhn
```

`verify_kuhn` extracts the policies and re-derives every rate with its own
arithmetic rather than calling `kuhn.aggregate`. It shares the solver
deliberately — reimplementing a best response to check a best response checks
nothing — and instead cross-checks the solver against the engine's recorded
returns on every game.

---

## Three defects the run found that the tests did not

Both were found by executing the experiment, not by inspecting it, and both are
now pinned by tests that fail under the old behaviour.

**A model beat an opponent that cannot be beaten.** The first complete run had
Haiku at +0.09 chips per hand against the exact equilibrium — impossible, since
equilibrium play is unexploitable by definition. Seat rotation and the deal were
both functions of the game index, so which seat an agent took was determined by
which deal was drawn, and the adapter's seed-to-deal map is not balanced across
seed parities. The model held a King 112 times to the baseline's 97. Balanced
seating now plays every deal in **every** seating, so the advantage cancels by
construction; Cheat keeps the original scheme, where position rather than cards
is what rotation has to wash out. Every number in this report is from the
re-run.

**A metric moved with the opponent rather than the player.** The bluff rate
pooled "calls a bet holding a Jack" into its numerator — which is a dominated
action, not a bluff — and let the opponent's betting frequency move its
denominator. The identical equilibrium policy scored 0.187 against itself and
0.144 against a random opponent. It is now betting-only and reported per
information set, where nothing outside the agent's own policy can move it.

**The pre-registered test silently ran on half the data.** The paired analysis
keyed on the deal seed. Under balanced seating each seed is played once per
seating, so a dict keyed on the seed kept whichever game came last — 150 of 300
games discarded, and not at random: every survivor had the model at seat 1. The
experimental unit is now (deal, seat), and a repeated unit is a refusal rather
than a silent drop. The corrected control rate is 8/38, not the 8/14 the broken
pairing implied; the sign test itself is unchanged at p = 0.0078, because the
discarded half contained no additional discordant pairs. This one is the repo's
own named silent-cap defect — bounded coverage with nothing saying what was
dropped — and it was caught by a reviewer noticing that `units_shared` was 150
when the transcripts held 300 games.
