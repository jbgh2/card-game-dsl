# Memory-event syntax

**Tier 4 — low impact, defer until forced.**

Games can declare custom memory-affecting events whose semantics
are expressed in the same projection vocabulary as the stdlib
operations. The vocabulary is closed; the runtime can derive
information-state tensors deterministically from any well-formed
custom event. The declaration syntax isn't yet pinned down —
awaits real examples beyond the stdlib operations.
