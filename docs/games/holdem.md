# Texas Hold'em

The companion formal file is [holdem.cardlang](holdem.cardlang); this is the
readable twin. Fixed-limit Texas Hold'em, three players — the corpus's second
**side-pot** game and its first with a **community board**. Source:
[Pagat](https://www.pagat.com/poker/variants/texasholdem.html).

Each hand:

1. The dealer button moves to the next seat that still has chips. The player
   to its left posts the
   **small blind** (2), the next the **big blind** (5) — these are forced bets,
   not decisions. **Heads-up the blinds reverse**: the button posts the small
   blind.
2. Burn one card, then deal each player two face-down **hole cards**.
3. **Pre-flop** betting, begun by the player to the big blind's left. A player
   may check, bet, call, raise (capped), or fold.
4. **The flop** — burn one, deal three face-up **community cards** — then a
   betting round begun by the first live player to the button's left.
5. **The turn** — burn one, deal one — then a betting round. Limits double here
   (5 becomes 10).
6. **The river** — burn one, deal one — then the last betting round.
7. **Showdown** — each remaining player makes their best five-card poker hand
   from the seven available (their two hole cards plus the five community
   cards), and the best hand wins the pot, with side pots when players are
   all-in. A hand may use both hole cards, one, or none — "playing the board".

The community cards belong to nobody and are read by **every** player's hand
evaluation. That is the interesting thing about this game for the language: the
board is declared `Discard`, the library zone type whose contents are visible to
all, so its publicness is a property of its *type* and needs no rule. Leduc's
single face-up card already used that type; Hold'em is the five-card case.

The `.md` source is a cash game with no overall winner; to give the runtime a
terminal, the executable plays until one player holds **all** the chips and names
that player the winner. Chips are modelled as an integer `stack` per player (not
a resource-zone subsystem); the total is invariant. The whole hand runs in the
DSL: the betting on the kernel `round` in **priority order** (each turn re-scans
the seat order from the leader and offers the first still-pending player, so
after a raise re-opens earlier seats action returns to the earliest owing seat),
and the showdown as plain statements — a contested hand reveals the contenders'
hole cards, each entrant collects its side-pot share via `holdem_pot_share(p)`,
and the hands leave play to the muck.

Two stdlib primitives, both pure reads. `holdem_pot_share` is the side-pot query
(the committed-total layering, odd chip to the first winner in seat order,
uncalled remainder to the best contender). `holdem_next_entrant` is the seat-ring
skip — the same shape as Coup's `coup_next_in_game` — and both the button's own
rotation and the blinds go through it. Stepping the button along the LIVE ring
rather than rotating it through every physical seat is what keeps the rotation
strict: map dead seats forward instead and, heads-up, one survivor takes the
button on two hands of every three. The poker evaluator behind the settlement is
shared with Seven-Card Stud (`cardlang/runtime/poker.py`) and unit-tested: which
cards a player has available is a property of the game, how five of them compare
is not.

The betting state splits two ways. What Hold'em touches it declares itself
(`bet_to_match`, `raises`, `raise_cap`, per-player `bet_by`/`folded`/`committed`);
the pure intra-street bookkeeping — `acted`, and the street's `limit` — the
library *provides*, so Hold'em never names it and could not write it if it tried.
The `until` predicate closes a street when no live player still owes or has yet
to act (or one lone contender remains, already matched).

Four of the five betting move types are not Hold'em's own. `uses poker_betting`
imports them — `check`, `bet`, `call`, `raise` and the `can_act`/`owes`/`pending`
ring predicates — from the family library shared with Kuhn, Leduc and Stud
([poker_betting](../libraries/poker_betting.cardlang),
[decisions.md](../decisions.md) "Family libraries"). Hold'em's own contribution
is `fold`, which mucks the folder's hole cards unseen — as in Kuhn and Leduc, and
unlike Stud, whose fold mucks upcards opponents were already watching — and the
`raise_cap` of 4 it declares as required state, where Stud declares 3 and Leduc
2. `raise_cap` counts aggressive actions *including* the opening bet, so 4 is
Pagat's "one bet plus three raises".

Hold'em is the family library's first consumer whose street shape **differs**
from Stud's. Stud opens every street with no standing bet; Hold'em opens pre-flop
with the blinds already posted, and its action order is *positional* rather than
derived from the visible cards. Both fit `open_street(<size>)` followed by a
forced post — the pattern Stud's bring-in established — so the library needed no
change to take a fourth consumer of a new shape.

**Simplifications.** No-limit and pot-limit betting are out (fixed limit only —
that is a parameterization of the betting round, not a structural change). The
"show one, show all" showdown rule is not modelled: every contender's hole cards
are revealed at a contested showdown. That rule is a per-observer move-level
projection override, which the language does not yet have — see
[open-questions/move-level-visibility.md](../open-questions/move-level-visibility.md),
whose witness this game is.

```
game Holdem {

  uses poker_betting

  players: 3
  direction: clockwise
  max_length: 30000

  cards: standard52
  ranking: aces high

  zones {
    deck          : Deck
    hole[player]  : Hand<player>           // the two private cards
    board         : Discard                // the community cards
    shown[player] : PublicHand<player>     // the showdown reveal
    muck          : Muck
    burn          : Burn
  }

  state {
    stack[player] : Integer = 100           // chips; total invariant, winner holds all
  }

  phase hand_sequence repeat until (number of players where stack[player] > 0) <= 1 {
    state { dealer : Player = 0 }
    before_each { move all cards to deck  shuffle deck }

    phase play {
      state {
        in_hand[player] : Boolean = false   committed[player] : Integer = 0
        folded[player]  : Boolean = false   bet_by[player]    : Integer = 0
        bet_to_match : Integer = 0          raises : Integer = 0
        raise_cap : Integer = 4            // one bet plus three raises
        button : Player = 0                 big_blind : Player = 0
      }

      for each player p: in_hand[p] := stack[p] > 0
      // Step the button along the LIVE ring: rotating through every physical
      // seat and mapping dead ones forward would give the same survivor the
      // button on two heads-up hands of every three.
      dealer := holdem_next_entrant(dealer offset_by left)
      button := dealer

      // Heads-up reverses the blinds: the button posts the small blind. Taking
      // the big blind as "the next entrant after the small blind" covers both
      // cases, so only the small blind needs the conditional.
      let small_blind = if (number of players where in_hand[player]) is 2
                          then button
                          else holdem_next_entrant(button offset_by left)
      big_blind := holdem_next_entrant(small_blind offset_by left)

      // The blinds post AFTER the street is opened, so opening does not clear
      // them; the big blind stands as the street's opening bet.
      run open_street(5)
      // ... post 2 from small_blind and 5 from big_blind (partial when short) ...
      bet_to_match := 5   raises := 1

      deal 1 card from deck to burn
      for each player p: if in_hand[p] { deal 2 cards from deck to hole[p] }

      // Pre-flop, from the big blind's left. The guard is the round's own
      // `until` terminator negated — a plain "two can act" test would deal the
      // hand out around a lone live player who still owes the blind.
      if (number of players where pending(player)) > 0
         and ((number of players where can_act(player)) > 1
              or (number of players where can_act(player) and owes(player)) > 0) {
        round offering [check, bet, call, fold, raise]
              from holdem_next_entrant(big_blind offset_by left)
              over players where pending(player)
              order priority
              until (number of players where pending(player)) is 0
                 or ((number of players where can_act(player)) <= 1
                     and (number of players where can_act(player) and owes(player)) is 0)
      }
      // ... flop / turn / river: three flat `if (contenders > 1) { ... }` blocks — a
      // burn + the street's cards to `board`, then `run open_street(5 / 10 / 10)` and
      // the same betting round `from holdem_next_entrant(button offset_by left)`. The
      // contender count is monotonic, so the flat guards short-circuit exactly as
      // nesting would (see holdem.cardlang).

      // Showdown — RNG-free, decision-free.
      if (number of players where in_hand[player] and not folded[player]) > 1 {
        for each player p: if in_hand[p] and not folded[p] {
          move all cards from hole[p] to shown[p]
        }
      }
      for each player p: if in_hand[p] { stack[p] := stack[p] + holdem_pot_share(p) }
      for each player p: if in_hand[p] {
        move all cards from hole[p] to muck
        move all cards from shown[p] to muck
      }
      move all cards from board to muck
    }
  }

  winner: highest stack
}

// Hold'em's own betting move; the folded hand mucks unseen.
move_type fold {
  when: bet_to_match > bet_by[actor]
  effect { folded[actor] := true  move all cards from hole[actor] to muck }
}
```
