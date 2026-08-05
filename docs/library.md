# Standard library

The named compositions that have emerged from the five-game corpus. Most users
write only in this layer; the primitives in [model.md](model.md) are for the
10% pushing the edges.

## The trick: a `round` configuration

A trick is the kernel `round` construct ([model.md](model.md)), not a built-in
mechanic. Each participant in turn order from the leader plays one card; the
lead sets the led suit; an optional early-termination predicate may end the pass
before everyone has played; then a winner function selects a player, bound as
`winner` for the surrounding body, which does the routing.

```text
round <move_type> from <leader> over <participants>
      source <zone> into <zone> winner <fn> [trump <expr>] [early <predicate>]
```

Key design notes:

- **`winner` names the player, not the routing.** The round computes which player
  the play selects; what happens to the cards is a routing concern. In Hearts the
  winner takes the cards into their captured pile; in Getaway the winner picks up
  the pile only when the trick terminated early. The word is reserved for this
  player sense — a tagged `(tag, payloads)` result is an **outcome**
  ([glossary.md](glossary.md)).

- **Routing is the surrounding body, not a parameter.** After the round returns,
  the body relocates the played cards: Hearts routes unconditionally
  (`move all cards from trick_pile to captured[winner]`); Getaway branches on
  the round's terminal state (`if state.trick_terminated_early { … } else { … }`).
  A finished round's terminal state stays readable as `state.x` until the next
  round runs.

- **`early <predicate>` is optional.** Most games omit it (the pass proceeds until
  all participants have played). Getaway uses `early on_play_off_led_suit`: an
  off-led-suit play (only possible when void — the game's *tochoo*) ends the trick.

- **`trump <expr>` is optional.** Omitted, the round uses the game-level `trump:`
  declaration (Spades); supplied, it overrides per hand (Oh Hell turns one up each
  deal; Bridge's contract sets it, none for no-trump).

- **The round emits observation events** for each play, with visibility derived
  from the zones. Hidden-info and perfect-info games use the same construct; the
  difference is zone visibility.

- **The next leader is the body's choice.** The round does not assume
  "winner-leads-next"; the surrounding phase sets `leader := winner` (or not).

## The climb: a `round` configuration

A climbing trick (Big Two, Tichu) is the kernel `round`
construct in its **climbing form** — one trick where each play is a *combination*,
not a single card. The leader leads a combination drawn from the engine, then each
participant beats the standing play with a higher one **of the same size** or
passes; a pass does not drop a player. The trick ends when action returns to the
last player who played (everyone else passed one full lap), when the `until`
predicate holds (a player has shed out), or at once when the lead itself ends
the trick (the engine marks the play `ends_trick` — Tichu's Dog — and the
followers draw nothing). The last player to play is bound as
`winner` for the surrounding body, which routes the pile and the next lead.

```text
round climb <move_type> from <leader> over <participants>
      source <zone> into <zone>
      combinations <lead_query> follows <follows_query>
      until <predicate>
```

Key design notes:

- **The combination engine is named, not built in.** `combinations` names a
  lead-options query (every combination a hand may lead) and `follows` a
  legal-follows query (those that beat the standing play). They are **game-local
  stdlib** ([decisions.md](decisions.md) "The climbing form of `round`"): Big Two's
  and Tichu's combination rules genuinely differ (suit tie-breaks, flushes and
  quads, cross-type five-card beating vs. bombs and special cards), so the engines
  stay per-game until a third instance. The construct depends only on their
  interface — a list of plays, each exposing the cards it moves as `.cards`.

- **No winner function.** Unlike the trick form, the winner is not a function of
  the cards — it is the loop's last player to play, returned directly and bound as
  `winner`. A combination play moves a *computed card-set*, which the movement
  grammar (cards by count) cannot name, so the construct performs the movement
  itself ([decisions.md](decisions.md) "The climbing form of `round`").

- **`until <predicate>` ends the trick — and, when the game wants it, the
  hand.** It is the shed-out gate: Big Two's `any player where hand[player] is empty`
  stops the trick the instant a player empties (matching the rule that the
  hand ends on the first shed). It is checked after each play, so the rest of
  that trick is not offered. A game whose tricks always play out (Tichu — the
  others must still beat or pass after a shed) writes `until false` and ends
  the *hand* in the surrounding `repeat until` instead.

- **The form exposes its terminal state to the body** (the trick form's
  `mech_state` → `last_round_state` pattern, read as `state.x`):
  `state.lead_ended_trick` (did an `ends_trick` lead close it?) and
  `state.shed_first` / `state.shed_second` (the first two players who played
  their last cards this trick, in play order — Tichu's finishing order, which
  double victory and the call payouts key on). Big Two reads none of these.

- **Routing is the surrounding body, not a parameter** (as for the trick). Big Two
  routes the spent pile to the discard (`move all cards from trick_pile to discard`)
  and passes the lead to the winner (`leader := winner`); Tichu routes to a team
  pile (`captured[team_of(winner)]`) — or to a random opponent's on a Dragon
  win, or to the discard with the lead passing to the partner on the Dog.

## The turn loop: the `turns` form

The loop beneath the round forms, for games whose turn is a *body of
statements* (draw-then-discard, ask-and-resolve) rather than one flat
candidate list — the full spec is [decisions.md](decisions.md) "The `turns`
form":

```text
turns <binder> from <leader> over <participants>
      until <pred> [again <state-var>] { <statements> }
```

Key design notes:

- **The binder is the turn-holder**, bound like a `for each player` binder
  (name + acting player), so the body's `offer`s and chosen movements are
  attributed without a cursor state variable.
- **The form owns rotation and termination** — advance in game direction
  through the participants predicate (re-evaluated per advance, so
  elimination falls out); `until` checked at every turn boundary, the first
  included.
- **`again <state-var>` is the go-again axis**: the body's move effects
  write a declared Boolean on every path; a turn ending with it true
  repeats the same player. Go Fish's hit-or-matching-draw is the corpus
  anchor; Gin Rummy's strictly alternating draw-discard cycle is the plain
  form's.
- **The dividing line from the auction form**: a turn that is one flat
  candidate list stays an auction-form configuration (Schnapsen's leader
  loop); `turns` exists for statement-structured turns.

## Move types

- `play_to_trick` — source: hand, destination: trick_pile
- `transfer_between_hands` — source: hand, destination: another hand
- `submit_bid` — source: nothing material, sets a state variable
- `pass` — source: nothing material, marks player as out of auction
- `declare_trump_suit` — source: nothing material, sets trump state
- `steal_left` — source: another player's hand, destination: own hand (Getaway)
- `check` / `bet` / `call` / `raise` / `fold` — Stud's betting vocabulary,
  **game-defined** `move_type`s (not library moves) that write the betting
  accumulator phase state; the bring-in is a forced effect, not a move
- `play_card(c : Card)` / `declare_marriage(s : Suit)` / `exchange_trump_jack` /
  `close_talon` — Schnapsen's lead vocabulary, **game-defined** `move_type`s in
  the same shape: one auction-form candidate list per leader turn. `play_card`
  is the corpus's first Card-parameterized move ([decisions.md](decisions.md)
  "Declared parameter domains": candidates are the live hand, in hand order)
- `bid` / `yes` / `pass` / `play_at_eighteen` / `throw_in` / `pick_up_skat` /
  `declare_hand` / `choose_suit_game` / `declare_grand` / `declare_null` /
  `declare_suit(s : Suit)` — Skat's Reizen and declaration vocabulary,
  **game-defined** `move_type`s: `bid` and `yes` are role-guarded (the
  call-and-response configuration, [decisions.md](decisions.md) "The auction
  form of `round`"), and `declare_suit` runs the Suit domain in a one-draw round
- `income` / `foreign_aid` / `coup` / `tax` / `assassinate` / `steal` /
  `exchange` — Coup turn actions (general and character actions)
- `challenge` — contest a character claim during a challenge window (Coup)
- `block` — counteract an action by claiming a blocking character (Coup)

## Rules

**Library rules are shared definitions**, not a prose catalogue: the bodies
live in `cardlang/stdlib/rules.cardlang`, and a game activates one by naming
it in `active_rules:` without defining it — the resolver splices the body in.
Defining a game-local rule under a library name is rejected (a local copy
would drift from the shared body silently). A parameterized rule is a
template: the reference passes arguments (`NoLeadingSuitUntilBroken(hearts)`)
and the resolver substitutes them into the body. Template parameter domains
are `Suit` only, corpus-first
([roadmap.md](roadmap.md), "Grammar surface deferred by the checker"); games may declare
their own parameterized rules with the same instantiation semantics.

The library:

- `MustFollowSuit` — constrains `play_to_trick`; the canonical follow-suit
  rule (Hearts, Getaway, Spades, Bridge, Oh Hell, Pinochle, Belote).
  French Tarot's
  follow rule is game-local under its own name (`MustFollowEffectiveSuit`):
  its demand reads `tarot_led_suit()`, the effective led suit, not the raw
  `state.led_suit` — a genuinely different body, so it does not share this
  definition (see below).
- `NoLeadingSuitUntilBroken(suit: Suit)` — constrains `play_to_trick`; no
  leading the named suit until it has been played to a trick
  (Hearts activates `(hearts)`, Spades `(spades)`).

Game-local rules that recur as *names* but not as bodies:

- `MustHeadTrick` — constrains `play_to_trick`; must beat the highest card of
  the led suit played so far when following (Pinochle)
- `MustTrumpIfVoid` — constrains `play_to_trick`; must trump when void in the
  led suit (Pinochle, French Tarot — the bodies differ: `trump_suit` vs the
  `atouts` rank-set)
- `MustOverTrump` — constrains `play_to_trick`; must beat the highest trump
  played so far when trumping (Pinochle, French Tarot — the bodies differ:
  `rank_value` within the trump suit vs `tarot_trump_height()`)
- `ExcuseIsExempt` — constrains `play_to_trick`; `exempts:` the Excuse from
  every obligation in the cascade (French Tarot). The corpus's first use of
  the rule `exempts:` clause ([decisions.md](decisions.md) "Rule exemption");
  see below.
- `MustFollowEffectiveSuit` — French Tarot's follow rule (see
  `MustFollowSuit` above)

Pinochle's four rules (`MustFollowSuit`/`MustHeadTrick`/`MustTrumpIfVoid`/
`MustOverTrump`) run as one `active_rules:` cascade, in this order (list order
is application order): follow suit and head the trick if able; if void, trump
and over-trump if able; else anything. Each rule's `if_impossible: hand`
intersects the *running* set with the whole hand — "keep the prior
narrowing" — so an inapplicable obligation falls through (`rules.legal_cards`'s
per-rule intersection, [decisions.md](decisions.md) "Rule demand forms").
Strict-trick legality recurs across the corpus, but not always as rules:
Schnapsen's endgame is the same follow-and-head shape expressed as an in-file
predicate (`follow_ok`) filtering a chosen movement, because its follower
answers outside any trick `round` (see "Mechanics" below). The cascade rules
above stay game-local because their bodies genuinely diverge between Pinochle
and Tarot (trump vocabulary and height helper); a shared parameterized
cascade is a promotion candidate only if a third strict-trick game arrives
whose bodies match one of the existing pairs. Belote is that third game and
its bodies match neither: its cascade (`MustHeadTrumpLead` /
`MustTrumpIfVoidVsOpponents` / `MustOverTrumpVsOpponents` /
`NoUnderTrumpVsPartner`, [games/belote.cardlang](games/belote.cardlang)) is
the corpus's richest — the trump and over-trump obligations are GATED
partnership-relatively (`applies_when` reads `belote_opp_winning()`, the
live trick's current winner against the actor's partnership), the
over-trump target is the trick's best trump from either side, trump leads
must be beaten regardless of who is winning, and the fourth-player
exception (partner winning on a trump: discard or over-trump, never
under-trump) is its own demand — all inside the existing
`applies_when`/`demands`/`if_impossible` running-intersection form, with no
new rule surface.

French Tarot's four-rule cascade (`ExcuseIsExempt`/`MustFollowEffectiveSuit`/
`MustTrumpIfVoid`/`MustOverTrump`) is the same running-intersection shape,
with one addition: `ExcuseIsExempt`'s `exempts:` clause removes the Excuse
from the cascade before the other three rules run, and appends it after every
other legal card once they've narrowed the rest — the Excuse is never subject
to follow-suit/trump/over-trump and never counts toward satisfying them.
`MustFollowEffectiveSuit`'s demand reads the stdlib `tarot_led_suit()` (the first
non-Excuse card played, or "excuse" if only the Excuse has been played so
far) rather than the kernel's own `state.led_suit` (the literal first card,
"excuse" included) — the split that reproduces the reference rule exactly:
when the Excuse is led, the next player faces "void in the led suit" (since
`tarot_led_suit()` is still "excuse", which nobody's non-Excuse cards can
match) and so must trump if able, a quirk the split preserves precisely.

## Winner functions

- `highest_of_led_suit` — no-trump winner
- `TrumpedHighestOfLedSuit(trump_suit)` — with-trump winner
- `tarot_trick_winner` — French Tarot: highest atout, else highest of the
  effective led suit (`tarot_led_suit()`); the Excuse never wins
- `belote_trick_winner` — Belote: highest trump under the J-9 trump order,
  else highest of the led suit under the ace-ten ranking

## Mechanics

- The trick `round` (see above) — owns its own per-trick state (`led_suit`,
  played-cards, `trick_terminated_early`), readable as `state.x` during the pass
  and, for the just-finished round, in the surrounding body. Per
  [appendix.md](appendix.md) (corpus catalogue), this is where these variables
  live; games don't redeclare them.
- **Pinochle's strict-trick play** is the ordinary trick `round` with no new
  construct: legality narrows through the `active_rules:` cascade documented
  under "Rules" above. Meld settles in a plain statement around the
  `pinochle_meld_value(player)` stdlib query (see "Stdlib functions") — a pure
  read of the live hand and the declared trump; `meld_score[team_of(p)] +=
  pinochle_meld_value(p)` is what credits it to the team. Not yet the shared
  combination model floated for Workstream 3 — game-local until a second
  melding game arrives.
- **Auctions run on the auction form of the kernel `round`** (see
  [decisions.md](decisions.md) "The auction form of `round`") — a continuous ring
  over a bid vocabulary (`offering [...] until <pred> outcome <fn>`) with the
  standing bid threaded through the phase's accumulator state. Bridge's auction
  (see [games/bridge.md](games/bridge.md)) runs on it: the vocabulary is
  `[pass, submit_bid, double, redouble]`, and `bridge_auction_outcome` computes the
  declarer from the bid history, producing `contract_finalized | all_pass`. So do
  the ascending-bid auctions — Pinochle's opening-bid/increment ring naming the
  high bidder and Tarot's four levels — and Skat's Reizen call-and-response,
  a role-guarded two-participant ring ([decisions.md](decisions.md), the
  call-and-response bullet under "The auction form of `round`").
  Each configuration is game-local, and stays so deliberately: a corpus
  comparison (Bridge, Pinochle, Tarot, Skat) found the four share only the
  kernel form itself — the accumulator variables, ring topology (continuous /
  shrinking / two-seat-twice), bid vocabulary, and outcome mechanism (named
  function vs inline survivor, and Skat uses the outcome-less betting form)
  all genuinely diverge — so the shared thing IS this `round` form, and a
  promoted `auction` configuration would abstract over instances that agree
  on nothing it could parameterize. Spades and Oh Hell use *inline per-player
  bidding* instead —
  every player bids exactly once in turn, no ascending constraint — so they do not
  use the auction form. Schnapsen configures the same form differently again: a
  single-participant ring whose free actions loop the leader until a card is led
  (see "Mechanics" below).
- **Betting runs on the betting form of the kernel `round`** (see
  [decisions.md](decisions.md) "The auction form of `round`") — the same
  continuous-ring form as an auction, in **`order priority`** (after a raise
  re-opens earlier seats, action returns to the earliest owing seat) and with the
  `outcome` clause omitted (a bet mutates chip/fold state directly, producing no
  variant). Stud (see [games/seven-card-stud.md](games/seven-card-stud.md)) runs a
  `round offering [check, bet, call, fold, raise]` per street over the
  non-folded, non-allin ring. The accumulator (`bet_to_match`, `raises`, per-player
  `bet_by`/`acted`/`committed`) is ordinary phase state; action-legality is the
  move types' own `when:` guards (free-to-act → check/bet; facing a bet →
  call/fold/raise-if-uncapped), not separate rules; the bring-in and first-to-act
  seats come from the `bring_in_seat()` / `first_to_act_seat()` stdlib selectors.
  The showdown settles in plain statements around the `pot_share(player)` stdlib
  query — the chips that player collects under the side-pot layering
  (committed-total levels, ties split with the odd chip to the first winner in
  seat order, uncalled remainder to the best contender), a pure read of the
  betting state and the live hands; `stack[p] := stack[p] + pot_share(p)` is
  what moves the chips. The shared `betting` definition — this configuration of
  the form — is promoted to this catalogue corpus-first at its third instance;
  Stud is the only instance today, so the move types and `pot_share` stay
  game-local.
- **Cribbage's counting hand** runs entirely on ordinary statements — no `round`
  form fits pegging's per-play scoring plus forced-play flow (see
  [kernel-migration.md](kernel-migration.md), Workstream 4). Both players'
  discards and every pegging play are filtered card movements (`move chosen …
  where …`); `repeat until` / `if`/`else` / `skip to next hand` reproduce the
  121-point cutoff one scoring component at a time. The current sub-round's card
  provenance (who played each `play_pile` card) is carried by two `Integer` state
  variables (`seq_bits`/`seq_len`, public information — every player watched the
  count) and decoded by the `peg_origin_of` stdlib query. Six game-local stdlib
  primitives (see "Stdlib functions") — `peg_value`, `peg_pair_points`,
  `peg_run_points`, `peg_origin_of`, `cribbage_show_value`, `cribbage_crib_value`
  — hold the pegging-count and show scorers, in the same game-local shape as
  Stud's `pot_share` and Pinochle's `pinochle_meld_value`; game-local until the
  shared `scoring_component` subsystem lands corpus-first.
- **Schnapsen's hand** runs on the kernel with no mechanic: the leader's mixed
  lead decision (play a card / declare a marriage / exchange the trump jack /
  close the talon) is the **auction form over a single-participant ring** —
  `round offering [play_card, declare_marriage, exchange_trump_jack,
  close_talon] from leader over players where player is leader until trick_pile
  is not empty`. The free actions (exchange/close) leave the predicate false,
  so the ring re-offers the leader; a lead (play or the marriage's queen) flips
  it. `play_card(c : Card)` enumerates the live hand in hand order
  ([decisions.md](decisions.md) "Declared parameter domains"). The
  follower's answer is a filtered chosen movement over the in-file `follow_ok`
  cascade (strict follow-and-head once the talon is closed or exhausted,
  anything while open), and the trick, claim-at-66, and paired talon draws are
  plain statements around the game-local `schnapsen_trick_winner` primitive
  (see "Stdlib functions"), with three `produce` sites for the typed
  `claimed | talon_closed | open_play` outcome.
- **Skat's hand** runs on the kernel with no mechanic: the Reizen is two
  sequential auction `round`s over role-guarded two-participant rings (the
  call-and-response configuration; the 62-value ladder lives in the
  `skat_next_bid` primitive and its exhaustion in the `until` predicate), the
  contract declaration a pair of `offer`s plus a one-draw
  `declare_suit(s : Suit)` round, and the ten tricks three single-actor
  filtered movements per trick over `skat_follow_ok` — like Schnapsen's
  follower, the strict-follow legality is a filter predicate, not an
  `active_rules` cascade, because the reference draws from hand-ordered
  legality where the trick form's rules-driven candidate set is unordered.
  The winner, matador count, and overbid arithmetic are the game-local
  primitives below; scoring writes `score[declarer]` directly (no typed
  outcome — the settlement is a plain two-armed statement).
- **Tichu's hand** runs on the kernel with no mechanic: each climbing trick is
  the climb `round` (above) over the `tichu_lead_options` / `tichu_follows`
  queries, with the Dog as the engine-marked `ends_trick` lead and the
  finishing order folded from the round's terminal `state.shed_first` /
  `state.shed_second`. The push is one chosen 3-card movement per player into
  a per-player `gift` pile (simultaneous by construction — gifts land only
  after every pick), distributed giver-major by draw-free `deal` statements.
  The calls and the Dragon are real decisions: grand tichu is an
  offer per player at the eight-card deal window, small tichu runs on the
  quiescence-lap poll before the push / after it / before each trick, and a
  Dragon-won trick is given by an announced `dragon_to_left` /
  `dragon_to_right` choice; the partnership/finishing lookups and card-point
  table are pure primitives. Scoring writes `score[team]` directly, and the
  playout harness derives its conservation audit from observation events
  (tests/playout_trace.py), not from the rules text.
- **Coup's game** runs on the kernel with no mechanic, at real interactive
  scope: each turn is one `offer` over the seven coin-guarded actions (the
  forced coup at ten coins falls out of the `when:` guards; `steal` /
  `assassinate` / `coup` carry a declared `target : Player` parameter),
  every response window is a poll of real decisions (`offer to <responder>
  one of [challenge, allow]` clockwise from the claimant, first challenge
  closing the window; blocks fold the claimed character into the vocabulary
  — `block_claiming_*`), every influence loss is a chosen movement by the
  loser (the single-actor `as victim` block) flipped
  publicly into `revealed`, and the exchange is a deal-n + chosen-n +
  shuffle. A proven challenge `reveal`s the shown card publicly before
  returning it to the deck, reshuffling, and redrawing; window results
  (`challenge_stands` / `block_stands`) are public phase state.
- `MeldingPhase` — currently a placeholder; real definition deferred.

## Scoring components

> **Status: proposed, not yet built.** No game runs a `scoring_component` /
> `ScoreDelta` subsystem — the runtime has no `apply_components:` construct. The
> decompositions below are the intended design; the corpus scores through
> game-local statements and stdlib primitives (see the Mechanics section above and
> `decisions.md`, "Scoring composition"). This catalogue is promoted corpus-first
> when the subsystem is built.

Composition by summation of `ScoreDelta` outputs; triggered components fire on
specific events via `triggered_by:` clauses (see decisions.md
"Triggered scoring components"). Proposed decompositions for Bridge and Spades
follow.

**Bridge:**

- `ContractTrickScore` — below-the-line points for tricks bid and made.
- `OvertrickScore` — above-the-line points for tricks beyond the contract.
- `UndertrickPenalty` — above-the-line points to defenders when contract fails.
- `SlamBonus` — above-the-line bonus for level-6/7 contracts made.
- `GameBonus`, `RubberBonus` — triggered after `apply_components` on
  the below-line-crosses-100 and games_won-reaches-2 thresholds.

**Spades:**

- `NilScoring` — per-player ±100 for Nil bidders.
- `ContractScoring` — per-team scoring on contract success/failure;
  also accumulates bags on overtricks.
- `BagOverflow` — triggered after `apply_components` on the
  bags-crosses-10 threshold.

All currently game-specific. Generalization candidates will emerge with
more scoring-heavy games (Bridge variants, Pinochle's full meld
scoring). Skat added another scoring shape (game_value computed from
base × multiplier with matadors, hand, schneider, schwarz inputs)
but kept the per-game-helper pattern — the multiplier arithmetic is plain
statements in the game file over the `skat_matadors` /
`skat_effective_loss` primitives rather than a generalized abstraction.

## Phase types

- **Bookkeeping phases** — state mutation only, no rules, no legal moves.
  Examples: `setup` (all games), `reveal_dummy` (Bridge). Structurally a
  regular phase with empty `active_rules` and `legal_moves`; named so the
  file reads like a rulebook.

## Types

The language's type vocabulary, both stdlib (built into the language)
and library (named compositions of primitives). Full design background
in [decisions.md](decisions.md) "Typed object model" and "Knowledge,
visibility, and the projection model".

### Stdlib types (built into the language)

- `Card` — individuated object: `{ suit, rank, attributes, optional facing }`.
- `Resource<Type>` — fungible quantity of the named type. Declared by
  the game's `resources { }` block.
- `Suit`, `Rank` — enumerable value types defined by the game's `cards`
  header.
- `Player` — bare identity.
- `Partnership` (alias: `Team`).
- `Seating` — derived from `players` + `partnerships`. The surface
  operator is `offset_by` (`dealer offset_by left` — seat arithmetic in
  the game's declared direction); partnership lookup is the
  `team_of(player)` stdlib function. An English replacement for
  `offset_by` — the clunkiest-reading operator in the language — is a
  decided direction whose spelling is still open
  ([design-notes/lexical-cleanup.md](design-notes/lexical-cleanup.md) §7).
- `Zone<Contents>` — a container parameterized by what it holds.
  Carries a per-observer visibility declaration (see
  [decisions.md](decisions.md) "Knowledge, visibility, and the
  projection model"), ownership, and structural type (set, ordered,
  stack).
- Zone contents are read through the **English query surface**, never
  methods — the queries bind `card` per candidate ([decisions.md](decisions.md)
  "The expression register"):
  - `cards in <zone> where <pred>` — the matching cards;
  - `number of cards in <zone> [where <pred>]` — count (bare: zone size);
  - `any card in <zone> where <pred>` / `all cards in <zone> where <pred>`;
  - `sum of <expr> over cards in <zone> [where <pred>]`;
  - `highest/lowest <expr> over cards in <zone> [where <pred>] or <default>`;
  - emptiness is `<zone> is empty` / `is not empty`.
  Resource queries (`amount_of(type)`, `total_amount`, `types_present`)
  are unbuilt — the corpus keeps chips as Integer state
  ([roadmap.md](roadmap.md), "Grammar surface deferred by the checker" — resource movements).

### Library zone types

The closed set of stdlib zone types, each shown with the per-observer
projection it encodes. The `Zone<Contents> { composition: ... }`
notation is the model, not a surface a game writes — a game selects a
named type in its `zones {}` block (see [decisions.md](decisions.md),
"Per-observer visibility on zones"). Type parameters use angle
brackets; a parameter of type `Player`, `Team`, etc. is a domain-value
parameter that binds into the projection.

```text
type Hand<Owner: Player>             = Zone<Card>             { composition: identity to Owner, count_only to others }
type SharedHand<Group: Team>         = Zone<Card>             { composition: identity to Group.members, count_only to others }
type PublicHand<Owner: Player>       = Zone<Card>             { composition: identity to all }      // ownership without privacy (e.g. Bridge dummy)
type HiddenPile<Owner: Player>       = Zone<Card>             { composition: identity to Owner, count_only to others }  // a resting pile a player owns but conceals (French Tarot's chien discard) — same profile as Hand, distinct name for a zone that is no longer an active hand
type Deck                            = Zone<Card>             { composition: count_only to all, ordered: yes }
type FaceDownPile                    = Zone<Card>             { composition: count_only to all, ordered: yes }
type Discard                         = Zone<Card>             { composition: identity to all }       // face-up, PUBLIC pile (discards, capture piles, displayed melds, etc.) — contrast HiddenPile, above, for a discard that must stay concealed
type PlayerPile<Owner: Player>       = Zone<Card>             { composition: identity to all }       // face-up pile owned by a player
type TeamPile<Group: Team>           = Zone<Card>             { composition: identity to all }       // face-up pile owned by a team (captured tricks, displayed melds, etc.)
type TrickPile                       = Zone<Card>             { composition: identity to all, ordered: yes }   // current-trick play area
type Muck                            = Zone<Card>             { composition: trivial to all }       // contents not visible going forward; prior observations persist
type Burn                            = Zone<Card>             { composition: trivial to all }       // dealer's burn pile
type RandomizedPile                  = Zone<Card>             { composition: count_only to all, ordered: no }  // cards publicly entered but positionally shuffled (Getaway's waste; some discard variants)
type ChipStack<Owner: Player>        = Zone<Resource<chip>>   { composition: count_only to all }

// Positional-layout types (decisions.md "Position domains and positional
// zones"). Their index parameter is usually a declared position domain
// (`tableau_up[column] : Cascade<column>`) — an UNOWNED index, so both
// projection columns must agree (uniform); the checker rejects an
// owner-differentiated type (Hand, HiddenPile) on a position index.
type Cascade<At: position>           = Zone<Card>             { composition: identity to all, ordered: yes }   // a face-up ordered pile; order public via arrival events (tableau runs, FreeCell columns)
type HiddenStack<At: position>       = Zone<Card>             { composition: count_only to all, ordered: yes } // a face-down pile family (Klondike's tableau_down)
type Foundation<At: position>        = Zone<Card>             { composition: identity to all, ordered: yes }   // an ascending suit pile, A up to K
type Cell<At: position>              = Zone<Card>             { composition: identity to all, capacity: 1 }    // a one-card holding space (FreeCell's free cells) — the one capacity-bounded row

// A "pot" in poker is not just a chip zone — it carries an eligibility
// set determining who can win it. There is no library Pot type: the
// eligibility shape varies by game, and Seven-Card Stud models it with
// game-level state alongside its chip zones rather than a dedicated
// type.
```

Each type also carries a **capacity** (see [decisions.md](decisions.md),
"Zone capacity"): `Cell` holds one card, shown above; every other row is
unbounded and omits it. A movement that would overfill a bounded
destination is a loud runtime error.

These get the corpus's zone declarations down to one line each, with
no loss of meaning. A game's `zones { }` block reads like the rulebook
would describe it:

```cardlang-fragment library_zones
zones {
  deck             : Deck
  hand[player]     : Hand<player>
  trick_pile       : TrickPile
  captured[player] : PlayerPile<player>
}
```

### User-defined types

Games can declare their own record types with a `type Name = { fields }`
block, optionally with a `derived { ... }` clause for computed fields
(see [decisions.md](decisions.md), "User-definable types"). A field's
type is a single type name; the block declares a record, not a zone,
and is not parameterized. No corpus game declares one yet — the
structured values games need (Bridge's contract, a poker pot) are
modelled with flat state variables and functions today — but the
surface is there for a game that needs a genuine record type.

## Operations

The closed operation vocabulary, in the three families set out in
[decisions.md](decisions.md) "The operation vocabulary". Surface verbs are
sugar over a small set of primitives; this is the catalogue.

**Movement** — one primitive; the verb supplies defaults. A movement is a
statement; trick routing is ordinary body movements after a `round` returns.

- `deal` — cards from a source (usually a deck) to recipients, per-recipient visibility; emits a semi-private observation to non-recipients (they see something moved)
- `transfer` — cards or resource units between zones; the amount is an expression and the item names the unit (`transfer 5 chips from stack[A] to pot`, `transfer chosen 3 cards from hand[p] to ...`). See [decisions.md](decisions.md) "Resource amount syntax".
- `move` — the generic relocation (`move all cards from X to Y`). The
  destination-only form `move all cards to <zone>` is a **gather**: it collects
  every card from all other zones into that zone (per-hand cleanup; see
  [decisions.md](decisions.md) "Loop lifecycle")
- `burn` / `muck` — relocate to the burn / muck pile (destination implied by the verb); mucked cards land in a trivial-projection zone, prior observations persisting
- `draw` — take from a pile into a hand

The `from <zone> … to <zone>` form additionally takes an optional `where
<lambda>` clause, narrowing the source pool to matching cards (in source
order) before the selection draws from it — see [decisions.md](decisions.md)
"The operation vocabulary" ("Movement `where` filter"). French Tarot's chien
discard is the corpus's first use (`move chosen 6 cards from hand[p] where
is_pref_discard(card) to discard[p]`).

**Epistemic** — prose statements; no relocation. Signatures are shown below,
but the surface is prose (`shuffle deck`, `reveal proof to all`); call syntax
is for value-returning functions, not operations (see [decisions.md](decisions.md)
"The operation vocabulary"). Full semantics in [decisions.md](decisions.md)
"Knowledge, visibility, and the projection model".

- `peek(target, observer)` — private look (target is a card or zone).
  Catalogued, unbuilt; its forcing function is an epistemic event with no
  physical-zone counterpart (a private look moves nothing, so no projection
  can carry it).
- `reveal(target, observers = all)` — show to observers (default: all).
  BUILT in its public one-card form: `reveal one card from <zone> [where
  <predicate>]` publicly identifies the first matching card in place,
  emitting a `("reveal", zone, card)` observation to every player (Coup's
  proven challenge). The grammar admits only that form — multi-card
  reveals and observer subsets are not expressible until a game forces
  them (same forcing function as `peek`).
- `hide(target, hidden_from = all_except_owner)` — future visibility downgrade; prior knowledge persists under perfect recall
- `shuffle(zone)` — destroys per-card identity knowledge; preserves count-by-type. No-op on pure-resource zones.
- `announce(fact, observers = all)` — purely epistemic event; updates observers' candidate sets
- `expose_top(zone)` — shorthand for `reveal(zone.top, all)`
- `forget(observer, target)` — **breaks perfect recall**; compiler warns; CFR/IS-MCTS guarantees no longer apply

**State-cycle** — `rotate <var> through [<values>]` advances a state variable
through a list (touches no zone).

Card games use `peek` / `reveal` / `shuffle` / `deal` predominantly.
Stud Poker (see [games/seven-card-stud.md](games/seven-card-stud.md))
is the first game to exercise the full vocabulary in non-trivial ways.
Resource-using games (Catan and similar, when they enter scope) use
`transfer` as the primary movement op.

## Stdlib component sets

The component sets a game can name — the individuated content of its
zones (see [decisions.md](decisions.md), "Component sets: cards and
pieces"). A game names one directly in its `cards:` line (a card deck)
or `pieces:` line (a piece set) and does not compose or extend it in the
surface; each entry below shows the set's content, which lives in the
stdlib registry. A **deck** is the card-flavored set, its two axes named
`suit` and `rank` (see also [decisions.md](decisions.md), "Deck
declaration"); these are the card entries:

- `standard52` = the 52-card Anglo-American deck.
  ```text
  { suits: { [S, H, D, C]: [2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A] } }
  ```
  Used by Hearts, Getaway, Spades, Bridge, Seven-Card Stud, Cribbage,
  Oh Hell.

- `tichu56` = the standard 52 plus Tichu's four special cards.
  ```text
  { suits: { [S, H, D, C]: [2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A] },
    specials: [Mahjong, Dog, Phoenix, Dragon] }
  ```
  Used by Tichu.

- `pinochle48` = double Pinochle deck, 6 ranks × 4 suits × 2 copies
  with 10 ranking above K.
  ```text
  { suits: { [S, H, D, C]: [9, J, Q, K, 10, A] }, copies_per_card: 2 }
  ```
  Used by Pinochle.

- `skat32` = 32-card German Skat deck, ace-ten order.
  ```text
  { suits: { [S, H, D, C]: [7, 8, 9, J, Q, K, 10, A] } }
  ```
  Used by Skat, Belote.

- `schnapsen20` = 20-card Schnapsen deck.
  ```text
  { suits: { [S, H, D, C]: [J, Q, K, 10, A] } }
  ```
  Used by Schnapsen.

- `tarot78` = 78-card Tarot deck.
  ```text
  { suits: { [S, H, D, C]: [1..10, J, Cavalier, Q, K], atouts: [1..21] },
    specials: [Excuse] }
  ```
  Used by French Tarot.

A **piece set** names its own two axes and carries none of the card
conventions:

- `xo_marks` = tic-tac-toe's nine marks: five X, four O. Axis `side`
  occupies a card's suit slot, axis `kind` its rank slot.
  ```text
  { side: [x, o], kind: [mark], copies: { x: 5, o: 4 } }
  ```
  Used by tic-tac-toe.

- `breakthrough_men` = breakthrough's thirty-two pawns: sixteen light,
  sixteen dark, all one kind. Same two-axis shape as `xo_marks`.
  ```text
  { side: [light, dark], kind: [man], copies: { light: 16, dark: 16 } }
  ```
  Used by breakthrough.

Each entry captures a set's *composition* only. Card-point values,
ranking for play, follow-suit semantics, and trump status are all
per-game declarations on a deck; a piece set carries none of them.

## Stdlib boards

The spatial boards a game can name in its `board:` line (see
[decisions.md](decisions.md), "Boards and cells"). A game names a
**family** with integer arguments — `board: grid(3, 3)` — and the
closed `BOARDS` registry instantiates it into a fixed set of cells and
lines; unknown family, wrong arity, or out-of-bounds arguments are
rejected at resolve.

- `grid(width, height)` = a rectangular board, `width` files (`a`, `b`,
  … from the left) by `height` ranks (`1`, `2`, … from the bottom),
  each argument in `1..16`. Cells are named file+rank, ordered row-major
  from `a1` (`a1 b1 c1 a2 …`); `lines(k)` returns every straight run of
  `k` consecutive cells along a row, a column, or either diagonal.
  `grid(3, 3)`'s `lines(3)` is the eight tic-tac-toe lines. A grid also
  carries the movement data the class-1 verbs read: the three
  seat-relative forward **directions** `ahead`, `ahead_left`,
  `ahead_right` (its `dir` domain); the per-player **frame** (the second
  seat's is the first's 180-degree rotation); and the **regions**
  `home(player)` (the back two ranks) and `far_row(player)` (the opposite
  edge). Used by tic-tac-toe (placement only) and breakthrough (the full
  movement set).

A board mints two named-member domains: the position domain `cell`
(its cells, on the declared-position substrate) and, for movement, the
move-parameter domain `dir` (its directions). See
[decisions.md](decisions.md), "Boards and cells".

## Stdlib state

Game state variables provided by the language with conventional
defaults. A game opts in by referencing the name; if no reference,
the variable is not allocated.

- `dealer : Player = initial_dealer` — the rotating dealer. Present
  in any game that names a dealer in setup or references `dealer`
  in its body. Initial value comes from the runtime-supplied
  `initial_dealer` (typically resolved by a low-cut, coin flip, or
  similar at game start). Rotation is per-game: `dealer := dealer.left`
  in multi-player clockwise games (Spades, Pinochle, Bridge, Stud,
  Cribbage), `dealer := other player` in two-player games
  (Schnapsen, Cribbage). Hearts and Getaway don't reference
  `dealer` and pay no cost for the stdlib slot.

- **Turn-order start.** The initial position of turn order is
  runtime-supplied, the same way `initial_dealer` is. Dealing games
  name the opener via `dealer` (`dealer.left`); games that derive it
  from a game rule compute it (Hearts/Getaway via the holder of a
  specific card, Stud via the lowest door card); a game with no
  in-rules opener (Coup) relies directly on the runtime seed.
  Pre-game randomization (low-cut, coin-flip, "winner of the last
  game") is the runtime's concern, not the rules engine's. A dedicated
  first-player syntax is deferred — see issue #120.

## Stdlib functions

Standard helpers available across games. A function below (or a game-local
primitive in the same shape) that reads live zones or state does so by the
game's declared names — a coupling the pipeline cannot see — so every such
read is declared in the `PRIMITIVE_READS` registry
(`cardlang/runtime/reads.py`) and made through its typed accessors:
`tests/test_primitive_reads.py` pins the declarations against the game
file's actual zone/state declarations and against each module's source, so
renaming either side fails a static test rather than key-erroring
mid-playout.

- `best_five_card_hand(cards: Set<Card>) → HandRank` — given a set of
  cards (typically 7 for Stud, 5 for draw poker, 2+5 community for
  Hold'em), returns the best 5-card poker hand as a `HandRank`
  value. Stdlib because every poker variant needs it; the
  implementation is standard and not game-specific.
- `next_active_player(p) → Player` — returns the next player
  clockwise from `p` who is not folded and not all-in. A general
  helper; Stud's betting ring no longer needs it — the kernel
  `round`'s per-turn participant filter (`over players where not
  folded[player] and stack[player] > 0 …`) advances the ring and
  skips folded/all-in seats without a draw.
- `player_holding(card) → Player` — returns the player whose hand
  contains the named card. Asking for a card in nobody's hand is a
  game-logic error and fails loudly at the call (every corpus use runs
  right after a full deal, when the card is guaranteed held — a silent
  absence value here would surface later as an unrelated failure).
  Used by Hearts (`player_holding(2 of clubs)`), Getaway
  (`player_holding(ace of spades)`).
- `team_of(player) → Team` — derived from the game's `partnerships`
  declaration; returns the team containing the given player. Used
  in Spades, Pinochle, Bridge, anywhere team-of-trick-winner
  matters.
- `rank_value(card: Card) → Integer` — the card's rank strength under the
  game's `ranking:` declaration (higher = stronger; `rs.rank_index`), deck-
  agnostic. Used by Pinochle's `MustHeadTrick`/`MustOverTrump` rules to find
  the highest card of a suit played so far in the trick.
- `card_value(card: Card) → Integer` — the card's deck-declared card-point
  value (the `values` table on the `cards:` deck; 0 for ranks the deck scores
  nothing for), general-purpose for any point-trick game. Used by Pinochle
  (`trick_score[...] += sum of card_value(card) over cards in trick_pile`), Schnapsen
  (`card_points[w] += sum of card_value(card) over cards in trick_pile`), and Skat
  (the declarer's points: a `sum of … over cards in captured[declarer]` plus the skat).
- `top_of(zone) → Card` / `bottom_of(zone) → Card` — the card at an ordered
  collection's two ends (top = the sequence end, the most recent arrival;
  bottom = the front — decisions.md "Position domains and positional zones",
  sequence orientation). A loud runtime error on an empty collection: guard
  the read (`Z is not empty`). Used throughout Klondike and FreeCell (build
  targets, foundation progression, the moving run's split rank).
- `lines(k) → Collection<Line>` — the board's straight lines of exactly `k`
  cells: every run of `k` consecutive cells along a row, a column, or either
  diagonal (decisions.md "Boards and cells"), for the `any line in lines(k)
  where …` register. A resolve error in a game with no `board:`, and for a
  literal `k` outside the board's span. Used by tic-tac-toe (`lines(3)`, the
  eight winning lines).
- `neighbor(from, along, player) → Cell` — the cell one step along direction
  `along` in `player`'s frame. Total by contract: an off-board step is guarded
  by `has_step`, not returned (decisions.md "Boards and cells", movement).
- `has_step(from, along, player) → Boolean` — whether that step stays on the
  board (the guard that gates `neighbor`).
- `is_diagonal(along) → Boolean` — whether a step along `along` changes file
  (a grid's capturing directions).
- `home(player) → Collection<Cell>` — a player's back two ranks (its setup
  region).
- `far_row(player) → Collection<Cell>` — the far edge of `player`'s frame (its
  reach-to-win goal).
  These five read the `board:` entry (a resolve error in a boardless game, like
  `lines`). Used by breakthrough.

Cribbage's pegging and show scoring, plus the pegging count's card provenance,
are six game-local primitives reading `cardlang/runtime/cribbage.py` — game-local
(like Stud's `pot_share`) until the shared `scoring_component` subsystem lands
corpus-first:

- `peg_value(card: Card) → Integer` — the card's pegging/fifteens pip value:
  A=1, 2..10 = face value, J/Q/K = 10. Distinct from a card's *ranking* (which
  orders cards for trick-taking comparisons).
- `peg_pair_points() → Integer` — pair points (2/6/12 for a two/three/four-of-a-
  kind streak) at the tail of the live `play_pile` count.
- `peg_run_points() → Integer` — run points (the length of the longest run of
  three or more ending at the tail) of the live `play_pile` count.
- `peg_origin_of(card: Card) → Player` — which player played a given live
  `play_pile` card, decoded from the `seq_bits`/`seq_len` play-order state; routes
  each sub-round's cards into `played[dealer]` / `played[nondealer]` at the close.
- `cribbage_show_value(player: Player) → Integer` — a player's pegged hand's show
  score (fifteens, pairs, runs, flush, his-nob) counted against the shared starter.
- `cribbage_crib_value() → Integer` — the dealer's crib show score (a flush needs
  all five cards, unlike the four-card hand flush).

Schnapsen's two-card trick resolution is one game-local primitive reading
`cardlang/runtime/schnapsen.py`, in the same shape as `pot_share` and
`pinochle_meld_value`:

- `schnapsen_trick_winner(leader: Player, trump: Suit?) → Player` — the
  completed trick's winner from the two-card `trick_pile` (the leader played
  first; highest trump, else highest of the led suit — no over-trump
  obligation). Also emits the play/trick_end/trick trace events the playout
  harness audits winners against.

Skat's contract machinery is five game-local primitives reading
`cardlang/runtime/skat.py`; the contract-dependent ones read the declared
contract (`is_grand` / `is_null` / `trump_suit`) from phase state:

- `skat_next_bid(value: Integer) → Integer` — the next of the 62 reachable
  Reizen game values above `value`, or 0 when the ladder is exhausted (the
  auction's `until` reads 0 as "the speaker cannot raise").
- `skat_follow_ok(p: Player, c: Card) → Boolean` — follow-class legality
  against the led card (`trick_pile[0]`): the four jacks and the trump suit
  are one class in Suit and Grand; Null has plain suits and no trumps.
- `skat_trick_winner(leader: Player) → Player` — the completed three-card
  trick's winner (highest trump, else highest of the led suit; Null's own
  rank order). Emits the play/trick_end/trick traces the playout harness
  recomputes winners from.
- `skat_matadors(p: Player) → Integer` — the with/without run from the club
  Jack down the trump order, over `p`'s hand plus the skat.
- `skat_effective_loss(game_value: Integer, bid: Integer, base: Integer) →
  Integer` — the loss base under the overbid rule (the smallest multiple of
  the base covering the bid; a ceiling the expression language lacks).

500's contract machinery is six game-local primitives reading
`cardlang/runtime/five_hundred.py`; the play-legality ones read the declared
contract (`trump_suit` / `is_misere` / `is_open_misere` / `joker_suit` /
`declarer`) from phase state:

- `five_hundred_next_bid(standing: Integer, strain: Suit?) → Integer` — the
  cheapest rung in the strain that beats the standing contract ordinal on
  the 27-rung ladder (misère above the sevens, open misère between 10♦ and
  10♥), or 0 when none exists — also 0 for the deck-derived "joker"
  pseudo-strain, which is never biddable.
- `five_hundred_bid_value(rank: Integer) → Integer` — the ordinal's score
  value (the Pagat table; misère 250, open misère 500); off-ladder ordinals
  refuse loudly.
- `five_hundred_bid_level(rank: Integer) → Integer` — a suit/no-trump
  ordinal's trick target (6..10); the misères have none and refuse.
- `five_hundred_follow_ok(p: Player, c: Card) → Boolean` — follow-class
  legality against the led card: under a trump contract the joker, right
  bower, and left bower are members of the trump suit in all respects (the
  Skat follow-class shape plus the left bower's effective-suit change); in
  the no-trump family the joker is suitless (playable only when void; FORCED
  when void in a misère) or, once nominated, a member of its suit.
- `five_hundred_lead_ok(p: Player, c: Card) → Boolean` — lead legality: an
  un-nominated joker may not be led in the no-trump family before the
  holder's last card (the modelled form of the lead-nomination rule —
  [games/five-hundred.md](games/five-hundred.md), "Chosen ruleset").
- `five_hundred_trick_winner(leader: Player) → Player` — the completed
  trick's winner (three cards in a misère — the declarer's partner sits
  out — else four): highest trump (joker > bowers > A..), else highest of
  the led class; an un-nominated joker wins any no-trump trick it is played
  to. Emits the play/trick_end/trick traces the playout harness recomputes
  winners from.

Tichu's hand needs twelve game-local primitives plus the two climb queries,
all reading `cardlang/runtime/tichu.py` (the combination engine itself stays
`cardlang/runtime/combinations.py`); the finishing-order readers consume the
`out_first` / `out_second` phase state:

- `tichu_lead_options` / `tichu_follows` — the climb `round`'s queries: every
  combination a hand can lead (plus the Dragon/Phoenix/Dog lead singles, the
  Dog marked `ends_trick`), and the follows that beat the standing play (same
  kind and length and higher, any bomb, the Dragon/Phoenix single answers).
- `tichu_mahjong_holder() → Player` — leads the first trick (post-push).
- `tichu_players_holding() → Integer` — non-empty hands (the hand ends ≤ 1).
- `tichu_double_victory() → Boolean` — the first two finishers are teammates.
- `tichu_partner(p: Player) → Player`, `tichu_opponent_team(p: Player) →
  Team`, `tichu_first_out() → Player`, `tichu_next_holder(p: Player) →
  Player` — partnership and finishing lookups (`next_holder` is the
  post-trick leader advance, counterclockwise past empty hands).
- `tichu_dragon_won() → Boolean` — the completed trick's standing play was
  the lone Dragon, read off the round's terminal state like the `state`
  pronoun.
- `tichu_card_points(c: Card) → Integer` — K/10 = 10, 5 = 5, Dragon +25,
  Phoenix −25 (100 per hand).

Coup's bookkeeping is four game-local primitives in
`cardlang/runtime/coup.py`, pure reads plus one trace emitter (every window
response, claim, and target is a chooser decision in the DSL body — see the
Mechanics entry):

- `coup_players_in() → Integer`, `coup_next_in_game(p: Player) → Player`,
  `coup_has_char(p: Player, r: String) → Boolean` — in-game scans and the
  challenge-proof lookup (pure reads).
- `coup_game_summary() → Integer` — the `coup_game` trace emitter (the
  50-coin / 15-card conservation invariants and the finals). The
  reveal-sequence golden derives from observation events at the harness
  layer instead (tests/playout_trace.py).

French Tarot's non-uniform 78-card deck (suit×rank card points that vary by
suit, an effective led suit that isn't the kernel's own, and a settlement the
`ranking:`/`card_value` general machinery can't express — see
[decisions.md](decisions.md) "Deck declaration") needs six game-local
primitives, all reading `cardlang/runtime/tarot.py`:

- `tarot_card_points(card: Card) → Integer` — the doubled card-point value
  (printed value × 2, so all integers; the 78 cards sum to 182). K/Q/Cavalier/J
  score 9/7/5/3 in a plain suit; a bout (the Excuse, the 1 of atouts, the 21)
  scores 9; every other card scores 1.
- `tarot_trump_height(card: Card) → Integer` — an atout's rank as an int
  (1..21) for the over-trump comparison; 0 for a non-atout.
- `tarot_led_suit() → Suit` — the effective led suit of the live trick: the
  first non-Excuse card played so far, or "excuse" if only the Excuse has
  been played — distinct from the kernel's own `state.led_suit` (the literal
  first card, "excuse" included), which gates the rules' `applies_when`
  instead of naming the follow-suit demand (see the Rules section above).
- `tarot_trick_winner` — a **winner function** (named on `round …
  winner tarot_trick_winner`, not called with parens): highest atout if any
  was played, else highest of the effective led suit; the Excuse never wins.
- `tarot_excuse_player() → Player?` — which player (if any) played the Excuse
  in the trick that just completed, read off the round's exposed terminal
  state (`state.played`) the same way the `state` pronoun is.
- `tarot_per_opp(pb: Integer) → Integer` — the zero-sum per-opponent
  settlement amount: the bouts-conditional threshold ({3 bouts: 36, 2: 41, 1:
  51, 0: 56} doubled points), the taker's doubled card points (`captured` and
  `discard`, plus the chien's at Garde sans le chien — the chien is never
  moved there, so it counts where it sits), the petit-au-bout adjustment
  `pb`, and the bid multiplier.

Belote's within-trump rank reorder (J > 9 > A > 10 > K > Q > 8 > 7 —
suit-contextual, so outside the `ranking:` declaration's scope; the
plain-suit order is `ranking: ace-ten`), its partnership-gated obligations,
and its declaration combinations need ten game-local primitives, all reading
`cardlang/runtime/belote.py`:

- `belote_trump_height(card: Card) → Integer` — a rank's strength within
  the trump suit (1..8), the over-trump comparison's currency (the demand
  filters on `card.suit is trump_suit` itself).
- `belote_trick_winner` — a **winner function** (named on `round …
  winner belote_trick_winner`): highest trump under the J-9 trump order if
  any was played, else highest of the led suit under the ace-ten
  `rank_index`.
- `belote_opp_winning() → Boolean` — is the live, partial trick's current
  winner an opponent of the acting player? The partnership-relative gate on
  the trump/over-trump obligations, read in the rules' `applies_when` off
  the live round accumulator plus the actor `legal_cards` bound.
- `belote_royal_player() → Player?` — who played a trump King or Queen in
  the trick that just completed (a pure read of public facts), aiming the
  Belote-Rebelote window's `offer`.
- `belote_best_is(p: Player, class: Integer, rank: Rank, trump: Boolean) →
  Boolean` — the declaration moves' guard: the stated combination is the
  hand's best, exactly (no false, weaker, or absent declarations).
- `belote_decl_points(p)` / `belote_decl_class(p)` / `belote_decl_height(p)`
  / `belote_decl_trump(p)` — the best combination's points, class, height,
  and trump flag (the scoring bookkeeping behind the announced content).
- `belote_decl_size(p: Player) → Integer`, `belote_decl_slot(p: Player,
  k: Integer, card: Card) → Boolean` — the per-card enumeration of the best
  combination, walked by the entitled side's showing (`reveal one card from
  hand[p] where belote_decl_slot(p, show_k, card)`).

`Card.__str__`'s rendering (used by observation logs and `to_string` in the
OpenSpiel encoding) maps atouts to `★` and the Excuse to `☆` alongside the
four standard suit glyphs, falling back to `:<suit>` for any other suit — so a
future non-French-suited deck renders without crashing.

More will be added as games surface common helpers.
