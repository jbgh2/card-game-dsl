# Heads-up Texas Hold'em

The companion formal file is [holdem-heads-up.cardlang](holdem-heads-up.cardlang);
this is the readable twin. **Heads-up (two-player) fixed-limit Texas Hold'em,
one hand** — blinds 1/2, bet sizes 2/2/4/4, four aggressive actions per street.
Source: [Pagat](https://www.pagat.com/poker/variants/texasholdem.html), with one
deliberate deviation recorded under "The raise cap" below.

This is the corpus's **second Hold'em**. [holdem.md](holdem.md) is the
three-handed cash game played on until one player holds every chip; this is the
two-handed single hand — the unit the heads-up-limit literature measures on, and
the third rung of the poker family after [Kuhn](kuhn-poker.md) and
[Leduc](leduc-poker.md).

The hand:

1. **Blinds.** Heads-up the blinds are **reversed**: the button posts the
   **small blind** (1) and the other seat the **big blind** (2). These are
   forced bets, not decisions.
2. **Deal.** Burn one card, then two face-down **hole cards** each. (Pagat burns
   here as well as before each community stage — four burns a hand, where common
   casino practice burns only three.)
3. **Pre-flop** betting, **begun by the button** — heads-up the button is the
   small blind, so it acts first before the flop and last on every street after
   it. A player may check, bet, call, raise (capped), or fold.
4. **The flop** — burn one, deal three face-up **community cards** — then a
   betting round begun by the big blind.
5. **The turn** — burn one, deal one — then a betting round. Bets double here
   (2 becomes 4).
6. **The river** — burn one, deal one — then the last betting round.
7. **Showdown** — each player makes their best five-card poker hand from the
   seven available (their two hole cards plus the five community cards), and the
   best hand wins the pot; equal hands split it. A hand may use both hole cards,
   one, or none — "playing the board".

Then the game ends. The score is `net`, the hand's chip delta against the
100-chip starting stack — exactly Leduc's scoring, and exactly OpenSpiel's
`money_[player] - kStartingMoney`.

## The raise cap — and the one deviation from Pagat

Pagat caps a fixed-limit betting round at "one bet plus three (sometimes four)
raises", and then says: *if a round begins with only two active players, there
is no limit on the number of raises.* [holdem.md](holdem.md) implements exactly
that — three-handed, a street that narrows to two goes uncapped.

**This game caps every street at four aggressive actions instead.** That is the
ruleset of the standard heads-up-limit benchmark (the ACPC / Cepheus
configuration), and it is what makes the hand a bounded, comparable unit. A
capped heads-up game and an uncapped one are different games; this file is the
capped one and pins it rather than inheriting the ambiguity.

"Four" alone is ambiguous, so here is the table it means. `raise_cap` counts
**aggressions including the opening bet**, so `raise_cap : 4` is four bets on
the street, not four raises on top of one:

| street | opening aggression | further raises | bets | `bet_to_match` caps at |
|---|---|---|---|---|
| pre-flop | the big blind | 3 | 4 | 8 |
| flop | a bet | 3 | 4 | 8 |
| turn | a bet | 3 | 4 | 16 |
| river | a bet | 3 | 4 | 16 |

`tests/test_playout_holdem_heads_up.py` drives each street to its cap and
asserts `raise` has left the legal set, so the table is pinned rather than
asserted in prose.

## Nobody is ever all-in, and that is arithmetic

The four caps sum to 8 + 8 + 16 + 16 = **48**, against a 100-chip stack. So no
seat can be short, `can_act`'s `stack[p] > 0` never gates, and **no side pot can
form**. Two simplifications follow, both of which three-handed Hold'em cannot
make: the blinds are written as flat subtractions rather than short-stack
conditionals, and the pre-flop street needs no entry guard for a lone player who
still owes a blind. Neither is a tidy-up — each rests on that 48-chip bound,
which is why a playout invariant checks it rather than the reader.

## What the language does here

The community `board` is a `Discard`, the library zone type whose contents are
visible to all: its publicness is a property of its **type** and needs no rule,
so the same five cards read into both players' hand evaluations while leaking
nothing. Leduc's single face-up card and three-handed Hold'em's five already use
it; this is the two-player case.

Everything else is the family library. `check`, `bet`, `call`, `raise` and the
`can_act`/`owes`/`pending` ring predicates come from
[poker_betting](../libraries/poker_betting.cardlang), shared with Kuhn, Leduc,
Seven-Card Stud and three-handed Hold'em. `fold` is the game's own, because it
touches the game's zones — the folded hand mucks unseen, so a fold reveals
nothing.

The showdown calls one primitive, `holdem_heads_up_pot_share`, which holds no
arithmetic: the payout layering is family-wide (`cardlang/runtime/poker.py`) and
the "hole cards plus the shared board" fact is Hold'em-wide
(`cardlang/runtime/holdem.py`). It exists as its own name only because a
primitive module binds one declared-reads row, keyed on (module, game file) —
see issue #232.

```
game HoldemHeadsUp {

  uses poker_betting

  players: 2
  direction: clockwise
  max_length: 200

  cards: standard52
  ranking: aces high

  zones {
    deck          : Deck
    hole[player]  : Hand<player>           // the two private cards
    board         : Discard                // the community cards
    shown[player] : PublicHand<player>     // the showdown reveal
    muck          : Muck                   // folded / spent cards
    burn          : Burn                   // one burned card before each deal
  }

  state {
    stack[player]     : Integer = 100      // ample: a hand costs at most 48
    net[player]       : Integer = 0        // terminal score: chips won or lost
    in_hand[player]   : Boolean = true     // the showdown primitive's declared read

    // The poker_betting `requires` contract.
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 4        // four aggressions per street, every street

    // Heads-up positions, fixed for the single hand: the button posts the
    // small blind and acts first pre-flop; the big blind opens every later
    // street. Public, so state rather than a hidden binding.
    button            : Player = 0
    big_blind         : Player = 1
  }

  phase deal {
    shuffle deck
    // The blinds post AFTER the street is opened, so opening does not clear
    // them; the big blind stands as the street's opening aggression. Neither
    // post can be partial (the 48-chip bound).
    run open_street(2)
    bet_by[button] := 1
    stack[button] := stack[button] - 1
    committed[button] := committed[button] + 1
    bet_by[big_blind] := 2
    stack[big_blind] := stack[big_blind] - 2
    committed[big_blind] := committed[big_blind] + 2
    bet_to_match := 2
    raises := 1

    deal 1 card from deck to burn
    // Two passes of one card: the deal goes round the table one at a time.
    for each player p: deal 1 card from deck to hole[p]
    for each player p: deal 1 card from deck to hole[p]
  }

  // Pre-flop, opened by the button. No entry guard, unlike three-handed
  // Hold'em's: nobody can be all-in here, so both seats are pending on entry.
  phase preflop {
    round offering [check, bet, call, fold, raise] from button
          over players where pending(player)
          order priority
          until (number of players where pending(player)) is 0
             or ((number of players where can_act(player)) <= 1
                 and (number of players where can_act(player) and owes(player)) is 0)
  }

  // Flop, turn and river: burn, deal, then a betting round opened by the big
  // blind. `folded` only grows, so the flat guards short-circuit exactly as
  // nesting would. Bets double from the turn on.
  phase flop {
    if (number of players where not folded[player]) > 1 {
      deal 1 card from deck to burn
      deal 3 cards from deck to board
      run open_street(2)
      round offering [check, bet, call, fold, raise] from big_blind
            over players where pending(player)
            order priority
            until (number of players where pending(player)) is 0
               or ((number of players where can_act(player)) <= 1
                   and (number of players where can_act(player) and owes(player)) is 0)
    }
  }

  phase turn {
    if (number of players where not folded[player]) > 1 {
      deal 1 card from deck to burn
      deal 1 card from deck to board
      run open_street(4)
      round offering [check, bet, call, fold, raise] from big_blind
            over players where pending(player)
            order priority
            until (number of players where pending(player)) is 0
               or ((number of players where can_act(player)) <= 1
                   and (number of players where can_act(player) and owes(player)) is 0)
    }
  }

  phase river {
    if (number of players where not folded[player]) > 1 {
      deal 1 card from deck to burn
      deal 1 card from deck to board
      run open_street(4)
      round offering [check, bet, call, fold, raise] from big_blind
            over players where pending(player)
            order priority
            until (number of players where pending(player)) is 0
               or ((number of players where can_act(player)) <= 1
                   and (number of players where can_act(player) and owes(player)) is 0)
    }
  }

  // Showdown — RNG-free, decision-free. A contested hand reveals both holdings
  // (the movement event carries both identities); a hand that ended in a fold
  // reveals nothing, so a folded holding stays unknowable even in hindsight.
  phase showdown {
    if (number of players where not folded[player]) > 1 {
      for each player p: if not folded[p] {
        move all cards from hole[p] to shown[p]
      }
    }
    for each player p: stack[p] := stack[p] + holdem_heads_up_pot_share(p)
    for each player p: move all cards from hole[p] to muck
    for each player p: move all cards from shown[p] to muck
    move all cards from board to muck
    for each player p: net[p] := stack[p] - 100
  }

  winner: highest net
}

// The game's own betting move; the folded hand mucks unseen.
move_type fold {
  when: bet_to_match > bet_by[actor]
  effect {
    folded[actor] := true
    move all cards from hole[actor] to muck
  }
}
```
