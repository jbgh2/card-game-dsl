# How Games Use Boards, Zones, and Spaces: A Rules-Language Survey

A survey of ~60 board, tile, and card games, read through their own rulebooks
(publisher PDFs, Pagat.com, and corroborating secondary sources), asking three
questions: what spatial *structures* do games actually use, what natural
*language* do rulebooks use to describe them, and what *computations* do the
rules demand. The corpus was deliberately weighted toward the hardest cases for
this project: games combining dynamic tile-laying, hidden information on or
about the board, and complex placement or scoring rules — because information
sets must be derived from zone visibility plus observation events, and spatial
hidden state is where that gets hard.

This document records what the games *are*. The companion survey,
`topology-and-query-requirements.md`, derives what the language must
*support*.

## TL;DR

- Rulebook spatial vocabulary is remarkably small and convergent. Across all
  six families, nearly every spatial rule is phrased with: **adjacent**
  (qualified orthogonal/diagonal/edge-sharing), **line/straight line**,
  **connected/chain/group/network**, **region/territory/area**,
  **exposed/uncovered/free**, **land on/pass/exact landing**, and
  **edge of the board**. A designer-first DSL can plausibly mirror this
  vocabulary directly.
- The structures reduce to about seven shapes: bounded grids (cell,
  intersection, or edge occupancy), graphs of nodes/edges/regions, linear and
  circular tracks (most of which reduce to integers), growing tessellations
  built from tiles with internal sub-structure, covering/blocking DAGs
  (solitaire fans, mahjong layers), fixed personal grids, and
  position-semantic sequences (racks, queues).
- The computations cluster into a clean ladder: O(1) adjacency checks →
  bounded ray/line scans → fixed-shape pattern matches → path existence →
  connected components / flood fill → longest path and best-path search →
  global move-existence → hypothetical-mutation legality ("legal iff property
  P still holds after this change"). The last four exceed a deliberately
  non-recursive expression language and are where the design work lies.
- Hidden information interacts with space in about nine distinct patterns,
  from "topology public, objectives hidden" (Ticket to Ride — easy) through
  "hidden position with partial projected observations" (Scotland Yard) to
  "content hidden from its own owner" (Golf/Skyjo) and "hidden state is a
  predicate, not a token" (Cryptid). Each pattern demands a different
  observation primitive.
- The single hardest recurring scoring computation found: connected regions
  over **tile-internal sub-structure** (Carcassonne roads/cities are built
  from edge segments smaller than a cell), compounded by farmer scoring's
  cross-referencing of two independently computed region partitions.
- The hardest single games for derived info sets: Letters from Whitechapel,
  Fury of Dracula, Scotland Yard, Tigris & Euphrates, Cryptid. None of them
  is hard for the same reason.

## Key findings

1. **"Adjacent" is never self-sufficient.** Every rulebook qualifies it:
   "horizontally and vertically adjacent" (Go's liberties), "adjacent
   hexagons share an edge" (Hex), "touching diagonally... or orthogonally"
   (Sagrada), "adjacent (touching)... or connected... by a dashed line"
   (Risk's sea lanes), "at least one edge adjacent and abutting" with the
   explicit negative "may not simply be placed corner to corner" (Carcassonne).
   Connectivity kind (4/6/8-way, edge-sharing, bespoke edge lists) is always
   part of the rule, so it must be a parameter, not a default.

2. **Three distinct things get occupied: cells, intersections, and edges.**
   Chess/Stratego occupy cells; Go occupies intersections; Ticket to Ride,
   Dots and Boxes, and TransAmerica occupy edges; Quoridor *removes* edges
   (walls); Catan occupies all three layers of a dual structure at once
   (hexes produce, intersections hold settlements, edges hold roads). A
   topology model that only knows "spaces" cannot express half the corpus.

3. **Rulebooks state graph algorithms in plain prose, and players execute
   them.** Pandemic's outbreak rule is a textbook BFS with a visited set:
   "add a cube... to each adjacent city... additional outbreaks may occur,
   causing a chain reaction. Note that each city may only outbreak once in
   each chain reaction." Power Grid's connection rule is Dijkstra ("the
   cheapest connection between the new city and one of his own cities...
   including any jumps"). Catan's Longest Road is longest-path with
   opponent-piece cuts ("continuous road... not interrupted by game pieces
   belonging to other players"). These are not implementation choices — they
   are the rules as written.

4. **Tiles have internal structure that crosses cell boundaries.**
   Carcassonne segments (city/road/field per edge, connected across the tile
   interior), Kingdomino's two halves, Galaxy Trucker's typed connectors
   (single/double/universal/smooth compatibility lattice), Take It Easy's
   three through-lines. Edge-matching legality ("all... segments... continue
   to... segments... on all abutting tiles") and region scoring both operate
   on the sub-cell graph, not on whole cells.

5. **Many tracks are integers wearing a costume.** Cribbage's pegging board,
   Eurogame scoring tracks (score mod length + lap counter), rondels
   ((target − current) mod N with a stepped cost function), and Snakes &
   Ladders (integer plus a static jump table) need no positional structure at
   all. The tracks that genuinely need structure are identifiable by their
   interaction rules: backgammon (typed per-point occupancy — "open point" =
   "not... occupied by two or more opposing checkers"; blots, the bar,
   bearing off with overshoot), Parcheesi/Ludo (shared ring plus per-player
   branch tails with an exact-landing gate), and racing games (lane ×
   distance grids with single-occupancy blocking).

6. **Solitaire "availability" is three different predicates under one word.**
   Linear-stack exposure (Klondike: top of cascade), covering-DAG exposure
   (Pyramid: "cards must not be covered... when an Ace rests on a Queen, that
   Queen cannot be removed" — exposed iff both parents removed), and
   layered-plus-lateral freedom (Mahjong: "no tile sits on top of it and at
   least one side (left or right) is open"). The covering relation is a DAG,
   a genuinely distinct topology from grids and graphs.

7. **Hidden information almost always sits *beside* public topology, in a
   small number of shapes.** The board/graph itself is public in nearly every
   surveyed game. What's hidden is: piece identity at a public position
   (Stratego ranks); full occupancy queried cell-by-cell (Battleship);
   objectives over public nodes (Ticket to Ride tickets, Risk missions);
   payoff values at public locations (Through the Desert's face-down
   waterhole tokens); position itself, with partial observations (Scotland
   Yard); a predicate rather than a token (Cryptid clues); and content hidden
   from its own owner (Golf/Skyjo layouts, Dracula's encounter cards).

8. **Revelation is event-shaped and one-way.** Cards/tiles flip from
   hidden to common knowledge via specific triggers: uncovering (Klondike:
   moving the face-up run flips the next card), adjacency interaction
   (Stratego: "declare the rank" at combat), direct query (Battleship,
   Whitechapel, Cryptid), scheduled reveal (Scotland Yard's turns 3, 8, 13,
   18, 24), or synchronous use (Kingdom Builder's terrain card). Perfect
   recall then keeps them public. This maps directly onto observation
   events — every one of these triggers is a movement or decision site.

9. **The worst cases compound orthogonal difficulties.** Tigris & Euphrates'
   kingdoms are *emergent zones* — equivalence classes recomputed by flood
   fill after every placement and removal ("when a tile is removed... it
   might cause the kingdom to be divided into two or more parts") — while its
   hidden element (victory points behind screens) has no spatial location at
   all. Taluva's 3D stacking makes placement legality itself a geometric
   computation with no hidden information anywhere. Hard topology and hard
   information-hiding are independent axes; games that combine them
   (a hypothetical hidden-content Taluva; Whitechapel's decoy tokens on a
   200-node path graph) are the true ceiling.

---

## The corpus

| Family | Games surveyed |
|---|---|
| Grids & piece movement | Chess, Go, Hex, Checkers/International Draughts, Stratego, Onitama, Battleship, Amazons, Breakthrough, Dots and Boxes, Hive, Shogi, Quoridor, Lines of Action, Abalone |
| Networks, routes & area control | Catan, Ticket to Ride, Power Grid, TransAmerica/TransEuropa, Risk, El Grande, Small World, Through the Desert, Twilight Struggle, Pandemic |
| Tracks & linear structures | Backgammon, cribbage pegging, Patchwork time track, rondels (Antike, Glen More), Snakes & Ladders, Formula D, Downforce, Tokaido, Parcheesi/Ludo, Hare & Tortoise, Eurogame scoring tracks |
| Dynamic tile-laying & growing boards | Carcassonne, Kingdomino, Cascadia, Calico, Azul, Patchwork, Bärenpark, Isle of Skye, Galaxy Trucker, Sagrada, Take It Easy, NMBR 9 |
| Tableau & solitaire layouts | Klondike, FreeCell, Spider, Pyramid, TriPeaks, Golf (solitaire), Mahjong solitaire, Golf/Skyjo (multiplayer), Racko, Bohnanza, Arboretum |
| Hidden-information × topology (challenge set) | Scotland Yard, Letters from Whitechapel, Fury of Dracula, Tigris & Euphrates, Cryptid, Kingdom Builder, Clue, Barony, Taluva |

---

## Family 1: Grids and piece movement

**Structures.** Bounded square grids with cell occupancy (chess 8x8, Stratego
10x10 with fixed impassable lakes, Onitama 5x5); intersection occupancy (Go —
structurally distinct: stones sit on points, not in cells); hex grids (Hex's
rhombus with owned opposite edges, Abalone's hexagon-of-hexagons); an
**unbounded** hex grid with no board at all (Hive — tiles define the space,
and the Beetle makes cells stackable); edge occupancy in both directions
(Dots and Boxes *adds* edges — "dots are vertices and lines are edges";
Quoridor *removes* them — walls block cell adjacency); multi-cell piece
footprints (Battleship's ships: "horizontally or vertically, but not
diagonally", "cannot overlap"); and an off-board reserve that re-enters play
(Shogi's pieces in hand).

**Movement language.** FIDE defines the axes: files, ranks, and "a straight
line of squares of the same colour... is called a 'diagonal'". Sliding pieces
move "any number of unoccupied squares" and stop at the first occupied one.
Displacement pieces are defined by offset, not line (the knight: "the nearest
square not on the same rank, file or diagonal"); Onitama externalizes offsets
onto shared cards ("the colored spaces show where your pawn can move relative
to its starting position"), mirrored 180° per side. Checkers jumps require
vacancy beyond the target and chain ("the jumps... may 'zigzag'"), with
mandatory-maximum variants turning legality into an optimization. Lines of
Action computes range from live occupancy: "exactly as many squares as there
are pieces of either colour anywhere along the line of movement." Abalone
moves coordinated groups and pushes by line-strength comparison ("push your
opponent's marbles if you have more marbles in line"). Hive constrains
movement globally: the One Hive Rule ("all pieces... must remain connected as
a single unit at all times", violated even transiently mid-slide) plus
Freedom to Move (a piece cannot squeeze out of "a hex that is almost
completely or completely surrounded").

**Interaction language.** Capture by occupation (chess, Onitama), by jump
(checkers), by surrounding (Go: liberties are "the vacant points that are
horizontally and vertically adjacent to a stone or a group of stones"; a
group with none is "captured and removed"), by rank comparison at adjacency
(Stratego: "declare the rank"), by shoving off the board (Abalone's "outer
rim"). Chess's attack predicate ("a piece is said to attack a square if the
piece could make a capture on that square") is reused for check, checkmate,
and castling's "may not pass through or land on an attacked square".

**Hidden information.** Mostly none — this family is the perfect-information
pole. The two exceptions are archetypes: Stratego (piece identity hidden at a
public position, revealed by adjacency-triggered combat) and Battleship (an
entire owner-visible grid queried coordinate-by-coordinate, "hit... miss...
sunk" as the projected answers).

**Computations.** O(1) neighbor checks; bounded ray scans with pluggable stop
conditions; flood fill (Go groups and territory); path existence (Hex's win:
a "chain of adjacent stones" linking owned edges — corner hexes explicitly
belong "to both adjacent board edges"); per-file uniqueness (Shogi's nifu: "a
pawn cannot be dropped in a column containing another unpromoted pawn");
global move-existence (checkmate; Amazons' "last player to be able to make a
move wins"); and hypothetical-mutation legality — Quoridor's wall rule is the
canonical case: "there must always remain one path to the goal for each
player", checked against the board *as if* the wall were placed.

## Family 2: Networks, routes, and area control

**Structures.** Node/edge graphs with printed maps (Ticket to Ride's cities
and colored routes; Pandemic's non-planar city graph; Risk's territories with
"sea-lane" special edges); Catan's triple dual structure (hexes produce for
adjacent intersections; settlements on intersections; roads on edges) over a
*randomized* hex layout; region-only boards with no edge layer at all (El
Grande's provinces, Twilight Struggle's countries grouped into scoring
regions); hex fields where the cells themselves chain into caravans (Through
the Desert).

**Placement language.** Catan's distance rule is an adjacency *prohibition*:
"no two settlements or cities may occupy adjacent intersections." Ticket to
Ride explicitly waives connectivity ("a player... is never required to
connect to any of his previously played routes"); Power Grid requires it as
an invariant ("you can't have two separate networks"); TransAmerica requires
it per-move ("he must play next to his marker or next to track connected to
his marker") and then allows cross-player network *union* ("players may
connect their networks to others and then use the connected networks as
their own"). Small World splits conquest (adjacency-gated: "each newly
conquered region must be adjacent to a region already occupied") from
redeployment ("it is not needed that these regions are adjacent"). Through
the Desert prohibits same-color merges across players.

**Scoring language.** Path existence against secret goals (Ticket to Ride:
"if a player successfully completes a series of routes that connect the two
cities... if they do not... they deduct the amount"); longest path (Catan's
Longest Road; Ticket to Ride's longest trail — "may include loops... but a
given plastic train may never be used twice"); cheapest completion
(TransAmerica scores minus points by minimal missing track, "most
favorable"); ranked majority (El Grande: most/second/third caballeros per
region, with the explicit exclusion "the Grandes... are not counted");
tiered counting + totality (Twilight Struggle: Presence / Domination /
Control, where Control = "more countries... than its opponent, and Controls
all of the Battleground countries in that Region"); pure totality (Risk:
"you must occupy all its territories"); propagation (Pandemic's outbreak
chain, quoted in Key Finding 3).

**Hidden information.** The family pattern: **topology public, something else
hidden.** Three variants: hidden goals over public nodes (destination
tickets, TransAmerica's five secret cities, Risk missions); hidden payoff at
a public location (Through the Desert's waterhole tokens "stay hidden from
other players until the end of the game"); and hidden timing/resources with
no spatial reference at all (Twilight Struggle's hand, Pandemic's epidemic
cards) — the last needs no topology-aware treatment whatsoever.

## Family 3: Tracks and linear structures

**Structures.** Shared linear tracks (Patchwork's time track, Tokaido's
one-way road with forced inn stops); circular tracks with laps (scoring
tracks, racing circuits); rondels (small circular action selectors); mirrored
linear-with-turnaround (backgammon's 24 points plus the bar and bear-off);
shared ring plus per-player branch tails (Parcheesi/Ludo home stretches);
lane × distance grids (Formula D's three lanes, Downforce).

**Movement language.** "Move to an open point" (backgammon — open = "not
currently occupied by 2 or more opposing checkers"); "bear off" with explicit
overshoot policy ("if there are no checkers on higher-numbered points, the
player is permitted (and required) to remove a checker from the highest
point"); "move clockwise... one, two or three wedges... free of charge. For
advancing more than three wedges, the bank must be paid" (Antike's rondel);
"land exactly on square 100" vs. bounce-back variants (Snakes & Ladders);
"you receive them when your time token moves onto or past these spaces"
(Patchwork — pass-through triggers); "must move his Traveler forward... to
the open space of his choice... as long as they don't pass the next inn
space" (Tokaido); "it is only permitted to change lanes twice in one turn"
and corner-stop requirements with wear-point penalties (Formula D). Turn
order from track position recurs: "the player whose time token is furthest
behind... takes their turn" (Patchwork), identically in Tokaido with a
lateral tie-break.

**Interaction language.** Bump/capture ("the piece 'eaten' will return home",
Parcheesi, negated on safe squares), blot-hitting with re-entry from the bar
(backgammon), blocking without capture (made points; Formula D lanes — "not
allowed to go over other cars — they must be driven round"), stacking as
turn-order tie-break (Patchwork: "the arriving token is placed on top").

**What reduces to an integer.** Cribbage pegging ("first... to reach 121"),
scoring tracks (score mod length + lap counter — literal place-value
arithmetic), rondel position (modular index), Snakes & Ladders (index + jump
table). What doesn't: backgammon (typed per-point occupancy), Parcheesi
(branch remapping at the home-stretch entry, exact-landing gate), racing
lanes (2D occupancy with path-scan passability), Hare & Tortoise's *rank*
queries (payouts depend on ordinal position among players: movement costs
n(n+1)/2 carrots, backward moves to "the closest tortoise space").

**Hidden information.** Essentially none anywhere in the family — worth
stating as a finding: pure tracks are a hidden-information desert, which is
why Cribbage's board correctly lives as score variables today.

## Family 4: Dynamic tile-laying and growing boards

**Structures.** A shared growing square tessellation (Carcassonne — the board
does not exist until played); personal growing boards, capped (Kingdomino:
"a kingdom may not be more than 5x5 squares") or uncapped (Cascadia's hexes,
Bärenpark); personal fixed boards filled by placement (Azul's 5x5 wall with
pre-printed color Latin square; Sagrada's window with per-cell color/value
restrictions; Calico and Take It Easy's fixed hex layouts); polyominoes on
personal grids (Patchwork — sole legality rule: "the patches on your quilt
board may not overlap"); tiles with internal segments (Carcassonne, Galaxy
Trucker's connector types); true 3D stacking (NMBR 9: levels with "no part of
the new tile overhangs the tiles below it", grid alignment across tiles;
Taluva in the challenge set).

**Placement language.** The near-universal minimum: "must be placed with at
least one edge adjacent and abutting one previously placed tile... may not
simply be placed corner to corner" (Carcassonne). Edge-matching: "all field,
city, and road segments on the new tile [must] continue to field, city, and
road segments, respectively, on all abutting tiles" (Carcassonne); "at least
2 connecting squares must have the same terrain type" (Kingdomino, whose
start tile's edges "are wild"); "the terrain on that edge must be the same"
but "roads DO NOT need to be continued" (Isle of Skye); connector
compatibility lattices (Galaxy Trucker). Cascadia deliberately decouples the
two: "matching terrain is not a placement rule but may gain you points."
Sagrada is the sharp *negative* constraint: "dice may never be placed
orthogonally adjacent to a die of the same color or the same value" —
diagonal is fine — plus per-cell restrictions and a first-die edge rule.
Unplaceable tiles are handled explicitly (Kingdomino discards; Isle of Skye:
"the tile goes back into the bag (you do not get back any money)").
Rotation is permissive everywhere and folded into the matching predicate
("you may turn the patch any way you like") — no surveyed game restricts
orientation below the full 4 (or 6) rotations.

**Scoring language.** Flood fill × local count (Kingdomino: "a territory is a
group of matching terrain squares that are connected horizontally or
vertically", scored as size × crowns); largest-component-per-type (Cascadia's
habitat corridors); flood fill + closure test (Isle of Skye: "an area is
considered completed if it is fully enclosed by areas of a different terrain
type"); fixed-shape pattern matches (2x2 squares, straight runs of 3+,
Calico's exact cat shapes, Take It Easy's all-or-nothing full-board lines);
two-axis run counting (Azul: count "tiles horizontally linked to the newly
placed tile", then vertically); per-tile arithmetic with no adjacency at all
(NMBR 9: "worth points equal to its number multiplied by its level"). The
ceiling is Carcassonne: roads and cities are connected components over
tile-internal *segments* ("a city is complete when [it] is surrounded by a
city wall with no gaps"), followers claim segments with a
reachability-of-prior-claim restriction ("may not deploy a follower on a...
segment if that segment connects to a segment... that already has a
follower"), contested features score by plurality with ties earning full
points for all, and farmer scoring cross-references field regions against
*completed* city regions via region-to-region adjacency — two independent
partitions and a relation between them.

**Hidden information.** Face-down draw stacks (Carcassonne — the next tile is
unknown, then public before placement); hidden bag contents (Cascadia's
wildlife tokens); real-time face-down pools (Galaxy Trucker — content
revealed on pickup); genuinely secret per-player objectives (Sagrada's
private color); and Isle of Skye's signature: hidden *valuation* — tiles are
public but each owner's assigned price and remaining gold are concealed
behind a screen. NMBR 9 has zero hidden information; Take It Easy hides
nothing but the shared draw order.

## Family 5: Tableau and solitaire layouts

**Structures.** Cascades: ordered stacks with a face-down prefix and face-up
suffix (Klondike's "seven fanned piles... each pile contains one more card
than the last... the topmost card... turned face up"; Spider); fully face-up
cascades plus free cells (FreeCell — "each [free cell] holds a single card at
a time"); covering DAGs (Pyramid's 28 cards where each card overlaps two
below; TriPeaks' three interleaved peaks); 3D layered DAGs with lateral
freedom (Mahjong solitaire); fixed personal face-down grids (Golf's 2x3,
Skyjo's 3x4); index-addressed racks (Racko's ten slots, win = "arranged in a
numerical progression from LOW to HIGH"); order-locked hand queues
(Bohnanza: "you cannot rearrange the cards in your hand — ever"); and a
personal growing grid scored by path search (Arboretum).

**Availability language — one word, three predicates.** "Only the top card"
(linear stacks); "cards must not be covered, so when an Ace rests on a Queen,
that Queen cannot be removed" (covering DAG — exposed iff *both* parents
gone); "a tile is free when no tile sits on top of it and at least one side
(left or right) is open" (Mahjong — vertical clearance AND lateral slide
room).

**Build language.** "In descending order, alternating colours"; "only a King
may be placed on an empty column" (Klondike — emptiness has bespoke fill
rules per game: FreeCell allows anything gated by the supermove formula
"(empty free cells + 1) multiplied by 2 for each empty column"); Spider
layers two predicates on one topology — single cards place suit-blind
("one rank higher") but groups move only if "in sequence and of the same
suit", and a complete same-suit K→A run is auto-removed.

**Hidden-from-owner — the family's landmark.** Pagat's Golf rules: "each
player may look once at the two nearest cards of his or her square layout...
After this, the layout cards may not be looked at again"; and the atomic
look-equals-replace rule: "you are not allowed to look at any of your layout
cards before deciding which to replace... There is no way to check the value
of a face down card and leave it in place." A player's own board cells are
outside their own information set, except the specifically peeked subset —
which is private, per-owner knowledge that no other player shares. Skyjo adds
a spatial collapse trigger: "three face-up cards of the same number in a
vertical column [are] immediately remove[d]."

**Position-as-semantics.** Racko: any slot may be overwritten by index; the
win predicate is global sortedness; the slot labels matter only for scoring.
Bohnanza: planting is FIFO-locked to the queue front, draws append to the
back, trading is exempt — order is a *constraint*, never player-editable.
Arboretum's scoring is the family's computational outlier: "a path is a
sequence of orthogonally adjacent cards of ascending value, where the first
and last cards are of the same species... the cards in between can be of any
species", doubled if length ≥ 4 and pure — a best-path search over a typed
grid, coupled to a hidden-hand bidding contest ("the player whose revealed
cards have the highest sum for that species gains the right to score").

**Revelation.** Two trigger shapes: uncovering (moving Klondike's face-up run
flips the card beneath — visibility changes as a side effect of movement
elsewhere in the zone) and same-cell action (Golf/Skyjo's flip-or-replace).
Both are one-way: once public, always public.

## Family 6: The challenge set — hidden information × topology

The deliberately-hunted hardest combinations, ranked from hardest to easiest
for a DSL that derives information sets from zone visibility plus observation
events:

1. **Letters from Whitechapel.** Hidden path (written, not tokened) AND
   hidden token identity on public cells (face-down women tokens, some real,
   some decoys), with observations only via adversarial queries: "the police
   may ask Jack if he has visited certain spaces that night" — yes/no per
   queried space. Two compounding hidden layers, pull-based observation.
2. **Fury of Dracula.** The trail: "Dracula... plac[es] location cards
   facedown on the trail... slides all cards already on the trail one space
   to the right" — a sliding-window FIFO of hidden history, with encounter
   cards seeded face-down (hidden even from their controller's opponents
   *and* deferred in effect), maturation resolving retroactively, and reveal
   partly gated on Dracula's choice to ambush. Hidden history, not hidden
   position.
3. **Scotland Yard.** The clean archetype: Mr X's node is hidden; every move
   emits an automatic *partial* observation — "the detectives can see which
   means of transportation Mr X used, but not his destination" — plus
   scheduled full reveals ("after making moves 3, 8, 13, 18, and 24, Mr X
   must surface"). The detective's information set is exactly the set of
   nodes reachable by label-consistent walks from the last reveal.
4. **Tigris & Euphrates.** Hard in the opposite direction: kingdoms are
   emergent zones — equivalence classes under adjacency, recomputed by flood
   fill after every placement and removal, merged by placement (external
   conflict "when two kingdoms are joined") and split by removal — while the
   hidden element (victory points "kept hidden behind players' screens") has
   no location at all and is driven causally by fully public events.
5. **Cryptid.** No movement, no tokens: each player's hidden state is a
   *predicate* over the public hex map ("each player knows one thing about
   its habitat, but all clues overlapped indicate exactly one space"), and
   observations are player-elicited single-bit evaluations of another
   player's predicate at a chosen hex.
6. **Clue.** The board only gates queries ("the Room you name must be the
   Room where your token is located"); the load-bearing pattern is the
   three-tier asymmetric fan-out of one suggestion: the asker sees the shown
   card, the refuter shows what they already knew, bystanders learn only
   *that* a card was shown.
7. **Kingdom Builder.** The floor case: one hidden terrain card, revealed
   unconditionally and synchronously with the placement it gates; scoring is
   public flood fill / distance / quadrant counting.
8. **Taluva.** No hidden information; the pure topology ceiling — placement
   legality on a growing 3D surface ("be placed on top of at least two other
   tiles (without any gaps under the land being created)", may not fully
   cover a settlement or any tower/temple).
9. **Barony.** Control case: dynamic tile map, exclusive-occupancy blocking,
   zero hidden information.

---

## The consolidated spatial vocabulary

Terms recurring across families, deduplicated. This is close to a complete
list of the words rulebooks use for space — a designer-first surface should
sound like this column.

| Term | Meaning across rulebooks | Where seen |
|---|---|---|
| adjacent / touching / next to | neighbor under a stated connectivity (4/6/8-way, edge-sharing, printed edge list) | universal |
| orthogonal / diagonal | axis qualifiers on adjacency and lines | chess, Go, Sagrada, Breakthrough, Arboretum |
| rank / file / row / column | named grid axes, incl. per-player "home row" | chess, shogi, Azul, Skyjo |
| straight line / in a line | maximal or bounded runs along an axis | chess, Amazons, Lines of Action, Cascadia (elk), Take It Easy |
| between / crossed / passed through | intermediate cells of a move or line | chess (castling), Downforce, Patchwork track |
| connected / chain / group / string / network | same connected component | Go, Hex, Hive, Catan, Power Grid, TtR, Pandemic, Kingdomino |
| region / territory / area / kingdom / continent | named or emergent cell set, unit of majority/totality scoring | El Grande, Risk, T&E, Twilight Struggle, Isle of Skye |
| surrounded / enclosed / no gaps | all neighbors occupied/hostile, or region closure | Go, Hive, Carcassonne cities, Isle of Skye, Calico goals |
| liberties | empty-neighbor set of a group | Go (named); computed unnamed elsewhere |
| blocked / open / occupied / vacant | occupancy predicates gating movement/placement | universal |
| exposed / uncovered / free | availability under a covering relation | Klondike, Pyramid, Mahjong, Golf solitaire |
| edge of the board / outer rim / off the board | boundary predicate, with per-game consequence | Amazons, Abalone, Hex, Sagrada first-die rule |
| land on / land exactly on / pass / overshoot | move-termination events and policies | all track games |
| bump / capture / hit / safe space | landing-on-occupied consequences and exemptions | Parcheesi, backgammon, Formula D |
| lap / around the board | circular-track wraparound with counting | cribbage, scoring tracks, racing |
| furthest behind (moves next) | turn order from relative track position | Patchwork, Tokaido |
| attack / attacked square | opponent-reachability predicate | chess, Stratego |
| path / route (to goal, between cities) | existence of a connecting walk | Quoridor, TtR, TransAmerica, Arboretum |
| longest road / longest path | maximal path/trail, with cut rules | Catan, TtR |
| edges must match / continue / compatible connectors | tile-boundary compatibility on placement | Carcassonne, Kingdomino, Isle of Skye, Galaxy Trucker |
| may not overlap / no overhang / supported | footprint constraints, incl. 3D support | Patchwork, Battleship, NMBR 9, Taluva |
| rotate / turn any way you like | orientation freedom folded into match predicates | all tile games |
| complete / completed | closure or full-coverage scoring gate | Carcassonne, Azul, Isle of Skye, Patchwork 7x7 |
| reveal / surface / declare / show | hidden→public transition events | Stratego, Scotland Yard, Clue, Golf |

## The consolidated computation catalogue

Deduplicated across all six families and ordered by computational class. The
classification matters because the expression sublanguage is deliberately
non-recursive: classes 1–4 are bounded local work; classes 5–9 are the
fixed-point / search tier that needs dedicated primitives; class 10 is a
modality on top of the others.

1. **O(1) adjacency/occupancy checks** — the universal atom. Neighbor
   emptiness, friend/enemy tests, edge-compatibility at placement, Sagrada's
   negative constraints, oasis-linking, production incidence (Catan).
2. **Bounded ray/line scans** — sliding movement with first-obstruction stop
   (chess, Amazons), count-derived range (Lines of Action), line-strength
   comparison (Abalone), two-axis run counting (Azul), passability walks
   along a move path (Downforce, Patchwork pass-through triggers).
3. **Fixed-shape pattern matches** — 2x2 squares, straight runs of length k,
   exact polyomino shapes (Calico cats), full lines (Take It Easy, Azul
   rows/columns), full-coverage checks (Patchwork 7x7, Bärenpark 4x4).
   Template lookup, no traversal.
4. **Track arithmetic** — position ± delta, modular laps, exact-landing /
   overshoot policies, static jump tables, branch remapping at a threshold
   (Parcheesi), cost-as-function-of-distance (rondel steps, triangular
   numbers), rank/min queries over player positions (furthest-behind).
5. **Path existence between node sets** — Hex's win, Quoridor's wall
   legality, destination tickets, Whitechapel/Scotland Yard candidate
   filtering. A yes/no query, distinct from enumeration.
6. **Connected components / flood fill** — Go groups and territory, Hive's
   one-hive invariant, Kingdomino territories, Cascadia corridors,
   Carcassonne features over *sub-cell segments*, T&E kingdom identity,
   Pandemic outbreaks (BFS with visited set), Power Grid's single-network
   invariant, TransAmerica's cross-player component union, enclosure tests
   (Isle of Skye, Through the Desert).
7. **Optimization searches** — longest path/trail (Catan, TtR), cheapest
   path (Power Grid, TransAmerica's missing-track scoring), maximum-capture
   chains (international draughts), best ascending path (Arboretum),
   supermove capacity is the degenerate arithmetic case (FreeCell).
8. **Global move-existence** — checkmate/stalemate, Amazons' last-to-move,
   "no free pair exists" (Mahjong stuck detection). Enumerate all candidate
   moves, test each against full legality.
9. **Region-cross-referencing** — Carcassonne farmers: two independent
   partitions (field regions; completed-city regions) plus a
   region-to-region adjacency relation between them. The hardest scoring
   computation found anywhere in the corpus.
10. **Hypothetical-mutation legality** — "legal iff P holds after the
    change": Quoridor walls (path existence survives), Hive (connectivity
    holds *during* transit), castling (no intermediate square attacked),
    Galaxy Trucker's live re-validation after damage. A modality applied to
    classes 5–6, requiring evaluation against a tentative state.

## Hidden information × space: the patterns

Nine distinct shapes, each needing a different treatment in an observation
model. Ordered roughly from cheapest to hardest.

1. **Hidden timing/resources, topology-irrelevant.** Twilight Struggle's
   hand, Pandemic's epidemics. Ordinary hidden-zone handling; the board
   needs nothing.
2. **Hidden pre-commitment revealed synchronously with use.** Kingdom
   Builder's terrain card; face-down draw stacks generally (Carcassonne's
   next tile). Hidden for a bounded window, revealed unconditionally at the
   decision site.
3. **Hidden goals/objectives over public topology.** Destination tickets,
   TransAmerica cities, Risk missions, Sagrada's private color, Arboretum's
   hand-sum contest. A private variable evaluated by a public-graph query at
   scoring time.
4. **Hidden payoff value at a public location.** Through the Desert's
   waterhole tokens; Isle of Skye's hidden prices (valuation channel on
   public tiles). The position is common knowledge; the value is not.
5. **Hidden identity at a public position, revealed by interaction.**
   Stratego ranks (adjacency-triggered mutual reveal), Whitechapel's decoy
   tokens. Occupancy public, attribute private, per-observer.
6. **Hidden occupancy revealed by query.** Battleship (hit/miss/sunk as the
   projected answer), Whitechapel's "did you visit space X", Cryptid's
   habitat questions, Clue's suggestions. Pull-based: an action whose effect
   is evaluating a predicate over hidden state and broadcasting the result —
   with Clue adding role-conditioned payloads (asker sees the card;
   bystanders see only that one was shown).
7. **Hidden position with projected observations.** Scotland Yard: automatic
   partial emission per move (edge label, not endpoint) plus scheduled
   reveals; Fury of Dracula extends the hidden variable to a sliding window
   of history with player-gated reveal. The information set is a
   reachability computation over the observation-consistent walks.
8. **Content hidden from its own owner.** Golf/Skyjo's face-down layouts
   (owner chooses replacement targets by position, blind to value; peeked
   cells form a private singleton subset); Dracula's encounter cards
   (unknown to everyone until triggered). Breaks the assumption that
   ownership implies knowledge.
9. **Emergent zones over mutable adjacency, driving non-spatial hidden
   accumulators.** Tigris & Euphrates: zone *identity* (kingdoms) is
   recomputed by flood fill each turn; public events in those derived zones
   feed hidden per-player scores that live nowhere on the board.

## Sources

Primary rulebooks fetched directly where possible: FIDE Laws of Chess; AGA/BGA
Go rules; official rulebook PDFs for Onitama, Antike, Formula D, Downforce,
Kingdomino (Blue Orange), Cascadia and Calico (Alderac), Azul, Patchwork,
Bärenpark, Isle of Skye (Lookout), Sagrada (Floodgate), Take It Easy, NMBR 9,
Galaxy Trucker (CGE), Bohnanza (Rio Grande), Arboretum, TransAmerica (Rio
Grande), Carcassonne (Rio Grande); Pagat.com for Golf and cribbage;
Wikipedia/UltraBoardGames/BGG threads and publisher pages as corroboration
for Hive, Quoridor, Stratego, Scotland Yard, Letters from Whitechapel, Fury
of Dracula, Tigris & Euphrates, Cryptid, Clue, Taluva, Barony, and the
solitaire family. Verbatim quotes above are from these sources; where a
primary PDF was unparsable (Calico, Bärenpark, Galaxy Trucker) the quote is
from the most widely mirrored official text.
