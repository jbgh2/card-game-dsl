## Combination Catalogues

A climbing game declares its plays in its own file: a **Combination
Catalogue** names the card multisets a play may be, and a **follows
function** says which of them a seat may play over the standing play. The
climbing round names both, and runs on them as its **Declared Engine**:

```text
combinations big_two {
  single:         1 card
  pair:           2 of a kind
  triple:         3 of a kind
  straight:       5 in sequence, not all one suit
  flush:          5 cards, all one suit, not in sequence
  full_house:     3 of a kind with 2 of a kind
  quads:          4 of a kind with 1 card
  straight_flush: 5 in sequence, all one suit
}

function big_two_follows(play : Combination, standing : Combination?) = …

round climb play_combination from leader over players
      source hand into trick_pile
      combinations big_two follows big_two_follows
      until (any player where hand[player] is empty)
```

**A row is a label and a Combination Shape.** The label names the row's
plays and nothing else of the game — a rank, a suit, a state variable, a
zone, a function, a move type, a phase, the catalogue, or a registered
query by that spelling is refused; a binder may still take it, as a binder
shadows a suit. A shape is one part, or two parts joined by `with`, then
its qualifiers. The parts are a count and a noun:

- `1 card`, `N cards` — any N cards;
- `N of a kind` — N cards of one rank;
- `N in sequence` — N cards whose ranks are N consecutive places of the
  game's Rank Sequence.

`A with B` is a part A and a part B over disjoint ranks (`3 of a kind with
2 of a kind`, a full house; `4 of a kind with 1 card`, quads and a kicker).
The qualifiers narrow a single-part row: `, all one suit`, `, not all one
suit`, `, not in sequence`. The vocabulary is `catalogue.SHAPE_PARTS`,
`SHAPE_QUALIFIERS` and `SHAPE_FORMS`, each pinned to the grammar's aliases.
A count agrees with its noun (`1 card`, never `1 cards`; `1 of a kind` is
`1 card`), names a play the deck holds, and a sequence is at least two
places and at most the Rank Sequence's length; a qualifier is said once,
and removes some of its row's plays and leaves some. Every phrase a
growth game needs and this vocabulary lacks — a run of any length, a run
of groups, a named card, a wild card, a play that interrupts or ends the
trick — is refused by its Reject-with-Replacement Twin citing issue #989;
a shape of more than two parts, issue #994.

**The Rank Sequence** is the `sequence:` game clause: the deck's ranks in
the order a run reads them, lowest place first. A rank may stand at both
ends — Big Two's `A 2 3 … K A`, where the ace is low in A-2-3-4-5 and high
in 10-J-Q-K-A and nothing runs past it — and nowhere else twice. It is
declared exactly where a row reads it (`in sequence`, `not in sequence`).

**A catalogue's plays are judged whole, at check time.** The catalogue pass
derives every card multiset of the deck each row names
(`runtime/declared.py`, the one home of what a row names) and refuses:

- two rows naming one multiset, with the multiset as witness — an overlap
  is settled in the rows (`, not all one suit`, `, not in sequence`), never
  by row order, which carries no meaning;
- a row that names no play of the deck;
- a catalogue no climbing round names;
- a catalogue numbering more plays than `catalogue.ENUMERATED_UNIVERSE_BOUND`
  — one that large needs its plays numbered arithmetically from its rows,
  which issue #989 holds;
- a catalogue over a deck holding cards beyond the standard deck's
  (jokers, Tichu's special cards), issue #989.

Three refusals are designed constraints, not deferrals. A catalogue is
written in the game's file, never a library's: it declares one game's plays.
A game runs one climb engine, so a second catalogue a second round names is
refused ("a game runs one climb engine"): the action space numbers one
universe of plays. And a `Combination` is a function parameter's type only
(below).

**The follows function** has the signature
`(play : Combination, standing : Combination?) -> Boolean`. A seat is
offered every multiset of its hand that a row names and the function
admits against the play standing in the trick, then the pass; at a lead
`standing` is `none`, and the function admits the plays a seat may lead
(Big Two's opening lead holds the 3♦). A lead offers no pass, so a lead at
which the function admits no play of the hand is a loud error naming the
fix. Reading `standing`'s cards before testing it for `none` is a loud
error at play naming `standing is none or …`; issue #990 holds the
checker's refusal of an optional read untested.

**A `Combination` is read as its cards and its shape.** `cards in play`,
`number of cards in play`, `any card in play where …`, an aggregation
over `cards in play`, and card membership (`(3 of diamonds) in play`) read
its cards; `play.shape is <label>` reads its row. Its one field is
`catalogue.COMBINATION_FIELDS`' readable one; `play.wild` is refused citing
issue #989. Everything else is refused with its fix: another field, `is
empty` (a play holds a card; the absent play is `standing is none`), two
plays compared whole (they are compared by what is read of them), a play
as a number, a play passed where a card or a zone is taken, anything but a
play passed to a `Combination` parameter, a subset source over a play, and
`Combination` as the type of a state variable, a move type's or a
procedure's parameter, or an outcome payload — a play exists while a round
asks its follows function about it.

**What the function may read.** Beyond its two plays, it reads the game's
state and zones as any function does, judged by the Hidden Read Owner Guard
at the asked seat: a count of another seat's hand is public, its cards are
not, and `player_holding` names a hidden holder. The play zone shows every
seat its cards (a climbing round into a zone whose type hides them is
refused), so the standing play and the trick's earlier plays are public.
The offered list is therefore a function of the seat's own hand and what
every seat sees: its information set derives from the movements the
climb form already emits, and a Declared Engine adds no observation site.

**The function is an ordinary DSL function, cached.** Resolve stamps on the
round's engine every state variable and zone the function reads, through
the functions it calls (`DeclaredEngine.state_reads` / `zone_reads`), and
the engine caches its answers for the game on the two plays' cards and the
values of those reads. A function that reads a pronoun, a round's published
state or a declared Primitive's `reads` runs uncached
(`DeclaredEngine.cacheable`).

**A play's identity is its card multiset.** Copies of one card in a
duplicate deck stay distinct plays' cards, never one card twice
(`primitives.play_identity`). The action space numbers the catalogue's
plays by card count and then by their sorted card ids, the order the climb
form offers a seat's candidates in, and each play moves its cards in
card-id order (`primitives.action_order`, `in_card_order`, which the
registered engines share).

A game whose plays no catalogue declares yet — Tichu's runs of any length,
runs of pairs, bombs, and the four special cards — names a **Registered
Engine** instead: a game-local Primitive lead query and its follows query
(`PRIMITIVE_CLIMB_ENGINES`), keyed by the lead query, with an arithmetic
combo codec for its play universe ("The climbing form of `round`"). Resolve
stamps each round's engine as one of the two kinds (`ClimbRound.engine`)
and refuses a round pairing one engine's slot with another's.
