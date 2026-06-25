# Migrating the corpus onto the decision kernel

This is the execution brief for removing the per-game **concrete runtime
mechanics** and expressing their decision logic in the DSL itself, on the
interactive-decision kernel. The design it executes is settled in
[decisions.md](decisions.md), "Interactive decisions: a kernel and an in-DSL
standard library", with the full rationale in
[superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md](superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md).
The discipline (red→green, IR goldens, exhaustiveness) is in
[building.md](building.md). This file is the *order of operations* and the
per-game scope.

It is written to be handed to an implementer. Each workstream states what
capability it adds, the kernel/standard-library pieces it builds, the
checkpoints where a genuine language gap might surface, and its definition of
done.

## The goal, concretely

Eight games still hold their decision logic in hand-written Python dispatched by
name in `cardlang/runtime/mechanics.py::instantiate`. Bridge's, Pinochle's, and
Tarot's auctions have been lifted onto the kernel `round` — so `run_bridge_auction`
is gone, and `run_pinochle_hand` / `run_tarot_hand` are now the post-auction
`run_pinochle_rest` / `run_tarot_rest`:

- inline in `mechanics.py`: `run_schnapsen_hand`, `run_pinochle_rest`
- separate modules: `runtime/coup.py`, `cribbage.py`, `skat.py`, `stud.py`,
  `tarot.py` (post-auction), `tichu.py`

This violates the two-layer architecture ([principles.md](principles.md): the
library is *written in the DSL*, not the engine). The stage is done when:

- `instantiate` dispatches only to kernel constructs — no per-game name
  branches — and the six `runtime/*.py` game modules and the three inline
  `run_*_hand` functions are deleted;
- all 13 games run on the kernel plus the in-DSL standard library, with every
  `tests/test_playout_*.py` green and **behaviour preserved**;
- IR golden snapshots are regenerated and reviewed;
- `mypy --strict` is clean and no `language-gap` entry is silent (each is zero
  or a named `open-questions/<slug>.md`);
- [decisions.md](decisions.md), [library.md](library.md), and this file are
  updated in lockstep, per the [CLAUDE.md](../CLAUDE.md) operating rules.

The built-in `Trick` mechanic was also engine code, not DSL. Retiring it —
moving Hearts, Spades, Getaway, and Bridge's play onto the kernel `round` (Oh
Hell already used it) — is done as part of the prerequisite below.

## Non-negotiable discipline

These hold for every step; they are what make a 1,800-line deletion safe.

- **Behaviour-preserving.** The Oh Hell trick migration is the precedent: the
  game's playout test and conservation invariants (cards/coins/points balance)
  stay green across the change, with no behavioural diff. Migrate, don't
  redesign.
- **Test-depth nets before risky migrations.** Random playouts never reach
  skill-gated branches (Schnapsen false claims, Spades nil/+500, Coup
  challenge-loser — see [roadmap.md](roadmap.md), "Test-depth regression nets").
  Where a game has such a branch, add an independent-recompute test **before**
  migrating it, or the migration can pass playouts while being subtly wrong.
- **One construct per commit**, red fixture → minimal kernel/grammar/checker
  change → green, IR golden diff reviewed. Constructs are never batched.
- **A definition adds words, not semantics.** Standard-library definitions
  (`auction`, `betting`, `climb`, `challenge`, `block`, `trick`) compose over
  the fixed kernel; they do not introduce control primitives or mutate rules.
  Variation lives in *values along the closed axes*. A genuinely new **axis** is
  a major change requiring explicit sign-off — flag it, don't quietly add an
  engine hook.
- **Promote at the third instance.** A definition stays game-local until roughly
  three corpus games exhibit the same shape, then moves to the shared standard
  library (corpus-first).

## Step 0 — Generalize the `round` kernel (prerequisite)

*The trick-migration portion of this step is built: every trick game (Hearts,
Spades, Getaway, Bridge, Oh Hell) runs on the kernel `round`, the built-in
`Trick` mechanic and the routing-def construct are retired, and `round` carries
the termination axis (`early`) plus round-state exposure. The remaining axes
below (accumulator, order, move vocabulary) land with the workstreams that first
need them — see [roadmap.md](roadmap.md).*

The `Round` node (`cardlang/ast/nodes.py`) is trick-shaped: one card play per
participant plus an `outcome` function. Everything below composes on a
`round` grown to the closed axes from [decisions.md](decisions.md):

- **participants** — actor / others / ring / list
- **order** — turn-from-a-seat / priority / simultaneous
- **accumulator** — a value threaded across steps (high bid, bet-to-match,
  running total, led combination)
- **termination** — a predicate over the accumulator/state
- **typed outcome** — reusing the Stage 1–3 variant/outcome machinery
- **move vocabulary** — not only card plays: non-material `move_type`s (bids,
  passes, actions) chosen via `offer`

Build this, then re-express the existing trick `round` as one configuration of
it with no behavioural change (the same proof Oh Hell already gives). Then
migrate the remaining built-in-`Trick` games onto the kernel `round` —
Hearts/Spades (rule-delta transitions) and Getaway (early termination) — and
delete the built-in `Trick` mechanic. This both retires shared engine code and
exercises every axis before the harder games arrive.

## Workstream 1 — Auctions (Bridge, Skat, Tarot, Pinochle)

Highest leverage: four instances of one shape, so `auction` is promotable to the
standard library immediately on the third.

Build an `auction` definition over `round`: `ring` participants, accumulator =
current high bid + pass state, termination = all-but-one passed (or N
consecutive passes), typed outcome = a contract variant. Then per game, supplying
*values along the axes*:

- **Bridge** — *done.* A two-dimensional bid space (level × strain) plus
  doubling/redoubling, on the auction form of `round`; the typed
  `contract_finalized | all_pass` outcome computes the declarer over the bid
  history. `run_bridge_auction` and its `instantiate` branch are deleted.
- **Pinochle** — *done (auction).* The ascending bid runs on the auction form of
  `round` over a **shrinking participants ring** (`over players where not
  passed[player] and (lead_bidder is none or player != lead_bidder)`), the nullary
  `submit_bid`/`pass` vocabulary, and the single-variant `bid_won(declarer, bid)`
  outcome (opener-at-50 fallback when all pass). `run_pinochle_rest` (the renamed
  monolith minus its auction block) reads the declarer and runs `declare_trump` +
  meld + tricks; byte-identical over 50 seeds. (Meld scoring is Workstream 3/4;
  the module is deleted then.)
- **Tarot** — *done (auction).* The four-level ascending bid (Petite < Garde <
  Garde sans < Garde contre) on the auction form of `round`: a **counterclockwise
  single-pass ring** (each seat drops out of the participants ring after acting,
  one bid each), five nullary level moves guarded by the standing bid, and a
  two-variant `taken(taker, level) | thrown_in` outcome (an all-pass hand is
  thrown in via `skip to next hand`). Exposed and fixed the kernel's
  clockwise-only `turn_order_from` (now honours `direction`). `run_tarot_hand` is
  the post-auction `run_tarot_rest` (chien dispatched by level, eighteen tricks,
  scoring); byte-identical over 50 seeds.
- **Skat** — the Reizen call-and-response auction (one player names successive
  values, the other holds or passes), then the contract choice (Suit / Grand /
  Null, hand vs. picking up the skat).

**Checkpoint (possible new axis).** Skat's call-and-response is a different
*order* from a simple ascending ring. Confirm it is a value on the order axis;
if it is not expressible, that is a `language-gap` → file an open question, do
not special-case it.

**Dependency surfaced by Bridge — built.** The auction form does not silently skip
a participant with no legal move — the ring is stated by the participants clause and
"all but one passed" by `until` ([decisions.md](decisions.md), "The auction form
of `round`"). Bridge keeps every seat in with an always-legal `pass`, but the
ascending auctions drop players who pass for good (and skip the standing high
bidder) with no decision — a *shrinking ring*. Reproducing that byte-identically
needs the participant predicate re-evaluated each turn — the **participant-filtering
axis**, which `run_auction` now does (it re-evaluates `over … where …` per turn, a
no-draw skip for a dropped player; a static ring like Bridge's `all players` is the
invariant case). Built with Pinochle; reused by Workstream 2 (Stud's non-folded
ring). An always-legal `pass` would instead offer passed players and consume RNG
the monolith does not.

**Scope note.** Skat, Tarot, and Pinochle are *monoliths* — the auction is fused
with play and scoring in one Python function ([roadmap.md](roadmap.md)). The
auction extraction is the entry point, but the whole hand must land in the DSL
before the module is deleted: auction here, trick play on the Step 0 `round`,
scoring in Workstream 4. Bridge is already split (play is DSL), so it finishes
first and validates `auction` end to end.

## Workstream 2 — Betting and the pot (Seven-Card Stud)

The corpus's only betting game and first real chip economy (Coup already settled
resource amount + transfer-failure — [decisions.md](decisions.md), "Resource
amount syntax" / "Resource transfer failure").

- A `betting` definition over `round`: `ring` over non-folded players,
  accumulator = bet-to-match / last-aggressor / raises-so-far, move vocabulary =
  check / call / bet / raise / fold, termination = action closed. The legality
  rules already exist as `BettingRound` active-rules ([library.md](library.md)).
- A **pot** subsystem: chips as a resource, side-pot reconciliation by amount
  committed, distribution at showdown via `best_five_card_hand` (already a
  declared `runtime-primitive` signature).
- Multi-street: ante, bring-in, five betting streets (3rd–7th), showdown.

**Checkpoint (language gap candidate).** `reconcile_pots` needs "the pot that was
current when a player folded" — event-indexed state, flagged in
[building.md](building.md) as the first real gap candidate. Decide
`needs-formalizing` (expressible with existing loops/`let`/`transfer`/queries)
vs `language-gap`; if the latter, file `open-questions/<slug>.md` rather than
reaching into the runtime.

**Test-depth net.** Total-chips invariant exists; add a side-pot correctness
recompute before deleting `run_stud_hand`.

## Workstream 3 — Combinations and climbing (Tichu)

The first climbing game and first non-(rank,suit) cards. It introduces a
**combination model** reused later by Pinochle melds and Cribbage scoring (three
instances → promote to the standard library).

- A typed `Combination` value: type × length × strength, with a comparison
  (single / pair / triple / straight / full house / bomb).
- A `climb` definition over `round`: each turn plays a combination matching the
  led type and length and beating it, or passes; three passes end the trick.
- The four special cards as values/rules: Mahjong (leads, lowest, wish), Dog
  (hands lead to partner), Phoenix (wild / −25), Dragon (highest single, +25,
  trick to an opponent). Plus pushing (pre-play card passing) and the
  double-victory finish.

**Checkpoint (likeliest new axis besides Coup).** A **bomb** interrupts turn
order — any player, any time. Confirm whether that is a value on the
participants/order axes or a genuinely new interrupt axis; if the latter, it is a
signed-off axis change + open question, not an engine special-case.

Delete `run_tichu_hand` once green.

## Workstream 4 — Counting and in-play scoring (Cribbage, Schnapsen, Pinochle scoring)

This workstream builds the **`scoring_component` runtime subsystem**
([decisions.md](decisions.md), "Scoring composition" / "Triggered scoring
components"), which the runtime has so far folded inline ([roadmap.md](roadmap.md)).

- **Cribbage** — discard to the crib (offers), pegging as a `round` with a
  running-total accumulator and triggered components (fifteen / thirty-one /
  pair / run / last-card), then the show: combination scoring (fifteens, pairs,
  runs, flush, his-nob) applied to non-dealer hand, dealer hand, and crib. Re-home
  the module-level Cribbage scorers as standard-library combination queries.
- **Schnapsen** — marriages as an in-play declaration (`offer` that scores
  20/40), the trump-jack exchange (`offer`), and closing the stock (`offer` →
  the mid-hand open→closed phase-shape transition; its `claimed | talon_closed |
  open_play` outcome is already typed), with the two-phase follow rules.
- **Pinochle** — meld detection + scoring via the shared combination model, then
  trick play and point scoring.

**Test-depth nets.** Add Schnapsen's six-way settlement recompute (1/2/3 game
points) before migrating it; the Cribbage scorers are already unit-tested and
should keep that coverage as stdlib queries.

Delete `run_cribbage_hand`, `run_schnapsen_hand`, and the Pinochle scoring
remainder once green.

## Workstream 5 — Challenge, block, influence (Coup)

The furthest game from cards, and the construct [decisions.md](decisions.md) uses
to draw the in-scope line (a game that *defines* "challenge" vs. one that mutates
its own rules). Do it last, once the kernel is proven.

- `challenge` and `block` as response-window definitions over `round`: after an
  actor declares an action, a window in which others may challenge (priority
  order) → reveal/penalty, or block → a counter-window.
- Hidden-influence cards, the coin economy (resource), influence loss,
  elimination, and forced coup at ten coins.

**Checkpoint (highest new-axis risk).** The action → response → counter-response
nesting and simultaneous/priority windows are the sharpest test of the closed
axes. If they cannot be expressed as values on the existing axes, that is an
explicit signed-off axis addition plus an open question — this is exactly the
boundary the kernel is meant to make visible.

**Test-depth net.** Add a recompute that a challenge resolves to the correct
loser before deleting `run_coup_game`.

## Cross-cutting build-out

These land inside the workstreams above and are shared on the third use:

- generalized `round` axes — Step 0, the spine for all of it;
- the `scoring_component` runtime subsystem — Workstream 4;
- the resource/pot economy — Workstream 2, reused by Coup;
- the `Combination` model + queries — Workstream 3, reused by Pinochle and
  Cribbage.

## Recommended sequence

1. **Step 0** — generalize `round`; re-express the trick; migrate Hearts /
   Spades / Getaway off built-in `Trick` and delete it.
2. **Auctions** — Bridge first (already split, proves `auction`), then Pinochle
   bid → Tarot → Skat.
3. **Stud** — betting + pot.
4. **Tichu** — climbing + the combination model.
5. **Cribbage + Schnapsen + Pinochle scoring** — the scoring-component subsystem.
6. **Coup** — challenge / block / influence.

This is breadth-first by shape: it reaches `auction`'s third instance early and
keeps each step small. The alternative is depth-first on a single monolith (Skat
is the natural choice) to force the full kernel — auction, trick, and structured
scoring — to completion on one game before generalizing. That yields a complete
end-to-end proof sooner at the cost of less reuse upfront; it is a reasonable
swap for steps 2–5 if a single finished game is more valuable than incremental
breadth. Step 0 and Coup-last hold either way.

## Stage definition of done

- No per-game branch remains in `mechanics.py::instantiate`; the six
  `runtime/*.py` game modules and the three inline `run_*_hand` functions are
  gone; the built-in `Trick` mechanic is gone.
- All 13 games run on the kernel + in-DSL standard library; every
  `test_playout_*` is green; IR goldens regenerated and reviewed; `mypy
  --strict` clean; conservation invariants and the new recompute nets green.
- The `language-gap` list is zero or every entry is a named, deferred open
  question.
- Each promoted definition (`auction`, `betting`, `climb`, `challenge`, `block`,
  `trick`) is documented in [library.md](library.md), and
  [decisions.md](decisions.md) reflects any axis decision made along the way.
