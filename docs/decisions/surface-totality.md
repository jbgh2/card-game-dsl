## Surface totality

The corpus-first gate ([principles.md](../principles.md), "Three implementations
before abstracting") governs *admission*: a construct or axis enters the
language only when games demonstrate the need. It does not license partial
implementation. Once a construct is admitted, its surface is **total** — every
composition the grammar accepts has an accounted outcome.

Concretely: when a construct is added or extended, enumerate its composition
points — the host production's other optional clauses, the selection modes, the
destination forms, and every executor branch that receives the node — and put
each cell in exactly one of three states:

1. **Implemented** — defined semantics, with a test.
2. **Statically rejected** — resolve/typecheck refuses the combination with a
   clear message, with a test asserting the rejection. The rejected combination
   gets a tracker record — a GitHub issue, cited in the ledger as
   `issue #N` — so a future game can lift it when it needs the cell.
3. **Grammatically inexpressible** — the grammar itself cannot produce the
   combination.

The fourth state — parses, runs, and silently ignores the clause
("accepted-but-ignored") — is a defect, not deferred work. For the design-tool
goal it is the worst failure mode: a designer who writes a legal sentence must
get either the behavior or an error, never a silent misread. When a cell is not
worth implementing, prefer static rejection over a runtime error, and never
silence.

**A clause nothing reads is refused.** A game clause whose readers are
constructs the game writes — the game's card points (the `card_points { }`
table or the `card_points` function), read by `card_points(card)`;
`suit ranking:`, read by `suit_value`; a Trick Order (its answers to
`is_trump`, `follow_class` and `card_strength`), read by
`highest_by_trick_order` on a round or by a call of `follows_lead`,
`highest_by_trick_order` or its three names outside its own answers — is
refused at the clause when nothing the game writes
reads it: its own text, every definition a library splices in, and every
library rule it activates. Judged on written text, not on the code that runs:
each reader is refused wherever it is written when its clause is absent, so
judging the same text is what keeps a sentence from being refused both with
the clause and without it. A clause's own body never reads it — a Trick
Order's three answers are one clause, so one calling another does not make
the Trick Order read — and an instrument is no reader: the end-of-game card
census and the OpenSpiel ranked policy's trump fallback read clauses without
making a game read them. A function answering no contract is no clause:
nothing refuses it for going uncalled.

**An accounted outcome is not enough: the outcome must be the one the surface
plainly says.** A combination that parses to *defined but unintended*
semantics — an omitted mandatory clause silently reinterpreting an adjacent
token, a wrong-typed operand comparing as always-false — is the same defect
class as accepted-but-ignored, reached through a misread instead of a
silence. Totality is therefore checked adversarially as well as
enumeratively: every new or extended form ships with **misuse probes** — the
most plausible wrong sentences an author would write (omitted mandatory
clauses, retired spellings, wrong-typed operands in every predicate context,
out-of-scope or shadowed binders, boundary-token slips) — each proven to
produce a diagnostic, and pinned as rejection tests. Grammar work carries a
specific probe: wherever an optional clause shares a boundary token with a
mandatory one, the omitted-clause and doubled-token variants must fail to
parse or parse to the same meaning, never to a different one.

**Composition points enumerate at every consuming pass, and pairwise.** A
combination made inexpressible at the grammar layer can still reach a
semantic pass that treats all forms uniformly (a resolver loop over
references, a typechecker branch over operators, a runtime arm over value
shapes) — each pass has its own cell matrix. And a new construct's cells
compose with the *existing* constructs its values can meet: every value shape
the construct produces is enumerated against every operation that consumes
that shape. Per-construct enumeration alone misses the defects that live in
the products of constructs. The mechanized recipe for all of the above is the
`surface-totality-audit` skill (`.claude/skills/`), a mandatory gate beside
the regression checks (CLAUDE.md, "Verifying changes").

The transfer production is the worked example of the matrix: the selection
modes (dealt / `chosen` / `random` / `all`), the destination forms (`to
<zone>`, `to each`, the round-robin `as-equally-as-possible to each` deal, the
gather), the `where` filter, the item noun, and the deferred clauses (the `in
<zone>` form, the `visibility =` override) compose into a grid in which every
cell is implemented (`tests/test_movement_filter_execute.py`) or statically
rejected (`tests/test_movement_combination_validity.py`) — see "The operation
vocabulary" for the enforced combinations.

**Minimal and complete.** The language carries one spelling per meaning and
no family with a missing member. A synonym — a second word the parser reads
as the same node — is dead surface the moment it lands, and leaves. A member
of a closed family — the alternatives of one rule or the words of one
terminal: `any` / `all` / `number of`, `sum` / `highest` / `lowest`, `rounded
up` / `rounded down`, `chosen` / `random` — ships whole with its family,
with or without a corpus writer, because a language with `highest` and not
`lowest` has a hole a designer meets and the language cannot explain. Such a
member carries a sunset: the direction review retires a member still written
by no corpus file ten corpus games after the review first lists it, and
re-reads the family's symmetry with it. The dead-surface report (`python -m
tools.dead_surface`) is the instrument: it classes every row it lists as a
sibling kept whole, a placeholder kept for the located message a rejection
fixture pins, a reject arm, or dead — and the dead class is pinned empty
(`tests/test_dead_surface_report.py`), so surface with no writer and no
reason cannot land. ADR-0004 records the ruling and the corpus-first cut
that lost.
