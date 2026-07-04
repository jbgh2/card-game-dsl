# Migrating the corpus onto the decision kernel

This is the execution brief for removing the per-game **concrete runtime
mechanics** and expressing their decision logic in the DSL itself, on the
interactive-decision kernel. The design it executes is settled in
[decisions.md](decisions.md), "Interactive decisions: a kernel and an in-DSL
standard library", with the full rationale in
[superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md](superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md).
The discipline (red→green, IR goldens, exhaustiveness) is in
[building.md](building.md). This file is the *order of operations* and the
per-game scope.

It is written to be handed to an implementer. Each workstream states what
capability it adds, the kernel/standard-library pieces it builds, the
checkpoints where a genuine language gap might surface, and its definition of
done.

## The goal, concretely

Four games still hold their decision logic in hand-written Python dispatched by
name in `cardlang/runtime/mechanics.py::instantiate`. Bridge's, Pinochle's, and
Tarot's auctions have been lifted onto the kernel `round` — so `run_bridge_auction`
is gone, and Pinochle and Tarot are both fully kernel (Pinochle: trump
declaration, meld, and the twelve strict tricks; Tarot: the chien handling, the
eighteen atout-trump tricks, and the bouts-conditional scoring — `run_tarot_hand`
and its post-auction `run_tarot_rest` are both gone). Cribbage's whole counting
hand — discard, cut, pegging, and the show — runs on ordinary DSL statements
(filtered movements, `repeat until`, `skip to next hand`), so `run_cribbage_hand`
is gone as well:

- inline in `mechanics.py`: `run_schnapsen_hand`
- separate modules: `runtime/coup.py`, `skat.py`, `tichu.py`

(`runtime/stud.py`, `runtime/bigtwo.py`, `runtime/pinochle.py`,
`runtime/tarot.py`, and `runtime/cribbage.py` remain, but hold no `instantiate`
mechanic — only pure stdlib primitives the DSL calls: Stud's poker evaluator,
seat selectors, and `pot_share`; Big Two's combination engine; Pinochle's meld
evaluator, `pinochle_meld_value`; Tarot's per-card queries, effective led suit,
trick outcome, Excuse-player lookup, and the per-opponent settlement arithmetic;
Cribbage's pegging/show scorers and provenance decoder — `peg_value`,
`peg_pair_points`, `peg_run_points`, `peg_origin_of`, `cribbage_show_value`,
`cribbage_crib_value`.)

This violates the two-layer architecture ([principles.md](principles.md): the
library is *written in the DSL*, not the engine). It also carries **info-set
debt**: a Python mechanic runs its decisions outside the observation-event
stream, so its information sets are not *derived* — the hardest, load-bearing
requirement for the OpenSpiel target ([CLAUDE.md](../CLAUDE.md), "OpenSpiel is the
target…"; [decisions.md](decisions.md), "OpenSpiel compilation";
[design-notes/kernel-extensibility.md](design-notes/kernel-extensibility.md), §6).
Retiring these mechanics onto the kernel closes that debt as well as the
architecture violation. Each migration now has a second, concrete payoff: the
OpenSpiel projection substrate
([superpowers/specs/2026-07-01-openspiel-projection-substrate-design.md](superpowers/specs/2026-07-01-openspiel-projection-substrate-design.md))
derives information sets for any fully-kernel game for free, so a game
leaving its Python mechanic becomes OpenSpiel-ready automatically — register
it in `cardlang/openspiel/game.py:GAMES` and add it to the proof harness
(`tests/test_openspiel_ready.py`) — so "migrated" now means "derived info
sets proven," not just "runs on the kernel." One latent footgun to watch for
as new mechanics migrate: `cardlang/openspiel/infostate.py`'s `_render`
sorts list/tuple-valued state variables before rendering into the
information state, so a future *ordered* list-valued state variable (a bid
history, a play sequence — anything where order itself carries information)
must not be rendered sorted, or distinct information sets that differ only
in order would silently collapse into the same string. The stage is done
when:

- `instantiate` dispatches only to kernel constructs — no per-game name
  branches — and the five remaining game-mechanic modules and the one inline
  `run_*` function are deleted (pure stdlib-primitive modules like `stud.py`,
  `bigtwo.py`, and `pinochle.py` stay);
- all 14 games run on the kernel plus the in-DSL standard library, with every
  `tests/test_playout_*.py` green and **behaviour preserved**;
- IR golden snapshots are regenerated and reviewed;
- `mypy --strict` is clean and no `language-gap` entry is silent (each is zero
  or a named `open-questions/<slug>.md`);
- [decisions.md](decisions.md), [library.md](library.md), and this file are
  updated in lockstep, per the [CLAUDE.md](../CLAUDE.md) operating rules.

The built-in `Trick` mechanic was also engine code, not DSL. Retiring it —
moving Hearts, Spades, Getaway, and Bridge's play onto the kernel `round` (Oh
Hell already used it) — is done as part of the prerequisite below.

## Non-negotiable discipline

These hold for every step; they are what make a 1,800-line deletion safe.

- **Behaviour-preserving.** The Oh Hell trick migration is the precedent: the
  game's playout test and conservation invariants (cards/coins/points balance)
  stay green across the change, with no behavioural diff. Migrate, don't
  redesign.
- **Test-depth nets before risky migrations.** Random playouts never reach
  skill-gated branches (Schnapsen false claims, Spades nil/+500, Coup
  challenge-loser — see [roadmap.md](roadmap.md), "Test-depth regression nets").
  Where a game has such a branch, add an independent-recompute test **before**
  migrating it, or the migration can pass playouts while being subtly wrong.
- **One construct per commit**, red fixture → minimal kernel/grammar/checker
  change → green, IR golden diff reviewed. Constructs are never batched.
- **A definition adds words, not semantics.** Standard-library definitions
  (`auction`, `betting`, `climb`, `challenge`, `block`, `trick`) compose over
  the fixed kernel; they do not introduce control primitives or mutate rules.
  Variation lives in *values along the closed axes*. A genuinely new **axis** is
  a major change requiring explicit sign-off — flag it, don't quietly add an
  engine hook.
- **Promote at the third instance.** A definition stays game-local until roughly
  three corpus games exhibit the same shape, then moves to the shared standard
  library (corpus-first).

## Step 0 — Generalize the `round` kernel (prerequisite)

*The trick-migration portion of this step is built: every trick game (Hearts,
Spades, Getaway, Bridge, Oh Hell) runs on the kernel `round`, the built-in
`Trick` mechanic and the routing-def construct are retired, and `round` carries
the termination axis (`early`) plus round-state exposure. The remaining axes
below (accumulator, order, move vocabulary) land with the workstreams that first
need them — see [roadmap.md](roadmap.md).*

The `Round` node (`cardlang/ast/nodes.py`) is trick-shaped: one card play per
participant plus an `outcome` function. Everything below composes on a
`round` grown to the closed axes from [decisions.md](decisions.md):

- **participants** — actor / others / ring / list
- **order** — turn-from-a-seat / priority / simultaneous
- **accumulator** — a value threaded across steps (high bid, bet-to-match,
  running total, led combination)
- **termination** — a predicate over the accumulator/state
- **typed outcome** — reusing the Stage 1–3 variant/outcome machinery
- **move vocabulary** — not only card plays: non-material `move_type`s (bids,
  passes, actions) chosen via `offer`

Build this, then re-express the existing trick `round` as one configuration of
it with no behavioural change (the same proof Oh Hell already gives). Then
migrate the remaining built-in-`Trick` games onto the kernel `round` —
Hearts/Spades (rule-delta transitions) and Getaway (early termination) — and
delete the built-in `Trick` mechanic. This both retires shared engine code and
exercises every axis before the harder games arrive.

## Workstream 1 — Auctions (Bridge, Skat, Tarot, Pinochle)

Highest leverage: four instances of one shape, so `auction` is promotable to the
standard library immediately on the third.

Build an `auction` definition over `round`: `ring` participants, accumulator =
current high bid + pass state, termination = all-but-one passed (or N
consecutive passes), typed outcome = a contract variant. Then per game, supplying
*values along the axes*:

- **Bridge** — *done.* A two-dimensional bid space (level × strain) plus
  doubling/redoubling, on the auction form of `round`; the typed
  `contract_finalized | all_pass` outcome computes the declarer over the bid
  history. `run_bridge_auction` and its `instantiate` branch are deleted.
- **Pinochle** — *done — fully kernel.* The ascending bid runs on the auction
  form of `round` over a **shrinking participants ring** (`over players where
  not passed[player] and (lead_bidder is none or player != lead_bidder)`), the
  nullary `submit_bid`/`pass` vocabulary, and the single-variant
  `bid_won(declarer, bid)` outcome (opener-at-50 fallback when all pass). Trump
  declaration is a second, one-draw round on the same form (`round offering
  [declare_trump_suit] from high_bidder over players where player ==
  high_bidder until trump_suit is not none`), guarded by a `has_marriage`
  function checked over the four suits; no marriage anywhere is a
  statement-level `if`/`else` with no decision offered at all (abandoning the
  bid) — reproducing the monolith's no-draw abandon path exactly. Meld is a
  forced `for each player p: meld_score[team_of(p)] += pinochle_meld_value(p)`
  (the Counter-based tally moved verbatim into the new `runtime/pinochle.py`),
  and the twelve strict tricks run on the trick form of `round`, legality
  narrowed by a four-rule cascade (MustFollowSuit, MustHeadTrick,
  MustTrumpIfVoid, MustOverTrump) whose running-intersection semantics
  (`rules.legal_cards`) reproduce the monolith's follow/head/trump/over-trump
  obligation exactly (verified against 20,000 simulated (hand, trick, trump)
  scenarios pre-migration). The post-auction Python mechanic and its trick-
  legality helper are deleted along with the `instantiate` branch;
  byte-identical over 50 seeds. With it,
  Pinochle is fully kernel: registered in `cardlang/openspiel/game.py:GAMES`
  with derived info sets proven in the readiness harness.
- **Tarot** — *done — fully kernel.* The four-level ascending bid (Petite <
  Garde < Garde sans < Garde contre) runs on the auction form of `round`: a
  **counterclockwise single-pass ring** (each seat drops out of the
  participants ring after acting, one bid each), five nullary level moves
  guarded by the standing bid, and a two-variant `taken(taker, level) |
  thrown_in` outcome (an all-pass hand is thrown in via `skip to next hand`).
  Exposed and fixed the kernel's clockwise-only `turn_order_from` (now honours
  `direction`). The whole post-auction hand then followed onto the kernel too:
  the chien discard (at Petite/Garde) is a filtered movement — the new
  movement `where <lambda>` clause, narrowing the source pool to the matching
  cards before the selection draws from it (preferring non-trump non-King
  cards, falling back to any non-bout) — and the eighteen atout-trump tricks
  run on the trick form of `round` under a new `ExcuseIsExempt`/
  `MustFollowSuit`/`MustTrumpIfVoid`/`MustOverTrump` rule cascade. The Excuse's
  exemption needed a second new axis — a rule `exempts:` clause: cards it
  selects (when the rule's `applies_when` holds) sit outside the demand
  cascade entirely and are appended after every other legal card, in hand
  order, regardless of hand position — which an ordinary demands-intersection
  cannot express (it can narrow a candidate set, never reorder one to the
  end). Both axes were user-approved before implementation, landing as their
  own red-fixture-to-green commits (`docs/decisions.md`, "Movement `where`
  filter" / "Rule `exempts:` clause"). `run_tarot_hand` and its post-auction
  `run_tarot_rest` are both gone; byte-identical over 50 seeds against the
  unchanged golden. A follow-up fidelity stage then rerouted the chien
  discard from the taker's public `captured` pile (a wart the byte-identical
  migration inherited from the monolith) to a genuinely hidden
  `discard[player] : HiddenPile<player>` zone — a deliberate, user-mandated
  model change, so its golden regenerated (reviewed: zero-sum and
  `hands_played` invariants held per seed, the 50-seed contract mix stayed
  within measurement noise of the pre-change baseline). With it, Tarot is
  fully kernel: registered in `cardlang/openspiel/game.py:GAMES` (its own
  derived 78-card action-space block, since atouts/the Excuse fall outside the
  standard 52-card catalogue) with derived info sets — including the hidden
  discard specifically — proven in the readiness harness.
- **Skat** — *deferred (language gap).* The Reizen call-and-response auction (one
  player names successive values, the other holds or passes) is **not expressible
  on the existing order axis**: role-dependent vocabularies (speaker `bid`/`pass`
  vs responder `yes`/`pass`), conditional participation (the responder is skipped
  when the speaker passes), and a seat *reorder* in the second contest that a
  participants filter cannot produce. Per the checkpoint below this is a
  `language-gap`, filed as
  [open-questions/auction-order-axis.md](open-questions/auction-order-axis.md) and
  left in `run_skat_hand` pending a second call-and-response game (or sign-off to
  add a new `order` value). The contract choice (Suit / Grand / Null, hand vs.
  picking up the skat) waits on the same.

**Checkpoint (possible new axis) — resolved as a gap.** Skat's call-and-response
is a different *order* from a simple ascending ring. It was confirmed **not** a
value on the existing order axis (turn-from-a-seat / priority / simultaneous), so
per the discipline it was surfaced as an open question rather than special-cased
with an engine hook — see the Skat bullet above and
[open-questions/auction-order-axis.md](open-questions/auction-order-axis.md).

**Dependency surfaced by Bridge — built.** The auction form does not silently skip
a participant with no legal move — the ring is stated by the participants clause and
"all but one passed" by `until` ([decisions.md](decisions.md), "The auction form
of `round`"). Bridge keeps every seat in with an always-legal `pass`, but the
ascending auctions drop players who pass for good (and skip the standing high
bidder) with no decision — a *shrinking ring*. Reproducing that byte-identically
needs the participant predicate re-evaluated each turn — the **participant-filtering
axis**, which the auction form (`AuctionForm.next_actor`) now does (it re-evaluates
`over … where …` per turn, a no-draw skip for a dropped player; a static ring like
Bridge's `all players` is the invariant case). Built with Pinochle; reused by Workstream 2 (Stud's non-folded
ring). An always-legal `pass` would instead offer passed players and consume RNG
the monolith does not.

**Scope note.** Skat is still a *monolith* — the auction is fused with play and
scoring in one Python function ([roadmap.md](roadmap.md)); Pinochle and Tarot
were too, until each one's trick play and scoring followed its auction onto
the kernel (above). The auction extraction is the entry point, but the whole
hand must land in the DSL before the module is deleted: auction here, trick
play on the Step 0 `round`, scoring in Workstream 4 (Pinochle's own meld and
Tarot's own per-opponent settlement arithmetic both stayed game-local stdlib
primitives rather than moving to Workstream 4's shared `scoring_component`
subsystem — see that workstream's note below). Bridge is already split (play
is DSL), so it finishes first and validates `auction` end to end.

## Workstream 2 — Betting and the pot (Seven-Card Stud)

The corpus's only betting game and first real chip economy (Coup already settled
resource amount + transfer-failure — [decisions.md](decisions.md), "Resource
amount syntax" / "Resource transfer failure").

- **The betting runs on the kernel `round` — done.** Antes, the deal, the bring-in
  post, and the five streets (3rd–7th) are DSL statements; each street's betting is
  a `round offering [check, bet, call, fold, raise]` over the non-folded, non-allin
  ring (`over players where not folded[player] and stack[player] > 0 and (not
  acted[player] or bet_by[player] < bet_to_match)`) in **priority order**. The
  accumulator (bet-to-match, raises, per-player bet_by/acted) is ordinary phase
  state written by the move-type effects; a bet/raise is a partial all-in when the
  actor can't cover it and resets every other `acted`. Termination (`until`) closes
  a street when no live player still owes or has yet to act (or one lone matched
  contender remains). The bid value isn't chosen — `limit` is per-street state.
- **The `priority` order value — done.** Stud's betting order ("after a raise
  re-opens earlier seats, action returns to the earliest owing seat") is the
  pre-designed `priority` value on the order axis (turn-from-a-seat / priority /
  simultaneous), not a new axis. It is `order priority` on the betting round
  ([decisions.md](decisions.md), "The auction form of `round`"); the continuous
  ring (`order ring`, the default) was the only order built before. Reused by
  Coup's WS5 response windows.
- **Seat selectors as stdlib primitives.** The bring-in (lowest door card) and the
  first-to-act (highest visible upcards) are argmin/argmax over players keyed on
  card ranks/suits — not DSL-expressible — so `bring_in_seat()` / `first_to_act_seat()`
  are Stud-local stdlib functions called from the betting phase (like `team_of`),
  pure reads of the dealt cards (no RNG).
- **The showdown runs in the DSL — done.** A contested hand reveals the
  contenders' hole cards into the `PublicHand` (two movements per contender —
  the board parked into `hole`, then all seven flipped into `upcards` — so the
  muck inherits the hole-first order the next hand's pre-shuffle deck depends
  on; the flip's movement event carries the seven identities, the *derived*
  reveal). Each entrant then collects `stack[p] := stack[p] + pot_share(p)` and
  the hands leave play to the muck; a folded entrant's hole cards muck with a
  count-only emission (unrevealed), and a lone contender collects with no
  reveal at all. `pot_share` is the **Stud-local settle primitive** (the
  committed-total layering, odd chip to the first winner in seat order,
  uncalled remainder to the best contender), *not* a generalized "pot
  subsystem": side-pot reconciliation is a single corpus instance (Coup has no
  pot — its second resource game is a coin/treasury economy; the natural second
  *side-pot* game is a poker variant like Hold'em, still a candidate), so per
  corpus-first it stays game-local until a second poker variant justifies a
  shared `betting`/pot definition. The evaluator `hand_rank` stays internal;
  `best_five_card_hand` is the documented runtime-primitive to wire then. The
  showdown is RNG-free and decision-free, so it cannot shift the chooser
  sequence; the per-hand stack golden pinned its payouts byte-identically
  across the migration. With it, Stud is fully kernel: registered in
  `cardlang/openspiel/game.py:GAMES` with derived info sets proven in the
  readiness harness (its conformance check is a bounded random API walk —
  a full random sim of a ~10k-action chip-migration game is quadratic).

**Checkpoint (event-indexed pots) — confirmed closed.** The settlement
reconciles purely from per-player committed running totals + fold flags (sorted
commitment levels, divmod odd-chip to the first winner); there is no "pot
current when a player folded" anywhere. `pot_share` reads exactly that state;
no event-indexed pot ever existed, and nothing is filed as an open question.

**Test-depth nets — built.** The per-hand stack golden (`seven-card-stud_hands.json`,
50 seeds, pinned pre-migration — the end-of-game scores are degenerate, so the
sensitive signal is the post-hand stack vector) confirmed the betting *and*
showdown migrations are byte-identical; the `_payouts` recompute covers the
side-pot layers (short all-in, tie+odd-chip, three-way layered,
all-but-one-folded).

## Workstream 3 — Combinations and climbing (Tichu)

The first climbing game and first non-(rank,suit) cards. It introduces a
**combination model** reused later by Pinochle melds (promote to the standard
library once a third instance arrives).

- A typed `Combination` value: type × length × strength, with a comparison
  (single / pair / triple / straight / full house / bomb).
- A `climb` definition over `round`: each turn plays a combination matching the
  led type and length and beating it, or passes; three passes end the trick.
- The four special cards as values/rules: Mahjong (leads, lowest, wish), Dog
  (hands lead to partner), Phoenix (wild / −25), Dragon (highest single, +25,
  trick to an opponent). Plus pushing (pre-play card passing) and the
  double-victory finish.

**Status — the `climb` construct is built; Big Two runs on it byte-identically;
Tichu's migration is the remaining step.** The kernel `round climb` construct
(a `ClimbForm` hook bundle over the shared `run_decision_round` interpreter in
`mechanics.py`, dispatched in `execute.py`, with the grammar / AST / IR / resolve /
typecheck wiring) plays one combination-climbing trick over a pair of game-local
engine queries. Its runtime is now one of the three form bundles over the single
per-step decision loop (`docs/design-notes/kernel-extensibility.md` §4, §9 step 2),
not a standalone loop. **Big Two** is fully migrated onto it
(`docs/games/big-two.cardlang`) — the climbing loop, the 3♦ opening, pile routing,
the shed-out finish, and penalty scoring are DSL; its engine (`bigtwo.py`) is named
as the `bigtwo_lead_options` / `bigtwo_follows` queries — and reproduces its pinned
net (`tests/golden/bigtwo_scores.json`, 50 seeds) byte-for-byte. The `run_bigtwo_hand`
monolith and the `BigTwoHand` mechanic are deleted. **Tichu** still runs in
`run_tichu_hand` (`combinations.py` extracted, `tichu_scores.json` pinned); its
migration onto `climb` is the next step.

The design the construct settled:

- **`climb` is trick-shaped, not auction-shaped.** A combination play moves a
  *specific computed card-set* (the chosen combination's cards) from the hand to
  the pile — and the movement vocabulary moves cards *by count* (`all` / `one` /
  `N cards`), never a named set. So the play cannot be a DSL `move_type` effect the
  way a bet is. `climb` is a **kernel `round` construct** (the `ClimbForm` bundle,
  beside `TrickForm` / `AuctionForm` over the shared interpreter): it enumerates
  candidates from the engine, runs one climbing trick (lead → beat-or-pass; the
  trick ends when action returns to the last player, or the `until` predicate
  holds), and performs the card movement itself. There is *no* DSL-visible `Combination` value and no runtime-query move
  parameter — the construct depends only on the engine's *interface*
  (`combos(hand, ctx)`, `legal_follows(hand, led, ctx)`, `play.cards`).
- **Two engines, one construct interface.** Tichu's and Big Two's combination
  engines differ — Big Two keys on (rank, suit) because suit breaks every tie,
  carries flushes/quads, and follows cross-type within the five-card group, where
  Tichu keys rank-only, has bombs, and the special cards. So the engines stay
  game-local (beside the promote-at-the-third-instance rule — Pinochle melds would
  be a further instance), each named as a `combinations` / `follows` query
  pair on the `round climb`. The divergent *routing* lives in the DSL body, not the
  construct (the trick-form discipline): the climb form's `outcome` returns the
  winner (the last player to play, bound as `outcome`), and the body routes the pile
  and the next lead — Big Two: `move trick_pile to discard`, the winner leads.
- **What Tichu's migration still needs (PR after this).** Tichu's Dog is a
  *trick-ending lead* (its followers get no chooser draw — an `ends_trick` property
  on the engine's play that the climb form reads to skip the follow phase); this is a
  genuine **new axis** to surface and sign off, not an engine hook. Its termination
  is "≤ 1 player still holds cards" (Big Two's is "any player empty"), an existing
  value on the termination axis. Plus pushing (pre-play passing), the
  double-victory finish, and Dragon → opponent routing (a post-trick
  `dragon_recipient()` draw at the same RNG site). Routing the Dragon's pile to an
  opponent and the Dog's lead to the partner needs the body to know *what* won, not
  just *who* — so the climb form will expose the winning play's kind as terminal
  round-state (the trick form's `mech_state` → `last_round_state` pattern, read as
  `state.x`), which Big Two does not consult (re-verified byte-identical when added).
  Then
  `run_tichu_hand` is deleted, byte-identical against `tichu_scores.json`.
- The bomb **interrupt** axis (any player, any time) is moot at the migrated
  scope: the current Tichu omits out-of-turn bombs (bombs play only on-turn, as a
  follow), and Big Two has no bombs, so the kernel needs no interrupt axis to
  reproduce either. Revisit if a game forces out-of-turn play.

## Workstream 4 — Counting and in-play scoring (Cribbage, Schnapsen)

This workstream builds the **`scoring_component` runtime subsystem**
([decisions.md](decisions.md), "Scoring composition" / "Triggered scoring
components"), which the runtime has so far folded inline ([roadmap.md](roadmap.md)).

- **Cribbage** — *done, ahead of this workstream.* The whole hand landed on the
  kernel without the `scoring_component` subsystem this workstream builds: the
  discards and every pegging play are filtered card movements, and the 121-point
  cutoff is reproduced a component at a time by ordinary statement control flow
  (`repeat until`, `if`/`else`, `skip to next hand`). No `round` form fits
  pegging's per-play scoring plus forced-play flow, so it uses none; the current
  sub-round's card provenance is carried in two `Integer` state variables and
  decoded by the `peg_origin_of` stdlib primitive. The module-level Cribbage
  scorers (pegging counts + the show's fifteens/pairs/runs/flush/his-nob) re-homed
  as game-local stdlib primitives, like Stud's `pot_share` and Pinochle's
  `pinochle_meld_value` — migrate, don't redesign; promoting them to the shared
  `scoring_component` subsystem is corpus-first future work, not a requirement
  this migration carried.
- **Schnapsen** — marriages as an in-play declaration (`offer` that scores
  20/40), the trump-jack exchange (`offer`), and closing the stock (`offer` →
  the mid-hand open→closed phase-shape transition; its `claimed | talon_closed |
  open_play` outcome is already typed), with the two-phase follow rules.
- **Pinochle** — *done, ahead of this workstream.* The whole hand (trump
  declaration, meld, and the twelve strict tricks) landed on the kernel via
  Workstream 1 (above) before this workstream reached it. Meld stayed a
  Counter-based, game-local `pinochle_meld_value` stdlib primitive (like
  Stud's `pot_share`) rather than either this workstream's `scoring_component`
  subsystem or Workstream 3's combination model — migrate, don't redesign;
  promoting it to either shared mechanism is corpus-first future work, not a
  requirement the migration itself carried.
- **Tarot** — *done, ahead of this workstream.* Likewise landed via Workstream
  1 (above): the bouts-conditional threshold, the taker's doubled card points,
  the petit-au-bout adjustment, and the bid multiplier all settle in
  `tarot_per_opp`, a game-local stdlib primitive in the same shape as
  `pinochle_meld_value`/`pot_share` — not this workstream's `scoring_component`
  subsystem.

**Test-depth nets.** Add Schnapsen's six-way settlement recompute (1/2/3 game
points) before migrating it; the Cribbage scorers kept their unit-test coverage
as stdlib queries.

Delete `run_schnapsen_hand` once green.

## Workstream 5 — Challenge, block, influence (Coup)

The furthest game from cards, and the construct [decisions.md](decisions.md) uses
to draw the in-scope line (a game that *defines* "challenge" vs. one that mutates
its own rules). Do it last, once the kernel is proven.

- `challenge` and `block` as response-window definitions over `round`: after an
  actor declares an action, a window in which others may challenge (priority
  order) → reveal/penalty, or block → a counter-window.
- Hidden-influence cards, the coin economy (resource), influence loss,
  elimination, and forced coup at ten coins.

**Checkpoint (highest new-axis risk).** The action → response → counter-response
nesting and simultaneous/priority windows are the sharpest test of the closed
axes. If they cannot be expressed as values on the existing axes, that is an
explicit signed-off axis addition plus an open question — this is exactly the
boundary the kernel is meant to make visible.

**Test-depth net.** Add a recompute that a challenge resolves to the correct
loser before deleting `run_coup_game`.

## Cross-cutting build-out

These land inside the workstreams above and are shared on the third use:

- generalized `round` axes — Step 0, the spine for all of it;
- the `scoring_component` runtime subsystem — Workstream 4;
- the integer **resource primitive** (per-player amounts + `transfer`) — settled by
  Coup ([decisions.md](decisions.md), "Resource amount syntax" / "Resource transfer
  failure"), used by Stud's chips and Coup's coins. *Distinct from Stud's side-pot
  reconciliation,* which is poker-specific: Coup has no pot (a coin/treasury
  economy, not a shared pot), so it shares the primitive but not the layering. The
  side-pot pot stays Stud-local until a second poker variant (Hold'em) lands;
- the `Combination` model + queries — Workstream 3, reused by Pinochle and
  Cribbage.

## Recommended sequence

1. **Step 0** — generalize `round`; re-express the trick; migrate Hearts /
   Spades / Getaway off built-in `Trick` and delete it.
2. **Auctions** — Bridge first (already split, proves `auction`), then Pinochle
   bid → Tarot → Skat.
3. **Stud** — betting + pot.
4. **Tichu** — climbing + the combination model.
5. **Cribbage + Schnapsen** — the scoring-component subsystem (Pinochle's and
   Cribbage's scoring both landed ahead of this step — Pinochle with its
   Workstream 1 migration, Cribbage on ordinary statements plus game-local stdlib
   primitives rather than the subsystem itself; Schnapsen remains).
6. **Coup** — challenge / block / influence.

This is breadth-first by shape: it reaches `auction`'s third instance early and
keeps each step small. The alternative is depth-first on a single monolith (Skat
is the natural choice) to force the full kernel — auction, trick, and structured
scoring — to completion on one game before generalizing. That yields a complete
end-to-end proof sooner at the cost of less reuse upfront; it is a reasonable
swap for steps 2–5 if a single finished game is more valuable than incremental
breadth. Step 0 and Coup-last hold either way.

## Stage definition of done

- No per-game branch remains in `mechanics.py::instantiate`; the seven
  `runtime/*.py` game modules and the three inline `run_*_hand` functions are
  gone; the built-in `Trick` mechanic is gone.
- All 14 games run on the kernel + in-DSL standard library; every
  `test_playout_*` is green; IR goldens regenerated and reviewed; `mypy
  --strict` clean; conservation invariants and the new recompute nets green.
- The `language-gap` list is zero or every entry is a named, deferred open
  question.
- Each promoted definition (`auction`, `betting`, `climb`, `challenge`, `block`,
  `trick`) is documented in [library.md](library.md), and
  [decisions.md](decisions.md) reflects any axis decision made along the way.
