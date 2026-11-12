## Typed object model

The language has a typed object model with built-in types and
convenience sugar that rewrites to underlying forms.

**Built-in types:**

- `Card` — `{ suit, rank, attributes, optional facing }`. Suit and
  rank are declared at the game level (`cards { suits: { ... } }`,
  see "Deck declaration" below). Attributes are a per-game extension
  point. Facing is an optional built-in dimension that composes with
  zone visibility (see "Knowledge, visibility, and the projection
  model" below). Suit and rank are deck-defined *values*, not language
  keywords — a rank is any name or number, checked against the deck's
  `Rank` enum, so the grammar reserves no rank letters. A card is
  written either as `<rank> of <suit>` (`2 of clubs`, `Q of spades`)
  or, for a named card, as the bare constant the deck declares
  (`Dragon`, `Duke`), which resolves like a `Suit` value. The two axes
  are flexible: a suitless game degenerates one of them — Coup carries
  the character as the `rank` under a singleton dummy suit `court`, and
  makes no suit comparison.
- `Resource<Type>` — fungible quantity of the named type. Declared
  by the game's `resources { }` block.
- `Suit`, `Rank` — enumerable value types defined by the game's
  `cards` header.
- `Player` — bare identity; relational queries delegate to Seating.
- `Team` — declared in the game header; indexable as a key into
  per-team state.
- `Seating` — derived from `players` + `teams`; exposes
  `partner_of(p)`, `left_of(p)`, `right_of(p)`, `LHO_of(p)`,
  `RHO_of(p)`, `opposite_of(p)`. Relational queries are function
  calls (and the `offset_by` operator), never dot chains — see the
  access discipline below.
- `Zone<Contents>` — a container parameterized by what it holds.
  Carries a per-observer visibility declaration (see "Knowledge,
  visibility, and the projection model"), ownership, and structural
  type (set, ordered, stack).
- Zone contents are read through the English query surface (see "The
  expression register"): `cards in … where`, `number of cards in …`,
  `any/all card(s) in … where`, `sum of … over cards in …`,
  `highest/lowest … over cards in … or <default>`, and the emptiness
  checks `is empty` / `is not empty`. Resource queries are unbuilt
  ([roadmap.md](../roadmap.md), "Grammar surface deferred by the checker").
- Phase outcomes — tagged-union values; pattern-matched, not
  dot-accessed.

**No user-declared record types.** A game models its structured values
with flat state variables and functions — Bridge's contract is
`contract_level : Integer`, `trump_suit : Suit?`, `doubled_mult :
Integer`; a poker pot is a chip zone plus an eligibility set. A record
declaration is surface no game has needed, and a surface with no
consumer is not kept as a sanctioned future path: the game that needs a
true record is the witness that adds one, built against the language as
it stands then.

**Angle brackets: the head fixes the argument.** `Name<Arg>` means one of two
things, and which is decided by the head, not by the reader:

- A **zone-type head** (`Hand`, `TeamPile`, `Cascade` — the kernel's zone
  types) takes an **index domain**: a lower-case domain id, equal to the
  declaration's own index. `hand[player] : Hand<player>` reads "a hand per
  player", and the checker refuses any disagreement between the two brackets.
  The argument says who the family is keyed by, never what the zone holds —
  the zone type's own name already fixes that.
- A **value-constructor head** (`Collection`, the only one) takes an **element
  type**: a Title Case name, and the language admits exactly one of them,
  `Card`. `cards : Collection<Card>` reads "a collection of cards", and
  `Collection<Player>` — a type the checker itself mints for `all players` —
  is refused by name. The allow-list is held equal to the element types
  registered Python actually takes, so a second element arrives as an event
  with a witness rather than as a widening: the day an implementation takes a
  collection of something else, the list is red until it admits that element.
  The spelling is legal in a `primitives { }` entry's two type slots and
  nowhere else, because a set of cards anywhere else in a game is a zone;
  every other type position teaches that placement rather than reporting a
  shape error (see [Primitives Block](../glossary/primitives-block.md) and
  [Collection Type](../glossary/collection-type.md)).

Case does the disambiguating on the page — an index domain is a lower-case id,
an element type is a Title Case name — and both cross-confusions are refused
by name. `?` suffixes a **value** type only: never a zone, never a collection
(an absence inside a set has no rulebook reading, and `is empty` is a
collection's absence). There are no type variables anywhere in the language: no
declaration takes one, no Builtin is parametrically polymorphic (several take
the top type `Any`, which is a widened parameter, not a variable), and no
rulebook says "for any type T".

**Optional types and the `none` literal.** A type written `T?` is optional: it
holds a `T` or the absence value `none`. `none` is the language's single
absence literal, used by every optional (`leader : Player? = none`, `contract :
Contract? = none`, `state.led_suit is none`) — it is not a member of any enum.
Where a game needs a value that reads like "nothing happens" but is a real
domain choice — Hearts' no-pass hand — it gets its *own* enum value
(`SeatDirection = {left, right, across, hold}`), never `none`. This keeps `none`
unambiguously "no value": a `Player` that is `none` is unset, not the string
`"none"`. An optional is accepted where its base type is wanted, since the
language has no flow narrowing, so a `Player?` known to be set reads as a
`Player`; a `none` that reaches a Builtin or Primitive argument whose type
holds no `none` (`has_step(c, d, p)` with `d : dir?` unset) is refused at
play, naming the call and the type it wanted.

`true` and `false` are the two boolean literals, the values a `Boolean` field
takes (`eliminated[player] : Boolean = false`, `eliminated[p] := true`). Like
`none`, they are language literals rather than enum members, so a game never
declares them.

**Deck declaration.** The `cards:` line names the deck a game uses.
The deck is a constant from the closed kernel table (`DECKS` in
`cardlang/runtime/values.py`): a game selects one by name and does not
spell out its cards.

```cardlang-fragment cards_line
cards: standard52
```

Each registered deck defines its own card set — the standard 52-card
deck, Pinochle's doubled 48, Skat's 32, and the decks whose suits do
not share a single rank list: French Tarot's 78 (four 14-card suits, a
21-card trump suit, and the Excuse) and Tichu's 56 (the standard 52
plus the four special cards Mahjong, Dog, Phoenix, Dragon). Those
compositions live in the registry, not in per-game syntax;
[library.md](../library.md) "Built-in component sets" catalogues them
(decks are its card-flavored entries), and adding a deck is a kernel-table
registry addition. Tichu's non-(suit, rank) specials
are a separate question from the registry itself; see
[open-questions/special-cards-declaration.md](../open-questions/special-cards-declaration.md).

Per-card mutable attributes (tapping, counters, status effects) are
not part of the surface — the oriented- and CCG-style card state they
would serve is deferred ([roadmap.md](../roadmap.md), "Out of scope").

**Convenience sugar (rewrites that compile away):**

- `card.tapped` → `card.attributes[tapped]`

Sugar is documented; the underlying form is what the compiler
manipulates.

**Access discipline.** The bracket form is the only indexed
access: `hand[player]`, `captured[team_of(winner)]`,
`hand[player offset_by pass_direction]`, `score[team]`. The dot
form is **object-member access and nothing else** — fields of a
`Card` (`card.suit`, `card.rank`, attribute sugar), fields of a
`Move` (`action.card`). A dot whose receiver is a
player, team, integer, or boolean is a static error pointing at
the bracket form — including receivers rooted at loop, quantifier,
player-query, and comprehension binders, which the checker types
by their roles (a `for each player p` / `any player p` binder is a
`Player`, a `for each team t` binder a `Team`, a comprehension
binder its source's element type). The one receiver the checker
still cannot type is a lambda parameter (a lambda's element type
belongs to its receiver, which the checker does not model); there
the runtime fails loud rather than guessing. Relational
chains stay out of subject position: the corpus derives them with
`offset_by`, functions, and player-indexed public state. The
predicted forcing case — Doppelkopf's Fox/Charlie scoring, which
the rulebook phrases as "the partner of the ♦A's player, relative
to the trick winner's side" — flattened to equalities over
player-indexed public state
([games/doppelkopf.cardlang](../games/doppelkopf.cardlang)) rather
than needing `dealer.left.partner.hand`-style chains, so no
complex-receiver dot form exists. Koenigrufen's runtime-chosen
called king is the named reopener if a future game's relational
subject resists this flattening.
