# Schnapsen

The companion formal file is [schnapsen.cardlang](schnapsen.cardlang); this is
the readable twin. Schnapsen is a two-player Ace-Ten point-trick game on a
20-card deck (A 10 K Q J in four suits; card values A=11, 10=10, K=4, Q=3, J=2,
so the deck holds 120 points). Each hand is a race to **66 card points**; the
match is played to **7 game points scored downward** — the first player to reach
0 wins. Source: [Pagat](https://www.pagat.com/marriage/schnaps.html).

How a hand goes:

- Deal 3 cards each, turn one up to fix **trump**, deal 2 more each; the rest is
  the face-down **talon**, drawn from after every trick.
- **Phase 1 (talon open).** The leader may lead any card — there is no
  obligation to follow suit. After each trick the winner draws the top of the
  talon, then the loser draws (the last draw is the face-up trump card, which
  goes to the loser). When on lead a player may also:
  - **declare a marriage** — lead the K or Q of a suit while holding both, for
    20 points (40 in trump); the points are *pending* until the declarer wins a
    trick;
  - **exchange the trump jack** — swap the jack of trump in hand for the turned-up
    trump card;
  - **close the talon** — stop the draw and switch immediately to strict play.
- **Phase 2 (talon closed or exhausted).** Strict play: follow suit and play a
  higher card of the led suit if you can; if void, you must trump; otherwise play
  anything. (Schnapsen has no over-trump obligation.)
- A player who reaches 66 **claims** and ends the hand.

Settlement, in game points deducted from the claimer's (or opponent's) score:

- **Correct claim, talon not closed** — 1 point, 2 if the opponent has fewer than
  33 card points (Schneider), 3 if the opponent took no trick (Schwarz).
- **Correct claim after closing** — the same tiers, but measured against the
  opponent's standing *at the moment of the close* (the Viennese snapshot).
- **Failed close** (the closer never reached 66) — the opponent scores 2, or 3 if
  shut out at the close.
- **No close, no claim, cards run out** — the last trick is worth 1 point.

The hand runs fully on the kernel. The leader's mixed turn — lead a card,
declare a marriage, exchange the trump jack, or close the talon — is one flat
candidate list on the **auction form of `round`** over a single-participant
ring: the free actions (exchange/close) leave `until trick_pile is not empty`
false, so the ring re-offers the leader until a card is led. `play_card(c :
Card)` enumerates the leader's live hand in hand order — the
state-dependent Card domain ([decisions.md](../decisions.md) "Declared
parameter domains"). The follower answers with a filtered chosen movement
over the in-file `follow_ok` cascade (strict follow-and-head once the talon is
closed or exhausted), and the trick, claim-at-66, and paired talon draws are
plain statements around the game-local `schnapsen_trick_winner` Primitive
primitive. The hand resolves three ways and produces a typed outcome —
`claimed`, `talon_closed`, or `open_play` — which the `play` phase declares
and the `scoring` phase settles with a `produces:` block (see
[decisions.md](../decisions.md) "Typed phase outcomes").

```
game Schnapsen {

  players: 2
  direction: clockwise            // irrelevant with two players; kept for uniformity
  max_length: 1000

  cards: schnapsen20
  ranking: ace-ten

  zones {
    deck            : Deck
    talon           : FaceDownPile      // the face-down stock drawn after each trick
    trump_indicator : Discard           // the face-up trump card (the last draw)
    hand[player]    : Hand<player>
    trick_pile      : TrickPile
    captured[player]: PlayerPile<player>
  }

  state {
    // Match score: starts at 7, scored downward; first to 0 wins.
    game_score[player] : Integer = 7
  }

  phase hand_sequence repeat until (any player where game_score[player] <= 0) {
    state {
      dealer                 : Player  = 0
      leader                 : Player? = none
      trump_suit             : Suit?   = none
      card_points[player]    : Integer = 0
      tricks_won[player]     : Integer = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 3 cards from deck to each hand
      deal 1 card from deck to trump_indicator    // turn up the trump card
      trump_suit := suit_of(trump_indicator)
      deal 2 cards from deck to each hand
      move all cards from deck to talon            // the rest is the stock
      dealer := dealer offset_by left              // alternates each hand
      leader := the player where player is not dealer  // non-dealer leads
      for each player p: card_points[p] := 0
      for each player p: tricks_won[p] := 0
    }

    // The hand resolves three ways: a player claimed 66 (with the opponent's
    // effective card points and tricks), the closer failed to reach 66, or the
    // talon emptied and the last trick decides. The play phase produces one;
    // the scoring phase settles it.
    phase play -> outcome {
      claimed(Player, Integer, Integer)
        | talon_closed(Player, Integer)
        | open_play(Player)
    } {
      state {
        pending[player] : Integer = 0     // marriage points owed until the declarer wins a trick
        closed          : Boolean = false
        closed_by       : Player? = none
        closer_opp_cp   : Integer = 0     // opponent's card points at the close (Viennese snapshot)
        closer_opp_tr   : Integer = 0     // opponent's tricks at the close
        last_winner     : Player? = none
      }

      last_winner := leader

      repeat until (any player where hand[player] is empty) {
        // Strict follow applies from the trick AFTER the close/exhaustion.
        let endgame = closed or (talon is empty and trump_indicator is empty)

        // The leader takes free actions (exchange / close), then leads a card.
        round offering [play_card, declare_marriage, exchange_trump_jack, close_talon]
              from leader over players where player is leader
              until trick_pile is not empty

        // The follower answers; strict follow-and-head in the endgame. The
        // `as fol` block binds the single acting player for the chosen movement
        // (decisions.md "Single-actor decisions: the `as` block").
        let fol = the player where player is not leader
        if endgame {
          as fol {
            move chosen one card from hand[fol] where follow_ok(fol, card) to trick_pile
          }
        } else {
          as fol {
            move chosen one card from hand[fol] to trick_pile
          }
        }

        let w = schnapsen_trick_winner(leader, trump_suit)
        card_points[w] += sum of card_value(card) over cards in trick_pile
        tricks_won[w] += 1
        if pending[w] > 0 {
          card_points[w] += pending[w]
          pending[w] := 0
        }
        move all cards from trick_pile to captured[w]
        last_winner := w

        // Claim the instant a player reaches 66 (the trick winner checked first).
        let lo = the player where player is not w
        if card_points[w] >= 66 {
          produce claimed(w,
                          if closed_by is not none and closed_by is w then closer_opp_cp else card_points[lo],
                          if closed_by is not none and closed_by is w then closer_opp_tr else tricks_won[lo])
        }
        if card_points[lo] >= 66 {
          produce claimed(lo,
                          if closed_by is not none and closed_by is lo then closer_opp_cp else card_points[w],
                          if closed_by is not none and closed_by is lo then closer_opp_tr else tricks_won[w])
        }

        // The winner draws first, then the loser (talon first, then the indicator).
        if not closed and not (talon is empty and trump_indicator is empty) {
          if talon is not empty { move one card from talon to hand[w] }
          else { if trump_indicator is not empty { move one card from trump_indicator to hand[w] } }
          if talon is not empty { move one card from talon to hand[lo] }
          else { if trump_indicator is not empty { move one card from trump_indicator to hand[lo] } }
        }
        leader := w
      }

      if closed_by is not none {
        produce talon_closed(closed_by, closer_opp_tr)
      }
      produce open_play(last_winner)
    }

    phase scoring {
      // Settle the hand in game points, deducted from the loser-facing score.
      play produces:
        claimed(claimer, opp_card_points, opp_tricks) {
          let game_pts = if opp_tricks is 0 then 3 elif opp_card_points < 33 then 2 else 1
          game_score[claimer] -= game_pts
        }
        talon_closed(closer, closer_opp_tricks) {
          // Closer never reached 66: the opponent scores 2 (3 if shut out at the close).
          let opp = the player where player is not closer
          let game_pts = if closer_opp_tricks is 0 then 3 else 2
          game_score[opp] -= game_pts
        }
        open_play(last_trick_winner) {
          // Nobody closed or claimed; the last trick is worth 1.
          game_score[last_trick_winner] -= 1
        }
    }
  }

  winner: lowest game_score
}

// === Lead move vocabulary ===
//
// The leader's single mixed decision per turn: one flat candidate list — every
// hand card as a lead (hand order), the marriage suits (deck-suit order), then
// the free actions. A marriage leads its queen, so both leading moves flip the
// round's until-predicate; exchange/close leave it false and the ring re-offers
// the leader.

move_type play_card(c : Card) {
  effect { move one card from hand[actor] where card is c to trick_pile }
}

move_type declare_marriage(s : Suit) {
  when: has_marriage(actor, s)
  effect {
    // 40 for the royal (trump) marriage, 20 otherwise — banked until the
    // declarer has won a trick.
    if tricks_won[actor] > 0 { card_points[actor] += if s is trump_suit then 40 else 20 }
    else { pending[actor] += if s is trump_suit then 40 else 20 }
    move one card from hand[actor] where card.rank is Q and card.suit is s to trick_pile
  }
}

move_type exchange_trump_jack {
  when: not closed
        and not (talon is empty and trump_indicator is empty)
        and trump_indicator is not empty
        and (any card in hand[actor] where card.rank is J and card.suit is trump_suit)
  effect {
    move one card from trump_indicator to hand[actor]
    move one card from hand[actor] where card.rank is J and card.suit is trump_suit to trump_indicator
  }
}

move_type close_talon {
  when: not closed
        and not (talon is empty and trump_indicator is empty)
        and talon is not empty
  effect {
    closed := true
    closed_by := actor
    let opp = the player where player is not actor
    closer_opp_cp := card_points[opp]
    closer_opp_tr := tricks_won[opp]
  }
}

// Does p hold both the K and the Q of s? (Pinochle's marriage predicate; rank
// names compare as the literal strings a `Card.rank` holds.)
function has_marriage(p : Player, s : Suit) =
  (any card in hand[p] where card.suit is s and card.rank is K) and
  (any card in hand[p] where card.suit is s and card.rank is Q)

// The led card, read from the single-card trick pile at follow time.
function led_suit_now() = suit_of(trick_pile)
function led_rank_now() = sum of rank_value(card) over cards in trick_pile

function holds_suit(p : Player, s : Suit) =
  any card in hand[p] where card.suit is s

// Endgame legality (strict follow): follow suit and head if you can; else
// follow; else trump; else anything. Schnapsen has no over-trump obligation.
function follow_ok(p : Player, c : Card) =
  if holds_suit(p, led_suit_now())
  then (if (any card in hand[p] where card.suit is led_suit_now() and rank_value(card) > led_rank_now())
        then c.suit is led_suit_now() and rank_value(c) > led_rank_now()
        else c.suit is led_suit_now())
  elif holds_suit(p, trump_suit) then c.suit is trump_suit
  else true
```
