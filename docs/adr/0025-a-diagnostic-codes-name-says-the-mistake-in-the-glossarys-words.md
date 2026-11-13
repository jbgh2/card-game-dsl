# ADR-0025: A Diagnostic Code's name says the mistake, in the glossary's words

- **Status:** Accepted
- **Date:** 2026-11-12
- **Ruled by:** the operator, in session on 2026-11-11 and 2026-11-12, on the harness desk's proposals
- **Record:** PR #1101 (the two ruling comments); the PR that lands the renames
- **Governs:** decisions.md, "Every refusal carries its Diagnostic Code"

## Context

The registry ADR-0023 set up shipped with names a tool could key on but a
designer could not always read: engine words (`answer-reads-beyond-the-card`,
`climb-round-queries`), words the glossary reserves used bare (`unknown-rule`,
`type-mismatch`, `unknown-option`, `unknown-library`), and codes named after
the construct they were found in rather than the mistake (`board-shape`,
`mode-pairing`, `deal-distribution`, `choose-integer-bounds`,
`bad-requires-row`). No outside tool read the codes yet, so the shipped
spellings could change once, in one change, before one did. Two measurements
preceded the last names: standard-library text reaches two of the "library
text" codes (crafted text through the standard library's loader), and the
five sites of `unknown-index-domain` judge four different slots.

## Decision

- Engine words are respelled: `trick-order-function-reads-beyond-the-card`,
  `trick-order-function-calls-a-later-one`,
  `climb-round-lead-and-follows-mismatch`, `card-plays-look-alike`,
  `checker-type-not-known-here`.
- A reserved glossary word appears in a code name only inside an approved
  compound, and a library code names the sort of library: "with a consistent
  glossary an agent reading the error codes and the glossary can make an
  informed guess about where to look". The proposed names were confirmed:
  "Proposed code names look good".
- `name-taken` and `written-twice` both stay, "name-taken preferred over
  written-twice": a site that could be either is `name-taken`.
- `needs-a-trick-round` retires into `rule-never-consulted` (now
  `game-rule-never-consulted`); its one site that is not about a rule joins
  `unused-declaration`.
- Codes named after a construct are respelled: "each code says the mistake,
  and a refusal an existing code already names joins that code". The ruling
  covers the registry's other codes of that shape.
- Where the measurements split a code, it splits by the slot judged
  (`unknown-zone-index`, `unknown-zone-owner`, the `for each` domain, the
  query's position domain) and by the sort of library (a family library's
  code beside a standard library's).

## Alternatives

- **Keep the shipped spellings.** Lost: ADR-0023's stability rule protects
  tools, and none read the codes yet, so a single re-bless costs nothing a
  later rename would not cost more.
- **Merge `written-twice` into `name-taken`.** Lost: deleting a repeat and
  renaming one of two things are different corrective acts.
- **Keep `needs-a-trick-round`.** Lost: every refusal it held but one is a
  rule that would never be asked, which `rule-never-consulted` already names.
- **Keep the construct codes as umbrellas.** Lost: each held refusals asking
  for different fixes, several of them fixes an existing code already named.

## Consequences

- A test reads the glossary's reserved-words table and refuses a code name
  using a reserved word outside an approved compound; "checker type" and the
  round forms' names joined their rows' approved compounds, and a row whose
  compounds open "one meaning only" (the Outcome row) approves its bare word.
- The same ruling respells `unknown-round-function`, whose sites judge a trick
  round's winner function and early-termination predicate, as
  `unknown-trick-round-function`.
- Every `name-taken` and `written-twice` site is classified by the act its
  sentence asks for, over a scraped axis, so a misfiled site reddens.
- The board registry's refusals carry which misuse they are; the check-time
  teller is the one place a misuse is matched, exhaustively, and a refusal
  raised at play keeps the record layer's own code.
- From here ADR-0023's rule holds again: a shipped code is never renamed.
- The names minted for split and dissolved codes are proposals the operator
  may adjust, spelled where they can be with the language's own keywords
  (`choose-integer-needs-fixed-ceiling`,
  `deal-all-to-each-needs-as-equally-as-possible`); each is spelled once in
  the registry.
- A refusal joining an existing code restates that code's meaning line to
  cover it. Restated: `wrong-argument-count` (a board, a game rule and a
  checker type join a call and a zone type), `wrong-signature` (a `requires`
  row joins a definition), `checker-type-not-allowed-here` (a word of a type
  slot joins a checker type) and `game-rule-never-consulted` (a game rule no
  trick round asks joins one no decision asks). Joined with their lines
  unchanged: `out-of-range`, `conflicting-clauses`, `unused-declaration`,
  `missing-declaration`, `wrong-spelling`, `wrong-subscript` and
  `name-taken`.
