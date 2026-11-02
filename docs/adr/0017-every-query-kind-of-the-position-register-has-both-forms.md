# ADR-0017: Every query kind of the position register has both forms, bare and over a collection

- **Status:** Accepted
- **Date:** 2026-11-02
- **Ruled by:** the operator, on the twin question the implementer put on #972, with Hoyle's implementation-stage sitting on the amended design
- **Record:** issue #972 (the operator's ruling, https://github.com/jbgh2/card-game-dsl/issues/972#issuecomment-6567933141; the question, https://github.com/jbgh2/card-game-dsl/issues/972#issuecomment-6566773771); PR #1025 (it lands the ruling, with Hoyle's sitting in its body)
- **Governs:** decisions.md, "Boards and cells"; decisions.md, "Position domains and positional zones"

## Context

ADR-0015's decision 2 refused the collection twin of the set form,
`<noun>s in <expr> where <pred>`, with a Diagnostic Grammar twin. Cut as
any noun, that twin also captured a membership written without its
parentheses: `if at in cells where …`, `if actor in players where …`. Cut
as the word `cells`, its message was false in every game with no board.
A boardless card game was told "cells live on the board", and the named
fix, `cells where …`, was refused; an integer `column` game was told the
same. The position register held `any` and `all` over a collection and no
collection count or set, so the card register's `number of cards in
<zone>` and `cards in <zone> where` had no position twin.

## Decision

"Make it symmetric."
- **Two forms join `quantifier`.** The collection set `<noun>s in <expr>
  where <pred>` and the collection count `number of <noun>s in <expr>
  where <pred>` join `any`/`all` over a collection. Every query kind then
  has both forms, as the card register has every kind over `in <zone>`.
- **The twin is deleted.**
- **The collection noun universe is completed** to the game's Position
  Domains and the board's `line`.
- **The membership capture is refused at resolve.** An unparenthesized
  membership that the collection set now parses, `at in cells where …`, is
  refused naming the parenthesized spelling.

This supersedes ADR-0015's decision 2 and extends its decision 3 to the
collection forms. Decisions 1, 3 for the bare forms, and 4 stand.

## Alternatives

- **The `cells`-only twin**, with the ruled message. It is false in three
  measured games with no board, and it leaves every other noun's
  collection twin an opaque syntax error.
- **A twin over every `<noun>s in <expr> where`, in words drawn from the
  game's own Position Domains.** It still refuses a sentence the card
  register states as the language. It also needs a twin that builds a node
  where every twin today raises, and it still captures a plural local
  tested without parentheses.

## Consequences

- **Measured on the amended grammar:**
  - corpus, library and stdlib: 38 of 38 files parse to the identical
    tree at zero ambiguity;
  - rejection fixtures: of 207, only the two collection-twin fixtures
    change;
  - the keyword-fusion sweep finds 0 deletions that still parse to the
    same tree.
- **The count's `where` is mandatory.** With it optional, `number of cells
  in cells where P` reads two ways.
- **A cell collection's source is a line or a collection of cells**, so
  `any cell in home(p) where …` and `any cell in neighbors(c) where …`, once
  refused, are the language.
- **#111's collection count/set wall is lifted** on completeness grounds.
  Numeric aggregation over a cell or line collection stays inexpressible.
- **#1024's capture shape is covered** for the position and player
  registers; the card register's stays with #1024.
