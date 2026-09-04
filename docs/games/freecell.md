# FreeCell

The companion formal file is [freecell.cardlang](freecell.cardlang); this is
the readable twin. FreeCell is the perfect-information solitaire: one
player, a standard 52-card deck dealt entirely face up. **Rules pinned
here: Microsoft FreeCell** — eight cascades, four free cells, four
foundations, one card moved at a time. (The multi-card "supermove" of the
Microsoft implementation is interface shorthand for a sequence of
single-card moves through free cells and empty cascades, not a separate
rule, so the atomic single-card rule is what is modeled. Cell-to-cell moves
are excluded — they change nothing.)

Setup and play:

- **Layout.** Shuffle and deal all 52 cards face up into eight cascades:
  the first four get seven cards each, the last four six. Above them sit
  four empty **free cells** (each holds at most one card) and four empty
  **foundations**.
- **Goal.** Build the foundations — one per suit — from ace up to king.
  All 52 home wins.
- **A move.** One card at a time. The movable cards are the top card of
  any cascade and any card in a free cell. A movable card may go:
  - to an **empty free cell** (from a cascade top);
  - to its suit's **foundation**, if it is the next rank up (ace first) —
    foundation cards never come back down;
  - onto a **cascade** whose top card is one rank higher and the opposite
    color;
  - onto an **empty cascade** — any single card, no King restriction
    (unlike Klondike).
- **End.** Won when all 52 cards are on the foundations; lost when no
  useful move remains or the player abandons (the score stands at the
  cards sent home).

How the DSL says it: FreeCell is the orthogonality proof for the positional
design (decisions.md "Position domains and positional zones"). It uses the
same machinery as Klondike — position domains (`column : 1..8`,
`cell : 1..4`), position-indexed `Cascade`/`Cell`/`Foundation` families,
`top_of`, the rank-scale guards — and **no `HiddenStack` anywhere**: every
zone projects identity to the sole player, so every observation event
carries full identity, each information set is a singleton, and the game
carries zero visibility machinery it does not need. The proof module
(`tests/openspiel_ready/test_freecell.py`) states the degeneracy directly:
no populated zone projects less than identity, all 52 identities appear in
the derived information state, and the adapter's terminal returns agree
with the DSL's.
