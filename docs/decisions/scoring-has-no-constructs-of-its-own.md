## Scoring has no constructs of its own

Scoring is arithmetic on state, and the language already does arithmetic on
state. A game scores with exactly three things, none of them a scoring
construct:

- **Declared data** — a table keyed by something the deck or the game already
  names. The rank-keyed `card_points { }` clause is the one the language has
  (below).
- **General constructs** — the comprehensions, queries, conditionals and
  arithmetic every other part of a game uses. A scoring sentence is a legality
  sentence with a different variable on the left: Scopa's "can this card
  capture?" and cribbage's "how many fifteens?" are the same subset query.
- **A ranking direction** — `winner: highest <var>` / `lowest <var>`, or
  `loser:` for elimination ("Game result: `winner:` and `loser:`"). The
  variable is whatever play accumulated; the word says which end wins.

**The test, at the moment of temptation: a construct whose definition has to
mention a point value is the wrong shape.** Recognition over card sets is
general and earns grammar on witnesses; pricing never does. A construct that
is general by definition but finds only scoring consumers is filed as general.
The dead-surface report (`python -m tools.dead_surface`) shows the surface no
game, library or stdlib rule uses; whether a live construct's consumers are
all scoring sentences is a question for the checked game, not the parse tree
(issue #664). A member of a closed register may ship ahead of its first game
when its sibling has one (a language with `highest` and not `lowest` has a
hole a designer meets).

What the language cannot yet say about a hand stays a declared Primitive in
the game file (`primitives { }`; "Family libraries"), where the declaration is
the inventory of what is not expressible. That is the escape hatch by design:
a typed function at function granularity, which is the granularity that
works. A shared engine module behind several games' declared Primitives —
poker's hand ranking and side pots, one module, three games — is that hatch's
healthiest shape and a designed end state rather than debt, until the general
constructs it needs (a composite ordered value, a selection returning the
player) earn witnesses of their own.

The rule generalizes two rulings already below it: the `card_points { }`
clause deliberately carries no more than the rank-keyed table, and structured
score is a per-game declaration, not a language-level concept. It is derived,
not imported: measured 2026-09-07, 21 of the corpus's 32 games score with no
Python and nothing beyond the three things above, and of the four
game-description languages with corpora that were read, none has a scoring
language. The rejected alternative — a subsystem of batched `ScoreDelta`s and
event-triggered components — and the measurement behind this ruling are in
[design-notes/scoring-components.md](../design-notes/scoring-components.md).

**Structured-score shapes are per-game, not generalized.** Bridge
declares two score variables per team — `total_score` and
`below_current` — because the game-win threshold cares specifically
about below-the-line accumulation. Stud has a different shape: a list of
pots with per-pot eligibility, length data-dependent on all-in
history. The games whose score is a single integer per player
— Cribbage, Skat, Oh Hell, Pinochle (final team score) — don't have
a "structure" at all; the structure lives in the *computation*
(Skat's `base × multiplier`, Cribbage's pegging stream + show), not
the *output*.

Bridge's channels and Stud's pots-with-eligibility don't share a
structural form. The minimal generalization that fits both ("list
of scoring channels with per-channel eligibility") would constrain
the corpus to express simpler games through a heavier abstraction,
and the third structured-score game (Skat) declined to produce a
third shape — it kept a scalar score. The honest read: structured
score is a per-game declaration, not a language-level concept. Each
game declares whatever score variables its mechanics need (one
integer, two channels, a list of pots settled in a Primitive); there
is no shared score-structure type.

**Per-card points: a rank-keyed table is the `card_points { }`
clause; everything richer stays an inline expression or a
per-game helper.** A game whose card points are a function of
rank declares them as a block clause beside `cards:`, rows in
`ranking:`'s key position (a NAME or a bare INT), values static
signed integer literals, with one optional trailing `else:` row
for the everything-else value:

```text
card_points {
  A: 1
  2: 2  3: 3  4: 4  5: 5  6: 6  7: 7  8: 8  9: 9  10: 10
  J: 10  Q: 10  K: 10
}
```

Rows are whitespace-separated like every block clause; the empty
block is a syntax error (at least one rank row); a duplicate rank
key and a key that is not a rank of the declared deck are resolve
errors naming the deck. Unlisted ranks read the `else:` value, or
0 with no else row (Tichu's sparse table prices five ranks; the
rest read 0). Negative rows are ordinary (`Phoenix: -25`). The table
is a spelling of the `card_points(card : Card) : Integer` Kernel
Definition Contract ("Trick Order"): the parse builder lowers it to
the function a designer would write by hand, `function
card_points(card : Card) = if card.rank is A then 1 elif ... else 0`,
and a game writes that function directly when the table cannot carry
the fact. Either spelling is the one answer; a game writing both is
refused. `card_points(card)` reads the answer; an answer no
`card_points(card)` call reads is refused ("Surface totality", "A
clause nothing reads is refused"), and calling it in a game that
answers none is a resolve error — the
points have ONE source, the game's own answer: the deck registry
carries composition only, never points (`values.Deck`), so one
deck serves games that price it differently, and a piece game is
refused the clause outright (the noun/content agreement guard,
"Component sets: cards and pieces").

The clause deliberately carries no more than the rank-keyed
table. Card points that vary by more than rank stay inline or in
a per-game `function`, composed OVER the clause where a table
carries part of the fact: Hearts scores `if card.suit is hearts
then 1 elif card is Q of spades then 13 else 0` inline; French
Tarot declares `card_points { K: 9  Q: 7  C: 5  J: 3  else: 1 }`
and wraps its bouts inline (`if is_bout(card) then 9 else
card_points(card)` — a rank-keyed table cannot carry the petit,
whose rank "1" is worth 9 in the atouts and 1 in the plain
suits); Belote's trump-dependent pricing is a function with no
table at all. A `card_points` answer is held to the Trick Order's
hermeticity law, since the end-of-game card census reads it where no
phase frame stands, and it may call the Trick Order's answers. A declarative rank-keyed `counters: { ... }`
block on the CARD definition was considered and stays rejected —
it re-attaches a scoring fact to the card itself, and only cleanly
handles the pure-rank shape; the game-level clause carries that
shape, and inline conditionals scale to the rest. Lift to a
per-game helper function when the composition is large enough to
repay the indirection (Canasta's twelve-pile meld sum,
`canasta_meld_points`, is an example).
