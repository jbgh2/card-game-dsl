# ADR-0007: A game answers the kernel's trick facts by writing `function <name>`; the blocks that spelled them lower or retire

- **Status:** Accepted
- **Date:** 2026-10-22
- **Ruled by:** the operator, decision by decision against Hoyle's counsel
- **Record:** issue #921 (the Ruling section; Hoyle's counsel, comment 1); PRs for its three units, issues #942, #943 and #944, closed 2026-10-25 with milestone 18
- **Governs:** decisions.md, "Trick Order"; decisions.md, "Named functions"

## Context

A designer whose card points depend on more than rank wrote Belote's
`function bel_card_points(c : Card)` by hand and was refused the one name
the kernel's census read: `function card_points(c : Card)` "shadows the
native function of the same name". A Trick Order was three expressions
under a block heading with its own grammar, where `function is_trump(c :
Card) = …` is the same sentence. Step 5 of epic #818's cut list, under the
Destination "One meaning, written once". Backfilled on 2026-11-01 from the
issue.

## Decision

1. Native names are two registries, pinned disjoint: Builtins, which a
   game may never define, and Kernel Definition Contracts — `card_points`,
   `is_trump`, `follow_class`, `card_strength` — which only the game
   answers, by writing `function <name>` with the contract's signature, by
   the name alone with no marker, the way a game answers a library's
   `requires` row. `follow_class` and `card_strength` carry stdlib
   defaults; `is_trump` and `card_points` carry none, so absence is stated.
2. `card_points { }` stays as the designer's spelling, because it is how a
   rulebook presents the fact; the builder lowers it to the contract
   function, so the checker and runtime know only the four functions. A
   game writes the function directly when the table cannot carry the fact.
3. Three units in order, each proved on the tree the previous one left:
   the capability (Merge Lane B, zero corpus files move), the corpus (Merge
   Lane C, byte-identical at full width), the cut (Merge Lane A).
4. `trick_order { }` and the game-level `trump:` clause retire from the
   grammar, with retired-spelling twins that tell a designer the functions
   to write.

## Alternatives

- **The function as the only spelling of a point table** (`function
  card_points(c : Card) = if c.rank is A then 11 elif …`). Lost to the
  table, which lowers to it: the table is how a rulebook states the fact.
- **The Trick Order block kept.** Lost because its rows were already
  expressions and the function is the same sentence — a second spelling of
  one meaning.
- **A marker on the answering function.** Lost: the signature check does
  the work a marker would.

## Consequences

The kernel reads four functions and nothing else for these facts; a game
defining a Builtin's name is refused; the five Trick Order games and Spades
play byte-identically at full width after the rewrite. Milestone 18 closed
2026-10-25.
