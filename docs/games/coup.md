# Coup

The companion formal file is [coup.cardlang](coup.cardlang); this is the
readable twin. Coup (base game, 3-6 players; the executable fixes four) — a
bluff-and-challenge game with a 15-card deck (five characters, three copies
each) and a coin economy. Each player holds two face-down *influence* cards and
some coins; on a turn the active player takes one action, others may challenge
or block it, and influence is lost by flipping a card permanently face-up. The
last player with influence wins. Rules: Tchanturia, 2012.

A turn's actions:

- **Income** — take 1 coin (uncontestable).
- **Foreign aid** — take 2 coins, unless someone claims the Duke to block it.
- **Coup** — pay 7, force a player to lose influence (uncontestable). Forced once
  you reach 10 coins.
- **Tax** (claim Duke) — take 3 coins.
- **Assassinate** (claim Assassin) — pay 3, a target loses influence unless they
  claim the Contessa to block.
- **Steal** (claim Captain) — take 2 coins from a target unless they claim
  Captain or Ambassador to block.
- **Exchange** (claim Ambassador) — draw 2 from the deck and return 2.

Any character claim (an action or a block) can be **challenged**: if the claimant
holds the character, the challenger loses influence and the claimant swaps the
proven card for a fresh one; if it was a bluff, the claimant loses influence and
the action fails. A player who loses their last influence is exiled and their
coins return to the bank.

The game runs fully on the kernel. Each turn is one `offer` over the seven
coin-guarded actions (the forced Coup at ten coins falls out of the `when:`
guards); every influence loss is a chosen movement by the loser, flipped
publicly into `revealed` (everyone sees the lost card — real Coup); the
exchange draws off the top, returns two chosen cards, and reshuffles. At the
migrated random-play scope the response windows carry no player decisions —
challenges and blocks fire at a modest random rate, the blocker's claimed
character is a random pick, and targets are random in-game opponents — so
they are inline statements around game-local rng primitives at the
reference's exact draw sites, with the window results
(`challenge_stands` / `block_stands`) as public phase state. A proven
challenge returns the claimed card to the deck, reshuffles, and redraws (as
hidden movements; real Coup shows the proven card — that fidelity upgrade
rides the interactive-windows scope of
[kernel-migration.md](../kernel-migration.md), Workstream 5, along with
challenge/block/target as real decisions). Coins are integers (always 50 in
total, the treasury clamping every gain) and influence cards conserve to 15.
`alive[p]` is 1 while a player is in
and 0 once exiled, so `winner: highest alive` names the survivor. The forced
Coup at 10 coins guarantees elimination and termination.

```
game Coup {

  players: 4
  direction: clockwise
  max_length: 500

  cards: coup15

  zones {
    court_deck        : Deck
    influence[player] : Hand<player>
    revealed[player]  : PlayerPile<player>
  }

  state {
    coins[player]  : Integer = 0
    treasury       : Integer = 50
    alive[player]  : Integer = 1
  }

  phase play {
    state {
      turn             : Player  = 0
      challenge_stands : Boolean = true
      block_stands     : Boolean = false
    }

    shuffle court_deck
    deal 2 cards from court_deck to each influence
    for each player p: coins[p] += 2
    treasury -= 8

    repeat until coup_players_in() <= 1 {
      if alive[turn] == 1 and influence[turn] is not empty {
        offer to turn one of [income, foreign_aid, tax, steal, exchange, coup, assassinate]
      }
      turn := coup_next_in_game(turn)
    }

    let summary = coup_game_summary()
  }

  winner: highest alive
}

move_type income {
  when: coins[actor] < 10
  effect {
    let g = if treasury < 1 then treasury else 1
    treasury -= g
    coins[actor] += g
  }
}

move_type foreign_aid {
  when: coins[actor] < 10
  effect {
    block_stands := false
    let b = coup_fa_blocker(actor)
    if b is not none {
      let claim = coup_duke_claim()
      block_stands := true
      let ch = coup_challenger(b)
      if ch is not none {
        if coup_has_char(b, claim) {
          move one card from influence[b] where c => c.rank == claim to court_deck
          shuffle court_deck
          deal one card from court_deck to influence[b]
          for each player q:
            if q == ch and alive[q] == 1 and influence[q] is not empty {
              move chosen one card from influence[q] to revealed[q]
              let noted = coup_note_reveal(q)
              if influence[q] is empty { alive[q] := 0
                treasury += coins[q]
                coins[q] := 0 }
            }
        } else {
          for each player q:
            if q == b and alive[q] == 1 and influence[q] is not empty {
              move chosen one card from influence[q] to revealed[q]
              let noted = coup_note_reveal(q)
              if influence[q] is empty { alive[q] := 0
                treasury += coins[q]
                coins[q] := 0 }
            }
          block_stands := false
        }
      }
    }
    if not block_stands {
      let g = if treasury < 2 then treasury else 2
      treasury -= g
      coins[actor] += g
    }
  }
}

move_type tax {
  when: coins[actor] < 10
  effect {
    challenge_stands := true
    let ch = coup_challenger(actor)
    if ch is not none {
      if coup_has_char(actor, "Duke") {
        move one card from influence[actor] where c => c.rank == "Duke" to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q == ch and alive[q] == 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] == 1 and influence[actor] is not empty {
          move chosen one card from influence[actor] to revealed[actor]
          let noted = coup_note_reveal(actor)
          if influence[actor] is empty { alive[actor] := 0
            treasury += coins[actor]
            coins[actor] := 0 }
        }
        challenge_stands := false
      }
    }
    if challenge_stands {
      let g = if treasury < 3 then treasury else 3
      treasury -= g
      coins[actor] += g
    }
  }
}

move_type steal {
  when: coins[actor] < 10
  effect {
    let t = coup_random_target(actor)
    challenge_stands := true
    let ch = coup_challenger(actor)
    if ch is not none {
      if coup_has_char(actor, "Captain") {
        move one card from influence[actor] where c => c.rank == "Captain" to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q == ch and alive[q] == 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] == 1 and influence[actor] is not empty {
          move chosen one card from influence[actor] to revealed[actor]
          let noted = coup_note_reveal(actor)
          if influence[actor] is empty { alive[actor] := 0
            treasury += coins[actor]
            coins[actor] := 0 }
        }
        challenge_stands := false
      }
    }
    if challenge_stands {
      block_stands := false
      if alive[t] == 1 and influence[t] is not empty and coup_block_roll() {
        let claim = coup_steal_block_claim()
        block_stands := true
        let bch = coup_challenger(t)
        if bch is not none {
          if coup_has_char(t, claim) {
            move one card from influence[t] where c => c.rank == claim to court_deck
            shuffle court_deck
            deal one card from court_deck to influence[t]
            for each player q:
              if q == bch and alive[q] == 1 and influence[q] is not empty {
                move chosen one card from influence[q] to revealed[q]
                let noted = coup_note_reveal(q)
                if influence[q] is empty { alive[q] := 0
                  treasury += coins[q]
                  coins[q] := 0 }
              }
          } else {
            for each player q:
              if q == t and alive[q] == 1 and influence[q] is not empty {
                move chosen one card from influence[q] to revealed[q]
                let noted = coup_note_reveal(q)
                if influence[q] is empty { alive[q] := 0
                  treasury += coins[q]
                  coins[q] := 0 }
              }
            block_stands := false
          }
        }
      }
      if not block_stands {
        let amt = if coins[t] < 2 then coins[t] else 2
        coins[t] -= amt
        coins[actor] += amt
      }
    }
  }
}

move_type exchange {
  when: coins[actor] < 10
  effect {
    challenge_stands := true
    let ch = coup_challenger(actor)
    if ch is not none {
      if coup_has_char(actor, "Ambassador") {
        move one card from influence[actor] where c => c.rank == "Ambassador" to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q == ch and alive[q] == 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] == 1 and influence[actor] is not empty {
          move chosen one card from influence[actor] to revealed[actor]
          let noted = coup_note_reveal(actor)
          if influence[actor] is empty { alive[actor] := 0
            treasury += coins[actor]
            coins[actor] := 0 }
        }
        challenge_stands := false
      }
    }
    if challenge_stands {
      let avail = count over court_deck as c: true
      let n = if avail < 2 then avail else 2
      deal n cards from court_deck to influence[actor]
      move chosen n cards from influence[actor] to court_deck
      shuffle court_deck
    }
  }
}

move_type coup {
  when: coins[actor] >= 7
  effect {
    let t = coup_random_target(actor)
    coins[actor] -= 7
    treasury += 7
    for each player q:
      if q == t and alive[q] == 1 and influence[q] is not empty {
        move chosen one card from influence[q] to revealed[q]
        let noted = coup_note_reveal(q)
        if influence[q] is empty { alive[q] := 0
          treasury += coins[q]
          coins[q] := 0 }
      }
  }
}

move_type assassinate {
  when: coins[actor] >= 3 and coins[actor] < 10
  effect {
    let t = coup_random_target(actor)
    coins[actor] -= 3
    treasury += 3
    challenge_stands := true
    let ch = coup_challenger(actor)
    if ch is not none {
      if coup_has_char(actor, "Assassin") {
        move one card from influence[actor] where c => c.rank == "Assassin" to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q == ch and alive[q] == 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] == 1 and influence[actor] is not empty {
          move chosen one card from influence[actor] to revealed[actor]
          let noted = coup_note_reveal(actor)
          if influence[actor] is empty { alive[actor] := 0
            treasury += coins[actor]
            coins[actor] := 0 }
        }
        challenge_stands := false
      }
    }
    if challenge_stands {
      block_stands := false
      if alive[t] == 1 and influence[t] is not empty and coup_block_roll() {
        let claim = coup_contessa_claim()
        block_stands := true
        let bch = coup_challenger(t)
        if bch is not none {
          if coup_has_char(t, claim) {
            move one card from influence[t] where c => c.rank == claim to court_deck
            shuffle court_deck
            deal one card from court_deck to influence[t]
            for each player q:
              if q == bch and alive[q] == 1 and influence[q] is not empty {
                move chosen one card from influence[q] to revealed[q]
                let noted = coup_note_reveal(q)
                if influence[q] is empty { alive[q] := 0
                  treasury += coins[q]
                  coins[q] := 0 }
              }
          } else {
            for each player q:
              if q == t and alive[q] == 1 and influence[q] is not empty {
                move chosen one card from influence[q] to revealed[q]
                let noted = coup_note_reveal(q)
                if influence[q] is empty { alive[q] := 0
                  treasury += coins[q]
                  coins[q] := 0 }
              }
            block_stands := false
          }
        }
      }
      if not block_stands {
        for each player q:
          if q == t and alive[q] == 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      }
    }
  }
}
```
