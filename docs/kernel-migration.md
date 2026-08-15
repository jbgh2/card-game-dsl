# Migrating the corpus onto the decision kernel

This is the execution brief for removing the per-game **concrete runtime
mechanics** and expressing their decision logic in the DSL itself, on the
interactive-decision kernel. The design it executes is settled in
[decisions.md](decisions.md), "Interactive decisions: a kernel and an in-DSL
standard library". The discipline (red→green, IR goldens, exhaustiveness) is in
[building.md](building.md). This file is the *order of operations* and the
per-game scope.

It is written to be handed to an implementer. Each workstream states what
capability it adds, the kernel/standard-library pieces it builds, the
checkpoints where a genuine language gap might surface, and its definition of
done.

## The goal, concretely — REACHED

No game holds decision logic in hand-written Python. The `instantiate`
construct is deleted end-to-end (grammar, AST, IR, resolve/typecheck,
runtime, and the OpenSpiel adapter's rejection — nothing remains to reject);
every `run_*` monolith is gone (`run_bridge_auction`, `run_pinochle_hand`,
`run_tarot_hand`/`run_tarot_rest`, `run_stud_game`, `run_bigtwo_hand`,
`run_cribbage_hand`, `run_schnapsen_hand`, `run_skat_hand`, `run_tichu_hand`,
`run_coup_game`); and every corpus game runs on the kernel `round` forms plus
ordinary statements, registered in `cardlang/openspiel/game.py:GAMES` with
the readiness proofs green (`tests/openspiel_ready/`).

The per-game `runtime/*.py` modules that remain hold no mechanic — only pure
Primitives the DSL calls: Stud's poker evaluator, seat selectors, and
`pot_share`; Big Two's combination engine; Pinochle's meld evaluator; Tarot's
per-card queries and settlement arithmetic; Cribbage's pegging/show scorers
and provenance decoder; Schnapsen's two-card trick resolution; Skat's bid
ladder, follow-class legality, trick winner, matador count, and overbid
arithmetic; Tichu's climb queries over the shared `combinations.py` engine,
team/finishing lookups, and the OpenSpiel combo codec; Coup's
in-game scans and trace emitters.

The stage-done checklist holds: no per-game branch anywhere outside the
Primitive registries; every `tests/test_playout_*.py` green with
behaviour preserved (byte-identical goldens per migration, sanctioned
normalizations recorded in `tests/test_migration_characterization.py`); IR
goldens unchanged (no kernel game ever emitted an `instantiate` node);
`mypy --strict` clean; docs in lockstep. One latent footgun to watch as the
language grows: `cardlang/openspiel/infostate.py`'s `_render` sorts
list/tuple-valued state variables before rendering into the information
state, so a future *ordered* list-valued state variable (a bid history, a
play sequence — anything where order itself carries information) must not be
rendered sorted, or distinct information sets that differ only in order
would silently collapse into the same string.

**What remains honest to record — the scope boundary, not debt.** No
rules-level randomness remains: both Workstream 5 halves are done. Coup's
challenges, blocks, claimed characters, and targets are real announced
decisions, and so are Tichu's call windows (grand at the eight-card deal
window, small on the off-the-clock poll — decisions.md "Off-the-clock
windows") and its Dragon routing. Each game's remaining scope reductions
are named in its own game file (Tichu's Mahjong wish and bomb variants,
and the like) — scope, not hidden randomness.

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
  skill-gated branches (Spades nil/+500, Coup
  challenge-loser — see issue #83).
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
need them — see issue #140.*

The `Round` node (`cardlang/ast/nodes.py`) is trick-shaped: one card play per
participant plus a `winner` function. Everything below composes on a
`round` grown to the closed axes from [decisions.md](decisions.md):

- **participants** — actor / others / ring / list
- **order** — turn-from-a-seat / priority / simultaneous
- **accumulator** — a value threaded across steps (high bid, bet-to-match,
  running total, led combination)
- **termination** — a predicate over the accumulator/state
- **typed outcome** — reusing the Stage 1–3 outcome machinery
- **move vocabulary** — not only card plays: non-material `move_type`s (bids,
  passes, actions) chosen via `offer`

Build this, then re-express the existing trick `round` as one configuration of
it with no behavioural change (the same proof Oh Hell already gives). Then
migrate the remaining built-in-`Trick` games onto the kernel `round` —
Hearts/Spades (mode transitions) and Getaway (early termination) — and
delete the built-in `Trick` mechanic. This both retires shared engine code and
exercises every axis before the harder games arrive.

## Workstream 1 — Auctions (Bridge, Skat, Tarot, Pinochle)

Highest leverage: four instances of one shape, so `auction` is promotable to the
standard library immediately on the third.

Build an `auction` definition over `round`: `ring` participants, accumulator =
current high bid + pass state, termination = all-but-one passed (or N
consecutive passes), typed outcome = a contract outcome. Then per game, supplying
*values along the axes*:

- **Bridge** — *done.* A two-dimensional bid space (level × strain) plus
  doubling/redoubling, on the auction form of `round`; the typed
  `contract_finalized | all_pass` outcome computes the declarer over the bid
  history. `run_bridge_auction` and its `instantiate` branch are deleted.
- **Pinochle** — *done — fully kernel.* The ascending bid runs on the auction
  form of `round` over a **shrinking participants ring** (`over players where
  not passed[player] and (lead_bidder is none or player is not lead_bidder)`), the
  nullary `submit_bid`/`pass` vocabulary, and the single-case
  `bid_won(declarer, bid)` outcome (opener-at-50 fallback when all pass). Trump
  declaration is a second, one-draw round on the same form (`round offering
  [declare_trump_suit] from high_bidder over players where player is
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
  guarded by the standing bid, and a two-case `taken(taker, level) |
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
- **Skat** — *done.* The Reizen call-and-response auction needed NO new order
  value: it is a role-guarded two-participant ring — `bid` guarded to the
  speaker, `yes` to the responder, `pass` open, `until` carrying
  pass-or-exhausted-ladder (the reference's zero-draw auto-pass), two
  sequential `round`s threading the survivor ([decisions.md](decisions.md),
  "The auction form of `round`", the call-and-response bullet). The three
  once-filed objections (role vocabularies, conditional participation, the
  seat reorder) each mapped to an existing axis — guards, the `until`
  predicate, `from <speaker>`. The contract choice is a pair of `offer`s plus
  a one-draw `declare_suit(s : Suit)` round; the ten tricks run
  Schnapsen-style (three single-actor filtered movements over
  `skat_follow_ok` — the trick form's rules-driven candidates are unordered
  where the reference draws hand-ordered legality); scoring is plain
  statements over the game-local `skat_matadors` primitive, with the
  overbid arithmetic written as rounded division in the game text.

**Checkpoint (possible new axis) — dissolved.** Skat's call-and-response was
filed as a language gap, then probed against the unmodified kernel at
migration time: a scripted-chooser fixture reproduced the reference
`exchange()`'s draw sequence draw-for-draw on the plain ring with role-guarded
moves. The open question resolved into
[decisions.md](decisions.md) ("The auction form of `round`") with the order
axis unchanged — the discipline's happy path: the gap was surfaced, held, and
closed by configuration rather than an engine hook.

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

**Scope note.** A monolith lands whole: Pinochle, Tarot, and Skat each fused
auction, play, and scoring in one Python function until the whole hand moved
in that game's migration (auction on this workstream's form, trick play on the
Step 0 `round` or hand-ordered filtered movements, scoring as game-local
Primitives rather than Workstream 4's shared `scoring_component`
subsystem — see that workstream's note below). Bridge was already split (play
is DSL), so it finished first and validated `auction` end to end.

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
- **Seat selectors as Primitives.** The bring-in (lowest door card) and the
  first-to-act (highest visible upcards) are argmin/argmax over players keyed on
  card ranks/suits — not DSL-expressible — so `bring_in_seat()` / `first_to_act_seat()`
  are Stud-local Primitives, called from the betting phase by name exactly as
  the Builtin `team_of` is,
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

**Status — done for both climbing games.** The kernel `round climb` construct
(a `ClimbForm` hook bundle over the shared `run_decision_round` interpreter in
`mechanics.py`, dispatched in `execute.py`, with the grammar / AST / IR / resolve /
typecheck wiring) plays one combination-climbing trick over a pair of game-local
engine queries. Its runtime is one of the three form bundles over the single
per-step decision loop (`docs/design-notes/kernel-extensibility.md` §4, §9 step 2),
not a standalone loop. **Big Two** runs fully on it
(`docs/games/big-two.cardlang`) — the climbing loop, the 3♦ opening, pile routing,
the shed-out finish, and penalty scoring are DSL; its engine (`bigtwo.py`) is named
as the `bigtwo_lead_options` / `bigtwo_follows` queries — and reproduces its pinned
net (`tests/golden/bigtwo_scores.json`, 50 seeds) byte-for-byte. The `run_bigtwo_hand`
monolith and the `BigTwoHand` mechanic are deleted. **Tichu** runs fully on it
too (`docs/games/tichu.cardlang`; `run_tichu_hand` deleted, byte-identical
against `tichu_scores.json` and the 811-hand `tichu_hands.json`): the push is
chosen movements into per-player gift piles distributed giver-major, each
trick one `round climb` over `tichu_lead_options` / `tichu_follows`
(the engine stays `combinations.py`), and the special-card flows ride two
climb-form facilities plus two rng primitives (below).

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
  construct (the trick-form discipline): the climb form's `outcome` hook returns the
  winner (the last player to play, bound as `winner`), and the body routes the pile
  and the next lead — Big Two: `move trick_pile to discard`, the winner leads.
- **The special-card flows are engine-interface values plus terminal
  round-state, not grammar.** Tichu's Dog is a *trick-ending lead*: the
  engine's play carries an `ends_trick` property the climb form reads at
  apply time, closing the trick with zero follower draws. The form also
  adopts the trick form's `mech_state` → `last_round_state` pattern, so the
  body reads `state.lead_ended_trick` (route the Dog: pile to the discard,
  lead to the partner) and `state.shed_first` / `state.shed_second` (the
  first two players to play out per trick, in play order — the finishing
  order double victory and call scoring key on). Big Two consults none of
  these (re-verified byte-identical). Tichu's trick itself never ends early
  (`until false` — a shed does not stop the beating); the *hand* ends at
  "≤ 1 player still holds cards" or double victory, in the surrounding
  `repeat until`. Dragon → opponent routing and the Tichu/Grand-Tichu
  calls landed at migration as rng draws at the monolith's exact RNG sites;
  Workstream 5's Tichu half has since upgraded both to real announced
  decisions (see the WS5 section).
- **The OpenSpiel combo block is computed for Tichu, enumerated for Big
  Two.** Big Two's play universe (19,898) is enumerated and golden-pinned;
  Tichu's is 211,204,694 (straights of length 5–14 under free suit
  assignment are 208.8M of it, and the engine's Mahjong-as-rank-1 quirk adds
  a Phoenix+Mahjong pair and Mahjong-filled phoenix fullhouses), so
  enumeration is infeasible: its ids come from an arithmetic codec
  (`runtime/tichu.py::TichuComboCodec` via `primitives.climb_codec_function`) —
  pure card-set ↔ index functions over a fixed per-kind block layout, so ids
  stay stable across determinized worlds with no table. Pinned by exact-size,
  spot-id, engine-emission and per-block roundtrip tests
  (`tests/test_openspiel_encoding.py`).
- The bomb **interrupt** axis (any player, any time) is moot at the migrated
  scope: the current Tichu omits out-of-turn bombs (bombs play only on-turn, as a
  follow), and Big Two has no bombs, so the kernel needs no interrupt axis to
  reproduce either. Revisit if a game forces out-of-turn play.

## Workstream 4 — Counting and in-play scoring (Cribbage, Schnapsen)

This workstream builds the **`scoring_component` runtime subsystem**
([decisions.md](decisions.md), "Scoring composition" / "Triggered scoring
components"), which the runtime has so far folded inline (issue #115).

- **Cribbage** — *done, ahead of this workstream.* The whole hand landed on the
  kernel without the `scoring_component` subsystem this workstream builds: the
  discards and every pegging play are filtered card movements, and the 121-point
  cutoff is reproduced a component at a time by ordinary statement control flow
  (`repeat until`, `if`/`else`, `skip to next hand`). No `round` form fits
  pegging's per-play scoring plus forced-play flow, so it uses none; the current
  sub-round's card provenance is carried in two `Integer` state variables and
  decoded by the `peg_origin_of` Primitive. The module-level Cribbage
  scorers (pegging counts + the show's fifteens/pairs/runs/flush/his-nob) re-homed
  as game-local Primitives, like Stud's `pot_share` and Pinochle's
  `pinochle_meld_value` — migrate, don't redesign; promoting them to the shared
  `scoring_component` subsystem is corpus-first future work, not a requirement
  this migration carried.
- **Schnapsen** — *done.* Not `offer`s: the leader's whole mixed turn (lead a
  card / declare a marriage / exchange the trump jack / close the talon) is ONE
  flat candidate list, so it landed as the **auction form over a
  single-participant ring** (`until trick_pile is not empty`; the free actions
  leave the predicate false and the ring re-offers the leader), with
  `play_card(c : Card)` the corpus's first state-dependent move-parameter
  domain ([decisions.md](decisions.md), "Declared parameter domains"). The
  two-phase follow legality is the in-file `follow_ok` predicate filtering the
  follower's chosen movement (no `active_rules` cascade — the follower answers
  outside any trick `round`); marriages score 20/40 into a `pending` counter
  flushed on the declarer's first trick win; the `claimed | talon_closed |
  open_play` outcome `produce`s from the phase body. The two-card trick
  resolution re-homed as the game-local `schnapsen_trick_winner` Primitive
  primitive (the `pot_share`/`pinochle_meld_value` shape).
- **Pinochle** — *done, ahead of this workstream.* The whole hand (trump
  declaration, meld, and the twelve strict tricks) landed on the kernel via
  Workstream 1 (above) before this workstream reached it. Meld stayed a
  Counter-based, game-local `pinochle_meld_value` Primitive (like
  Stud's `pot_share`) rather than either this workstream's `scoring_component`
  subsystem or Workstream 3's combination model — migrate, don't redesign;
  promoting it to either shared mechanism is corpus-first future work, not a
  requirement the migration itself carried.
- **Tarot** — *done, ahead of this workstream.* Likewise landed via Workstream
  1 (above): the bouts-conditional threshold, the taker's doubled card points,
  the petit-au-bout adjustment, and the bid multiplier all settle in
  `tarot_per_opp`, a game-local Primitive in the same shape as
  `pinochle_meld_value`/`pot_share` — not this workstream's `scoring_component`
  subsystem.

**Test-depth nets.** Schnapsen's nets are the pinned 50-seed scores golden plus
the per-hand `game_score` vector golden (`tests/test_migration_characterization.py`
— a hand settles only 1–3 game points, so the per-hand vector surfaces a draw
divergence at the hand it first perturbs); the Cribbage scorers kept their
unit-test coverage as Primitive queries.

## Workstream 5 — Challenge, block, influence (Coup)

The furthest game from cards, and the construct [decisions.md](decisions.md) uses
to draw the in-scope line (a game that *defines* "challenge" vs. one that mutates
its own rules). Done last, once the kernel was proven.

**Status — done at REAL interactive scope; the checkpoint resolved with NO
new axis.** The windows are decisions: challenge windows poll each other
in-game player clockwise from the claimant with `offer to <responder> one of
[challenge, allow]` (first challenge closes the window — plain `repeat
until` + `offer` inside the action's effect, a tested-legal combination);
blocks fold the claimed character into the window vocabulary
(`block_claiming_*`), so the bluff is the decision itself; `steal` /
`assassinate` / `coup` carry a declared `target : Player` parameter; and a
proven challenge `reveal`s the shown card publicly before returning it to
the deck. The single-pass poll pattern replaced the anticipated auction
`priority`-mode substrate — a challenge window never loops, so the ring
machinery buys nothing. One recorded residual: the proven card's *return
movement* stays count-projected, so a formal observer cannot exclude the
kept-the-copy world (the runtime's filter guarantees the proven card
returns; tabletop common knowledge is epsilon finer — the public-transit
encoding closes it if a consumer ever needs that bit). Interactive Coup
also surfaced the corpus's first legally unbounded lines
([open-questions/unbounded-lines-and-max-length.md](open-questions/unbounded-lines-and-max-length.md)).

The anticipated new-axis risk (action → response → counter-response
nesting, priority windows) dissolved on inspection at migration time and
stayed dissolved through the interactive upgrade: every decision lands on
existing kernel sites — the turn's action pick and every window response
are `offer`s, every influence loss is a chosen movement by the loser (the
single-actor `as victim` block), and the exchange is a
deal-n + chosen-n + shuffle. Setup and every deck draw deal off the top
(the corpus convention). `run_coup_game` was deleted at migration, and with
it the whole `instantiate` construct (zero mechanics remained); the
reveal-sequence golden (`tests/golden/coup_scores.json`: every influence
flip in order, final coins, alive, winner, 40 seeds) pins the interactive
scope, re-pinned at the WS5 sign-off.

**The Tichu half — done at real-rules fidelity.** The call rules were
verified against the publisher's English rules (Pagat's commercial-games
index defers to Fata Morgana for Tichu): grand tichu is a discrete
first-eight-cards window (offer per player, then the deal completes); small
tichu is off-the-clock until the caller's first play and runs on the
quiescence-lap poll (decisions.md "Off-the-clock windows") with publicly
derivable eligibility (pre-push: nobody has played; post-push: a 14-card
hand is exactly "unplayed"); the Dragon's trick is given by a real announced
choice. The rng gates (`tichu_call_roll`, `tichu_dragon_recipient`) are
deleted from the registries. New goldens pin the behaviour change, captured
under a reference call policy — the uniform chooser diverges, which is the
second legally-unbounded-lines witness
([open-questions/unbounded-lines-and-max-length.md](open-questions/unbounded-lines-and-max-length.md)).

## Cross-cutting build-out

These land inside the workstreams above and are shared on the third use:

- generalized `round` axes — Step 0, the spine for all of it;
- the `scoring_component` runtime subsystem — Workstream 4;
- the integer **resource primitive** (per-player amounts + `transfer`) — settled by
  Coup ([decisions.md](decisions.md), "Resource amount syntax" / "Resource transfer
  failure"), used by Stud's chips and Coup's coins. *Distinct from Stud's side-pot
  reconciliation,* which is poker-specific: Coup has no pot (a coin/treasury
  economy, not a shared pot), so it shares the primitive but not the layering. The
  side-pot stays Stud-local until a second poker variant (Hold'em) lands;
- the `Combination` model + queries — Workstream 3, reused by Pinochle and
  Cribbage.

## Recommended sequence

1. **Step 0** — generalize `round`; re-express the trick; migrate Hearts /
   Spades / Getaway off built-in `Trick` and delete it.
2. **Auctions** — Bridge first (already split, proves `auction`), then Pinochle
   bid → Tarot → Skat.
3. **Stud** — betting + pot.
4. **Tichu** — done: climbing + the combination model (Big Two first, then
   Tichu's special-card flows on the climb form's terminal state).
5. **Cribbage + Schnapsen** — done, without the scoring-component subsystem
   (Pinochle's, Cribbage's, and Schnapsen's scoring all landed as ordinary
   statements plus game-local Primitives; the subsystem itself remains
   unbuilt, corpus-first future work).
6. **Coup** — done at real interactive scope: challenge / block / claim /
   target are player decisions (Workstream 5; Tichu's call windows remain).

This is breadth-first by shape: it reaches `auction`'s third instance early and
keeps each step small. The alternative is depth-first on a single monolith (Skat
is the natural choice) to force the full kernel — auction, trick, and structured
scoring — to completion on one game before generalizing. That yields a complete
end-to-end proof sooner at the cost of less reuse upfront; it is a reasonable
swap for steps 2–5 if a single finished game is more valuable than incremental
breadth. Step 0 and Coup-last hold either way.

## Stage definition of done — MET

- `instantiate` is deleted outright (no mechanic remained to dispatch); every
  `run_*` monolith is gone; the built-in `Trick` mechanic is gone.
- Every corpus game runs on the kernel + in-DSL standard library; every
  `test_playout_*` is green; IR goldens unchanged (no kernel game ever
  emitted an `instantiate` node); `mypy
  --strict` clean; conservation invariants and the recompute nets green.
- The `language-gap` list is zero or every entry is a named, deferred open
  question.
- The shipped configurations (`trick`, the auction/betting forms, `climb`)
  are documented in [library.md](library.md) with every axis decision in
  [decisions.md](decisions.md); the shared `auction` / `betting` /
  `challenge` / `block` *named definitions* stay corpus-first promotions at
  their third instances (the interactive-windows scope, Workstream 5, is the
  likely forcing function for the last two).
