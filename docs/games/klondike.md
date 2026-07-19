# Klondike

The companion formal file is [klondike.cardlang](klondike.cardlang); this is
the readable twin. Klondike is THE solitaire: one player, a standard 52-card
deck, seven tableau columns, four foundations, and a stock cycled through a
waste pile. **Variant pinned here: deal 1 (one stock card turned at a time),
unlimited redeals, Kings only to empty columns, partial-run moves allowed,
no worrying back (a card on a foundation never comes down), and a newly
exposed face-down card is flipped face up immediately.** Pagat has no
standalone Klondike page (its patience section links out to solitaire
sites); this pin follows the classic rules Pagat's Klondike-derived entries
(e.g. [Double Solitaire](https://www.pagat.com/patience/double.html))
assume.

Setup and play:

- **Layout.** Shuffle. Deal seven columns left to right: column 1 gets one
  card, column 2 two, up to column 7 with seven — all face down — then flip
  each column's top card face up (28 cards). The remaining 24 cards form
  the face-down **stock**; beside it sits the (initially empty) face-up
  **waste**.
- **Goal.** Build the four **foundations** — one per suit — from ace up to
  king. All 52 cards home wins.
- **A turn.** Any one of:
  - **Turn the stock.** Flip the top stock card face up onto the waste.
    Only the waste's top card is playable.
  - **Redeal.** When the stock is empty, turn the whole waste over —
    without shuffling — to form the new stock. Unlimited redeals; each
    pass repeats the last pass's order (minus whatever was played).
  - **To a foundation.** Move the waste's top card, or any column's top
    face-up card, onto its suit's foundation if it is the next rank up
    (ace first). Foundation cards never come back down.
  - **Build on a column.** Move the waste's top card onto a column whose
    top face-up card is one rank higher and the opposite color (red on
    black, black on red).
  - **Move a run.** Take any face-up card in a column *together with every
    card on top of it* and move the whole unit onto another column whose
    top card is one rank higher than the unit's bottom card and the
    opposite color. Partial runs may move (you may split a run anywhere).
  - **Fill a space.** An empty column may be filled only by a King (or a
    run whose bottom card is a King), from the waste or another column.
  - **Give up.** The player may abandon the game at any time; the score
    stands at the number of cards on the foundations.
- **The flip.** The instant a column's face-up cards are all gone and face-
  down cards remain, the top face-down card is flipped face up.
- **End.** The game is won when all 52 cards are on the foundations, and
  otherwise ends when the player abandons it.

How the DSL says it (decisions.md "Position domains and positional zones"):
the seven columns are a declared position domain (`column : 1..7`), and each
column is **two stacked zone families** — `tableau_down[column]`, a
`HiddenStack` whose contents project as a bare count, under
`tableau_up[column]`, a `Cascade` whose contents (and order) are public.
The flip is an ordinary `draw` from the hidden stack to the cascade, and
its observation event — a count on the source side, the card's identity on
the destination side — *is* the reveal: nothing about the flip is
hand-authored, and a face-down card's identity is non-observable until its
flip event (proven in `tests/openspiel_ready/test_klondike.py`, along with
the chance-hidden swap partition). The run move is the existing filtered
movement: a cascade's face-up run is always a strictly-descending
alternating sequence, so "this card and everything above it" is denoted by
a rank filter against the target's top card. The stock cycle needs no
shuffle: the dealt take is FIFO, so `move all cards from waste to deck`
reproduces the physical turn-over exactly, and after one full pass the
player's observation history pins the stock's order — derived knowledge,
not a rules gap.

```
// Klondike — one player, standard 52-card deck. Variant pinned: deal 1,
// unlimited redeals, Kings only to empty columns, partial-run moves allowed,
// no worrying back (foundation cards never come down), mandatory immediate
// flip. Pagat has no standalone Klondike page (its patience section links
// out); this pin follows the classic rules its Klondike-derived entries
// (pagat.com/patience/double.html) assume.
//
// This is the corpus witness for POSITION DOMAINS (decisions.md "Position
// domains and positional zones"): seven tableau columns as position-indexed
// zone families, each column TWO stacked zones — a face-down HiddenStack
// under a face-up Cascade — so the flip is an ordinary kernel movement whose
// observation event (count from the hidden side, identity at the open side)
// IS the derived reveal. Hidden information here is chance-hidden (the
// shuffle), not opponent-hidden: the sole player's information set is exactly
// the exposed cards + counts + their own observation history.
//
// Foundations are four position-indexed piles under a fixed suit layout
// (clubs=1, diamonds=2, hearts=3, spades=4 — a presentational convention,
// rule-equivalent: each foundation builds one suit A up to K, and the suit a
// pile takes is determined the moment its ace lands). `ranking: aces low`
// gives rank_value A=0 .. K=12, the foundation/tableau arithmetic scale.

game Klondike {

  players: 1
  direction: clockwise
  max_length: 600

  cards: standard52
  ranking: aces low

  positions {
    column : 1..7    // the seven tableau columns, left to right
    fslot  : 1..4    // the four foundation piles (clubs, diamonds, hearts, spades)
  }

  zones {
    deck                  : Deck                  // the face-down stock
    waste                 : Discard               // the face-up waste pile
    tableau_down[column]  : HiddenStack<column>   // a column's face-down cards
    tableau_up[column]    : Cascade<column>       // a column's face-up run
    foundation[fslot]     : Foundation<fslot>     // ace up to king, one suit each
  }

  state {
    resigned           : Boolean = false
    home_count[player] : Integer = 0    // cards sent to the foundations (the score)
  }

  // Column c is dealt c cards face down, then its top card is flipped: the
  // flip is the draw from the hidden stack to the open cascade, and its
  // observation event is what shows the player the seven exposed cards.
  phase setup {
    shuffle deck
    deal 1 card  from deck to tableau_down[1]
    deal 2 cards from deck to tableau_down[2]
    deal 3 cards from deck to tableau_down[3]
    deal 4 cards from deck to tableau_down[4]
    deal 5 cards from deck to tableau_down[5]
    deal 6 cards from deck to tableau_down[6]
    deal 7 cards from deck to tableau_down[7]
    draw 1 card from tableau_down[1] to tableau_up[1]
    draw 1 card from tableau_down[2] to tableau_up[2]
    draw 1 card from tableau_down[3] to tableau_up[3]
    draw 1 card from tableau_down[4] to tableau_up[4]
    draw 1 card from tableau_down[5] to tableau_up[5]
    draw 1 card from tableau_down[6] to tableau_up[6]
    draw 1 card from tableau_down[7] to tableau_up[7]
  }

  // One player, one decision per turn, until the game is won or abandoned.
  // `resign` is always legal, so the offer can never be empty; a solitaire
  // player may abandon at any point, and under random play that is also what
  // bounds the game length.
  phase play {
    turns t from 0 over all players
          until resigned or (any player where home_count[player] is 52) {
      offer to t one of [draw_stock, redeal, waste_to_foundation,
                         waste_to_tableau, tableau_to_foundation,
                         tableau_to_tableau, resign]
    }
  }

  winner: highest home_count
}

// The fixed foundation layout: which pile a suit builds on.
function fpile(s : Suit) = if s is clubs then 1 elif s is diamonds then 2 elif s is hearts then 3 else 4

// Card color, for the alternating tableau build.
function red(s : Suit) = (s is hearts) or (s is diamonds)

// May c be placed on t in the tableau? One rank lower, opposite color.
function fits_down(c : Card, t : Card) = (rank_value(c) is rank_value(t) - 1) and (red(c.suit) is not red(t.suit))

// May c go to its foundation next? Its pile's ace first, then ascending.
function home_ok(c : Card) = if foundation[fpile(c.suit)] is empty then rank_value(c) is 0 else rank_value(c) is rank_value(top_of(foundation[fpile(c.suit)])) + 1

// Turn one stock card face up onto the waste (deal-1 variant).
move_type draw_stock {
  when: deck is not empty
  effect {
    draw 1 card from deck to waste
  }
}

// Stock exhausted: turn the waste over, unshuffled, to form the new stock.
// The dealt take is FIFO (decisions.md, sequence orientation), so the new
// pass repeats the last pass's order — exactly the physical turn-over. The
// player has seen every card go by, so after one full pass the stock's
// order is derived knowledge in their observation history; no shuffle, no
// new chance.
move_type redeal {
  when: (deck is empty) and (waste is not empty)
  effect {
    move all cards from waste to deck
  }
}

// The top waste card to its foundation.
move_type waste_to_foundation {
  when: (waste is not empty) and home_ok(top_of(waste))
  effect {
    let c = top_of(waste)
    move one card from waste where card is c to foundation[fpile(c.suit)]
    home_count[actor] += 1
  }
}

// The top waste card onto a column: onto a fitting face-up top card, or a
// King onto an empty column. The flip invariant (a column's face-up part is
// empty only when its face-down part is too) makes `tableau_up[dst] is
// empty` the whole emptiness test.
move_type waste_to_tableau(dst : column) {
  when: (waste is not empty)
        and (if tableau_up[dst] is empty
             then top_of(waste).rank is K
             else fits_down(top_of(waste), top_of(tableau_up[dst])))
  effect {
    let c = top_of(waste)
    move one card from waste where card is c to tableau_up[dst]
  }
}

// A column's top card to its foundation, flipping the newly exposed card
// if the face-up run empties.
move_type tableau_to_foundation(src : column) {
  when: (tableau_up[src] is not empty) and home_ok(top_of(tableau_up[src]))
  effect {
    let c = top_of(tableau_up[src])
    move one card from tableau_up[src] where card is c to foundation[fpile(c.suit)]
    home_count[actor] += 1
    if (tableau_up[src] is empty) and (tableau_down[src] is not empty) {
      draw 1 card from tableau_down[src] to tableau_up[src]
    }
  }
}

// Move a face-up run (a card and everything above it) between columns.
// Onto a non-empty column, the moving unit is determined by the target's
// top rank: the run's card one rank below it, opposite color, plus all
// cards above — denoted by the rank filter, because a cascade's face-up
// run is a strictly-descending alternating sequence (the run invariant,
// decisions.md "Position domains and positional zones"). Onto an empty
// column, only a King-based run may move, and it moves whole.
move_type tableau_to_tableau(src : column, dst : column) {
  when: (src is not dst)
        and (tableau_up[src] is not empty)
        and (if tableau_up[dst] is empty
             then bottom_of(tableau_up[src]).rank is K
             else (any card in tableau_up[src]
                   where fits_down(card, top_of(tableau_up[dst]))))
  effect {
    if tableau_up[dst] is empty {
      move all cards from tableau_up[src] to tableau_up[dst]
    } else {
      let v = rank_value(top_of(tableau_up[dst]))
      move all cards from tableau_up[src] where rank_value(card) < v to tableau_up[dst]
    }
    if (tableau_up[src] is empty) and (tableau_down[src] is not empty) {
      draw 1 card from tableau_down[src] to tableau_up[src]
    }
  }
}

// Abandon the game; the score stands at the cards already sent home.
move_type resign {
  effect {
    resigned := true
  }
}
```
