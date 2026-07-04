# Broad-sweep stress test — findings (2026-07-04)

16 games attempted by independent lower-power agents (Haiku for 4 controls,
Sonnet for 12), DSL only, no Python, no `instantiate`. Each implementation was
audited by a second agent that re-ran the checks, compared the file against
Pagat, and classified every claimed language gap as **real-gap /
construct-exists / agent-error** with grammar/runtime line citations. Two
games (Euchre, Texas Hold'em) never produced files — their agents died twice
on infrastructure failures (API stalls, then a spend limit), so the bower
rank-remap and community-card-showdown probes remain **untested**, not
failed.

## Scoreboard

| Game | Checker | Playouts | Audit grade | Confirmed real gaps |
|---|---|---|---|---|
| Whist | green | 20/20 | rules-faked | 0 |
| Knockout Whist | green | 20/20 | simplified-ok | 0 (all 3 claims = construct-exists) |
| Crazy Eights | green | **crash** | broken | 1 (5 of 6 claims = construct-exists) |
| Old Maid | green | 20/20 | rules-faked | 1 minor |
| Go Fish | green | 20/20 | *(unaudited)* | 2 major (in-file GAP notes) |
| President | green | 20/20 | simplified-ok | 6 |
| Gin Rummy | green | 20/20 | simplified-ok | 6 |
| Blackjack | green | 20/20 | *(unaudited)* | 1 major + minors |
| Ninety-Nine | green | 20/20 | simplified-ok | 6 |
| Palace | green | **~10-15% seeds crash** | broken | 9 |
| Durak | green | 20/20 | rules-faked | 5 |
| Cheat | green | 20/20 | *(unaudited)* | 2 major (in-file GAP notes) |
| Casino | green | 100/100 | rules-faked | 6 |
| Canasta | green | 20/20 | rules-faked | 8 |
| Euchre | — | — | no file (infra) | — |
| Texas Hold'em | — | — | no file (infra) | — |

All 14 written files reach checker-green. "rules-faked" means the audit found
*undeclared* deviations from the real rules — a fidelity failure of the
implementing agent, not (usually) of the language.

## What is working

**1. The info-set bet is validated — the headline positive.** Across all 14
games, including the ones chosen to break it, *zero* games needed custom
visibility code. Who-sees-what fell out of zone declarations alone:

- **Cheat** (the designed stress case): the public rank claim is a state
  variable (state is public by convention; hidden information lives only in
  zones), the true cards sit in a `FaceDownPile`, and a challenge *is* a
  movement into a public `Discard` zone — the reveal derives from the
  projection model with no epistemic operation. Claim-vs-content separation,
  the thing that looked like it would need new machinery, is already
  representable.
- **Palace**: blind-even-to-owner cards fell out of a library zone type.
- **Durak**: defender picking up the whole public table, hidden talon,
  public trump — stock projections.
- **Blackjack**: hole card = `Hand<house>` next to a `PublicHand` — the
  face-up/face-down split is two zone declarations.
- **President**: the four-leg card exchange is visible to exactly the two
  players swapping (others see counts), with zero visibility clauses.

**2. The substrate under the `round` forms is far more general than the
corpus suggests.** Seven games (Canasta, Casino, Durak, Gin Rummy,
Ninety-Nine, Palace, Cheat) fit *none* of trick/climb/auction and still
reached green by hand-rolling turn structure from `offer` + `repeat until` +
game-defined `move_type`s. Draw-meld-discard, attack/defence, fishing,
adding, and banking games all run on the raw kernel primitives today.

**3. Sum-capture works.** Casino's headline mechanic (capture by sum) is
expressible and was verified live (419 firings across 30 seeds) — bounded to
2-card sums by the subset-selection gap below, but real.

**4. Corpus idioms transfer.** French Tarot's "direct a chosen movement at
one named player" idiom was independently rediscovered by President and
Cheat; Cribbage's pegging fold powered Ninety-Nine's running count; Stud's
auction-form round shape became Blackjack's forced dealer and Cheat's
serialized challenge window. The idioms generalize — but see the
discoverability finding below.

## What is not working

**1. The docs promise more than the runtime delivers — the most repeated
confirmed gap, and the loudest bell.** Audits independently confirmed, with
file/line citations, that constructs documented in `decisions.md` /
`library.md` are unimplemented or wrong:

- Epistemic ops: only `shuffle` exists; `reveal/peek/hide/announce/
  expose_top/forget` are grammar comments.
- ZoneContents API: only `.where` and `.cards_of_suit`; `.top`,
  `highest_by`, `highest_of_suit`, `has_card_of_suit`,
  `contains_card_of_suit`, `.non_empty`, `.count`, `amount_of`,
  `total_amount`, `types_present` are documented, unimplemented.
- Deck declaration: docs show an inline `cards: { suits: ... }` literal and
  `standard52 + { values: ... }` composition; the grammar accepts one bare
  registry name.
- Per-card attributes; the `<actor> chooses` expression form; callable
  2-arg `min`/`max` — all documented, all absent.
- **`count` aggregator ignores its predicate body** and returns collection
  size — documented semantics, silently wrong results.
- **`actions`-kind rule demands are checker-accepted and runtime-ignored**
  (Hearts' own `action.card_count == 3` demand has no consumer).

For a project whose operating rules are all about spec integrity, this is
spec corruption in the reverse direction: the spec describes a language that
does not exist yet, and every agent (human or model) that codes against it
falls through the gap.

**2. Closed Python registries are the new escape hatches.** The walls agents
hit hardest are all "the list is closed":

- `DECKS`: no 36-card deck (Durak), no 2×52+jokers (Canasta) — one closed
  dict forecloses the stripped-deck European family *and* the multi-deck
  rummy family.
- Climb combination engines: `STDLIB_CLIMB_LEADS/FOLLOWS` contain exactly
  Big Two's two functions; President had to play Big Two's combinatorics,
  including five-card hands that don't exist in President.
- `legal_moves:` validates against a closed stdlib table — a game's own
  `move_type`s can't be listed.
- Move-parameter domains: `enumerate_domain` supports Suit only. This one
  gap is the root cause of Go Fish's both major distortions (can't
  parameterize over Player or Rank, so "ask anyone for any rank you hold"
  became "ask a fixed seat-relation for a rank from a fixed cycle"),
  Ninety-Nine's 14 nullary move types, and Canasta's per-rank move
  explosion.
- Stdlib function dispatch is a closed match statement, and unknown names
  typecheck as `TAny` — misspellings pass the checker and die at runtime.

Same lesson as `kernel-extensibility.md` §6, one level down: per-game Python
mechanics were recognized as debt, but per-construct Python *registries*
reproduce the same debt at finer grain.

**3. Decision-value plumbing.** No way to read back which card a `chosen`
movement selected; `action` is not bound inside a game-defined `move_type`'s
own effect body; `choose` supports only integer ranges — there is no scalar
card extraction at all. Ninety-Nine could not express "the card just played"
(King's set-to-99 fought the fold model); Palace triplicated pile-resolution
logic partly for this reason.

**4. Combinatorial/joint selection.** `chosen N where pred` filters
per-card; there is no "choose a *set* satisfying a joint predicate".
Blocks: multi-card same-rank plays (Palace; President under ties),
arbitrary-size sum captures and multi-group captures (Casino),
and any meld-partition search (Gin — worked around elegantly by making meld
arrangement a sequence of player decisions rather than a solver).

**5. Expression-language holes.** No division (Blackjack's 3:2 payout is
inexpressible at bet 1 — rebased to bet 2); no unary minus; no rank-keyed
lookup tables (13-branch elif chains); statement-level `if` has no `elif`;
functions can't take Zone parameters and there is no statement-level
procedure, forcing triplication (Palace ~15 lines × 3, Gin 6 helpers × 3).

**6. Runtime robustness and performance.**
- Checker-green ≠ playable: Crazy Eights and Palace both pass the checker
  and crash at runtime. The hardcoded 10,000-iteration `repeat until` cap
  kills ~10-15% of Palace seeds (thousands of legitimate turns).
- `ClimbForm` asserts `ring[0] == leader`, crashing whenever a trick winner
  sheds out on their own winning play — a latent bug reachable from Big Two
  itself, found because President exercised the form harder.
- The tree-walking interpreter with no memoization made Gin Rummy's
  when-guards (tens of thousands of `evaluate()` calls per decision) slow
  enough to require gameplay caps — relevant to the OpenSpiel target, where
  playout speed is the currency.

**7. Turn-order dynamics.** No direction reversal (Ninety-Nine's 4s — worked
around with a Direction-typed state variable and `offset_by`), no
player-by-absolute-index, first-player selection still roadmapped.

## Process findings (about the method, not the language)

- **Unaudited lower-power output cannot be trusted**: 5 of 11 audited games
  had silently faked rules (Canasta worst: a fabricated all-2s-meld
  mechanic, 2-card draws); the "cleanest" self-report (Whist) was a 12-trick
  game. Meanwhile roughly half of all *claimed* gaps — and 5 of 6 for the
  weakest implementer — were refuted as construct-exists.
- **Discoverability is a real language-adoption gap**: the refuting idioms
  almost always lived in a specific game file, not in the indexed docs
  (French Tarot's chien idiom, Oh Hell's trump indicator, Pinochle's
  `declare_trump_suit`). A patterns cookbook (mechanic → idiom → game file)
  would have prevented most false gap reports, and would serve human users
  identically.

## Verdict

**The language is not painting itself into a corner.** The architectural
bets — zones + projections for derived info sets, phases/moves/rules over a
small operational core — generalized to 14 structurally diverse games with
zero visibility special-casing, which is precisely the property the OpenSpiel
target needs. The corner-risk lives elsewhere: features are entering as
closed Python registries and as documentation that outruns the
implementation, and both fail exactly the audience a DSL exists for. The
sweep independently corroborates the direction already named in
`kernel-extensibility.md`: make the closed lists authorable from the DSL.

## Suggested priorities from this sweep

1. **Doc-honesty pass**: mark every unimplemented construct in
   `decisions.md`/`library.md` as proposed (the `scoring_component`
   precedent), and fix the two active traps: the `count` aggregator's
   ignored predicate and checker-accepted-but-inert `actions` demands.
2. **Inline deck declarations** — one feature unblocks two whole game
   families (stripped decks, multi-deck).
3. **Move-parameter domains beyond Suit** (Rank, Player) and parameterized
   move types in plain `offer` — kills the nullary-move-type explosion.
4. **Bind `action` in move_type effects + a `.top`/last-moved accessor** —
   the decision-value plumbing.
5. **Runtime**: configurable/diagnostic loop cap; fix the ClimbForm
   leader-sheds-out assertion (and check whether Big Two can reach it).
6. Division + unary minus + callable min/max.
7. Longer-term: a joint-subset selection primitive; a patterns cookbook doc.
8. Re-run the two lost probes (Euchre's bowers, Hold'em's community cards)
   when budget allows — they test axes nothing else in this sweep covered.
