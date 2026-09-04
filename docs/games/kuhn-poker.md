# Kuhn Poker

The companion formal file is [kuhn-poker.cardlang](kuhn-poker.cardlang); this
is the readable twin. Kuhn poker is the canonical toy poker for **two
players** — three cards, one betting round, and a game tree small enough to
solve by hand, which is why it is the standard first target for every
imperfect-information algorithm. Source: Kuhn's 1950 *Simplified Two-Person
Poker*; this corpus entry is configured to match OpenSpiel's native
`kuhn_poker` at two players, tree for tree and payoff for payoff.

A hand:

1. **Ante.** Both players put 1 chip in the pot.
2. **Deal.** The three-card deck — Jack, Queen, King, all of one suit — is
   shuffled and one card is dealt face down to each player. The third card is
   never used and never seen.
3. **One betting round**, opened by player 0, with a bet size of 1 chip and no
   raises:
   - Player 0 **checks** or **bets** 1.
   - After a check, player 1 checks (showdown) or bets 1; player 0 then
     **folds** or **calls**.
   - After a bet, player 1 **folds** or **calls**.
4. **Showdown.** If neither player folded, both cards are turned face up and
   the **higher card** (K > Q > J) takes the pot. A fold gives the pot to the
   player still in, and the folded card is *never shown*.

The score is each player's **net chips** for the hand: +1/-1 when an
unraised pot is decided at showdown or a bet takes it down uncalled, +2/-2
when a bet is called and the showdown decides the larger pot. That is
OpenSpiel's own `money_[player] - kStartingMoney`, so the two
implementations' returns are directly comparable; `net[player]` in the formal
file is that quantity, computed once at the end of the hand from the `stack`
the betting moved.

Zones and visibility: `hand[player]` is a `Hand<player>` — identity to its
owner, a bare count to the opponent — and that single projection is the
entire hidden structure of the game. `deck` is a `Deck` (a count to
everyone), holding the one undealt card. The showdown moves both hands into
`shown[player]`, a `PublicHand<player>` whose movement event carries the card
name to *both* players; a fold instead moves the folded hand to the `muck`, a
`Muck`, which projects as trivial to everyone including its owner, so a fold
reveals nothing. Chips are ordinary public integer state, as in Seven-Card
Stud.

**The information-set point.** Kuhn's information sets are exactly what makes
it the standard benchmark: a player knows their own card, the betting so far,
and nothing else — six deals collapse into three information sets per player
per betting node. Nothing in this file states that. It falls out of
`Hand<player>`'s declared projection plus the observation events the betting
moves and the card movements emit, the same way it does for every other
corpus game. The one thing worth naming is the *negative* half: the folded
card must stay hidden, and it does because `Muck` is declared trivial — had
the fold routed the card to a public pile, the losing player's holding would
leak and the game would no longer be Kuhn. That pairing (public reveal at
showdown, trivial disposal at a fold) is asserted directly in
`tests/openspiel_ready/test_kuhn_poker.py`.

**The family-library point.** Kuhn is one of two anchors for the `uses`
import tier ([decisions.md](../decisions.md) "Family libraries"). Its
betting comes entirely from
[poker_betting](../libraries/poker_betting.cardlang) — `check`, `bet`,
`call`, `raise`, and the `can_act`/`owes`/`pending` ring predicates — shared
verbatim with Leduc and Seven-Card Stud, three games whose *tables* have
nothing else in common. Three things about that sharing are visible here:

- **`fold` is Kuhn's own.** Folding touches cards, and where the folded card
  goes is a property of the game: Stud mucks the folder's *upcards*, which
  opponents were watching; Kuhn mucks a card nobody ever saw. The library
  holds the zone-free core and stops there.
- **A member offers a subset of the family vocabulary.** Kuhn's `offering`
  list is `[check, bet, call, fold]`: `raise` arrives with the import and is
  never offered — Kuhn has no raise. The parameterization that says so is
  ordinary required state, `raise_cap := 1`, so the imported move is
  guard-false as well as unoffered. Nothing about it reaches OpenSpiel: the
  action space is derived from the `offering` lists, not from the game's
  move-type table, so a whole-library import costs no action ids.
- **A library owns some of its state, and contracts for the rest.** Kuhn
  declares seven of `poker_betting`'s variables and never mentions `acted`
  or `limit`: those the library *provides*, with its own defaults, and Kuhn
  may read them but not write them. That is why Kuhn's one street is opened
  with `run open_street(1)` — the bet size is the argument, since a bet size
  is a property of a street rather than of a game.
