---
name: surface-totality-audit
description: "MANDATORY completeness gate for any change that adds or extends grammar surface, a checker Owner Guard or diagnostic, a native registry or kernel table, or any closed-domain mechanism — INCLUDING a change made in response to a review finding on one, where the finding is a sample of a class and never the spec for the fix. Run BEFORE writing the implementation — the grid is authored red first — and again before committing. Produces the artifacts the change must ship with: the grid (the crossed coverage domain as an executable test), the misuse-probe rejection tests, the completeness ledger, and — when answering a finding — the class ledger. A green suite is a regression gate, not a completeness gate; this skill is the completeness gate."
---

# Surface-totality audit

The two defect classes this repo ranks worst — accepted-but-ignored and
vacuously green (decisions.md "Surface totality", "Closed-domain
completeness") — are never caught by the regression gates (`mypy`, `pytest`,
byte-identical goldens). They are caught by two motions this skill makes
mandatory: **materialize the coverage domain as a grid — axes derived from
their registries in code, expected outcomes authored red before the
implementation exists**, and **probe the surface adversarially with the
sentences an author would plausibly get wrong**. Where this repo mechanized
completeness (the `assert_never` node dispatches, the glob↔registry pin,
the movement matrix), changes at scale shipped with zero coverage misses;
where the doctrine stayed prose, guards shipped with holes. This skill
converts the prose into artifacts, under one law: **an author-filled
artifact inherits the author's blind spot.** Every completeness claim this
repo lodged in prose drifted; every claim lodged in a check that runs held.
So coverage evidence is computed from the repo, never asserted about it —
prose is reserved for the judgment the grid cannot state itself.

## Step 1 — Materialize the grid, red, before implementing

Name the registry that defines the universe the change must cover, and
derive the cell list from it — in code, as the parametrization of a
checked-in test, never as a list in your head or a table in prose.
Hand-enumerating cases where a registry already defines the universe is the
tell that this step is being skipped.

**Each AXIS of the domain derives from its own registry in code** — the
operator axis from the operator terminal (ALL of it: ordering and arithmetic
ops, not only the ones the Owner Guard handles), the node axis from the Expr union,
the context axis from the full predicate-position list, the value axis from
the type registry, the declaration-position axis from the grammar
productions that reference the position's nonterminal (every production
naming `type_name` or `payload_type`, not the ones the change happens to
touch). Never derive an axis from the Owner Guard's existing coverage:
**a `domain:` row that is just the grid's parametrization spelled out in
English is the tell** that the domain was read off the implementation
instead of the registry —
the audit is then measuring the Owner Guard against itself.

**An axis with no defining site in code gets one as the change's first
deliverable.** Some universes are real but implicit — scattered across
grammar productions, or maintained by hand at several sites. Deriving such
an axis (a grammar scrape, an AST-union walk) is not preparation for the
audit; it IS the audit's first artifact, and the missing derivation is
itself a registry-drift finding to record. A hand-listed axis is complete
only by luck and goes stale silently the day a parallel change extends the
surface; a derived axis surfaces the new member as an uncovered row that
fails loud.

**When a change gives an existing domain a second definition site** (a new
deck-derived namespace beside a declared ordering, a new registry beside an
old declaration list), the sources' reconciliation IS part of the domain:
enumerate what happens when they disagree, and either guard the disagreement
at resolve time or record it. Two sources with no reconciliation check is a
`does not prove:` row, not background.

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

An Owner Guard guards its whole class **at the layer that owns the class**: an
operand-compatibility rule belongs in the type layer consulted by every
comparison-shaped context, not at the first site that motivated it. If the
Owner Guard is being written inline at one site, say why the class has exactly one
member.

**The framing check (mandatory, before outcomes are authored).** The grid
makes every decided cell honest; it does nothing for the axis you never
derived. So before authoring the expected column, hand a fresh subagent
the definition sources ONLY — the grammar, the AST unions, and the
registry modules (a domain defined by a native registry appears in
neither grammar nor AST) — never the diff, the plan, or your domain
statement — and ask what axes and positions the surface actually has.
Your own derivation is PROVISIONAL until this diff: the accepted domain
statement is what survives it, and no expected outcome is authored before
acceptance. Tell the subagent that unsure candidates are welcome — an
axis it half-suspects goes on the list, because the diff sorts
over-report cheaply and an under-report never surfaces. The same
permission runs through this whole process: unsure is a legal state with
a named route (a marked cell, the tracker, open-questions); the silent guess is
the only illegal move.
The definition-source set is itself an axis and gets no author-side
selection: it comes from the pinned registry-module manifest (a
checked-in list, itself pinned by a scrape over module-level registry
constants — tracked as issue #108 until it lands), and until that
manifest exists the subagent gets the ENTIRE `cardlang/` package.
Completeness by superset, never by judgment: a hand-picked subset
smuggles your framing back in through the input list. Diff its list against yours: every discrepancy is a new axis for the
grid or a recorded gap. The context that produced an implementation
plan frames the domain as the implementation's shape (a change statement
reading "validates function-param and variant-payload type names" has
already narrowed a five-position axis to the two positions it guards); a
fresh context is the same cure Step 2 applies to probes, applied where it
matters more — the frame.

**Materialize the grid, red, before implementing.** Cross the derived axes
into a checked-in parametrized test and author its expected-outcome column
before the implementation exists: every cell is a design decision — accept,
or reject with a named diagnostic. A genuinely undecided cell is never
guessed into the grid to complete the parametrization: a guess pinned by a
passing row carries the authority of an executed decision nobody made, and
the next author reads its flip as a regression rather than as an open
question surfacing. An undecided cell goes to the TRACKER with its guard,
not into the grid: its outcome is an open question, and no mark states one
— the gate still applies, so this is no cheap out. The grid pins decisions that have been
made; it is not a device for making them. Then run it. The red cells are the work list, and the red run is the proof the grid
can fail. Cells meant to keep current behavior may capture it from the
pre-change tree, but a captured value is reviewed as a decision — a
captured outcome nobody can justify is a design finding now, not a review
finding later. Implement until green. A cell that flips uncommanded is a
regression caught at write time; a commanded cell that stays green means
the grid does not reach the behavior — fix the grid before touching the
implementation.

The push discipline (both checks green before any push — CLAUDE.md) still
holds: commit the grid with strict `xfail` marks on the designed-to-flip
cells (`strict=True` per mark; a global `xfail_strict = true` in
pyproject makes it the default, so a bare mark cannot opt out). Constrain
each mark to the cell's designed failure — `raises=AssertionError` for
the outcome assertion, or the specific expected exception — because an
unconstrained xfail counts ANY exception as the expected red: a harness
crash, an import error, a broken fixture all masquerade as design-red
and exit 0. Red-for-the-wrong-reason is the vacuously-green class
wearing red. CI stays green, the implementation removes the marks, and
strict turns a leftover mark on a now-passing cell into a loud failure,
so a flip cannot be forgotten.

`xfail` is for a cell whose red is DESIGNED — you know the failure and can
name it. `skip` runs nothing and reports nothing, so a skipped cell is
enumerated-but-never-run wearing a mark: a broken harness stays quiet, and
so does an implementation that later satisfies the cell. Reserve `skip` for
a cell this harness genuinely cannot execute (an absent optional
dependency, a platform gate), and say so in `domain:` too. A cell whose
correct outcome is nobody's decision yet is not a grid cell at all — it is
an open question, and it goes to the tracker with its guard, because
reaching for `raises=` there invents the answer this order exists to
prevent. The red-to-green transition is then
visible in the diff. Structure the grid so its derived cell table is
exportable as data: the review replays the HEAD-derived cells against the
merge base (the cells that fail there, plus the cells that cannot exist
there, are the change's behavioral delta, materialized) — the base tree
must never re-derive the cell list, or a change that adds a production or
registry member loses exactly its new cells from the replay.

## Step 2 — Misuse probes (the adversarial pass)

For each new or extended surface form, write the **five most plausible wrong
sentences** a designer or an LLM author would produce, and run each through
`check_dsl`. Every probe must yield a diagnostic with a span, in the layer's
failure channel (compile = bag-collected diagnostic; runtime = typed
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
   bodies). An Owner Guard that fires in one context and not another is a hole, not
   an Owner Guard. Include pronoun-rooted members (`action.card.*`), which type
   differently from binder-rooted ones.
3. **Old-register / retired spelling** — must be rejected with the
   replacement named, not accepted with different semantics.
4. **Out-of-scope or shadowed binder** — an implicit binder referenced
   outside any introducing construct; the same implicit binder nested inside
   itself (self-comparison tautologies).
5. **Boundary-token doubling or shifting** — the extra `or`, the missing
   `:`, the singular/plural noun swap.

Probes that correctly fail loud become **rejection tests** in the change.
Probes that reveal a silent misread or a wrong-channel failure are defects
to fix before the change ships — or loud guards plus a roadmap record if
genuinely deferred.

**A cell without an executed row is not covered, whatever the prose says.**
Step 1's grid produces cells; a cell is covered when it IS a row the grid
runs. "Covered by the same code path", "covered by symmetry", and a prose
pointer to a test nothing walks are assumption, not coverage — the cell is
`skip` or `xfail` with its reason, or it is an issue. This applies with full force to the pairwise-interaction cells
(new value shape × existing operation): enumerating them and then running
none is the most common way this audit goes vacuously green.

For a large surface (several interacting productions), run the probes via a
**fresh adversarial subagent** given only the surface spec and told to break
it: the context that produced an implementation is conditioned to believe
it, and a fresh context is the cheap cure. **Slice by ledger**: one audit
run per ledger's surface (one Owner Guard, one construct family), not one run over
a whole branch — a single context auditing everything under-probes every
ledger; parallel narrow runs probe each domain to its edges.

**A pin born green carries its mutation witness.** Not every property is
grid-shaped: a performance bound, a fixpoint-termination guarantee, a
registry-equality or count pin over behavior that is already correct starts
life green — its red run never happened, so its capacity to fail is
unproven. Such a pin ships with the one-line mutation that reddens it: make
the edit, watch the test fail, revert, and record it in the test's
docstring as `red under: <the edit>`. The edit must plant the claimed
fault in the code under guard — production code, a registry, the scraped
surface — never in the pin's own assertions or expected values: a pin
that can only be reddened by editing itself guards nothing. The
obligation is per CLAIM:
anything the ledger credits with catching a failure is a pin and carries
its own witness — a module that can fail does not prove each credited
guard can (a dead assertion survives behind a live neighbor's witness).
A grid born red needs no witness —
its red run is the witness. A pin whose author cannot name a reddening edit
is not a pin; it is the vacuously-green class wearing a test's name.

## Step 2b — Answering a review finding: the class ledger

A review finding arrives pre-scoped, and that is the trap. It names a line,
so the line reads as the job; it arrives while you are closing a loop rather
than opening a problem; and its specificity reads as a specification —
"at minimum handle X and Y" invites doing exactly X and Y. **A finding is
one row of a class. It is never the spec for the fix.** decisions.md already
requires the sweep ("When an Owner Guard fails or a gap is found, sweep the class
before patching the instance … the sweep binds at find time, not fix time");
this step exists because that rule has been read and violated anyway, three
times in one branch, each violation shipped as a fix that a later reviewer
reopened. A rule with no artifact is a rule that decays.

So a change answering a finding on an audit-triggering mechanism writes a
**class ledger** BEFORE the fix, in the commit message or the PR body:

```
finding:  <what the reviewer named, verbatim in one line>
class:    <the closed domain that finding is one member of>
members:  <the members, DERIVED from the registry that defines them>
covered:  <which the fix closes>
residual: <which it does not, each with its guard and roadmap line>
```

The value is that it cannot be satisfied by intending to sweep. Writing
`members:` forces the derivation, and a `members:` line narrower than its
own `class:` line is visibly wrong on the page — which is exactly the
mistake that keeps shipping. `class:` is the load-bearing row: state the
domain in terms of the POSITION or PROPERTY, never of the syntax the finding
happened to use ("every way a role id is consulted", not "`==` against a
role string"), because the narrow spelling is how the next member escapes.

If deriving the class shows the finding is genuinely a one-off — the class
has exactly one member — say so in `class:` and why. That is a legitimate
outcome; an unexamined one is not.

## Step 3 — The completeness ledger

The grid IS the coverage record. No row of the ledger restates what the
grid runs — prose is the medium that drifts (a header claiming 13 sites
over a dict pinning 14; a citation no test walks), and a row that runs
is the medium that holds. What the table carries is the judgment the grid
cannot state itself, and it lives in the docstring of the grid's test
module — next to the code it describes, nowhere else:

```
property:        <the guarantee, one line>
domain:          <what is quantified over, and what is deliberately
                  outside it — the boundary stated positively>
registry:        <where each axis is derived in code, and where a property
                  this module leans on is proven elsewhere — locators only>
does not prove:  <what a green here does NOT establish, and why>
```

**`registry:` is the locator row; the other three are claim rows.** Nothing
in it asserts coverage. Two kinds of locator go there: where each axis is
derived, and — when a property this module depends on is pinned in another
module — that module's test id. The second is how you pay CLAUDE.md rule 4:
cite the sibling pin instead of re-copying its enumeration. Write it in
locator register, a label and the id, no assertion verb. "The partition is
pinned at X" is a coverage claim wearing a pointer's clothes; `partition:
tests/test_signatures.py::test_deck_only_classification_partitions_call_funcs`
is a locator.

Rank the rows by failure mode, not by how likely they are to be wrong: what
does being wrong license the reader **not to do?** A claim that something
is tested licenses not testing it, so a stale one leaves a gap open and
says it is closed. A stale locator sends the reader somewhere that is not
there, and `tests/test_ledger_referents.py` reddens on it.

**Route what is left; do not pour it into the last row.** Only an
instrument limit is a `does not prove:` row. The five other things you may
be holding have homes that act on them:

| what you have | where it goes | a row? |
|---|---|---|
| Deferred work | the tracker: `issue #N`, cited beside the guard | no |
| An uncovered cell | `skip`/`xfail` in the grid, with its reason | no |
| A domain boundary — nothing missing | `domain:`, stated positively | no |
| A designed constraint — never to be fixed | the spec, or a comment at the construct | no |
| An instrument limit — what a green does *not* prove | `does not prove:` | **yes** |
| Nothing | nothing; omit the row | no |

If you are about to write "not covered here" — stop and ask which of the
six it is. Three of them are not instrument limits at all, and the row's
name is what should have stopped you.

Deferred work goes **beside the guard**, never in a row: the refusal is
where a reader meets it, not the ledger. Add a positive sentence in
`domain:` too **only** when the deferral bounds what the module covers — an
unwritten form is a real limit on the domain today. If the deferral bounds
nothing, and most do not, writing a boundary sentence for it invents a scope
limit that is not there.

A boundary goes in `domain:` **positively** — name what holds, and what
rejects the rest. "X is not covered" reads as a gap and sends the reader
looking for work that does not exist.
`tests/test_ranking_conventions.py` states a domain with no exclusion in it
at all: every deck in `cardlang.runtime.values.DECKS` crossed with every
convention in `cardlang.runtime.values.RANKING_CONVENTIONS`, split into the
French cells, which carry frozen expected tuples, and the non-French ones,
whose guard is probed through real source per deck and per convention. That
names its set in good English, and no matcher should ever redden it.

`tests/test_ledger_referents.py` sweeps the tree for the half a matcher
reaches: every reference a ledger writes, in every row, must resolve. Two
things it cannot see, and they stay yours — a row naming a real test that
does not test what the row says, and a `does not prove:` row that is really
deferred work in disguise.

No matcher reads the prose of these rows, and that is deliberate. Prose
written to satisfy a matcher is worse prose, and a row naming its set in
good English is the goal — "every French deck crossed with every
convention in `RANKING_CONVENTIONS`, frozen expected tuples" is exactly
right and must never be reddened.

The gate follows the routing: **an uncovered cell without both a guard and
a record fails the audit** — the record being the mark's reason or `issue
#N` — **and a `does not prove:` row holding deferred work fails it
equally.** "No corpus witness" is never by itself a reason to leave a cell
silent — corpus-first governs which mechanisms exist, not how completely a
mechanism covers its own domain (decisions.md "Closed-domain
completeness"). When you notice a gap and defer it: write the guard or write
the tracker line — never neither. And when the construct itself has no
corpus witness, the change ships a minimal witness fixture — a complete
game exercising it end to end — because a corpus hole is an integration
blind spot, not an exemption (two of this repo's worst self-inflicted
defects lived on struct paths precisely because zero corpus games declare
one).

## Step 4 — Gate order

The order is: derive the axes -> framing check -> author the expected
column -> run the grid red -> implement -> green -> re-check the ledger
before committing. Answering a review finding inserts one step at the
front: derive the CLASS and write its ledger (Step 2b) before deciding what
the fix even is, because the finding's own scope is the thing most likely to
be wrong about it. Run this audit before writing the implementation, not
merely before writing the tests — the grid IS the tests, and a grid
authored after the implementation exists degrades into a transcript of
whatever the code already does, expected column included. `mypy` + full
`pytest -q` remain mandatory (CLAUDE.md) but they gate regressions, not
completeness; do not let a green suite stand in for a standard it does not
measure.
