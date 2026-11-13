## Closed-domain completeness

Surface totality's principle, applied below the grammar. The corpus-first
gate governs which *mechanisms* exist — a proof harness, a projection
emitter, an action encoder, an invariant — exactly as it governs which
constructs exist. It does not govern how completely a mechanism covers its
own domain. Once a mechanism exists, its completeness is measured against
the domain it quantifies over, never against the corpus: "every corpus game
passes" is a witness, not a definition of done, because the games exercise a
sliver of any semantic domain.

The operative distinction is **closed versus open**, not thorough versus
lazy:

- A **closed, enumerable domain** — the projection lattice, the observation
  event vocabulary, the sequence dimensions of a log (content, multiplicity,
  order, extension), both directions of a biconditional, the arms of a
  dispatch over a registry — is covered *exhaustively*, derived from the
  registry that defines it, pinned complete against that registry by a
  static test, and backed by a runtime refusal on anything left over.
  Hand-enumerating cases where a registry already defines the universe is
  the tell that this rule is being violated: find the registry, derive from
  it, refuse on the remainder. The worked example is the soundness matrix's
  probe table (`tests/openspiel_ready/partition.py`, `ZONE_PROBES`): the
  distinctions each projection level must show and must hide are a declared
  table, pinned complete against `ZONE_PROJECTIONS` at test time and
  enforced by a probe-time refusal, so a new emission rule cannot be
  silently under-probed.
- An **open design space** — which round axes exist, the meld model, the
  constructive world generator — stays corpus-first: generalizing from zero
  or one instance produces speculative abstractions, and waiting is cheap.
  But every deferral must be a **loud guard** (a static rejection or a
  runtime refusal, with a test), never a silent gap. Deferred-and-guarded is
  corpus-first done right; deferred-and-silent is a defect.

**"Vacuously green" is a defect class of equal rank to
"accepted-but-ignored."** A check presented as a guarantee must be able to
fail: an assertion no input can reach, a perturbation that cannot alter the
observed value, a comparison that shares its code path with the thing it
checks, or coverage that quietly narrowed to nothing all read as proof
while proving nothing — the proof-layer analogue of a silently ignored
clause. A check cited as a guarantee states its quantifier (exhaustive over
what; sampled how); where it cannot cover its domain, it records the gap
(the coverage-record obligation in
[open-questions/structural-infoset-proofs.md](../open-questions/structural-infoset-proofs.md))
rather than reading as if it did. A check born green — a pin over behavior
already correct when the pin was written — additionally records and
demonstrates the one-line mutation that turns it red (`red under: <the
edit>` in its docstring), the mutation planting the fault in the code
under guard — never in the pin's own assertions or expected values; a
guarantee whose author cannot name a reddening edit, or can name only an
edit to the pin itself, is this defect class wearing a test's name. The crime is never
incompleteness; it is *silent* incompleteness.

Acceptance for changes to rigor-critical machinery — anything the
information-set guarantees, the encodings, or the invariants rest on — is
therefore a stated completeness argument, not a green suite. For an
enumerable domain the argument's canonical form is the **grid**: the
domain's axes derived in code from their defining registries — an axis with
no defining site gets its derivation built as the change's first
deliverable, because a hand-listed axis is complete only by luck and goes
stale silently when a parallel change extends the surface — crossed into a
parametrized test whose expected-outcome column is authored **before the
implementation exists** and run red first. Every cell is a design decision
(accept, or reject with a named diagnostic), so a cell that flips
uncommanded is a regression caught at write time, and a commanded cell that
stays green means the test does not reach the behavior. A cell whose
correct outcome is not yet decided is never guessed into the grid — a
guess pinned by a passing row carries the authority of a decision nobody
made; it goes to the tracker with its guard. An undecided outcome is an
open question, not a coverage gap, and no mark can carry one — `xfail`
asserts a failure nobody has decided on, and `skip` asserts nothing and
goes on asserting nothing.
The grid pins decisions that have been made; it is not a device for making
them. The grid IS the coverage record, so no row of the ledger restates
what it runs.

**Unsure is a legal state everywhere in this process; the silent guess is
not.** Every mandate above names its uncertainty exit: an undecided cell
goes to the tracker with its guard, an open design question to its
open-questions/ file, a
guard that cannot be classified does not land until it can, a review
claim rests at PLAUSIBLE without executed evidence. The imperatives here
prohibit manufactured certainty, never hesitation — a stated "not
decided" with a guard is the process working; a guessed answer wearing a
green row is the defect. The tie-breaker runs the same way: when unsure
whether a gate applies, it applies — the superset is cheap, the guess is
not. The
judgment columns ship as the **completeness ledger** in the grid module's
docstring:

```text
property:        <the guarantee, one line>
domain:          <what is quantified over, and what is deliberately
                  outside it — the boundary stated positively>
registry:        <where each axis is derived in code, and where a property
                  this module leans on is proven elsewhere — locators only>
held by:         <the Enforcement Ladder rung this guarantee sits on; below
                  Unrepresentable, why its fact cannot live a rung higher>
does not prove:  <what a green here does NOT establish, and why>
```

**`registry:` is the locator row; the other four are claim rows.** Every
entry in it points into code and none of them asserts coverage. Two kinds
of locator live there: where each axis is derived, and — when a property
this module depends on is pinned in another module — that module's test id.
The second is what keeps [maintaining.md](../maintaining.md)'s
cross-reference-don't-duplicate rule payable at all: cite the sibling pin
rather than re-copying its enumeration, which is the duplication that
drifts. Write it in locator register, a label and the id with no assertion
verb, because "the partition is pinned at X" is a coverage claim wearing a
pointer's clothes, and no row of this format holds a coverage claim.

The division is by failure mode, which is how prose should be ranked: not
by how likely it is to be wrong but by **what being wrong licenses a reader
not to do.** A wrong claim licenses inaction — a row asserting something is
tested is a reason not to test it, so a stale one leaves a gap open and
says it is closed. A wrong locator sends the reader to a place that is not
there, and `tests/test_ledger_referents.py` reddens on it.

**Only `does not prove:` carries a caution**; the other four state the
guarantee, its scope, where to look, and the rung that holds it
("Prefer the guard you cannot need"). The row is named for the one thing
it may hold, because a catch-all noun catches all — deferred work, an
uncovered cell, a domain boundary and a designed constraint make four
different demands on a reader, and each has a home that acts on it. A slot
named for what it holds cannot take the others:

| what you have | where it goes | a row? |
|---|---|---|
| Deferred work | the tracker: `issue #N`, cited beside the guard | no |
| An uncovered cell | `skip`/`xfail` in the grid, with its reason | no |
| A domain boundary — nothing missing | `domain:`, stated positively | no |
| A designed constraint — never to be fixed | the spec, or a comment at the construct | no |
| An instrument limit — what a green does *not* prove | `does not prove:` | **yes** |
| Nothing | nothing; omit the row | no |

Three of the six are not instrument limits at all. The slot name does the
sorting, so mis-filing stops at the point of writing rather than at review.

A **history** is none of the six. A residual row often accumulates the
story of how something came to be fixed -- which defects escaped, who found
them, what the fix replaced -- and none of that describes the guarantee
today. Route it the way the rest of the spec is routed: the design it argues
for goes to the construct and is stated there as the design, in the present
tense, never as the story of what it replaced -- a docstring says what the
code does and why it is shaped that way, not what went wrong before. The
narrative goes nowhere ([maintaining.md](../maintaining.md), spec not
history). It is
specifically NOT an instrument limit. Writing "a green here is no evidence
about X" because X once went wrong states something false the moment X is
pinned, and the row that says so is read in the present tense.

Deferred work records **beside the guard that makes it loud**, never in a
row — the ledger is not where a reader learns that something is unbuilt, the
refusal is. Where the deferral also *bounds what the module covers*, the
boundary additionally gets its positive sentence in `domain:`, citing the
same issue: a form that has not been written yet is a real limit on the
domain today, and stating it there is not a duplicate of the guard but the
scope it implies. Most deferred work bounds nothing — a cell that ought to
be covered and is not — and inventing a boundary sentence for it would
manufacture a scope limit that does not exist.

Between the two marks, prefer **`xfail(strict=True, raises=...)`**: strict
reddens the moment the cell starts passing, so an implementation that
satisfies the case cannot land unnoticed, and `raises=` keeps a harness
crash from impersonating the designed red. **`skip` runs nothing and says
nothing, forever** — a skipped cell is enumerated-but-never-run, the defect
this section names, wearing a mark. Reserve it for a cell the harness
genuinely *cannot* execute here (an absent optional dependency, a platform
gate): that is a fact about the environment, and it belongs in `domain:`
as a boundary as well. A cell that could run and is merely unwritten is
`xfail`, or it is an issue.

The gate follows the routing: an uncovered cell without both a guard and a
record fails it — the record being the mark's reason or `issue #N` — and a
`does not prove:` row holding deferred work fails it equally, because the
row's name is the thing that was supposed to stop that. "No corpus witness"
is never by itself a reason to leave a cell silent, because corpus-first
governs which mechanisms exist,
not how completely a mechanism covers its own domain — and when the
construct itself has no corpus witness, the change ships a minimal witness
fixture (a complete game exercising the construct end to end): a corpus
hole is an integration blind spot, not an exemption. A guard guards its
whole class at the layer that owns the class: an operand-compatibility rule
lives in the type layer consulted by every comparison-shaped context, not
at the first site that motivated it. The `surface-totality-audit` skill
(`.claude/skills/`) operationalizes this section and "Surface totality" as
a pre-commit gate, including the red-first order (axes -> framing check ->
expected column -> red -> implement -> green) and the
`xfail(strict=True, raises=...)` mechanism — each mark constrained to the
cell's designed failure, so a harness crash cannot impersonate the red
run — that keeps the pre-push checks green while the red-to-green
transition stays visible in the diff.

**Every reference a ledger writes resolves.** A ledger names things — a
test id, a tracked file, a module attribute — and a name goes stale in
silence: a rename moves a test out from under the row citing it, and the
row goes on reading as authoritative forever. A format with no coverage row concentrates
rather than removes this hazard, because the weight it does carry is
locators, and a locator's whole value is that it resolves.
`tests/test_ledger_referents.py` sweeps every completeness ledger in the
tree and holds every reference, in every row, to resolving. What no matcher
reaches is a row naming a real test that does not test what the row says;
that stays the reviewer's, and that module's own ledger records the reach
rather than leaving it implied.

No mechanism polices the prose of the surviving rows, and the reason is
measured rather than assumed. Requiring a quantified sentence to name its
set beside it fires only on ordinary English here: pointed at any row of
this format it flags eight sentences across the tree, all eight of them
correct prose (measured 2026-08-20, 90 ledgers). Prose written to satisfy a matcher is
worse prose, and a row naming its set in good English is the goal, not the
violation. The class ledger keeps its own `covered:` row and the rule with
it — there `members:` is the named set, derived on the line above. The
completeness ledger holds no row a matcher should read.

**Widening a ledger's sentence until its check goes green is the defect.** A
`property:` or `domain:` sentence widened to admit new pins credits rows the
module does not cover, so a widened ledger re-derives every axis from that
axis's own registry. A claim found broader than its pins is removed, not
sharpened: a more exact overclaim is still an overclaim.

**Prose names the registry, never the cardinality.** A ledger row — or any
spec sentence — states what it quantifies over, not how many members that
set holds today. "Every registry with a signature table" stays true as
registries are added; "the four registries" is false the moment one is,
and a stale tally is indistinguishable from a fresh one, so it rots in
silence where a broken path or a failing pin would announce itself. That
silence is what makes it the same defect as a row claiming coverage it
does not have, one layer out: the count is a second statement of a fact the code already
holds, and the two drift (`decisions.md` is not exempt from
[maintaining.md](../maintaining.md)'s cross-reference-don't-duplicate rule).
Where the set is worth naming, name the registry that defines it — the
prose-only game Shadow Guards are `PROSE_ONLY_TWINS`, not "six Shadow Guards" — so a
reader can count it and a change that grows it cannot leave the sentence
behind. Identifiers in prose carry the same hazard for the same reason:
nothing checks that a backticked name still resolves, so one naming a
deleted registry reads as authoritative forever. Numbers that are facts
about the *domain* rather than the repo — four suits, thirteen ranks, a
two-card trick — are not tallies and are unaffected.

**The test is whether the count can go stale in silence.** A sentence
counting the language's own designed surface — a sub-phase's three exit
forms, the two shapes of a `demands:` clause, the four suits — is safe,
and this rule does not touch it: adding a fourth exit form *is* a spec
edit, so the sentence is revisited by the very change that would falsify
it. What rots is a count of a set that accumulates through routine work —
registry entries, corpus games, deferred cells, review findings — because
nothing about adding one prompts anyone to revisit the prose, and the
count and the set drift apart unwitnessed. Count a designed surface
freely; never count an accumulating one. Read the other way, this rule
applied bluntly would strip the spec of sentences that state the design,
which is the opposite of what it is for.

**Scope is the tense, not the document.** The rule binds any doc making a
present-tense claim about the repo — `docs/`, design notes, and module
docstrings alike — because a reader acts on the present tense wherever it
appears, and a proposal's supporting evidence misleads exactly as a spec
sentence does once it stops being true. The exemption is therefore not a
document class but an explicit date: a measurement framed as a snapshot
(the mutation sweep's operator and seed counts, now carried by issue #109)
is a historical record and stays as written,
because it claims only what was true when it ran. A live claim that would
be correct if dated should be dated, not deleted — the figures are
evidence, and deleting them to satisfy this rule would cost the argument
its support.

**A fact specified and not yet built is marked, never deleted.** Where a doc
specifies a construct or symbol the tree does not implement, the sentence says
so and names the issue that builds it; it is neither deleted to satisfy this
rule nor stated as present. The mark is the one place spec prose speaks of what
is not yet built, and it is an exception that keeps a specified surface
findable, never a license for future tense elsewhere.

An Owner Guard must also speak its **layer's failure channel**: the compile
stages fail as diagnostics (`DiagnosticBag`, with a span and a
designer-readable message — a raw registry raise mid-resolve is loud in
the wrong channel and suppresses every other diagnostic in the file);
the runtime fails as typed exceptions; the proofs fail with a witness.
Loud-but-wrong-layer is a bug with the same rank as silent. "Channel" is
never bare: a game's scoring channels, the observation channel and a
library's feeding channel are different things (see the glossary's
reserved words).

**A check lands only after naming its owner (write-time triage).** Two
tells at edit time mean information is being lost rather than defended:
*re-deriving* a fact an earlier pass already established (re-classifying
a name instead of reading the `ref_kind` the resolver stamped, re-inferring
a type the checker validated, re-computing visibility the zone-type table
declares), and *guarding* a condition that is already checked somewhere
else. Either tell stops the edit — the fix is upstream, not local. Before
it lands, the check is classified as exactly one of three things: an
**Owner Guard** (it moves to the layer that owns the class, in that layer's
failure channel, with a test), a **Shadow Guard** (it stays, and its comment names
the Owner Guard it shadows — and the recorded gap that makes it reachable,
if one exists), or a **missing Owner Guard** (the Owner Guard is built at the owning
layer, and the local site becomes a Shadow Guard citing it). A guard that
cannot say which of the three it is does not land. Each pass states its
contract — what it assumes, what it establishes, and what becomes illegal
after it — in a `Contract` block in its module docstring
(`cardlang/parse.py` through `cardlang/ir.py`); the owning pass's contract
decides where a check belongs. Each Establishes clause also says how it is
held: the rung of the Enforcement Ladder that keeps it true
("Prefer the guard you cannot need") — Unrepresentable, Derived and Pinned,
Born-Green Pin, or Review-Enforced Prose — and a clause held below
Unrepresentable names why its fact cannot live a rung higher, the same line
a ledger's `held by:` row carries. A Contract Block without held-by lines
gains them when its module is next edited; a new one carries them from
birth. For the runtime packages the triage is
mechanized: `tests/test_assert_triage.py` scrapes every assert-channel
site in `cardlang/runtime/` and `cardlang/stdlib/` and fails the build on
any site whose attached text names neither a dispatch fallthrough nor the
Owner Guard it shadows.

**When an Owner Guard fails or a gap is found, sweep the class before patching
the instance.** A found defect names a class: identify the closed domain
the instance belongs to, probe every other member (the other projection
levels, the other declaration namespaces, the other malformed inputs),
and close or guard the whole class in one change. A lone patch converts a
class defect into a recurring one — the corpus's duplicate-name
shadowing sat for months as exactly this: the duplicate-move-parameter
instance was fixed while duplicate zones, state variables and move types
kept shadowing silently until the class was swept. The
sweep binds at find time, not fix time: a *report* of one cell of a
crossable product is an incomplete report — cross the product and report
the pattern, whoever holds the finding.

**The sweep is hardest, and most often skipped, when someone else holds
the finding.** Self-found gaps get swept because finding one already
required asking what the domain was. A finding that ARRIVES — from a
reviewer, a bot, a bug report — arrives pre-scoped, and its scope is the
thing most likely to be wrong about it: it names a line, so the line reads
as the job; it lands while the work is closing a loop rather than opening a
problem; and its specificity reads as a specification, so "at minimum
handle X and Y" gets answered with exactly X and Y. This rule was read and
violated three times in a single branch on exactly that path — each fix
correct about the instance named, silent about the class, and each reopened
by the next reviewer.

Prose did not prevent that, so the rule carries an artifact. A change
answering a finding on a closed-domain mechanism writes a **class ledger**
before the fix — `finding` / `class` / `members` / `covered` / `residual` /
`why missed`, with `members` DERIVED from the registry that defines them
(the `surface-totality-audit` skill owns the form). `why missed` says which
guard and test should have caught the member and what they looked at
instead. "The guard reads the code and nothing checks what runs" means the
fix is a runtime check and an agreement test, not another member; a second
ledger on the same guard, or several findings at once on one guard, means
the guard is the problem and takes one ledger. It cannot be satisfied by
intending to sweep: a `members` line narrower than its own `class` line is
visibly wrong on the page, which is the one thing the exhortation could
never be. State `class` as the position or property — "every way a role id
is consulted" — never as the syntax the finding happened to use, because
the narrow spelling is how the next member escapes. A class of exactly one
member is a legitimate answer; an unexamined class is not.

**A check's comment names the downstream contract, never the downstream
exception type.** A guard is most naturally justified by what goes wrong
without it, and the temptation is to name the crash: "without this guard,
`to each hand[0]` would die on the executor's `NameRef` assert". That
couples the comment to another module's current implementation — the one
detail a reader editing *this* file never sees, and the one most likely to
move. The failure channel is deliberately mobile here: a bare `KeyError`
becomes a typed `RuntimeError`, a Shadow Guard assert becomes an Owner Guard one layer
up. Every comment naming the old type is then confidently wrong while still
reading as precise, which is worse than vague. Name instead what the
downstream layer *requires* — the thing that actually justifies the guard:
"without this guard, it would reach the executor, which requires a zone in
this position and refuses anything else at play time". The warning survives
a change of channel; the coupling does not. The exception type is
load-bearing in two places. The first is an argument *about* the failure channel
("a typed error, not a bare `KeyError`"), where the type is the subject
rather than incidental colour. The second is a type that carries a guard's
ROLE — `OwnerGuardError` and `ShadowGuardError` (glossary/owner-guard.md, glossary/shadow-guard.md) — where
the type IS the classification rather than a report of it. Mobility still runs
in the direction this rule was written for: bare to typed is an upgrade in
specificity, and it stays free. What is no longer free is a guard changing
ROLE, which now changes its type, and deliberately so — a guard moving from
authoritative to redundant, or one layer to another, is a design change, and
the type is what makes it visible instead of silent.

State the consequence in the subjunctive — "would check clean and die" —
not as a past event ("checked clean and died") and not as a present claim
("checks clean and dies"). The past tense is unfalsifiable: it stays
literally true after the behaviour it describes is gone, so it rots into a
misleading implication that nothing can catch. The subjunctive says
something about the code as it stands, which means a reader can check it
and the claim can be found wrong — the same reason guards beat prose
everywhere else in this document.

### Every refusal carries its Diagnostic Code

A refusal is told to a tool as well as to a designer, and the two read it
differently: the designer reads the sentence, a tool keys on the
[[diagnostic-code]] (`cardlang/diagnostic_codes.py`). The registry is closed,
and `Diagnostic.code` is a required field, so a refusal made without a code
does not type-check (Unrepresentable). A code names the **kind of fix** the
refusal asks for, in the designer's words (`unknown-zone`, `written-twice`,
`decides-on-hidden-cards`): two refusals share a code exactly when the
corrective act is the same kind, never because their wording or their raise
site is shared. A code derived from the message or the site is rejected,
because it would change exactly when wording improves or a pass is split,
which is the breakage a code exists to end. A refusal whose fix cannot be
stated in designer words is a finding about that refusal, never a reason
for a vague code. A code's name says the mistake, never the construct it is
found in, and uses a word the glossary reserves, singular or plural, only
inside a compound that word's own entry marks (`compounds:`;
`unknown-game-rule`, `checker-type-mismatch`), so a reader holding the
glossary can tell from a code where to look. Of the refusals about a name,
one asking the author to rename one of two things is `name-taken`, one
asking to delete or merge a repeat is `written-twice`, and one that could be
either is `name-taken`. ADR-0025 records the names. A
shipped code is never renamed, removed or given a second meaning, and a
refusal's code does not move silently: the blessed list holds every code's
spelling and meaning, a witness per code holds that each is
told, and every rejection case's ordered codes are a golden beside its text
(tests/test_diagnostic_codes.py). A site no rejection case reaches can move
to another code with no test reddening; the grid module's ledger says how
many there are and how to count them. The ruling and the options it refused
are ADR-0023.

The code never reaches the text output: `Diagnostic.format` does not show
it, and the rejection corpus staying byte-identical is the proof. A tool asks
for it with `--json`, which every command takes: `cardlang check --json`
prints one [[record-envelope]] (`cardlang/records.py`): `schema`, `kind`, and
one record per [[told-diagnostic]] carrying its code, severity, [[author]],
place (file, line, column, length), message, notes and suggestions, the
lines the command line prints beside the refusal among the notes, each with
no place. A suggestion is a
[[near-miss]], marked `offered`, never mechanically applicable. The record
composes no words: its message is the diagnostic's own, and its author is
the one the telling layer stamped (the attribution step for a pass, the raise
for the parser and the extract step, the command line for its own refusals,
and `refusal_diagnostic` for a runtime refusal, keyed on its type). A reader
refuses an envelope whose `schema` or `kind` it does not know. `--json` is
total on every command: stdout holds the one envelope and nothing else, with
the exit code the text gives; under `play` and `demo` every refusal is a
record, the command's own included, and everything else the command prints
goes to stderr word for word. Beside `--emit-ir` it is a usage error, and a
command line refused before it is read is refused as text. The exit code
says who must act, by the author of the refusal told: the game's or a
library's 1, the invocation's, the installation's or a registration's 2, the
engine's 3, an exception outside the typed channels raised while the
command is carried out included.

### Allow-list, never deny-list

A consumer of a closed domain enumerates the members it **handles** and
makes everything else fail loudly. It never enumerates the members it
treats specially and lets the rest fall through to a default. The first is
an allow-list; the second is a deny-list, and a deny-list over a closed
domain is prohibited.

The reason is an asymmetry in what happens when the registry grows, which
is the only moment either shape is tested:

- Under an **allow-list**, a new member breaks every consumer that has not
  been extended, by name, at build time. The cost is a loud failure in
  code someone is already editing.
- Under a **deny-list**, a new member silently acquires the default's
  behaviour at every consumer at once. Nothing fails; the game runs; the
  answer is wrong. The author of the registry change never learns which
  consumers assumed something about the members that existed when they
  were written.

This is not a preference between equally valid styles. A deny-list encodes
"every member I did not name behaves like this one" — a claim about
members that do not exist yet, which no author is in a position to make.

**Enforcement follows the domain's visibility to the type checker.** Where
a closed domain is a Python union, the allow-list is a type error: every
consumer dispatches with a structural `match` ending in
`typing.assert_never`, so under `mypy --strict` adding a node without
handling it everywhere fails to compile (docs/building.md, "Typed-AST
discipline"). Where the domain is a registry of strings — the stdlib
registries — the type checker cannot see it, so a pin substitutes for it:
`tests/test_operand_choke_point.py` requires every operand coercion to
route through one check, deriving its axes from the registry it guards so
it widens with that registry rather than going stale. Visibility is
itself a choice, not a fact of nature: a string domain the checker cannot
see can usually be promoted to one it can (see "Prefer the guard you
cannot need"), and the pin is the right mechanism only where that
promotion is genuinely priced and declined. The domain table's role ids
are the worked example of the promotion: they are `domains.Role`, a plain
`Enum` every consumer dispatches over, so comparing a role against a
string literal is a type error and the marker scrape that used to ask for
a reason is gone. What `tests/test_role_comparison_pin.py` still holds is
the residue the type cannot see — strings that merely SPELL a role
(`player` as an unresolved name, `suit` as a component-set axis) — guarded
per module so a new one must be looked at. A closed
domain with neither an `assert_never` nor a pin is unenforced, whatever
its consumers currently do.

### Pin the derivation, not just the instance

Deriving a fact from a registry is half the rule. The other half is that
the derivation must be **pinned**, because a registry only prevents drift
in the consumers that actually consult it, and nothing stops the next
consumer from re-spelling the fact locally.

The evidence is this repo's own history. `domains.zone_key_of` was
introduced to replace an `== "team"` re-spelling at five consumer sites,
"each of which silently defaulted every non-team role to player keying".
That cleanup fixed five instances and left no guard — so the class
regenerated: a per-site enumeration of Player positions with no pin (the
positions the enumeration missed went unchecked), an empty team domain read
as an unknown bound (the check skipped itself), and a sixth `== "team"` in
a new consumer (every future role read as player-keyed). Three findings,
one shape — the deny-list above, three times. Five separate files carry
comments narrating earlier rounds of the same cleanup, which is what a
convention without a mechanism looks like.

So a closed domain gets both halves:

- **Derive** the fact from the registry wherever a consumer can.
- **Pin** it where a consumer cannot. A consumer that legitimately
  implements one row reconciles itself against the registry beside the
  branch, so widening the table fails *there*, by name —
  `runtime/execute.py` pins its player-only simultaneous executor against
  `SIMULTANEOUS_ROLES`; `resolve` pins its empty-domain guards against
  `ZONE_INDEX_ROLES`; `openspiel/replay` pins its returns
  keying against the same set as `resolve` and raises for a role it cannot invert, exactly as
  `domains.zone_observer_key` does rather than guessing player keying.
  The practising sites are enumerated in code, not here: the census in
  `tests/test_registry_guard_witnesses.py` derives them and demands a witness
  for each, so a site added without one fails there rather than going unlisted.

**The boundary is closed versus open, and it is load-bearing.** Everything
above applies to a domain whose membership is enumerable — a union, a
registry, a table. Over an OPEN domain the same shape is a defect in the
other direction: an allow-list there would refuse values the language is
deliberately permissive about, and a guard that manufactures an error is
exactly what the gradual-typing promise forbids (see "`Any` means the top,
never a failed lookup", which owns that case — `TAny` passes, and a
*lookup miss* against a table the program does have raises rather than
falling back). The two rules meet at the same principle: a fallback
standing in for an answer the program could have looked up is a silent
wrong answer. Deciding which side a domain sits on is therefore the first
question, not an afterthought — and "unsure" resolves to closed, because
an unnecessary loud failure is cheap and a silent default is not.

### Prefer the guard you cannot need

Enforcement has a ladder, and each rung down costs more to hold:

1. **Unrepresentable** — the illegal state cannot be written: a union the
   type checker dispatches over, a grammar that cannot produce the
   combination, a fact derived from one defining site so a second copy
   cannot exist.
2. **Derived and Pinned** — the fact has one source; consumers derive from
   it, and a pin catches the consumer that re-spells it.
3. **Born-Green Pin** — behavior already correct, guarded by a check that
   names its reddening mutation, its witness.
4. **Review-Enforced Prose** — an authoring rule, held by whoever happens
   to read it.

Every claim on a lower rung is machinery that must itself be kept honest —
markers need reasons, reasons need vocabularies, scrapes need manifests —
and that maintenance is where enforcement findings breed. So a proposed
pin carries one more row in its ledger, `held by:`: the rung, and **why the
fact cannot live a rung higher.** "The domain is strings the checker cannot
see" is an answer only after asking whether the strings should be a union
the checker can see —
a registry of role ids is a closed domain by definition, which is exactly
the shape an enum holds for free. A pin whose fact could have been a type
is built on the wrong rung, and the findings it later generates are the
interest on that choice.

The rung is stated wherever a guarantee is written down — a ledger's
`held by:` row, a Contract Block's held-by line (write-time triage,
above) — and the top rung is the default: a clause whose fact a union, an
exhaustive match or a single constructor can hold is held there, and a
lower rung is a recorded decision, never a default. ADR-0010 records the
rung-first default and the two shapes that lost.

The rung is a design decision and gets recorded like one: when rung 3 or 4
is chosen over an available rung 1 or 2, the ledger says why (a subtype
relation the type system deliberately lacks, a migration priced and
deferred with its tracker record) — so the next reader finds a decision,
not a default.

### The machinery is guarded once

These rules bind the shipping surface — grammar, checker, registries,
runtime, the adapter — and the rigor-critical machinery the
information-set guarantee rests on: the proof harness, the projections,
the encodings, the invariants. For those, completeness is measured against
the domain, as this whole section says.

Enforcement *scaffolding* — the pins, scrapes, hygiene tests, and audit
tooling built to hold the rules above — is a different case, and the
difference is load-bearing: every layer of guarding is itself a closed
domain, so applying this section to its own machinery recurses without a
base case, and each layer added is new surface for the next audit to find
wanting. The base case is: **scaffolding carries exactly one level of
guarding** — a grid's red run, a pin's `red under:` witness — and receives
no preemptive machinery of its own. A defect *in* scaffolding is fixed
when it bites (a finding it should have caught and did not), or in a named
integrity sweep with its own scope, and is filed with its reachability
stated — never as routine finding fodder. This is corpus-first applied to
the machine: the witness for meta-machinery is a failure, and waiting for
it is cheap because the shipping surface underneath is still guarded.

The test for which side something is on: if it fails silently, is a wrong
game trusted, or a wrong *audit* trusted? The first is rigor-critical.
The second is scaffolding.

The cap prices the process as well as the artifacts. A change wholly on
the scaffolding side of that test — no refusal, no runtime step, no proof
obligation changes — still ships its grid, but takes one review round and
no standalone adversarial claim-audit. The full cadence is reserved for
deltas a designer, the corpus, or a proof can meet. Scaffolding misjudged
is caught the way scaffolding is guarded: when it bites.

### Reachability ranks the work

Severity says what kind of defect; reachability says who can meet it.
Every finding, uncovered cell, and tracker issue states one:

- **R1 — corpus-reachable.** A game in `docs/games/` (or anything trained
  or proven against one) meets it today.
- **R2 — designer-reachable.** A checker-green sentence a designer could
  plausibly write meets it. The design-tool promise binds here: R2 silence
  is how a designer ships a wrong game. Plausible means a rule of some
  real game would be written that way, or the sentence is a slip away from
  one the corpus writes. Corpus use does not decide it: an accepted
  construct no corpus game writes is R2 when a game's rules would be
  written with it, because the corpus gates which mechanisms exist, not
  what a designer may write.
- **R3 — rarely reached.** Reaching it takes one of two things, and the
  `blocked:needs-witness` label says which:
  - **Accepted but unwritten.** A checker-green sentence that no game's
    rules ask for. Two shapes are typical: a member of a closed family
    kept whole for totality ("Surface totality", minimal and complete;
    the dead-surface report's `sibling` rows), and a combination of
    accepted constructs that only an exercise of the surface writes.
  - **Witness-gated.** Surface the language does not yet accept: a cell
    deferred behind a guard, lifted only when its named witness lands.
    These issues carry `blocked:needs-witness`.
- **R4 — auditor-only.** Reaching it requires planting a mutation,
  widening a registry, or editing the machinery itself.

The tags are exclusive by precedence: assign the lowest-numbered tag
whose condition holds — reachability names the *closest* party who can
meet the defect, never the typical one.

The tag names who can TRIGGER the defect, never who ultimately suffers
it. Every defect in a design tool eventually reaches a designer, so
transitive harm raises no tag — reasoned transitively, everything is R2
and the axis orders nothing. And the tag ranks reach, not worth: a
bitten R4 can sit at the top of the ordering while a speculative R2
waits, so R4 is a fact about who can meet the cell, never a demotion of
the work that closes it.

Disposition follows the tag: R1 is fixed now; R2 is fixed or filed with a
kind. An accepted-but-unwritten R3 is filed with a kind, ranks after R2,
and carries no Priority Tier unless the direction review gives it a
reason. When a game's rules turn out to write the sentence, it is
re-tagged R2, or R1 once a corpus game writes it. A witness-gated R3 is a
marked cell with its guard and its record, per the gate above. R4 is
recorded in the owning ledger and files an issue only when the guarded
guarantee is rigor-critical. And effort follows it the same way:
a fix whose size is out of proportion to its reachability routes to
record-and-file, not to fix-now — the proportionality call is made in
planning, out loud, not discovered in review.
