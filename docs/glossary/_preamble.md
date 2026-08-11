# Glossary

The glossary of OpenRegel's shared language — one entry per concept, one spelling per
concept. (DDD calls this the "ubiquitous language"; this file is named for the word
people can actually remember — "vocabulary" belongs to the DSL itself; see its entry.)
`principles.md` already holds this rule for the DSL surface ("A second spelling is a
defect"); this file extends it to the implementation. When code, docs, or diagnostics
need a word for one of these concepts, use the term in the left column. When a word
appears in the reserved-words table below, do not use it unqualified.

Three usage rules bind every term in this file:

1. **Full phrase, always.** A multi-word term is never truncated — Owner Guard, not
   "owner"; truncation is how overloads regrow.
2. **Title Case in prose.** A glossary term is capitalized wherever it appears in
   comments, docstrings, docs, and issues — the capital marks "this is a Name, not
   two English words" and distinguishes the term sense from the ordinary word
   (the Author of a failure vs the author of a paper). Code identifiers keep their
   language's casing. (This is also DDD's own convention for ubiquitous-language
   terms.) Body prose is recased term-by-term as entries split into per-term files.
3. **One name, one shape.** A spelling shared across sibling modules claims
   identical meaning, return shape included — two functions named `deck_suits`
   returning an ordered tuple in one module and a frozenset in another is the
   witness defect.

Companion: `design-notes/glossary-findings.md` records where current code diverges
from this file, with evidence. Divergences below are marked (→ F-n).

Definitions of the game model itself stay in `model.md`; bounded contexts stay in
`design-notes/domain-map.md`. This file is the *naming* authority: what each thing is
called, and what each name may mean.

---

## Using this vocabulary

Two full phrases and a test-freeze word carry the whole taxonomy. Timing (static vs runtime) is never part
of a term — it's visible from where a guard lives, and both roles exist at both times.
Per the preamble rules: always the full phrase, always Title Case — never "owner"
(that's the zone-family owner) or "shadow". Bare "guard" is the family noun in prose
only; "check" stays the fully generic word for any validation. Retired spellings, recorded on the entries: *wall* (Owner Guard), *backstop* and
*twin* (Shadow Guard). Never names for a guard, but not retired spellings either:
*gate*, *sweep*, *mirror*, *copy*, *sibling* — ordinary words with lives of their
own here (the merge gate, sweeping a class, a sweep's sibling), so they take no
`retired_spellings` entry and must not be rewritten out of those uses. Freeing the word:
`MoveTypeDef.guard` → `.when` (a convergence rename the audit already mandated) rides
the migration.

These words currently carry 4–9 meanings each (see findings). In new code, comments,
docs, and diagnostics, always qualify them:

Interop is an anti-corruption layer (`domain-map.md`), so OpenSpiel's words legitimately
differ from ours. The translation is part of the vocabulary — keep it explicit:
The encoding's flattened move-type × parameter-domain cross-product is the
**offering block**. Inside `cardlang/openspiel/`,
OpenSpiel's senses of `action`, `player`, `state`, `observation` win; outside it,
ours do.

How work flows through agents and the operator. Mechanics live in `harness.md`;
these entries own the names.
