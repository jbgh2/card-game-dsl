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
to a real implementation.

## Coverage by open question

| Open question | Needs | Top candidates |
|---|---|---|
| [simultaneous-body-grammar](../open-questions/simultaneous-body-grammar.md) | simultaneous step with substructure | [diplomacy](#diplomacy), [bohnanza](#bohnanza), [coup](#coup) (challenge resolution) |
| [typed-amount-syntax](../open-questions/typed-amount-syntax.md), [transfer-failure](../open-questions/transfer-failure.md), [move-level-visibility](../open-questions/move-level-visibility.md) | second resource-using game | [holdem](#holdem), [omaha-hi-lo](#omaha-hi-lo), [liars-dice](#liars-dice) |
| [zone-access-syntax](../open-questions/zone-access-syntax.md) | game with complex relational receivers | [doppelkopf](#doppelkopf), [sheepshead](#sheepshead) |
| [memory-event-syntax](../open-questions/memory-event-syntax.md) | three to four examples beyond stdlib ops | [hanabi](#hanabi) (information tokens), [cabo](#cabo) (peek-and-swap), [coup](#coup) (reveal-then-rehide) |
| [higher-order-knowledge](../open-questions/higher-order-knowledge.md) | a rule that reads second-order knowledge | [hanabi](#hanabi) (canonical), [coup](#coup) (bluff modeling), [eleusis](#eleusis) (rule inference) |
| [knowledge-events](../open-questions/knowledge-events.md) | phase outcome observed unequally | [coup](#coup) (challenge reveals), [belote](#belote) (in-play declarations) |

## Trick-taking with bidding

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

### doppelkopf

4 players, 48-card double-pinochle deck, trick-taking where
partnerships are *not* fixed: each player holds private knowledge of
which side they're on (based on which player holds the Queens of
Clubs), and partnerships are revealed through play.

**Why interesting.** The canonical
[zone-access-syntax](../open-questions/zone-access-syntax.md) test
case. Queries like "partner of (player holding Queen of Clubs other
than me)" are complex relational chains in subject position.
Announcements ("Re", "Kontra", "No 90", "No 60") are spoken by
individual players but bind partnership-level contracts — distinct
from Bridge's dummy in that the speaker is both actor and chooser
of their own announcement; the partnership-binding is a scoring
concern, not a delegated-play one.

**Notes.** Rules vary by region. **Pagat** for tournament rules and
the special-card hierarchy: <https://www.pagat.com/schafk/doko.html>.

### sheepshead

5 players (most common), 32-card double-pinochle deck. One player is
"picker" against the others — or calls a partner via a specific card
("I call the Jack of Diamonds").

**Why interesting.** *Calling a partner by card identity* creates a
partnership defined by whoever holds a specific card. The partner
*knows* they are the partner; the picker and the other defenders
don't — until the called card is played. Strong material for both
[zone-access-syntax](../open-questions/zone-access-syntax.md) (the
"partner" reference resolves through a card-holding query) and
[higher-order-knowledge](../open-questions/higher-order-knowledge.md)
(the picker knows the partner knows but doesn't know who knows).

**Notes.** US Wisconsin variant is the most widely played. **Pagat**
for variant choice and the leaster / jack-of-diamonds-down rules:
<https://www.pagat.com/schafk/shphd.html>.

## Climbing & shedding

### president

3+ players, standard 52, climbing where each play must beat the
previous play (single card, pair, triple, etc.). Cross-hand routing:
losers must give their highest cards to winners at the start of the
next hand.

**Why interesting.** Routing override that fires *between hands*
(President of last hand receives from Asshole, etc.) — a different
shape from Getaway's first-trick-to-waste, and probably the cleanest
shape for a cross-hand setup helper or per-game function rather than
a Trick parameter. Cross-hand
state (the President/Asshole assignment) gates the next hand's
setup.

**Notes.** Known by many names: Asshole, Daihinmin (Japan),
Capitalism, Scum. Rules vary widely on combinations, revolutions,
and wild twos. **Pagat** for a canonical version:
<https://www.pagat.com/climbing/president.html>.

### big-two

4 players, standard 52, climbing where combinations (single, pair,
triple, five-card hands — straight / flush / full-house /
four-plus-one / straight-flush) are played in sequence; first to
empty hand wins.

**Why interesting.** Combination-based climbing — each "play" is a
*multi-card move* whose legality is a structured predicate over the
played set (the combination must be of the same type as the
previous play and beat it). Useful test of how the DSL expresses
"valid combination" as a rule on a `play_combination` move type.
Contrast with President's simpler "single card beats single card."

**Notes.** Cantonese and Asian variants have slightly different
combination hierarchies. Standard Big Two suffices.

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
selected (often multiple legal captures exist, with the player
choosing). Tests
[zone-access-syntax](../open-questions/zone-access-syntax.md) on
multi-card target selection and the move type's relation to a
shared zone.

**Notes.** **Pagat** for the capture rules and the four-way
end-of-hand scoring (cards, denari, settebello, primiera):
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

### gin-rummy

2 players, standard 52, set/run formation with knock-or-gin
termination.

**Why interesting.** Introduces *meld* as a fundamental concept the
current corpus doesn't have. A meld is a multi-card group held in
the player's own hand (not transferred to a capture zone) that
must be *recognized* — the hand's score depends on which subset of
cards forms valid melds vs. deadwood. New shape of move: a "knock"
announces a configuration that triggers scoring without moving any
cards into a capture zone.

**Notes.** Knock-or-gin termination is a classic typed-phase outcome
(knock with N deadwood / gin with 0 / undercut by opponent's
better-or-equal melds).

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

### hanabi

2–5 players, 50-card custom deck (5 suits × 1,1,1,2,2,3,3,4,4,5),
cooperative: players hold their cards facing outward — they see
each other's cards but not their own — and must play cards in
ascending-by-suit order using a limited communication budget.

**Why interesting.** The canonical
[higher-order-knowledge](../open-questions/higher-order-knowledge.md)
game. Information given by one player constrains what the recipient
can deduce, and the giver knows what the recipient can deduce; the
literature on optimal Hanabi (Bouzy, Cox, etc.) explicitly models
second- and third-order knowledge. Also a clean test of inverse
zone visibility: `hand[player]` is `identity to all_except(player)`
— the inverse of the standard `Hand<player>` projection. The hint
actions (color hint, number hint) are
[memory-event-syntax](../open-questions/memory-event-syntax.md)
candidates distinct from card movement.

**Notes.** Modern (Bauza, 2010). Strong "what does the rules engine
need to track to support optimal play" forcing function.

### cabo

2–6 players, standard 52 + 2 jokers. Memory-and-bluff: players are
dealt four face-down cards, briefly peek at two of their own, and
then play through swap/reveal/peek actions toward a low total.
Whoever calls "Cabo" with the lowest total wins; wrong calls pay
penalties.

**Why interesting.** Memory mechanics *are* the gameplay:
peek-and-remember (own card), peek-and-remember (opponent's card),
forced-swap, look-and-swap. Each is a different memory-affecting
event. Direct test of
[memory-event-syntax](../open-questions/memory-event-syntax.md): the
DSL needs to express not just "card moved" but "observer X gained
identity knowledge of card C in zone Z."

**Notes.** Cambio is a near-identical variant. The Cabo call is a
typed-phase outcome with verification at the round's end.

### coup

3–6 players, 15-card custom deck (5 character types × 3 copies),
bluff and challenge: players claim character abilities; others may
challenge; lying = lose influence, wrong challenge = challenger
loses influence.

**Why interesting.** Challenge-resolution is the canonical
*knowledge event with branching outcome.*
- [memory-event-syntax](../open-questions/memory-event-syntax.md):
  reveals are observed by all, then the revealed card returns to a
  reshuffled deck — a `reveal` immediately followed by a `hide` plus
  a `shuffle` to obliterate prior identity knowledge.
- [knowledge-events](../open-questions/knowledge-events.md): the
  outcome of a challenge changes what is common knowledge and what
  remains private.
- [simultaneous-body-grammar](../open-questions/simultaneous-body-grammar.md):
  the "any player can challenge" step is a simultaneous decision
  with conditional commit.

**Notes.** Modern (Tchanturia, 2012). Not on Pagat. Coup's compact
ruleset makes it a high-leverage test case for the DSL's
information-set machinery.

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
[zone-access-syntax](../open-questions/zone-access-syntax.md) and
the existing visibility model handle a zone owned by no one but
used in every player's hand evaluation. Also second data point for
[typed-amount-syntax](../open-questions/typed-amount-syntax.md) and
[transfer-failure](../open-questions/transfer-failure.md).

**Notes.** Texas Hold'em is the canonical variant. No-limit vs
fixed-limit is a parameterization of `BettingRound`, not a
structural change. Stud's `BettingRound` mechanic should port over.

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
and a second resource-style transfer game for
[typed-amount-syntax](../open-questions/typed-amount-syntax.md).

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

## Edge-case experiments

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
assumptions, but provides a forcing function for thinking about
[simultaneous-body-grammar](../open-questions/simultaneous-body-grammar.md):
slaps are simultaneous moves with priority resolution.

**Notes.** Provocation, not a realistic candidate. Real-time
mechanics are out of scope for the current DSL — the entry exists
to flag the gap.

### bohnanza

2–7 players, custom 154-card deck (8 bean varieties × varying
counts), must plant cards in hand-order; *trading* between players
is a core phase.

**Why interesting.** The Trading Phase is the cleanest
[simultaneous-body-grammar](../open-questions/simultaneous-body-grammar.md)
candidate from a real published game: any pair of players can
propose trades, accept/reject is conditional on offers, and
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

**Why interesting.** The canonical forcing function for
[simultaneous-body-grammar](../open-questions/simultaneous-body-grammar.md).
Orders interact: a hypothetical card-game whose play phase had
Diplomacy-like simultaneous order resolution would absolutely
require non-trivial body grammar inside the `simultaneously:`
block.

**Notes.** Wildly out of scope (not a card game, has a map).
Included as a thought experiment — when reasoning about how rich
simultaneous bodies need to be, ask "could this express
Diplomacy?" as a worst-case bound.
