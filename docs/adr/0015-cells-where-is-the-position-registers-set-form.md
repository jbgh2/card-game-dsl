# ADR-0015: `cells where <pred>` is the position register's set form, with no new keyword

- **Status:** Superseded by ADR-0017
- **Date:** 2026-10-25
- **Ruled by:** the operator, decision by decision against Hoyle's single-seat counsel
- **Record:** issue #953 (the #972 section of the Ruling; Hoyle's counsel, comment 6); its unit, issue #972, a ruled Merge Lane A part of the hex milestone; the class issue #984
- **Governs:** decisions.md, "Boards and cells" (amended by #972)

## Context

Hex's win test needs the set of cells satisfying a predicate as a value —
the connectivity check over the cells a player holds. The position
register had `any`, `all` and `number of cells where` and no set-valued
form, and the collection twin (#111) does not admit cells. Written
2026-11-01 from the issue's Ruling section.

## Decision

1. **The bare set form:** `cells where <pred>` as one alternative in
   `quantifier` (`QNOUN _WHERE_KW expr -> q_set_domain`) beside `number of
   cells where`, no new keyword or terminal; the fold on the existing
   position-query node, typed `Collection<Cell>` (an integer position
   domain's noun yields `Collection<Integer>`), evaluating to a tuple in
   the domain's order.
2. **One twin** in the Diagnostic Grammar, for `<noun>s in <expr> where
   <pred>`: cells live on the board, not in a zone; the set form is `cells
   where <pred>`, with the membership in the predicate. R2.
3. **The noun universe is the declared position domains only**
   (`game.positions`: the board's `cell`, an integer `positions { }` name);
   after the `dir` lift (ADR-0011) the direction domain is a quantifier
   noun and `dirs where` stays refused by name.
4. **The promotion:** `DomainQuery.kind` becomes a closed `Literal`
   matched exhaustively in the evaluator, the type checker and the IR as
   the unit's first deliverable — an unknown position-query kind types as
   Boolean silently today — with the phrase table pinned to it; the same
   `str`-kind shape on `PlayerQuery`, `CardQuery` and `SubsetQuery` is one
   class issue (#984), not swept here.

## Alternatives

- **The keyword-led `the cells where`.** Lost on one name, one shape.
- **A grammar-free verb.** Lost as a shape the language has nowhere.

## Consequences

Two grid corrections ride with the ruling: collection equality under `is`
is accepted by value, so the grid pins both truth values against a region
verb; and `if at in cells where …` stays a syntax error under the
production (membership's right side sits below the query forms), so the
isolation probe is the call-argument or parenthesized shape. #972 joins
milestone 23; any thread implements it with a fresh Hoyle counsel
attached, and its PR stops at the operator's button.
