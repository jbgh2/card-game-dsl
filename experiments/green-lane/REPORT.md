# Green Lane — evaluation report

What the toolchain said about the design in [DESIGN.md](DESIGN.md). Everything
below came out of the repo's own pipeline: the two `.cardlang` files compile
through the ordinary checker, run on the kernel, and reach OpenSpiel through
the same general adapter as the corpus (registered path-based by
`glcommon.py`, chance root shrunk to one seed because the game has no
shuffle). Solvers are stock OpenSpiel (`cfr`, `exploitability`,
`outcome_sampling_mccfr`). `PYTHONHASHSEED=0` throughout.

## 1. It runs, and the information sets are right

`smoke.py` — 200 random playouts per game, all returns exactly zero-sum.

| | full game | mini |
|---|---|---|
| decisions per game | 17.6 (14–22) | 7.4 (6–10) |
| mean branching | 3.14 (max 6) | 2.27 (max 3) |
| P0 mean return (random play) | −1.3 ± σ32.5 | +0.8 ± σ25.6 |
| P0/draw/P1 (200 games) | 79/41/80 | 55/98/47 |

For scale, corpus GOPS under the same adapter: 26 decisions/game, branching
7.0. Green Lane full is a smaller decision problem per game than GOPS but
with far richer information structure (GOPS reveals both bids every round;
Green Lane's waves reveal nothing).

Mid-game information states behave exactly as designed (see the sample in
`smoke.py` output): the merchant's committed card renders as `shipment[0]=[A♣]`
for the merchant and `shipment[0]=#1` for the inspector; waved cargo lands in
a count-only warehouse; fines and tokens are public state.

`proofs.py` — the experiment-local counterpart of `tests/openspiel_ready/`
(the corpus harness's generic 2-player swap pairs a hand against the un-dealt
deck, which is empty here; Green Lane's hidden information is
choice-generated, so the meaningful properties are proved directly):

- **Shipment indistinguishability**: histories differing only in the
  merchant's concealed choice are byte-identical to the other player, with
  identical legal actions — 2767 forked pairs (full) + 293 (mini), all agree;
  the merchant's own states all differ.
- **Warehouse opacity**: after both variants are waved through and an
  identical continuation is played, the other player's information state
  stays byte-identical for the rest of the game — 259 + 102 later-ply checks.
- **Perfect recall**: observation logs append-only along playouts.
- **Seed non-observability**: seeds 0 and 99 give byte-identical information
  states everywhere (the game draws nothing from the generator).

No per-game observation code exists — the zone declarations
(`HiddenPile` for shipment/warehouse, `PlayerPile` for cleared/seized, public
integers for tokens/fines) derived all of this, which is the project's thesis
exercised on a game that didn't exist this morning.

## 2. Ground truth: the mini game demands mixed play

`analyze_mini.py` — the mini tree is exactly enumerable: **568 decision
nodes, 576 terminals, 73 + 71 information sets, depth 11**. CFR+ (400
iterations, exact expected-value updates):

| iteration | exploitability (points/game) |
|---|---|
| 1 | 7.750 |
| 50 | 0.724 |
| 100 | 0.339 |
| 200 | 0.212 |
| 300 | 0.123 |
| 400 | **0.064** |

On stakes where one fine is 4 points and the contraband ace swings ~34, a
best response beats the learned profile by less than 0.07 points/game — the
profile is essentially an equilibrium, and that equilibrium is **fair**: the
game value for P0 is **−0.0005 ≈ 0**, despite the asymmetric move order.

The equilibrium is pervasively mixed — 102 of the 144 information sets
reached under it randomize over more than one action (>2% each). The opening
book, read straight off the average policy:

- **Merchant, round 1** (reach 1.0): ship 2♣ / 3♣ / A♣ at **1/3 each** — at
  equilibrium you run the ace immediately a third of the time.
- **Inspector, round 1** (reach 1.0, a single information set — the crate is
  opaque): **inspect 0.333 / wave 0.667**.
- **Round 2 responses**: inspect probability climbs to 0.45–0.60 as the
  merchant's room to hide shrinks. (The *spread* across same-round infosets
  conditions on the responder's own concealed cards — which the shipper
  cannot see, so the shipper faces the average, exactly 0.333 in round 1;
  at an interior equilibrium the responder is indifferent there, so that
  spread is equilibrium-selection residue. The round-over-round *rise* is
  the genuine signal.)
- After surviving round 1 with a decoy shipped, the merchant plays the ace
  vs the remaining decoy at ~50/50.
- The two decoys (2 and 3) are treated exactly symmetrically everywhere —
  they are payoff-equivalent by design (every legal card scores for its
  shipper no matter what), and the solver confirms it. The game's texture is
  entirely in the *timing* of contraband against the token budget.

## 3. No simple rule survives (mini, exact)

`analyze_heuristics.py` + `analyze_exploit.py` — every {shipping rule} ×
{inspection rule} combo, evaluated exactly two ways (mean of both seats,
points/game): against the CFR+ **equilibrium** (deviation loss — how much you
lose if the opponent doesn't adapt), and against an exact **best response**
(what an opponent who knows your rule does to you):

| naive rule | vs equilibrium | vs best response |
|---|---|---|
| ace_first / always-inspect | −0.04 | **−42.00** |
| ace_first / never-inspect | −5.99 | −34.00 |
| ace_first / coin-flip | −0.76 | −35.75 |
| ace_last / always-inspect | +0.02 | **−42.00** |
| ace_last / never-inspect | −6.01 | −34.00 |
| ace_last / coin-flip | −0.75 | −35.75 |
| uniform-ship / always-inspect | −0.01 | −14.00 |
| uniform-ship / never-inspect | −6.00 | −6.00 |
| uniform-ship / coin-flip | −0.75 | −7.75 |
| *CFR+ profile (for scale)* | *0.00* | *−0.06* |

Read together, the two columns are the game's character. The equilibrium
column alone would flatter naive inspection rules — at an interior
equilibrium the inspector is *indifferent* between inspect and wave, so any
rule inside the support ties (that's what mixing means). The best-response
column shows what that predictability actually costs: a **deterministic
shipping order forfeits 34–42 points per game** — the entire score range —
because an adapter catches the ace every time and baits every scheduled
inspection. Even perfectly random shipping with a fixed inspection rule
bleeds 6–14. The safest naive combo loses 6.00/game where the solved profile
loses 0.06. The concealed mixing isn't decorative; it is roughly the whole
game.

## 4. The full game: skill gradient and sustained mixing

`analyze_full.py` — outcome-sampling MCCFR on the full game, 120k iterations
("strong") and 12k ("weak"), then head-to-head play (2000 games per pairing,
seats alternating, mean return ± stderr):

| pairing | result |
|---|---|
| strong vs uniform random | **+3.46 ± 0.75** |
| weak vs uniform random | +0.93 ± 0.74 |
| strong vs weak | **+1.95 ± 0.75** |

A monotone skill gradient: 10× more training more than triples the edge over
random and beats its own earlier self — thinking helps, and *more* thinking
helps more. (For calibration: random-vs-random has σ≈32 per game, and the
per-game swing range is ±82; these are real but modest edges, consistent
with a policy still far from converged — see the caveat below.)

Mixture evidence from 1500 self-play games with the strong policy: **11,493
information sets visited; 75.6% of in-game decisions taken at information
sets where the policy mixes** (>1 action above 5%); mean strategy entropy
0.76 bits. The learned opening book: P0's first shipment spreads over all
six cards (decoys ~0.15–0.24 each, K 0.14, A 0.10 — contraband first ~24%
of the time), and the round-1 response is inspect 0.37 / wave 0.63.

Two honesty notes. First, an MCCFR average policy at this budget is
*evidence of sustained mixing pressure*, not an equilibrium — no
exploitability number exists at this size, so the exact frequencies carry
solver noise. Second, the red-team pass (§7/F2) later proved the baseline
full game **decomposes into two strategically independent lanes** (each
player's merchant-self and inspector-self share no state any rule reads),
so its exact equilibrium is one lane's equilibrium mirrored — the honest
reading of this section is "the sampled solver behaves as the decomposition
predicts", and the deeper fix for the decomposition itself is variant V2
(§8).

## 5. Design-loop lesson: the fine is not the knob

`sweep_fine.py` — regenerate the mini game with fine ∈ {0, 2, 4, 8}, re-solve
each with CFR+ (250 iterations), read the round-1 equilibrium off the average
policy. The expectation was "change the fine, move the bluffing economy". The
data said no:

| fine | P(ship ace, round 1) | P(inspect, round 1) | exploitability @250 |
|---|---|---|---|
| 0 | 0.335 | 0.335 | 0.159 |
| 2 | 0.332 | 0.335 | 0.198 |
| 4 | 0.332 | 0.334 | 0.118 |
| 8 | 0.333 | 0.333 | 0.167 |

The opening mixtures are **identical to within solver residual across a 16×
range of fine stakes** (fine=0 means a false alarm costs the inspector
nothing at all — and they still don't inspect more). The behaviour-setting
resource is the token budget: spending your only token on a decoy hands the
merchant a free lane for the rest of the game, and that opportunity cost —
not the fine — disciplines inspection. The fine reprices outcomes; it does
not reshape play.

That is a genuine design-loop lesson, delivered by the solver in one sweep:
a designer who wants to tune Green Lane's bluffing frequencies must touch
the token economy (counts, refunds, transfers), not the price list. The
variant round below (§8) does exactly that. (The fine=4 row also doubles as
a consistency check: solved through a different file path and an extra memo
layer, it reproduces the §2 run's exploitability trajectory exactly.)

## 6. What the tooling cost

- Writing and checking the two game files: the checker caught one real
  mistake (a card-count query used as a comparison operand needs
  parentheses); everything else passed first try. No new grammar, stdlib,
  or Python was needed for the game itself.
- The adapter re-simulates from the seed per query, which is the right
  correctness trade for the corpus but makes whole-tree solvers expensive.
  Two pure-function memos in `glcommon.py` (on `replay.run` and on the
  information-state string) made exact CFR+ practical without touching the
  package. Worth knowing for any future "solve a cardlang game" work.

## 7. Red-team findings (design critique by agent, no solver)

A dedicated red-team pass over the rules, the DSL text, and the solved
equilibrium found, in decreasing order of weight:

- **F2 — the game decomposes.** No rule reads state across the two
  directions of play, and the score is the sum of the two lanes' margins —
  so the baseline is two independent, mirrored smuggling duels played in
  alternation. Fingerprints: the mini census's **576 terminals = 24²**
  (24 = one lane's 3! shipping orders × 4 inspection patterns), and the
  "fair" game value, which is *forced* by mirror symmetry rather than
  emergent. Your merchant-self and inspector-self never interact — "two
  games in a trenchcoat." This is the deepest structural criticism and the
  target of variant V2.
- **F1 — a docs/implementation mismatch on fines** (prose said "fines
  received", the implementation nets them, so one fine moves the margin by
  2F, not F). The DSL matched the intended rules; DESIGN.md was corrected.
- **F3 — dead choices.** Once the relevant inspector is out of tokens, the
  merchant's shipping *order* into an auto-waved hidden warehouse is payoff-
  and information-irrelevant, yet still offered (fingerprint: the solved
  strategy at the post-seizure infoset is uniform to machine precision).
  Inflates the tree and, for humans, pads the post-climax tail with
  ceremony.
- **F5 — K vs A is a near-non-choice** (catch margins 32 vs 34; swapping
  their timing moves EV by ≤ ~0.6 points). The full game's second
  contraband is a *class*, not a decision. Target of variant V3.
- **F6 — draws are fat.** Every margin is even, 0 is an atom: 49% of random
  mini games draw. `winner: highest` has no tiebreak, so a five-minute duel
  often ends in "nothing happened".
- **F7 — latent threshold drift** in the mini (setup selected contraband
  with `>= 12`, the inspect test used `>= 11` — consistent today, divergent
  under future edits). Fixed: both sites now read identically.
- The human-game critique in one line: the bones are good (public token
  doomsday clock, compulsory shipment, count-only warehouse as the
  card-counting medium), but per-round agency is thin, and the tension arc
  can peak in round 2 and coast.

## 8. Variant rounds (builder agents, exact solves)

Rule variants targeting F2/F3/F5, each implemented by a sub-agent as full +
mini `.cardlang` files in `variants/`, checker-clean, information-set
proofs passed, and exactly solved with CFR+ (300 iterations) through the
same pipeline. All minis compared:

| | baseline | V1 impound | V2 bounty | V3 graded {7,A} |
|---|---|---|---|---|
| targets | — | F5 (decoy identity) | **F2 (decomposition)** | F5 (contraband grades) |
| mini census (nodes/terminals) | 568 / 576 | 568 / 576 | **1128 / 1136** | 568 / 576 |
| game value (P0) | −0.0005 | −0.0015 | **+2.55** | −0.0004 |
| exploitability @300 | ~0.12 | 0.11 | 0.13 | 0.13 |
| mixed infosets (reached) | 102/144 | 102/144 | 216/458 | 102/144 |
| safest naive rule vs best response | −6.00 | −6.33 | −8.67 | **−10.08** |
| round-1 ship mixture | 2/3/A: ⅓ each | 3: .35, A: .33, 2: .32 | A: .36, 2/3: .32 | **A: .37, 2: .35, 7: .28** |
| round-1 inspect | 0.333 | 0.335 | 0.367 | 0.332 |

**V1 (impound: inspected-legal goods score nobody, fine 4→5).** The decoys
finally separate — and in an instructive direction: the *cheap* decoy is
held back (round-1 ship-2 drops to 0.315) because an inspected 2 nets +8
margin against the 3's +6: better bait is saved for higher-inspection
rounds. Everything else (fairness, tree, mixedness) is undisturbed. A
modest, composable texture gain.

**V2 (token bounty: a false alarm hands the spent token to the merchant,
fine 2).** The structural variant, and it does what it set out to do: the
terminal count stops being a perfect square (1136 — the lanes no longer
factor), reached information sets triple, and the coupling is visible in
the equilibrium: at otherwise-matched decisions, a player holding a
freshly-won bounty token inspects at **0.508** where the single-token
holder inspects at 0.376 — behavior in one lane now conditions on outcomes
in the other, which is exactly what "one game instead of two" means.
Naive rules also get punished harder across the board (−8.67 to −38).
The cost: **fairness broke** — game value +2.55 for P0. The rules were
verified faithful, so this is a real property: with a fixed within-pair
order, P0's bounties are always spendable in the same round-pair while
P1's activate a pair later (and die worthless if won in the last pair) — a
first-mover advantage through bounty freshness. Patch tested as V2b below.

**V3 (graded contraband {7, A}).** The clean win of the round. The
equilibrium runs the **ace early and boldly** — round-1 P(ship A) = 0.368
is the *highest* single-card rate, while the 7 defers (0.28 first ship,
0.06 for the second shipper) — "run the diamonds while the threat is
symmetric; the cigarettes ride cheap later." Neither feared degeneracy
appeared: no pure sacrifice-the-7 opening, and the 7 still gets inspected
(late-round inspect rates stay ~0.5). Naive play is punished markedly
harder than baseline: the safest simple rule bleeds **−10.08**/game (was
−6.00). Fairness and tree size unchanged.

### Round 2: composition and the fairness patch

| | V4 = V1 + V3 (composed) | V2b = V2 + delayed bounty |
|---|---|---|
| mini census (nodes/terminals) | 568 / 576 | 956 / 964 |
| game value (P0) | **−0.0005** | +0.66 (was +2.55) |
| exploitability @300 | 0.143 | 0.093 |
| mixed infosets (reached) | 102/144 | 166/354 |
| safest naive rule vs best response | **−10.83** | −8.67 |
| round-1 ship mixture | A: .36, 2: .35, 7: .29 | A: .39, 2/3: .31 |
| round-1 inspect | 0.331 | 0.392 |

**V4 (graded contraband + impound, fine 5).** The composition is clean:
same tree skeleton, value exactly fair, and both parents' signatures
survive — the bold ace (0.360 first ship, the 7 deferred at 0.07–0.29) and
the impound bait-pricing on the decoy. It posts the **largest naive-rule
punishment of every ruleset tested (−10.83/game)** while keeping the 71%
mixed share. Nothing emergent broke it. This is the recommended
human-facing ruleset.

**V2b (bounties activate at the next pair boundary).** The delay verifiably
keeps the coupling (964 terminals — the lanes still don't factor; 354
reached infosets; a player sitting on a bounty-plus-disarmed-opponent
inspects at 0.678 where the matched baseline node sits at ~0.38) and cuts
the first-mover edge **four-fold, +2.55 → +0.66 — but not to zero**: with
an odd number of round-pairs and a fixed within-pair order, bounty
freshness can't fully cancel. Its exploitability (0.093) is the
best-converged of the bounty family, so the residual is real. The bounty
economy is the boldest design and the only one that makes the two roles
one game — but it should be played as an even-count match with seats
swapped, or wait for a further order-balancing iteration.

## 9. Verdict

**What came out of the iteration loop** (every number above is an exact
CFR+ solve through the repo's own checker → kernel → adapter pipeline,
except the full-game MCCFR section):

1. **Green Lane works as designed**: fair, pervasively mixed, with the
   strategic content exactly where intended — concealed timing against a
   scarce, public inspection budget. Its purest property is methodological:
   with no shuffle anywhere, every information set is generated by
   *concealed choices*, and the engine derived them all from zone
   declarations (2767-pair indistinguishability proof, zero per-game
   observation code).
2. **The recommended table ruleset is the V4 composition** — hand
   2/3/4/5/**7**/A per player, contraband {7, A}, inspected-legal goods
   impounded (score nobody, fine 5 compensation), 2 tokens each. It keeps
   the baseline's fairness and mixedness, adds two real decision axes
   (which contraband when; which decoy as bait), and punishes rote play
   hardest (−10.8/game vs −6.0 baseline). Solved exactly at mini scale;
   the full file is written and checker-clean, with the baseline full
   game's MCCFR behaviour as the scaling precedent.
3. **The token-bounty family (V2/V2b) is the structural future**: it is
   the only change that couples a player's two roles (the red team's
   deepest criticism), it visibly rewires equilibrium behaviour, and it
   deepens the anti-naive gap — at a measured fairness cost (+0.66 after
   the delay patch) that match play neutralizes. A further iteration
   (order-balanced pairs, or bounty-caps) is the obvious next experiment.
4. **Design-loop lessons the solver delivered**: the fine is dead as a
   behaviour knob (round-1 equilibrium invariant across a 16× fine range —
   token scarcity does the work); coupling mechanisms buy interaction but
   spend fairness, and the exact price is measurable; and
   "ties-the-equilibrium" is a misleading test of a rule's quality — the
   best-response column is where a bluffing game's depth actually shows.

Residual, honestly held: draws remain fat at ~49% under random play in
every fair variant (a tiebreak like "ties go to more contraband seized" is
future work); the full-scale variants are checker-clean but solved only at
mini scale; and the two-lane decomposition of every non-bounty variant
means their full games, while huge on paper, are exactly two mirrored
copies of a ~16k-leaf lane game.

## 9. Verdict

<!-- VERDICT -->
