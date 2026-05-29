# Standard library

The named compositions that have emerged from the five-game corpus. Most users
write only in this layer; the primitives in [model.md](model.md) are for the
10% pushing the edges.

## The Trick mechanic

After three implementations, the Trick mechanic stabilized with these
parameters:

```
mechanic Trick (
  participants:        List<Player>
  leader:              Player
  source_zone:         per-player Zone
  chooser_for:         (Player) → Player       // default: identity (actor chooses)
  play_zone:           shared Zone
  play_rules:          RuleSet
  outcome:             (played_cards, state) → Player
  routing:             (played_cards, state, outcome) → List<Move>
  early_termination:   (state) → Boolean       // default: false
)
```

Key design notes:

- **`outcome`, not `winner`.** The mechanic computes which player is selected
  by the play; whether that's a "winner" or a "loser" is a routing concern.
  In Hearts the outcome is the winner (cards go to their captured pile). In
  Getaway the outcome may be the loser depending on whether the trick was
  terminated early.

- **`routing` is a function, not a destination.** Hearts can use a trivial
  routing function; Getaway needs conditional routing depending on whether
  the trick was terminated early.

- **`early_termination` is parameterized.** Most games leave it at default
  false (the trick proceeds until all participants have played). Getaway
  uses it.

- **The mechanic itself emits observation events** for each play, with
  visibility derived from the zones. Hidden-info vs perfect-info games use
  the same mechanic; the difference is in zone visibility.

- **The mechanic produces shared state** (`next_leader`) which the enclosing
  phase reads to start the next trick. The mechanic does not assume
  "winner-leads-next" — the enclosing phase makes that choice.

- **`chooser_for` defaults to identity.** Almost every game leaves it
  unset, meaning each actor chooses their own card. Bridge passes a
  game-defined helper that routes dummy's turn to declarer. See
  [decisions.md](decisions.md) "Delegated play".

## Move types

- `play_to_trick` — source: hand, destination: trick_pile
- `transfer_between_hands` — source: hand, destination: another hand
- `submit_bid` — source: nothing material, sets a state variable
- `pass` — source: nothing material, marks player as out of auction
- `declare_trump_suit` — source: nothing material, sets trump state
- `steal_left` — source: another player's hand, destination: own hand (Getaway)
- `bring_in` — forced opening bet at third street (Stud)
- `check` — pass-action when there's no bet to match (Stud)
- `call` — match the current bet (Stud)
- `bet` — open a betting round (Stud)
- `raise` — increase the current bet (Stud)
- `fold` — exit the current hand (Stud)

## Rules

- `MustFollowSuit` — constrains `play_to_trick`; the canonical follow-suit rule
- `MustHeadIfFollowing` — constrains `play_to_trick`; must beat highest of led suit when following
- `MustTrumpIfVoid` — constrains `play_to_trick`; must trump when void in led suit
- `MustOvertrumpIfTrumping` — constrains `play_to_trick`; must beat highest trump played when trumping
- `BidExceedsCurrent` — constrains `submit_bid`; ascending auction rule
- `BidIsLegalIncrement` — constrains `submit_bid`; bid increment validity
- `BringInMandatory` — constrains `bring_in`; bring-in player must post the bring-in amount (Stud)
- `NoLeadingHeartsUntilBroken` — Hearts-specific
- `NoLeadingSpadesUntilBroken` — Spades-specific
- *Generalization candidate:* `NoLeadingSuitUntilBroken(suit)` — parameterize
  by suit so Hearts and Spades both use the same rule

## Outcome functions

- `highest_of_led_suit` — no-trump outcome
- `TrumpedHighestOfLedSuit(trump_suit)` — with-trump outcome

## Mechanics

- `Trick` (see above) — owns its own per-trick state (`led_suit`,
  played-cards, `trick_terminated_early`). Per [appendix.md](appendix.md)
  (corpus catalogue), this is where these variables live; games don't
  redeclare them.
- `Auction` (see [games/pinochle.md](games/pinochle.md)) — parameterized
  over participants, opening bid, increment, outcome callback. Owns its
  own per-auction state (`current_bid`, `last_bidder`, `passed[player]`).
  Used by Pinochle; applicable to Spades (when refactored to use Auction
  rather than its current inline bidding), Oh Hell, and any other
  ascending-bid game.
- `BridgeAuction` (see [games/bridge.md](games/bridge.md)) — Bridge-specific
  specialization; placeholder. Real definition deferred; needs
  doubling/redoubling and the structured contract outcome.
- `BettingRound` (see [games/seven-card-stud.md](games/seven-card-stud.md))
  — parameterized over active players, opening bet, limit increment, max
  raises, and outcome. Owns its own per-betting-round state
  (`bet_to_match`, `last_aggressor`, `has_acted`, `raises_so_far`, `bet_by`).
  Action-legality is expressed as `active_rules:` on the mechanic
  (`CheckLegalIfNothingToCall`, `CallLegalIfBetToMatch`,
  `BetLegalIfNoBetToMatch`, `RaiseLegalIfBetExistsAndRaiseCapNotHit`),
  reading per-round state via lexical scoping. Used by Stud across
  multiple streets; applicable to any limit-betting game.
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
more scoring-heavy games (Bridge variants, Skat, Pinochle's full meld
scoring).

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

## Memory operations

Stdlib operations that affect player knowledge. Full design in
[decisions.md](decisions.md) "Knowledge, visibility, and the projection
model".

- `peek(target, observer)` — private look (target is a card or zone)
- `reveal(target, observers = all)` — show to observers (default: all)
- `hide(target, hidden_from = all_except_owner)` — future visibility downgrade; prior knowledge persists under perfect recall
- `shuffle(zone)` — destroys per-card identity knowledge; preserves count-by-type. No-op on pure-resource zones.
- `announce(fact, observers = all)` — purely epistemic event; updates observers' candidate sets
- `expose_top(zone)` — shorthand for `reveal(zone.top, all)`
- `deal(from, to, visibility)` — card moves with per-recipient visibility; emits semi-private observation to non-recipients (they see something moved)
- `transfer(amount, from, to, visibility?)` — resource units move; analogous to `deal` for fungible quantities. Syntax: `transfer { wood: 2 } from bank to hand[player]` or `transfer 5 chips from stack[A] to pot`.
- `muck(target)` — card leaves play to a trivial-projection zone; prior observations persist
- `forget(observer, target)` — **breaks perfect recall**; compiler warns; CFR/IS-MCTS guarantees no longer apply

Card games use `peek` / `reveal` / `shuffle` / `deal` predominantly.
Stud Poker (see [games/seven-card-stud.md](games/seven-card-stud.md))
is the first game to exercise the full vocabulary in non-trivial ways.
Resource-using games (Catan and similar, when they enter scope) use
`transfer` as the primary movement op.

## Stdlib functions

Standard helpers available across games.

- `best_five_card_hand(cards: Set<Card>) → HandRank` — given a set of
  cards (typically 7 for Stud, 5 for draw poker, 2+5 community for
  Hold'em), returns the best 5-card poker hand as a `HandRank`
  value. Stdlib because every poker variant needs it; the
  implementation is standard and not game-specific.
- `next_active_player(p) → Player` — returns the next player
  clockwise from `p` who is not folded and not all-in. Stud uses
  this in `BettingRound`'s main loop; any betting game would use
  the same shape.
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
