# Candidate games for the corpus

A curated list of games to consider implementing next. Corpus-first
development means each addition to [games/](.) is a chance either to
confirm a pattern (third data point on an open question) or to surface
a new edge case the current design doesn't handle. The entries below
are organized by mechanism family; the coverage table maps them to the
open questions they would unblock.

This file is the pipeline, not the corpus. Entries are not
commitments — the *current* corpus is whatever's in [games/](.).
When a candidate is implemented, its entry is deleted from here and
replaced by a real game file. Treat the entries as "why this game is
interesting" signals, not as rule references.

The table below lists questions a new game could unblock.
Decision-ready questions (no new evidence required) live in
[open-questions/_index.md](../open-questions/_index.md) under the
relevant tier.

**Source policy.** Summaries are written from memory for games the
author is confident about. For games with regional variation or fiddly
scoring (Skat, French Tarot, Doppelkopf, Sheepshead, Piquet,
regional Scopa variants), the entry flags where
[Pagat](https://www.pagat.com/) should be consulted before committing
to a real implementation. Pagat covers card games only; board-game
entries (the topology ladder below) pin their variant to a named public
rule source instead, with the native OpenSpiel implementation as the
executable tiebreaker where one exists.

## Coverage by open question

| Open question | Needs | Top candidates |
|---|---|---|
| [special-cards-declaration](../open-questions/special-cards-declaration.md) (contextual rank) | 2nd play-time *relative*-rank card beyond Tichu's Phoenix | **[euchre](#euchre)** (bowers: rank *and effective suit* remap, in the base rules, keyed to a runtime-chosen trump), [president](#president) single-joker variant ("one higher than the card below it") |
| [move-level-visibility](../open-questions/move-level-visibility.md) | per-observer move-level override (forces replace-vs-merge) | **poker "show one, show all"** — no longer game-gated: Texas Hold'em is [in the corpus](holdem.md) with the rule deliberately not modelled, and Stud's showdown would take the same override. See the question file |
| [memory-event-syntax](../open-questions/memory-event-syntax.md) | an event composition can't express | **[hanabi](#hanabi)** (partial-identity hint over an inverted hand — forces it; _dedicated deck, out of scope_), [cabo](#cabo) (composable from existing ops) |
| [knowledge-events](../open-questions/knowledge-events.md) | phase outcome observed unequally | **[mascarade](#mascarade)**, [love-letter](#love-letter) (both _dedicated deck, out of scope_); Belote (now in the corpus) supplies the in-play announce-and-show data point — see the question file |
| [structural-infoset-proofs](../open-questions/structural-infoset-proofs.md) | board-shaped instances of the compound hidden-function probe, extending the Cheat-anchored constructive world generator to spatial hiding | **[battleship](#battleship)** (shot result = public predicate of a hidden board), [stratego-barrage](#stratego-barrage) (combat double-reveal) |
| [unbounded-lines-and-max-length](../open-questions/unbounded-lines-and-max-length.md) | a game whose legal lines cycle, forcing the draw-rule design | **[nine-mens-morris](#nine-mens-morris)**, [english-draughts](#english-draughts) (both counter-based draw rules; wave C of the topology ladder is gated on this settlement) |
| [rule-scope-beyond-trick-play](../open-questions/rule-scope-beyond-trick-play.md) | a reusable declarative constraint on a non-trick decision site | **[english-draughts](#english-draughts)** (mandatory capture), [nine-mens-morris](#nine-mens-morris) (in-mill removal restriction) — the pair forcing rules to bind at every kernel decision site |

`higher-order-knowledge` is no longer listed: the verified pass found no
card game whose *rules* read second-order knowledge (Hanabi and
Sheepshead were debunked at the rule level), so it was resolved as
not-forced and moved to [decisions.md](../decisions.md) "Higher-order
knowledge is out of scope". Two questions —
[memory-event-syntax](../open-questions/memory-event-syntax.md) and
[knowledge-events](../open-questions/knowledge-events.md) — are now
blocked on a *scope decision* rather than on finding a game: their
cleanest forcing functions (Hanabi; Mascarade / Love Letter) are
dedicated-deck games outside the current standard-deck corpus.

## Trick-taking with bidding

### euchre

4 players (partnerships of 2), 24-card deck (9–A only), five-card hands,
two-round trump-making (order up the turned card, then name a suit), play
to 10 points.

**Why interesting.** The bowers are the sharpest known witness for
[special-cards-declaration](../open-questions/special-cards-declaration.md)'s
contextual-rank axis, and they go further than Tichu's Phoenix: the jack of
trumps becomes the highest trump, and the jack of the *same-colour* suit
changes its **effective suit** — it is a trump for following, beating, and
leading, keyed to a trump suit chosen at runtime. Any design that only
remaps rank (not suit-for-follow-purposes) fails Euchre in the base rules,
not a variant. Secondary pressures: the 24-card stripped deck exercises the
deck declaration, and the accept-or-name trump-making is a compact two-round
auction shape. "Going alone" adds a mid-auction participation change.

**Notes.** **Pagat** for the trump-making sequence, stick-the-dealer, and
going-alone scoring: <https://www.pagat.com/euchre/euchre.html>. North
American rules; British variants differ in deck size.

### piquet

2 players, 32-card deck, three phases per deal (declarations, play,
scoring) with elaborate structured scoring: carte blanche, point,
sequences, sets, capot, pique, repique.

**Why interesting.** Among the most heavily structured-scored games
in existence. Each phase contributes scoring events that can change
the *order and value* of subsequent ones (pique, repique). A stress
test for the scoring-component composition story in
[decisions.md](../decisions.md) and for the triggered-scoring
machinery committed there.

**Notes.** **Pagat is mandatory** here — Piquet's scoring is
notoriously edge-case heavy: <https://www.pagat.com/last/piquet.html>.

## Trick-taking with partnerships

### koenigrufen

4 players, 54-card *Industrie und Glück* Tarock pack (tarot family, like
French Tarot — within extended corpus scope). The declarer "calls a
King"; whoever holds it is the secret partner.

**Why interesting.** The named reopener for the settled access
discipline ([decisions.md](../decisions.md) "Typed object model"): the
queried card is **chosen at runtime** ("names a suit, the holder of
that king becomes partner"), and the rules name the degenerate
resolutions — "it is legal to call your own king" (declarer ends up
solo) and "you also play alone if the called king happens to be in the
talon" (the holding query resolves to no player). Scoring bonuses
("called king captured by declarer's opponents", "king ultimo") read
the call-derived side. If its runtime-chosen relational subject resists
the player-indexed-state flattening Doppelkopf's Fox rule settled on,
the discipline gets its stress test.
**Pagat**: <https://www.pagat.com/tarot/koenig.html>.

### sheepshead

5 players (most common), 32-card Skat pack (7–A in four suits). One
player is "picker" against the others — or calls a partner via a specific
card ("I call the Jack of Diamonds" / a fail-suit ace).

**Why interesting.** *Calling a partner by card identity* creates a
partnership defined by whoever holds a specific card, and the partner
*knows* they are the partner before anyone else. It **corroborates** the settled access discipline
([decisions.md](../decisions.md) "Typed object model") — the "partner"
reference resolves through a card-holding query — and the verified pass
found it does **not force multi-hop depth**: no scoring rule goes the
second hop ("partner of the holder of X"); play-legality constraints
are one hop ("the holder of the called ace must reserve it").
It is *not* a higher-order-knowledge case either — the partner's identity
is first-order hidden information, and no rule reads knowledge-of-
knowledge (that question is now resolved as not-forced). **Pagat**:
<https://www.pagat.com/schafkopf/shep.html>.

## Climbing & shedding

### president

3+ players, standard 52, climbing where each play must beat the
previous play (single card, pair, triple, etc.). Cross-hand routing:
losers must give their highest cards to winners at the start of the
next hand.

**Why interesting — two distinct draws:**

- *Cross-hand routing* that fires *between hands* (President of last
  hand receives from Asshole, etc.) — a different shape from Getaway's
  first-trick-to-waste, and probably the cleanest shape for a cross-hand
  setup helper rather than a Trick parameter. Cross-hand state (the
  President/Asshole assignment) gates the next hand's setup.
- *Contextual rank* — the verified forcing function for the
  [special-cards-declaration](../open-questions/special-cards-declaration.md)
  residual (play-time relative rank, the hard Phoenix shape). In the
  widespread single-joker variant, "a joker played by itself is one
  higher than the card played before it" (a joker on a 5 is a 6) — the
  Tichu-Phoenix shape ("half a rank above the last play") in a
  standard-52 game, documented on Pagat. The related "transparent
  threes" variant (a three becomes the rank it beats) is also
  relative-to-play. By contrast Haggis's wild J/Q/K and the Great
  Dalmuti's Jester are *chosen-constant* wilds (the easy shape) — they
  do **not** force the relative-rank design, despite looking like they
  might.

**Notes.** Known by many names: Asshole, Daihinmin (Japan), Capitalism,
Scum. Contextual rank is *variant-gated* — the basic game has no jokers;
cite the joker-single variant specifically. **Pagat**:
<https://www.pagat.com/climbing/president.html>.

(Big Two, formerly a candidate here, is now in the corpus
([big-two.cardlang](big-two.cardlang)) as the second combination-climbing
instance after Tichu — it drives the `climb` kernel construct.)

### crazy-eights

2+ players, standard 52, shedding with wild cards (8s) and
forced-draw when no legal play.

**Why interesting.** The simplest game in the corpus with a *draw*
mechanic responding to inability to play — a clean test of the
`if_impossible` fallback when the player has no legal move. Wild
cards (8s let the player choose the next suit) introduce a
mid-move state change that's a miniature typed-phase outcome.

**Notes.** UNO is a commercial near-variant with custom cards and
extra effects (Draw Two, Skip, Reverse, Wild Draw Four). Crazy
Eights first; UNO is a delta with extra card effects.

## Capture & fishing

### scopa

2 or 4 players (partnerships), 40-card Italian deck. Capture-by-sum:
a played card captures a single table card of equal rank, or a set
of table cards whose ranks sum to it.

**Why interesting.** A fishing mechanic — capture rather than
trick-take. Cards on the table form an evolving public zone; the
played card's destination depends on which capture combination is
selected. Tests the settled access discipline ([decisions.md](../decisions.md)
"Typed object model") on multi-card target selection and the move
type's relation to a shared zone.

**Notes.** Correction to flag: in **base** Scopa, when a single-card
rank match exists you are *forced* to take the single card — the
sum-capture is only the fallback, and free choice between rank-match and
sum (and the "sum to 15" rule) belong to variants (Cirulla / Scopa a
Quindici). So the "player chooses among multiple captures" framing is
variant-specific. **Pagat** for capture rules and four-way scoring
(cards, denari, settebello, primiera):
<https://www.pagat.com/fishing/scopa.html>. Scopone is the 4-player
partnership variant.

### cassino

2–4 players, standard 52, English fishing variant with capture-by-sum
*and* building (creating multi-card combinations on the table that
must be captured as a single unit).

**Why interesting.** Builds are *persistent multi-player state*: a
build of 8 sits on the table claimed by a specific player; another
player can capture it, add to it (extending the build), or pass.
Strong test of stateful intermediate zones and per-player claims on
shared content. Distinct from Scopa's simpler capture-only model.

**Notes.** Royal Cassino lets face cards capture by named value;
Diamond Cassino adds bonus scoring. Standard Cassino suffices.

## Rummy family

(Gin Rummy — [gin-rummy.md](gin-rummy.md) — anchors the `turns` form and
joint-predicate selection; Canasta — [canasta.md](canasta.md) — settled
meld groups as flattened zone families and answered the frozen-pile
zone-state question, both now in [decisions.md](../decisions.md). Hand
and Foot, a Canasta extension with two hands per player — the "hand"
played first, then the "foot" — would be a delta on the Canasta file if
ever wanted.)

## Memory, bluff, inference

(Cheat, formerly a candidate here, is now in the corpus
([cheat.cardlang](cheat.cardlang)): the compound hidden-function probe
anchoring the constructive world generator of
[structural-infoset-proofs](../open-questions/structural-infoset-proofs.md),
and the second challenge-window instance after Coup.)

### hanabi

2–5 players, 50-card custom deck (5 suits × 1,1,1,2,2,3,3,4,4,5),
cooperative: players hold their cards facing outward — they see
each other's cards but not their own — and must play cards in
ascending-by-suit order using a limited communication budget.

**Why interesting — the verified forcing function for
[memory-event-syntax](../open-questions/memory-event-syntax.md).** Two
features combine into the first event the pass found that is *neither* a
stdlib op nor a clean composition of them: (1) the **inverted-visibility
hand** — `hand[player]` is `identity to all_except(player)`, the owner
sees *less* than everyone else; (2) the **hint** — a colour or number
hint must indicate *all* matching cards (and may indicate zero), so it's
a per-attribute, multi-position, complete-information projection update to
one observer about cards they can't see, carrying negative information
("your other cards are not red"). That's not `peek`, `reveal`, or
`announce`. This is the case the open-question file ("awaits a case
composition can't express") was waiting for.

It does **not** force higher-order-knowledge: that question is now
resolved as not-forced (decisions.md "Higher-order knowledge is out of
scope") — Hanabi's *rules* read only objective tile facts; the
second-/third-order reasoning in the optimal-play literature (Bouzy, Cox)
lives in player conventions, outside the rules.

**Notes.** Modern (Bauza, 2010). Dedicated deck → **out of current corpus
scope**; bringing it in is a scope decision, not a search problem. The 6th
(multicolour) suit variant is usually a *short* 5-card suit (55 cards),
occasionally a full 10 (60); the base game is 50.

### cabo

2–6 players, **dedicated point deck** (suits numbered 0–13, commonly four
each of 1–12 plus two 0s and two 13s; *not* standard 52 + 2 jokers —
that's the folk Cambio/Pablo variant). Players are dealt four face-down
cards, briefly peek at two of their own, then play swap/reveal/peek
actions toward a low total. Whoever calls "Cabo" with the lowest total
wins; wrong calls pay penalties.

**Why interesting — a memory game, but everything is composable.** The
verified actions are peek-own, peek-opponent (`peek`), reveal-on-failed-
match (`reveal`), and **blind-swap** (transfer two cards with no
observation). All map to existing stdlib ops or trivial compositions, so
Cabo does **not** force custom-event declaration syntax — it confirms the
"composition suffices" hypothesis. Its one contribution is making
blind-swap a *first-class, deliberate* action (move cards + destroy
per-slot identity knowledge, reveal nothing), which argues for stating
that semantics explicitly. (The "King look-then-swap" power attributed to
Cabo previously could not be verified in any authoritative ruleset — it
exists only in a Malaysian standard-deck folk variant, as a blind swap.)

**Notes.** Cambio / Pablo / Cactus are the standard-52 folk versions. The
Cabo call is a typed-phase outcome with verification at round end.
Dedicated deck → out of current corpus scope.

### mascarade

3+ players, dedicated character-card deck. Each player has one face-down
character card; on a turn a player may swap their card with another's
*under the table without looking*, or claim a character's power.

**Why interesting — the cleanest verified forcing function for
[knowledge-events](../open-questions/knowledge-events.md).** "Exchange
your Mask" resolves to *swapped* or *not swapped*, and that outcome is
observed **unequally by construction**: the acting player knows whether
the swap happened; the player whose card was taken does *not*; the table
sees only that an exchange occurred — and even the actor doesn't learn the
card identities. The unequal observation is structural to the move, not an
optional peek. The phase outcome itself is partial to different observers
— exactly the construct. **Notes.** Bruno Faidutti; dedicated deck → out
of current corpus scope. Asmodee v2 rulebook is authoritative.

### love-letter

2–6 players, 16-card dedicated deck. Each player holds one card; on a turn
you draw one and play one, resolving its effect.

**Why interesting.** The strongest *standard-shaped* corroborator for
[knowledge-events](../open-questions/knowledge-events.md): the **Baron**
("you and that player secretly compare hands; the lower is out") is one
resolution step that produces three information states — the two comparers
learn each other's card, the table learns only "who lost", and only the
loser's card is then revealed. The **Priest** (privately look at one
player's hand) is a second case. The **Guard** (public hit/miss) is *not*
— a useful contrast. **Notes.** Kanai / AEG; dedicated deck → out of
current corpus scope; official 2019 rulebook is authoritative.

### eleusis

2+ players, two standard 52 decks. Scientific-induction game: one
player ("God") sets a secret rule for legal cards; others
("scientists") play cards trying to deduce the rule, with God
marking each play legal or illegal.

**Why interesting.** Among the few games where the *rule itself is
hidden state*. A strong stretch of the DSL's hidden-information
model — the secret rule is per-game, not per-player, and is
queried by every play. Doesn't fit standard-deck conventions
cleanly; included as a provocation rather than a Tier 1 candidate.

**Notes.** Robert Abbott, 1956. Mostly useful as inspiration for
the inference-game corner of the design space.

## Staking & resource games

### omaha-hi-lo

2–10 players, standard 52, community-card poker like
[Hold'em](holdem.md) but with four hole cards (use exactly two)
and split pots: best high hand and best qualifying low hand each
take half.

**Why interesting.** Split-pot scoring: each pot resolves to *two
winners by different criteria* (high hand and best qualifying low
hand take half each), with the low half requiring five unpaired
cards each ≤ 8. With Hold'em now in the corpus the community board
and the side-pot layering are both already carried, so what Omaha
newly forces is exactly the per-pot SPLIT — a per-game shape that
fits the "each game declares its own scoring structure" decision in
decisions.md "Scoring composition". The use-exactly-two constraint
is a second pressure: Hold'em's evaluator takes the best five of
seven unconstrained, which Omaha cannot.

**Notes.** "Eight or better" is the standard low-half qualifier;
"Omaha 8" is a common shorthand.

### liars-dice

2+ players, 5 dice per player + dice cups. Bidding game: each bid
claims a count of a face value across all dice; the next player
either out-bids or challenges the previous bid.

**Why interesting.** *Not a card game* — but exercises the
visibility model in an instructive way: each player's dice are
private (peek after roll), the bid is public, and the challenge
reveals everyone's dice at once. The dice are individuated neither
as cards (no rank/suit) nor as fungible resources (the *count* of
each face matters and acts like `count_by_type`). Useful
provocation for whether the projection lattice in
[decisions.md](../decisions.md) is uniform across content types,
and another resource-style transfer game (the amount syntax is
settled in decisions.md "Resource amount syntax").

**Notes.** Perudo is the South American variant with the "calza"
(exact-call) action. Included to stress-test the DSL's scope, not
because it's a card game.

## Solitaire & patience

### spider

1 player, two 52-card decks, solitaire with ten tableau columns.
Sequences must form same-suit runs to be removed to foundations.

**Why interesting.** The *removal criterion* (complete K-to-A run
in one suit) is a stronger combination-recognition test than
Klondike's foundations. Bridges solitaire and meld-recognition (Gin
Rummy). The positional substrate is in place
([klondike](klondike.md) + [freecell](freecell.md) — position
domains, Cascade/HiddenStack column pairs, `top_of`); Spider's new
pressure is the removal recognizer and the ten-column two-deck
scale, plus a genuine test of the run-invariant assumption: Spider's
mid-game deals drop a fresh row onto the piles, so a face-up pile is
NOT rank-monotone and the rank-filter suffix denotation no longer
covers every legal unit move — the positional-slice movement
recorded as deferred in issue #111.

## Boards: the topology witness ladder

The witness ladder for the topology axis
([design-notes/generalization-path.md](../design-notes/generalization-path.md)
§1), in graduation order; the model each rung tests, the selection
criteria, the coverage matrix, and the rejected candidates (Snakes &
Ladders, Ludo, phantom variants, chess, Go, Quoridor, tile-layers) are
in [design-notes/board-topology.md](../design-notes/board-topology.md).
Each rung adds exactly one mechanism over its predecessors, and every
rung except Barrage has a native OpenSpiel implementation as a
differential oracle. Not card games — precedent for that is
[liars-dice](#liars-dice), below — but unlike the provocation entries,
these are real pipeline candidates: the dream goal on the project's own
table is all fixed-outcome board games.

(Tic-tac-toe, the ladder's first rung, is now in the corpus
([tic-tac-toe.md](tic-tac-toe.md)): the walking skeleton for the whole
axis — board declaration, the minted `cell` domain, cell-indexed zone
families, the placement vocabulary, declared line patterns, `turns` on a
board, and draw-on-full-board — perfect information and monotone, the
baseline every later rung changes exactly one thing against. Rules are
common knowledge; OpenSpiel's native `tic_tac_toe` is the differential
oracle.)

(Breakthrough, the ladder's second rung, is now in the corpus
([breakthrough.md](breakthrough.md)): the movement rung — per-player
direction frames ("forward" as a per-seat transform over one shared
board), the minted `dir` domain and the `step(from, along)` vocabulary,
the neighbor/region query verbs, `for each cell` setup over `home`,
displacement capture into a public captured pile, and two termini
(reach `far_row`, or take the last enemy man). Still monotone — every
move advances or removes a man — so no draw machinery. Invented by Dan
Troyka, 2000; OpenSpiel's native `breakthrough` is the differential
oracle.)

### backgammon

2 players, the 24-point track + bar + bear-off, 15 checkers each, two
dice. Race game: enter and run checkers per pip counts, hit blots to
the bar; bear off on the exact roll, or with a higher roll from the
rearmost checker once no higher point is occupied; first fleet off
wins. **Single game, no
doubling cube** (the cube is a wager layer, excluded to match the
oracle's scope; a later variant delta if wanted).

**Why interesting.** The chance rung — and only that: the first
mid-game chance nodes (`roll`), which are a replay-model change
([design-notes/domain-map.md](../design-notes/domain-map.md), the
in-play-dice tripwire), on the track family (one shared 24-cell track
under opposed per-player pip frames; bar and tray are ordinary
zones), per-point stacks (blots and made points as count guards), bar
re-entry, and exact-or-highest bear-off. Named the cheapest topology entry by
generalization-path §1; the ladder puts two deterministic rungs before
it so the chance change lands in isolation.

**Notes.** Backgammon rules are heavily standardized (e.g. US
Backgammon Federation rules). OpenSpiel `backgammon` (thoroughly
tested, explicit-stochastic) is the oracle.

### battleship

2 players, two private 10×10 grids, the 1990 Milton Bradley fleet
(carrier 5, battleship 4, cruiser 3, submarine 3, destroyer 2). Place
ships secretly (horizontal/vertical, no overlap); alternate calling
shots; hit/miss announced per shot, ship type announced when sunk;
repeated shots illegal; first fleet sunk loses.

**Why interesting.** The first hidden-information board: per-player
hidden cell families (identity to owner, nothing to others) and the
**probe action** — a shot's result is a public function of a hidden
zone's true contents: the compound hidden-function probe class whose
Cheat anchor landed the constructive world generator
(`tests/openspiel_ready/worlds.py`;
[structural-infoset-proofs](../open-questions/structural-infoset-proofs.md)).
Battleship extends that generator to spatial hiding — the question's
recorded residual — so the two are budgeted together. Footprint
placement (one decision, a bounded effect placing each segment) and
monotone shot sets keep everything else already-earned.

**Notes.** 1990 Milton Bradley rules; note some editions announce ship
type on every hit — the pin announces type on sink only. OpenSpiel
`battleship` (imperfect-information, CFR-consumable) is the oracle,
parameterized to match: default `ship_sizes [2;3;3;4;5]`,
`allow_repeated_shots=false`, `loss_multiplier=1.0` (zero-sum).

### stratego-barrage

2 players, the 10×10 Stratego board with lakes, 8 pieces per side:
Flag, Spy, 2 Scouts, Miner, General, Marshal, Bomb, placed secretly in
the back rows. Pieces move one square orthogonally (Scouts any clear
distance); attacking reveals both ranks and removes the loser (Spy
kills Marshal when attacking; Miner defuses Bomb; Flag capture wins);
two-square shuttle rule in scope (its tracking state is
position-typed — the recorded position-typed-state wall lifts here,
first witness), the chase rule scoped out and named.

**Why interesting.** The one moat-level rung: position-public,
rank-private pieces force **attribute-level projections** (C3) and
**anonymous-persistent identity** on movement events (C6) — the
per-object visibility risk the domain map marks as its own workstream,
with the extended partition proofs as the acceptance bar, landed
before the game. Combat is the second compound hidden-function probe;
scout moves and moved-so-not-a-bomb narrowing test that candidate-set
semantics derive partial identity from public movement correctly.
Barrage is the minimal variant carrying all of it; Banqi/Luzhanqi are
the named second witnesses if C3/C6 generality needs one.

**Notes.** Jumbo's official Stratego rules, Barrage/"duel" quick-play
variant. **No OpenSpiel oracle** (verified absent) — acceptance is the
proof battery plus playout characterization, flagged as the ladder's
one non-differential rung.

### hex

2 players, 11×11 hex rhombus, no swap rule. Alternate placing stones;
win by connecting your two opposite sides.

**Why interesting.** Exactly one addition: the bounded `reachable`
fixed point (class-5 connectivity) — the query generalization-path §1
calls the real design object of the axis — on a hex tiling entry.
Monotone, drawless (a filled hex board always has a winner), perfect
information: everything else is wave-A machinery.

**Notes.** Rules are two sentences; the pin excludes the swap/pie rule
to match the oracle default. OpenSpiel `hex` (`board_size=11`,
`swap=false`) is the oracle.

### nine-mens-morris

2 players, the 24-point mill board (an enumerated graph, not a grid),
9 men each. Phase 1: alternate placing; phase 2: move to adjacent
points; a player reduced to 3 men flies anywhere. Forming a mill
(three declared collinear points) removes an opponent man — not from
an opponent mill unless nothing else is available. Reduce the opponent
to two men, or block them from moving, to win.

**Why interesting.** The non-grid rung: an enumerated graph entry with
declared mills, the place→move→fly phase shift on one board,
mill-triggered removal (a second decision inside the turn, with the
in-mill removal restriction as its guard), blockade loss
(no-legal-move as a termination predicate), and the ladder's first
cyclic movement — which is why it is **gated on settling**
[unbounded-lines-and-max-length](../open-questions/unbounded-lines-and-max-length.md)
(the draw rule; align the pin with the oracle's termination rule at
entry time).

**Notes.** Standard rules with the flying phase (flying is
variant-divergent across sources — the pin names it explicitly).
OpenSpiel `nine_mens_morris` is the oracle.

### english-draughts

2 players, 8×8 board (dark squares), 12 men each. Men move/capture
diagonally forward; captures are **mandatory** and a chosen jump
sequence must be completed (no maximum-capture rule); reaching the
back row crowns a king (ending the move) that moves/captures both
ways; lose with no pieces or no legal move; 40-move no-capture rule
draws.

**Why interesting.** The rule-composition rung: mandatory capture as a
rule whose demand narrows the vocabulary to jumps when any exist —
with [nine-mens-morris](#nine-mens-morris)'s in-mill removal
restriction, the forcing pair for
[rule-scope-beyond-trick-play](../open-questions/rule-scope-beyond-trick-play.md)
(rules constraining non-trick decision sites are validated but
unenforced today; the ladder resolves that by binding rules at every
kernel decision site) — jump
`(from, over, to)` triples as declared relation data, multi-jump
chains on the `turns` form's `again` axis with a position-typed chain
anchor (reusing the wall-lift the [stratego-barrage](#stratego-barrage)
rung lands),
promotion as a supply swap, and counter-based draw state. English over
International deliberately: no capture maximization, so the gated
optimization query class stays unwitnessed. Same
unbounded-lines gate as morris.

**Notes.** WCDF/APA English draughts rules. OpenSpiel `checkers`
implements exactly this pin (forced captures, 40-move no-capture
draw) and is the oracle.

## Edge-case experiments

### gops

2 players, standard 52: one suit is the prize deck, flipped one card at a
time; players simultaneously bid one card from their hand of a suit each;
higher bid takes the prize's value. Sealed bids, revealed together.

**Why interesting.** The *minimal in-scope* witness for sealed
simultaneous decisions — a genuine simultaneous-move game (not
sequentialized-by-convention like the corpus's exchange phases), which is
what the MARL algorithms distinguish. Also the first **differential
validation** target: OpenSpiel ships a native `goofspiel`, so a DSL
implementation can be checked game-tree-against-reference — divergence on
identical lines is a bug in one of them. (The same angle applies to
[euchre](#euchre), [gin-rummy](gin-rummy.md), and Hearts, all of which have
native OpenSpiel implementations — a compiled game validating against a
hand-coded reference is the strongest external check the engine's
correctness story can get.)

**Notes.** Also called Goofspiel / Game of Pure Strategy. **Pagat**:
<https://www.pagat.com/adders/gops.html>.

### war

2 players, standard 52. Each player flips top card; higher card
wins both; ties trigger a "war" subroutine where additional cards
are committed and the winner takes all.

**Why interesting.** Trivial as a game — no choices. Worth
implementing *because* it has no choices: pure tests of zone
routing and *recursive sub-phase mechanics*. Ties recursively
trigger sub-routines that consume additional cards and accumulate
to the resolution winner — a stack-discipline sub-phase pattern
not yet exercised by the corpus.

**Notes.** Often dismissed as "not a real game." That's the point.

### egyptian-ratscrew

2+ players, standard 52, real-time slap-based capture: cards are
played to a center pile; whenever certain patterns appear (pair,
sandwich, ten-jack-queen), the first player to slap claims the
pile.

**Why interesting.** *Action priority is real-time* rather than
turn-ordered. Doesn't fit the DSL's current turn-based
assumptions; slaps are simultaneous moves with priority resolution
— could reopen the simultaneous body grammar question if implemented.

**Notes.** Provocation, not a realistic candidate. Real-time
mechanics are out of scope for the current DSL — the entry exists
to flag the gap.

### bohnanza

2–7 players, custom 154-card deck (8 bean varieties × varying
counts), must plant cards in hand-order; *trading* between players
is a core phase.

**Why interesting.** The Trading Phase is the cleanest "in-block
substructure" candidate from a real published game: any pair of
players can propose trades, accept/reject is conditional on offers, and
multiple trades can execute as a coordinated set. Forces grammar
for "if branch inside simultaneous block" and conditional commit.

**Notes.** Modern (Rosenberg, 1997). Out-of-scope for the
standard-52 family, but the trading mechanic is the strongest
cross-domain pull on DSL design choices.

### diplomacy

2–7 players, no cards (uses a map and pieces). Every player writes
orders simultaneously; all orders resolve at once with complex
inter-order dependencies (A supports B; if B is dislodged, A's
support fails).

**Why interesting.** The canonical forcing function for richer
simultaneous-body grammar (the now-closed open question; would
reopen if implemented). Orders interact: a hypothetical card-game
whose play phase had Diplomacy-like simultaneous order resolution
would absolutely
require non-trivial body grammar inside the `simultaneously:`
block.

**Notes.** Wildly out of scope (not a card game, has a map).
Included as a thought experiment — when reasoning about how rich
simultaneous bodies need to be, ask "could this express
Diplomacy?" as a worst-case bound.

## Long-horizon capstones

### marvel-snap

2 players, 12-card singleton decks drawn from a large closed card pool,
6 turns, 3 locations (each holding up to 4 cards per player). Both
players place cards face-down simultaneously each turn, then reveal in
priority order; power is compared per location; win 2 of 3. Born as a
physical prototype (Brode's team playtested it on a table), shipped as
a videogame — it lives in the liminal space between the two, which is
exactly why it's here.

**Why interesting — a capstone that composes nearly every deferred
thread at once, and nothing it needs is unrecorded:**

- *Simultaneous commit, ordered resolution.* Cards are committed
  face-down simultaneously, then resolved in priority order — the
  commit-then-sequentialize transform the simultaneity gap needs,
  present as a first-class designer-visible rule rather than an
  encoding trick. The opponent seeing *that* you played at a location
  but not *what* is `existence_only` at a position, verbatim.
- *Location effects are zone-scoped rules-as-values.* Each location
  carries a rule drawn from a closed pool, hidden and revealed on a
  schedule (turns 1–3) — a disciplined, well-behaved second witness
  for the rules-as-selectable-values axis (Fluxx is the wild one).
- *On Reveal / Ongoing* map one-to-one onto the effect-script
  requirements in
  [design-notes/deck-builder-onramp.md](../design-notes/deck-builder-onramp.md):
  on-play triggers and continuous derived modifiers, over a large but
  closed pool of small scripts — Innovation-density, below the bounded-
  MtG ceiling.
- *Snapping* is backgammon's doubling cube plus retreat-as-concession;
  bluff-snapping under hidden information is poker-shaped, which makes
  Snap a prime seat for the LLM-player angle
  ([design-notes/llm-player-seats.md](../design-notes/llm-player-seats.md)).
- *Deck construction* is parametrized setup over declared data (the
  Scrabble-lexicon mechanism), outside the game proper.

**Beyond hosting it, the payoffs are unusual:** a DSL implementation is
an executable spec to differential-test against the digital game
(divergent outcomes on identical seeds = a bug in one of them); new-card
design becomes a data problem (write a script, the totality checker and
simulation harness exercise it against the pool); and the game's
tabletop-prototype origins mean re-implementing it *recovers* the
physical artifact its designers started from.

**Notes.** Long-horizon: gated on the deck-builder effect-script
on-ramp and the simultaneity form — do not attempt before both exist.
Mechanics are uncopyrightable but the Marvel IP is not; anything shared
beyond personal/research use wants a re-theme.
