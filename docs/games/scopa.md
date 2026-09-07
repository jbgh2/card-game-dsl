# Scopa

**Variant:** base Scopa (Pagat's main rules: the forced single-card capture,
the scopa sweep with its final-play exception, four scoring categories beside
the scopas, game to 11). **Players:** 2. **Deck:** 40 cards — the Italian pack, played here in
French suits, where coins are diamonds. **Executable spec:**
[scopa.cardlang](scopa.cardlang). **Rules source:**
https://www.pagat.com/fishing/scopa.html (fetched live).

Scopa is a fishing game: cards are captured from a shared face-up layout
rather than won in tricks. Every card has a **capture value** — ace 1, pips
their face value, jack 8, queen 9, king 10 — and a played card takes layout
cards adding up to itself.

## The deal

Three cards to each player, one at a time, and four cards face up on the
table. If three or four of those four are kings the deal is void: the layout
is gathered, shuffled and dealt again by the same dealer. When both players
have played their three cards, three more are dealt to each — never any more
to the table — and so on until the pack is exhausted. Six rounds of three
exhaust the deal: 18 cards each plus the four on the table.

The non-dealer plays first, and the players alternate from there. The deal
passes after each hand.

## Capturing

A turn is one card played face up from hand. It captures, or it does not:

- If some single layout card has the same capture value, that card is
  captured — and this is **forced**. Where several single cards match, the
  player chooses which one to take; the sum-capture is not an option.
- Otherwise, if some set of two or more layout cards has capture values
  summing to the played card's, that set is captured. Where several such sets
  exist, the player chooses among them.
- Otherwise the played card joins the layout face up.

Capturing is compulsory: a player who can capture may not decline. Captured
cards and the card that took them go face down into the capturer's own pile.

**Scopa.** Clearing the layout is a *scopa* and scores a point. The single
exception is the very last play of the deal: a card that clears the table
there captures normally but scores no scopa.

**The remainder.** When the last card has been played, whatever is still face
up goes to the player who captured most recently. This is not a capture and
never scores a scopa.

## Scoring a deal

Five components. Each of the first four is worth one point, taken outright or
by nobody — a tie awards it to neither side.

| component | who scores it |
| --- | --- |
| Cards | most cards in the capture pile |
| Coins | most diamonds |
| Settebello | holding the seven of diamonds |
| Primiera | best prime (below) |
| Scopas | one point each, counted as they happen |

**The primiera.** A *prime* is four cards, one of each suit, valued on a scale
of its own:

| rank | 7 | 6 | A | 5 | 4 | 3 | 2 | J, Q, K |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primiera points | 21 | 18 | 16 | 15 | 14 | 13 | 12 | 10 |

A player's prime is their best card in each suit, so its total is the sum of
four per-suit maxima. A player holding no card of some suit can form no prime
and cannot take the point.

This scale is not the capture value and not any ordering — 7 beats 6 beats
ace here, while the capture value runs ace up to king. The game file declares
the primiera scale as its `card_points { }` table and reads the capture value
off its `ranking:` clause, because a game may declare only one such table and
the primiera scale is the fact that nothing else derives.

## Winning

First to eleven or more points wins, over as many deals as it takes. If both
players reach eleven in the same deal the higher total wins; level, another
deal is played.

## What the DSL cannot say

One sentence lives in `cardlang/runtime/scopa.py` as a declared Primitive:
whether *these* cards are a legal sum-capture. It stays there for two reasons
that are both about the capture being a DECISION rather than a question. A
`where jointly` predicate must root in a call, because that root names the
subset codec below; and a collection type — the type of the candidate set the
predicate is handed — is spellable in a `primitives { }` entry and nowhere
else ([issue #246](https://github.com/jbgh2/card-game-dsl/issues/246)).

The question beside it *is* in the language: whether *some* set of layout
cards sums to the played card is `any subset of 2 or more cards in table where
(sum of capture_value(card) over cards in subset) is played_value`. So is
everything else — the forced single-card capture is a plain guarded movement,
and the primiera is a `for each suit` sum of `highest card_points(card) over
cards in ... or 0`.

The capture decision reaches OpenSpiel through a subset codec
([decisions.md](../decisions.md), "Joint-predicate selection"), which numbers
every set of two or more cards of this deck whose capture values sum to at
most a king's. That universe is the union over every value a played card can
carry; which of its members is legal in a given position is the movement's
own candidate set.
