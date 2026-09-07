# Five-Card Draw

**Variant:** heads-up fixed-limit Five-Card Draw, one hand — ante 1, no blinds,
limits 2 before the draw and 4 after, four aggressive actions per betting round,
and a discard of zero to three cards.
**Players:** 2. **Deck:** standard 52. **Executable spec:**
[five-card-draw.cardlang](five-card-draw.cardlang). **Rules source:**
https://www.pagat.com/poker/variants/5draw.html (fetched live).

Aces are high. The corpus's first **draw**-family poker game: where
[Seven-Card Stud](seven-card-stud.md) and the two Hold'em variants
([three-handed](holdem.md), [heads-up](holdem-heads-up.md)) add cards to a
holding, this one lets a player exchange them.

## The hand

1. **Ante.** Each player puts 1 chip in the pot. Forced, equal, and not a bet:
   an ante buys no right to be called, so the first betting round opens with no
   standing bet and either player may check.
2. **Deal.** Five cards each, face down, dealt one at a time starting with the
   player to the dealer's left. Seat 1 deals, so seat 0 receives first and acts
   first throughout.
3. **First betting round**, at a bet size of 2, begun by the player to the
   dealer's left. Check, bet, call, raise or fold; four aggressive actions in
   all (an opening bet and three raises), after which only call and fold remain.
4. **The draw.** Each player in turn, starting to the dealer's left, discards
   **zero to three cards face down** and is immediately dealt that many
   replacements. A player who discards none has **stood pat**. One player
   finishes their whole exchange, replacements included, before the next
   begins — so the second player draws knowing how many the first took. The
   first round's betting is settled and done before a card is exchanged: no
   bet stands over the draw, and the stake for what follows is already the
   doubled one.
5. **Second betting round**, at that doubled bet size of 4, with the same four
   aggressive actions.
6. **Showdown.** Both players show; the best five-card poker hand takes the pot,
   and equal hands split it. A hand that ended in a fold is never shown.

Then the game ends. The score is `net`, the hand's chip delta against the
100-chip starting stack — the same scoring as
[Leduc](leduc-poker.md) and [heads-up Hold'em](holdem-heads-up.md).

## What each player knows

The exchange is the whole point of the game, and what an opponent learns from it
is exactly one number: **how many cards you took, never which**. That is not a
rule written anywhere in the description above — it falls out of the zone the
discards go into. `discards[player]` is a `HiddenPile<player>`, whose projection
is *identity to the owner, count only to everyone else*, so an opponent's
information state carries `discards[0]=#3` where the owner's carries the three
cards by name. The replacements come off the deck, whose projection is
*count only to all*, so they arrive as `('move', 'deck', 3, 'hole[0]', 3)` in the
opponent's observation stream — three cards moved, three cards unnamed.

A **folded** hand goes to the `Muck`, whose contents are trivial to every
observer including the owner, so a fold reveals nothing and a folded holding
stays unknowable in hindsight.

## What this variant sets, where Pagat leaves it open

Pagat's page fixes the shape of the hand and leaves three things to the table.
This variant's choices:

- **Bet sizing: fixed limit 2 before the draw, 4 after.** The page names no
  sizing at all. The doubling at the draw matches the doubling at the turn in
  the corpus's [fixed-limit Hold'em](holdem-heads-up.md).
- **Four aggressive actions per betting round** — an opening bet and three
  raises — the cap [Seven-Card Stud](seven-card-stud.md) and both Hold'em
  variants carry.
- **Discard zero to three**, the page's base rule. Its optional extension,
  "some allow a player to discard and draw four cards if the fifth card is an
  ace", is a house rule this variant does not adopt.

Two players is Pagat's stated minimum (it calls six the best game), and the
ante of 1 is "an agreed ante" — the page's own words for a quantity the table
settles.

## One deviation from Pagat

**The second betting round opens with the same seat as the first.** Pagat opens
it "with the player who opened the betting on the first round" — the seat that
made the first round's opening *aggression*, not its first-to-act. That seat is
not derivable from anything this game can read: `bet_by` is cleared when a
street opens, and equal `committed` totals do not say who bet first. The family
library [`poker_betting`](../libraries/poker_betting.cardlang) owns `bet` and
`raise` and records no opener, and `uses` imports without inheriting, so a game
cannot observe the aggression without changing the library. Both rounds
therefore open with the seat to the dealer's left — which is also what Pagat's
own rule yields whenever the first round is checked around. This game is the
named witness for [issue #544](https://github.com/jbgh2/card-game-dsl/issues/544),
which is where that gap is tracked.

**Pagat's showdown order wants the same missing fact** and is not a second
deviation. Players show "in clockwise order, beginning with the last player who
took aggressive action (bet or raised) in the second betting round" — the same
unrecorded aggressor. Because every contender shows and no decision stands
between the two reveals, the order changes no seat's information at any
decision, and the showdown reveals both hands at once as Stud's and Hold'em's
do.

## The discard is a sequence of one-card decisions

Not a departure from the game — the documented form of `move chosen N cards`.
At the table a player pushes their discards forward in one motion. Here `toss`
discards one chosen card and `stand` ends the exchange and takes the
replacements, with the `turns` form's `again` axis keeping the same player
deciding until they stand. A player therefore learns nothing between their own
tosses and completes the whole exchange before the next seat begins, so the
reachable exchanges and the information each seat holds match the one-motion
push; only the shape of the game tree differs. The one-decision spelling —
`move chosen some cards from hole[actor] where jointly ...` — needs a
registered per-predicate subset codec ([decisions.md](../decisions.md),
"Joint-predicate selection"), which is engine Python, and the
announce-then-stage decomposition is what that section prescribes in its place.

## Two bounds, stated rather than hoped for

**No player is ever all-in.** Four aggressions at 2 cap the first round's
standing bet at 8 and four at 4 cap the second at 16, so a hand cannot take more
than 24 chips plus the 1-chip ante off a 100-chip stack. No side pot can form
and the ante is never a partial post.

**The deck never runs short.** Ten cards are dealt and at most six drawn, out of
52, so Pagat's reshuffle rule for a depleted stock has no reachable case here
and is not written.
