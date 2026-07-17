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

## 4. Learned play (outcome-sampling MCCFR)

<!-- RESULTS_MCCFR -->

## Honesty ledger

- No exploitability number exists or will exist at this size; nothing here
  is an equilibrium claim. MCCFR at this budget on a 52-decision 4-player
  game is a *shallow* learner — its numbers are directional.
- The tide probes parse public observation events only (plays, the
  tide-marker move, the gather), reconstructing 12 of each game's 13
  tricks (terminal states carry no logs; the last trick drops out).
- Human fun remains unmeasured by construction; what §2–§4 certify is that
  the decisions exist, persist, and connect to outcomes.
