# Pinochle

The companion formal file is [pinochle.cardlang](pinochle.cardlang); this is the
readable twin. Partnership Bid Pinochle, single 48-card pack (two copies each of
A 10 K Q J 9 per suit; 10 ranks between K and A), four players in fixed
partnerships sitting across. First team to **150** wins.

Each hand:

1. Deal 12 cards each.
2. **Auction** — an ascending bid opening at 50 and rising in 10s; players pass
   out, the last bidder takes the contract.
3. **Declare trump** — the high bidder names a suit he holds a *marriage* (K-Q)
   in. With no marriage anywhere he abandons the bid and his side is set back by
   the bid amount.
4. **Meld** — both sides score their meld combinations (runs, marriages, dix,
   pinochle, and the four-around sets — the standard single-pack values, with
   doubles scoring the published double values).
5. **Play** — twelve strict tricks: follow suit and head the led suit if you
   can; if void, trump and over-trump if you can. A/10/K captured score 10 each,
   and the last trick is worth 10 (250 trick points in all).
6. **Score** — the bidding side adds meld + tricks if it reached its bid, else is
   set back by the bid; the other side always adds its meld + tricks.

The whole hand runs in the DSL. The ascending auction runs on the kernel
`round` (a shrinking participants ring over the `submit_bid`/`pass` vocabulary
below, settling on a declarer and his bid). Trump declaration is a second,
one-draw `round offering [declare_trump_suit]`, guarded by a `has_marriage`
function checked over each of the four suits (no marriage anywhere abandons
the bid with no decision offered at all). Meld is a forced
`pinochle_meld_value(p)` stdlib query per player, credited to his team. The
twelve strict tricks run on the trick form of `round`, legality narrowed by
the MustFollowSuit/MustHeadTrick/MustTrumpIfVoid/MustOverTrump rule cascade
below (follow suit and head the trick if able; else trump and over-trump if
able; else anything). The meld evaluator (`pinochle_meld_value`) is a pure
stdlib primitive (`cardlang/runtime/pinochle.py`) — not yet the shared
combination model.

```
game Pinochle {

  players: 4
  partnerships: [[0, 2], [1, 3]]   // partners sit across the four-hand ring
  direction: clockwise
  max_length: 1000

  cards: pinochle48
  ranking: ace-ten            // 10 sits between K and A

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
  }

  state {
    // Game-level: persist across hands.
    score[team] : Integer = 0
  }

  phase hand_sequence repeat until (any team where score[team] >= 150) {
    state {
      dealer            : Player  = 0
      trump_suit        : Suit?   = none
      current_bid       : Integer = 0
      high_bidder       : Player? = none
      bid_abandoned     : Boolean = false
      meld_score[team]  : Integer = 0
      trick_score[team] : Integer = 0
      leader            : Player? = none
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 12 cards from deck to each hand
      dealer := dealer offset_by left
      for each team t: meld_score[t] := 0
      for each team t: trick_score[t] := 0
      bid_abandoned := false
      trump_suit := none
    }

    phase auction -> outcome { bid_won(Player, Integer) } {
      state {
        passed[player] : Boolean = false
        bids           : Integer = 0
        lead_bidder    : Player? = none
        working_bid    : Integer = 0
        opener         : Player? = none
      }
      opener := dealer offset_by left
      round offering [submit_bid, pass] from opener
            over players where not passed[player]
                              and (lead_bidder is none or player is not lead_bidder)
            until (number of players where not passed[player]) <= 1 or bids >= 16
            outcome pinochle_auction_outcome
    }
    auction produces:
      bid_won(d, c) { high_bidder := d  current_bid := c  continue to play }

    phase play {
      active_rules: [MustFollowSuit, MustHeadTrick, MustTrumpIfVoid, MustOverTrump]
      legal_moves:  [declare_trump_suit, play_to_trick]

      // The high bidder names trump — a suit he holds a marriage (K-Q) in. With
      // no marriage anywhere he abandons the bid (no decision is offered) and
      // the hand goes straight to scoring, where his side is set back.
      if any suit where has_marriage(high_bidder, suit) {
        round offering [declare_trump_suit] from high_bidder
              over players where player is high_bidder
              until trump_suit is not none

        // Meld is forced (a rational player melds everything) — a pure
        // computation per player, credited to his team.
        for each player p: meld_score[team_of(p)] += pinochle_meld_value(p)

        // Twelve strict tricks: high bidder leads; A/10/K score 10 each and
        // the last trick 10 (card_value reads the pinochle48 deck table).
        leader := high_bidder
        repeat until (all players where hand[player] is empty) {
          round play_to_trick from leader over all players source hand into trick_pile
                winner highest_trump_or_led_suit trump trump_suit
          trick_score[team_of(winner)] += sum of card_value(card) over cards in trick_pile
          move all cards from trick_pile to captured[team_of(winner)]
          leader := winner
        }
        trick_score[team_of(leader)] += 10   // ten for the last trick
      } else {
        bid_abandoned := true
      }
    }

    phase scoring {
      if bid_abandoned {
        score[team_of(high_bidder)] -= current_bid
      } else {
        for each team t:
          if t is team_of(high_bidder) {
            if team_score_in_hand(t) >= current_bid {
              score[t] += team_score_in_hand(t)
            } else {
              score[t] -= current_bid
            }
          } else {
            score[t] += team_score_in_hand(t)
          }
      }
    }
  }

  winner: highest score
}

// The bid value is derived, not chosen: 50 to open, then a fixed 10 higher.
move_type submit_bid {
  effect {
    working_bid := if working_bid is 0 then 50 else working_bid + 10
    lead_bidder := actor
    bids        := bids + 1
  }
}
move_type pass { effect { passed[actor] := true } }

// A team's total for the hand: meld plus tricks. Named so the bidder's
// make-the-bid test and every team's payout add the same total from one place.
function team_score_in_hand(t : Team) = meld_score[t] + trick_score[t]

// Trump declaration: the guard enumerates `Suit` in deck order and keeps the
// marriage suits, so the candidate list is the auction's marriage-suit set
// exactly (same length, same order as `has_marriage` below is checked).
move_type declare_trump_suit(s : Suit) {
  when: has_marriage(actor, s)
  effect { trump_suit := s }
}

// Does p hold both the K and the Q of s? (Bare rank names are not enum values
// in this language — `10`/`9` lex as integers, and there is no bare-name path
// for `K`/`Q` either — so the rank check compares against the literal string
// a `Card.rank` actually holds.)
function has_marriage(p : Player, s : Suit) =
  (any card in hand[p] where card.suit is s and card.rank is K) and
  (any card in hand[p] where card.suit is s and card.rank is Q)

// === Pinochle strict-trick legality (rule DSL) ===
//
// The cascade reproduces the classic obligation: follow suit and head the
// trick if able; if void, trump and over-trump if able; else anything. Each
// rule's `if_impossible: hand` intersects the running set with the whole
// hand — i.e. "keep the prior narrowing" — so an inapplicable obligation
// falls through (rules.legal_cards).

// MustFollowSuit is a standard-library rule (library.md "Rules"): activated
// by name above, defined once in cardlang/stdlib/rules.cardlang.

rule MustHeadTrick {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: cards in hand where card.suit is state.led_suit and
             rank_value(card) > (highest rank_value(card) over cards in trick_pile
               where card.suit is state.led_suit or -1)
  if_impossible: hand   // cannot head (or is void): the prior narrowing stands
}

rule MustTrumpIfVoid {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: cards in hand where card.suit is trump_suit
  if_impossible: hand   // holds the led suit, or has no trump
}

rule MustOverTrump {
  constrains: play_to_trick
  applies_when: state.led_suit is not none and
                (any card in trick_pile where card.suit is trump_suit)
  demands: cards in hand where card.suit is trump_suit and
             rank_value(card) > (highest rank_value(card) over cards in trick_pile
               where card.suit is trump_suit or -1)
  if_impossible: hand   // cannot over-trump: any trump (or the prior set) stands
}
```
