# Games implementation — running log

Branch: `games-implementation`. Goal: bring every remaining corpus game from a
`.md` design doc to an executable `.cardlang` that a random-layout playout can
play end to end while preserving the game's invariants (the runtime net).

This file is **process history** — decisions made and questions raised while
building, kept out of `docs/` deliberately (the docs are spec, not history, per
CLAUDE.md). Genuine settled language decisions get promoted into
`docs/decisions.md` (spec voice); genuine open design questions get promoted
into `docs/open-questions/`.

## Starting state

- Executable today: Hearts, Getaway. Runtime is trick-taking-shaped: one
  `Trick` mechanic, card-only chooser, `standard52`-only deck, led-suit-only
  outcome, per-player integer scoring, winner = min/max of a score var.
- Remaining (this branch): Spades, Oh Hell, Schnapsen, Pinochle, Bridge, Skat,
  French Tarot, Cribbage, Seven-Card Stud, Tichu, Coup.

## Strategy (confirmed with advisor)

- Order by distance from the `Trick` engine, not "difficulty":
  - *Trump-trick family* (extend `Trick`): Spades, Oh Hell, Schnapsen, Pinochle,
    Bridge, Skat, Tarot.
  - *Structurally different* (new mechanic each): Cribbage (pegging/counting),
    Seven-Card Stud (betting + hand ranking), Tichu (combination climbing),
    Coup (bluff/influence).
- Widen each Hearts-shaped chokepoint *generically* the first time a game forces
  it — never add a second hardcoded branch beside Hearts.
- Stop only on a true DSL breakdown: grammar/IR can't express a game without a
  change that breaks games already working. New backward-compatible syntax is
  additive, expected work — keep going.
- Each game is "done" only when its playout test would go **red** under a real
  bug (card conservation, point/trick reconciliation, trump resolution,
  termination, correct winner) — not merely "the playout ran".

## Decisions

### Spades (done)

Language extensions added (all generic, reusable across the trump-trick family):
- `trump: <suit>` game declaration; the outcome function
  `highest_trump_or_led_suit` reads it (outcome functions now receive the trump
  suit as a third argument; `highest_of_led_suit` ignores it).
- Partnerships: `partnerships: [[0, 2], [1, 3]]` (teams as seat-index lists), a
  `team` index role for zones and state, `team_of(p)`, a `team` domain for
  `for each team` / `any team`, and team-indexed `captured`/`score`. The driver
  already ranks the winner over whatever the score var is keyed by, so a
  team-indexed score var makes `winner: highest score` rank teams with no
  special case.
- `choose integer in <lo> .. <hi>` expression — the value-general decision seam
  the advisor flagged. The chooser is now typed over `Any`, not just cards.
- `*` multiplication operator (the grammar only had `+`/`-`).
- `TeamPile` zone type; `submit_bid` move type.

Spades-specific design choices:
- Scoring is folded into the `scoring` phase (inline, as Hearts does); the
  `scoring_component` / `apply_components` / `ScoreDelta` subsystem sketched in
  spades.md is **not** built — every Spades component (contract, nil, bag
  overflow) was expressible inline. Deferred until a game genuinely needs
  triggered cross-hand components.
- Dropped the redundant first-trick spade ban; "no leading spades until broken"
  already forbids leading a spade on trick 1 in this variant.
- Termination at +500 **or** −200. The −200 floor is a standard Spades loss
  threshold and it guarantees termination under uniform-random bidding, which
  systematically overbids (two random 0..13 bids sum to ~13 but only ~6.5
  tricks per team are winnable, so contracts almost always fail and scores
  trend negative). Bidding order is irrelevant to invariants under random play,
  so `for each player` is used rather than adding an `each player in turn`
  construct.

Falsifiable invariants in `tests/test_playout_spades.py` (200 games): card
conservation (52 cards, no hand holds cards at end), 13 tricks/hand × 4
plays/trick, **trick-winner correctness recomputed from the cards played**
(would go red under a wrong outcome function), termination at a real threshold,
winner = top-scoring team.

### Oh Hell (done)

Language/runtime additions (generic):
- A per-trick `trump =` argument to `instantiate Trick(...)`: when trump varies
  by hand, the cardlang passes the per-hand trump state var; the mechanic falls
  back to the game-level `trump:` decl when the arg is absent. The trump is also
  surfaced in the `trick_end` trace (a dict key) so playout tests can verify
  trick-winner correctness against a per-hand trump.
- `suit_of(card | zone)` stdlib call — the suit of a card, or of the single card
  in a zone (the face-up trump indicator).

Design choices:
- Variable hand size carried by a `hand_size` state var recomputed each hand in
  `before_each` (a phase-body `let` would not thread into the deal/play
  sub-phases — lets don't cross phase boundaries; state vars do).
- 19 fixed hands via a `hand_index` counter incremented in `after_each`;
  termination `repeats until hand_index >= 19`.
- Dealer hook enforced as a post-bid correction to the dealer's bid (guarantees
  total bids ≠ hand size) rather than a choice-time constraint — see the open
  question on sequential bidding.
- Exact-bid scoring folded inline into the `scoring` phase.

Falsifiable invariants (`tests/test_playout_oh_hell.py`, 100 games): exactly 19
hands, exactly 109 tricks total (the hand-size sequence sums to 109), card
conservation, and per-trick winner correctness against the hand's trump.

### Schnapsen (done)

Generic seams added (reused by later games):
- **Deck table** (`runtime.values.DECKS`): each deck names its suits, ranks, and
  an optional card-point value table. `schnapsen20` = A 10 K Q J × 4 suits,
  values A=11 10=10 K=4 Q=3 J=2 (120 points total). `build_deck` is table-driven.
- **Deck-driven rank strength** (`rs.rank_index`, built from the game's
  `ranking:`): the single source of rank truth. Outcome functions now take a
  `rank_index` and use it instead of the hardcoded `Card.rank_order`, so a
  non-standard deck (A > 10 > K) ranks correctly. `Card.rank_order` is retained
  only for standard-deck *tests*; nothing in the runtime decision path uses it.
- **Card-value census**: `game_end` trace now carries `total_value`, enabling a
  deck-integrity invariant (Schnapsen = 120).
- `FaceDownPile` zone type.

Schnapsen-specific:
- The hand is run by the built-in **`SchnapsenHand` mechanic** — built concretely
  (corpus-first; abstract action-selection at the *second* instance, not the
  first, per the advisor). It implements all five lead moves, marriages (pending
  until the declarer wins a trick), the trump-jack exchange, talon closing with
  the Viennese snapshot, the talon draw (winner first; loser takes the face-up
  trump as the last draw), the strict-follow endgame, and claiming. The random
  chooser picks among legal moves uniformly; the only baked-in strategy is
  claiming 66 on reaching it (so the win-by-claim settlement is exercised).
- The cardlang holds the deal, the four-tier settlement, and termination (match
  to 7 game points, scored down; first to 0 wins).

Falsifiable invariants (`tests/test_playout_schnapsen.py`, 200 games):
card-point integrity (exactly 120 across all zones — catches a wrong value table
or rank order), per-trick winner correctness against the schnapsen20 rank order
*and* trump, and that every hand reduces the total game score (settlement always
fires).

### Pinochle (done)

Generic seams added:
- Deck `copies` (the pinochle48 pack is two of each A 10 K Q J 9 → 48 cards);
  `build_deck` repeats accordingly. Card values A/10/K = 10 (counters), rest 0.
- Phase-level `repeats until` now has the same 10000-iteration backstop the
  statement-level loop has (committed separately) — surfaced by the three Spades
  smoke runs that span at 100% CPU for 14h before the −200 fix.

Pinochle-specific (concrete `PinochleHand` mechanic, like SchnapsenHand):
- Ascending auction (open 50, +10, pass out; capped to stay bounded under random
  bidding), trump declaration (high bidder needs a marriage in the suit, else the
  bid is abandoned and the side is set back), forced **meld** scoring (a pure
  computation — `pinochle_meld`, standard single-pack combos incl. doubles), and
  twelve strict tricks (follow/head/trump/over-trump). The cardlang holds the
  deal, contract settlement, and termination (first team to 150).

Falsifiable invariants (`tests/test_playout_pinochle.py`, 150 games): 48-card /
240-counter conservation, per-trick winner correctness against the pinochle rank
order + trump, and **250 trick points distributed every played-out hand**
(240 counters + 10 last trick) — catches a wrong rank order, value table, or
last-trick award.

This is the **second/third instance** of two recurring gaps now firmly
identified (see open questions): heterogeneous action-selection (auctions) and
strict-trick legality rules. Both still live in concrete mechanics. Bridge is
next and shares both — the point at which lifting strict-trick legality into the
rule DSL (rank comparison + trick-pile query methods) likely pays for itself.

### Bridge (rubber, simplified) (done)

Key finding: **Bridge trick play needs only follow-suit** (no head/trump
obligation), so the thirteen tricks run on the ordinary `Trick` mechanic — no
strict-rule machinery needed. Only the auction is special. So the
"lift strict-trick rules into the DSL" generalization is *not* forced by Bridge
after all; it remains a Pinochle/Skat/Tarot concern.

- `BridgeAuction` mechanic (concrete): ascending bids over C D H S NT with
  double/redouble, ending after three passes follow a call; declarer = first of
  the side to name the final strain. NT contracts pass `trump = none` to the
  Trick (which `highest_trump_or_led_suit` already handles).
- Full rubber scoring in the DSL: below/above the line, game bonus at 100
  (vulnerable 500 / non-vuln 300), rubber bonus, slam bonus, overtricks,
  undertrick penalties, vulnerability = `games_won >= 1`. The winner's score var
  (`total_score`) lives at **game level**, not in the rubber loop, so it is still
  in scope when the driver reads the winner after the phase ends (a real gotcha:
  loop-phase state is popped before the winner read).

Non-termination, handled (the Spades lesson again): random declarers almost
never make high contracts, so an uncapped auction made rubbers take hundreds of
failed hands to crawl to two games (and ran scores into the six figures). Random
bids are capped at level 3 — partscores are made often enough that a rubber is a
realistic ~14 hands. Game-level (3NT/4M/5m) and slam contracts are thus
unreachable under random play; their scoring is implemented but unexercised
(like Spades' +500). `1 - dteam` is used for "the other team" (clean for two
teams; a `the team where` query would generalize it).

Falsifiable invariants (`tests/test_playout_bridge.py`, 40 rubbers): card
conservation, every played hand is exactly 13 tricks of 4 plays, per-trick winner
correctness against the contract trump (incl. none for NT), and termination with
winner = higher total.

### Skat (done)

The most intricate trump game: three trump structures in one game (Suit = four
jacks + trump suit; Grand = four jacks only; Null = no trumps, distinct rank
order), the Reizen call-and-response auction over a fixed bid sequence, the
skat pickup/discard or hand mode, and base×multiplier scoring with matadors,
Schneider, Schwarz, and the overbid rule. Built as a concrete `SkatHand`
mechanic in its own module (`runtime/skat.py`) to keep `mechanics.py` from
bloating; it updates the `score` var directly. Deck `skat32` (A 10 K Q J 9 8 7,
Ace-Ten values, 120 points).

Notes:
- Only the declarer's score moves (the basic DSkV variant). Random declarers
  rarely make 61+, so scores trend negative; the game still terminates (fixed 36
  hands) and the winner is the least-negative — invariants hold, no termination
  risk, so no Spades-style floor needed.
- `GameResult.hands_played` (the driver's `_HandCounter`) counts phases literally
  named `scoring`; Skat has none (the mechanic scores), so that field reads 0 for
  Skat. The actual hand count is the `hands_played` state var / the 36 `hand_end`
  traces. Minor: the counter is coupled to a magic phase name — a candidate
  cleanup, logged below.

Falsifiable invariants (`tests/test_playout_skat.py`, 50 games): 32-card /
120-point integrity, exactly 36 hands, and per-trick winner correctness
recomputed for all three game types (catches a wrong jack ordering, trump
structure, or rank order).

### French Tarot (done) — trump-trick family complete

Generic seam: **non-uniform decks**. `Deck` gained an explicit `cards` list, so
tarot78 (four 14-card suits + a 21-card atout suit + the singleton Excuse) is
buildable without a suits×ranks cross product. Card values vary by rank *and*
suit, so the deck value table is left empty and the mechanic computes points (in
doubled integer units; 78 cards = 182).

Concrete `TarotHand` mechanic (`runtime/tarot.py`): four-level ascending bid,
chien handling dispatched by bid level, eighteen atout-trump tricks with
must-trump/must-over-trump and the Excuse's special routing (stays with its team,
repays the winner a low card), and bouts-threshold / multiplier / petit-au-bout
scoring. Zero-sum: the taker collects 3× the per-opponent amount. poignée
declaration and the Excuse half-point IOU deferral are scoped out (a random
player can't sensibly declare poignée; the IOU is a rare edge).

Falsifiable invariants (`tests/test_playout_french_tarot.py`, 40 games): 78-card
conservation, card points total 182 every hand, **zero-sum score**, fixed 36
hands, per-trick winner correctness (highest atout, else led suit; the Excuse
never wins).

---

**Trump-trick family complete (7/11):** Spades, Oh Hell, Schnapsen, Pinochle,
Bridge, Skat, French Tarot. Remaining are the four non-trick engines: Cribbage
(pegging + the show), Seven-Card Stud (betting rounds + poker hand ranking),
Tichu (combination climbing), Coup (bluff/influence elimination). Each needs a
genuinely new mechanic, not a Trick variant — the real test of "faithful or
flagged".

### Cribbage (done) — first non-trick engine

A pure counting game: discard to the crib, cut the starter, peg to 31, then the
show. Concrete `CribbageHand` mechanic (`runtime/cribbage.py`) with the
combination scorers (fifteens, pairs, runs-with-multiplicity, flush, his nob;
pegging pairs/runs) exposed module-level and **unit-tested against known hands**
(the 29-hand, run multiplicity, flush rules, his nob) — the right falsifiable
check for a game with no card-value conservation total. The mechanic stops the
moment a player reaches 121 (non-dealer shows first), so the winner is exactly
the first to 121.

Bug caught by the conservation invariant: pegged cards were held in a local list
between rounds, so an early win-return mid-pegging dropped them from the census
(48≠52). Fixed by routing played cards through the `play_pile` zone.

Falsifiable: unit tests on the scorers (known values) + a 50-game playout
(termination, exactly one player crosses 121, winner = that player, 52-card
conservation).

### Seven-Card Stud (done) — first betting game

The corpus's first game with **chips**. Rather than build a resource-zone
subsystem, chips are modelled as an integer `stack[player]` state var and the
mechanic does integer betting — total chips are invariant (the falsifiable check
for all the betting/pot logic). Concrete `StudHand` mechanic (`runtime/stud.py`):
antes, bring-in, five betting streets (check/call/bet/raise/fold under fixed
limits, raise-capped), and a showdown with proper **side-pot** distribution by
amount committed (plus a leftover sweep that guarantees chip conservation in the
rare uncalled-over-commit edge). The poker evaluator (`hand_rank`, best five of
seven) is module-level and unit-tested (category order, the wheel, tiebreakers).

The `.md` is a cash game (no winner); the runtime needs a terminal, so the
executable plays until one player holds all the chips. Random fixed-limit play
busts everyone onto one stack in ~80-330 hands. The 4th-street open-pair limit
doubling is simplified out (lower on 3rd/4th, upper on 5th-7th).

Decisions worth noting: `resources {}` / `ChipStack` from the `.md` are **not**
built — chips-as-integers covers every chip game we have; revisit only if a game
needs chips as first-class movable objects with visibility. The `.md`'s 2..8
player range is fixed at 4 for the executable (the driver instantiates
`players.low`).

Falsifiable: evaluator unit tests + a 15-game playout (chip conservation = 400,
card conservation = 52, termination with one player holding everything).

### Tichu (done) — first climbing game

The corpus's first climbing game and first non-(rank,suit) cards (the four
specials). Concrete `TichuHand` mechanic (`runtime/tichu.py`) with a combination
engine (`_combos`: singles/pairs/triples/full houses/straights/consecutive
pairs/four-of-a-kind bombs, Phoenix as a wildcard in pairs/triples/full houses)
and `_legal_follows` (same type+length and higher, or a bomb, or the Phoenix/
Dragon single) — both unit-tested. The climbing trick (three passes end it), the
four specials (Mahjong leads/lowest, Dog → partner, Phoenix wild/−25, Dragon
highest/+25 to an opponent), pushing, finishing order with the double-victory
shortcut, and card-point + Tichu-call scoring are all in the mechanic. New deck
`tichu56` (52 + Mahjong/Dog/Phoenix/Dragon under a `special` suit).

Card points total **100** every non-double-victory hand (40+40+20 from K/10/5,
Dragon +25 and Phoenix −25 cancelling) — the conservation invariant.

Scope reductions (random play, faithful-or-flagged): the Mahjong wish, the
Phoenix as a wildcard inside straights/consecutive-pairs, straight-flush bombs,
and out-of-turn bombs are omitted; Tichu/Grand Tichu are called at a low random
rate so card points (always +100/hand) drive the game to 1000. The endgame
hand-over (last player gives their won tricks to the first-out player) moves the
*whole team's* captured pile rather than only that player's own tricks — captured
piles are team-keyed, so the already-out partner's tricks ride along; card-point
conservation (100/hand) is unaffected, only the within-team attribution.

Falsifiable: combination-engine + climbing-legality unit tests, and a 30-game
playout (56-card conservation, 100 card points every non-DV hand, termination
with the higher team winning).

### Coup (done) — corpus complete (11/11)

The furthest-from-cards game: hidden influence, a coin economy, and actions
resolved through challenge/block windows with bluffing. Concrete `CoupGame`
mechanic (`runtime/coup.py`) runs the entire game to a sole survivor: setup, the
turn loop, the seven actions, nested challenge/block windows, and elimination.
New deck `coup15` (five characters as the rank under one `court` suit, three
copies). Coins are integers; `alive[p]` (1/0) is the winner var so
`winner: highest alive` names the survivor.

Two conservation invariants: total coins = 50 (treasury + players), total
influence = 15 (deck + hands + revealed). Challenges/blocks fire at a modest
random rate; forced Coup at 10 coins guarantees termination.

Falsifiable (`tests/test_playout_coup.py`, 40 games): exactly one survivor who is
the winner, 50-coin conservation, 15-card conservation.

---

## ALL 11 GAMES COMPLETE

Spades, Oh Hell, Schnapsen, Pinochle, Bridge, Skat, French Tarot, Cribbage,
Seven-Card Stud, Tichu, Coup — every corpus game is executable and passes a
random-playout invariant test. No critical DSL breakdown was hit: every game was
expressible as additive, backward-compatible growth (new decks, zone/move/
mechanic registry entries, a few generic seams) plus, for the structurally
different games, a concrete per-game mechanic with its distinctive logic and a
clearly logged expressiveness gap (faithful rules, flagged surface).

## Open questions

- **Representative playouts vs invariant playouts.** Uniform-random bidding
  never reaches Spades' +500 win branch, so that branch is exercised only by the
  −200 path in the test. The random driver's job is invariant-preservation, not
  realism, so this is acceptable — but a light "rational-ish" bidding policy
  would make playouts more representative and exercise win branches. Deferred.
- **`scoring_component` subsystem.** Still unbuilt; Spades didn't need it.
  Bridge/Skat (contract bonuses, vulnerability, rubber) may force a real
  decision here.
- **Heterogeneous lead-action choice in DSL.** Schnapsen's lead moves are handled
  by a built-in mechanic because the DSL can't yet express "choose among move
  types, run the chosen effect" or rank-comparison legality rules
  (`MustHeadIfFollowing`, `MustTrumpIfVoid`). This is the **first** instance;
  the auction games (Bridge/Pinochle/Skat/Tarot) and the back-four engines are
  the others. Per corpus-first, design the generic surface when the second
  instance reveals the shared shape — until then, concrete mechanics + a flagged
  gap, not a premature framework. (Faithful rules, flagged expressiveness.)
- **Sequential bidding / `choose … excluding …`.** Oh Hell's dealer hook and the
  Bridge/Skat auctions want a player to choose in turn order while reading prior
  choices, and to exclude specific candidates. Modelled approximately for Oh
  Hell (post-bid correction). A real `each player in turn from <p>: …` construct
  plus an exclusion form on `choose` is likely needed for the auction games and
  should be designed once, generically, when Bridge forces it.

## Deferred PR-review follow-ups (PR #2)

From the comprehensive review of PR #2. The four "Important" items were applied;
these are the deferred ones, kept here so they aren't lost.

- **`RuntimeState` config-into-constructor.** Six+ config fields (`rank_index`,
  `card_values`, `trump`, `teams`, `team_of`, `rule_index`, `routing_index`,
  `move_type_index`, `deck_zone`, `score_var`) are set on the instance by the
  driver *after* construction, so an under-initialized `RuntimeState` fails deep
  in evaluation rather than at construction. Deferred deliberately: the only
  construction sites today are the driver and two focused unit tests, so every
  clean fix (required kwargs → friction on those tests; a frozen `GameConfig`
  sub-struct → churns ~30–50 `rs.X` read sites) costs more than it returns until
  a *second* real caller exists. **Do it when the OpenSpiel adapter is built** —
  that's the second construction site to design the right shape against.
- **Test-depth (regression nets for already-correct logic).** Add when those
  games are next touched: Schnapsen's six-way settlement *amount* (1/2/3 game
  points — currently only "score falls" is asserted); Spades nil/bag-overflow
  score branches (exercised by random play but not asserted); Coup challenge
  resolution picks the correct loser (a swapped winner/loser still conserves and
  terminates, so it's undetected today). The Bridge analogue was done (the
  scoring recompute test).
- **`team_of` `NewType(TeamId, int)`.** Player ids and team ids are both `int`,
  so the checker can't catch a swapped argument. Marginal; skipped.

## OpenSpiel adapter (Hearts) — decisions to review

Building the Hearts→OpenSpiel adapter (spec:
`docs/superpowers/specs/2026-06-07-openspiel-hearts-adapter-design.md`). Autonomy
granted; decisions worth a later look:

- **Dependency.** Installed `open_spiel 1.6.15` into the venv (a macOS-arm64/cp311
  wheel exists). Added as an optional extra `[openspiel]`, not default `dev`;
  adapter tests `importorskip("pyspiel")` so core CI is unaffected.
- **Chance model.** Using `EXPLICIT_STOCHASTIC` with a bounded set of K seed
  outcomes at a root chance node (rather than `SAMPLED_STOCHASTIC` as the spec
  first said): it's the well-trodden Python path (matches the shipped
  `kuhn_poker` example) and keeps `num_distinct_actions = 52` because chance ids
  live in `max_chance_outcomes`. **Limitation:** only K distinct deals are
  representable. Fine for the proof; revisit if real solving is wanted.
- **Runtime additions (generic, not Hearts-specific).** `play_game` gains a
  `chooser=` parameter (default `random_chooser`), and a `ChooserAbort` exception
  protocol: a chooser may raise it to suspend the playout, and `play_game`
  attaches the live `RuntimeState` before it propagates so the adapter can read
  the paused world. This is the general "steppable adapter" seam.
- **Info-state is Hearts-specific.** The observation rules (trick plays are
  public; pass picks are visible only to their actor) live in the adapter's
  encoder. Encoding = p's current hand + the p-observable action log + scores.
  A no-leak test guards it. A general per-game observation model is deferred.
- **`RuntimeState` constructor refactor stays deferred.** The adapter drives
  games via `play_game` (which constructs `RuntimeState` internally), so it never
  constructs one directly — the two-phase-init concern isn't triggered here
  either. Not folded in.
- **Utility = ZERO_SUM (recentred), not CONSTANT_SUM.** Hearts points are
  constant-sum per hand but the cumulative total varies by game length; returns
  are recentred (`mean − score`) so they sum to zero. `utility_sum=0.0`,
  `min/max_utility = ±200` (generous bounds).
- **Performance: O(n²) re-sim ≈ 3.4 s per random Hearts game** (to 100 points,
  ~1000 decisions). Conformance test runs `num_sims=2`. Fine for the proof;
  if heavier OpenSpiel use is wanted, add memoisation across queries or a
  snapshot/restore path. Review item.

**Outcome:** `pyspiel.random_sim_test` passes and a full rollout via the public
OpenSpiel `State` API plays Hearts to terminal with zero-sum returns and
leak-free perfect-recall info-states. **Invariant #0 is validated** — the IR /
runtime drives real OpenSpiel.
