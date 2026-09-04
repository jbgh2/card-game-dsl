# Getaway (Bhabhi)

The companion formal file is [getaway.cardlang](getaway.cardlang); this is the
readable twin. Getaway (Bhabhi) is an elimination game: shed all your cards to
"get away", and the last player still holding cards is the loser. Players must
follow the led suit; a player who is void plays a **tochoo** (an off-suit card),
which ends the trick at once and forces whoever played the highest card of the
led suit to pick up the whole pile. When everyone follows, the highest card wins
and the played cards are discarded out of play.

## Formalization notes

Two variant mechanics that appeared in an earlier sketch of this game are
deliberately **not** formalized, because they are not part of standard Getaway
(Pagat) and each was underspecified:

- **Stealing (`steal_left`).** An "alone leader steals from the left" action
  was listed but its *effect* was never defined (no statement said what a steal
  does). The core elimination game is complete without it.
- **Drawing from the waste.** A rule let the trick winner draw a card back from
  the waste when their hand emptied. It contradicts the elimination invariant
  (a player who has shed all cards is out) and, by feeding hands from the
  discard pile, can prevent the game from ever terminating. The standard game
  has no such draw: cards only leave hands, so the game always ends.

Both can be revisited as explicit, fully-specified variants later.
