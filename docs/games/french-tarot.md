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
   HIDDEN from the opponents (the discards still count to the taker); at
   Garde sans the chien counts to the taker unseen; at Garde contre it counts
   to the opponents.
4. **Play** — eighteen tricks; atouts are trumps. Follow suit; if void you must
   trump, and you must over-trump if you can. The Excuse may be played at any
   time, never wins, and stays with its team (transferring a low card to the
   trick winner in compensation).
5. **Score** — the threshold is 36/41/51/56 card points for 3/2/1/0 bouts.
   `pt = taker points − threshold`; with the petit-au-bout bonus `pb` (±10 if the
   1 of atouts falls in the last trick) and the bid multiplier `mu`
   (1/2/4/6), each opponent pays `(25 + pt + pb) × mu` and the taker collects
   three times that (zero-sum).

The whole hand runs in the DSL. The four-level bid runs on the kernel `round`
(a counterclockwise single-pass ring over the move vocabulary below, settling
on a taker via `tarot_auction_outcome`). The chien discard is a filtered
movement (`move chosen 6 cards from hand[p] where c => is_pref_discard(c) to
discard[p]`, preferring plain non-King cards and falling back to any non-bout)
into a genuinely hidden `discard[player]` zone — a deliberate departure from
the printed rules' physical table layout, where the discard sits face down in
front of the taker but is not itself secret information the opponents lack;
here it is modelled as hidden because the opponents cannot see which specific
cards were set aside, only that six were. The eighteen tricks run on the trick
form of `round`, legality narrowed by the `ExcuseIsExempt`/`MustFollowSuit`/
`MustTrumpIfVoid`/`MustOverTrump` rule cascade (the Excuse is exempt from
every obligation via the `exempts:` clause, and never wins the trick). The
Excuse's special routing — it stays with its own side, repaying the trick
winner a low card when one is available — is ordinary body movements after
the round. `tarot_per_opp` computes the settlement (bouts threshold, doubled
card points from `captured` + the hidden `discard`, petit-au-bout, bid
multiplier); the `for each player` scoring statement applies it 3:1 zero-sum.
Card points are kept in doubled integer units (the 78 cards sum to 182).
Real FFT forces the taker to discard atouts/the Excuse/a King face up when
fewer than six other cards remain to discard — out of scope here (a 24-card
taker hand+chien essentially never runs short of plain non-King cards).
poignée declaration and the Excuse half-point IOU deferral are also out of
scope.

```
game FrenchTarot {

  players: 4
  direction: counterclockwise        // canonical for French Tarot
  max_length: 15000

  cards: tarot78
  trump: atouts

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    chien            : FaceDownPile        // the six-card kitty
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
    discard[player]  : HiddenPile<player>  // the taker's discarded chien cards, hidden from opponents
  }

  state {
    score[player] : Integer = 0
    hands_played  : Integer = 0
  }

  phase hand_sequence repeats until hands_played >= 36 {
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
            until (number of players where not acted[player]) == 0
            outcome tarot_auction_outcome
    }
    auction produces:
      taken(t, lvl) { taker := t  bid_level := lvl  continue to play }
      thrown_in     { skip to next hand }

    phase play {
      active_rules: [ExcuseIsExempt, MustFollowSuit, MustTrumpIfVoid, MustOverTrump]
      legal_moves:  [play_to_trick]
      state {
        leader        : Player? = none
        petit_in_last : Boolean = false
      }

      // Chien, by contract level. At Petite/Garde the taker merges the chien and
      // discards six, HIDDEN from the opponents — bouts are never discardable,
      // and plain non-King cards are preferred whenever six exist. At Garde
      // sans / Garde contre the chien is NOT moved: it stays in its zone and
      // is counted at scoring — moving it would reorder the next hand's
      // pre-shuffle gather.
      if bid_level <= 2 {
        for each player p: if p == taker {
          move all cards from chien to hand[p]
          if (sum over hand[p] as c: if is_pref_discard(c) then 1 else 0) >= 6 {
            move chosen 6 cards from hand[p] where c => is_pref_discard(c) to discard[p]
          } else {
            move chosen 6 cards from hand[p] where c => not is_bout(c) to discard[p]
          }
        }
      }

      // Eighteen tricks, counterclockwise; the player to the dealer's right
      // leads the first. The Excuse is exempt from every obligation and never
      // wins (tarot_trick_winner).
      leader := dealer offset_by right
      repeat until (all player p: hand[p] is empty) {
        round play_to_trick from leader over all players source hand into trick_pile
              outcome tarot_trick_winner
        petit_in_last := (sum over trick_pile as c:
                            if c.suit == atouts and c.rank == "1" then 1 else 0) > 0
        let xp = tarot_excuse_player()
        if xp is not none and ((xp == taker) != (outcome == taker)) {
          // The Excuse stays with its own side; the winner takes the rest and is
          // repaid the first captured low card, when one is available.
          move all cards from trick_pile where c => c.suit == excuse to captured[xp]
          move all cards from trick_pile to captured[outcome]
          if (sum over captured[xp] as c: if tarot_card_points(c) == 1 then 1 else 0) > 0 {
            move one cards from captured[xp] where c => tarot_card_points(c) == 1
                 to captured[outcome]
          }
        } else {
          move all cards from trick_pile to captured[outcome]
        }
        leader := outcome
      }

      // Scoring: per-opponent amount (bouts threshold, petit-au-bout, bid
      // multiplier — half-point arithmetic in tarot_per_opp); 3:1 zero-sum.
      let pb = if petit_in_last then (if leader == taker then 10 else 0 - 10) else 0
      let v = tarot_per_opp(pb)
      for each player p: if p == taker { score[p] += 3 * v } else { score[p] -= v }
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
  c.suit == excuse or (c.suit == atouts and (c.rank == "1" or c.rank == "21"))

// Preferred discard: a plain-suit non-King (never a trump, the Excuse, or a
// bout). Bare rank names are not enum values in this language — the check
// compares against the string literal `Card.rank` holds.
function is_pref_discard(c : Card) =
  c.suit != atouts and c.suit != excuse and c.rank != "K"

// === Tarot strict-trick legality (rule DSL) ===
//
// The Excuse is exempt: never subject to an obligation, never satisfies one,
// and offered AFTER the constrained cards, in hand order (rules.legal_cards's
// exempt pre-pass). The three demand rules run the running-intersection
// cascade: follow the effective led suit (tarot_led_suit() — the first
// non-Excuse card; when the Excuse is led, the next player's card sets the
// suit); if void, trump; over-trump the pile's best atout when able.

rule ExcuseIsExempt {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  exempts: hand.where(c => c.rank == "Excuse")
}

rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(tarot_led_suit())
  if_impossible: hand   // void in the effective led suit
}

rule MustTrumpIfVoid {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(atouts)
  if_impossible: hand   // holds the led suit, or has no trump
}

rule MustOverTrump {
  constrains: play_to_trick
  applies_when: state.led_suit is not none and
                (sum over trick_pile as t: if t.suit == atouts then 1 else 0) > 0
  demands: hand.where(c => tarot_trump_height(c) >
             (max over trick_pile as t: tarot_trump_height(t)))
  if_impossible: hand   // cannot over-trump: any trump (or the prior set) stands
}
```
