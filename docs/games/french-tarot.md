# French Tarot

The companion formal file is [french-tarot.cardlang](french-tarot.cardlang);
this is the readable twin. Four-player French Tarot (FFT rules) on the 78-card
Tarot deck — four 14-card suits (K Q Cavalier J 10…1), 21 atouts (trumps), and
the Excuse. One player (the *taker*) plays alone against the other three, trying
to take enough card points in tricks to beat a threshold set by how many *bouts*
(the 1 of atouts, the 21, and the Excuse) they capture. Thirty-six hands are
played; the highest score wins. Source:
[Pagat](https://www.pagat.com/tarot/frtarot.html).

Each hand:

1. Deal 18 cards to each player and 6 to the *chien* (kitty).
2. **Bid** — one ascending bid per player: Petite < Garde < Garde sans le chien
   < Garde contre le chien. The highest bidder is the taker; if all pass, the
   hand is thrown in.
3. **Chien** — at Petite/Garde the taker takes the chien and discards six,
   HIDDEN from the opponents (the discards still count to the taker). The
   discard may never contain a King or a bout; atouts go in only when the
   taker holds fewer than six plain non-King cards, and any atout discarded
   is shown to the whole table first. At Garde sans the chien counts to the taker
   unseen; at Garde contre it counts to the opponents.
4. **Play** — eighteen tricks; atouts are trumps. Follow suit; if void you must
   trump, and you must over-trump if you can. The Excuse may be played at any
   time, never wins, and stays with its team (transferring a low card to the
   trick winner in compensation). Leading it is legal and sets no suit: the
   next player may play any card, and that card fixes the suit to follow.
5. **Score** — the threshold is 36/41/51/56 card points for 3/2/1/0 bouts.
   `pt = taker points − threshold`; with the petit-au-bout bonus `pb` (±10 if the
   1 of atouts falls in the last trick) and the bid multiplier `mu`
   (1/2/4/6), each opponent pays `(25 + pt + pb) × mu` and the taker collects
   three times that (zero-sum).

The whole hand runs in the DSL. The four-level bid runs on the kernel `round`
(a counterclockwise single-pass ring over the move vocabulary below, settling
on a taker via `tarot_auction_outcome`). The chien discard is a filtered
movement (`move chosen 6 cards from hand[p] where is_pref_discard(card) to
discard[p]`) into a genuinely hidden `discard[player]` zone — a deliberate
departure from the printed rules' physical table layout, where the discard
sits face down in front of the taker but is not itself secret information the
opponents lack; here it is modelled as hidden because the opponents cannot see
which specific cards were set aside, only that six were. When fewer than six
plain non-Kings exist among the taker's 24, the forced branch moves every one
of them in and tops the discard up with chosen non-bout atouts routed through
`shown_atouts`, a public zone: each forced atout arrives there with identity
to all four seats before joining the hidden discard, so the opponents'
information sets carry exactly what the real game shows them — the forced
atouts — and nothing else of the discard. The atouts, the follow classes and
the card strengths are one declared `trick_order { }` block that the trick
winner, the follow demand and the over-trump comparison all read: the Excuse
belongs to no class, so it never wins and a led Excuse sets no suit — neither
restated by a rule, and the must-trump obligation reads the second off the
pile, binding only where the trick has an effective lead to be void in. The
eighteen tricks run on the trick form of `round`, legality narrowed by the
`ExcuseIsExempt`/`MustFollowEffectiveSuit`/`MustTrumpIfVoid`/`MustOverTrump`
rule cascade (the Excuse is exempt from every obligation via the `exempts:`
clause). The Excuse's special routing — it stays with its own side, repaying
the trick winner a low card when one is available — is ordinary body movements
after the round. `tarot_per_opp` computes the settlement (bouts threshold,
doubled card points from `captured` + the hidden `discard`, petit-au-bout, bid
multiplier); the `for each player` scoring statement applies it 3:1 zero-sum.
Card points are kept in doubled integer units (the 78 cards sum to 182); the
`card_points { }` clause carries the rank-keyed part of that table. poignée
declaration and the Excuse half-point IOU deferral are out of scope.

```
game FrenchTarot {

  players: 4
  direction: counterclockwise        // canonical for French Tarot
  max_length: 15000

  cards: tarot78
  // Doubled card points (printed half-points doubled: K=4.5, Q=3.5, C=2.5,
  // J=1.5, every other card half a point). The bouts (Excuse, petit, 21)
  // are worth 4.5 each and stay INLINE at the reads — a rank-keyed table
  // cannot carry the petit, whose rank "1" is 4.5 in atouts and half a
  // point in the plain suits: `if is_bout(card) then 9 else card_points(card)`.
  card_points { K: 9  Q: 7  C: 5  J: 3  else: 1 }

  // The trick order. The atouts are the trump class; the Excuse belongs to no
  // class at all, which is what makes "the Excuse never wins" fall out of the
  // kernel: a card that is neither a trump nor of the effective led class is
  // never a candidate. Strength carries its own arithmetic because no one
  // `ranking:` can serve a deck where rank "1" is the petit at the top of the
  // atouts and the lowest card of a plain suit.
  trick_order {
    trump:         card.suit is atouts
    follow_class:  if card.suit is excuse then none else card.suit
    card_strength: if card.suit is excuse then 0
                   elif is_trump(card) then 100 + numeral(card)
                   elif card.rank is K then 14
                   elif card.rank is Q then 13
                   elif card.rank is C then 12
                   elif card.rank is J then 11
                   else numeral(card)
  }

  // The two this game borrows from outside the DSL at a CALL position,
  // implemented in `cardlang/runtime/tarot.py`: who played the Excuse in the
  // trick just completed, and the hand's per-opponent settlement. The two
  // entries sit at opposite extremes, and that is the entry grain doing its
  // work: the Excuse query takes no `reads` clause — the completed trick's
  // plays reach it as an engine fact, and a clause names this game's own zones
  // and state variables alone — while the settlement reads the whole contract
  // and every pile that scores.
  //
  // `taker` and `bid_level` are declared by `phase hand_sequence`, not by the
  // game, so a read of one names that phase. The tail rides the READ, not the
  // clause: the three zones are game-level and carry none. Naming the phase
  // also promises what the resolver then checks — an entry reading
  // `in hand_sequence` is called only where that phase is running, which here
  // is its descendant `phase play`.
  //
  // The auction's own outcome query is not here and cannot be: an outcome is
  // named on a `round auction ... outcome` slot, a Primitive namespace the
  // block does not cover (issue #142), so `tarot_auction_outcome` keeps the
  // `PRIMITIVE_READS` row its dispatch binds.
  primitives {
    tarot_excuse_player() : Player?
    tarot_per_opp(pb : Integer) : Integer
        reads taker in hand_sequence, bid_level in hand_sequence,
              captured, discard, chien
  }

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    chien            : FaceDownPile        // the six-card kitty
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
    discard[player]  : HiddenPile<player>  // the taker's discarded chien cards, hidden from opponents
    shown_atouts     : Discard             // forced-discard atouts pause here, identity to every seat, then join discard[taker]
  }

  state {
    score[player] : Integer = 0
    hands_played  : Integer = 0
  }

  phase hand_sequence repeat until hands_played >= 36 {
    state {
      dealer    : Player  = 0
      taker     : Player? = none   // set by the auction's `taken` arm
      bid_level : Integer = 0      // 1..4 = petite..garde_contre
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 18 cards from deck to each hand
      deal 6 cards from deck to chien
      dealer := dealer offset_by right        // counter-clockwise rotation
    }

    phase auction -> outcome { taken(Player, Integer) | thrown_in } {
      state {
        acted[player] : Boolean = false
        current_level : Integer = 0    // 0 = no bid; 1..4 = petite..garde_contre
        lead_taker    : Player? = none
        opener        : Player? = none
      }
      opener := dealer offset_by right
      round offering [pass, bid_petite, bid_garde, bid_garde_sans, bid_garde_contre]
            from opener
            over players where not acted[player]
            until (number of players where not acted[player]) is 0
            outcome tarot_auction_outcome
    }
    auction produces:
      taken(t, lvl) { taker := t  bid_level := lvl  continue to play }
      thrown_in     { skip to next hand }

    phase play {
      active_rules: [ExcuseIsExempt, MustFollowEffectiveSuit, MustTrumpIfVoid, MustOverTrump]
      legal_moves:  [play_to_trick]
      state {
        leader        : Player? = none
        petit_in_last : Boolean = false
      }

      // Chien, by contract level. At Petite/Garde the taker merges the chien
      // and discards six, HIDDEN from the opponents — Kings and bouts are
      // never discardable, so the discard is six chosen plain non-Kings
      // whenever six exist; when fewer do, every plain non-King goes in and
      // chosen non-bout atouts top the discard up to six, SHOWN to the table
      // through the public `shown_atouts` on their way in. At Garde
      // sans / Garde contre the chien is NOT moved: it stays in its zone and
      // is counted at scoring — moving it would reorder the next hand's
      // pre-shuffle gather.
      if bid_level <= 2 {
        as taker {
          move all cards from chien to hand[taker]
          if (number of cards in hand[taker] where is_pref_discard(card)) >= 6 {
            move chosen 6 cards from hand[taker] where is_pref_discard(card) to discard[taker]
          } else {
            move all cards from hand[taker] where is_pref_discard(card) to discard[taker]
            let atouts_owed = 6 - (number of cards in discard[taker])
            move chosen atouts_owed cards from hand[taker]
                 where card.suit is atouts and not is_bout(card)
                 to shown_atouts
            move all cards from shown_atouts to discard[taker]
          }
        }
      }

      // Eighteen tricks, counterclockwise; the player to the dealer's right
      // leads the first. The Excuse is exempt from every obligation and never
      // wins -- the trick order gives it no class, so it is never a candidate.
      leader := dealer offset_by right
      repeat until (all players where hand[player] is empty) {
        round play_to_trick from leader over all players source hand into trick_pile
              winner highest_by_trick_order
        petit_in_last := any card in trick_pile
                           where card.suit is atouts and card.rank is "1"
        let xp = tarot_excuse_player()
        if xp is not none and ((xp is taker) is not (winner is taker)) {
          // The Excuse stays with its own side; the winner takes the rest and is
          // repaid the first captured low card, when one is available.
          move all cards from trick_pile where card.suit is excuse to captured[xp]
          move all cards from trick_pile to captured[winner]
          if any card in captured[xp] where (if is_bout(card) then 9 else card_points(card)) is 1 {
            move one card from captured[xp] where (if is_bout(card) then 9 else card_points(card)) is 1
                 to captured[winner]
          }
        } else {
          move all cards from trick_pile to captured[winner]
        }
        leader := winner
      }

      // Scoring: per-opponent amount (bouts threshold, petit-au-bout, bid
      // multiplier — half-point arithmetic in tarot_per_opp); 3:1 zero-sum.
      let pb = if petit_in_last then (if leader is taker then 10 else -10) else 0
      let v = tarot_per_opp(pb)
      for each player p: if p is taker { score[p] += 3 * v } else { score[p] -= v }
    }

    after_each {
      hands_played += 1
    }
  }

  winner: highest score
}

// One pass counterclockwise: pass, or raise to a level above the standing bid.
move_type pass             { effect { acted[actor] := true } }
move_type bid_petite       { when: current_level < 1
                             effect { current_level := 1  lead_taker := actor  acted[actor] := true } }
move_type bid_garde        { when: current_level < 2
                             effect { current_level := 2  lead_taker := actor  acted[actor] := true } }
move_type bid_garde_sans   { when: current_level < 3
                             effect { current_level := 3  lead_taker := actor  acted[actor] := true } }
move_type bid_garde_contre { when: current_level < 4
                             effect { current_level := 4  lead_taker := actor  acted[actor] := true } }

// A bout (oudler): the Excuse, the 1 of atouts (petit), or the 21.
function is_bout(c : Card) =
  c.suit is excuse or (c.suit is atouts and (c.rank is "1" or c.rank is "21"))

// Preferred discard: a plain-suit non-King (never a trump, the Excuse, or a
// bout). Name-form ranks are bare enum values (K); only the numeric ranks
// ("1", "21") spell as strings, since a bare number is an Integer.
function is_pref_discard(c : Card) =
  c.suit is not atouts and c.suit is not excuse and c.rank is not K

// The number a rank spells, and 0 for a rank that spells a letter -- the
// arithmetic the `card_strength:` row carries. Covers 1-21, so one function
// serves both the plain suits' pip cards and the whole atout band.
function numeral(c : Card) =
  if c.rank is "1" then 1 elif c.rank is "2" then 2 elif c.rank is "3" then 3
  elif c.rank is "4" then 4 elif c.rank is "5" then 5 elif c.rank is "6" then 6
  elif c.rank is "7" then 7 elif c.rank is "8" then 8 elif c.rank is "9" then 9
  elif c.rank is "10" then 10 elif c.rank is "11" then 11
  elif c.rank is "12" then 12 elif c.rank is "13" then 13
  elif c.rank is "14" then 14 elif c.rank is "15" then 15
  elif c.rank is "16" then 16 elif c.rank is "17" then 17
  elif c.rank is "18" then 18 elif c.rank is "19" then 19
  elif c.rank is "20" then 20 elif c.rank is "21" then 21
  else 0

// === Tarot strict-trick legality (rule DSL) ===
//
// The Excuse is exempt: never subject to an obligation, never satisfies one,
// and offered AFTER the constrained cards, in hand order (rules.legal_cards's
// exempt pre-pass). The three demand rules run the running-intersection
// cascade over the trick order: follow what the trick was effectively led
// (the first card with a follow class — the Excuse has none, so when it is
// led the next player's card sets the class); if void of THAT class, trump;
// over-trump the pile's best atout when able. Void is a fact of the effective
// lead, so a trick led with the Excuse has no class to be void in and binds
// nobody.

rule ExcuseIsExempt {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  exempts: cards in hand where card.rank is Excuse
}

// Not the library MustFollowSuit: that one demands the raw `state.led_suit`,
// the LITERAL first card's suit, which is "excuse" when the Excuse is led.
// This demands `follows_lead`, the trick order's own candidate test over the
// EFFECTIVE lead, so the rule is Tarot's own under its own name.
rule MustFollowEffectiveSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: cards in hand where follows_lead(card, trick_pile)
  if_impossible: hand   // void in the effective led suit
}

// Void is a fact of the EFFECTIVE lead, not of `state.led_suit`: a led Excuse
// makes the literal led suit "excuse" while setting no class at all, and a
// seat void in nothing owes no trump. The other two demand rules need no such
// guard — `MustFollowEffectiveSuit` falls to its `if_impossible` with nothing
// to follow, and `MustOverTrump` already asks for a trump in the pile.
rule MustTrumpIfVoid {
  constrains: play_to_trick
  applies_when: (any card in trick_pile where
                   (is_trump(card) or follow_class(card) is not none))
  demands: cards in hand where is_trump(card)
  if_impossible: hand   // holds the led suit, or has no trump
}

rule MustOverTrump {
  constrains: play_to_trick
  applies_when: state.led_suit is not none and
                (any card in trick_pile where is_trump(card))
  demands: cards in hand where card_strength(card) >
             (highest card_strength(card) over cards in trick_pile or 0)
  if_impossible: hand   // cannot over-trump: any trump (or the prior set) stands
}
```
