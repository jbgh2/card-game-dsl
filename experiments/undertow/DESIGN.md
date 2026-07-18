# Undertow — design notes

Second original design of this project (experiment, not corpus — the first,
Green Lane, lives in `../green-lane/`). The brief changed between the two:
Green Lane was built small so the solver could hold all of it; Undertow is
built the other way — **few rules, huge emergent state space** — in the
spirit of a "3½ rules" family game that a table can learn in one breath but
that keeps its bite. Solvability is deliberately sacrificed; the pipeline's
job downgrades from *prove* to *probe*.

## The 3½ rules

Four players, standard 52-card deck, deal it all out. Whoever holds the 2♣
leads the first trick.

1. **Follow the led suit if you can.** The trick goes to the highest trump
   in it, otherwise the highest card of the led suit; the winner leads next.
2. **The undertow:** when a trick is gathered, its **lowest card** (earliest
   played breaks ties) names the **trump suit for the next trick**.
3. **Most tricks wins the hand.**

½. The first trick is played with no trump — the tide hasn't come in yet.

That's the whole game. Aces high, twos low — and every 2 is a rudder.

## Why this twist

The design carries one lesson straight out of Green Lane's post-mortem and
the design razor it ended on (*a game is interesting where its stages hold
live choices*):

- In every classic trick-taker there is a famously dead decision: the
  **sluff**. When you're void and can't win, your discard is near-noise.
  Undertow's single rule change points the steering wheel at exactly that
  spot: if everyone follows suit, the lowest card of the led suit sets the
  tide — but a **void player sluffing a low off-suit card steals it**,
  redirecting next trick's trump to a suit of their choosing. The
  classically-dead choice becomes the control move.
- Winning a trick and steering the tide are different currencies paid with
  different ends of your hand. High cards take tricks; low cards take the
  future. "When do I spend my 2s" is a real sequencing problem all the way
  to the last trick — there is no exhaustible token whose spending kills
  the game's tail. Decisions run to the end by construction.
- No player-vs-player lanes, no fairness patches: one shared trick, four
  people in it, fully coupled.

## What "large state space" means here

Full 52-card deal across four hands (~5.4 × 10²⁸ deals), 13 tricks, hidden
hands with void-inference — far past exact solving, which is the point.
Honest consequences: no exploitability number will exist; equilibrium
claims are off the table. The feedback instruments are:

- random-rollout shape (length, branching, seat balance through the 2♣ lead);
- **decision-liveness**: how choice-rich the plies stay by trick number —
  the razor metric;
- the **tide-control probe**: P(win trick t+1 | you set the tide at t)
  against baseline, under random play and under MCCFR-trained play — if
  training widens the gap, the twist is a lever skill actually pulls, not
  chrome;
- tide-steal frequency (how often a void sluff takes the tide) — texture;
- a skill gradient: an MCCFR-trained seat against random seats.

## Names and priors

The lowest-card-sets-next-trump mechanic doesn't match any documented game
we could find (checked the trick-taking surveys and Pagat's invented-games
index). Rotating/dynamic trump exists (turn-ups, contract choices,
last-trick-winner picks); tying it to the *lowest card of the trick itself*
— making the weakest card in every trick the one that writes the future —
appears to be new. "Undertow" is a working title (there are unrelated
board games by that name); the metaphor is load-bearing: the low current
under the wave decides where the next one breaks.
