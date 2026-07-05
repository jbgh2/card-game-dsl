# Skat

The companion formal file is [skat.cardlang](skat.cardlang); this is the
readable twin. Three-player Skat (DSkV / International rules, post-1999), 32-card
deck. Players bid (*Reizen*) for the right to play alone against the other two;
the declarer chooses a game type, takes or skips the two-card skat, and tries to
make the contract for a calculated game value. Thirty-six hands are played and
the highest score wins. Source: [Pagat](https://www.pagat.com/schafkopf/skat.html).

Each hand:

1. Deal 3 - 2(skat) - 4 - 3.
2. **Reizen** — middlehand bids against forehand, then rearhand against the
   survivor; bids climb the fixed legal sequence (18, 20, 22, 23, 24, 27, …).
   The last bidder is declarer; if all pass, forehand may play at 18 or throw the
   hand in.
3. **Declare** — the declarer either picks up the skat (and discards two) or
   plays *hand*, then names the contract: a trump suit, **Grand** (only the jacks
   are trumps), or **Null** (no trumps).
4. **Play** — ten tricks. In Suit and Grand the four jacks are permanent trumps
   (C > S > H > D), above the trump-suit cards in a Suit game; non-trump cards
   rank A > 10 > K > Q > 9 > 8 > 7. Null has no trumps and ranks
   A > K > Q > J > 10 > 9 > 8 > 7; the declarer must take *no* trick.
5. **Score** — only the declarer's score moves. A Suit/Grand contract needs 61+
   card points; its value is `base × multiplier`, the multiplier being matadors
   plus one for game, plus one each for hand, Schneider (a side under 31), and
   Schwarz (a side with no trick). Making it scores the value; failing loses
   twice it — or, when overbid, twice the smallest multiple of the base that
   meets the bid. Null is a fixed value (23, or 35 played from the hand).

The hand runs fully on the kernel. The Reizen is two sequential auction
`round`s over role-guarded two-participant rings — `bid` guarded to the
speaker, `yes` to the responder, `pass` open, so the candidate lists alternate
[bid, pass] / [yes, pass]; a pass (or the exhausted 62-value ladder) flips the
`until` predicate, and the survivor threads into the second contest
([decisions.md](../decisions.md), "The auction form of `round`", the
call-and-response bullet). The contract declaration is a pair of `offer`s
(play-at-18/throw-in on an all-pass; hand vs picking up the skat, with the
two-card discard in the `pick_up_skat` effect; the three-way game type) plus a
one-draw `declare_suit(s : Suit)` round. The ten tricks are three single-actor
filtered movements per trick over the `skat_follow_ok` follow-class predicate
(the four jacks and the trump suit are one class; Null has no trumps and its
own rank order), with the winner from the game-local `skat_trick_winner`
primitive; scoring writes `score[declarer]` directly through `skat_matadors`
and the overbid-aware `skat_effective_loss`.

```
game Skat {

  players: 3
  direction: clockwise

  cards: skat32
  ranking: A 10 K Q J 9 8 7

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    skat             : FaceDownPile        // the two-card widow
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }

  state {
    // Game-level: persists across hands.
    score[player] : Integer = 0
    hands_played  : Integer = 0
  }

  phase hand_sequence repeats until hands_played >= 36 {
    state {
      dealer : Player = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      // 3 - 2(skat) - 4 - 3 deal.
      deal 3 cards from deck to each hand
      deal 2 cards from deck to skat
      deal 4 cards from deck to each hand
      deal 3 cards from deck to each hand
      dealer := dealer offset_by left
    }

    phase play {
      state {
        speaker         : Player? = none
        responder       : Player? = none
        passer          : Player? = none
        working_bid     : Integer = 0
        declarer        : Player? = none
        thrown          : Boolean = false
        hand_mode       : Boolean = false
        is_grand        : Boolean = false
        is_null         : Boolean = false
        trump_suit      : Suit?   = none
        matadors        : Integer = 0
        declarer_tricks : Integer = 0
        leader          : Player? = none
      }

      // --- The Reizen: middlehand speaks against forehand, then rearhand
      // against the survivor. A speaker bids the next ladder value or passes;
      // the responder holds (yes) or passes. The exhausted ladder ends the
      // exchange with no draw, like a pass by the speaker.
      responder := dealer offset_by left           // forehand answers first
      speaker := responder offset_by left          // middlehand speaks
      round offering [bid, yes, pass] from speaker
            over players where player == speaker or player == responder
            until passer is not none or skat_next_bid(working_bid) == 0
      let w1 = if passer is none then responder
               else the player where (player == speaker or player == responder) and player != passer
      speaker := speaker offset_by left            // rearhand speaks
      responder := w1
      passer := none
      round offering [bid, yes, pass] from speaker
            over players where player == speaker or player == responder
            until passer is not none or skat_next_bid(working_bid) == 0
      declarer := if passer is none then responder
                  else the player where (player == speaker or player == responder) and player != passer

      // All passed: forehand may play at 18 or throw the hand in (it still
      // counts toward the 36).
      if working_bid == 0 {
        offer to declarer one of [play_at_eighteen, throw_in]
        if thrown { skip to next hand }
      }

      // --- Contract declaration: hand or pick up the skat (discarding two),
      // then the game type; a Suit game names its trump in a one-draw round.
      offer to declarer one of [pick_up_skat, declare_hand]
      offer to declarer one of [choose_suit_game, declare_grand, declare_null]
      if not is_grand and not is_null {
        round offering [declare_suit] from declarer
              over players where player == declarer
              until trump_suit is not none
      }
      // Matadors (with/without the top trumps) exist only under a trump
      // structure; the count reads hand + skat BEFORE play.
      if not is_null { matadors := skat_matadors(declarer) }

      // --- Ten tricks: forehand leads; strict follow by class (trump = the
      // jacks + the trump suit; Null: plain suits). The single-actor
      // `for each player p: if p == X` wrapper binds the acting player for
      // each chosen movement — the idiom open-questions/single-actor-binding.md
      // names as a candidate `as <player> { }` block.
      leader := dealer offset_by left              // forehand leads trick 1
      repeat until (all player p: hand[p] is empty) {
        let second = leader offset_by left
        let third  = second offset_by left
        for each player p: if p == leader { move chosen one card from hand[p] to trick_pile }
        for each player p: if p == second { move chosen one card from hand[p] where c => skat_follow_ok(p, c) to trick_pile }
        for each player p: if p == third  { move chosen one card from hand[p] where c => skat_follow_ok(p, c) to trick_pile }
        let w = skat_trick_winner(leader)
        if w == declarer { declarer_tricks += 1 }
        move all cards from trick_pile to captured[w]
        leader := w
      }

      // --- Scoring: the declarer alone wins or loses (opponents' scores
      // never move). Null is a fixed value; otherwise base x multiplier with
      // matadors, hand, Schneider, Schwarz — and the overbid rule on a loss.
      if is_null {
        let game_value = if hand_mode then 35 else 23
        if declarer_tricks == 0 and game_value >= working_bid { score[declarer] += game_value }
        else { score[declarer] -= 2 * skat_effective_loss(game_value, working_bid, game_value) }
      } else {
        let pts = (sum over captured[declarer] as c: card_value(c)) + (sum over skat as c: card_value(c))
        let base = if is_grand then 24
                   elif trump_suit == diamonds then 9
                   elif trump_suit == hearts then 10
                   elif trump_suit == spades then 11
                   else 12
        let schneider = if pts >= 90 or pts <= 30 then 1 else 0
        let schwarz = if declarer_tricks == 10 or declarer_tricks == 0 then 1 else 0
        let game_value = base * (matadors + 1 + (if hand_mode then 1 else 0) + schneider + schwarz)
        if pts >= 61 and game_value >= working_bid { score[declarer] += game_value }
        else { score[declarer] -= 2 * skat_effective_loss(game_value, working_bid, base) }
      }
    }

    after_each {
      hands_played += 1
    }
  }

  winner: highest score
}

// === The Reizen + declaration vocabulary ===
//
// Game-defined move_types (the Stud/Schnapsen shape). The two auction roles
// are guards over the same vocabulary: the speaker sees [bid, pass], the
// responder [yes, pass] — the reference's literal candidate lists.

move_type bid {
  when: actor == speaker and skat_next_bid(working_bid) > 0
  effect { working_bid := skat_next_bid(working_bid) }
}

move_type yes {
  when: actor == responder
  effect { }
}

move_type pass {
  effect { passer := actor }
}

move_type play_at_eighteen {
  effect { working_bid := 18 }
}

move_type throw_in {
  effect { thrown := true }
}

move_type pick_up_skat {
  effect {
    move all cards from skat to hand[actor]
    move chosen 2 cards from hand[actor] to skat
  }
}

move_type declare_hand {
  effect { hand_mode := true }
}

// Selecting "a Suit game" and naming which suit are two decisions in the
// reference (a three-way draw, then a four-way draw), so the game-type offer
// carries a selection-only move and the suit round follows.
move_type choose_suit_game {
  effect { }
}

move_type declare_grand {
  effect { is_grand := true }
}

move_type declare_null {
  effect { is_null := true }
}

move_type declare_suit(s : Suit) {
  effect { trump_suit := s }
}
```
