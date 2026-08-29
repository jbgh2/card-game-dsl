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
filtered movements per trick, and the contract's order is the game's Trick
Order ([decisions.md](../decisions.md), "Trick Order"): its rows read the
declared contract off the public state, which is what puts the four jacks and
the trump suit in one follow class under Suit and Grand and leaves Null
trumpless on its own rank order. Follow legality (`follows_lead`) and the
winner (`highest_by_trick_order`) are then both the language's. Scoring writes
`score[declarer]` directly through `skat_matadors`, with the overbid rule's
smallest-covering-multiple written as rounded division (`working_bid divided
by base rounded up`) in the game text.

The contract's three variables (`is_grand`, `is_null`, `trump_suit`) are
declared at game level rather than in `phase play`, because a `trick_order`
block is a game clause and sees game state only; the phase clears them on
entry, so they still last exactly one hand.

```
game Skat {

  players: 3
  direction: clockwise
  max_length: 8000

  cards: skat32
  ranking: ace-ten
  card_points { A: 11  10: 10  K: 4  Q: 3  J: 2  9: 0  8: 0  7: 0 }

  // The two this game borrows from outside the DSL. `skat_next_bid` takes no
  // `reads` clause: the ladder is a table, pure over its argument, and resolve
  // refuses a clause on an entry that never receives one. `skat_matadors`
  // counts the run from the club Jack down the trump order over ONE hand plus
  // the widow, so `hand[p]` narrows to the hand the call names while `skat`
  // and the three contract variables are whole-value reads.
  primitives {
    skat_next_bid(value : Integer) : Integer
    skat_matadors(p : Player) : Integer
        reads is_null, is_grand, trump_suit, hand[p], skat
  }

  // The declared contract decides the order, so the rows read it off the
  // public state the declaration wrote (`is_null`, `is_grand`, `trump_suit`).
  // Suit and Grand: the four jacks are trumps, banded above everything, clubs
  // > spades > hearts > diamonds; a Suit game adds its whole trump suit below
  // them, in ONE class with them, which is what makes the jacks unfollowable
  // by their printed suit. Null: no trumps at all, and the natural order
  // A K Q J 10 9 8 7, where the jack sits between the queen and the ten
  // instead of above the ace. Non-trumps follow as their printed suit — the
  // omitted `follow_class:` row's default — so a Null hand is plain suits
  // throughout.
  trick_order {
    trump:         not is_null
                   and (card.rank is J or (not is_grand and card.suit is trump_suit))
    card_strength: if is_null then null_strength(card)
                   elif card.rank is J then 100 + suit_order(card.suit)
                   else rank_value(card)
  }

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
    // The declared contract. Game-level because the Trick Order rows read it
    // and a game clause sees game state only — not because it outlives a
    // hand: `phase play` clears all three on entry, where its own state block
    // would otherwise have re-declared them.
    is_grand      : Boolean = false
    is_null       : Boolean = false
    trump_suit    : Suit?   = none
  }

  phase hand_sequence repeat until hands_played >= 36 {
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
        declarer_tricks : Integer = 0
        leader          : Player? = none
      }

      // The contract's three variables are game-level (the Trick Order reads
      // them); clearing them here is what the phase's own state block did.
      is_grand := false
      is_null := false
      trump_suit := none

      // --- The Reizen: middlehand speaks against forehand, then rearhand
      // against the survivor. A speaker bids the next ladder value or passes;
      // the responder holds (yes) or passes. The exhausted ladder ends the
      // exchange with no draw, like a pass by the speaker.
      responder := dealer offset_by left           // forehand answers first
      speaker := responder offset_by left          // middlehand speaks
      round offering [bid, yes, pass] from speaker
            over players where player is speaker or player is responder
            until passer is not none or skat_next_bid(working_bid) is 0
      let w1 = if passer is none then responder
               else the player where (player is speaker or player is responder) and player is not passer
      speaker := speaker offset_by left            // rearhand speaks
      responder := w1
      passer := none
      round offering [bid, yes, pass] from speaker
            over players where player is speaker or player is responder
            until passer is not none or skat_next_bid(working_bid) is 0
      declarer := if passer is none then responder
                  else the player where (player is speaker or player is responder) and player is not passer

      // All passed: forehand may play at 18 or throw the hand in (it still
      // counts toward the 36).
      if working_bid is 0 {
        offer to declarer one of [play_at_eighteen, throw_in]
        if thrown { skip to next hand }
      }

      // --- Contract declaration: hand or pick up the skat (discarding two),
      // then the game type; a Suit game names its trump in a one-draw round.
      offer to declarer one of [pick_up_skat, declare_hand]
      offer to declarer one of [choose_suit_game, declare_grand, declare_null]
      if not is_grand and not is_null {
        round offering [declare_suit] from declarer
              over players where player is declarer
              until trump_suit is not none
      }
      // Matadors (with/without the top trumps) exist only under a trump
      // structure; the count reads hand + skat BEFORE play. A `let` local, NOT
      // a state variable: it derives from the declarer's hidden hand plus the
      // face-down skat, and state is public (rendered into every player's
      // information state) — storing it would leak the jack holdings to the
      // defenders mid-hand.
      let matadors = if is_null then 0 else skat_matadors(declarer)

      // --- Ten tricks: forehand leads; strict follow by class (trump = the
      // jacks + the trump suit; Null: plain suits). Each `as <seat>` block binds
      // the acting player for its chosen movement (decisions.md "Single-actor
      // decisions: the `as` block").
      leader := dealer offset_by left              // forehand leads trick 1
      repeat until (all players where hand[player] is empty) {
        let second = leader offset_by left
        let third  = second offset_by left
        as leader { move chosen one card from hand[leader] to trick_pile }
        as second { move chosen one card from hand[second] where follow_ok(second, card) to trick_pile }
        as third  { move chosen one card from hand[third] where follow_ok(third, card) to trick_pile }
        let w = highest_by_trick_order(trick_pile)
        if w is declarer { declarer_tricks += 1 }
        move all cards from trick_pile to captured[w]
        leader := w
      }

      // --- Scoring: the declarer alone wins or loses (opponents' scores
      // never move). Null is a fixed value; otherwise base x multiplier with
      // matadors, hand, Schneider, Schwarz — and the overbid rule on a loss.
      if is_null {
        let game_value = if hand_mode then 35 else 23
        if declarer_tricks is 0 and game_value >= working_bid { score[declarer] += game_value }
        else { score[declarer] -= 2 * (if game_value >= working_bid
                                       then game_value
                                       else game_value * (working_bid divided by game_value rounded up)) }
      } else {
        let pts = (sum of card_points(card) over cards in captured[declarer]) + (sum of card_points(card) over cards in skat)
        let base = if is_grand then 24
                   elif trump_suit is diamonds then 9
                   elif trump_suit is hearts then 10
                   elif trump_suit is spades then 11
                   else 12
        let schneider = if pts >= 90 or pts <= 30 then 1 else 0
        let schwarz = if declarer_tricks is 10 or declarer_tricks is 0 then 1 else 0
        let game_value = base * (matadors + 1 + (if hand_mode then 1 else 0) + schneider + schwarz)
        if pts >= 61 and game_value >= working_bid { score[declarer] += game_value }
        else { score[declarer] -= 2 * (if game_value >= working_bid
                                       then game_value
                                       else base * (working_bid divided by base rounded up)) }
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
  when: actor is speaker and skat_next_bid(working_bid) > 0
  effect { working_bid := skat_next_bid(working_bid) }
}

move_type yes {
  when: actor is responder
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

// === Functions ===

// Within the jacks: clubs > spades > hearts > diamonds.
function suit_order(s : Suit) =
  if s is clubs then 4 elif s is spades then 3 elif s is hearts then 2 else 1

// Null's natural order, A K Q J 10 9 8 7 — the ten drops below the jack,
// which the game's ace-ten `ranking:` (read by `rank_value`) does not do, so
// Null spells its own eight values rather than deriving them.
function null_strength(c : Card) =
  if c.rank is A then 8 elif c.rank is K then 7 elif c.rank is Q then 6
  elif c.rank is J then 5 elif c.rank is "10" then 4 elif c.rank is "9" then 3
  elif c.rank is "8" then 2 else 1

// Strict follow by class, straight off the Trick Order: `follows_lead` is the
// winner's own candidate test, so legality and winning read ONE definition of
// the led class — under Suit and Grand a trump obliges a trump, whatever suit
// it is printed. Void in the class, anything goes; the void case is the
// `if any ... else true` shape, because `follows_lead` on a pile with nothing
// led is the value false.
function follow_ok(p : Player, c : Card) =
  if any card in hand[p] where follows_lead(card, trick_pile)
  then follows_lead(c, trick_pile)
  else true
```
