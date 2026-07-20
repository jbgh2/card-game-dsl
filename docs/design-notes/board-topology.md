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
the same medicine as decks) generates a finite named-member position
domain (its cells),
named **relations** (edge sets), named **regions** (cell subsets), and
named **lines** (pattern triples/tuples); a game's `zones {}` block then
declares a zone family indexed by `cell` exactly as Klondike's tableau
is indexed by `column` — the landed position-domain mechanism
([decisions.md](../decisions.md) "Position domains and positional
zones"), which boards extend rather than rival (§2.2). Pieces are ordinary zone **contents** — the
individuated content kind, of which cards are the deck-flavored
specialization (**`Card ⊂ Piece`**, §2.3); a piece set is a
component-set registry entry with declared axes and multiplicities.
Placement and movement are the **existing kernel
movement** between cell zones and ordinary off-board zones (reserves,
captured piles, the bar), so observation events emit through the
declared projections at the sites that already exist, and information
sets derive with **no new observation machinery for the entire
perfect-information family**. Decisions are parameterized moves whose
cell parameters ride the landed position-domain mechanism — a fixed
cross-product the OpenSpiel adapter ids once and guards mask per
state, already anchored by Klondike's `build(src : column, dst :
column)`. The
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
board: grid(8, 8)          // breakthrough
board: draughts8           // grid(8, 8) restricted to the 32 dark squares
board: hex_rhombus(11)     // hex
board: morris9             // nine men's morris (enumerated graph)
board: backgammon_track    // one shared 24-cell track, opposed per-player pip frames
```

A registry entry — generated (grids, hex tilings, tracks) or enumerated
(morris9) — defines, as static data:

- **Cells**: the finite position set, minted as a **named-member
  position domain** — the landed `positions {}` mechanism
  ([decisions.md](../decisions.md) "Position domains and positional
  zones") with registry-minted named constants (`a1 … h8`,
  `p1 … p24`) in place of integer bounds, reconciled by the same
  name-collision wall.
- **Relations**: named edge sets — `orthogonal`, `diagonal`,
  `dark_diagonal`, hex adjacency, track successor. Where a game's
  movement is rank-asymmetric, the entry also carries **per-player
  frames**: `forward(player)` and `forward_diagonal(player)` resolve to
  opposite concrete relations per seat — one shared graph, a declared
  per-player transform, never a second board (the requirements doc's
  ownership/mirroring property). Where a family's movement is
  direction-parameterized (grids), the entry also mints its direction
  names as a second named-member domain for move parameters (§2.4).
- **Regions**: named cell subsets — `back_row(player)`, `home(player)`,
  `crownhead(player)`. Two non-examples fix the boundary: off-board
  places (the backgammon bar and borne-off tray) are ordinary zones
  (§2.3), never regions or cells; and holes (the Stratego lakes) are
  cell-set modifiers (below), not regions — the remaining cells need
  no name.
- **Lines**: named tuple sets for pattern rules — `lines(3)` on a grid
  (rows, columns, diagonals of length 3, statically enumerated), the
  16 mills of `morris9`.
- **Jump triples**, where the family has them: `(from, over, to)`
  triples for the draughts jump — declared data, so guards and effects
  look up the captured square instead of computing geometry.

Concretely — "registry entry" must not hide the content — an entry is
data in the `DECKS` style ([library.md](../library.md) shows each
deck's composition; boards get the same treatment). Payload sketches
are **literal data** — lists, `..` ranges (the tarot78/`choose`
precedent), visible elisions — with derivations in prose; they use no
indexed meta-variables, because `_` is an ordinary identifier
character in the language (`went_again`, `entry_cell`) and a
pseudo-subscript would collide with real names. The two non-grid
ladder entries in full:

```text
backgammon_track = track(24):
  cells:   [p1 .. p24]                      // one shared track, named in
                                            // White's numbering (the published convention)
  frames:  pip_order(white) = [p1 .. p24]   // p1 is White's 1-point (bear-off end)
           pip_order(black) = [p24 .. p1]   // the same cells, traversed oppositely
  regions: home(player) = the first 6 cells of the player's frame
  derived: pip(player, cell) = the cell's 1-based position in the player's frame;
           next(player); advance(cell, player, d, policy);
           entry_cell(player, d) = the cell at position 25 - d in the player's frame
```

A die move is **class-4 track arithmetic over the frame, not
edge-walking**: a die `d` advances a checker `d` positions along its
owner's frame (`advance`); entry from the bar targets
`entry_cell(actor, d)`; bear-off legality reads `home(actor)` and the
exact-or-highest overshoot policy; the pip count sums
`pip(actor, cell)` over the actor's occupied cells. The bar and
the borne-off tray are **not cells** — they are ordinary per-player
zones (§2.3's off-board rule), sources and destinations of moves
whose cell end is computed from the frame. `track(n)` is the family;
Parcheesi-style rings with per-player tails would add branch
remapping to it later, not a new shape.

```text
morris9 = enumerated graph:
  cells:  a1 d1 g1  b2 d2 f2  c3 d3 e3  a4 b4 c4  e4 f4 g4
          c5 d5 e5  b6 d6 f6  a7 d7 g7                       // the 24 points
  edges:  adjacent = { a1-d1, d1-g1, a1-a4, b2-d2, ... }     // the 32 board segments
  lines:  mills = { (a1,d1,g1), (b2,d2,f2), ..., (g1,g4,g7) } // all 16
```

Generated families take **cell-set modifiers** where the physical
board has unused or missing squares, because a cell no rule can ever
touch must not exist: `draughts8` is grid(8, 8) restricted to the 32
dark squares (the diagonal relation, its derived jump triples, and
the `crownhead(player)` regions living on the restriction), and the
Stratego board is grid(10, 10) minus the lakes. Dead cells kept in
the `Cell` domain would reserve action ids legal in no state — the
defect the declared-ceiling rule already names
([decisions.md](../decisions.md) "Declared parameter domains") — so
restriction happens in the entry, never by permanent guard-mask.

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

### 2.2 Cells are zones, on the landed position-domain substrate

The substrate already exists: **declared position domains**
([decisions.md](../decisions.md) "Position domains and positional
zones", anchored by Klondike/FreeCell) mint per-game finite domains
that index zone families (`tableau_up[column] : Cascade<column>`) and
parameterize moves (`build(src : column, dst : column)`), enumerated
into the guard-masked cross-product and the OpenSpiel action space.
Boards do not add a rival mechanism: **a board entry mints a position
domain** — with two extensions over the `positions {}` block's
integer-keyed form: members are **named constants** (`a1 … h8`,
reconciled by the same name-collision wall), and the domain carries
the topology data of §2.1 (relations, regions, lines, frames) for the
query verbs to consult. The 256-member cap accommodates every ladder
board (the largest is 10×10 = 100). This also answers the recorded
deferral in [positional-zones.md](positional-zones.md) "Adjacency":
adjacency arrives on board-minted domains as declared entry data,
never as an algebra on bare `positions {}` integers.

```text
zones {
  square[cell]     : Cell<cell>         // identity to all, capacity 1
  point[cell]      : Point              // identity to all, unbounded stack (backgammon)
  ocean[player][cell] : HiddenCell<player>  // identity to owner; nothing to others (battleship)
  reserve[player]  : PlayerPile<player> // unplaced pieces, public
  captured[player] : PlayerPile<player>
}
```

Zone types: `Cell` (the one-card holding space FreeCell landed) is
**reused** for capacity-1 squares — same profile, one spelling per
concept — with **capacity** made a typed zone-type property in the
same change (1 for `Cell`, unbounded for the new stack row `Point`),
enforced as a loud runtime wall and respected by movement guards.
`HiddenCell<Owner>` (identity to owner, **trivial** to others —
`count_only` would leak occupancy, which for a board cell *is* the
secret) pairs with `Cell` exactly as the landed `HiddenStack` pairs
with `Cascade`. New rows land in the same closed registries as every
other zone type (`LIBRARY_ZONE_TYPES` + `ZONE_PROJECTIONS` +
`ZONE_PROBES`, `cardlang/stdlib/zones.py`). This is C1 of the
requirements doc — per-position zone families sharing a projection
policy — and it is the entire visibility story for boards: projections
attach to cells because cells are zones.

One landed wall matters here: **positions are unowned** — an
owner-differentiated zone type on a position index is rejected because
its owner projection would be unreachable. Wave A never touches that
wall (`Cell`, `Point` are uniform-projection rows, exactly the class
the wall admits).

The double-indexed family (`ocean[player][cell]`) is one genuinely new
index shape — Battleship needs a board *per player* — and it is where
the positions-are-unowned wall gets its stage-4 **amendment, not an
exception**: an owner-differentiated type is legal on a compound index
iff a component supplies the owner key (here `player`; the position
component stays unowned), which is the same contract the landed
owner-argument wall already enforces on single-index families. A
`HiddenCell` on a bare position index stays rejected.

### 2.3 One individuated content kind: `Piece`, with `Card` as its deck specialization

Zone contents keep their two-kind ontology — individuated and fungible
(`Resource`, untouched) — but the individuated kind's base is the
**`Piece`**: identity = two enumerable axes with per-set declared
names, times multiplicities, plus per-game attributes and optional
facing. **`Card` is the deck specialization of `Piece`, not the other
way around.** A deck is a component set whose axes are named
`suit`/`rank` and which carries the card-only conventions — `ranking:`,
the follow/trump rule family, hand-order enumeration, the `Card`
move-parameter domain. A piece set names its axes (`side`/`kind` for
the ladder's games) and carries none of them. Both flavors live in one
closed component-set registry — the `DECKS` registry generalized, decks
becoming its card-flavored entries — and a game selects one with the
matching head word, `cards:` or `pieces:`, mutually exclusive until a
game witnesses needing both:

```text
pieces: xo_marks           // axes: side = [x, o], kind = [mark]; copies 5/4
pieces: draughts_men       // axes: side = [white, black], kind = [man, king]; 12 men + 12 kings per side
pieces: stratego_barrage   // axes: side = [red, blue], kind = [flag, spy, scout, miner, general, marshal, bomb]; scout ×2
```

The machinery argument is unchanged by the direction of the subset:
zones, projections, movement, and multiplicity attach to the **base**,
so pieces need no new observation machinery (two identical men are
duplicate entries exactly as Pinochle's doubled deck already is, and
Stratego's hidden ranks are piece identity under a hiding projection).
What the direction changes is **where the walls sit**. Modelling
pieces as cards would give every card convention a per-construct
backstop excluding piece games — `ranking:` over sides, follow-suit
over pieces, a hand-order `Card` parameter in a game with no hands —
the backstop-proliferation tell of
[decisions.md](../decisions.md)'s write-time triage. With
`Card ⊂ Piece`, each of those is one wall at the content-kind level:
the construct demands deck content, and the checker rejects it in a
piece game by type, naming the kind. (Piece interactions that look
rank-like but are not a linear order — spy beats marshal — stay
per-game pure functions: meaning is interpretation, never a smuggled
ranking.)

Doctrine already points in this direction: [model.md](../model.md)
calls Card "the **canonical** individuated content of zones" — the
canonical instance, not the base;
[generalization-path.md](generalization-path.md) §0 frames cards as
the high-affordance entry *token*, and its §2 files content-type
declarability as "the same closed-registry medicine already filed for
decks". Tichu's specials — cards that already strain the suit × rank
tuple
([open-questions/special-cards-declaration.md](../open-questions/special-cards-declaration.md))
— are independent evidence that the base wants declared axes even
within cards. The base still carries exactly what the ladder's
witnesses force — two named axes, multiplicities, optional facing —
and no more; specials and richer attributes remain their own
question.

Two consequences fix the surface coherently. The query register
follows the declared content — `pieces in square[c] where …` in a
piece game, `cards in hand where …` in a deck game — one noun per
game, with noun/content agreement checked, so neither noun is a
second spelling of the other. And the movement construct reaches
pieces through its **item-noun slot**, which
[decisions.md](../decisions.md) "The operation vocabulary"
deliberately holds open (`cards` today, "so a resource transfer can
one day be the same construct"): `move one piece from reserve[actor]
to square[at]` is the same movement production with the noun bound to
the game's content kind, not a second construct.

The flip's acceptance criterion is that **the card corpus cannot
tell**: every card game in the corpus keeps `cards:`, card queries,
and byte-identical behavior. `Card` becoming a specialization must be
surface-invisible to them, or the refactor is wrong.

Promotion (draughts man → king) is a supply swap — move the man to the
supply, move a king from the supply to the cell — two public kernel
movements, observation-clean, no pose machinery needed for fungible
pieces. (Pose remains axis 2's mechanism for *individuated* pieces
whose identity must persist through the change.)

Off-board structure is ordinary zones throughout: reserves for
unplaced pieces, captured piles, the backgammon bar and bear-off tray,
the battleship fleet-before-placement. This is where the existing
zone machinery is reused verbatim, and it is most of every game's
zone list.

### 2.4 Decisions: board cells are position-domain move parameters

```text
move_type place(at : cell) {
  when: square[at] is empty
  effect { move one piece from reserve[actor] to square[at] }
}

move_type step(from : cell, to : cell) {
  when: occupant_side(from) is side_of(actor)
        and to in neighbors(from, forward_diagonal(actor))
  effect { move all pieces from square[from] to square[to] }
}
```

This surface is **already landed**: a declared position domain is a
move-parameter domain, enumerated into the guard-filtered
cross-product with one OpenSpiel action id per combination
([decisions.md](../decisions.md) "Position domains and positional
zones" — `build(src : column, dst : column)` is the corpus anchor).
Boards inherit it whole; the parameter spelling is the board domain's
name, exactly as Klondike's is `column`. A `(from, to)` pair over an
8×8 board is 4096 ids; where that is wasteful, the board family also
mints its **direction names** (a grid's compass constants) as a second
named-member domain through the same landed minting, so `step(from :
cell, along : dir)` is 64 × 3, the guard consulting
`neighbor(from, along)` — a declared entry table over
(cell, direction) pairs, looked up with the move's bound values. Directions are deliberately *not* a new parameter-domain
kind (no declared-enum parameter surface exists, and none is proposed)
and *not* per-direction move types (hand-compiling one move type per
direction is exactly the nullary explosion position domains exist to
prevent). This also matches how the native OpenSpiel board games
encode moves. Adjacency,
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
`turns` form") plus a position-typed chain-anchor state variable
(public, as all state is) expresses "same piece continues" —
position-typed `state` is currently **rejected surface** (a recorded
walled residual, [roadmap.md](../roadmap.md) "Positional zones —
walled residuals"); the wall lifts at stage 5, whose Barrage shuttle
rule is its first forcing witness, and the chain anchor reuses the
lift. Mandatory capture is a reusable declarative rule — and that is
a commitment about where rules are *going*, not a description of
today: rules currently bind only at the trick form's card-decision
site, and a rule constraining any other move type is validated but
unenforced
([open-questions/rule-scope-beyond-trick-play.md](../open-questions/rule-scope-beyond-trick-play.md)).
A board corpus cannot leave that standing — unenforced constraints
are the accepted-but-ignored defect class — and the future-facing
resolution is uniform: **rules bind at every kernel decision site**,
attached at the decision interpreter's candidate hook, so one
enforcement path serves the trick form, `turns`-body offers, and
every later form. Draughts' forced capture and morris's in-mill
removal restriction are the two forcing witnesses that question has
been waiting for; §4 stages it.

Compound placements (a battleship spanning four cells) are one
decision whose **effect** runs a bounded sequence of kernel movements
— `place_ship_h(at : cell)` computes the footprint from declared data
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
  track advance with landing policy and per-player frame reads
  (backgammon's bear-off and pip count). The
  cell-query surface mirrors the card-query register — `cells in
  <region> where <pred>`, `number of cells in …`, `any/all cell(s)
  in … where` — one spelling per concept, lifted to positions. This
  is a deliberate **wall-lift**: quantifiers and iteration over
  position domains are currently rejected surface with recorded
  residuals ([roadmap.md](../roadmap.md) "Positional zones — walled
  residuals" — no solitaire addressed columns by loop or quantifier);
  board win predicates ("any line…", "board full") and fixed setup
  arrays (breakthrough's 16 pieces on two rows) are the witnesses
  those records were waiting for, so the lifts land here with the
  register, not as silent accepts.
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
  hidden-function probe class whose first instance (Cheat) anchored
  the constructive world generator (`tests/openspiel_ready/worlds.py`;
  [open-questions/structural-infoset-proofs.md](../open-questions/structural-infoset-proofs.md)).
  Battleship extends the generator to **spatial** hiding — exactly
  that question's recorded residual (generalizing the sampler across
  emission-site shapes) — so the stage budgets the probe action and
  that generalization together.
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
   workstream: `roll`, doubles, the track family (one shared 24-cell
   track under opposed per-player pip frames; bar and tray are
   ordinary zones), stacks with capacity semantics (blots, made
   points as count guards), bar re-entry, exact-or-highest bear-off,
   race win. The
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
   Extends the Cheat-anchored constructive world generator
   (`tests/openspiel_ready/worlds.py`) to spatial hiding — that
   question's recorded residual.
5. **Stratego, Barrage variant** (10×10 with lakes; 8 pieces per side:
   Flag, Spy, 2 Scouts, Miner, General, Marshal, Bomb; two-square
   rule in scope — its shuttle tracking is the first forcing witness
   for position-typed state, whose recorded wall lifts here — chase
   rule scoped out and named in the entry; **no
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
   narrowing (mandatory capture as rule composition — with morris,
   the forcing pair for binding rules at every decision site,
   [open-questions/rule-scope-beyond-trick-play.md](../open-questions/rule-scope-beyond-trick-play.md)),
   jump triples,
   multi-jump chains on the `again` axis, promotion, counter-based
   draw state. English over International deliberately: no
   maximum-capture optimization, so class 7 stays unwitnessed.

### 3.3 Coverage

Each mechanism's earning rung (first column it appears in is the rung
that forces it; every rung earns at least one):

| Mechanism | TTT | Brk | BG | Bshp | Barr | Hex | NMM | Drts |
|---|---|---|---|---|---|---|---|---|
| Generated grid + board position domain + cell zones (C1) | ● | | | | | | | |
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
day one), its surface passes the totality audit (the grid authored red
before the implementation + misuse-probe rejection tests + completeness
ledger), and its witness's proof module + differential check close it.
Later-stage names are rejected loudly from the first stage that could
parse them.

- **Stage 1 — structure.** Grammar: `board:` and `pieces:` as
  `game_item` alternatives (docking at the existing skeleton-clause
  walls, which grow their combination matrix: `board:` requires
  `pieces:`, `cards:`+`board:` together rejected-until-witnessed,
  `ranking:` demands deck content). The `BOARDS` registry with the
  wave-A entries + integrity pins; the component-set registry
  generalizing `DECKS` — **`Card ⊂ Piece` lands here**, with
  byte-identical card-corpus behavior as its acceptance wall;
  board entries minting **named-member position domains** through the
  landed declared-domain machinery (same collision wall; deliberately
  no new row in the built-in domains registry, per the alternative
  positional-zones.md already rejected); capacity as a typed
  zone-type property on the existing `Cell` row plus the new `Point`
  row, with probe rows.
- **Stage 2 — decisions, movement, classes 1–4.** Board domains ride
  the landed position-parameter enumeration (ids from the declared
  domain, no new action-space block kind) plus the small direction
  enums; cell-zone endpoints through the existing movement executor;
  class 1–4 verbs into the stdlib call/signature/dispatch registries;
  the cell-query register — lifting the recorded position
  quantifier/iteration walls against their board witnesses (§2.5).
  Witnesses: tic-tac-toe, then breakthrough;
  the GOPS differential harness generalized to a reusable
  native-oracle comparison. Perfect-info proof modules (adapter
  agreement, conformance, degenerate partitions).
- **Stage 3 — chance.** The `roll` site in the decision interpreter
  (chance actor, outcome into history, public announce); adapter
  chance nodes beyond the root seed; seed/rng non-observability proof
  extended to roll sites. Witness: backgammon.
- **Stage 4 — probes.** The probe action (declared pure predicate
  over a hidden zone, result announced to declared observers);
  double-indexed zone families with the unowned-wall amendment
  (owner key supplied by the player component — §2.2) and the
  `HiddenCell` row. Witness: battleship — budgeted together with
  extending the Cheat-anchored constructive world generator
  (`tests/openspiel_ready/worlds.py`) to spatial hiding, the
  structural-infoset-proofs residual.
- **Stage 5 — the moat workstream.** C3 attribute-level emission
  classes + C6 anonymous-persistent movement identity, with the
  partition-proof battery extended **first** as the acceptance bar.
  Also lifts the position-typed `state` wall (a recorded residual):
  the two-square shuttle rule tracks the mover's previous from/to,
  the wall's first forcing witness; draughts' chain anchor reuses the
  lift at stage 7. Witness: Barrage. Explicitly a moat-level event
  with its own sign-off.
- **Stage 6 — fixed points.** `reachable`/`region` as bounded
  built-ins with deterministic frontier order. Witness: hex.
- **Stage 7 — open-ended play.** Settle
  unbounded-lines-and-max-length (draw rules; counter-based state
  idioms; repetition history stays out unless that settlement pulls
  it in), and **generalize declarative-rule binding to every kernel
  decision site** via the decision interpreter's candidate hook.
  This is the stage where
  [open-questions/rule-scope-beyond-trick-play.md](../open-questions/rule-scope-beyond-trick-play.md)
  resolves — against its two board witnesses (draughts' forced
  capture, morris's in-mill removal restriction) — and is promoted
  into decisions.md per maintaining.md's promotion rule; until then
  the question stays open and its file carries the tradeoffs,
  including the guards-may-suffice counter-evidence this note argues
  against. Validated-but-unenforced rules do not survive this stage.
  Witnesses: nine men's morris, then english draughts.

Cross-cutting honesty: the adapter still provides no tensors
(information-state strings carry CFR; the Representation domain is
unmoved); replay stays O(n²) re-simulation, which the ladder's episode
lengths tolerate; tabular-CFR work on battleship needs a shrunk
variant, which would be its own pinned game file, not a parameter of
the corpus one.

## 5. What this note leaves open

Ratifying this note means opening (or updating) exactly these
questions, not silently deciding them:

- **The board/piece surface details**: the content-kind direction is
  §2.3's commitment (`Card ⊂ Piece`), but its surface residue is open —
  how a component-set entry declares its axis names, how
  noun/content agreement is enforced (resolver vs typechecker), the
  board-declaration argument forms, and cell-constant lexing (`a1` as
  a minted constant vs a name). One-spelling-per-concept is the
  criterion throughout.
- **Position-typed state**: currently rejected surface with a
  recorded residual ([roadmap.md](../roadmap.md) "Positional zones —
  walled residuals"); stage 5 lifts it against its first witness
  (Barrage's two-square tracking), and the draughts chain anchor
  reuses it — public like all state, with the state-type set growing
  by declared position domains.
- **The draw/repetition settlement** — already
  [open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md);
  wave C is its forcing set.
- **Mutable topology** (Quoridor-class walls, growth) and the
  **in-file board form** (Catan-class maps): each waits on its
  witness; both are named walls until then.
- **The spatial leak lint** (requirements doc, key finding 8): owned
  by the knowledge model; its static half is unscheduled.
- **The positional residuals this ladder does not lift**: the landed
  positional machinery is this design's substrate (§2.2), and the
  ladder lifts exactly three of its recorded walls (quantifiers and
  iteration at stage 2, position-typed state at stage 5). The others
  stay walled on their own witnesses — the positional slice movement
  on Spider, the position-family gather on a first gathering layout
  ([roadmap.md](../roadmap.md) "Positional zones — walled
  residuals") — and nothing here re-sequences them.

The ladder's candidates entries are in
[games/_candidates.md](../games/_candidates.md); per corpus-first
discipline, the next concrete action is implementing rung 1 against
stage 1–2, and nothing else in this note before its stage's witness.
