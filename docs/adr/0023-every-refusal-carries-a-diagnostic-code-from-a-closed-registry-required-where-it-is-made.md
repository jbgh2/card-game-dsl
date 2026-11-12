# ADR-0023: Every refusal carries a Diagnostic Code from a closed registry, required where it is made

- **Status:** Accepted
- **Date:** 2026-11-10
- **Ruled by:** the operator, on the Architect's early counsel posted to issue #1046
- **Record:** issue #1046 (the counsel and the `## Ruling` comment); the PR that lands the registry and `cardlang check --json`
- **Governs:** decisions.md, "Every refusal carries its Diagnostic Code"

## Context

A tool reading `cardlang check` had only English sentences to read: nothing
told one refusal from another except the words, which change whenever a
message improves. The epic of making a designer's model able to author a
game end to end (issue #1043) needs refusals as data, and its benchmark and
query command key on what a refusal is. The early counsel counted about 550
report sites by grep on 2026-11-10 and set out three options for how a code
is assigned and held.

## Decision

"Full sweep": a closed registry of codes, the code required where a
diagnostic is made, so the type checker refuses an uncoded refusal, and every
report site takes its code in one change. Under the same message the desk
took the counsel's side on the two smaller calls: codes are spelled in
designer words (`unknown-zone`), and the text output of `check` never shows
one.

## Alternatives

- **Codes derived from the message or the raise site.** Lost: a code would
  change exactly when wording improves or a pass is split, the breakage a
  code exists to end, and no test could redden on it before a consumer broke.
- **Family-level codes first, finer codes later.** Lost: a tool still could
  not tell one resolver refusal from another, which is the issue's stated
  need; its variant with an "uncoded" placeholder would leave most refusals
  uncoded.
- **Numbered codes.** Lost: a number names nothing a designer can read.
- **Showing the code in the text output.** Lost: the text is the designer's,
  and keeping it byte-identical is the proof that the sweep changed no words.

## Consequences

- Adding a refusal means naming its kind of fix from the registry, or adding
  to it; a shipped code is never renamed, removed or given a second meaning.
- `cardlang check --json` prints the refusals as a versioned Record Envelope;
  the query command (issue #1047) docks on the same envelope.
- A runtime refusal takes the same record by its type; `play --json` and
  `demo --json` are issue #1095.
- Deliberately not decided: how fine a runtime code is beyond one per refusal
  type.
