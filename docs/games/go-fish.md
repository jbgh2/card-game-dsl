# Go Fish

The companion formal file is [go-fish.cardlang](go-fish.cardlang); this is the
readable twin. Go Fish is a collect-the-set game for four players on a
standard 52-card deck: on your turn you publicly ask a named opponent for a
named rank you already hold, hoping to collect **books** — all four cards of
a rank — before your hand empties or the stock runs out. Suit never matters
here, only rank does. It is played as a single game — deal once, play to the
finish, most books wins — with no multi-hand match structure to accumulate a
score across. Pagat allows 3–6 players (2 with 7 cards each); this corpus
entry fixes **four**, five cards each, the shape that gives every ask a real
choice of both target and rank. Source:
[Pagat](https://www.pagat.com/quartet/gofish.html).

Setup and play:

- **Deal.** Shuffle the deck and deal 5 cards to each of the four hands; the
  rest sit face down as the **stock**. (Edge case, resolved the same way it
  is during play: if a hand's opening 5 cards happen to include all four
  cards of one rank, that book is shown to the table and set aside before
  the first turn.)
- **A turn.** Someone is designated to go first (seat 0). On your turn you
  name another player and a rank — out loud, in public — that you currently
  hold at least one card of. You cannot name yourself, and you cannot name a
  rank you don't hold; both are illegal asks, not just bad ones.
  - **A hit.** If the named player holds any cards of that rank, they must
    hand over **all** of them to you, and you go again — a brand-new ask,
    naming anyone and any rank you now hold, not a repeat of the one you
    just made.
  - **A miss — "go fish".** If the named player holds none of that rank, you
    draw the top card of the stock. If it's the rank you asked for, you show
    it to the table and go again. Otherwise you keep it — privately, no one
    else learns what it is — and the turn passes to the next player on your
    left.
- **Books.** The instant your hand contains all four cards of some rank —
  however it got there: a hit, a stock draw, or the opening deal — it is
  shown to the table and set aside as a completed book. Booked cards are out
  of play for the rest of the game; they no longer count as being "in your
  hand" for any future ask.
- **Game end.** The game ends immediately, even mid-chain, the moment any
  player's hand is empty or the stock runs out — checked after every single
  ask, including ones that would normally earn the asker another turn. So if
  an ask happens to empty a hand (the named player's, by giving away their
  last cards on a hit; the asker's, by completing a book that was their
  whole hand) or draws the stock's last card, the game is over right there —
  no bonus final ask, and no refill for an emptied hand.
- **Winner.** Whoever holds the most books when the game ends.

The turn structure runs as one kernel loop: `phase play` repeats `offer to
current_player one of [ask]` until a hand is empty or the stock is, and
every rule of the turn — the give-all-matching transfer, the stock draw,
book completion — lives inside `ask`'s single `effect` block, written in the
existing closed movement verbs (`move`, `draw`). "Go again" needs no special
control flow: nothing in a hit branch or a matching-draw branch ever
reassigns `current_player`, so the next loop iteration simply offers the
same actor another ask. The one branch that *does* reassign it —
`current_player := actor offset_by left` — is the non-matching draw, handing
the turn on exactly where Pagat says it should. Book completion is one guard
("does this hand now contain all four of some rank?"), reused twice: once
at the end of every `ask` (covering hits and both kinds of draw) and once
for every hand in `phase setup` (covering an opening quad that no later
check would ever revisit). The `ranking:` declaration exists only to name
the 13 valid `Rank` values `ask`'s second parameter enumerates over — Go Fish
never compares rank order; there's no trick-taking here, only rank
*identity*.

Zones and visibility: `hand[player]` is a private `Hand<player>` — its owner
sees every card, everyone else only its size. `book[player]` is a public
`PlayerPile<player>`: once four cards of a rank land there they are shown
and stay visible to the whole table, matching Pagat's "must be shown and
discarded." `deck` is a `Deck`, a face-down ordered stock — its remaining
count is public, its contents are not. `book_count[player]`, the tally the
game is scored on, is ordinary public state: only zone *contents* are ever
hidden in this language, state never is.

**The information-set point.** Go Fish is the corpus's witness for
**declared parameter domains**
([decisions.md](../decisions.md) "Declared parameter domains").
`ask(target: Player, rank: Rank)` ranges, statically, over all four seats
and all 13 ranks — a fixed 4 × 13 = 52-entry cross-product, exactly the
constant action-space size OpenSpiel needs declared up front. Per decision,
the guards ("not yourself", "a rank you currently hold") mask that fixed 52
down to whichever pairs are actually legal for whoever is on turn — at most
3 targets, times however many distinct ranks are in their hand right now —
and the kernel's `offer` enumerates that guard-filtered cross-product as one
flat menu, the same way it already does for a single `Suit` parameter.

What earns the ask its corpus slot is what its legality *implies*. Because
the guard is "you may only ask for a rank you hold," the public announcement
of the chosen `(target, rank)` pair is itself proof that the asker holds at
least one card of that rank — every observer's derived information set
gains that fact the instant the ask is made, not because any code says so,
but because it falls straight out of a public move whose own legality
already required it. The rest of the turn stays just as disciplined: a
hit's transfer is never seen card-by-card by a bystander, because
`hand[player]` shows every card to its owner and only a bare count to
everyone else, so a bystander derives "the asker now holds N more of rank
R" from the public ask plus the public size change on both hands, never
from watching the cards move. Even the stock draw needs no special-casing
to stay honest: whether the same player is asked again next is public
(`current_player` is state, and state is always public in this language),
and "go again" only follows a hit or a matching draw, so a bystander can
always tell whether a fish draw matched without ever being shown the card
itself. This is the derived-information-set model the whole language is
built on: what a player knows falls out of who can see what, never out of
hand-authored "and now player X learns Y" logic.

```
game GoFish {

  players: 4
  direction: clockwise
  max_length: 600

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck         : Deck                 // face-down stock
    hand[player] : Hand<player>         // private hand
    book[player] : PlayerPile<player>   // completed books, shown then set aside
  }

  state {
    current_player     : Player  = 0
    book_count[player] : Integer = 0
  }

  phase setup {
    shuffle deck
    deal 5 cards from deck to each hand
    for each player p:
      if any rank where rank_count(p, rank) is 4 {
        move all cards from hand[p]
             where rank_count(p, card.rank) is 4
             to book[p]
        book_count[p] += 1
      }
    current_player := 0
  }

  phase play {
    repeat until (deck is empty) or (any player where hand[player] is empty) {
      offer to current_player one of [ask]
    }
  }

  winner: highest book_count
}

// The turn: name a live opponent and a rank you hold; the ask is public.
move_type ask(target : Player, rank : Rank) {
  when: target is not actor
        and (any card in hand[actor] where card.rank is rank)
  effect {
    let target_holds = number of cards in hand[target] where card.rank is rank
    if target_holds > 0 {
      move all cards from hand[target] where card.rank is rank to hand[actor]
      // A hit: current_player unchanged, so the next iteration offers to the same
      // player — "you go again".
    } else {
      let before = number of cards in hand[actor] where card.rank is rank
      draw 1 card from deck to hand[actor]
      let after = number of cards in hand[actor] where card.rank is rank
      if after is before {                 // drew a non-matching card: pass left
        current_player := actor offset_by left
      }
      // drew the asked rank: go again (current_player unchanged)
    }
    // Book completion (from a transfer or a draw): set aside four of a rank.
    if any rank where rank_count(actor, rank) is 4 {
      move all cards from hand[actor]
           where rank_count(actor, card.rank) is 4
           to book[actor]
      book_count[actor] += 1
    }
  }
}

// How many cards of a rank a hand holds. Factored as a function so the book
// predicates can count the OUTER card's rank: passing `card.rank` in as an
// argument avoids nesting two card queries (the inner one would rebind
// `card` and shadow the outer binder).
function rank_count(p : Player, r : Rank) = number of cards in hand[p] where card.rank is r

```
