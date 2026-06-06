# Games implementation — running log

Branch: `games-implementation`. Goal: bring every remaining corpus game from a
`.md` design doc to an executable `.cardlang` that a random-layout playout can
play end to end while preserving the game's invariants (the runtime net).

This file is **process history** — decisions made and questions raised while
building, kept out of `docs/` deliberately (the docs are spec, not history, per
CLAUDE.md). Genuine settled language decisions get promoted into
`docs/decisions.md` (spec voice); genuine open design questions get promoted
into `docs/open-questions/`.

## Starting state

- Executable today: Hearts, Getaway. Runtime is trick-taking-shaped: one
  `Trick` mechanic, card-only chooser, `standard52`-only deck, led-suit-only
  outcome, per-player integer scoring, winner = min/max of a score var.
- Remaining (this branch): Spades, Oh Hell, Schnapsen, Pinochle, Bridge, Skat,
  French Tarot, Cribbage, Seven-Card Stud, Tichu, Coup.

## Strategy (confirmed with advisor)

- Order by distance from the `Trick` engine, not "difficulty":
  - *Trump-trick family* (extend `Trick`): Spades, Oh Hell, Schnapsen, Pinochle,
    Bridge, Skat, Tarot.
  - *Structurally different* (new mechanic each): Cribbage (pegging/counting),
    Seven-Card Stud (betting + hand ranking), Tichu (combination climbing),
    Coup (bluff/influence).
- Widen each Hearts-shaped chokepoint *generically* the first time a game forces
  it — never add a second hardcoded branch beside Hearts.
- Stop only on a true DSL breakdown: grammar/IR can't express a game without a
  change that breaks games already working. New backward-compatible syntax is
  additive, expected work — keep going.
- Each game is "done" only when its playout test would go **red** under a real
  bug (card conservation, point/trick reconciliation, trump resolution,
  termination, correct winner) — not merely "the playout ran".

## Decisions

### Spades (done)

Language extensions added (all generic, reusable across the trump-trick family):
- `trump: <suit>` game declaration; the outcome function
  `highest_trump_or_led_suit` reads it (outcome functions now receive the trump
  suit as a third argument; `highest_of_led_suit` ignores it).
- Partnerships: `partnerships: [[0, 2], [1, 3]]` (teams as seat-index lists), a
  `team` index role for zones and state, `team_of(p)`, a `team` domain for
  `for each team` / `any team`, and team-indexed `captured`/`score`. The driver
  already ranks the winner over whatever the score var is keyed by, so a
  team-indexed score var makes `winner: highest score` rank teams with no
  special case.
- `choose integer in <lo> .. <hi>` expression — the value-general decision seam
  the advisor flagged. The chooser is now typed over `Any`, not just cards.
- `*` multiplication operator (the grammar only had `+`/`-`).
- `TeamPile` zone type; `submit_bid` move type.

Spades-specific design choices:
- Scoring is folded into the `scoring` phase (inline, as Hearts does); the
  `scoring_component` / `apply_components` / `ScoreDelta` subsystem sketched in
  spades.md is **not** built — every Spades component (contract, nil, bag
  overflow) was expressible inline. Deferred until a game genuinely needs
  triggered cross-hand components.
- Dropped the redundant first-trick spade ban; "no leading spades until broken"
  already forbids leading a spade on trick 1 in this variant.
- Termination at +500 **or** −200. The −200 floor is a standard Spades loss
  threshold and it guarantees termination under uniform-random bidding, which
  systematically overbids (two random 0..13 bids sum to ~13 but only ~6.5
  tricks per team are winnable, so contracts almost always fail and scores
  trend negative). Bidding order is irrelevant to invariants under random play,
  so `for each player` is used rather than adding an `each player in turn`
  construct.

Falsifiable invariants in `tests/test_playout_spades.py` (200 games): card
conservation (52 cards, no hand holds cards at end), 13 tricks/hand × 4
plays/trick, **trick-winner correctness recomputed from the cards played**
(would go red under a wrong outcome function), termination at a real threshold,
winner = top-scoring team.

### Oh Hell (done)

Language/runtime additions (generic):
- A per-trick `trump =` argument to `instantiate Trick(...)`: when trump varies
  by hand, the cardlang passes the per-hand trump state var; the mechanic falls
  back to the game-level `trump:` decl when the arg is absent. The trump is also
  surfaced in the `trick_end` trace (a dict key) so playout tests can verify
  trick-winner correctness against a per-hand trump.
- `suit_of(card | zone)` stdlib call — the suit of a card, or of the single card
  in a zone (the face-up trump indicator).

Design choices:
- Variable hand size carried by a `hand_size` state var recomputed each hand in
  `before_each` (a phase-body `let` would not thread into the deal/play
  sub-phases — lets don't cross phase boundaries; state vars do).
- 19 fixed hands via a `hand_index` counter incremented in `after_each`;
  termination `repeats until hand_index >= 19`.
- Dealer hook enforced as a post-bid correction to the dealer's bid (guarantees
  total bids ≠ hand size) rather than a choice-time constraint — see the open
  question on sequential bidding.
- Exact-bid scoring folded inline into the `scoring` phase.

Falsifiable invariants (`tests/test_playout_oh_hell.py`, 100 games): exactly 19
hands, exactly 109 tricks total (the hand-size sequence sums to 109), card
conservation, and per-trick winner correctness against the hand's trump.

## Next up: Schnapsen (runway note)

Schnapsen is the first game that needs an **action-selection** layer, not just a
card chooser. At each lead the player chooses among heterogeneous moves —
`play_to_trick`, `declare_marriage`, `exchange_trump_jack`, `close_talon`,
`claim_66` — each with its own effect on per-hand state. The plain `Trick`
mechanic (everyone plays one card) can't express this; it needs a new mechanic
(a trick-and-draw / lead-action loop) alongside `Trick`. Also new: the
`schnapsen20` deck, Ace-Ten **card point values** (J=2 Q=3 K=4 10=10 A=11), the
talon draw after each trick, marriages, talon closing with a state snapshot, and
the five-shape settlement.

Assessment against the stop condition: this is **additive** (a new mechanic +
new deck + card-value table), not a DSL breakdown — keep going. The likely
generic seams to widen: a deck-values table (also needed by Pinochle/Tarot), and
a way to express "choose which move type to make, then run its effect" (also the
shape of the auction games, so design it to generalize).

## Open questions

- **Representative playouts vs invariant playouts.** Uniform-random bidding
  never reaches Spades' +500 win branch, so that branch is exercised only by the
  −200 path in the test. The random driver's job is invariant-preservation, not
  realism, so this is acceptable — but a light "rational-ish" bidding policy
  would make playouts more representative and exercise win branches. Deferred.
- **`scoring_component` subsystem.** Still unbuilt; Spades didn't need it.
  Bridge/Skat (contract bonuses, vulnerability, rubber) may force a real
  decision here.
- **Sequential bidding / `choose … excluding …`.** Oh Hell's dealer hook and the
  Bridge/Skat auctions want a player to choose in turn order while reading prior
  choices, and to exclude specific candidates. Modelled approximately for Oh
  Hell (post-bid correction). A real `each player in turn from <p>: …` construct
  plus an exclusion form on `choose` is likely needed for the auction games and
  should be designed once, generically, when Bridge forces it.
