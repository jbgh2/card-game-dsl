# Getaway (Bhabhi)

The companion formal file is [getaway.cardlang](getaway.cardlang); this is the
readable twin. Getaway (Bhabhi) is an elimination game: shed all your cards to
"get away", and the last player still holding cards is the loser. Players must
follow the led suit; a player who is void plays a **tochoo** (an off-suit card),
which ends the trick at once and forces whoever played the highest card of the
led suit to pick up the whole pile. When everyone follows, the highest card wins
and the played cards are discarded out of play.

```
game Getaway {

  players: 4
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck         : Deck
    hand[player] : Hand<player>
    trick_pile   : TrickPile
    waste        : Discard          // fully-followed tricks are discarded here
  }

  state {
    eliminated[player] : Boolean = false    // set once a hand is empty
    leader             : Player? = none      // each trick's winner; read by loser:
  }

  phase setup {
    shuffle deck
    deal all cards from deck as-equally-as-possible to each hand
  }

  phase first_trick {
    // Forced opening lead: the ace of spades. The first trick always goes to
    // the waste — the body routes it there unconditionally, not a rule.
    active_rules: [MustFollowSuit, MustLeadAceOfSpadesOnFirstPlay]
    legal_moves: [play_to_trick]

    leader := player_holding(A of spades)
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit early on_play_of_tochoo
    move all cards from trick_pile to waste
    leader := outcome
  }

  phase play {
    active_rules: [MustFollowSuit]
    legal_moves:  [play_to_trick]

    // Loop tricks until at most one player still holds cards.
    repeat until (number of players where hand[player] is not empty) <= 1 {
      round play_to_trick from leader over players where not eliminated[player]
            source hand into trick_pile outcome highest_of_led_suit early on_play_of_tochoo
      // On a tochoo the highest led-suit card picks up the pile; otherwise the
      // followed cards are discarded.
      if state.trick_terminated_early { move all cards from trick_pile to hand[outcome] }
      else { move all cards from trick_pile to waste }
      leader := outcome
      for each player p: if hand[p] is empty { eliminated[p] := true }
    }
  }

  // The sole survivor loses. If the last players all shed their final card on
  // one trick (no one holds cards), the winner of that trick — the last
  // `leader` — loses.
  loser: if (number of players where hand[player] is not empty) == 1
         then the player where hand[player] is not empty
         else leader
}

// === Getaway-specific rules ===

rule MustLeadAceOfSpadesOnFirstPlay {
  constrains: play_to_trick
  applies_when: state.led_suit is none       // i.e., leading
  demands: hand.where(c => c == A of spades)
  if_impossible: error("first lead must be the ace of spades")
}

// === Standard library rule ===

rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
}
```

## Formalization notes

Two variant mechanics that appeared in an earlier sketch of this game are
deliberately **not** formalized, because they are not part of standard Getaway
(Pagat) and each was underspecified:

- **Stealing (`steal_left`).** An "alone leader steals from the left" action
  was listed but its *effect* was never defined (no statement said what a steal
  does). The core elimination game is complete without it.
- **Drawing from the waste.** A rule let the trick winner draw a card back from
  the waste when their hand emptied. It contradicts the elimination invariant
  (a player who has shed all cards is out) and, by feeding hands from the
  discard pile, can prevent the game from ever terminating. The standard game
  has no such draw: cards only leave hands, so the game always ends.

Both can be revisited as explicit, fully-specified variants later.
