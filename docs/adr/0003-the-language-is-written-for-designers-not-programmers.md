# ADR-0003: The language is written for designers, not programmers; every refusal names the fix in the designer's words

- **Status:** Accepted
- **Date:** 2026-09-03
- **Ruled by:** the operator, as the reason given for the primitives block's spelling
- **Record:** PR #561 (merged 2026-09-04); the counsels on issues #472 and #517, which carried the sentence as a binding axis
- **Governs:** CLAUDE.md, "A note on the games" (the cold-read acceptance test, which a refusal is part of); the `cardlang-code-review` skill's register axis

## Context

The primitives block's parameter spelling was under design: a programmer's
generic (`Collection<Card>`) against a sentence a designer reads. The same
cycle's reviews had found refusals voiced by the lexer ("No terminal
matches '?'") and messages built from engine nouns ("the bundle is keyed by
bare name"). Backfilled on 2026-11-01 from the session record.

## Decision

The operator: "This language is used by designers not programmers." The
acceptance test for a game file — a non-player reads it cold and plays a
hand — applies to every refusal, because a refusal is part of that reading.
A diagnostic names the ruled form and the fix in game words, at a span the
designer can find. Engine vocabulary in a designer-facing sentence —
bundle, registry, table, arm, lexer terminal — is a review finding.

## Alternatives

- **Accept the engine's exact term where it is the precise word.** Lost:
  the reader is the designer, who cannot open the engine to learn what the
  word means.

## Consequences

Lexer-voiced refusals get teaching twins (the Diagnostic Grammar); the
register axis is part of every review brief in the repository; the same
register binds issue titles, which speak impact rather than mechanism
(CLAUDE.md, "The tracker"). A refusal that names a remedy is a claim about
the remedy, which must itself pass.
