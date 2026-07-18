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
scoring (Skat, French Tarot, Doppelkopf, Sheepshead, Piquet, 500,
Belote, regional Scopa variants), the entry flags where
[Pagat](https://www.pagat.com/) should be consulted before committing
to a real implementation. Pagat covers card games only; board-game
entries (the topology ladder below) pin their variant to a named public
rule source instead, with the native OpenSpiel implementation as the
executable tiebreaker where one exists.

## Coverage by open question

| Open question | Needs | Top candidates |
|---|---|---|
| [special-cards-declaration](../open-questions/special-cards-declaration.md) (contextual rank) | 2nd play-time *relative*-rank card beyond Tichu's Phoenix | **[euchre](#euchre)** (bowers: rank *and effective suit* remap, in the base rules, keyed to a runtime-chosen trump), [president](#president) single-joker variant ("one higher than the card below it") |
| [move-level-visibility](../open-questions/move-level-visibility.md) | per-observer move-level override (forces replace-vs-merge) | **poker "show one, show all"** — a Stud or [holdem](#holdem) variant, exercisable in the *existing* poker corpus |
| [memory-event-syntax](../open-questions/memory-event-syntax.md) | an event composition can't express | **[hanabi](#hanabi)** (partial-identity hint over an inverted hand — forces it; _dedicated deck, out of scope_), [cabo](#cabo) (composable from existing ops) |
| [knowledge-events](../open-questions/knowledge-events.md) | phase outcome observed unequally | **[mascarade](#mascarade)**, [love-letter](#love-letter) (both _dedicated deck, out of scope_) |
| [structural-infoset-proofs](../open-questions/structural-infoset-proofs.md) | a compound hidden-function probe (public outcome as a non-trivial function of hidden state) | **[cheat](#cheat)** (challenge outcome = boolean function of hidden cards, then a reveal), [500](#500) open misère (corroborates: full reveal, not a function), [battleship](#battleship) (shot result = predicate of a hidden board), [stratego-barrage](#stratego-barrage) (combat) |
| [unbounded-lines-and-max-length](../open-questions/unbounded-lines-and-max-length.md) | a game whose legal lines cycle, forcing the draw-rule design | **[nine-mens-morris](#nine-mens-morris)**, [english-draughts](#english-draughts) (both counter-based draw rules; wave C of the topology ladder is gated on this settlement) |

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

### 500

4 players (partnerships of 2), 43- or 45-card deck, bidded trick-taking
with miseres and open miseres.

**Why interesting.** Some bids (Miseres) have *inverse* scoring —
declarer wants zero tricks. Open Miseres reveal the declarer's hand —
a knowledge event mid-phase that flips the visibility of a private
zone. Useful variant input to
[knowledge-events](../open-questions/knowledge-events.md), and a
second data point for inverse-outcome scoring beyond Hearts'
shoot-the-moon.

**Notes.** Multiple regional variants (Australian, Canadian, US).
**Pagat** for the bidding table and contract-by-contract scoring
brackets: <https://www.pagat.com/500/500.html>.

### belote

4 players (partnerships), 32-card deck, bidded trick-taking with
melding (Belote-Rebelote, sequences, four-of-a-kind), strict follow
rules.

**Why interesting.** Pinochle's continental cousin. Follow rules are
stricter than Pinochle's (in many variants: must overtrump the best
trump played so far by *partnership*, not just by self), exercising
the constrained-follow rule family in a new shape. Declarations of
melds happen *during* play (announced on the trick they're shown),
introducing mid-phase knowledge events that affect end-of-hand
scoring.

**Notes.** **Pagat** for declaration rules — what can be announced,
when, and how announcements interact: <https://www.pagat.com/jass/belote.html>.
Klaverjas (Dutch) is a near-twin; implement Belote first and treat
Klaverjas as a delta.

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

(Gin Rummy is in the corpus — [gin-rummy.md](gin-rummy.md) — anchoring the
`turns` form and joint-predicate selection.)

### canasta

4 players (partnerships), two 52-card decks + 4 jokers. Rummy with a
frozen discard pile, melds of seven (canastas), elaborate per-hand
scoring.

**Why interesting.** The *frozen pile* is an instance of a zone
whose state (frozen vs. unfrozen) changes the rule set for taking
from it — analogous to Hearts' `hearts_broken` sub-phase pattern, but
on a zone rather than a phase. Useful test of whether the
boolean-vs-sub-phase criterion in
[decisions.md](../decisions.md) generalizes to zone state.

**Notes.** Hand and Foot is a Canasta extension with two hands per
player (the "hand" played first, then the "foot"). Implement
Canasta first.

## Memory, bluff, inference

### cheat

3+ players, standard 52, shedding by claim: each play is face-down cards
plus a public rank claim ("three 7s"); any player may challenge, flipping
the played cards — the liar (or the wrong challenger) takes the whole pile.

**Why interesting — two high-leverage unblocks in one small game:**

- *The compound hidden-function probe* that
  [structural-infoset-proofs](../open-questions/structural-infoset-proofs.md)
  is blocked on: the challenge outcome is a **public boolean function of
  hidden content** (were the face-down cards what was claimed?), followed
  by a public reveal of exactly those cards. No simple swap axis survives
  that channel — this is the named data point for the constructive world
  generator.
- *The second real challenge window* after interactive Coup (and the claim
  vocabulary is open — any rank — where Coup's is closed), advancing the
  `challenge` stdlib promotion toward its third instance.

Claim-versus-content is also the modeling rule from decisions.md ("a
public assertion is a state variable *because* it is public") in its
purest form. Verified expressible at stress scope (the broad-sweep
branch hand-rolled it twice).

**Notes.** Known as I Doubt It / Bullshit / Bluff. **Pagat**:
<https://www.pagat.com/beating/cheat.html>.

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

### holdem

2–10 players, standard 52, community-card poker with two hole cards
and five public cards, four betting rounds.

**Why interesting.** Second resource-using game after Stud, with one
critical difference: *shared community cards* are observed by all
and used by every player in hand evaluation. Tests whether
the settled access discipline and
the existing visibility model handle a zone owned by no one but
used in every player's hand evaluation. Also a third resource-using
game (after Stud and Coup), confirming the resource-transfer decisions
now in decisions.md ("Resource amount syntax", "Resource transfer
failure"). And the verified home for
[move-level-visibility](../open-questions/move-level-visibility.md): the
"show one, show all" showdown rule (Robert's Rules §6) is a per-observer
move-level override that names *some* observers and *some* cards while the
rest stay at the zone default — "if only a portion of the hand has been
shown, there is no requirement to show the unseen cards" — which forces
the replace-vs-merge sub-question directly. This is exercisable in the
existing poker corpus (Stud already in), so move-level-visibility may not
need a new game at all.

**Notes.** Texas Hold'em is the canonical variant. No-limit vs fixed-limit is a
parameterization of the **betting form of `round`** (`order priority`), not a
structural change. Stud's betting is the template — the per-street `round
offering [check, bet, call, fold, raise]` plus the Stud-local `settle` for side
pots — and Hold'em would be the **second side-pot instance** that justifies
promoting a shared `betting`/pot definition (Coup, the other resource game, has a
coin/treasury economy with no pot, so it does not).

### omaha-hi-lo

2–10 players, standard 52, community-card poker like Hold'em but
with four hole cards (use exactly two) and split pots: best high
hand and best qualifying low hand each take half.

**Why interesting.** Split-pot scoring: each pot resolves to *two
winners by different criteria* (high hand and best qualifying low
hand take half each), with the low half requiring five unpaired
cards each ≤ 8. The shape extends Stud's pot-with-eligibility
pattern with a per-pot split — a per-game shape that fits the
"each game declares its own scoring structure" decision in
decisions.md "Scoring composition".

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

### klondike

1 player, standard 52, solitaire with seven tableau columns, four
foundations, draw from stock.

**Why interesting.** Canonical solitaire — explicitly deferred in
[roadmap.md](../roadmap.md) but flagged as a high-value test of
*positional zones*. Tableau columns have ordered visibility (top of
pile visible, beneath hidden until exposed), and movement obeys
positional adjacency rules. The DSL currently has no story for
positional zones; Klondike is the forcing function.

**Notes.** Klondike forces "ordered zone with positional visibility"
and "stack-movement primitive" as first-class design questions.

### freecell

1 player, standard 52, solitaire variant with all cards face-up at
deal, four free cells, eight tableau columns.

**Why interesting.** A Klondike variant with *no hidden
information* — positional but perfect-information. Tests whether
the positional-zone design forced by Klondike collapses cleanly to
the no-information case, or whether positional and informational
zone properties need orthogonal treatment.

### spider

1 player, two 52-card decks, solitaire with ten tableau columns.
Sequences must form same-suit runs to be removed to foundations.

**Why interesting.** The *removal criterion* (complete K-to-A run
in one suit) is a stronger combination-recognition test than
Klondike's foundations. Bridges solitaire and meld-recognition (Gin
Rummy). Useful third positional candidate; implementation can wait
until after Klondike+FreeCell expose the right primitives.

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

### tic-tac-toe

2 players, 3×3 grid, 5+4 marks. Alternate placing on empty cells;
three in a line wins; full board draws.

**Why interesting.** The walking skeleton for the whole axis: board
declaration, the `Cell` parameter domain, cell-indexed zone families,
the placement vocabulary, declared line patterns, `turns` on a board,
draw-on-full-board. Perfect information and monotone, so the
observation model does not move at all — which is the point: every
later rung changes one thing against this baseline.

**Notes.** Rules are common knowledge; OpenSpiel `tic_tac_toe`
(thoroughly tested) is the oracle.

### breakthrough

2 players, 8×8 grid, 16 pawn-like pieces each. Move one piece one
square straight or diagonally forward; capture diagonally only; first
to reach the opponent's back row wins.

**Why interesting.** The movement rung: per-player direction frames
("forward" as a declared per-seat transform over one shared board),
the step/capture vocabulary with `Cell` (or cell × direction)
parameters, displacement capture into a captured pile, reach-region
win. Still monotone — pieces only advance, so no draw machinery.

**Notes.** Invented by Dan Troyka, 2000; rules on the inventor's and
standard abstract-games references. OpenSpiel `breakthrough`
(thoroughly tested; `rows`/`columns` parameters) is the oracle.

### backgammon

2 players, the 24-point track + bar + bear-off, 15 checkers each, two
dice. Race game: enter and run checkers per pip counts, hit blots to
the bar, bear off exactly; first fleet off wins. **Single game, no
doubling cube** (the cube is a wager layer, excluded to match the
oracle's scope; a later variant delta if wanted).

**Why interesting.** The chance rung — and only that: the first
mid-game chance nodes (`roll`), which are a replay-model change
([design-notes/domain-map.md](../design-notes/domain-map.md), the
in-play-dice tripwire), on the track family (one shared 24-cell track
under opposed per-player pip frames; bar and tray are ordinary
zones), per-point stacks (blots and made points as count guards), bar
re-entry, and exact-policy bear-off. Named the cheapest topology entry by
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
zone's true contents, which is exactly the compound hidden-function
probe [structural-infoset-proofs](../open-questions/structural-infoset-proofs.md)
awaits, in board shape (Cheat is the card shape); budget the two
together per the domain map. Footprint placement (one decision, a
bounded effect placing each segment) and monotone shot sets keep
everything else already-earned.

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
two-square shuttle rule in scope, the chase rule scoped out and named.

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
rule whose demand narrows the vocabulary to jumps when any exist, jump
`(from, over, to)` triples as declared relation data, multi-jump
chains on the `turns` form's `again` axis with a `Cell?` chain anchor,
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
