# Gin Rummy

**Variant:** standard Gin Rummy (Pagat's base rules: knock at 10 or less,
layoffs, undercut +10, gin +20, game to 100, boxes at 20).
**Players:** 2. **Deck:** standard 52. **Executable spec:**
[gin-rummy.cardlang](gin-rummy.cardlang). **Rules source:**
https://www.pagat.com/rummy/ginrummy.html (fetched live).

Aces are low everywhere: A-2-3 of a suit is a run; Q-K-A is not. Card points
are ace 1, pips face value, courts 10.

## The deal

Each player receives ten cards, dealt one at a time. The 21st card is turned
face up beside the stock — the **upcard**, which starts the discard pile. The
first dealer is arbitrary; after that, the winner of each hand deals the
next.

## Turn one: the upcard ritual

The non-dealer speaks first: take the upcard or pass. If they pass, the
dealer gets the same choice. Whoever takes it completes the first turn by
discarding a **different** card (or knocking). If both pass, the non-dealer
must draw the top card of the stock and complete the turn the same way.
Either way, the other player takes the next turn, and turns alternate from
there.

## The turn cycle

On your turn you must first draw — either the top of the stock (unseen) or
the top of the discard pile (seen by both players) — and then end the turn
one of two ways:

- **Discard:** place one card face up on the discard pile. If you took the
  discard-pile card this turn, you may not discard that same card.
- **Knock:** announce the knock and discard one card **face down**. This is
  legal only if the ten cards you keep can be arranged into melds — sets of
  three or four of a rank, or runs of three or more consecutive cards in one
  suit — whose unmatched remainder (**deadwood**) totals 10 points or less.
  Going down with zero deadwood is **gin**.

If the stock is ever reduced to two cards and the player who drew the third
last card discards without knocking, the hand is a **no-result**: nobody
scores, and the same dealer redeals.

## The showdown

The knocker exposes their hand, arranged into melds plus deadwood. Then the
defender exposes theirs, arranging melds where possible — and, **unless the
knocker went gin**, may lay off cards onto the knocker's melds (extending a
shown set or run; never onto deadwood). The knocker never lays off on the
defender's melds.

Count both deadwoods:

- **Knock** (knocker's count strictly lower): the knocker scores the
  difference.
- **Undercut** (defender's count lower **or equal**): the defender scores
  the difference plus a 10-point bonus.
- **Gin**: the knocker scores 20 plus the defender's entire count. A gin
  hand cannot be undercut, and nothing lays off against it.

The winner of the hand deals the next.

## The match

Hands repeat until one player's cumulative score reaches 100 — that player
is the champion (reaching 100 ends the match at once; only one side scores
in any hand, so there is exactly one champion). Settlement then adds the
traditional bonuses to the written scores: the champion adds a **game
bonus** of 100 — or 200 when the opponent never scored a point — and each
player adds a **box** of 20 for every hand they won. (The bonuses are
settlement arithmetic; the champion is fixed the moment 100 is reached,
even where the loser's boxes push their settled total past 100.)

## Notes for the executable spec

- The "different card" rule is structural in the DSL: a taken discard waits
  in a hidden staging zone and merges into the hand only as the turn's
  discard completes, so it is never among the discard candidates.
- The knock is announced (a nullary move), then the face-down knock card is
  a chosen movement filtered to knock-legal discards — one card-valued
  action per decision, as the action encoding requires.
- At the showdown the knocker declares melds one at a time as joint
  selections (`where jointly gin_arrange_ok(...)`), each guarded so the
  remaining hand still arranges to a legal knock; the defender's
  declarations are guard-free (`gin_valid_meld`), since a suboptimal
  defensive arrangement is rule-legal — it just scores worse.
