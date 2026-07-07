# Big Two

The companion formal file is [big-two.cardlang](big-two.cardlang); this is the
readable twin. A four-player **climbing / shedding** game (also called Deuces or
Choh Dai Di) on the standard 52-card deck. The aim is to be the first to play out
your whole hand; the others lose penalty points for the cards they are caught
with. Lowest cumulative penalty wins. Rules: [Pagat](https://www.pagat.com/climbing/bigtwo.html)
(basic game).

**Card order.** Two rank orders coexist, which is the heart of the game:

- For **singles, pairs, triples, four-of-a-kinds, and full houses** (and a
  flush's top card), the **2 is the highest rank**, then A, K, Q, J, 10, …, down
  to the 3. **Suits break every tie**, high to low: **♠ > ♥ > ♣ > ♦** (a single
  52-card deck, so 7♠ beats 7♥).
- For **straights**, ranks run in **natural** order: the ace is high in
  10-J-Q-K-A (the highest straight) and low in A-2-3-4-5 (the *wheel*, the lowest
  straight). There is **no wrap-around** — J-Q-K-A-2 is not a straight, and the 2
  is just an ordinary low card here.

Each hand:

1. Deal **13 cards** to each player. On the **first hand of the match** the holder
   of the **3♦** leads and must include it in the opening combination; on every
   later hand the **winner of the previous hand** leads, with any combination.
2. Players **climb**: a play must have the **same number of cards** as the
   standing combination and **beat** it, or you **pass**. Passing does not lock
   you out — you may play again when the turn comes back around. A trick ends when
   the action returns to the last player who played (everyone else passed); that
   player then **leads the next trick** with anything.
3. The combinations, by size:
   - **Singles** — one card; **pairs** — two of a rank; **triples** — three of a
     rank. A higher pair/triple is one of a higher rank (suit breaks a pair tie).
   - **Five-card hands**, weakest type to strongest: **straight** < **flush**
     (five of a suit; a higher suit beats a lower one outright, then top card) <
     **full house** (ranked by its triple) < **four of a kind** (all four of a
     rank **plus a fifth kicker card**, ranked by the four) < **straight flush**
     (five in sequence and suit). A stronger *type* beats a weaker one of the same
     size, so any flush beats any straight, any full house beats any flush, and so
     on. There is **no four-card play** and no bombs — a single only follows a
     single, a five-card hand only a five-card hand.
4. The hand ends the **instant a player empties their hand** — they win it. The
   others score **penalty points** for the cards still in hand: **1 per card** for
   nine or fewer, **2 per card** for ten–twelve, **3 per card** for a full
   thirteen (39). The winner scores 0. The match ends when a player's cumulative
   penalty reaches 100; the **lowest** total wins.

The hand runs on the kernel **`round climb`** construct: one combination-climbing
trick per round, with the combination engine named as the game-local stdlib
queries `bigtwo_lead_options` (lead candidates, 3♦-filtered on the opening) and
`bigtwo_follows` (legal follows). The climbing loop, the pile routing, the
shed-out finish, and penalty scoring are DSL. Scope reductions (random play): each
pair/triple is offered as its single strongest representative per rank (highest
suits), and each five-card type as its strongest representative (the top five of a
suit for a flush, the highest top card for a straight); none of these change which
combinations a hand can legally beat. One corollary at the **opening 3♦ lead**: the
single 3♦ is always offered, but a multi-card opening whose strongest representative
omits the 3♦ (a pair or triple of 3s — represented by its two highest suits — or a
straight/flush built on a higher-suit 3) is not. The single 3♦ guarantees a legal
opening; exhaustive opening coverage would require dropping the representative
reduction (full per-suit enumeration), a global change deferred for random play.
Match-doubling surcharges (for holding 2s, or a 13-card blitz) are omitted — the
basic 1/2/3-per-card penalty only. The turn
direction (clockwise) is a fixed choice; Pagat leaves it to the table.

```
game BigTwo {

  players: 4
  direction: clockwise
  max_length: 25000

  cards: standard52

  zones {
    deck         : Deck
    hand[player] : Hand<player>
    trick_pile   : TrickPile          // the climbing trick in progress
    discard      : Discard            // spent tricks (no capture in Big Two)
  }

  state {
    score[player] : Integer = 0       // cumulative penalty points (lower is better)
    winner_seat   : Player? = none    // who shed out last hand; leads the next one
    opened        : Boolean = false   // has the opening (3♦) lead been played?
    leader        : Player? = none    // who leads the current trick
  }

  phase hand_sequence repeats until (any player p: score[p] >= 100) {
    before_each {
      move all cards to deck
      shuffle deck
      deal 13 cards from deck to each hand
      leader := (if winner_seat is none then bigtwo_first_leader() else winner_seat)
    }

    phase play {
      legal_moves: [play_combination]
      repeat until (any player p: hand[p] is empty) {
        round climb play_combination from leader
              over players where hand[player] is not empty
              source hand into trick_pile
              combinations bigtwo_lead_options follows bigtwo_follows
              until (any player p: hand[p] is empty)
        opened := true
        move all cards from trick_pile to discard
        leader := outcome
      }
    }

    phase scoring {
      winner_seat := leader
      for each player p:
        if hand[p] is not empty {
          score[p] += bigtwo_penalty(count over hand[p] as c: true)
        }
    }
  }

  winner: lowest score
}

function bigtwo_penalty(n : Integer) = if n <= 9 then n elif n <= 12 then 2 * n else 3 * n
```
