# Memory-event syntax

**Tier 4 — low impact, defer until forced.**

Games can declare custom memory-affecting events whose semantics
are expressed in the same projection vocabulary as the stdlib
operations. The vocabulary is closed; the runtime can derive
information-state tensors deterministically from any well-formed
custom event. The declaration syntax isn't yet pinned down —
awaits real examples beyond the stdlib operations.

**Coup (second data point).** Coup's challenge-defense — prove a
claimed character, return it to the court deck, reshuffle, and draw a
replacement — looks like a custom event but is expressed as a plain
composition of stdlib ops: `reveal` → `transfer` to court_deck →
`shuffle` → `deal`. No declaration was needed. This sharpens the
question rather than answering it: across the two non-trivial examples
so far (Stud's deal/muck choreography, Coup's reveal-return-redraw),
composition of the closed vocabulary has sufficed, so the live issue is
whether any real game needs a *named custom* event at all — or whether
the declaration syntax is unnecessary because composition always
covers it. Still awaits a case composition can't express.
