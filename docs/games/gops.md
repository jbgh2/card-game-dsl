# GOPS (Goofspiel)

The companion formal file is [gops.cardlang](gops.cardlang); this is the
readable twin. GOPS — the Game Of Pure Strategy — is a sealed-bid auction
game for **two players** using three suits of a standard 52-card deck: one
suit each to bid with, and a shuffled third suit as the prizes being bid on.
There are no tricks, no draws after the deal, and no hidden deal — every
card's location is public knowledge from the first round; the *only* secrets
in the whole game are the order of the face-down prize pile and each
player's not-yet-revealed bid. It is played as a single 13-round hand.
Source: [Pagat](https://www.pagat.com/misc/gops.html). This corpus entry
fixes the **tied-bid-discards-the-prize** variant (Pagat's main text instead
keeps a tied prize on offer, accumulating it into the next round's stake, and
records the discard rule as a variant): the discard rule is what OpenSpiel's
native `goofspiel` implements, and this file is deliberately configured to
mirror `goofspiel(players=2,num_cards=13,points_order=random)` so the two
implementations can be validated against each other trajectory by trajectory
(`tests/test_differential_gops.py`).

Setup and play:

- **Deal.** Split the deck by suit: player 0 takes all thirteen **clubs** as
  a bidding hand, player 1 all thirteen **spades**; the thirteen **diamonds**
  are shuffled face down as the prize pile; the hearts are removed from play
  entirely. Nothing about this deal is secret except the diamond order.
- **A round.** Turn the top diamond face up — this is the prize, worth its
  rank in points: Ace 1, spot cards face value, Jack 11, Queen 12, King 13
  (91 points in the pile). Each player then selects one card from their hand
  and places it face down as a **sealed bid**. Once both are committed, the
  bids are revealed simultaneously.
  - **Higher bid takes the prize** (Ace low, King high — the same A=1..K=13
    scale as the prize values). The winner banks the prize card's points.
  - **Equal bids discard the prize** — nobody scores it, and it is out of
    the game.
  - Either way, both bid cards are spent: they go face up to a common
    discard and are gone for good.
- **Game end.** After 13 rounds the hands are empty and the prize pile is
  exhausted. Whoever banked more prize points wins; equal totals are a draw.

Zones and visibility: `hand[player]` is a `Hand<player>` and `bid[player]` a
`HiddenPile<player>` — both show every card to their owner and only a bare
count to the opponent. That count-projection is what makes the bid *sealed*:
between your opponent's commit and the reveal, your information set contains
`bid[opp]=#1` and nothing more. `prize_deck` is a `FaceDownPile` (a count to
everyone — the undrawn prize order is the game's chance), while `prize`, the
`captured[player]` piles, and the common `discard` are fully public, and the
hearts sit in a `Muck` nobody observes. `prize_points[player]` is ordinary
public state, written only on the public resolution after the reveal — only
zone *contents* are ever hidden in this language, state never is.

**The information-set point.** GOPS is the corpus's witness for a **sealed
simultaneous decision**: a concealed commitment that is not a claim about a
hidden holding (Coup) or a hidden deal (every trick game) but a *choice*
kept secret for exactly one beat. The encoding is the doctrine's: the sealed
bid is **zone contents, never state**. Each round runs
`each player simultaneously: move chosen 1 card from hand[player] to
bid[player]` — the same construct as Hearts's pass — so the second player to
be serialized by the kernel decides against an information state that is
byte-identical whatever the first player committed (their log gains no
event; the bid zone projects as a count; the offered actions don't change).
Then `reveal one card from bid[0]` / `bid[1]` makes both bids public as
observation events, and everything downstream — the rank comparison, the
prize routing, the `prize_points` write — is plain public statements over
already-revealed information. No per-game observation rule exists anywhere:
the sealed phase falls out of `HiddenPile`'s declared projection, and the
open phase out of the `reveal` events plus public-zone movements. Because
the deal itself is public (each player's remaining bid cards are perfectly
deducible from the reveals), the derived information set is *almost* the
whole state — hidden in exactly two places, the prize order and the live
bid, which is precisely what makes the game pure strategy. The rank scale
needs no game-local primitive: under `ranking: aces low`,
the stdlib `rank_value` is 0 for the Ace up to 12 for the King — the bid
comparison directly, and the prize value as `rank_value + 1`.

```
game GOPS {

  players: 2
  direction: clockwise
  max_length: 200

  cards: standard52
  ranking: aces low

  zones {
    deck             : Deck                 // empty after setup
    dead             : Muck                 // the hearts, out of play
    prize_deck       : FaceDownPile         // the shuffled diamond suit
    prize            : Discard              // the face-up prize on offer this round
    hand[player]     : Hand<player>         // P0: clubs. P1: spades.
    bid[player]      : HiddenPile<player>   // this round's sealed bid
    captured[player] : PlayerPile<player>   // prizes won
    discard          : Discard              // spent bids + tied-away prizes
  }

  state {
    prize_points[player] : Integer = 0
  }

  phase setup {
    move all cards from deck where card.suit is clubs to hand[0]
    move all cards from deck where card.suit is spades to hand[1]
    move all cards from deck where card.suit is diamonds to prize_deck
    move all cards from deck to dead          // the hearts take no part
    shuffle prize_deck
  }

  phase play {
    repeat until prize_deck is empty {
      // Turn up the round's prize.
      move one card from prize_deck to prize

      // Sealed simultaneous bids: each player commits one card face down.
      each player simultaneously:
        move chosen 1 card from hand[player] to bid[player]

      // Both bids are revealed to everyone; all routing below is public.
      reveal one card from bid[0]
      reveal one card from bid[1]

      let b0 = sum of rank_value(card) over cards in bid[0]
      let b1 = sum of rank_value(card) over cards in bid[1]
      let pv = (sum of rank_value(card) over cards in prize) + 1   // A=1 .. K=13

      if b0 > b1 {
        prize_points[0] += pv
        move all cards from prize to captured[0]
      } else {
        if b1 > b0 {
          prize_points[1] += pv
          move all cards from prize to captured[1]
        } else {
          // Equal bids: the prize is discarded (nobody scores it).
          move all cards from prize to discard
        }
      }
      move all cards from bid[0] to discard
      move all cards from bid[1] to discard
    }
  }

  winner: highest prize_points
}
```
