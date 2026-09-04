# Leduc Poker

The companion formal file is [leduc-poker.cardlang](leduc-poker.cardlang);
this is the readable twin. Leduc is the standard step up from Kuhn for
**two players**: still tiny enough to solve exactly, but with a community
card, two betting rounds and a real raise, so the strategies it produces
are recognisably poker. Source: Southey et al., *Bayes' Bluff* (2005); this
corpus entry is configured to match OpenSpiel's native `leduc_poker` at two
players.

A hand:

1. **Ante.** Both players put 1 chip in the pot.
2. **Deal.** The six-card deck — Jack, Queen, King in two suits — is shuffled
   and one card is dealt face down to each player.
3. **First betting round**, opened by player 0, with a bet size of **2**:
   check, bet, call, raise or fold. At most **two aggressive actions** per
   round (a bet and one raise), after which the only replies are call and
   fold.
4. **The board.** If both players are still in, one card is turned **face
   up** — the community card, shared by both hands. A round that ended in a
   fold never reaches this: no board card is dealt at all.
5. **Second betting round**, opened by player 0, identical except that the
   bet size **doubles to 4** and the raise count starts over.
6. **Showdown.** A private card of the **same rank as the board** is a pair
   and beats any unpaired holding; otherwise the **higher private card**
   wins. Equal ranks split the pot. A fold gives the pot to the player still
   in, and the folded card is *never shown*.

Only one player can ever pair: the deck holds exactly two cards of each rank,
so if the board and one hand share a rank, both copies are spoken for.

The score is each player's **net chips** for the hand — OpenSpiel's own
`money_[player] - kStartingMoney`, so the two implementations' returns are
directly comparable. `net[player]` in the formal file is that quantity,
computed once at the end of the hand from the `stack` the betting moved.

Zones and visibility: `hand[player]` is a `Hand<player>` — identity to its
owner, a bare count to the opponent. `board` is a `Discard`, fully public, so
turning the community card is an observation event both players receive with
the card named. The showdown moves both hands into `shown[player]`, a
`PublicHand<player>`; a fold instead moves the folded hand to the `muck`, a
`Muck`, which projects as trivial to everyone including its owner. Chips are
ordinary public integer state, as in Kuhn and Seven-Card Stud.

**The information-set point.** A Leduc information set is the player's own
card, the board once it is turned, and the betting so far. Nothing in this
file says so: it falls out of `Hand<player>`'s and `Discard`'s declared
projections plus the events the betting moves and card movements emit. Two
negative properties are worth naming because they are easy to lose and are
asserted directly in `tests/openspiel_ready/test_leduc_poker.py`: a folded
card mucks without identity, and a **first-round fold turns no board card at
all** — dealing one anyway would shrink the set of hands the folder could
have held, leaking through the deck rather than through the fold.

**The family-library point.** Leduc is one of two anchors for the `uses`
import tier ([decisions.md](../decisions.md) "Family libraries"). Its
betting comes entirely from
[poker_betting](../libraries/poker_betting.cardlang) — `check`, `bet`,
`call`, `raise`, and the `can_act`/`owes`/`pending` ring predicates — shared
verbatim with Kuhn and Seven-Card Stud. Leduc is the member that exercises
the tier's **parameterization** claim: the family's constants ride on state,
not on arguments to the import. The two halves of that are visible side by
side here. `raise_cap` is **2** where Stud's is **3** — a per-game constant,
so it is `requires`d and Leduc declares it. The bet size is not a per-game
constant at all (it is **2** then **4**), so no declaration could carry it:
`limit` is state the library *provides*, and each street names its own size
by opening with `run open_street(2)` / `run open_street(4)`. Neither the
library text nor the `uses` line mentions the difference. `fold` is Leduc's own, as in every
poker game — folding touches cards, and where the folded card goes is a
property of the table, not of the betting.
