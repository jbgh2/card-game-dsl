# Seven-Card Stud

The companion formal file is
[seven-card-stud.cardlang](seven-card-stud.cardlang); this is the readable twin.
Fixed-limit Seven-Card Stud — the corpus's first **betting** game. Source:
[Pagat](https://www.pagat.com/poker/variants/7stud.html).

Each hand:

1. Every player antes; deal two hole cards and one upcard each.
2. The lowest upcard (ties by suit) **brings in**.
3. Five betting streets — 3rd through 7th — interleaved with a dealt card each
   (an upcard on 4th/5th/6th, a face-down card on 7th, a burn before each). On
   each street a player may check, bet, call, raise (capped), or fold; the
   highest visible board acts first from 4th street on. The lower limit applies
   on 3rd/4th, the upper limit from 5th.
4. **Showdown** — the best five-card poker hand from each remaining player's seven
   cards wins the pot, with side pots when players are all-in.

The `.md` source is a cash game with no overall winner; to give the runtime a
terminal, the executable plays until one player holds **all** the chips and names
that player the winner. Chips are modelled as an integer `stack` per player (not
a resource-zone subsystem); the total is invariant. The whole hand runs in the
DSL: the betting — antes, deal, the bring-in post, and the five streets — on the
kernel `round` in **priority order** (each turn re-scans the seat order from the
leader and offers the first still-pending player, so after a raise re-opens
earlier seats action returns to the earliest owing seat), and the showdown as
plain statements — a contested hand reveals the contenders' hole cards into the
public board, each entrant collects its side-pot share via `pot_share(p)`, and
the hands leave play to the muck. The stdlib primitives are pure reads: the
door-card seat selectors (`bring_in_seat` / `first_to_act_seat`) and the
side-pot query (`pot_share`); the poker evaluator behind them is unit-tested.
The 4th-street open-pair limit doubling is simplified out.

The betting state is carried as ordinary phase state (`bet_to_match`, `raises`,
per-player `bet_by`/`acted`/`folded`/`committed`); a `check`/`bet`/`call`/`raise`/
`fold` move type writes it (a bet or raise is a partial all-in when the actor
can't cover it, and resets every other player's `acted` so action re-opens). The
`until` predicate closes a street when no live player still owes or has yet to act
(or one lone contender remains, already matched). The 3rd street is shown in full;
streets 4–7 repeat the same betting round after a burn and a dealt card.

```
game SevenCardStud {

  players: 4
  direction: clockwise
  max_length: 30000

  cards: standard52
  ranking: aces high

  zones {
    deck            : Deck
    hole[player]    : Hand<player>           // face-down cards
    upcards[player] : PublicHand<player>     // face-up cards
    muck            : Muck                   // folded / spent cards
    burn            : Burn                   // one burned card per street
  }

  state {
    stack[player] : Integer = 100            // chips; total invariant, winner holds all
  }

  phase hand_sequence repeat until (number of players where stack[player] > 0) <= 1 {
    state { dealer : Player = 0 }
    before_each { move all cards to deck  shuffle deck  dealer := dealer offset_by left }

    phase play {
      state {
        in_hand[player] : Boolean = false   committed[player] : Integer = 0
        folded[player]  : Boolean = false   bet_by[player]    : Integer = 0
        acted[player]   : Boolean = false   bet_to_match : Integer = 0
        raises : Integer = 0   limit : Integer = 0
      }

      for each player p: in_hand[p] := stack[p] > 0
      for each player p: if in_hand[p] { stack[p] := stack[p] - 1  committed[p] := committed[p] + 1 }
      for each player p: if in_hand[p] { deal 2 cards from deck to hole[p]  deal 1 card from deck to upcards[p] }

      // Bring-in (a forced post) + 3rd street.
      if (number of players where stack[player] > 0) >= 2 {
        let bringer = bring_in_seat()
        bet_by[bringer] := if 2 < stack[bringer] then 2 else stack[bringer]
        stack[bringer] := stack[bringer] - bet_by[bringer]
        committed[bringer] := committed[bringer] + bet_by[bringer]
        bet_to_match := 2   raises := 1   limit := 5
        round offering [check, bet, call, fold, raise] from bringer offset_by left
              over players where pending(player)
              order priority
              until (number of players where pending(player)) is 0
                 or ((number of players where can_act(player)) <= 1
                     and (number of players where can_act(player) and owes(player)) is 0)
      }
      // ... 4th–7th streets: four flat `if (contenders > 1) { ... }` blocks — a burn
      // + a dealt card (upcard on 4th/5th/6th, hole on 7th), then the same betting
      // round with limits 5 / 10 / 10 / 10 and `from first_to_act_seat()`. The
      // contender count is monotonic, so the flat guards short-circuit exactly as
      // nesting would (see seven-card-stud.cardlang).

      // Showdown — RNG-free, decision-free. A contested hand reveals the
      // contenders' hole cards (the two-step move keeps the muck order the
      // next hand's pre-shuffle deck depends on; the flip into the public
      // board emits the seven identities — the derived reveal). Each entrant
      // collects its side-pot share; the hands leave play to the muck.
      if (number of players where in_hand[player] and not folded[player]) > 1 {
        for each player p: if in_hand[p] and not folded[p] {
          move all cards from upcards[p] to hole[p]
          move all cards from hole[p] to upcards[p]
        }
      }
      for each player p: if in_hand[p] { stack[p] := stack[p] + pot_share(p) }
      for each player p: if in_hand[p] {
        move all cards from hole[p] to muck
        move all cards from upcards[p] to muck
      }
    }
  }

  winner: highest stack
}

// The betting vocabulary (game-defined move types). Offered in this order; the
// `when:` guards filter to the legal options at each decision.
move_type check { when: bet_to_match <= bet_by[actor]  effect { acted[actor] := true } }
move_type bet {
  when: bet_to_match is 0
  effect {
    let post = if limit < stack[actor] then limit else stack[actor]
    stack[actor] := stack[actor] - post   committed[actor] := committed[actor] + post
    bet_by[actor] := bet_by[actor] + post  bet_to_match := bet_by[actor]  raises := 1
    for each player p: acted[p] := false   acted[actor] := true
  }
}
move_type call {
  when: bet_to_match > bet_by[actor]
  effect {
    let owed = bet_to_match - bet_by[actor]   let pay = if owed < stack[actor] then owed else stack[actor]
    stack[actor] := stack[actor] - pay   committed[actor] := committed[actor] + pay
    bet_by[actor] := bet_by[actor] + pay   acted[actor] := true
  }
}
move_type raise {
  when: bet_to_match > bet_by[actor] and raises < 3
  effect {
    let owed = bet_to_match - bet_by[actor]   let want = owed + limit
    let pay = if want < stack[actor] then want else stack[actor]
    stack[actor] := stack[actor] - pay   committed[actor] := committed[actor] + pay
    bet_by[actor] := bet_by[actor] + pay
    bet_to_match := if bet_to_match > bet_by[actor] then bet_to_match else bet_by[actor]
    raises := raises + 1   for each player p: acted[p] := false   acted[actor] := true
  }
}
move_type fold {
  when: bet_to_match > bet_by[actor]
  effect { folded[actor] := true  move all cards from upcards[actor] to muck }
}

// Betting-ring predicates, factored with named functions so the `over` filter and
// the `until` terminator name the same set (and cannot drift). `pending` composes
// the others.
function can_act(p : Player) = not folded[p] and stack[p] > 0
function owes(p : Player)    = bet_by[p] < bet_to_match
function pending(p : Player) = can_act(p) and (not acted[p] or owes(p))
```
