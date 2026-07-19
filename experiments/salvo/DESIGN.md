# Salvo — design notes

An original two-player game for a standard deck plus two jokers, designed
in the DSL. The prompt was "Marvel Snap with a regular deck": three
contested locations, sealed simultaneous commits, win two of three. This
directory is an experiment, deliberately outside `docs/games/` — the game
is not (yet) corpus, so the registry/proof pins don't apply. If it earns a
place, it goes through `docs/games/_candidates.md` like any other
candidate.

Relationship to the `marvel-snap` capstone entry in
`docs/games/_candidates.md`: Salvo is the standard-deck cousin, not the
capstone. It witnesses two of the capstone's named ingredients —
simultaneous multi-card commits, and location cards that bend the rules
where they sit — without the two gates the capstone waits on (the
effect-script on-ramp and the full simultaneity form). A location here
cannot carry a bespoke script, because a location is just a card; its suit
and rank must parameterize a small closed set of rules. That constraint is
the design. No Marvel content of any kind is used; the mechanics are an
original composition.

## Design goal

- **New**: not a description of an existing game, and not Snap — a
  standard-deck original in Snap's shape.
- **Standard materials**: 52 cards plus two jokers, nothing printed,
  playable at a kitchen table from one page of rules.
- **Snap's soul preserved**: both players commit face-down at the same
  time, every turn, into a fight over three places; the reveal is the
  drama beat.
- **Familiar vocabulary**: scoring leans on combos every card player
  already owns — pairs, runs, flushes — rather than invented iconography.
- **Measurably interesting**: sealed commits should *mix* at equilibrium
  (bluffing frequencies with interior probabilities), and the lab battery
  should demonstrate that, not just assert it.
- **Small DSL footprint**: at most one candidate-new construct (the
  set-valued simultaneous commit, named below); everything else rides
  surface the corpus already exercises.

## The idea

Three cards dealt face-up are the locations. Each broadcasts two things:
a **target rank** and an **affinity suit**. A card committed to a location
is worth more the closer its rank sits to the target, plus a bonus if it
matches the suit. So the three locations *reprice the whole deck every
deal* — a king is gold at a queen-target and nearly dead at a 3-target;
every card is good somewhere. That repricing is what lets the game skip
any energy or cost system: there is no globally best card to dump.

Over six turns the players build armies at the locations, two sealed
cards at a time at most, drawing as they go. Armies score their proximity
and affinity — and their internal structure: a pair, a run, a flush
committed to one location is worth extra, so some commits are made for
shape rather than raw closeness, and some cards are held back for a
combo that never quite arrives. The turn-by-turn questions are Snap's:
where, how much, and what is the opponent committing *right now*.

## Rules (full game)

All point values below are starting values, expected to move at the
simulation step; the mechanisms are the design.

**Setup.** Shuffle 54 cards (standard 52 plus two jokers). Deal three
cards face-up in a row: the **locations**. (A joker dealt as a location
is set aside, replaced from the deck, then shuffled back in; jokers only
ever live in hands.) Deal each
player a hand of five. The rest is the face-down **deck**. Ranks run
ace low: A=1, 2..10, J=11, Q=12, K=13, linear, no wraparound.

**The locations.** Each location card sets, for cards committed there:

- **Target**: its rank. A committed card's base value is
  13 minus the distance between its rank and the target (a bullseye
  scores 13, the farthest possible miss scores 1).
- **Affinity**: its suit. Each committed card matching it scores +3.

**Turn loop** (six turns). Each turn:

1. **Draw.** Both players draw one card from the deck.
2. **Commit.** Both players *simultaneously and secretly* choose zero,
   one, or two cards from hand and assign each chosen card to a
   location (two cards may go to the same location or different ones).
   Committing nothing is legal.
3. **Flip.** All committed cards are revealed at once and placed
   face-up in their owner's row at their location. They stay there for
   the rest of the game. Nothing triggers on reveal, so reveal order
   never matters.

Cards left in hand after turn six score nothing.

**Scoring** (after turn six). At each location, each player totals their
army there:

- **Proximity**: 13 minus distance-to-target, per card.
- **Affinity**: +3 per card of the location's suit.
- **Combos**, within one player's army at one location. Each combo type
  scores once per location, best instance only; one card may serve
  several types (7 of spades + 7 of hearts + 8 of spades + 9 of spades
  scores a pair, a run of three, and a flush of three):
  - pair +4; three of a kind +12; four of a kind +20 (within the
    of-a-kind family only the largest scores)
  - run of three +6; run of four +10; run of five or longer +15
  - flush of three +5; flush of four +9; flush of five or longer +14
- **Jokers**: a joker scores as a perfect hit (13) at any location, has
  no suit, and participates in no combo.

The higher army total takes the location; an exact tie leaves it
unclaimed.

**Result.** Most locations taken wins. If that ties (one each plus one
unclaimed, or all unclaimed), higher grand total across all three
locations wins; if that also ties, the game is a draw.

### Why the scoring is shaped this way

- **Proximity repricing** replaces an energy system. Without it, high
  cards are simply best and the commit decision collapses. With it, the
  deal hands each game a different economy: a 7-target prices the whole
  deck between 7 and 13 (a safe volume war), while a 2- or K-target
  makes half the deck near-worthless there (a precision fight). The
  extremeness of a deal is its personality; that is why ranks do not
  wrap.
- **Affinity is a rescue mechanic** — a matching suit lifts a mediocre
  distance into a playable commit — and it aims the long game: a flush
  in the location's own suit stacks both bonuses.
- **Combos reward planning across turns** and justify off-target
  commits, which keeps hands from being priced by proximity alone.
- **The all-positive curve is a recorded risk.** Every commit scores at
  least +1, and a player sees eleven cards (five dealt plus six drawn)
  against twelve commit slots — so on paper, committing the maximum
  every turn is close to dominant, and the 0/1/2 choice may be fake.
  The simulation gate arbitrates (see the evaluation plan). Two
  fallbacks are ready if it confirms the dominance: (a) **zero-centered
  values** — base value 6 minus distance, so far-off commits score
  negative, passing and hand-digging become real, and mid-vs-edge
  targets diverge harder (a one-line change); (b) **shared capacity
  with priority reveal** — locations hold a limited number of cards
  total, the current leader's cards flip and claim slots first — which
  disciplines volume through scarcity instead. Fallback (a) is the
  default; (b) is the more Snap-authentic but heavier lever.

## Information structure

Hidden information: each hand, the deck order, and the opponent's
*concurrent* commit. Because every turn ends in a full flip, there is no
lingering "I can see where but not what" state — the sealed commit is
resolved the moment it is observable. So v1's imperfect information is
GOPS-class (outguessing a simultaneous choice, plus hidden hands and
deck), with a much richer action space per decision. The
existence-only-placement construct the capstone entry names arises only
in parked variants (blind-to-end reveal, two-wave commits), not in v1 —
this is stated so the capstone link is not overclaimed.

## Mini variant (salvo-mini, exactly solvable)

A shrunk twin for exact-tier ground truth on the one question that
matters most: **do sealed commits mix at equilibrium?** Shape: two suits
of ranks A–6 (twelve cards), no jokers; two locations; deal three or
four each; three or four turns; commit zero or one card per turn; no
draw; combos reduced to pairs only; result by grand total (majority is
degenerate at two locations). Exact numbers are build-time knobs sized
to the census budget, per the lab's tiering.

## Candidates considered and rejected

- **Sharpshooter scoring** (only the closest card counts): elegant duel,
  but it guts multi-card armies and the combo layer with them.
- **Blackjack sum-to-target** (army's pip sum seeks the target): bust
  rules and ace-value questions, and it punishes exactly the multi-card
  flow the turn structure wants.
- **Open alternating play**: simplest, but loses the simultaneous-commit
  soul; it would be a different (and less novel) game.
- **Steady drip** (commit exactly one, no pass): the machinery-lite
  fallback if the set-valued commit proves expensive — kept as a
  variant file, not v1, because tempo choice is where the bluffing
  texture lives.
- **Zero-centered value curve**: not rejected — the recorded first
  fallback for the commit-max risk, above.
- **Shared capacity + priority reveal**: not rejected — the recorded
  second fallback; adds a genuine race to commit early.
- **Target-warper jokers** (a joker replaces a location's card
  mid-game): flavorful chaos, but swingy and it creates the game's only
  resolution-timing rule; parked as a variant.
- **Snap-style stake doubling**: backgammon's cube plus
  retreat-as-concession — the capstone's bluff-snapping angle. Needs a
  match/points superstructure around single hands; parked as a variant
  layer, not v1.
- **Blind-to-end reveal** (armies stay face-down until scoring):
  maximum poker and a true existence-only witness, but you can never
  react to being behind; parked.
- **Two-wave commits** (place face-down, see placement counts, then
  optionally add one more before the flip): restores existence-only
  information inside the turn at the cost of a sub-round; parked.

## DSL surface notes

Existing surface this rides: sealed simultaneous choice
(`each player simultaneously:` — GOPS's bids, Hearts's passing),
turned-card-as-rule-parameter (the trump turn-up family), per-location
accumulation piles, shared-deck draw, and combo detection over a card
set (cribbage's show scoring is the stdlib precedent).

The one candidate-new construct: a **set-valued simultaneous commit** —
each player secretly selects up to two cards *with a location assignment
each*. GOPS seals one card with a fixed destination; Hearts seals three
with a fixed destination; Salvo seals zero-to-two with *chosen*
destinations. If this exceeds the current simultaneous form, that is a
witnessed corpus-first need (and exactly the surface the capstone
requires later); it goes through the surface-totality gate like any
grammar change, with the steady-drip variant standing as the
within-surface fallback. No per-game Python is anticipated; the combo
bonus table may want a small stdlib scoring primitive if cribbage's
machinery doesn't already generalize.

## Evaluation plan

The standard loop: check, play, simulate; then the battery
(`experiments/game-to-artifact-plan.md`), probe tier for the full game,
exact tier for salvo-mini.

Decision questions, in priority order:

1. **Commit-max dominance** (decisive for the value curve): across
   MCCFR/arena play, how often does a nontrivial policy commit fewer
   than two cards? If holding and passing never appear outside forced
   positions, adopt fallback (a) and re-run.
2. **Do sealed commits mix?** Exact tier on salvo-mini: equilibrium
   commit choices should show interior probabilities, not pure
   strategies.
3. **Location liveness**: are all three locations contested, or does
   play collapse onto two? (Unclaimed-tie frequency feeds this.)
4. **Combo incidence and table tuning**: how often does each combo type
   score? Sweep the bonus table so combos matter without dwarfing
   proximity.
5. **Balance and length**: seat symmetry (should be exact — no first
   mover), score margins, game length, decision liveness by turn.
