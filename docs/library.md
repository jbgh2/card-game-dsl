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

A climbing trick (Big Two; Tichu, pending its migration) is the kernel `round`
construct in its **climbing form** — one trick where each play is a *combination*,
not a single card. The leader leads a combination drawn from the engine, then each
participant beats the standing play with a higher one **of the same size** or
passes; a pass does not drop a player. The trick ends when action returns to the
last player who played (everyone else passed one full lap), or the `until`
predicate holds (a player has shed out). The last player to play is bound as
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

- **`until <predicate>` ends the trick — and the hand.** It is the shed-out gate:
  Big Two's `any player p: hand[p] is empty` stops the trick the instant a player
  empties (matching the rule that the hand ends on the first shed). It is checked
  after each play, so the rest of that trick is not offered.

- **Routing is the surrounding body, not a parameter** (as for the trick). Big Two
  routes the spent pile to the discard (`move all cards from trick_pile to discard`)
  and passes the lead to the winner (`leader := outcome`); a point-capturing game
  (Tichu) will route to a team pile instead.

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
- `income` / `foreign_aid` / `coup` / `tax` / `assassinate` / `steal` /
  `exchange` — Coup turn actions (general and character actions)
- `challenge` — contest a character claim during a challenge window (Coup)
- `block` — counteract an action by claiming a blocking character (Coup)

## Rules

- `MustFollowSuit` — constrains `play_to_trick`; the canonical follow-suit rule
- `MustHeadIfFollowing` — constrains `play_to_trick`; must beat highest of led suit when following
- `MustTrumpIfVoid` — constrains `play_to_trick`; must trump when void in led suit
- `MustOvertrumpIfTrumping` — constrains `play_to_trick`; must beat highest trump played when trumping
- `BidExceedsCurrent` — constrains `submit_bid`; ascending auction rule
- `BidIsLegalIncrement` — constrains `submit_bid`; bid increment validity
- `NoLeadingHeartsUntilBroken` — Hearts-specific
- `NoLeadingSpadesUntilBroken` — Spades-specific
- *Generalization candidate:* `NoLeadingSuitUntilBroken(suit)` — parameterize
  by suit so Hearts and Spades both use the same rule

## Outcome functions

- `highest_of_led_suit` — no-trump outcome
- `TrumpedHighestOfLedSuit(trump_suit)` — with-trump outcome

## Mechanics

- The trick `round` (see above) — owns its own per-trick state (`led_suit`,
  played-cards, `trick_terminated_early`), readable as `state.x` during the pass
  and, for the just-finished round, in the surrounding body. Per
  [appendix.md](appendix.md) (corpus catalogue), this is where these variables
  live; games don't redeclare them.
- **Auctions run on the auction form of the kernel `round`** (see
  [decisions.md](decisions.md) "The auction form of `round`") — a continuous ring
  over a bid vocabulary (`offering [...] until <pred> outcome <fn>`) with the
  standing bid threaded through the phase's accumulator state. Bridge's auction
  (see [games/bridge.md](games/bridge.md)) runs on it today: the vocabulary is
  `[pass, submit_bid, double, redouble]`, and `bridge_auction_outcome` computes the
  declarer from the bid history, producing `contract_finalized | all_pass`. The
  ascending-bid auctions (Pinochle's opening-bid/increment ring naming the high
  bidder; Tarot's four levels; Skat's call-and-response) move onto the same form as
  the migration reaches them ([kernel-migration.md](kernel-migration.md)); each is
  game-local until the shared `auction` definition — the ascending-bid
  configuration of this form — is promoted to this catalogue corpus-first at its
  third instance. Spades and Oh Hell use *inline per-player bidding* instead —
  every player bids exactly once in turn, no ascending constraint — so they do not
  use the auction form.
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
- `ChallengeWindow` (see [games/coup.md](games/coup.md)) — Coup.
  Parameterized over the claimant and the claimed character; resolves
  to `claim_stands | claim_refuted`. Offers each other in-game player a
  `challenge`/`pass` decision in clockwise priority and adjudicates the
  first challenge: proof → challenger loses influence and the proven
  card is returned-shuffled-redrawn (a stdlib-op composition, not a
  custom memory event); bluff → claimant loses influence. The reusable
  bluff-adjudication unit.
- `BlockWindow` (see [games/coup.md](games/coup.md)) — Coup.
  Parameterized over the eligible blockers and the set of blocking
  characters; resolves to `blocked | not_blocked`. A declared block is
  itself a character claim, so it opens a nested `ChallengeWindow` on
  the blocker.
- `MeldingPhase` — currently a placeholder; real definition deferred.

## Scoring components

Introduced in Bridge, now in Bridge, Spades, and Cribbage. Composition
by summation of `ScoreDelta` outputs; triggered components fire on
specific events via `triggered_by:` clauses (see decisions.md
"Triggered scoring components").

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

**Cribbage:**

- `HisHeels` — triggered on `cut_starter` event when the starter is a Jack.
- `PeggingFifteen`, `PeggingThirtyOne` — triggered on `play_card` when
  the running total reaches 15 or 31.
- `PeggingPair`, `PeggingRun` — triggered on `play_card` from suffix
  patterns on the play pile.
- `PeggingLastCard` — triggered on `end_of_round`.
- `ShowFifteens`, `ShowPairs`, `ShowRuns`, `ShowFlush`, `ShowHisNob`
  — per-batch components, applied three times (non-dealer hand, dealer
  hand, crib).

All currently game-specific. Generalization candidates will emerge with
more scoring-heavy games (Bridge variants, Pinochle's full meld
scoring). Skat added another scoring shape (game_value computed from
base × multiplier with matadors, hand, schneider, schwarz inputs)
but kept the per-game-helper pattern — the calculation lives in
SkatScoring rather than a generalized abstraction.

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
type Deck                            = Zone<Card>             { composition: count_only to all, ordered: yes }
type FaceDownPile                    = Zone<Card>             { composition: count_only to all, ordered: yes }
type Discard                         = Zone<Card>             { composition: identity to all }       // face-up pile (discards, capture piles, displayed melds, etc.)
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
- `value(card: Card) → Integer` — the card's pegging-pip value as
  used in Cribbage and adding games: A=1, 2..10 = face value, J/Q/K = 10.
  Distinct from a card's *ranking* (which orders cards for
  trick-taking comparisons).

More will be added as games surface common helpers.
