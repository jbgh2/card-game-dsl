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
