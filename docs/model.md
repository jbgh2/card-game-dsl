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
| **State variable** | A typed, named, scoped piece of game state. Scope is lexical: a variable lives as long as the phase instance that lexically encloses its declaration. See [decisions.md](decisions.md) "State scoping" and "Mutation semantics"; [appendix.md](appendix.md) catalogues every state variable across the five-game corpus as a reference for both. |
| **User-defined type** | A struct-like declaration with named, typed fields and optional `derived` fields. May be parameterized (see [library.md](library.md), "Types"). See [decisions.md](decisions.md) "Typed object model". |
| **Move type** | A named pattern of movement between zones, with declared source/destination/participating zones and associated events. Moves can carry cards (`play_to_trick`) or resources (`transfer`). Reusable across games. |
| **Move** | A specific instance of a move type with bound participants and content. |
| **Phase** | A bounded interval of game time during which a specific set of rules is active. May be nested (sub-phases) and sequenced. Has entry condition, exit condition, active rule set, and legal move types. May resolve to a typed outcome (see [decisions.md](decisions.md) "Typed phase outcomes"). |
| **Rule** | A named, parameterizable constraint on a move type. Attached to phases via the phase's active rule set. |
| **Constraint composition** | Rules combine by intersection (AND) over the set of legal candidate moves. |
| **Observation event** | An event emitted automatically by a move or memory operation, projected per observer according to the visibility settings of the zones involved (see [decisions.md](decisions.md) "Knowledge, visibility, and the projection model"). Maintained as per-player histories; used to derive information sets. |
| **Memory operation** | A stdlib-named operation that affects player knowledge (`peek`, `reveal`, `hide`, `shuffle`, `announce`, `expose_top`, `deal`, `transfer`, `muck`, `forget`). See [decisions.md](decisions.md). |
| **Resolution** | A deterministic computation over current state, used to drive non-choice moves (e.g., "who won the trick"). |
| **Scoring component** | A named, parameterizable function producing a ScoreDelta. Batched components compose by summation inside `apply_components:`; triggered components fire on specific events via `triggered_by:` clauses. Bridge introduced this; see [library.md](library.md) "Scoring components" and [decisions.md](decisions.md) "Scoring composition" / "Triggered scoring components". |

## The phase / state / move-type / rule relationship

This was the design crux. Resolution:

### Phases vs states

**Phases are not synonyms for state-machine states, but they are state-machine
states.**

- A phase is a *named interval of game time during which a particular rule set
  is active*. Phases are units rulebooks use.
- A state-machine state is a *discrete configuration the system can be in*.

Every phase corresponds to a state (or equivalence class of states) in the
underlying state machine, but most states aren't worth naming as phases. The
criterion for "this discrete configuration deserves to be a phase" is: **does
the active rule set change?**

If yes → phase (or sub-phase).
If no → just state (a variable, a counter, ordinary data).

This gives us a clean answer to the earlier "flags as a smell" observation:
flags that gate rules are sub-phases in disguise; flags that are purely
informational are just variables.

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
- **Move types** are named card-movement patterns. Rules constrain move types.
- **Move types are scoped to phases via the phase's active rules** (a move type
  is legal in a phase if rules constraining it are active there).
- **Events emit automatically from moves**, with visibility derived from zones.

### Sub-phases

A phase may contain nested sub-phases. Sub-phases inherit the parent's rule
set and add/modify their own. They have their own entry/exit conditions.

Example: Hearts' `play` phase contains the sub-phases `hearts_not_broken` and
`hearts_broken`. The transition between them fires on the first heart played.
The active rule set differs (`NoLeadingSuitUntilBroken(hearts)` is active
only in the first sub-phase).

This replaces the ad-hoc `hearts_broken` boolean flag with structure.

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
always playable last; see [decisions.md](decisions.md) "Rule exemption").

Rules are referenced from phases by name:

```text
phase play {
  active_rules: [MustFollowSuit, NoLeadingSuitUntilBroken(hearts), ...]
}
```

### Move types

A move type names a kind of move a player can make. Some are stdlib
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
`offer`; the stdlib move types are shared, so Hearts, Spades, and
Pinochle all use `play_to_trick`.

The set of legal move types in a phase is derivable from the phase's active
rules: each rule constrains a move type, so the legal move types are the union
across the rules. (Whether this should be implicit or explicitly listed in the
phase declaration is an open question — see
[open-questions/phase-legal-moves.md](open-questions/phase-legal-moves.md).)
