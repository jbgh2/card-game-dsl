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
phase state, and every window field is cleared where the action that opened
it resolves, so the seat asked for its turn reads no verdict and no claimant
from the action just settled. Coins are integers (always 50 in total, the treasury clamping
every gain) and influence cards conserve to 15. `alive[p]` is a Boolean —
true while a player is in, false once exiled — so `winner: highest alive`
names the survivor. The three blocks the game repeats — the challenge window
(×8), the influence loss (×14) and the proven-claim swap (×7) — are named
`procedure`s, written once and `run` at each site, with each argument bound once
at the call ([decisions.md](../decisions.md) "Named procedures"). The forced Coup at 10 coins drives every aggressive line to an
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
    alive[player]  : Boolean = true
  }

  phase play {
    state {
      turn             : Player  = 0
      // Everything below belongs to ONE action and its windows, and holds
      // its idle value between actions: `clear_windows` runs where the
      // action resolves, so the seat asked for its turn reads no verdict
      // and no claimant from the action that just settled. `turn` is the
      // exception — it is the rotation itself, and outlives every action.
      challenge_stands : Boolean = true   // idle: no claim is pending to disprove
      block_stands     : Boolean = false
      challenged       : Boolean = false
      challenger       : Player? = none
      block_claim      : Rank?   = none
      blocker          : Player? = none
      responder        : Player? = none
      window_open      : Boolean = false
    }

    shuffle court_deck
    deal 2 cards from court_deck to each influence
    for each player p: coins[p] += 2
    treasury -= 8

    repeat until (number of players where alive[player] and influence[player] is not empty) <= 1 {
      if alive[turn] and influence[turn] is not empty {
        offer to turn one of [income, foreign_aid, tax, steal, exchange, coup, assassinate]
      }
      turn := the first player from turn offset_by left where alive[player] and influence[player] is not empty
    }

    let summary = coup_game_summary()
  }

  winner: highest alive
}

// --- the three repeated blocks, named ---

// The challenge window on a claim: everyone else, clockwise from the claimant,
// is offered [challenge, allow]; the first challenge closes the window. Leaves
// its verdict in `challenged` (and the challenger's seat in `challenger`).
// The idle state of an action's bookkeeping, run where the action resolves.
// Reset at the END of the action rather than the start of the next one: the
// two differ exactly at the turn decision in between, which is where the
// asking seat reads the state. `income` and `coup` open no window, so they
// leave the state idle and do not call this.
procedure clear_windows() {
  challenged := false
  challenger := none
  block_claim := none
  blocker := none
  responder := none
  challenge_stands := true
  block_stands := false
}

procedure challenge_window(claimant : Player) {
  challenged := false
  window_open := true
  responder := claimant
  repeat until not window_open {
    responder := the first player from responder offset_by left where alive[player] and influence[player] is not empty
    if responder is claimant { window_open := false }
    if window_open {
      offer to responder one of [challenge, allow]
      if challenged { window_open := false }
    }
  }
}

// A challenge answered by proof: show the claimed card, return it to the deck,
// reshuffle, and draw a replacement (real Coup shows the proven card). `claim` is
// `Rank?` because the caller cannot prove to the checker that a block claim is
// set — the call sites all sit inside `if block_claim is not none`, but the
// language has no flow narrowing, and a `Rank` parameter would reject the very
// argument the block sites need to pass.
procedure prove_claim(claimant : Player, claim : Rank?) {
  reveal one card from influence[claimant] where card.rank is claim
  move one card from influence[claimant] where card.rank is claim to court_deck
  shuffle court_deck
  deal one card from court_deck to influence[claimant]
}

// One influence lost: the victim chooses which of their own cards to flip face
// up, and is exiled (coins to the treasury) once they hold none.
//
// The `as victim` block is what makes the VICTIM, not the caller, the chooser of
// the flipped card: binding a player also binds the acting player, and a `chosen`
// movement asks whoever is acting. Reading `victim` inside the block is safe
// because a procedure argument is evaluated ONCE, in the caller's context, before
// the body runs (decisions.md "Named procedures") — so the `actor` passed at four
// of these sites is the move's actor.
procedure lose_influence(victim : Player) {
  as victim {
    if alive[victim] and influence[victim] is not empty {
      move chosen one card from influence[victim] to revealed[victim]
      if influence[victim] is empty { alive[victim] := false
        treasury += coins[victim]
        coins[victim] := 0 }
    }
  }
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
    block_claim := Duke
    blocker := actor
  }
}

move_type block_claiming_captain {
  effect {
    block_claim := Captain
    blocker := actor
  }
}

move_type block_claiming_ambassador {
  effect {
    block_claim := Ambassador
    blocker := actor
  }
}

move_type block_claiming_contessa {
  effect {
    block_claim := Contessa
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
    block_claim := none
    window_open := true
    responder := actor
    repeat until not window_open {
      responder := the first player from responder offset_by left where alive[player] and influence[player] is not empty
      if responder is actor { window_open := false }
      if window_open {
        offer to responder one of [block_claiming_duke, allow]
        if block_claim is not none { window_open := false }
      }
    }
    if block_claim is not none {
      block_stands := true
      run challenge_window(blocker)
      if challenged {
        if any card in influence[blocker] where card.rank is block_claim {
          run prove_claim(blocker, block_claim)
          run lose_influence(challenger)
        } else {
          run lose_influence(blocker)
          block_stands := false
        }
      }
    }
    if not block_stands {
      let g = if treasury < 2 then treasury else 2
      treasury -= g
      coins[actor] += g
    }
    run clear_windows()
  }
}

move_type tax {
  when: coins[actor] < 10
  effect {
    challenge_stands := true
    run challenge_window(actor)
    if challenged {
      if any card in influence[actor] where card.rank is Duke {
        run prove_claim(actor, Duke)
        run lose_influence(challenger)
      } else {
        run lose_influence(actor)
        challenge_stands := false
      }
    }
    if challenge_stands {
      let g = if treasury < 3 then treasury else 3
      treasury -= g
      coins[actor] += g
    }
    run clear_windows()
  }
}

move_type steal(target : Player) {
  when: coins[actor] < 10 and target is not actor
        and alive[target] and influence[target] is not empty
  effect {
    challenge_stands := true
    run challenge_window(actor)
    if challenged {
      if any card in influence[actor] where card.rank is Captain {
        run prove_claim(actor, Captain)
        run lose_influence(challenger)
      } else {
        run lose_influence(actor)
        challenge_stands := false
      }
    }
    if challenge_stands {
      // block window: the target alone chooses WHICH character to claim, or allows.
      block_stands := false
      block_claim := none
      if alive[target] and influence[target] is not empty {
        offer to target one of [block_claiming_captain, block_claiming_ambassador, allow]
      }
      if block_claim is not none {
        block_stands := true
        run challenge_window(target)
        if challenged {
          if any card in influence[target] where card.rank is block_claim {
            run prove_claim(target, block_claim)
            run lose_influence(challenger)
          } else {
            run lose_influence(target)
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
    run clear_windows()
  }
}

move_type exchange {
  when: coins[actor] < 10
  effect {
    challenge_stands := true
    run challenge_window(actor)
    if challenged {
      if any card in influence[actor] where card.rank is Ambassador {
        run prove_claim(actor, Ambassador)
        run lose_influence(challenger)
      } else {
        run lose_influence(actor)
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
    run clear_windows()
  }
}

move_type coup(target : Player) {
  when: coins[actor] >= 7 and target is not actor
        and alive[target] and influence[target] is not empty
  effect {
    coins[actor] -= 7
    treasury += 7
    run lose_influence(target)
  }
}

move_type assassinate(target : Player) {
  when: coins[actor] >= 3 and coins[actor] < 10 and target is not actor
        and alive[target] and influence[target] is not empty
  effect {
    coins[actor] -= 3
    treasury += 3
    challenge_stands := true
    run challenge_window(actor)
    if challenged {
      if any card in influence[actor] where card.rank is Assassin {
        run prove_claim(actor, Assassin)
        run lose_influence(challenger)
      } else {
        run lose_influence(actor)
        challenge_stands := false
      }
    }
    if challenge_stands {
      // block window: the target alone may claim the Contessa.
      block_stands := false
      block_claim := none
      if alive[target] and influence[target] is not empty {
        offer to target one of [block_claiming_contessa, allow]
      }
      if block_claim is not none {
        block_stands := true
        run challenge_window(target)
        if challenged {
          if any card in influence[target] where card.rank is block_claim {
            run prove_claim(target, block_claim)
            run lose_influence(challenger)
          } else {
            run lose_influence(target)
            block_stands := false
          }
        }
      }
      if not block_stands {
        run lose_influence(target)
      }
    }
    run clear_windows()
  }
}
```
