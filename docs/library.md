# Standard library

The named compositions that have emerged from the five-game corpus. Most users
write only in this layer; the primitives in [model.md](model.md) are for the
10% pushing the edges.

## The trick: a `round` configuration

A trick is the kernel `round` construct ([model.md](model.md)), not a built-in
mechanic. Each participant in turn order from the leader plays one card; the
lead sets the led suit; an optional early-termination predicate may end the pass
before everyone has played; then an outcome function selects a player, bound as
`outcome` for the surrounding body, which does the routing.

```
round <move_type> from <leader> over <participants>
      source <zone> into <zone> outcome <fn> [trump <expr>] [early <predicate>]
```

Key design notes:

- **`outcome`, not `winner`.** The round computes which player the play selects;
  whether that is a "winner" or a "loser" is a routing concern. In Hearts the
  outcome is the winner (cards go to their captured pile); in Getaway the outcome
  picks up the pile only when the trick terminated early.

- **Routing is the surrounding body, not a parameter.** After the round returns,
  the body relocates the played cards: Hearts routes unconditionally
  (`move all cards from trick_pile to captured[outcome]`); Getaway branches on
  the round's terminal state (`if state.trick_terminated_early { … } else { … }`).
  A finished round's terminal state stays readable as `state.x` until the next
  round runs.

- **`early <predicate>` is optional.** Most games omit it (the pass proceeds until
  all participants have played). Getaway uses `early on_play_of_tochoo`: a tochoo
  (an off-suit play, only possible when void) ends the trick.

- **`trump <expr>` is optional.** Omitted, the round uses the game-level `trump:`
  declaration (Spades); supplied, it overrides per hand (Oh Hell turns one up each
  deal; Bridge's contract sets it, none for no-trump).

- **The round emits observation events** for each play, with visibility derived
  from the zones. Hidden-info and perfect-info games use the same construct; the
  difference is zone visibility.

- **The next leader is the body's choice.** The round does not assume
  "winner-leads-next"; the surrounding phase sets `leader := outcome` (or not).

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
`outcome` for the surrounding body, which routes the pile and the next lead.

```
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

- **No `outcome` function.** Unlike the trick form, the winner is not a function of
  the cards — it is the loop's last player to play, returned directly and bound as
  `outcome`. A combination play moves a *computed card-set*, which the movement
  grammar (cards by count) cannot name, so the construct performs the movement
  itself ([decisions.md](decisions.md) "The climbing form of `round`").

- **`until <predicate>` ends the trick — and, when the game wants it, the
  hand.** It is the shed-out gate: Big Two's `any player p: hand[p] is empty`
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
  and passes the lead to the winner (`leader := outcome`); Tichu routes to a team
  pile (`captured[team_of(outcome)]`) — or to a random opponent's on a Dragon
  win, or to the discard with the lead passing to the partner on the Dog.

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

- `MustFollowSuit` — constrains `play_to_trick`; the canonical follow-suit rule
  (Hearts, Getaway, Spades, Bridge, Oh Hell, Pinochle, French Tarot — Tarot's
  demand reads `tarot_led_suit()`, the effective led suit, not the raw
  `state.led_suit`; see below)
- `MustHeadTrick` — constrains `play_to_trick`; must beat the highest card of
  the led suit played so far when following (Pinochle)
- `MustTrumpIfVoid` — constrains `play_to_trick`; must trump when void in the
  led suit (Pinochle, French Tarot)
- `MustOverTrump` — constrains `play_to_trick`; must beat the highest trump
  played so far when trumping (Pinochle, French Tarot)
- `ExcuseIsExempt` — constrains `play_to_trick`; `exempts:` the Excuse from
  every obligation in the cascade (French Tarot). The corpus's first use of
  the rule `exempts:` clause ([decisions.md](decisions.md) "Rule exemption");
  see below.
- `BidExceedsCurrent` — constrains `submit_bid`; ascending auction rule
- `BidIsLegalIncrement` — constrains `submit_bid`; bid increment validity
- `NoLeadingHeartsUntilBroken` — Hearts-specific
- `NoLeadingSpadesUntilBroken` — Spades-specific
- *Generalization candidate:* `NoLeadingSuitUntilBroken(suit)` — parameterize
  by suit so Hearts and Spades both use the same rule

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
answers outside any trick `round` (see "Mechanics" below). Rules are not yet a
shared/reusable definition the way move types and mechanics are — each game
declares its own rule bodies — so promoting a common cascade waits on a second
`active_rules` DSL instance.

French Tarot's four-rule cascade (`ExcuseIsExempt`/`MustFollowSuit`/
`MustTrumpIfVoid`/`MustOverTrump`) is the same running-intersection shape,
with one addition: `ExcuseIsExempt`'s `exempts:` clause removes the Excuse
from the cascade before the other three rules run, and appends it after every
other legal card once they've narrowed the rest — the Excuse is never subject
to follow-suit/trump/over-trump and never counts toward satisfying them.
`MustFollowSuit`'s demand reads the stdlib `tarot_led_suit()` (the first
non-Excuse card played, or "excuse" if only the Excuse has been played so
far) rather than the kernel's own `state.led_suit` (the literal first card,
"excuse" included) — the split that reproduces the reference rule exactly:
when the Excuse is led, the next player faces "void in the led suit" (since
`tarot_led_suit()` is still "excuse", which nobody's non-Excuse cards can
match) and so must trump if able, a quirk the split preserves precisely.

## Outcome functions

- `highest_of_led_suit` — no-trump outcome
- `TrumpedHighestOfLedSuit(trump_suit)` — with-trump outcome
- `tarot_trick_winner` — French Tarot: highest atout, else highest of the
  effective led suit (`tarot_led_suit()`); the Excuse never wins

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
  Each is game-local until the shared `auction` definition — the ascending-bid
  configuration of this form — is promoted to this catalogue corpus-first at its
  third instance. Spades and Oh Hell use *inline per-player bidding* instead —
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
  close_talon] from leader over players where player == leader until trick_pile
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
  The two rule-level randomnesses of the migrated scope — the Tichu/Grand-
  Tichu call gates and the Dragon's trick going to a random opponent — are
  the `tichu_call_roll` / `tichu_dragon_recipient` rng primitives; the
  partnership/finishing lookups and card-point table are pure primitives; and
  `tichu_hand_summary` emits the hand's conservation trace. Scoring writes
  `score[team]` directly.
- **Coup's game** runs on the kernel with no mechanic: each turn is one
  `offer` over the seven coin-guarded actions (the forced coup at ten coins
  falls out of the `when:` guards), every influence loss is a chosen
  movement by the loser (the single-actor `for each player q: if q == X`
  idiom) flipped publicly into `revealed`, and the exchange is a
  deal-n + chosen-n + shuffle. At the migrated random-play scope the
  challenge and block windows carry NO player decisions — the gates,
  the blocker's claimed character, and the action targets are rng — so
  they are inline statements around game-local rng primitives at the
  reference's exact draw sites, with the window results
  (`challenge_stands` / `block_stands`) as public phase state. A proven
  challenge returns the claimed card to the deck, reshuffles, and redraws
  (hidden movements; real Coup shows the proven card — the
  interactive-windows scope upgrade, [kernel-migration.md](kernel-migration.md)
  Workstream 5, brings response windows as decisions in priority order, a
  Player target domain, and a `reveal` epistemic op).
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
- `Seating` — derived from `players` + `partnerships`; exposes
  `partner_of`, `left_of`, `right_of`, `LHO_of`, `RHO_of`, `opposite_of`.
- `Zone<Contents>` — a container parameterized by what it holds.
  Carries a per-observer visibility declaration (see
  [decisions.md](decisions.md) "Knowledge, visibility, and the
  projection model"), ownership, and structural type (set, ordered,
  stack).
- `ZoneContents` — the query interface on zones and intermediate
  collections. Common operations across all zone types: `where`,
  `count`, `non_empty`, `empty`. Card-specific operations (`cards_of_suit`,
  `highest_of_suit`, `has_card_of_suit`, `highest_by`,
  `contains_card_of_suit`) apply to `Zone<Card>`. Resource-specific
  operations (`amount_of(type)`, `total_amount`, `types_present`) apply
  to `Zone<Resource>`.

### Library zone types

Common zone configurations, named as aliases over the primitive
`Zone<Contents> { composition: ... }` form. Parameters use angle
brackets for type parameters (per standard language conventions);
parameters with type `Player`, `Team`, etc. are domain-value
parameters that bind into the visibility declaration.

```
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

// A "pot" in poker is not just a chip zone — it carries an eligibility
// set determining who can win it. Pot is therefore a user-defined type
// in games that need it (see games/seven-card-stud.md), wrapping a chip
// zone with the additional structural field. No library Pot type — the
// eligibility shape varies by game.
```

These get the corpus's zone declarations down to one line each, with
no loss of meaning. A game's `zones { }` block reads like the rulebook
would describe it:

```
zones {
  deck             : Deck
  hand[player]     : Hand<player>
  trick_pile       : TrickPile
  captured[player] : Captured<player>
}
```

### User-defined types

Games can declare their own types with a `type Name = { fields }`
block, optionally with a `derived { ... }` clause for computed fields.
Bridge declares `Contract` and `HandResult`; Spades declares
`SpadesHandResult`; Stud declares `Pot` and `HandRank`. See the
relevant game files in [games/](games/).

User-defined types can themselves be parameterized:

```
type DiscardLayer<Layer: Integer> = Zone<Card> { composition: identity to all }
```

Parameterization uses the same angle-bracket convention as stdlib
generics; the parameter binds into the type body.

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
c => is_pref_discard(c) to discard[p]`).

**Epistemic** — prose statements; no relocation. Signatures are shown below,
but the surface is prose (`shuffle deck`, `reveal proof to all`); call syntax
is for value-returning functions, not operations (see [decisions.md](decisions.md)
"The operation vocabulary"). Full semantics in [decisions.md](decisions.md)
"Knowledge, visibility, and the projection model".

- `peek(target, observer)` — private look (target is a card or zone)
- `reveal(target, observers = all)` — show to observers (default: all)
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

## Stdlib decks

Named deck compositions usable in the `cards:` block. See
[decisions.md](decisions.md) "Deck declaration" for the underlying
form. Games either use one of these directly (`cards: standard52`)
or compose with extras (`cards: standard52 + { specials: [...] }`).

- `standard52` = the 52-card Anglo-American deck.
  ```
  { suits: { [S, H, D, C]: [2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A] } }
  ```
  Used by Hearts, Getaway, Spades, Bridge, Seven-Card Stud, Cribbage,
  Oh Hell. Tichu uses `standard52 + { specials: [Mahjong, Dog,
  Phoenix, Dragon] }`.

- `pinochle48` = double Pinochle deck, 6 ranks × 4 suits × 2 copies
  with 10 ranking above K.
  ```
  { suits: { [S, H, D, C]: [9, J, Q, K, 10, A] }, copies_per_card: 2 }
  ```
  Used by Pinochle.

- `skat32` = 32-card German Skat deck, ace-ten order.
  ```
  { suits: { [S, H, D, C]: [7, 8, 9, J, Q, K, 10, A] } }
  ```
  Used by Skat.

- `schnapsen20` = 20-card Schnapsen deck.
  ```
  { suits: { [S, H, D, C]: [J, Q, K, 10, A] } }
  ```
  Used by Schnapsen.

- `tarot78` = 78-card Tarot deck.
  ```
  { suits: { [S, H, D, C]: [1..10, J, Cavalier, Q, K], atouts: [1..21] },
    specials: [Excuse] }
  ```
  Used by French Tarot.

Each constant captures a deck's *composition* only. Card-point
values, ranking for play, follow-suit semantics, and trump status
are all per-game declarations on top.

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
  first-player syntax is deferred — see [roadmap.md](roadmap.md).

## Stdlib functions

Standard helpers available across games.

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
  contains the named card (or none if no player holds it).
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
  (`trick_score[...] += sum over trick_pile as c: card_value(c)`), Schnapsen
  (`card_points[w] += sum over trick_pile as c: card_value(c)`), and Skat
  (the declarer's points: `sum over captured[declarer]` plus `sum over skat`).

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

Tichu's hand needs twelve game-local primitives plus the two climb queries,
all reading `cardlang/runtime/tichu.py` (the combination engine itself stays
`cardlang/runtime/combinations.py`); the finishing-order readers consume the
`out_first` / `out_second` phase state:

- `tichu_lead_options` / `tichu_follows` — the climb `round`'s queries: every
  combination a hand can lead (plus the Dragon/Phoenix/Dog lead singles, the
  Dog marked `ends_trick`), and the follows that beat the standing play (same
  kind and length and higher, any bomb, the Dragon/Phoenix single answers).
- `tichu_call_roll() → Integer` — one player's Tichu/Grand-Tichu gate at the
  migrated random-play scope (200 at 4%, else 100 at 8%, else 0; rng).
- `tichu_dragon_recipient(w: Player) → Player` — the opponent given the
  Dragon's trick (rng at the same site as the reference).
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
- `tichu_hand_summary() → Integer` — emits the `tichu_hand` trace (double
  victory, captured card points) the playout harness audits conservation
  against.

Coup's window randomness and bookkeeping are twelve game-local primitives
reading `cardlang/runtime/coup.py` (the rng ones consume the reference's
exact draws; the migrated scope plays randomly — see the Mechanics entry):

- `coup_challenger(claimant: Player) → Player?` — the challenge gate: scan
  in-game opponents clockwise from the claimant, each challenging at 18%;
  first hit or none.
- `coup_fa_blocker(actor: Player) → Player?` — foreign aid's block gate
  (seat-order scan at 30%); `coup_block_roll() → Boolean` — the
  single-blocker gate (the assassination/steal target).
- `coup_duke_claim()` / `coup_contessa_claim()` / `coup_steal_block_claim()
  → String` — the blocker's claimed character (each consumes the
  reference's `rng.choice`; steal's is the one real two-way pick).
- `coup_random_target(actor: Player) → Player` — a random in-game opponent.
- `coup_players_in() → Integer`, `coup_next_in_game(p: Player) → Player`,
  `coup_has_char(p: Player, r: String) → Boolean` — in-game scans and the
  challenge-proof lookup (pure reads).
- `coup_note_reveal(p: Player) → Integer`, `coup_game_summary() → Integer` —
  the `coup_reveal` / `coup_game` trace emitters (the reveal-sequence golden
  and the 50-coin / 15-card conservation invariants).

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
- `tarot_trick_winner` — a **trick outcome function** (named on `round …
  outcome tarot_trick_winner`, not called with parens): highest atout if any
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

`Card.__str__`'s rendering (used by observation logs and `to_string` in the
OpenSpiel encoding) maps atouts to `★` and the Excuse to `☆` alongside the
four standard suit glyphs, falling back to `:<suit>` for any other suit — so a
future non-French-suited deck renders without crashing.

More will be added as games surface common helpers.
