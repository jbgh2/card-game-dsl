# Board topology: the concrete design and the witness ladder

*Status: a concrete proposal — further committed than
[generalization-path.md](generalization-path.md) §1's axis sketch, but
still a design note, not settled spec. It rests on two research
documents: [research/board-topology-rules-language.md](../research/board-topology-rules-language.md)
(what ~60 board games are) and
[research/topology-and-query-requirements.md](../research/topology-and-query-requirements.md)
(what the language must support to host them — the two-primitive core,
the query classes, the nine hidden-information patterns, the six
capability candidates C1–C6). This note does not restate that analysis;
it decides what the analysis explicitly left open: the shape of the
declarations, **which witness games gate which implementation stage**,
and the staging against the engine's registries. Per corpus-first
discipline, nothing here is built speculatively — each rung graduates by
its game entering [games/_candidates.md](../games/_candidates.md), then
the corpus, forcing its constructs. The witness entries are filed there
under "Boards: the topology witness ladder".*

## 1. The shape of the design, in one paragraph

A **board is an indexed family of zones plus declared static data about
their indices**. The board declaration (a closed stdlib registry entry,
the same medicine as decks) generates a finite `Cell` value domain,
named **relations** (edge sets), named **regions** (cell subsets), and
named **lines** (pattern triples/tuples); a game's `zones {}` block then
declares a zone family indexed by `cell` exactly as it declares one
indexed by `player`. Pieces are ordinary zone **contents** — a piece set
is a registry entry in the deck family (side as suit, kind as rank,
with multiplicities). Placement and movement are the **existing kernel
movement** between cell zones and ordinary off-board zones (reserves,
captured piles, the bar), so observation events emit through the
declared projections at the sites that already exist, and information
sets derive with **no new observation machinery for the entire
perfect-information family**. Decisions are parameterized moves whose
`Cell` parameters join the closed declared-domain set — a fixed
cross-product the OpenSpiel adapter ids once and guards mask per state,
exactly the contract `Player`/`Rank` parameters already satisfy
([decisions.md](../decisions.md) "Declared parameter domains"). The
topology itself is **meaning, never state**: pure data consulted by
closed query verbs, per the two organizing principles of
[generalization-path.md](generalization-path.md) §0.

Two alternatives were weighed and rejected, briefly, because the
requirements analysis already did the heavy arguing:

- **A monolithic board primitive** (one zone holding a position→piece
  map, with its own visibility and its own movement verbs) rebuilds the
  projection/emission machinery as a second, parallel moat, and its
  intra-zone moves would run outside today's observation sites — the
  escape-hatch pattern at the scale §1 of generalization-path warns
  about. The requirements doc's pivotal reuse ("making cells zones is
  what lets the visibility model extend to boards without a parallel
  mechanism") is the same verdict from the other direction.
- **Bridging an external engine** (wrapping Ludii or OpenSpiel native
  boards) hand-authors information sets per bridge and composes with
  nothing; [kernel-extensibility.md](kernel-extensibility.md) §3 already
  answers this fork.

The one place the moat *deliberately* moves is Stratego-class attribute
hiding (C3/C6), staged below as its own workstream with the partition
proofs as the acceptance bar — per
[domain-map.md](domain-map.md)'s stillness test, a signed-off moat-level
event, never a side effect of a game PR.

## 2. The model, concretely

### 2.1 The board declaration

A game selects a board the way it selects a deck — by name, from a
closed stdlib registry, never by hand-enumerating cells
([domain-map.md](domain-map.md) names per-game cell enumeration as the
nullary-explosion wall returning):

```text
board: grid(3, 3)          // tic-tac-toe
board: grid(8, 8)          // breakthrough, draughts (with dark-squares region)
board: hex_rhombus(11)     // hex
board: morris9             // nine men's morris (enumerated graph)
board: backgammon_track    // 24 typed points + bar + off, per-player direction
```

A registry entry — generated (grids, hex tilings, tracks) or enumerated
(morris9) — defines, as static data:

- **Cells**: the finite position set, minted as value constants
  (`a1 … h8`, `p1 … p24`) in the same way a deck mints card and rank
  constants. `Cell` becomes an enumerable value type of the game,
  exactly parallel to `Rank`.
- **Relations**: named edge sets — `orthogonal`, `diagonal`,
  `dark_diagonal`, hex adjacency, track successor. Where a game's
  movement is rank-asymmetric, the entry also carries **per-player
  frames**: `forward(player)` and `forward_diagonal(player)` resolve to
  opposite concrete relations per seat — one shared graph, a declared
  per-player transform, never a second board (the requirements doc's
  ownership/mirroring property).
- **Regions**: named cell subsets — `back_row(player)`, `home(player)`,
  `bar`, `off`, the lakes' complement on the Stratego board.
- **Lines**: named tuple sets for pattern rules — `lines(3)` on a grid
  (rows, columns, diagonals of length 3, statically enumerated), the
  16 mills of `morris9`.
- **Jump triples**, where the family has them: `(from, over, to)`
  triples for the draughts jump — declared data, so guards and effects
  look up the captured square instead of computing geometry.

Everything in the entry is **closed data with integrity pins from
birth** ([decisions.md](../decisions.md) "Closed-domain completeness"):
every relation total over the entry's cells and symmetric where
declared, jump triples consistent with their base relation, lines and
regions subsets of the cell set — all pinned by a static test derived
from the registry, with a loud runtime refusal as the backstop. An
in-file bespoke graph syntax is deliberately deferred: five ladder
games use five registry entries, and the first game whose board is
genuinely one-off (a Catan-shaped map) is the witness that forces the
in-file form.

### 2.2 Cells are zones

The `zones {}` block gains cell-indexed families; the index-role set
(today exactly `player`/`team` — [domain-map.md](domain-map.md), the
Decision registry) grows by `cell`:

```text
zones {
  square[cell]     : BoardCell          // identity to all, capacity 1
  point[cell]      : Point              // identity to all, unbounded stack (backgammon)
  ocean[player][cell] : HiddenCell<player>  // identity to owner; nothing to others (battleship)
  reserve[player]  : PlayerPile<player> // unplaced pieces, public
  captured[player] : PlayerPile<player>
}
```

The new zone types are rows in the same closed registries as every
other zone type (`LIBRARY_ZONE_TYPES` + `ZONE_PROJECTIONS`,
`cardlang/stdlib/zones.py`, with `ZONE_PROBES` rows in the same
change): `BoardCell` = identity to all; `Point` = identity to all,
stack; `HiddenCell<Owner>` = identity to owner, trivial to others.
**Capacity** is a zone-type property (capacity 1 for `BoardCell`,
unbounded for `Point`), enforced as a loud runtime wall and respected
by movement guards. This is C1 of the requirements doc — per-position
zone families sharing a projection policy — and it is the entire
visibility story for boards: projections attach to cells because cells
are zones.

The double-indexed family (`ocean[player][cell]`) is one genuinely new
index shape — Battleship needs a board *per player*. It composes the
two existing index roles rather than inventing a third.

### 2.3 Pieces are contents

A piece set is a registry entry in the deck family — the `pieces:`
clause names it, mutually exclusive with `cards:` until a game
witnesses needing both:

```text
pieces: xo_marks           // { sides: { [x, o]: [mark] }, copies: 5/4 }
pieces: draughts_men       // { sides: { [white, black]: [man, king] }, 12 men + 12 kings per side }
pieces: stratego_barrage   // { sides: { [red, blue]: [flag, spy, scout, miner, general, marshal, bomb] }, scout ×2 }
```

Side plays the structural role suit plays for cards; kind plays rank;
multiplicities are the Pinochle mechanism. This is why the content axis
needs **no new machinery at all**: indistinguishable tokens are
duplicate "cards" (identity projection of two copies is the same
multiset — the fungibility Pinochle already models), and Stratego's
individuated hidden ranks are exactly what card identity under a hiding
projection already is. `pieces:` is a distinct head word rather than a
reuse of `cards:` because the two name different physical kits a cold
reader must distinguish — one concept per word, not a paraphrase pair —
but this is a surface call to ratify, flagged in §5. `ranking:` stays a
card-deck clause: piece interactions that look rank-like but are not a
linear order (spy beats marshal) are per-game pure functions, which is
the "meaning is interpretation" principle doing its job.

The movement construct reaches pieces through its **item-noun slot**,
which [decisions.md](../decisions.md) "The operation vocabulary"
deliberately holds open (`cards` today, "so a resource transfer can one
day be the same construct"): `move one piece from reserve[actor] to
square[at]` is the same movement production with a second noun, not a
second construct.

Promotion (draughts man → king) is a supply swap — move the man to the
supply, move a king from the supply to the cell — two public kernel
movements, observation-clean, no pose machinery needed for fungible
pieces. (Pose remains axis 2's mechanism for *individuated* pieces
whose identity must persist through the change.)

Off-board structure is ordinary zones throughout: reserves for
unplaced pieces, captured piles, the backgammon bar and bear-off tray,
the battleship fleet-before-placement. This is where the card
machinery is reused verbatim, and it is most of every game's zone list.

### 2.4 Decisions: `Cell` joins the closed parameter domains

```text
move_type place(at : Cell) {
  when: square[at] is empty
  effect { move one piece from reserve[actor] to square[at] }
}

move_type step(from : Cell, to : Cell) {
  when: occupant_side(from) is side_of(actor)
        and to in neighbors(from, forward_diagonal(actor))
  effect { move all pieces from square[from] to square[to] }
}
```

`Cell` enumerates its board's declared cell list — a fixed-from-
declaration domain exactly like `Rank` — and cross-products with other
parameters under the settled guard-filtered-mask contract: the
OpenSpiel action space reserves one id per combination, fixed for the
game, and the guard masks it per state
([decisions.md](../decisions.md) "Declared parameter domains"). A
`(from, to)` pair over an 8×8 board is 4096 ids; where that is
wasteful the vocabulary can carry a small declared direction enum
instead (`step(from : Cell, dir : Direction)` — 64 × 3), which also
matches how the native OpenSpiel board games encode moves. Adjacency,
occupancy, and path-clearness live in guards as **masks**, never as
domains that grow or shrink. Every board decision is therefore an
ordinary parameterized `offer` — one flat candidate list, one chooser
draw, one announce — and the no-implicit-actions wall
([decisions.md](../decisions.md)) carries over unchanged: a player
with no legal placement is a phase-termination predicate, never a
silently skipped turn.

Sliding moves (the Stratego scout; later rooks and bishops) stay one
decision: the guard demands a clear path (`between(from, to)` empty —
a class-2 query over declared data), not a per-step decision chain.
Draughts multi-jumps are the opposite: each hop **is** a decision, and
the `turns` form's `again` axis ([decisions.md](../decisions.md) "The
`turns` form") plus a `Cell?`-typed chain-anchor state variable
(public, as all state is) expresses "same piece continues" — with
mandatory capture as an ordinary rule whose demand narrows the
vocabulary to jumps when any exist.

Compound placements (a battleship spanning four cells) are one
decision whose **effect** runs a bounded sequence of kernel movements
— `place_ship_h(at : Cell)` computes the footprint from declared data
and moves each segment; every movement emits through the (hidden-cell)
projections at the existing sites. No atomic-multi-placement machinery
is needed for the ladder.

### 2.5 Queries: closed verbs over declared data

The query surface is the requirements doc's class 1–6 inventory,
admitted rung by rung, each verb a closed stdlib function
(registry + signature + dispatch, per
[domain-map.md](domain-map.md)'s Decision/Description pins) reading
only declared topology data and zone contents:

- **Wave A** needs classes 1–4 only: `neighbors`, `is_adjacent`,
  `occupant`/`is_empty`, `between`, region membership, line
  enumeration (`any line in lines(3) where every cell held by p`),
  track advance with landing policy (backgammon's exact bear-off). The
  cell-query surface mirrors the card-query register — `cells in
  <region> where <pred>`, `number of cells in …`, `any/all cell(s)
  in … where` — one spelling per concept, lifted to positions.
- **Wave C's gate** is the class-5/6 fixed point: `reachable(from,
  to, via, connectivity)` and `region(seed, same_by, connectivity)` as
  **built-in primitives that own their loops**, terminating in at most
  |cells| expansions by construction, with deterministic frontier
  order so replay stays pure. This is the "bounded reachability
  primitive" generalization-path §1 calls the real design object; Hex
  is its isolated witness.
- **Class 7** (longest-path optimization) and **class 10**
  (`holds_after` hypotheticals) are named now and rejected loudly
  until their witnesses arrive (surface totality: a named-but-
  unimplemented verb is a resolve-time error with a message, never a
  silent accept). English draughts is chosen over International
  *specifically because* its capture rule never maximizes — class 7
  stays out of the ladder entirely.

Predicates shared between a move guard and a termination predicate
("no legal move" — blockade loss in morris and draughts) are named
functions, the existing mechanism; move-existence (class 8) at ladder
scale is a bounded quantification over the declared vocabulary's
domains with the same guards, not new machinery.

### 2.6 Chance: the `roll` statement

Backgammon forces the first mid-game chance nodes. Today the engine's
randomness folds entirely into the root seed (one OpenSpiel chance
node; replay is a pure function of `(seed, history)`) — so `roll d6 as
d1` is **a replay-model change, not a registry entry**, exactly as
[domain-map.md](domain-map.md)'s tripwire says: a kernel chance site
that suspends like a decision with the chance actor, whose outcome
enters the action history and announces publicly through the existing
event vocabulary. CFR and IS-MCTS consume explicit chance nodes
natively; the seed keeps covering shuffles. A board game with no deck
and no roll has no chance at all, and the adapter's root chance node
degenerates accordingly. This lands as its own stage (below) with the
seed/rng non-observability proof extended to roll sites.

### 2.7 Information sets: what moves, and when

- **Wave A moves nothing.** Perfect-information boards are the trivial
  case of the hardest machinery: every cell zone projects identity to
  all, every movement announces itself, information states are common
  knowledge. The proof harness still runs per game (indistinguishability
  degenerates, adapter agreement and conformance do not), which is
  precisely why wave A de-risks topology mechanics without touching the
  moat.
- **Battleship adds C2, the probe action** — the evaluation half of
  "announce a declared pure predicate of a hidden zone's true
  contents" (`announce hit if ocean[opp][at] is not empty`); the
  emission half is the existing `announce`. A shot result is a
  **public function of hidden contents** — the compound
  hidden-function probe
  [open-questions/structural-infoset-proofs.md](../open-questions/structural-infoset-proofs.md)
  is blocked on, in its board-shaped form (Cheat is the card-shaped
  one). Per [domain-map.md](domain-map.md), budget the probe-action
  capability and that proof-generator work together.
- **Stratego Barrage adds C3 + C6 — the one moat-level event.**
  Position public, rank private-to-owner is a per-attribute projection
  (the emission classes grow beyond
  identity/count_only/trivial), and the opponent must track *which*
  unknown piece moved (anonymous-persistent identity on movement
  events). The requirements doc ranks both defer-until-second-witness
  in general; the ladder includes exactly one such game because the
  board design space is not honestly covered without hidden pieces,
  and Barrage is its minimal form. Acceptance is the extended
  partition-proof battery, extended **before** the game lands. Combat
  (both ranks revealed, loser removed — a second compound probe) and
  movement-derived narrowing (a moved piece is no bomb; a multi-square
  move is a scout) then fall out of candidate-set semantics over the
  observed history, with the swap proofs as the check that they fall
  out *correctly*.
- **The spatial leak lint** (a query over contents the observer cannot
  see, whose result the observer can see) is flagged in the
  requirements doc and owned by the knowledge model; the probe action
  is its sanctioned channel. The lint's design is not this note's to
  settle, but stages 4+ must not land without at least the dynamic
  (swap-proof) side covering it, which the existing battery already
  does.

## 3. The witness ladder

### 3.1 Selection criteria

Following the corpus model: each game earns constructs, jointly they
cover the design space, and none brings machinery another rung already
earned. Board-specific criteria, in priority order:

1. **A native OpenSpiel implementation as a differential oracle.**
   GOPS set the precedent ([games/gops.md](../games/gops.md)): a
   compiled game validated game-tree-against-reference is the
   strongest external check available. Seven of eight rungs have one
   (verified against the live registry); Barrage, the exception, is
   flagged.
2. **One new mechanism per rung.** Each rung changes exactly one thing
   relative to its predecessors, so a divergence has one suspect —
   the staging in §4 is this criterion, operationalized.
3. **Structural termination before open-ended play.** Monotone games
   (placement fills, pieces only advance, shots accumulate) cannot
   cycle, so they land before
   [open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md)
   is settled; cyclic games (morris, draughts) are gated on it —
   [domain-map.md](domain-map.md)'s "settle before the first
   open-ended board game", honored in the ordering.
4. **Perfect information before hidden, hidden in capability order**
   (C1 → C2 → C3/C6), per the requirements doc's ranking.
5. **Exact variant pins with public rule sources.** Pagat is a card
   site; board rungs pin to the named rulebook/reference in their
   candidates entry, with the OpenSpiel implementation as the
   executable tiebreaker where one exists.

### 3.2 The ladder

**Wave A — perfect information, deterministic, monotone.** The moat
does not move.

1. **Tic-tac-toe** (`grid(3,3)`; oracle `tic_tac_toe`, thoroughly
   tested). The walking skeleton: board declaration, `Cell` domain,
   cell-zone families, placement, `lines(3)` patterns, `turns` on a
   board, draw-on-full-board. Everything after it changes one thing.
2. **Breakthrough** (8×8; oracle `breakthrough`, thoroughly tested;
   parameterizable to 6×6 if tree size matters). Adds movement:
   per-player frames (`forward(p)`), step and diagonal-capture
   vocabulary, displacement capture, reach-region win. Still monotone
   — pieces only advance.
3. **Backgammon** (single game, no doubling cube; oracle `backgammon`,
   thoroughly tested, explicit-stochastic). Adds exactly the chance
   workstream: `roll`, doubles, the track entry with typed points,
   stacks with capacity semantics (blots, made points as count
   guards), bar re-entry, exact-policy bear-off, race win. The
   doubling cube is a wager layer excluded from the pin (matching the
   oracle's scope); it is separately interesting — a stake-state
   mechanic, not topology — and can be a later variant delta.

**Wave B — hidden information on boards, in capability order.**

4. **Battleship** (10×10; 1990 Milton Bradley fleet 5-4-3-3-2;
   repeated shots illegal; hit/miss announced per shot, ship type
   announced on sink; oracle `battleship`, imperfect-information and
   CFR-consumable, parameterized to match: default `ship_sizes
   [2;3;3;4;5]`, `allow_repeated_shots=false`, `loss_multiplier=1.0`
   for zero-sum). Adds C1-hidden (owner-identity boards, the
   double-indexed family) + C2 (the probe action); placement via
   footprint effects; still monotone (legal shots strictly shrink).
   Feeds the structural-infoset-proofs compound probe directly.
5. **Stratego, Barrage variant** (10×10 with lakes; 8 pieces per side:
   Flag, Spy, 2 Scouts, Miner, General, Marshal, Bomb; two-square
   rule in scope, chase rule scoped out and named in the entry; **no
   native oracle** — verified absent from OpenSpiel; DeepNash was
   never open-sourced). The moat rung: C3 attribute-level projections
   + C6 anonymous-persistent identity, partition proofs extended
   first, acceptance by proof battery instead of differential. Also
   the second compound probe (combat) and free setup as hidden
   placement decisions. Banqi and Luzhanqi are the named second
   witnesses if C3/C6 generality is later in doubt; dark chess-family
   games stay out (attempt-feedback, below).

**Wave C — the query frontier, then open-ended play.**

6. **Hex** (11×11, no swap rule, matching the oracle default; oracle
   `hex`). One addition: the class-5 `reachable` fixed point (win =
   your stones connect your two sides), on a hex tiling entry.
   Monotone and drawless (placement only), so it needs neither the
   chance nor the unbounded-lines machinery — its position this late
   is purely that `reachable` deserves an isolated rung.
7. **Nine Men's Morris** (with the flying phase; oracle
   `nine_mens_morris`). Adds the enumerated non-grid graph, the
   place→move→fly phase shift, mills as declared lines with a removal
   decision (and the may-not-remove-from-a-mill-unless-forced
   restriction), blockade loss, and the first cyclic movement — gated
   on settling unbounded-lines-and-max-length (the draw rule: align
   the pin with the oracle's termination rule at entry time).
8. **English draughts** (8×8, 12 men; captures mandatory, chosen jump
   sequences completed, crowning ends the move; 40-move no-capture
   draw, matching the oracle `checkers`, which implements forced
   captures and that exact draw rule). Adds rule-driven demand
   narrowing (mandatory capture as rule composition), jump triples,
   multi-jump chains on the `again` axis, promotion, counter-based
   draw state. English over International deliberately: no
   maximum-capture optimization, so class 7 stays unwitnessed.

### 3.3 Coverage

Each mechanism's earning rung (first column it appears in is the rung
that forces it; every rung earns at least one):

| Mechanism | TTT | Brk | BG | Bshp | Barr | Hex | NMM | Drts |
|---|---|---|---|---|---|---|---|---|
| Generated grid + `Cell` domain + cell zones (C1) | ● | | | | | | | |
| Placement vocabulary + line patterns + full-board draw | ● | | | | | | | |
| Movement vocabulary + per-player frames + reach-region win | | ● | | | | | | |
| Track entry, stacks/capacity, `roll` chance, race win | | | ● | | | | | |
| Hidden per-player boards (C1-hidden), probe actions (C2), footprint placement | | | | ● | | | | |
| Attribute projections (C3), anonymous identity (C6), combat probe | | | | | ● | | | |
| Hex tiling, `reachable` fixed point (class 5) | | | | | | ● | | |
| Enumerated graph, phase-shift, declared mills + removal decision, blockade loss | | | | | | | ● | |
| Mandatory-capture rules, jump triples, `again` chains, promotion, draw counters | | | | | | | | ● |
| Differential oracle | ● | ● | ● | ● | — | ● | ● | ● |

Deliberately **not** on the ladder, with reasons recorded so they are
not re-litigated:

- **Snakes & Ladders, and pure racing tracks**: no decisions — nothing
  for an information-set engine to prove, and the track reduces to
  integer state anyway (requirements doc, "what reduced away").
- **Ludo/Pachisi (OpenSpiel `maedn`)**: every mechanism is backgammon's
  minus stacks; adds only multi-token routing sugar. Fine later
  corpus growth, not a rung.
- **Connect Four, Gomoku, mnk-games**: line patterns are TTT's;
  gravity is one derived-placement guard. Near-free corpus growth
  after wave A, not rungs.
- **Phantom tic-tac-toe, dark hex, Kriegspiel, RBC**: attempt-feedback
  games — the player does not know their legal moves, which
  [generalization-path.md](generalization-path.md) §5 records as a
  knowledge-model boundary (with the "legality reads only
  observer-visible information" lint as its gate), not a topology gap.
- **Chess family**: check legality is `holds_after` iterated per
  candidate (class 10 under class 8), plus castling/en-passant
  compounds, plus repetition history — three gates past the ladder's
  end. Dark chess additionally fails the info-state contract its
  oracle would need to differentially check.
- **Go**: superko needs position history the engine deliberately does
  not track; area scoring is class 6 at scale. After the ladder, if
  ever.
- **Quoridor**: mutable topology (walls delete edges) crossed with
  reachability-per-candidate legality (classes 8×10×5), and its
  oracle carries known encoding issues. The named witness for
  topology-as-state, deferred with it.
- **Tile-layers (Carcassonne, Hive)**: growth mutability, segment
  grain, no oracles — the requirements doc's "strictly harder than
  OpenSpiel's board set" tier. The in-file board syntax and growth
  verbs wait for them.

## 4. Implementation staging

Each stage is one PR-train: its registries and pins land together
(closed-domain completeness — registry, static pin, runtime wall, on
day one), its surface passes the totality audit (misuse-probe
rejection tests + completeness ledger), and its witness's proof module
+ differential check close it. Later-stage names are rejected loudly
from the first stage that could parse them.

- **Stage 1 — structure.** Grammar: `board:` and `pieces:` as
  `game_item` alternatives (docking at the existing skeleton-clause
  walls, which grow their combination matrix: `board:` requires
  `pieces:`, `cards:`+`board:` together rejected-until-witnessed,
  piece games skip `ranking:`). The `BOARDS` registry with the wave-A
  entries + integrity pins; piece sets in the deck registry family;
  `Cell` value type + constants in resolve/typecheck; the `cell`
  index role in the domains table; `BoardCell`/`Point`/`HiddenCell`
  rows in the zone registries with probe rows; capacity walls.
- **Stage 2 — decisions, movement, classes 1–4.** `Cell` (and the
  small direction-enum) parameter domains + the action-space cell
  block; cell-zone endpoints through the existing movement executor;
  class 1–4 verbs into the stdlib call/signature/dispatch registries;
  the cell-query register. Witnesses: tic-tac-toe, then breakthrough;
  the GOPS differential harness generalized to a reusable
  native-oracle comparison. Perfect-info proof modules (adapter
  agreement, conformance, degenerate partitions).
- **Stage 3 — chance.** The `roll` site in the decision interpreter
  (chance actor, outcome into history, public announce); adapter
  chance nodes beyond the root seed; seed/rng non-observability proof
  extended to roll sites. Witness: backgammon.
- **Stage 4 — probes.** The probe action (declared pure predicate
  over a hidden zone, result announced to declared observers);
  double-indexed zone families. Witness: battleship — budgeted
  together with the structural-infoset-proofs compound-probe
  generator it unblocks.
- **Stage 5 — the moat workstream.** C3 attribute-level emission
  classes + C6 anonymous-persistent movement identity, with the
  partition-proof battery extended **first** as the acceptance bar.
  Witness: Barrage. Explicitly a moat-level event with its own
  sign-off.
- **Stage 6 — fixed points.** `reachable`/`region` as bounded
  built-ins with deterministic frontier order. Witness: hex.
- **Stage 7 — open-ended play.** Settle
  unbounded-lines-and-max-length (draw rules; counter-based state
  idioms; repetition history stays out unless that settlement pulls
  it in). Witnesses: nine men's morris, then english draughts.

Cross-cutting honesty: the adapter still provides no tensors
(information-state strings carry CFR; the Representation domain is
unmoved); replay stays O(n²) re-simulation, which the ladder's episode
lengths tolerate; tabular-CFR work on battleship needs a shrunk
variant, which would be its own pinned game file, not a parameter of
the corpus one.

## 5. What this note leaves open

Ratifying this note means opening (or updating) exactly these
questions, not silently deciding them:

- **The board/piece surface**: `pieces:` vs overloading `cards:`; the
  board-declaration argument forms; cell-constant lexing (`a1` as a
  minted constant vs a name). One-spelling-per-concept is the
  criterion; §2.3 states the current lean.
- **Cell-typed state** (`chain_from : Cell?`): a new state-variable
  value type — public like all state, but the type set is a closed
  domain that grows.
- **The draw/repetition settlement** — already
  [open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md);
  wave C is its forcing set.
- **Mutable topology** (Quoridor-class walls, growth) and the
  **in-file board form** (Catan-class maps): each waits on its
  witness; both are named walls until then.
- **The spatial leak lint** (requirements doc, key finding 8): owned
  by the knowledge model; its static half is unscheduled.
- **Solitaire positional zones are orthogonal**: Klondike's tableau is
  intra-zone order and per-position facing *within* one zone — none
  of the board machinery above — so the solitaire thread
  ([roadmap.md](../roadmap.md)) neither gates nor is gated by this
  ladder. Stating that here keeps the two threads from being
  sequenced against each other by mistake.

The ladder's candidates entries are in
[games/_candidates.md](../games/_candidates.md); per corpus-first
discipline, the next concrete action is implementing rung 1 against
stage 1–2, and nothing else in this note before its stage's witness.
