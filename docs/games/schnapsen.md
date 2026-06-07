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

The hand engine — the lead-action choice, marriages, the talon draw, the strict
endgame, and the claim — runs in the built-in `SchnapsenHand` mechanic, which
writes its results into the per-hand state vars the `scoring` phase below reads.
The DSL surface does not yet express heterogeneous lead-action choice or
rank-comparison legality rules; that generic surface is deferred (corpus-first)
until the auction games show its shape. The rules are implemented faithfully —
only the *expressiveness* is flagged.

```
game Schnapsen {

  players: 2
  direction: clockwise            // irrelevant with two players; kept for uniformity

  cards: schnapsen20
  ranking: A 10 K Q J

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

  phase hand_sequence repeats until (any player p: game_score[p] <= 0) {
    state {
      dealer                 : Player  = 0
      leader                 : Player? = none
      trump_suit             : Suit?   = none
      card_points[player]    : Integer = 0
      tricks_won[player]     : Integer = 0
      talon_closed_by        : Player? = none
      claimer                : Player? = none
      closer_opp_card_points : Integer = 0
      closer_opp_tricks      : Integer = 0
      last_trick_winner      : Player? = none
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 3 cards from deck to each hand
      deal 1 cards from deck to trump_indicator   // turn up the trump card
      trump_suit := suit_of(trump_indicator)
      deal 2 cards from deck to each hand
      move all cards from deck to talon            // the rest is the stock
      dealer := dealer offset_by left              // alternates each hand
      leader := the player where player != dealer  // non-dealer leads
      for each player p: card_points[p] := 0
      for each player p: tricks_won[p] := 0
      talon_closed_by := none
      claimer := none
      closer_opp_card_points := 0
      closer_opp_tricks := 0
    }

    phase play {
      legal_moves: [play_to_trick, declare_marriage, exchange_trump_jack, close_talon, claim_66]
      instantiate SchnapsenHand(leader = leader, trump = trump_suit)
    }

    phase scoring {
      if claimer is not none {
        let opp = the player where player != claimer
        let opp_cp = if talon_closed_by == claimer then closer_opp_card_points else card_points[opp]
        let opp_tr = if talon_closed_by == claimer then closer_opp_tricks else tricks_won[opp]
        let game_pts = if opp_tr == 0 then 3 elif opp_cp < 33 then 2 else 1
        game_score[claimer] -= game_pts
      } else {
        if talon_closed_by is not none {
          let opp = the player where player != talon_closed_by
          let game_pts = if closer_opp_tricks == 0 then 3 else 2
          game_score[opp] -= game_pts
        } else {
          game_score[last_trick_winner] -= 1
        }
      }
    }
  }

  winner: lowest game_score
}
```
