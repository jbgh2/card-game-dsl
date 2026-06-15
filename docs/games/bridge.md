# Bridge (rubber, simplified)

The companion formal file is [bridge.cardlang](bridge.cardlang); this is the
readable twin. Rubber Bridge with the standard below-the-line / above-the-line
scoring, game and rubber bonuses, slam bonuses, and vulnerability; honors and
the finer doubled-penalty table are simplified. One rubber is played (first side
to two games) and the side with the higher total wins.

Each hand:

1. Deal 13 cards each.
2. **Auction** — ascending bids over the strain order C D H S NT, with double and
   redouble; the auction ends when three passes follow a call. The final bid is
   the contract; declarer is the first of that side to have named the strain.
   (If all four pass, the hand is redealt.)
3. **Play** — the declarer's left-hand opponent leads; thirteen tricks, follow
   suit if able (Bridge has no head-or-trump obligation). The trump is the
   contract's strain, or none for a no-trump contract.
4. **Score** — the contract is *made* if declarer's side took 6 + level tricks.
   Made: the trick value goes below the line (20/trick in a minor, 30 in a major,
   30 + 10 in no-trump), times the doubling multiplier; overtricks and slam
   bonuses go above the line. Set: the defenders score the undertrick penalty
   above the line. When a side's below-the-line total crosses 100 it wins a game
   (bonus 300, or 500 when vulnerable), the below-the-line counters reset, and a
   second game ends the rubber (bonus 500/700).

The thirteen tricks run on the kernel `round` construct; only the auction is
special (the built-in `BridgeAuction` mechanic). The auction phase declares a
typed outcome — `contract_finalized(declarer, level, strain, doubling)` or
`all_pass` — and the `produces:` consumer either routes on into play or skips the
passed-out hand (see [decisions.md](../decisions.md) "Typed phase outcomes").
Random bids are capped at level 3 so rubbers stay
a realistic dozen-odd hands — game-level and slam contracts are unreachable under
random play (their scoring is implemented but unexercised). The dummy and
declarer-plays-dummy delegation are omitted: pure information/agency structure a
uniform-random playout does not exercise.

```
game Bridge {

  players: 4
  partnerships: [[0, 2], [1, 3]]   // partners sit across
  direction: clockwise

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
  }

  state {
    // The rubber accumulators (one rubber is played); read for the winner.
    games_won[team]     : Integer = 0
    total_score[team]   : Integer = 0
    below_current[team] : Integer = 0    // below-the-line toward the current game
  }

  phase rubber repeats until (any team t: games_won[t] >= 2) {
    state {
      dealer            : Player  = 0
      contract_level    : Integer = 0
      trump_suit        : Suit?   = none   // none = no-trump
      doubled_mult      : Integer = 1
      declarer          : Player? = none
      leader            : Player? = none
      tricks_taken[team]: Integer = 0
    }

    before_each {
      move all cards to deck
      shuffle deck
      deal 13 cards from deck to each hand
      dealer := dealer offset_by left
      for each team t: tricks_taken[t] := 0
    }

    phase auction -> outcome {
      contract_finalized(Player, Integer, Suit?, Integer) | all_pass
    } {
      legal_moves: [submit_bid, pass, double, redouble]
      instantiate BridgeAuction(opener = dealer)
    }
    auction produces:
      contract_finalized(d, level, strain, dbl) {
        declarer       := d
        contract_level := level
        trump_suit     := strain
        doubled_mult   := dbl
        continue to play
      }
      all_pass { skip to next hand }

    phase play {
      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      leader := declarer offset_by left
      repeat until (all player p: hand[p] is empty) {
        round play_to_trick from leader over all players source hand into trick_pile
              outcome highest_trump_or_led_suit trump trump_suit
        move all cards from trick_pile to captured[team_of(outcome)]
        tricks_taken[team_of(outcome)] += 1
        leader := outcome
      }
    }

    phase scoring {
      let dteam    = team_of(declarer)
      let oteam    = 1 - dteam
      let required = 6 + contract_level
      let actual   = tricks_taken[dteam]
      let vuln     = games_won[dteam] >= 1
      let per_trick = if trump_suit is none then 30
                      elif trump_suit == clubs then 20
                      elif trump_suit == diamonds then 20
                      else 30

      if actual >= required {
        let nt_bonus = if trump_suit is none then 10 else 0
        let below = (per_trick * contract_level + nt_bonus) * doubled_mult
        total_score[dteam]   += below
        below_current[dteam] += below

        let over = actual - required
        let ov_each = if doubled_mult == 1 then per_trick
                      elif doubled_mult == 2 then (if vuln then 200 else 100)
                      else (if vuln then 400 else 200)
        total_score[dteam] += ov_each * over

        if contract_level == 6 { total_score[dteam] += if vuln then 750 else 500 }
        if contract_level == 7 { total_score[dteam] += if vuln then 1500 else 1000 }

        if below_current[dteam] >= 100 {
          total_score[dteam] += if vuln then 500 else 300   // game bonus
          games_won[dteam] += 1
          below_current[dteam] := 0
          below_current[oteam] := 0
          if games_won[dteam] >= 2 {
            total_score[dteam] += if games_won[oteam] == 0 then 700 else 500   // rubber bonus
          }
        }
      } else {
        let under = required - actual
        let per_under = if doubled_mult == 1 then (if vuln then 100 else 50)
                        elif doubled_mult == 2 then (if vuln then 200 else 100)
                        else (if vuln then 400 else 200)            // redoubled
        total_score[oteam] += per_under * under
      }
    }
  }

  winner: highest total_score
}

rule MustFollowSuit {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: hand.cards_of_suit(state.led_suit)
}
```
