# Canasta

**Variant:** Classic Canasta (Pagat's base rules), with the simplifications
listed below. **Players:** 4, in fixed teams — partners sit across
(seats 0+2 vs 1+3). **Deck:** two standard 52-card packs plus four jokers,
108 cards (`canasta108`). **Executable spec:**
[canasta.cardlang](canasta.cardlang). **Rules source:**
https://www.pagat.com/rummy/canasta.html (fetched live).

**Simplifications** (everything else is the Pagat classic game):

- A fixed **four-deal match** replaces "first side to 5,000 wins". The
  initial-meld minimum still reads the real cumulative-score brackets,
  including the negative-score bracket.
- The initial-meld minimum must be met by a **single meld** (plus the top
  card of the pile when it is taken); the real game may combine several
  melds laid in the same turn to reach it.
- The optional "may I go out?" question to partner and the concealed-hand
  double bonus are omitted.
- The first dealer is seat 0; the deal rotates left each hand.

## The cards

Jokers and **deuces (2s) are wild**. Threes are special: **red threes** are
bonus cards that never stay in a hand, and **black threes** are stop cards
(see below). Everything else — A, K down to 4 — is a natural card. Card
point values:

| cards | value |
|---|---|
| joker | 50 |
| deuce, ace | 20 |
| K, Q, J, 10, 9, 8 | 10 |
| 7, 6, 5, 4, black 3 | 5 |

## The deal

Eleven cards to each player, one at a time, clockwise from dealer's left.
The rest of the pack becomes the face-down **stock**; one card is turned up
beside it to start the **discard pile**. If that card is a wild card or a
red three, it is placed sideways under the pile and another card turned,
until a start card appears — a pile begun this way is **frozen** (below).

Any red three dealt to a player is immediately laid face up with their
team's melds-to-be and replaced from the stock.

## The turn

Play is clockwise from dealer's left. On your turn you must first either:

- **draw** the top card of the stock, or
- **take the whole discard pile** — legal only under the pile rules below,
  and only by immediately melding the pile's **top card**. The rest of the
  pile joins your hand once that meld is made.

If you draw a red three, lay it out and draw a replacement (a red three
drawn as the stock's last card ends the hand at once — no meld, no
discard).

You may then **meld** as much as you wish (see melds), and must end your
turn by **discarding one card** face up onto the pile — except when going
out, which may be done with or without a final discard.

## Melds

A meld is three or more cards of one natural rank, laid face up in front of
the team. Wild cards substitute for the rank, under the composition
rule: **at least two natural cards, and never more than three wild cards**.
A side keeps **one meld per rank**; either partner may later add natural
cards of the rank, or wild cards (while the meld holds fewer than three),
on any of their turns. Melds belong to the team and stay on the
table to the end of the hand.

A meld of **seven or more cards is a canasta** — worth a 500 bonus if it
contains no wild card (**natural**), 300 otherwise (**mixed**). Cards may
still be added to a completed canasta; adding a wild card to a natural
canasta makes it mixed.

**The initial meld.** A side's first meld of a hand must meet a minimum
count — the sum of the standard values of the cards laid down — read from
the team's cumulative score:

| cumulative score | minimum |
|---|---|
| negative | 15 |
| 0 – 1,495 | 50 |
| 1,500 – 2,995 | 90 |
| 3,000 + | 120 |

Red threes count toward no minimum. When the pile is taken for the initial
meld, only its top card counts toward the minimum.

## The discard pile

- The pile can never be taken when its top card is a **wild card** or a
  **black three**. Discarding a black three thus blocks the next player
  from the pile; the three is simply buried by the next discard (black
  threes never freeze the pile, and can only ever be melded — as a group
  of three or four, no wilds — in the act of going out).
- Discarding a **wild card freezes the pile** (place it sideways). A pile
  started from a wild card or red three at the deal is frozen the same
  way. The freeze lasts until the pile is taken.
- The pile is always **frozen against a side that has not yet melded**.
- Taking a **frozen** pile (frozen for your side by either route) requires
  **two natural cards of the top card's rank from your hand**, melded with
  the top card.
- Taking an **unfrozen** pile requires melding the top card with two cards
  from hand (two naturals of its rank, or one natural and one wild), **or**
  adding it to your side's standing meld of that rank.

Taking the pile takes **all** of it: after the top-card meld is made, every
remaining pile card joins your hand (red threes from a frozen start go to
your side's red-three row), and you may go on melding before you discard.

## Going out

You go out by shedding every card in your hand — melding all of it, or all
but one card which becomes your final discard. Going out is legal only if
your team has completed **at least one canasta**, and it ends the
hand immediately. (The executable spec enforces this continuously: no meld
may leave you unable to legally end your turn — you always keep either two
cards, or a canasta on your side's row.)

## The end of the stock

If a player wants to draw and the stock is empty, the hand ends — with one
exception: while the pile can still legally be taken, play continues on
pile takes. With no stock, a player **must** take the pile when it is not
frozen against their side and its top card matches one of their side's
melds; they **may** take it whenever a take is legal; and a player who
neither must nor can (or declines a voluntary take) ends the hand.

## Scoring the hand

Each team scores, onto its cumulative total:

- **+** the card values of everything it melded (canastas included),
- **+ 500** per natural canasta, **+ 300** per mixed canasta,
- **+ 100** per red three — **800** for all four — if the side made at
  least one meld; the same amounts **negative** if it never melded,
- **+ 100** for going out,
- **−** the card values of everything still held in both partners' hands.

After four deals, the side with the higher cumulative score wins.

## Notes for the executable spec

- **Team melds are team-indexed zone families, one per rank**
  (`meldA[team] … meld4[team]`, plus the black-three group and the
  red-three row). A meld's typed state — natural vs mixed, canasta or not —
  is derived from its composition at every read (the game's own `function`s
  for the go-out and add guards and the meld-point sum; the canasta-bonus
  primitive for the per-pile object bonus); growth
  is ordinary card movement by either partner; hand-end scoring reads each
  pile as an object. This is the flattening that settles
  first-class meld groups (decisions.md "Meld groups: flattened zone
  families").
- **Melding is announce-then-stage**: `start_meld(rank)` (or a pile take)
  opens an attempt, cards join one at a time through the public `stage`
  zone, `close_meld` commits it. Every stage/close is guarded by a
  completability core (`cardlang/runtime/canasta.py`), so any reachable
  staging position still closes legally — Gin's arrange-guard totality,
  per card. The stage zone is public, as melding at a table is.
- **The frozen pile is a boolean, not a sub-phase** (`pile_frozen`): no
  rule's `applies_when:` reads it — it gates only the take-pile
  preconditions, and its effect is per-side anyway (a side that has not
  melded is frozen out regardless). Zone state does not change the
  boolean-as-sub-phase criterion (decisions.md).
- **Taking the pile moves public knowledge**: the pile's contents were
  public as they accumulated, so the take's movements (top card to the
  meld, the rest into the hand) are identity to every observer — everyone
  knows exactly which cards entered the taker's hand, while stock draws
  stay count-only. The proof module
  (tests/openspiel_ready/test_canasta.py) pins both.
