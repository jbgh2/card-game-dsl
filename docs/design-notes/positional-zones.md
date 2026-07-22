# Positional zones — analysis and rationale

The normative rules live in [decisions.md](../decisions.md), "Position
domains and positional zones". This note records the analysis behind them:
what Klondike forced, what FreeCell disproved, and the alternatives that
were rejected. Klondike ([games/klondike.md](../games/klondike.md)) and
FreeCell ([games/freecell.md](../games/freecell.md)) are the corpus
anchors.

## What Klondike forces

Three apparent requirements, from the tableau:

1. **Addressable places.** Seven columns that rules must name and moves
   must parameterize over ("move the run from column 3 to column 6") — a
   zone family indexed by something that is neither a player nor a team.
2. **Per-position visibility.** A column holds face-down cards below and
   face-up cards above; the boundary moves as cards flip.
3. **Stack movement.** A properly-ordered face-up run moves between
   columns as a unit, and the flip of a newly exposed card must be an
   observation event the kernel emits — never a hand-authored rule.

## The load-bearing move: per-position visibility is zone decomposition

The tempting design — a per-card `facing` bit inside one zone, with the
projection function reading it — would break the projection model's core
economy: a zone's visibility would no longer be a property of the *zone
type* but of each card's runtime state, and every consumer of
`ZONE_PROJECTIONS` (observation emission, the info-state builder, the
partition proofs) would need a second, state-dependent path.

Instead, **a mixed-facing pile is two stacked zones**: a face-down family
(`tableau_down[column] : HiddenStack<column>`, `count_only` to everyone)
underneath a face-up family (`tableau_up[column] : Cascade<column>`,
`identity` to everyone). The flip is an ordinary kernel movement —
`draw 1 card from tableau_down[c] to tableau_up[c]` — and the observation
event derives from the two declared projections exactly like every other
movement: the source side contributes a count, the destination side the
card's identity. The "reveal" every observer sees when a tableau card
flips face-up **is** that movement event. No new visibility machinery
exists; projections stay uniform per zone; info sets stay derived from
the same two ingredients as ever (zone projections + emitted events).

The cost is honest and small: game files write two zone families where the
table shows one physical pile, and the flip invariant ("when the face-up
part empties and face-down cards remain, flip one") is written in the
move effects that can expose it. The benefit is that *nothing* in the
knowledge model changed — the projection lattice, the emission rules, and
the proof machinery are untouched.

## Orthogonality: what FreeCell proves

FreeCell uses the same positional machinery — `column[col] :
Cascade<col>`, `cells[slot] : Cell<slot>`, `foundation[suit] :
Foundation<suit>` — with **no** `HiddenStack` anywhere: every zone is
`identity` to all, so every observation event carries full identity and
the sole player's information set is a singleton per state. Positional
structure (index domains, order, `top_of`) and informational structure
(the projection a zone type declares) are fully orthogonal: FreeCell
engages the first and degenerates the second, and it carries zero
visibility machinery it does not need. That is the collapse test the
candidate entry asked for, and it passes by construction — the positional
constructs never mention visibility, and the visibility constructs never
mention position.

## Order, orientation, and the observable contract

Runtime zones were already ordered lists; positional zones make the order
*meaningful*, so the orientation is now pinned (decisions.md has the
normative statement):

- Arrivals **append at the sequence's end** — placing on top of a face-up
  pile. `top_of` reads the end, `bottom_of` the front.
- The dealt take (`draw`/`deal` with no `where`) removes from the
  **front** — FIFO. For a shuffled stock the two ends are
  indistinguishable, so nothing observable changed for the existing
  corpus. For Klondike's stock cycle FIFO is exactly the physical rule:
  `move all cards from waste to deck` then drawing front-first reproduces
  turning the waste pile over — the first card drawn last pass is the
  first card drawn this pass.
- A filtered movement (`move all cards from Z where … to W`) selects in
  source order and appends in that order — already the pinned semantics
  of `_select_filtered`; positional zones simply rely on it.

Order knowledge needs no new projection level. The `identity` snapshot in
the info state renders a sorted multiset, but an observer entitled to a
zone's identity saw every arrival as an event, and the observation log is
part of the information state — so sequence knowledge is *derived from
history under perfect recall*, which is the same story the rest of the
knowledge model tells. Two worlds with differently-ordered cascades
necessarily have different histories, hence different logs, hence
different information states.

## Stack movement needs no new movement primitive

A cascade's face-up run is an invariant of the building rules: it is
always a strictly-descending, alternating-color sequence from its base
(cards only arrive by legal builds on top, and only leave as a
suffix-with-everything-above). Because ranks strictly descend upward,
"card X and everything above it" is *denotable by a rank filter*: the
suffix moving onto a destination whose top card has rank value `v` is
exactly `move all cards from tableau_up[src] where rank_value(card) < v
to tableau_up[dst]` — the existing filtered movement, whose
order-preservation is already pinned. Moving a king-based run to an empty
column is `move all cards from tableau_up[src] to tableau_up[dst]`. So
"stack movement" is a *usage pattern* of the existing movement verb, not
new surface — the design deliberately spends its one new construct on
position domains and keeps movement closed.

(Games whose piles are not rank-monotone runs — Spider's same-suit
removal is close but still monotone — would force a positional slice
("from card X up") as real surface. That is recorded as deferred in
[roadmap.md](../roadmap.md), behind the existing movement-filter wall: a
non-denotable selection simply has no sentence that expresses it.)

## Adjacency

Klondike and FreeCell reference *rank* adjacency (build down by one) and
*emptiness* of places — never column adjacency (column 3 is not "next
to" column 4 in any rule). So position domains deliberately carry **no
successor/neighbour algebra**: a position value is an opaque integer key
usable in `[...]` subscripts and comparable with the ordinary integer
operators (FreeCell's lowest-empty-cell convention, were a game to want
it, is expressible as a guard over `<`). Spatial adjacency (a tableau
where builds cross columns, or a board where a piece's moves depend on
neighbouring cells) is deliberately not a `neighbours`/offset algebra
over bare `positions {}` integers: it arrives on **board-minted**
position domains as declared entry data. That mechanism landed for
boards ([decisions.md](../decisions.md) "Boards and cells") — the
`lines(k)` register is its first form; richer relations (neighbours,
regions) arrive as further board-entry data with their witnesses
([board-topology.md](board-topology.md)).

## Alternatives rejected

- **Per-card facing state + state-dependent projection.** Rejected above:
  it forks every projection consumer and hand-authors the flip
  observation. The two-zone decomposition emits it from the kernel.
- **Named singleton zones (`tableau1`…`tableau7`).** Kills move
  parameterization (a move cannot range over zone *names*), multiplies
  every rule by seven, and leaves "which column" out of the action space.
- **A static `column` row in the domains registry.** The registry's rows
  are game-independent; column counts are per-game (7 vs 8) and
  per-family (`cell : 1..4` beside `column : 1..8` in FreeCell). Hence
  *declared* domains, reconciled against the built-in registry by a
  collision wall so the two sources can never disagree.
- **Extending `zone_key_of` to positions.** The domains table conflated
  "can index a zone family" with "an observer owns a key". Positions
  split it: they are indexable but unowned — `zone_observer_key` returns
  "no key" for every observer, so every observer gets the `others`
  projection. Ownership-differentiated zone types (`Hand`,
  `HiddenPile`, …) on a position index are therefore *rejected* — their
  owner projection would be unreachable, an accepted-but-ignored cell.

## The canonical-gather interaction, resolved explicitly

The canonical gather (`move all cards to <zone>`) collects **zones** in
lexicographic name order — it never sorts *cards*. For a positional
family this means: instances gather in ascending position order (the
family's key order), and each instance's internal sequence is preserved
as it lands. So gather over positional zones is deterministic and
order-preserving per zone, and the canonical rule needed no amendment —
the trap ("a positional zone must not be name-sorted on gather") does not
bite because name-sorting applies to the zone collection, not to a zone's
contents. Neither solitaire game gathers (single deal, no hand loop);
this paragraph exists so the interaction is settled rather than silent.

## One-player games

Klondike and FreeCell are the corpus's first 1-player games. The kernel,
seating ring, `turns` form, adapter, and returns computation are all
count-generic and needed no change; the openspiel_ready *harness*'s
hidden-swap and own-view proofs assume opponent hands, so the two proof
modules override those with the 1-player analogues (Klondike: a
chance-hidden swap between two zones hidden from the sole player;
FreeCell: a proof that no hidden card exists to swap) — per-game caveats
and rationale live in the proof modules, per the standing convention.
