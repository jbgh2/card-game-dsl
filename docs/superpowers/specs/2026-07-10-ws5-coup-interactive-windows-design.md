# WS5-Coup: interactive windows — design

**Signed off 2026-07-10** (the behaviour-change sign-off recorded as required by
[kernel-migration.md](../../kernel-migration.md), Workstream 5). Upgrades
Coup's six rng scope reductions to real player decisions, so those choices
enter the derived information sets. Rules source:
[docs/games/coup.md](../../games/coup.md) (Tchanturia 2012, already vetted
into the corpus). The partition checks (PR #39, `tests/openspiel_ready/`)
are the acceptance instrument; this branch rebases onto main once #39 merges.

## What changes, per rng site

| Today (rng primitive) | After (player decision) |
|---|---|
| `coup_random_target` | `steal(target : Player)`, `assassinate(target : Player)`, `coup(target : Player)` — declared Player parameter domain, `when:` guards exclude self/dead/empty targets. The turn `offer` enumerates them; the pick announces publicly. |
| `coup_challenger` (25% gate) | A challenge window: each other live player, clockwise from the claimant's left, is offered `[challenge, allow]`; first challenge closes the window. |
| `coup_fa_blocker` + `coup_duke_claim` | Foreign-aid block window: each other live player, clockwise from the actor's left, offered `[block_claiming_duke, allow]`; first block closes it. |
| `coup_block_roll` + `coup_steal_block_claim` | The steal target alone is offered `[block_claiming_captain, block_claiming_ambassador, allow]` — the claimed character IS the decision (the bluff). |
| `coup_block_roll` + `coup_contessa_claim` | The assassinate target alone is offered `[block_claiming_contessa, allow]`. |
| (no reveal — proven card returned hidden) | New `reveal` epistemic op: the proven card is publicly identified before it returns to the deck. |

Block claims are challengeable by every other live player *including the
original actor* (window over all but the blocker, clockwise from the
blocker's left) — same window pattern.

## Architecture decision: in-effect windows via pointer-walk + `offer`

Windows stay where they live today — inside each action's `effect` — with the
rng gate replaced by a decision poll. A challenge window is a single-pass
poll (no responder reacts to a later development), so the auction form's
`priority` machinery buys nothing; this design *revises* kernel-migration's
recorded "auction `priority` mode" direction accordingly, and the revision is
written back to that file in the same change. The poll uses the same
pointer-walk the turn loop already uses (`for each` has no ordered-list form;
grammar `for_each: "for" "each" NAME NAME`):

```
// challenge window on the actor's claim
challenged := false
window_open := true
responder := actor
repeat until not window_open {
  responder := coup_next_in_game(responder)
  if responder == actor { window_open := false }
  if window_open and influence[responder] is not empty {
    offer to responder one of [challenge, allow]
    if challenged { window_open := false }
  }
}
```

with nullary response move types writing phase state:

```
move_type challenge { effect { challenged := true; challenger := actor } }
move_type allow     { effect { } }
move_type block_claiming_duke      { effect { block_claim := "Duke" } }
move_type block_claiming_captain   { effect { block_claim := "Captain" } }
move_type block_claiming_ambassador{ effect { block_claim := "Ambassador" } }
move_type block_claiming_contessa  { effect { block_claim := "Contessa" } }
```

New phase state: `challenged : Boolean`, `challenger : Player` (meaningful
only while `challenged`), `block_claim : String` (`""` = no block),
`responder : Player`, `window_open : Boolean`. The existing
`challenge_stands` / `block_stands` result Booleans keep their roles.
Windows within one effect run sequentially and reset their state before each
poll, so one set of variables serves the action window, the block window,
and the block-challenge window.

**`offer` inside a `move_type` effect is the one new construct combination.**
It already parses (effects share the statement rule); surface totality
demands it be tested-legal or rejected — this design makes it tested-legal
(the runtime's `_offer` recurses through the same statement executor; the
plan adds direct unit tests plus the Coup usage). Nested response effects do
not themselves offer, so nesting depth is exactly two.

**Faithfulness note on serialization.** Real Coup's challenges are a race;
serializing responders clockwise from the claimant's left is the
tabletop-standard resolution and was already ruled faithful in
[decisions.md](../../decisions.md) ("Coup's challenge and block windows").
First-challenger-wins; later would-be challengers are never polled.

## The `reveal` epistemic op

A failed challenge (the claimant had the character) publicly shows the
proven card. New epistemic op, grammar kept to exactly the needed form:

```
epistemic_op: "shuffle" zone_expr                                   -> shuffle_op
            | "reveal" "one" "card" "from" zone_expr ["where" lambda] -> reveal_op
```

Semantics: evaluate the zone (single or family instance), select the first
card satisfying the filter (all cards eligible when no filter), **leave the
card where it is**, and emit `("reveal", <zone label>, <card string>)` to
**every** player's observation log. Revealing from an empty zone or with a
filter no card satisfies fails loudly (a game-description bug, never a
silent no-op). The event reaches every derived information state through the
log; the PR #39 partition machinery (obs-event embedding, the append probe)
covers the new event type with no new proof code.

Totality boundary: this is the whole implemented surface. The catalogued
family members that remain unimplemented — `peek`, `reveal to <subset>`,
multi-card/`all` reveals — are not grammatically expressible (the grammar
admits only this form), so nothing is accepted-but-ignored.
[library.md](../../library.md)'s memory-operations entry is updated: `reveal`
(public, one card, from a zone) is built; `peek` and observer-subset reveals
stay catalogued with their forcing function stated explicitly — an epistemic
event with **no physical-zone counterpart** (a private look, a
show-to-partner). Public full reveals of a *location* remain zone
projections' job.

Coup's proven-challenge sequence becomes:

```
reveal one card from influence[claimant] where c => c.rank == claim
move one card from influence[claimant] where c => c.rank == claim to court_deck
shuffle court_deck
deal one card from court_deck to influence[claimant]
```

**Recorded residual (accepted at sign-off):** the return movement is
count-projected (hidden hand → deck), so an observer's formal information
state cannot exclude the world where the claimant kept the shown copy and
returned their other card. The runtime always returns a claim-ranked card
(the filter guarantees it), so no observer holds a false belief; the
partition is epsilon coarser than tabletop common knowledge on exactly this
point. If a future consumer needs that bit, the public-transit encoding
(moving the proven card through a public zone) closes it without new
language surface.

## Retained modeling conventions (unchanged, now explicit)

- **Eliminated players' coins return to the treasury** (preserves the
  50-coin conservation invariant; the rulebook is silent and the coins are
  strategically inert either way).
- **Assassination and coup costs stay paid** even when the action is
  challenged away or blocked (real rule; already encoded).
- **Forced coup at 10 coins** falls out of the `when:` guards (already
  encoded; the guards extend to the new `target` parameters).
- The **influence-loss idiom** (`for each player q: if q == X { move chosen
  one card ... }`) stays as-is; migrating it to an `as` block waits on
  [open-questions/single-actor-binding.md](../../open-questions/single-actor-binding.md).

## Deletions

From `cardlang/runtime/coup.py`: `coup_random_target`, `coup_challenger`,
`coup_fa_blocker`, `coup_block_roll`, `coup_duke_claim`,
`coup_contessa_claim`, `coup_steal_block_claim`, and the probability
constants. Surviving primitives are all pure: `coup_players_in`,
`coup_next_in_game`, `coup_has_char`, `coup_note_reveal`,
`coup_game_summary`.

## Acceptance

1. **New goldens, re-pinned deliberately** — the rng stream changes
   wholesale (random play now challenges/blocks uniformly at the offers):
   `tests/golden/coup_scores.json` (reveal-sequence, 40 seeds) and the
   migration-characterization entries. `max_length: 500` re-measured over
   300 random seeds (measured max 57 decisions — uniform challenges shorten
   games; the bound keeps ~8x headroom). **Termination finding (recorded at
   implementation):** the interactive game has legally unbounded lines — an
   exchange-forever, never-challenge table makes no coin progress, so the
   greedy lowest-id line loops and hits the backstop. Coup therefore does
   NOT join the adapter walk-to-terminal set (`adapter_terminal_steps`
   stays unset; the coverage record says `terminal=False` honestly), and
   the raise-vs-graceful-terminal question is filed as
   [open-questions/unbounded-lines-and-max-length.md](../../open-questions/unbounded-lines-and-max-length.md).
2. **Partition proofs green** (after rebase onto merged #39): the full
   `tests/openspiel_ready/test_coup.py` suite with re-measured `depth` and
   `adapter_terminal_steps`; swap axis stays `"suit"` (court cards share the
   one `court` suit — same-suit pairs are the character swaps).
3. **Dedicated observational tests**: a challenge decision reaches every
   player's log and information state (it is a public announce); a `reveal`
   event reaches every player's log and information state verbatim; a
   blocked foreign aid transfers no coins.
4. **Offer-in-effect unit tests** independent of Coup (a minimal fixture
   game), so the construct combination is pinned by more than one game.
5. `mypy` (bare) and full `pytest -q` green before push, as always.

## Docs in lockstep (same change)

- `docs/games/coup.md` + `coup.cardlang` rewritten (the spec examples above).
- `docs/kernel-migration.md` WS5 section rewritten in place: status becomes
  done-at-real-scope for Coup; the auction-priority direction revised to the
  poll pattern; Tichu's remaining reductions stay recorded.
- `CLAUDE.md` honesty note: Coup's scope reductions removed from the caveat;
  Tichu's remain until the Tichu pass.
- `docs/library.md`: `reveal` moves from catalogued to built (with the
  totality boundary above); memory-operations list annotated with the
  forcing function for `peek`/subset-reveal.
- `docs/open-questions/structural-infoset-proofs.md`: the "two standing
  caveats" paragraph narrows to Tichu-only.
- `docs/decisions.md` "Coup's challenge and block windows" paragraph: the
  parenthetical about the random-play scope updated to describe the
  interactive encoding.

## Out of scope

Tichu (its own pass: Dragon routing + call windows, real rules verified
against Pagat first); challenge/block stdlib promotion (third-instance rule —
this is instance one and two of the window pattern at most);
`peek`/subset-reveal; representative playouts.
