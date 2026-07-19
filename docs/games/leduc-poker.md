# Leduc Poker

The companion formal file is [leduc-poker.cardlang](leduc-poker.cardlang);
this is the readable twin. Leduc is the standard step up from Kuhn for
**two players**: still tiny enough to solve exactly, but with a community
card, two betting rounds and a real raise, so the strategies it produces
are recognisably poker. Source: Southey et al., *Bayes' Bluff* (2005); this
corpus entry is configured to match OpenSpiel's native `leduc_poker` at two
players.

A hand:

1. **Ante.** Both players put 1 chip in the pot.
2. **Deal.** The six-card deck — Jack, Queen, King in two suits — is shuffled
   and one card is dealt face down to each player.
3. **First betting round**, opened by player 0, with a bet size of **2**:
   check, bet, call, raise or fold. At most **two aggressive actions** per
   round (a bet and one raise), after which the only replies are call and
   fold.
4. **The board.** If both players are still in, one card is turned **face
   up** — the community card, shared by both hands. A round that ended in a
   fold never reaches this: no board card is dealt at all.
5. **Second betting round**, opened by player 0, identical except that the
   bet size **doubles to 4** and the raise count starts over.
6. **Showdown.** A private card of the **same rank as the board** is a pair
   and beats any unpaired holding; otherwise the **higher private card**
   wins. Equal ranks split the pot. A fold gives the pot to the player still
   in, and the folded card is *never shown*.

Only one player can ever pair: the deck holds exactly two cards of each rank,
so if the board and one hand share a rank, both copies are spoken for.

The score is each player's **net chips** for the hand — OpenSpiel's own
`money_[player] - kStartingMoney`, so the two implementations' returns are
directly comparable. `net[player]` in the formal file is that quantity,
computed once at the end of the hand from the `stack` the betting moved.

Zones and visibility: `hand[player]` is a `Hand<player>` — identity to its
owner, a bare count to the opponent. `board` is a `Discard`, fully public, so
turning the community card is an observation event both players receive with
the card named. The showdown moves both hands into `shown[player]`, a
`PublicHand<player>`; a fold instead moves the folded hand to the `muck`, a
`Muck`, which projects as trivial to everyone including its owner. Chips are
ordinary public integer state, as in Kuhn and Seven-Card Stud.

**The information-set point.** A Leduc information set is the player's own
card, the board once it is turned, and the betting so far. Nothing in this
file says so: it falls out of `Hand<player>`'s and `Discard`'s declared
projections plus the events the betting moves and card movements emit. Two
negative properties are worth naming because they are easy to lose and are
asserted directly in `tests/openspiel_ready/test_leduc_poker.py`: a folded
card mucks without identity, and a **first-round fold turns no board card at
all** — dealing one anyway would shrink the set of hands the folder could
have held, leaking through the deck rather than through the fold.

**The family-library point.** Leduc is one of two anchors for the `uses`
import tier ([decisions.md](../decisions.md) "Family libraries"). Its
betting comes entirely from
[poker_betting](../libraries/poker_betting.cardlang) — `check`, `bet`,
`call`, `raise`, and the `can_act`/`owes`/`pending` ring predicates — shared
verbatim with Kuhn and Seven-Card Stud. Leduc is the member that exercises
the tier's **parameterization** claim: the family's constants ride on
required state the game declares, not on arguments to the import. `limit`
carries the bet size and is reassigned from 2 to 4 between the streets;
`raise_cap` is **2** where Stud's is **3**, and neither the library text nor
the `uses` line mentions the difference. `fold` is Leduc's own, as in every
poker game — folding touches cards, and where the folded card goes is a
property of the table, not of the betting.

```
game LeducPoker {

  uses poker_betting

  players: 2
  direction: clockwise
  max_length: 200

  cards: leduc6
  ranking: aces high

  zones {
    deck            : Deck                 // the three undealt cards
    hand[player]    : Hand<player>         // the private card
    board           : Discard              // the face-up community card
    shown[player]   : PublicHand<player>   // the showdown reveal
    muck            : Muck                 // a folded card, never seen
  }

  state {
    stack[player]     : Integer = 40
    net[player]       : Integer = 0        // terminal score: chips won or lost

    // The library's contract (poker_betting `requires`).
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    acted[player]     : Boolean = false
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    limit             : Integer = 2        // the first street's bet size
    raise_cap         : Integer = 2        // two aggressive actions per street

    first_actor       : Player = 0         // P0 opens both streets
  }

  phase deal {
    shuffle deck
    for each player p: deal 1 card from deck to hand[p]
    for each player p: stack[p] := stack[p] - 1
    for each player p: committed[p] := committed[p] + 1
  }

  phase first_street {
    round offering [check, bet, call, fold, raise] from first_actor
          over players where pending(player)
          order priority
          until (number of players where pending(player)) is 0
             or ((number of players where can_act(player)) <= 1
                 and (number of players where can_act(player) and owes(player)) is 0)
  }

  phase second_street {
    if (number of players where not folded[player]) > 1 {
      deal 1 card from deck to board
      bet_to_match := 0
      raises := 0
      limit := 4
      for each player p: bet_by[p] := 0
      for each player p: acted[p] := false
      round offering [check, bet, call, fold, raise] from first_actor
            over players where pending(player)
            order priority
            until (number of players where pending(player)) is 0
               or ((number of players where can_act(player)) <= 1
                   and (number of players where can_act(player) and owes(player)) is 0)
    }
  }

  phase showdown {
    let board_rank = sum of rank_value(card) over cards in board
    if (number of players where not folded[player]) > 1 {
      for each player p: move all cards from hand[p] to shown[p]
      let r0 = sum of rank_value(card) over cards in shown[0]
      let r1 = sum of rank_value(card) over cards in shown[1]
      let s0 = if r0 is board_rank then r0 + 10 else r0
      let s1 = if r1 is board_rank then r1 + 10 else r1
      if s0 > s1 {
        stack[0] := stack[0] + committed[0] + committed[1]
      } else {
        if s1 > s0 {
          stack[1] := stack[1] + committed[0] + committed[1]
        } else {
          for each player p: stack[p] := stack[p] + committed[p]
        }
      }
    } else {
      for each player p: if not folded[p] {
        stack[p] := stack[p] + committed[0] + committed[1]
      }
    }
    for each player p: net[p] := stack[p] - 40
  }

  winner: highest net
}

move_type fold {
  when: bet_to_match > bet_by[actor]
  effect {
    folded[actor] := true
    move all cards from hand[actor] to muck
  }
}
```
