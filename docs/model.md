# Language model

The deep structure: primitives the language is built on, and the relationship
between phases, rules, move types, and state. Anything domain-specific (trick,
trump, suit) lives in [library.md](library.md), not here.

## Primitives

All domain-neutral. About twenty things; none of them mention "trick" or
"trump."

| Primitive | Description |
|---|---|
| **Piece / Card** | The individuated content of zones. A **Piece** is the base kind: identity is two enumerable axes (with per-set declared names) times multiplicities, plus per-game attributes and optional facing. A **Card** is the deck specialization of a Piece — its two axes are named `suit` and `rank`, and it carries the card-only conventions (`ranking:`, follow/trump, the `Card` move parameter). A piece set names its own two axes (`xo_marks`: `side`, `kind`) and carries none of them. Cards are the canonical individuated content of zones — every corpus card game uses them; a game selects pieces with `pieces:` in place of `cards:`. See [decisions.md](decisions.md) "Component sets: cards and pieces", the attributes mechanism (typed object model), and the projection model (knowledge/visibility) for facing. |
| **Resource** | A typed fungible quantity (chips, wood, victory points, tokens). Resources have a type (declared in the game's `resources { }` block) but no per-unit identity. The strongest knowledge available for a resource zone is the count-by-type breakdown. Resources are the canonical fungible content of zones. See [decisions.md](decisions.md) "Knowledge, visibility, and the projection model" for how visibility differs from cards. |
| **Player / Agent** | A participant with identity. Relational queries (partner, left, right, LHO, RHO, opposite) delegate to Seating. |
| **Team** (alias: **Team**) | A named grouping of players for purposes of shared zones, shared scoring, indexable as a key into per-team state. |
| **Seating** | Derived from `players` + `teams`; exposes relational queries between players. |
| **Zone** | A named container parameterized by what it holds: `Zone<Card>`, `Zone<Resource>`, `Zone<Resource<chip>>`. Carries a per-observer visibility declaration (which projection of zone contents each observer is informed by — see [decisions.md](decisions.md) "Knowledge, visibility, and the projection model"), ownership, and structural type (set, ordered, stack). Library types in [library.md](library.md) give common configurations named aliases (`Hand<Player>`, `Deck`, `Discard`, `TrickPile`, `ChipStack<Player>`, `Pot`). |
| **Card queries** | The English query surface over zones: `cards in … where`, `number of cards in …`, `any/all card(s) in … where`, `sum of … over cards in …`, `highest/lowest … over cards in … or <default>` (decisions.md "The expression register"). |
| **TurnOrder** | A cyclic ordering of players with a current pointer and optionally a direction. Operations: advance, reverse, set. |
| **State variable** | A typed, named, scoped piece of game state. Scope is lexical: a variable lives as long as the phase instance that lexically encloses its declaration. See [decisions.md](decisions.md) "State scoping (lexical)" and "Mutation semantics"; [appendix.md](appendix.md) catalogues every state variable across the five-game corpus as a reference for both. |
| **User-defined type** | A struct-like declaration with named, typed fields and optional `derived` fields. May be parameterized (see [library.md](library.md), "Types"). See [decisions.md](decisions.md) "Typed object model". |
| **Move type** | A named, parameterized player action: declared source/destination/participating zones and associated events. Reusable across games. A move type's effect is written as **Transfers** (below). |
| **Move** | One played instance of a Move type, bound to its Parameters. A Move performs zero, one, or many **Transfers** — see "Moves and Transfers" below. |
| **Transfer** | The zone-relocation statement. Its verbs (`deal`/`draw`/`move`/`burn`/`muck`/`transfer`) are sugar over one primitive. Independent of Move: setup is Transfers with no Move. |
| **Phase** | A bounded interval of game time during which a specific set of rules is active. May be nested (sub-phases) and sequenced. Has entry condition, exit condition, active rule set, and legal move types. May resolve to a typed outcome (see [decisions.md](decisions.md) "Typed phase outcomes"). |
| **Rule** | A named, parameterizable constraint on a move type. Attached to phases via the phase's active rule set. |
| **Constraint composition** | Rules combine by intersection (AND) over the set of legal candidate moves. |
| **Observation event** | An event emitted automatically by a move or memory operation, projected per observer according to the visibility settings of the zones involved (see [decisions.md](decisions.md) "Knowledge, visibility, and the projection model"). Maintained as per-player histories; used to derive information sets. |
| **Memory operation** | A native-named operation that affects player knowledge (`peek`, `reveal`, `hide`, `shuffle`, `announce`, `expose_top`, `deal`, `transfer`, `muck`, `forget`). See [decisions.md](decisions.md). |
| **Resolution** | A deterministic computation over current state, used to drive non-choice moves (e.g., "who won the trick"). |
| **Scoring component** | A named, parameterizable function producing a ScoreDelta. Batched components compose by summation inside `apply_components:`; triggered components fire on specific events via `triggered_by:` clauses. Bridge introduced this; see [library.md](library.md) "Scoring components" and [decisions.md](decisions.md) "Scoring composition" / "Triggered scoring components". |

## The phase / state / move-type / rule relationship

This was the design crux. Resolution:

### Phases, modes, and states

Two different things want to be called "state", and the language gives each its
own word.

- A **phase** is a step in the game's sequential program. Phases run in
  declaration order and a phase ends when its work completes. `deal`,
  `first_trick`, `play`, `scoring`.
- A **mode** is a condition the game is in, existing to change which rules are
  active. It is not a step: you do not run a mode, you are in one.
  `hearts_not_broken`, `hearts_broken`.
- A **state variable** is ordinary data — a counter, a flag nothing gates on.

The criterion for "this configuration deserves a name" is still **does the
active rule set change?** If yes, it is a mode. If no, it is a state variable.
Flags that gate rules are modes in disguise; flags that are purely
informational are just variables.

Modes are **independent conditions, not an exclusive state machine.** A phase
may declare several, any number may hold at once, and their rule deltas stack.
That is what lets two unrelated conditions — "hearts have been broken", "the
queen has gone" — be written as two mode pairs instead of as the four modes of
their product.

Each mode is exactly one side of one condition: the **before** side, which
declares the `transition_to:` that ends it, or the **after** side, which a
sibling names as a target and whose body is usually empty. A mode that were
both would be a chain, and a mode that were neither could never be active at
all; the checker rejects both. A progression through three or more stages is
not a mode chain — use a state variable and gate the rules with
`applies_when:`.

### Moves and Transfers

Two independent things, and the corpus hid that for a long time because in a
trick game they coincide: one card play is one Move and one Transfer. They come
apart as soon as a board game arrives.

| what happens | Moves | Transfers |
|---|---|---|
| a card played to the trick | 1 | 1 |
| a pass | 1 | 0 |
| placing a mark on an empty cell | 1 | 1 |
| a capture (mover advances, captured piece leaves) | 1 | **2** |
| dealing at setup | 0 | many |

A **Move** is what a player chose; a **Transfer** is a relocation between zones.
Fusing them into one word makes a capture indescribable — which is the test the
naming had to pass. A future Pose domain (flip, orient) is neither: nothing
changes zones.

### The relationship between concepts

```text
       Phases organize game time and scope active rules
                     |
                     v
         Rules constrain Move types
                     |
                     v
            Moves transfer Cards
                     |
                     v
        Zones hold Cards (with visibility)
                     |
                     v
       Observations emitted from zone visibility
```

- **Phases** are primary structural units. A game is a sequence/tree of phases.
- **Rules** are reusable named constraints attached to phases.
- **Move types** are named card-transfer patterns. Rules constrain move types.
- **Move types are scoped to phases via the phase's active rules** (a move type
  is legal in a phase if rules constraining it are active there).
- **Events emit automatically from moves**, with visibility derived from zones.

### Sub-phases and modes

A phase may contain nested sub-phases — further steps, run in order, inheriting
the parent's rule set. It may also contain modes, which are not steps.

Example: Hearts' `play` phase declares the modes `hearts_not_broken` and
`hearts_broken`. The transition between them fires on the first heart played,
and the active rule set differs (`NoLeadingSuitUntilBroken(hearts)` is active
only in the first). The `play` phase's own body — the trick loop — runs
throughout, under whichever rules the current modes give it.

```text
phase play {
  active_rules: [MustFollowSuit]
  legal_moves:  [play_to_trick]

  mode hearts_not_broken {
    active_rules: [+ NoLeadingSuitUntilBroken(hearts)]
    transition_to: hearts_broken when play_to_trick where action.card.suit is hearts
  }
  mode hearts_broken { }

  repeat until (all players where hand[player] is empty) { … }
}
```

This replaces the ad-hoc `hearts_broken` boolean flag with structure. A mode's
body is configuration only — `active_rules:` and `transition_to:` — because
being in a mode *is* its behavior; the grammar admits nothing else there.

### What rules really are

A rule is **a named, reusable constraint on a move type, optionally with an
applicability condition**. Four clauses:

```text
rule <Name> {
  constrains: <move_type>
  applies_when: <predicate on state>     // default: always
  demands: <function returning a set of legal candidate moves>
  if_impossible: <fallback>              // default: any legal move under this move type
  exempts: <function returning a set of cards>   // optional; see below
}
```

The rule produces a *set of acceptable moves*. Composition is set
intersection: if multiple rules are active, the legal set is the intersection
of each rule's demand. The vacuous case (rule's demand can't be satisfied by
the actor) falls back to `if_impossible`, which defaults to permissive — this
prevents the intersection from collapsing to empty.

`exempts:` names a different axis, not a fourth ingredient of the
intersection: the cards it selects (when `applies_when` holds) sit *outside*
every rule's demand entirely — never narrowed, never counted toward
satisfying one — and are appended after every other legal card, in hand
order (French Tarot's Excuse: never bound by follow-suit/trump obligations,
always playable last; see [decisions.md](decisions.md) "Rule exemption (`exempts:`)").

Rules are referenced from phases by name:

```text
phase play {
  active_rules: [MustFollowSuit, NoLeadingSuitUntilBroken(hearts), ...]
}
```

### Move types

A move type names a kind of move a player can make. Some are kernel move types
names shared across games (`play_to_trick`, `submit_bid`); a game also
defines its own with a `move_type` block — an optional `when:` guard
and an `effect` that carries out the move:

```text
move_type play_card(c : Card) {
  effect { move one card from hand[actor] where card is c to trick_pile }
}
```

Rules attach to move types via their `constrains:` clause. A game
references a move type by name in a phase's `legal_moves:` or an
`offer`; the kernel move types are shared, so Hearts, Spades, and
Pinochle all use `play_to_trick`.

The set of legal move types in a phase is derivable from the phase's active
rules: each rule constrains a move type, so the legal move types are the union
across the rules. (Whether this should be implicit or explicitly listed in the
phase declaration is an open question — see
[open-questions/phase-legal-moves.md](open-questions/phase-legal-moves.md).)
