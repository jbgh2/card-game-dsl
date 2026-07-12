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

The game runs fully on the kernel, at real interactive scope. Each turn is
one `offer` over the seven coin-guarded actions (the forced Coup at ten
coins falls out of the `when:` guards); `steal`, `assassinate`, and `coup`
carry a declared `target : Player` parameter, so naming the victim is the
actor's own announced choice. A claimed action opens a challenge window —
each other in-game player, clockwise from the claimant's left, is offered
`[challenge, allow]`, and the first challenge closes the window. Blocks are
decisions too: foreign aid polls every opponent with
`[block_claiming_duke, allow]`, while a steal or assassination offers its
target the block vocabulary — so *which* character the blocker claims, the
bluff itself, is the decision. A block claim is challengeable by everyone
else, including the original actor, through the same window. A proven
challenge `reveal`s the shown card publicly, returns it to the deck,
reshuffles, and redraws; every influence loss is a chosen movement by the
loser, flipped publicly into `revealed` (everyone sees the lost card — real
Coup); the exchange draws off the top, returns two chosen cards, and
reshuffles. Window results (`challenge_stands` / `block_stands`) are public
phase state. Coins are integers (always 50 in total, the treasury clamping
every gain) and influence cards conserve to 15. `alive[p]` is 1 while a
player is in and 0 once exiled, so `winner: highest alive` names the
survivor. The forced Coup at 10 coins drives every aggressive line to an
end; a table that only ever exchanges makes no coin progress, so the
declared `max_length` backstop is Coup's real termination bound on
maximally passive lines
([open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md)).

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
      challenged       : Boolean = false
      challenger       : Player  = 0
      block_claim      : String  = ""
      blocker          : Player  = 0
      responder        : Player  = 0
      window_open      : Boolean = false
    }

    shuffle court_deck
    deal 2 cards from court_deck to each influence
    for each player p: coins[p] += 2
    treasury -= 8

    repeat until coup_players_in() <= 1 {
      if alive[turn] is 1 and influence[turn] is not empty {
        offer to turn one of [income, foreign_aid, tax, steal, exchange, coup, assassinate]
      }
      turn := coup_next_in_game(turn)
    }

    let summary = coup_game_summary()
  }

  winner: highest alive
}

// --- response vocabulary (window decisions; always legal when offered) ---

move_type challenge {
  effect {
    challenged := true
    challenger := actor
  }
}

move_type allow {
  effect {
  }
}

move_type block_claiming_duke {
  effect {
    block_claim := "Duke"
    blocker := actor
  }
}

move_type block_claiming_captain {
  effect {
    block_claim := "Captain"
    blocker := actor
  }
}

move_type block_claiming_ambassador {
  effect {
    block_claim := "Ambassador"
    blocker := actor
  }
}

move_type block_claiming_contessa {
  effect {
    block_claim := "Contessa"
    blocker := actor
  }
}

// --- the seven actions ---

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
    // block window: every other in-game player, clockwise from the actor,
    // may claim the Duke; the first block closes the window.
    block_stands := false
    block_claim := ""
    window_open := true
    responder := actor
    repeat until not window_open {
      responder := coup_next_in_game(responder)
      if responder is actor { window_open := false }
      if window_open {
        offer to responder one of [block_claiming_duke, allow]
        if block_claim is not "" { window_open := false }
      }
    }
    if block_claim is not "" {
      block_stands := true
      // challenge window on the blocker's Duke claim: everyone else,
      // including the original actor, clockwise from the blocker.
      challenged := false
      window_open := true
      responder := blocker
      repeat until not window_open {
        responder := coup_next_in_game(responder)
        if responder is blocker { window_open := false }
        if window_open {
          offer to responder one of [challenge, allow]
          if challenged { window_open := false }
        }
      }
      if challenged {
        if coup_has_char(blocker, block_claim) {
          reveal one card from influence[blocker] where card.rank is block_claim
          move one card from influence[blocker] where card.rank is block_claim to court_deck
          shuffle court_deck
          deal one card from court_deck to influence[blocker]
          for each player q:
            if q is challenger and alive[q] is 1 and influence[q] is not empty {
              move chosen one card from influence[q] to revealed[q]
              let noted = coup_note_reveal(q)
              if influence[q] is empty { alive[q] := 0
                treasury += coins[q]
                coins[q] := 0 }
            }
        } else {
          for each player q:
            if q is blocker and alive[q] is 1 and influence[q] is not empty {
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
    // challenge window on the actor's Duke claim.
    challenged := false
    window_open := true
    responder := actor
    repeat until not window_open {
      responder := coup_next_in_game(responder)
      if responder is actor { window_open := false }
      if window_open {
        offer to responder one of [challenge, allow]
        if challenged { window_open := false }
      }
    }
    if challenged {
      if coup_has_char(actor, "Duke") {
        reveal one card from influence[actor] where card.rank is Duke
        move one card from influence[actor] where card.rank is Duke to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q is challenger and alive[q] is 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] is 1 and influence[actor] is not empty {
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

move_type steal(target : Player) {
  when: coins[actor] < 10 and target is not actor
        and alive[target] is 1 and influence[target] is not empty
  effect {
    challenge_stands := true
    // challenge window on the actor's Captain claim.
    challenged := false
    window_open := true
    responder := actor
    repeat until not window_open {
      responder := coup_next_in_game(responder)
      if responder is actor { window_open := false }
      if window_open {
        offer to responder one of [challenge, allow]
        if challenged { window_open := false }
      }
    }
    if challenged {
      if coup_has_char(actor, "Captain") {
        reveal one card from influence[actor] where card.rank is Captain
        move one card from influence[actor] where card.rank is Captain to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q is challenger and alive[q] is 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] is 1 and influence[actor] is not empty {
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
      // block window: the target alone chooses WHICH character to claim, or allows.
      block_stands := false
      block_claim := ""
      if alive[target] is 1 and influence[target] is not empty {
        offer to target one of [block_claiming_captain, block_claiming_ambassador, allow]
      }
      if block_claim is not "" {
        block_stands := true
        // challenge window on the block claim: everyone else, incl. the actor.
        challenged := false
        window_open := true
        responder := target
        repeat until not window_open {
          responder := coup_next_in_game(responder)
          if responder is target { window_open := false }
          if window_open {
            offer to responder one of [challenge, allow]
            if challenged { window_open := false }
          }
        }
        if challenged {
          if coup_has_char(target, block_claim) {
            reveal one card from influence[target] where card.rank is block_claim
            move one card from influence[target] where card.rank is block_claim to court_deck
            shuffle court_deck
            deal one card from court_deck to influence[target]
            for each player q:
              if q is challenger and alive[q] is 1 and influence[q] is not empty {
                move chosen one card from influence[q] to revealed[q]
                let noted = coup_note_reveal(q)
                if influence[q] is empty { alive[q] := 0
                  treasury += coins[q]
                  coins[q] := 0 }
              }
          } else {
            for each player q:
              if q is target and alive[q] is 1 and influence[q] is not empty {
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
        let amt = if coins[target] < 2 then coins[target] else 2
        coins[target] -= amt
        coins[actor] += amt
      }
    }
  }
}

move_type exchange {
  when: coins[actor] < 10
  effect {
    challenge_stands := true
    // challenge window on the actor's Ambassador claim.
    challenged := false
    window_open := true
    responder := actor
    repeat until not window_open {
      responder := coup_next_in_game(responder)
      if responder is actor { window_open := false }
      if window_open {
        offer to responder one of [challenge, allow]
        if challenged { window_open := false }
      }
    }
    if challenged {
      if coup_has_char(actor, "Ambassador") {
        reveal one card from influence[actor] where card.rank is Ambassador
        move one card from influence[actor] where card.rank is Ambassador to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q is challenger and alive[q] is 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] is 1 and influence[actor] is not empty {
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
      let avail = number of cards in court_deck
      let n = if avail < 2 then avail else 2
      deal n cards from court_deck to influence[actor]
      move chosen n cards from influence[actor] to court_deck
      shuffle court_deck
    }
  }
}

move_type coup(target : Player) {
  when: coins[actor] >= 7 and target is not actor
        and alive[target] is 1 and influence[target] is not empty
  effect {
    coins[actor] -= 7
    treasury += 7
    for each player q:
      if q is target and alive[q] is 1 and influence[q] is not empty {
        move chosen one card from influence[q] to revealed[q]
        let noted = coup_note_reveal(q)
        if influence[q] is empty { alive[q] := 0
          treasury += coins[q]
          coins[q] := 0 }
      }
  }
}

move_type assassinate(target : Player) {
  when: coins[actor] >= 3 and coins[actor] < 10 and target is not actor
        and alive[target] is 1 and influence[target] is not empty
  effect {
    coins[actor] -= 3
    treasury += 3
    challenge_stands := true
    // challenge window on the actor's Assassin claim.
    challenged := false
    window_open := true
    responder := actor
    repeat until not window_open {
      responder := coup_next_in_game(responder)
      if responder is actor { window_open := false }
      if window_open {
        offer to responder one of [challenge, allow]
        if challenged { window_open := false }
      }
    }
    if challenged {
      if coup_has_char(actor, "Assassin") {
        reveal one card from influence[actor] where card.rank is Assassin
        move one card from influence[actor] where card.rank is Assassin to court_deck
        shuffle court_deck
        deal one card from court_deck to influence[actor]
        for each player q:
          if q is challenger and alive[q] is 1 and influence[q] is not empty {
            move chosen one card from influence[q] to revealed[q]
            let noted = coup_note_reveal(q)
            if influence[q] is empty { alive[q] := 0
              treasury += coins[q]
              coins[q] := 0 }
          }
      } else {
        if alive[actor] is 1 and influence[actor] is not empty {
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
      // block window: the target alone may claim the Contessa.
      block_stands := false
      block_claim := ""
      if alive[target] is 1 and influence[target] is not empty {
        offer to target one of [block_claiming_contessa, allow]
      }
      if block_claim is not "" {
        block_stands := true
        // challenge window on the Contessa claim: everyone else, incl. the actor.
        challenged := false
        window_open := true
        responder := target
        repeat until not window_open {
          responder := coup_next_in_game(responder)
          if responder is target { window_open := false }
          if window_open {
            offer to responder one of [challenge, allow]
            if challenged { window_open := false }
          }
        }
        if challenged {
          if coup_has_char(target, block_claim) {
            reveal one card from influence[target] where card.rank is block_claim
            move one card from influence[target] where card.rank is block_claim to court_deck
            shuffle court_deck
            deal one card from court_deck to influence[target]
            for each player q:
              if q is challenger and alive[q] is 1 and influence[q] is not empty {
                move chosen one card from influence[q] to revealed[q]
                let noted = coup_note_reveal(q)
                if influence[q] is empty { alive[q] := 0
                  treasury += coins[q]
                  coins[q] := 0 }
              }
          } else {
            for each player q:
              if q is target and alive[q] is 1 and influence[q] is not empty {
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
          if q is target and alive[q] is 1 and influence[q] is not empty {
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
