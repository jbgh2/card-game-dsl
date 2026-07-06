# Tichu

The companion formal file is [tichu.cardlang](tichu.cardlang); this is the
readable twin. A four-player partnership **climbing** game on a 56-card deck (the
standard 52 plus four special cards: Mahjong, Dog, Phoenix, Dragon). First
partnership to **1000** wins. Rules: Fata Morgana English edition.

Each hand:

1. Deal 14 cards each; every player **pushes** one card to each other player.
2. The Mahjong holder leads. Players **climb**: each play must be a combination
   of the led *type and length* and **beat** the previous play in rank, or be a
   **bomb** (four of a kind, which beats any non-bomb), or **pass**. Three passes
   end the trick and the last player to play wins it and leads next.
   Combinations: singles, pairs, triples, full houses, straights (≥5),
   consecutive pairs (≥2), and bombs.
3. The special cards: the **Mahjong** is rank 1 (lowest) and leads first; the
   **Dog** is led alone and hands the lead to your partner (no capture); the
   **Phoenix** is a wildcard / a single worth half a rank above the last play
   (and −25 points); the **Dragon** is the highest single, worth +25, and its
   trick is given to an opponent.
4. As players empty their hands they go out in order. If both partners of a team
   go out first and second — a **double victory** — the hand ends for 200 points
   with no card counting. Otherwise the last player's remaining hand goes to the
   opponents and their captured tricks to the first player out, and each team
   scores its captured card points (K and 10 = 10, 5 = 5, Dragon +25, Phoenix
   −25; 100 in all). Finally, **Tichu** (±100) and **Grand Tichu** (±200) calls
   pay out by whether the caller went out first.

The hand runs fully on the kernel. Each climbing trick is one `round climb`
over the game-local combination engine (`tichu_lead_options` /
`tichu_follows` — the enumeration itself is not DSL-expressible: a play moves
a specific computed card-set, where the movement vocabulary moves cards by
count). The Dog is a *trick-ending lead*: the engine marks the play
`ends_trick`, the climb form closes the trick with no follower draws, and the
body routes it off the round's terminal state (`state.lead_ended_trick` —
pile to the discard, lead to the partner). Finishing order likewise comes
from terminal round-state (`state.shed_first` / `state.shed_second`, the
first two players to play out their cards each trick, in play order). The
push is one chosen 3-card movement per player into a per-player `gift` pile
— simultaneous, since gifts land only after every pick — distributed
giver-major and draw-free (pick *i* to the *i*-th other seat), so each
receiver learns exactly what landed and from whom, and nobody else learns
anything but counts. The Tichu/Grand-Tichu call gates and the Dragon's
random opponent are the two rng primitives (`tichu_call_roll`,
`tichu_dragon_recipient`). Scope reductions
(random play): the Mahjong wish, the Phoenix as a wildcard inside
straights/consecutive-pairs, straight-flush bombs, and out-of-turn bombs are
omitted; Tichu/Grand Tichu are called at a low random rate.

```
game Tichu {

  players: 4
  partnerships: [[0, 2], [1, 3]]   // partners sit across
  direction: counterclockwise

  cards: tichu56

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    gift[player]   : Hand<player>     // the push: three picks, in pick order
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
    discard        : Discard          // the Dog goes here (no capture)
  }

  state {
    // Game-level: persists across hands.
    score[team] : Integer = 0
  }

  phase hand_sequence repeats until (any team t: score[t] >= 1000) {
    before_each {
      move all cards to deck
      shuffle deck
      deal 14 cards from deck to each hand
    }

    phase play {
      state {
        called[player] : Integer = 0   // 0 / 100 / 200; calls are announced (public)
        out_first  : Player? = none    // finishing order (public), first two only —
        out_second : Player? = none    //   all the scoring ever reads
        leader     : Player? = none
      }

      legal_moves: [play_combination]

      // Tichu / Grand Tichu calls (random-rate gates so card points drive the
      // game; the primitive consumes the reference's exact rng draws).
      for each player p: called[p] := tichu_call_roll()

      // The push: one draw of three from the live hand per player; gifts land
      // only after every pick (simultaneous). Distribution is draw-free and
      // giver-major: pick i goes to the i-th other player in seat order.
      for each player p: move chosen 3 cards from hand[p] to gift[p]
      for each player p: for each player q: if q != p { deal one card from gift[p] to hand[q] }

      // The Mahjong holder (post-push) leads the first trick.
      leader := tichu_mahjong_holder()

      // Climbing tricks until at most one player holds cards, or the first two
      // finishers are teammates (double victory ends the hand early). A Tichu
      // trick never ends early on a shed (`until false`) — the others must
      // still beat or pass; the DOG ends it via the engine's `ends_trick`.
      repeat until tichu_players_holding() <= 1 or tichu_double_victory() {
        round climb play_combination from leader
              over players where hand[player] is not empty
              source hand into trick_pile
              combinations tichu_lead_options follows tichu_follows
              until false
        if state.lead_ended_trick {
          // The Dog: no capture, the lead passes to the partner. The reference
          // records no shed on this path (its finishing order skips a player
          // who sheds by playing the Dog), so shed processing is skipped too.
          move all cards from trick_pile to discard
          leader := tichu_partner(outcome)
        } else {
          // Fold this trick's sheds (play order) into the finishing order.
          if state.shed_first is not none {
            if out_first is none { out_first := state.shed_first }
            else { if out_second is none { out_second := state.shed_first } }
          }
          if state.shed_second is not none {
            if out_first is none { out_first := state.shed_second }
            else { if out_second is none { out_second := state.shed_second } }
          }
          // The Dragon's trick is given to an opponent; otherwise the winner's
          // team captures the pile.
          if tichu_dragon_won() {
            move all cards from trick_pile to captured[team_of(tichu_dragon_recipient(outcome))]
          } else {
            move all cards from trick_pile to captured[team_of(outcome)]
          }
          leader := outcome
        }
        leader := tichu_next_holder(leader)
      }

      // --- Scoring: double victory is a flat +200 (no card points); otherwise
      // the lone remaining player's hand goes to the opponents and their
      // captured tricks to the first player out, then each team scores its
      // captured card points (100 in play every hand).
      if tichu_double_victory() {
        score[team_of(tichu_first_out())] += 200
      } else {
        if (any player p: hand[p] is not empty) {
          let last = the player where hand[player] is not empty
          move all cards from hand[last] to captured[tichu_opponent_team(last)]
          move all cards from captured[team_of(last)] to captured[team_of(tichu_first_out())]
        }
        for each team t: score[t] += (sum over captured[t] as c: tichu_card_points(c))
      }
      // Tichu / Grand Tichu settle against going out first.
      for each player p:
        if called[p] > 0 {
          if out_first is not none and p == out_first { score[team_of(p)] += called[p] }
          else { score[team_of(p)] -= called[p] }
        }
      let summary = tichu_hand_summary()   // the tichu_hand trace (invariant: 100 card points)
    }
  }

  winner: highest score
}
```
