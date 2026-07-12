---
name: surface-totality-audit
description: MANDATORY completeness gate for any change that adds or extends grammar surface, a checker wall or diagnostic, a stdlib registry, or any closed-domain mechanism. Run BEFORE writing the change's tests and again before committing. Produces the two artifacts the change must ship with — the misuse-probe rejection tests and the completeness ledger. A green suite is a regression gate, not a completeness gate; this skill is the completeness gate.
---

# Surface-totality audit

The two defect classes this repo ranks worst — accepted-but-ignored and
vacuously green (decisions.md "Surface totality", "Closed-domain
completeness") — are never caught by the regression gates (`mypy`, `pytest`,
byte-identical goldens). They are caught by two motions this skill makes
mandatory: **derive the coverage domain from its registry**, and **probe the
surface adversarially with the sentences an author would plausibly get
wrong**. Where this repo mechanized completeness (the `assert_never` node
dispatches, the glob↔registry pin, the movement matrix), changes at scale
shipped with zero coverage misses; where the doctrine stayed prose, walls
shipped with holes. This skill converts the prose into artifacts.

## Step 1 — Enumerate the domain from its registry, at every layer

Name the registry that defines the universe the change must cover, and derive
the cell list from it. Hand-enumerating cases where a registry already
defines the universe is the tell that this step is being skipped.

**Each AXIS of the domain derives from its own registry in code** — the
operator axis from the operator terminal (ALL of it: ordering and arithmetic
ops, not only the ones the wall handles), the node axis from the Expr union,
the context axis from the full predicate-position list, the value axis from
the type registry. Never derive an axis from the wall's existing coverage:
**a ledger whose `domain` rows match its `covered` rows exactly is the tell**
that the domain was read off the implementation instead of the registry —
the audit is then measuring the wall against itself.

**When a change gives an existing domain a second definition site** (a new
deck-derived namespace beside a declared ordering, a new registry beside an
old declaration list), the sources' reconciliation IS part of the domain:
enumerate what happens when they disagree, and either wall the disagreement
at resolve time or record it. Two sources with no reconciliation check is a
residual row, not background.

Enumerate at **every consuming layer**, not only the grammar. A combination
made inexpressible at the grammar layer can still reach a semantic pass that
treats all forms uniformly. For each cell, record which layer accounts for
it:

| layer | typical registry |
|---|---|
| grammar | the production's optional clauses × alternatives |
| parse builder | placeholder/None shapes per optional group |
| resolve | ref kinds × ops (e.g. rule_ref plain/add/remove/override), name classifications |
| typecheck | operand types × operator shapes × **every predicate context** |
| runtime | value shapes reaching each evaluator/executor arm |
| IR | node fields, conditional keys |

Then enumerate **pairwise interactions**: every value shape the new construct
produces × every existing operation that consumes that shape (a new
collection-producing query × the existing emptiness / membership /
subscript / movement clauses). Per-construct enumeration misses defects that
live in the products of constructs.

A wall guards its whole class **at the layer that owns the class**: an
operand-compatibility rule belongs in the type layer consulted by every
comparison-shaped context, not at the first site that motivated it. If the
wall is being written inline at one site, say why the class has exactly one
member.

## Step 2 — Misuse probes (the adversarial pass)

For each new or extended surface form, write the **five most plausible wrong
sentences** a designer or an LLM author would produce, and run each through
`check_dsl`. Every probe must yield a diagnostic with a span, in the layer's
failure currency (compile = bag-collected diagnostic; runtime = typed
exception; never a bare assert, a raw Python error, or — worst — a
*differently-shaped successful parse*). Draw probes from these categories,
which map one-to-one onto this repo's historical misses:

1. **Omitted mandatory clause** — especially where an optional clause and a
   mandatory one share a boundary token (`… where <pred> or <default>`: what
   does the sentence parse as when the author forgets the default?). An
   accepted parse whose meaning diverges from what the surface plainly says
   is the same defect class as accepted-but-ignored. **The omitted-clause
   probe must use an absorbing operand**: the remaining text must contain
   the shared boundary token at top level (a compound-`or` predicate when
   the default is `or`-delimited), so the parser has something to misread —
   a probe that merely truncates the sentence tests the parser's error
   path, not the misread. A syntax error on the truncated form proves
   nothing about the absorbing form.
2. **Wrong-typed operand, in every predicate context** — the same bad
   predicate written inside each context that accepts predicates (query
   `where`, movement/reveal filters, rule `demands`/`applies_when`,
   `transition_to … where`, aggregation bodies and defaults, quantifier
   bodies). A wall that fires in one context and not another is a hole, not
   a wall. Include pronoun-rooted members (`action.card.*`), which type
   differently from binder-rooted ones.
3. **Old-register / retired spelling** — must be rejected with the
   replacement named, not accepted with different semantics.
4. **Out-of-scope or shadowed binder** — an implicit binder referenced
   outside any introducing construct; the same implicit binder nested inside
   itself (self-comparison tautologies).
5. **Boundary-token doubling or shifting** — the extra `or`, the missing
   `:`, the singular/plural noun swap.

Probes that correctly fail loud become **rejection tests** in the change.
Probes that reveal a silent misread or a wrong-currency failure are defects
to fix before the change ships — or loud walls plus a roadmap record if
genuinely deferred.

**A cell without a run probe is residual by definition.** Step 1's
enumeration produces cells; a cell may be marked `covered` in the ledger
only on the evidence of an executed probe or a named test that pins it —
"covered by the same code path" or "covered by symmetry" is assumption, not
coverage, and goes in `sampled` or `residual`. This applies with full force
to the pairwise-interaction cells (new value shape × existing operation):
enumerating them and then probing none is the most common way this audit
goes vacuously green.

For a large surface (several interacting productions), run the probes via a
**fresh adversarial subagent** given only the surface spec and told to break
it: the context that produced an implementation is conditioned to believe
it, and a fresh context is the cheap cure. **Slice by ledger**: one audit
run per ledger's surface (one wall, one construct family), not one run over
a whole branch — a single context auditing everything under-probes every
ledger; parallel narrow runs probe each domain to its edges.

## Step 3 — The completeness ledger

The change ships with this table (in the commit message, or the docstring of
the covering test module — somewhere the reviewer sees without asking):

```
property:   <the guarantee, one line>
domain:     <what is quantified over>
registry:   <where that domain is defined in code>
covered:    <cells exhaustively handled, and by which layer>
sampled:    <cells covered by example only, and why that is enough>
residual:   <cells NOT covered — each with its wall and its roadmap.md line>
```

The gate: **a residual row without both a wall and a record fails the
audit.** "No corpus witness" is never by itself a reason to leave a residual
cell silent — corpus-first governs which mechanisms exist, not how completely
a mechanism covers its own domain (decisions.md "Closed-domain
completeness"). When you notice a gap and defer it: write the wall or write
the roadmap line — never neither.

## Step 4 — Gate order

Run this audit **before** writing the change's tests (the domain enumeration
tells you what the tests are), and re-check the ledger before committing.
`mypy` + full `pytest -q` remain mandatory (CLAUDE.md) but they gate
regressions, not completeness; do not let a green suite stand in for a
standard it does not measure.
