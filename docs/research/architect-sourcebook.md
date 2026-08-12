# The Architect's sourcebook

*Research annex for the Architect (issue #305; the seat's charter cites this book). Evidence file, not spec: the closing principles are proposals for the design-note distillation, and an **unverified** mark bars citation-as-established. Written 2026-08-08 against repo state ee62c43.*


## What this book is

The Architect is the design-counsel persona for this project: consulted when a
change touches the compiler's architecture, the type system, the diagnostics
doctrine, the language's evolution surface, the testing strategy, or the
observability model. This sourcebook is the persona's research annex — six
areas of literature, each read *against this repo's live questions*, not as a
general compiler-design survey. Every area answers three questions: what the
literature settles (results the Architect may cite as established), what it
warns (failure modes with named precedents), and where it touches this repo
(the issue numbers and `docs/decisions.md` sections the material bears on).

How the Architect cites it: by area and source — "the nanopass discipline
(Area 1, Sarkar et al. 2004)" — with the URL available here. A claim marked
**unverified** below was not confirmed against a primary source during the
research session and must not be cited as established; it may be cited as a
lead. The closing page lists candidate principles for the follow-up
design-note distillation; those are proposals, and this book is their
evidence file, not their authority.

The repo's live tensions this book is aimed at, for orientation:

- the coercions-not-subtyping stance meeting collection growth
  (issue #123; `cardlang/types.py`);
- the permissive top and its producer-raises containment
  (decisions.md, "`Any` means the top, never a failed lookup");
- the corpus-anchored-oracle gap (issues #271, #272, #273);
- the "accepted-but-ignored" and "wrong-channel failure" defect classes
  (decisions.md, "Surface totality" and "Closed-domain completeness");
- the seven-stage front-end smear and the Contract-block pass discipline
  (`docs/design-notes/kernel-extensibility.md`; `resolve.py` / `typecheck.py`
  docstrings);
- derived information sets as the moat, and its neighbors' answers
  (decisions.md, "Knowledge, visibility, and the projection model";
  `docs/design-notes/domain-map.md`).

---

## Area 1 — Pass architecture and IR design

### What the literature settles

**Many small passes beat few large ones, and the enabling condition is cheap,
declared intermediate languages.** The nanopass line (Sarkar, Waddell &
Dybvig, ICFP 2004) restructures a compiler as dozens of single-task passes,
each with a *formally declared* input and output language; the framework
generates the boilerplate traversal and checks that a pass's output conforms
to its declared grammar. The claimed benefits — understandability, testability
of each pass in isolation, and the ability to insert a pass without disturbing
neighbors — were later shown to survive commercial scale: Keep's dissertation
and the ICFP 2013 paper rebuilt Chez Scheme's backend as a nanopass compiler
with competitive performance, retiring the argument that the style is
academic-only. The load-bearing mechanism is not "small passes" as a slogan
but that the *language between passes is a checked artifact*: what a pass
establishes is representable, and a malformed intermediate program is caught
at the pass boundary rather than three passes later.

**IR facts are materialized, not re-derived.** In the nanopass style, when a
pass computes a fact downstream passes need (a classification, a type, an
expansion), the output language gains a slot for it, and downstream reads the
slot. Re-derivation downstream is treated as a design smell because the two
derivations drift. Multi-IR systems institutionalize the same point at larger
granularity: MLIR's design (Lattner et al., "MLIR: Scaling Compiler
Infrastructure for Domain Specific Computation", CGO 2021, arXiv:2002.11054 —
standard reference, not independently fetched this session) exists so that
each abstraction level can carry its own invariants and verifier rather than
encoding everything in one IR's conventions.

**IDE-grade front ends are a distinct architecture, settled by convergent
practice.** rust-analyzer's architecture document describes the now-standard
recipe: an error-tolerant parser over a lossless (full-fidelity) syntax tree,
with Roslyn-style red-green trees, and semantics computed on demand rather
than in a fixed batch pipeline; the document is explicit that rust-analyzer
is "to rustc what Roslyn is to the original C# compiler". Batch pipelines and
IDE pipelines are not the same artifact, and retrofitting the second onto the
first is the expensive path both ecosystems took.

**The expression-problem vocabulary for pipeline pain is standard.** Wadler's
1998 note defines the two-axis extension problem; Tarr, Ossher, Harrison &
Sutton (ICSE 1999, "N degrees of separation" — the repo cites it as the
"tyranny of the dominant decomposition"; standard reference, not fetched this
session) names the cost of decomposing by stage when features are cross-stage.
The tagless-final encoding (Carette, Kiselyov & Shan, JFP 2009 — standard
reference, cited in-repo) is the settled way to pick the "new cases cheap, new
operations expensive" horn, which `kernel-extensibility.md` already adopts
deliberately for round forms.

### What it warns

- **Prose contracts drift; declared languages do not.** Nanopass's whole bet
  is that a pass contract held only in documentation is unenforced. A
  docstring stating "downstream may not read types off the tree" is a
  convention; a grammar the framework checks is a guard. The warning applies
  with full force to any pipeline whose inter-pass contracts are prose.
- **Pass ordering and hidden coupling are the failure mode of many-pass
  systems.** Two passes that each hold their contract can still compose
  wrongly if an invariant is implicit (nanopass mitigates this by making the
  invariant part of the language definition). The repo's write-time triage —
  every check names its Owner Guard layer — is the same medicine applied
  manually.
- **A single rich IR accumulates "everything must know everything" pressure**;
  the MLIR line exists because one level of representation forced every
  analysis to confront every abstraction at once. For a seven-stage pipeline
  over one AST, the analogous pressure is each stage pattern-matching shapes
  it should not know exist.

### Where it touches this repo

- The `Contract` blocks in `cardlang/resolve.py` and `cardlang/typecheck.py`
  are hand-rolled nanopass contracts: "Assumes / Establishes / Now illegal" is
  exactly a pass's input language, output language, and the conformance
  predicate — held as prose plus Shadow Guards rather than as checked
  language definitions. The literature's pressure point: typecheck's own
  contract concedes the tension — types are ephemeral, "NOT written onto
  nodes", and "a downstream consumer that needs a type is a signal to
  materialize it in this pass, never to re-infer it there." Nanopass doctrine
  says the same thing, and adds: the moment of materialization is a language
  change, so make the intermediate language a checked artifact. The repo's
  stop-and-fix rule (CLAUDE.md; decisions.md "Closed-domain completeness",
  write-time triage) already treats re-derivation as the tell; the literature
  supplies the enforcement mechanism it currently lacks.
- The seven-stage smear (`kernel-extensibility.md` section 2) is the
  Tarr et al. diagnosis verbatim, and the note already cites it. The nanopass
  answer — make adding a pass or a form cheap by generating traversal
  boilerplate — is the front-end half `kernel-extensibility.md` names as
  undelivered ("the derivation/macro layer named there as separate future
  work"); Ludii's reflection-derived front end (Area 6) is the other
  existence proof.
- The planned LSP mode (memory: the permissive-top split resolution routes
  IDE recovery "through resolve-side recovery") will meet the batch-vs-IDE
  architecture split head-on; rust-analyzer's document is the map of what
  that costs.

### Sources

- Sarkar, Waddell, Dybvig, "A Nanopass Infrastructure for Compiler Education",
  ICFP 2004. https://www.cs.tufts.edu/comp/150FP/archive/kent-dybvig/nanopass.pdf
- Keep, Dybvig, "A Nanopass Framework for Commercial Compiler Development",
  ICFP 2013. https://www.cs.tufts.edu/comp/150FP/archive/icfp13.pdf
- Keep, dissertation (same title), Indiana University.
  https://andykeep.com/pubs/dissertation.pdf
- nanopass framework (Scheme/Racket implementations).
  https://github.com/nanopass/nanopass-framework-scheme
- rust-analyzer architecture document.
  https://rust-analyzer.github.io/book/contributing/architecture.html
- Wadler, "The Expression Problem", java-genericity list, 1998.
  https://homepages.inf.ed.ac.uk/wadler/papers/expression/expression.txt
- Tarr, Ossher, Harrison, Sutton, "N Degrees of Separation: Multi-Dimensional
  Separation of Concerns", ICSE 1999. (Standard reference; cited in-repo; not
  fetched this session.)
- Lattner et al., "MLIR", CGO 2021, arXiv:2002.11054. (Standard reference;
  not fetched this session.)
- Carette, Kiselyov, Shan, "Finally Tagless, Partially Evaluated", JFP 2009.
  (Standard reference; cited in-repo; not fetched this session.)

---

## Area 2 — Type-system engineering

### What the literature settles

**Gradual typing has a precise theory of the permissive top.** Siek & Taha
(Scheme Workshop 2006) define the dynamic type's interaction with static
types through *consistency*, a reflexive, symmetric, deliberately
non-transitive relation — non-transitivity is what stops `Any` from collapsing
the whole type lattice into one equivalence class. The "Refined Criteria for
Gradual Typing" paper (Siek, Vitousek, Cimini, Boyland, SNAPL 2015) settles
what a gradual system must guarantee (the gradual guarantee: removing
annotations never changes behavior except by removing errors). Wadler &
Findler's blame calculus (ESOP 2009) settles accountability at the
static/dynamic boundary: "well-typed programs can't be blamed" — when a
boundary check fails, the fault provably lies on the less-typed side. And
Takikawa et al. (POPL 2016) settled, negatively, the *cost* question for
sound gradual typing with runtime enforcement: fine-grained static/dynamic
boundaries produced 30x-100x slowdowns in Typed Racket.

**A top type does not have to launder errors, and the industrial systems
prove it two ways.** TypeScript 3.0 introduced `unknown` as "the type-safe
counterpart of `any`": everything is assignable *to* it, nothing is permitted
*on* it without narrowing — separating "I accept anything" from "I know
nothing", the two roles `any` had conflated. rustc separates the roles
differently: there is no permissive top at all, and the recovery type
`TyKind::Error` is constructible only with an `ErrorGuaranteed` token — a
value whose existence proves a diagnostic was already emitted. The dev guide
states the invariant plainly: the compiler should never produce the error
type "unless we know that an error has already been reported to the user",
because the error type's whole job is suppressing cascades. Both systems
agree on the principle: *the top for deliberate imprecision and the sink for
failed analysis must be distinguishable*, whichever one you build.

**Coercions and subtyping are formally interconvertible, and the price of the
coercion side is coherence.** Breazu-Tannen, Coquand, Gunter & Scedrov
("Inheritance as implicit coercion", Information & Computation 1991)
interpret subtyping *as* coercion functions and prove the obligation that
comes with it: because a program can typecheck by more than one derivation,
one must prove the meaning does not depend on which derivation (which
coercions, inserted where) was used. That coherence proof is the hidden
maintenance cost of every coercion added: it is global, not local to the new
coercion.

**Nominal vs structural is settled as "both, deliberately placed", not as a
war.** Malayeri & Aldrich (ECOOP 2008) integrate the two in one calculus and
catalog what each buys: nominal typing expresses design intent, supports
runtime tags and stable identity; structural typing buys unanticipated reuse
and compositionality. Their companion empirical study (ESOP 2009) found real
codebases contain latent structural patterns nominal-only systems force into
boilerplate. The practical synthesis (brands over structural types, nominal
kinds with structural read views) is the standard migration path.

### What it warns

- **`Any`-contamination is a real, studied failure mode**: one dynamic value
  silently exempts its whole downstream from checking. Gradual-typing
  literature accepts this *for values whose type genuinely cannot be known*
  and spends its machinery (consistency, blame) on keeping the boundary
  honest. What it does not license is the top as an error-recovery value —
  that is precisely what rustc's `ErrorGuaranteed` invariant exists to
  prevent.
- **Coercion sets grow badly.** Each new implicitly-convertible pair
  multiplies derivations; coherence must be re-argued; and context-dependent
  coercions ("readable as X here, not there") re-implement a subtype relation
  ad hoc at every consuming site. The literature's tell for "you have
  reinvented subsumption site-by-site" is exactly a fact that must be
  re-attached at every construction or rebuild site.
- **Runtime-checked soundness at fine-grained boundaries is a performance
  trap** (Takikawa) — relevant to any future design where the DSL's checked
  values cross into unchecked Python primitives per evaluation step rather
  than per compilation.

### Where it touches this repo

- **Issue #123 is this area's exact question.** `TCollection` carries `key`
  and `zone` facets on a structural type; every rebuild site must preserve
  them, and one already failed to (`unify` dropped both; pinned in
  `tests/test_let_typing.py`). The issue's own analysis — nominal kinds
  (`TZone`, `TMap<K,V>`) make preservation free and exhaustiveness forced,
  but demand a subtype-like "readable as `Collection<Card>`" relation the
  system deliberately lacks — is the Malayeri/Aldrich integration question
  plus the Breazu-Tannen coherence question. The literature's read: the three
  named triggers are sound waiting conditions, but trigger 2 (a second
  facet-preservation bug) is the coherence cost already being paid, and
  trigger 3 (per-kind *result* semantics) is where coercion-only stops
  scaling, because result types are where subsumption cannot be simulated by
  a boundary check. A "brand" design — nominal identity with a declared
  structural read view — is the literature's shape for keeping
  coercions-not-subtyping while making preservation free.
- **decisions.md "`Any` means the top, never a failed lookup" is
  independently confirmed doctrine.** The producer-raises discipline (closed
  registry miss raises in the compiler channel; environment miss raises; the
  permissive set is enumerated and pinned) is the same invariant as
  `ErrorGuaranteed`, enforced socially rather than by construction — rustc
  makes the error type *unconstructible* without the proof token, which is
  one rung higher on the repo's own enforcement ladder ("Prefer the guard you
  cannot need").
- **The rejected `TUnresolved` and the planned LSP mode** (memory:
  permissive-top split): batch compilation with producer-raises is coherent,
  but the IDE literature (rustc's error type + tainting; rust-analyzer's
  tolerant front end, Area 1) converged on a *distinguished error type with
  an emitted-diagnostic guarantee* precisely so analysis can continue past
  the first failure without laundering it as the top. When the LSP mode
  lands, this is the strongest documented pattern for it — resolve-side
  recovery alone reproduces half of it.
- `unify`'s docstring ("gradual all the way down, or it is just a top-level
  special case") matches the consistency relation's depth behavior in
  Siek & Taha; the repo's `Integer`-to-`Player`/`Team` assignability is a
  coercion in the Breazu-Tannen sense and inherits the coherence obligation
  as more contexts consume it (the player-literal choke point already
  centralizes it — the right mitigation).

### Sources

- Siek, Taha, "Gradual Typing for Functional Languages", Scheme Workshop
  2006. http://scheme2006.cs.uchicago.edu/13-siek.pdf
- Siek, Vitousek, Cimini, Boyland, "Refined Criteria for Gradual Typing",
  SNAPL 2015. https://drops.dagstuhl.de/storage/00lipics/lipics-vol032-snapl2015/LIPIcs.SNAPL.2015.274/LIPIcs.SNAPL.2015.274.pdf
- Wadler, Findler, "Well-Typed Programs Can't Be Blamed", ESOP 2009.
  https://users.cs.northwestern.edu/~robby/pubs/papers/esop2009-wf.pdf
- Takikawa, Feltey, Greenman, New, Vitek, Felleisen, "Is Sound Gradual Typing
  Dead?", POPL 2016. https://www2.ccs.neu.edu/racket/pubs/popl16-tfgnvf.pdf
- Breazu-Tannen, Coquand, Gunter, Scedrov, "Inheritance as Implicit
  Coercion", Information and Computation 93(1), 1991.
  https://www.sciencedirect.com/science/article/pii/0890540191900557
- Malayeri, Aldrich, "Integrating Nominal and Structural Subtyping", ECOOP
  2008. https://link.springer.com/chapter/10.1007/978-3-540-70592-5_12
- Malayeri, Aldrich, "Is Structural Subtyping Useful? An Empirical Study",
  ESOP 2009. http://www.cs.cmu.edu/~aldrich/papers/esop09.pdf
- TypeScript 3.0 release notes (`unknown`).
  https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-0.html
- rustc dev guide, "The ty module" (TyKind::Error, ErrorGuaranteed).
  https://rustc-dev-guide.rust-lang.org/ty.html

---

## Area 3 — Diagnostics engineering

### What the literature settles

**Error messages are a product surface, and the two acknowledged bars wrote
down how they got there.** Elm's "Compiler Errors for Humans" (Czaplicki,
2015) is the founding retrospective: treat the error message as UI; show the
relevant code with the problem located; name the actual values and types
involved rather than the internal machinery; suggest the likely fix; and
measure success by whether a user can act without leaving the terminal. The
rustc dev guide turned the same stance into enforceable house rules: messages
in plain simple English; errors point at the *smallest* span that signifies
the issue; "the word 'illegal' is illegal"; long explanations live behind an
error code (`--explain`), not in the message; and *suggestions* are
structured data with a machine-applicability flag so tooling can auto-apply
them. The research landscape report (Becker et al., ITiCSE WG 2019) surveys
fifty years of evidence that message quality measurably affects users,
especially novices — for a designer-facing DSL, the design-tool audience is
the novice case.

**Multiple errors per run is the settled UX, and it requires an
anti-cascade mechanism, not just a collection.** rustc's design is explicit:
after reporting a type error it produces the error type, which *propagates
and suppresses* downstream complaints — "the whole point of the Error type is
to suppress other errors" — under the `ErrorGuaranteed` invariant that
suppression is legal only because a diagnostic was already shown. Collecting
diagnostics without such a sink either stops at the first uncontinuable state
or floods the user with consequences of one mistake.

**Diagnostics are tested as snapshots plus annotations.** rustc's UI-test
system stores the compiler's rendered output (`.stderr`) beside each test,
regenerated deliberately via `--bless` and reviewed as a diff; inline
annotations assert that specific errors occur at specific lines. The
`ui_test` crate generalizes the harness. The settled points: (a) the *exact
rendering* is under test, not merely "an error occurred"; (b) regeneration is
an explicit, reviewed act, so message regressions are visible in diffs; (c)
tests minimize unrelated noise so snapshots stay reviewable.

### What it warns

- **"An error occurred" is a weak assertion.** A rejection test that checks
  only admit-vs-reject will hold while the message decays into something
  users cannot act on; the UI-test practice exists because message *content*
  regresses silently otherwise.
- **Wrong-layer loudness is a recognized defect shape**: a panic where a
  diagnostic belongs (rustc treats an ICE reached from bad user input as a
  bug per se), or a diagnostic so wide it points at the whole file. The
  smallest-span rule and the ICE-is-a-bug norm are the two guardrails.
- **Suggestions must know whether they are mechanical.** An unmarked
  suggestion gets auto-applied by tooling and silently changes meaning;
  rustc's applicability enum exists because this happened.
- **Cascade suppression can overshoot** — suppressing genuinely independent
  errors behind one taint. rustc bounds this by tying suppression to the
  error *value's* flow, not to "any error happened".

### Where it touches this repo

- The repo's diagnostic doctrine — `DiagnosticBag`, span plus
  designer-readable message, "on any error it raises with every diagnostic
  collected, not just the first" (`resolve.py`), and the wrong-channel rule
  ("a raw registry raise mid-resolve is loud in the wrong channel and
  suppresses every other diagnostic in the file", decisions.md
  "Closed-domain completeness") — is the settled practice. What the repo has
  that the literature lacks a name for is the *addressee* discipline
  (glossary section 5: every failure reported to its Author, in their
  vocabulary — game author, library author, engine maintainer); Elm gestures
  at it, the glossary states it as a rule. Worth keeping as a contribution,
  not an import.
- **Message-content testing: the mechanism exists in-house; the pressure is
  coverage.** The repo independently built the rustc-UI-test shape:
  `tests/test_rejections.py` holds `.cardlang`/`.expected` pairs, compares
  rendered diagnostics byte-for-byte, and regenerates deliberately under
  `REJECTIONS_BLESS=1` — that IS blessed-snapshot diagnostics testing, and
  any distillation that proposes building it would be duplicating a live
  mechanism. What the literature actually presses on is the corpus's
  *reach*: a diagnostic outside the rejection corpus has no message pin at
  all, and issue #133 records the resulting decay ("the grid asserts
  admit-vs-reject only, not the message text"; its message reads `unknown
  type '<name>'` where the sharper truth is "a position domain is not a
  declared type in this slot"). The concrete suggestion is a residual case
  in the existing corpus, not a new harness.
- The typecheck pass's continuation behavior after a reported error — what
  stands in for the error type so one bad expression does not cascade — is
  where the rustc suppression design bears directly; today `TAny`-as-
  propagation "downstream of a guard that already fired" plays this role and
  is enumerated in the audited permissive set (decisions.md "`Any` means the
  top..."), which is the ErrorGuaranteed invariant carried socially (see
  Area 2).

### Sources

- Czaplicki, "Compiler Errors for Humans", 2015.
  https://elm-lang.org/news/compiler-errors-for-humans
- rustc dev guide, "Errors and Lints" (message and span guidelines,
  suggestions, applicability). https://rustc-dev-guide.rust-lang.org/diagnostics.html
- rustc dev guide, UI tests (snapshots, `--bless`, annotations).
  https://rustc-dev-guide.rust-lang.org/tests/ui.html
- oli-obk, `ui_test` (generalized diagnostics-snapshot harness).
  https://github.com/oli-obk/ui_test
- Becker et al., "Compiler Error Messages Considered Unhelpful: The Landscape
  of Text-Based Programming Error Message Research", ITiCSE WG 2019.
  https://dl.acm.org/doi/10.1145/3344429.3372508 (PDF:
  https://www.brettbecker.com/wp-content/uploads/2019/12/becker2019compiler.pdf)
- rustc dev guide, "The ty module" (error-type suppression).
  https://rustc-dev-guide.rust-lang.org/ty.html

---

## Area 4 — External-DSL evolution

### What the literature settles

**Stability is a published contract, and the two industrial poles are
written down.** Go's "Go 1 and the Future of Go Programs" promises that
conforming programs "continue to compile and run correctly, unchanged" for
the lifetime of the spec, and the 2023 follow-up commits to "never" a
breaking Go 2 — evolution happens by addition only. Rust's editions (RFC
2052) are the engineered middle: breakage (new keywords included) is
*opt-in per crate*, editions interoperate within one ecosystem ("editions are
never allowed to split the ecosystem"), and migrations ship with automated
fixes. The settled lesson is not either policy but the shape both share: the
evolution rules are themselves a designed, documented surface, decided before
the pressure arrives.

**Grammars are engineering artifacts with lifecycles.** Klint, Lämmel &
Verhoef ("Toward an Engineering Discipline for Grammarware", TOSEM 2005)
establish that grammars and all grammar-dependent software need the same
discipline as code: versioning, testing, transformation tooling, and above
all a single authoritative grammar from which dependent artifacts derive —
because scattered, hand-copied grammar knowledge drifts. That is the
literature's frame for parser pragmatics too: Lark's own documentation
settles the mechanics this repo lives with — the contextual lexer narrows
terminal choice by parser state (LALR), the Earley `dynamic`/
`dynamic_complete` lexers consider every possible match, terminal collisions
resolve by explicit priority then match length, and "it is the
grammar-author's responsibility to make sure the literals don't collide, or
that if they do, they are matched in the desired order." Keyword-vs-identifier
anchoring is, per the primary source, the author's problem, permanently.

**Growth is a design axis, not an accident.** Steele's "Growing a Language"
(OOPSLA 1998) settles the direction: a language succeeds by being growable by
its users, with the maintainer coordinating rather than personally authoring
each addition — the argument `kernel-extensibility.md` already leans on. And
Hyrum's Law (hyrumslaw.com — informal but universally cited) names the
constraint on any observable behavior: with enough users, everything
observable becomes depended-upon, whether promised or not.

### What it warns

- **The "accepted-but-ignored" class is how external DSLs rot.** A construct
  that parses and does nothing is indistinguishable, to an author, from a
  working one; when a later version implements it, existing documents change
  meaning silently. The grammarware program's core warning is exactly this
  drift between the grammar's promise and the implementation's behavior; the
  repo has independently named the class and made it a defect
  ("Surface totality"). Nothing in the literature contradicts the repo here;
  the literature mostly documents the cost of *not* having the rule.
- **Keyword additions are the canonical breaking change** — Rust's editions
  were motivated in part by "superficial breakage such as adding new
  keywords". A DSL whose keywords are English words (this one's whole
  aesthetic) faces this maximally; a dynamic lexer defers the collision from
  lex time to parse time but does not delete it.
- **Deprecation without automated migration is churn.** Editions work because
  `cargo fix` exists; a deprecation policy for an external DSL with no
  rewriter is a demand that every document owner do compiler work by hand.
- **The versionless honeymoon ends the day a document lives outside the
  repo.** Lockstep evolution (change the language, fix every program in the
  same commit) is only possible while the language owner owns every program.

### Where it touches this repo

- The repo currently runs the pure lockstep model: "Games are the living
  embodiment of the spec... a game file that uses obsolete syntax is a bug"
  (CLAUDE.md operating rule 2), spec-not-history editing, no version marker
  in game files, no deprecation stage. Against a closed in-repo corpus this
  is the correct minimal policy, and Go/Rust practice does not say otherwise.
  The literature's pressure is a *timing* warning: the public repo (public
  since 2026-08-06) plus the design-tool ambition means external `.cardlang`
  documents are now possible, and every policy above (editions, migration
  tooling, Hyrum's Law) is cheapest to decide before the first external
  document exists. A one-line `language:` header in game files, reserved now
  and ignored, is the classic cheap option — noted here as literature-shaped
  counsel, not spec.
- The keyword-anchoring work (memory: #223/#101; `tests/keyword_fusion_sweep.py`
  as the runnable oracle; "grammar-text scrapes must follow `_<WORD>_KW`") is
  the grammarware program in miniature: one authoritative grammar, derived
  scrapes, and a pin on the derivation. Lark's documentation confirms the
  hazard is permanent and author-owned, so the sweep is load-bearing, not
  scaffolding.
- Family libraries (issue #137: libraries cannot hold phases or zones;
  procedures do not compose — "expansion is a single splice, not a call
  graph") is a language-evolution question the modularity literature frames:
  a module tier whose composition operator cannot nest sets a ceiling on
  sharing, and the issue's own mechanism-of-arrival note (shared material two
  procedure-calls deep has nowhere to go) is the forcing shape to watch.
- Surface totality's third state ("grammatically inexpressible") plus the
  guards ledger (`roadmap.md`) is a *reserved-syntax registry* in evolution
  terms — the same instrument Rust uses when it reserves keywords in a new
  edition ahead of features.

### Sources

- Go, "Go 1 and the Future of Go Programs". https://go.dev/doc/go1compat
- Go blog, "Backward Compatibility, Go 1.21, and Go 2".
  https://go.dev/blog/compat
- Rust RFC 2052, "Epochs" (editions).
  https://rust-lang.github.io/rfcs/2052-epochs.html
- Klint, Lämmel, Verhoef, "Toward an Engineering Discipline for Grammarware",
  TOSEM 14(3), 2005. https://dl.acm.org/doi/10.1145/1072997.1073000 (PDF:
  https://www.cs.vu.nl/grammarware/agenda/paper.pdf)
- Lark documentation, "Parsers" (contextual and dynamic lexers) and "Grammar
  Reference" (terminal priority, collision responsibility).
  https://lark-parser.readthedocs.io/en/stable/parsers.html ,
  https://lark-parser.readthedocs.io/en/stable/grammar.html
- Steele, "Growing a Language", OOPSLA 1998 keynote (video/transcript).
  https://archive.org/details/GrowingALanguageByGuySteeleAhvzDzKdB0
- Hyrum's Law. https://www.hyrumslaw.com (informal source, widely cited).
- Fowler, "Domain-Specific Languages", 2010 — external-DSL practice
  reference. https://martinfowler.com/books/dsl.html (book; not fetched this
  session).

---

## Area 5 — Compiler testing

### What the literature settles

**Differential testing is the founding oracle for languages, and its
precondition is a second interpretation.** McKeeman ("Differential Testing
for Software", Digital Technical Journal, 1998) names the method: feed the
same input to multiple implementations and let disagreement be the oracle.
Csmith (Yang, Chen, Eide, Regehr, PLDI 2011) industrialized it — 325+
previously unknown bugs across every C compiler tested, with the enabling
insight that generated programs must *avoid undefined behavior by
construction* or the oracle dissolves. YARPGen (Livinskii, Babokin, Regehr,
OOPSLA 2020) added generation *policies* — deliberately skewing generation to
reach optimizer-relevant shapes — and found 220+ more, establishing that
uniform random generation under-reaches and that generators need aimed
diversity.

**Metamorphic testing removes the need for a second implementation.** EMI
(Le, Afshari, Su, PLDI 2014) is the compiler-shaped instance: derive variants
of a program that are equivalent *modulo the profiled inputs* (prune
unexecuted code), then require identical behavior — the program becomes its
own oracle, and the method specifically reaches silent miscompilation. The
metamorphic survey (Chen et al., ACM Computing Surveys 2018) generalizes:
the asset is a *metamorphic relation* — a property connecting outputs across
transformed inputs — and relation choice, not volume, determines what a suite
can see. The oracle survey (Barr, Harman, McMinn, Shahbaz, Yoo, TSE 2015)
supplies the taxonomy: specified oracles, derived oracles (differential,
metamorphic), and implicit oracles (crashes, hangs), with the explicit
warning that derived oracles inherit the blind spots of what they derive
from.

**Coverage-guided grammar fuzzing closes the reach gap between random
generation and structure.** Nautilus (Aschermann, Frassetto, Holz, NDSS 2019)
combines grammar-based generation with coverage feedback so the corpus of
generated inputs migrates toward unexplored behavior — the settled mechanism
for finding shapes no hand-chosen witness anticipated.

### What it warns

- **Every oracle sees only what its generator can reach.** Csmith's authors
  bounded their claims to "a large subset of C"; YARPGen exists because even
  a good generator's default distribution misses whole optimization classes
  until policies aim it. Translated: a test corpus anchored to existing
  programs can, structurally, only find defects in shapes those programs
  contain.
- **A derived oracle that shares code with the system under test is a
  tautology.** The oracle literature is blunt that the value of a
  differential or restated-invariant oracle is its independence; an
  invariant computed by calling the implementation's own helper asserts the
  code equals itself.
- **Unvalidated oracles rot green.** The practice (and this repo's doctrine)
  answer is fault injection: an oracle is trusted only after it has caught a
  planted defect.
- **Triage and reduction are half the cost** of any fuzzing program (the
  Csmith project spent years on bug reporting workflow; C-Reduce — Regehr
  et al., PLDI 2012, standard reference, not fetched this session — exists
  because raw findings are unusable). A DSL fuzzer without a reduction story
  produces findings nobody can afford to read.

### Where it touches this repo

- **Issues #271, #272, #273 are this area's live edge, and the literature is
  squarely on their side.** #273's diagnosis — metamorphic transforms of
  corpus games and differentials against native implementations "can only
  find defects in shapes the corpus already contains," proven by four mode
  defects in shapes no corpus game has — is the generator-reach warning
  above, observed independently. The proposed third form ("generated +
  restated invariant": enumerate small mode graphs / phase trees, render to
  `.cardlang`, compare runtime behavior against an independently computed
  invariant) is precisely the Csmith/EMI move scaled to an enumerable domain,
  with #271/#272's two stated failure modes (never call the implementation's
  own helper; redden before trusting) matching the oracle-independence and
  oracle-validation warnings verbatim. The literature also endorses #273's
  own gating: EMI and Csmith earned their doctrine by finding bugs first.
- The existing suite maps cleanly onto the taxonomy: T1 pairing harness,
  T2 rename, T3 inline, T5 reorder (`tests/metamorphic/`;
  `docs/design-notes/metamorphic-suite.md` — T4 suit-relabel deferred, issue
  #127) are metamorphic relations over corpus programs; `tests/native_oracle.py`
  plus GOPS/Breakthrough/tic-tac-toe are differential; the goldens are
  regression pins, not oracles. CLAUDE.md's "Execution finds what enumeration
  cannot" is the Barr et al. position stated as doctrine.
- The memory note "solved games as instruments" (build the solved miniature
  first, so a harness bug is a *contradiction* rather than a plausible
  number) is a specified-oracle strategy the literature would classify but
  did not invent — Kuhn poker's known equilibrium value is a specification.
  Worth writing up; it is this repo's most exportable testing idea.
- When #271's enumerated mode graphs are built, Nautilus's lesson applies at
  the margin: if the enumerable domain ever stops being exhaustively
  enumerable (N grows), coverage-guided generation over the grammar is the
  continuation, and `docs/design-notes/grammar-fuzzing.md` already reserves
  the slot.

### Sources

- McKeeman, "Differential Testing for Software", Digital Technical Journal
  10(1), 1998. https://www.semanticscholar.org/paper/fc881e8d0432ea8e4dd5fda4979243cac5e4b9e3
- Yang, Chen, Eide, Regehr, "Finding and Understanding Bugs in C Compilers",
  PLDI 2011. https://users.cs.utah.edu/~regehr/papers/pldi11-preprint.pdf
- Le, Afshari, Su, "Compiler Validation via Equivalence Modulo Inputs", PLDI
  2014. https://web.cs.ucdavis.edu/~su/publications/emi.pdf (project page:
  https://web.cs.ucdavis.edu/~su/emi-project/)
- Livinskii, Babokin, Regehr, "Random Testing for C and C++ Compilers with
  YARPGen", OOPSLA 2020. https://users.cs.utah.edu/~regehr/yarpgen-oopsla20.pdf
- Aschermann, Frassetto, Holz et al., "NAUTILUS: Fishing for Deep Bugs with
  Grammars", NDSS 2019. https://wcventure.github.io/FuzzingPaper/Paper/NDSS19_Nautilus.pdf
- Chen et al., "Metamorphic Testing: A Review of Challenges and
  Opportunities", ACM Computing Surveys 51(1), 2018.
  https://dl.acm.org/doi/10.1145/3143561
- Barr, Harman, McMinn, Shahbaz, Yoo, "The Oracle Problem in Software
  Testing: A Survey", IEEE TSE 41(5), 2015.
  https://discovery.ucl.ac.uk/1471263/
- Regehr et al., "Test-Case Reduction for C Compiler Bugs" (C-Reduce), PLDI
  2012. (Standard reference; not fetched this session.)

---

## Area 6 — Game-description-language neighbors

*The closest literature: these systems already fought this repo's hardest
problem. Ordered by what each contributes to the observability question.*

### What the literature settles

**GDL-II settles that information sets can be derived from a declarative
spec, and it is this repo's direct ancestor.** Thielscher ("A General Game
Description Language for Incomplete Information Games", AAAI 2010) extends
GDL with exactly two constructs — the `random` role and the `sees(?r, ?p)`
relation, "role ?r perceives ?p in the next game state" — and that suffices:
the follow-up ("The General Game Playing Description Language Is Universal",
IJCAI 2011) proves GDL-II can describe *any* finite extensive-form game,
imperfect information included. A player's information set is not authored
anywhere; it falls out of the percept stream the `sees` clauses generate.
This is the formal license for the repo's whole bet.

**GDL-III settles where the knowledge-model ceiling is.** Thielscher
("GDL-III: A Description Language for Epistemic General Game Playing", IJCAI
2017) adds a single knowledge keyword so *rules* can depend on what players
know — epistemic games (Hanabi-like truthfulness conditions, knowledge-based
termination) need it; everything below that line does not. The repo's
"higher-order knowledge is out of scope... no card game's rules read it"
(decisions.md) has a named literature successor waiting if a rule ever does.

**The observation-first reformulation of game theory validates the
projection model.** The factored-observation line (Kovařík, Lisý and
colleagues: "Problems with the EFG formalism: a solution attempt using
observations", arXiv 1906.06291; developed into factored-observation
stochastic games in Kovařík, Schmid, Burch, Bowling, Lisý, "Rethinking Formal
Models of Partially Observable Multiagent Decision Making", Artificial
Intelligence 2022) argues the classical
extensive-form formalism obscures exactly what algorithms need, and rebuild
the model on *factored observations distinguishing private and public* — the
theory-side Shadow Guard of this repo's projection lattice and its
public/private/semi-private event taxonomy (decisions.md, "Formal
distinctions"). OpenSpiel itself encodes the practice: `spiel.h` requires
"the information state should be perfect-recall, i.e. if two states have a
different InformationState, then all successors of one must have a different
InformationState to all successors of the other," and demands that when both
are implemented, information state and observation "must be consistent for
all the players (even the non-acting player(s))." The repo's glossary
distinction (information state = the per-player artifact; information set =
the equivalence class it induces) matches the source.

**Ludii settles that the front-end tax is a tooling choice.** The ludemic
system (Piette, Soemers, Stephenson, Sironi, Winands, Browne, "Ludii — The
Ludemic General Game System", ECAI 2020; Browne's class-grammar design, ACG
2016 — standard reference, not fetched this session) derives its game
grammar *from the Java class hierarchy by reflection*: adding a ludeme class
extends the language, and the parse/validate/compile pipeline is generated,
never hand-edited. One thousand-plus games ship on it. This is the standing
existence proof, already cited by `kernel-extensibility.md`, that a
per-construct grammar-through-typecheck edit is not a law of nature.

**RBG settles that formal-semantics-first is viable — by paying for it with
scope.** Regular Boardgames (Kowalski, Mika, Sutowicz, Szykuła, AAAI 2019)
describes moves as regular expressions over board primitives, achieves
efficiency the logic-programming GDL line could not, and states its
universality claim precisely: "universal for the class of all finite
deterministic turn-based games with perfect information." Hidden information
is simply outside the language.

### What it warns

- **GDL-II's `sees` clauses are per-rule, hand-authored emissions — and that
  is its documented weakness for this repo's purposes.** Nothing in GDL-II
  checks that a game's `sees` clauses are complete or consistent with
  intent; an author who forgets a percept has silently changed the game's
  information structure, and no tool objects. The repo's move — visibility
  declared once per zone *type* in a closed registry, observation events
  emitted uniformly by the kernel, "no per-game observation rules"
  (CLAUDE.md) — is a direct response to this failure mode, and the
  generalization-path proposal for *user-declared computed projections*
  (axis 2) walks deliberately back toward GDL-II's expressiveness; it should
  import the lesson (pure, declared, kernel-emitted) explicitly. GDL-II
  reasoning cost is the second warning: knowledge queries over the percept
  stream are expensive (Schiffel, Thielscher, "Reasoning About General Games
  Described in GDL-II", AAAI 2011), which is why deriving *candidate sets*
  eagerly, as this repo does, rather than reasoning lazily over logs, is the
  performing choice.
- **Ludii's derivation puts semantics in the implementation.** A ludeme means
  what its Java class does; the grammar is generated from code, so there is
  no independent spec against which "accepted-but-ignored" could even be
  defined — the class *is* the definition. The benchmark dispute with RBG
  (Kowalski et al., "A note on the empirical comparison of RBG and Ludii",
  arXiv 1910.00309) is a symptom worth remembering: claims about such
  systems are hard to adjudicate exactly where behavior is defined by
  implementation. Ludii's later universality argument (Piette, Soemers,
  Stephenson, Browne, "The Ludii Game Description Language is Universal",
  arXiv 2205.00451) responds on expressiveness — cited here for the
  expressiveness point only; its observability treatment was not examined
  this session (**unverified** beyond the abstract).
- **OpenSpiel's own games hand-author their observers.** Every C++ game
  implements `InformationStateString`/observation tensors by hand against
  the comment-level contract above, and consistency is enforced by tests,
  not by construction. That is the practice this repo's general adapter
  refuses — and the refusal is the moat. The warning runs the other way too:
  the perfect-recall contract quoted above is *the* correctness obligation
  the adapter must keep proving as forms are added; OpenSpiel gives it one
  sentence and a test harness, this repo gives it a proof battery
  (`tests/openspiel_ready/`), and the delta is the defensible contribution.
- **Simultaneity is where every neighbor's model creaks.** GDL is
  synchronous-by-construction (turn-taking is encoded with no-ops); OpenSpiel
  carries a distinct simultaneous node kind; this repo is sequential-first
  with `EachSimultaneous` as a separate construct and
  sequentialize-with-concealment named as the info-set-equivalent transform
  (generalization-path section 5). The literature's lesson is that neither
  pole is free and the transform between them is the asset worth testing.

### Where it touches this repo

- decisions.md "Knowledge, visibility, and the projection model" — GDL-II is
  the ancestor (the repo says so); the projection lattice plus uniform
  emission is the repair of GDL-II's authored-`sees` weakness; GDL-III is
  the named reopener for knowledge-reading rules; FOSG is the theory to cite
  for the public/private factoring already in the spec.
- `docs/design-notes/kernel-extensibility.md` section 3 — the GDL-vs-Ludii
  fork is already correctly drawn there; this area adds RBG as the third
  reference point (formal core, scope sacrifice) and the warning labels
  above.
- `docs/open-questions/structural-infoset-proofs.md` — the swap-proof
  battery is ahead of every neighbor; the FOSG formalization is the natural
  target language for a *structural* proof, since it defines information
  states directly from observation sequences.
- Issue #123 sits downstream of this area too: `TZone` and per-kind result
  semantics will be forced fastest by the topology/pose axes
  (generalization-path axes 1-2), which is where Ludii's and RBG's
  board-first designs are the prior art to raid for query-surface shape.
- The Interop glossary translation table (glossary section 4) and the
  seed-at-root chance design map one-to-one onto OpenSpiel's documented node
  kinds; the perfect-recall sentence from `spiel.h` is the external statement
  of the pin `tests/openspiel_ready/` proves per game.

### Sources

- Thielscher, "A General Game Description Language for Incomplete
  Information Games", AAAI 2010.
  https://cdn.aaai.org/ojs/7647/7647-13-11177-1-2-20201228.pdf
- Thielscher, "The General Game Playing Description Language Is Universal",
  IJCAI 2011. https://www.ijcai.org/Proceedings/11/Papers/189.pdf
- Thielscher, "GDL-III: A Description Language for Epistemic General Game
  Playing", IJCAI 2017. https://www.ijcai.org/proceedings/2017/0177.pdf
- Schiffel, Thielscher, "Reasoning About General Games Described in GDL-II",
  AAAI 2011. https://cdn.aaai.org/ojs/7944/7944-13-11472-1-2-20201228.pdf
- Piette, Soemers, Stephenson, Sironi, Winands, Browne, "Ludii — The Ludemic
  General Game System", ECAI 2020 (arXiv 1905.05013).
  https://arxiv.org/abs/1905.05013 ; https://ludii.games/publications/ECAI2020.pdf
- Browne, "A Class Grammar for General Games", ACG 2016. (Standard
  reference; cited in-repo; not fetched this session.)
- Kowalski, Mika, Sutowicz, Szykuła, "Regular Boardgames", AAAI 2019.
  https://ojs.aaai.org/index.php/AAAI/article/view/3991
- Kowalski et al., "A note on the empirical comparison of RBG and Ludii",
  arXiv 1910.00309. https://arxiv.org/pdf/1910.00309
- Piette, Soemers, Stephenson, Browne, "The Ludii Game Description Language
  is Universal", arXiv 2205.00451. https://arxiv.org/pdf/2205.00451
  (abstract-level citation; **unverified** in detail)
- Kovařík, Lisý et al., "Problems with the EFG formalism: a solution attempt
  using observations", arXiv 1906.06291 (exact author list **unverified**
  this session). https://arxiv.org/pdf/1906.06291
- Kovařík, Schmid, Burch, Bowling, Lisý, "Rethinking Formal Models of
  Partially Observable Multiagent Decision Making", Artificial Intelligence
  2022 (the FOSG paper; standard reference, not fetched this session).
- OpenSpiel: Lanctot et al., "OpenSpiel: A Framework for Reinforcement
  Learning in Games", arXiv 1908.09453 (standard reference); `spiel.h`
  information-state contract (quoted above):
  https://raw.githubusercontent.com/google-deepmind/open_spiel/master/open_spiel/spiel.h ;
  API reference: https://openspiel.readthedocs.io/en/latest/api_reference/state_information_state_tensor.html

---

## Candidate principles for the distillation

The statements the follow-up design-note might assert, each tagged with the
area(s) whose evidence carries it. Proposals, not spec.

1. **A pass contract that matters is a checked artifact, not a docstring.**
   Where a Contract block's "Establishes" clause can be stated as a predicate
   over the tree, pin it with a test that walks the pass's output. (Area 1)
2. **When downstream re-derives, the IR is missing a slot.** Materializing a
   fact an earlier pass established is a language change; make it in the
   owning pass, never at the consuming site. (Area 1; already repo doctrine —
   the distillation should cite nanopass as its external confirmation.)
3. **The permissive top and the failed lookup must be distinguishable by
   construction, not by discipline.** The strongest known form is rustc's:
   the recovery value is unconstructible without proof a diagnostic was
   emitted. The audited-permissive-set pin is the current, weaker rung;
   record the rung choice. (Areas 2, 3)
4. **Every coercion is a coherence debt.** A value "readable as" another type
   at N consuming sites is a subtype relation implemented N times; when N
   grows or result types (not just legality) depend on the kind, promote to a
   nominal kind with a declared read view. This is issue #123's trigger 3,
   generalized. (Area 2)
5. **An IDE mode is a second architecture, not a flag on the first.**
   Error-tolerant parsing, a lossless tree, and a tainted error type are its
   known load-bearing parts; resolve-side recovery alone is half a pattern.
   (Areas 1, 2, 3)
6. **A rejection test that does not pin the message tests half the
   diagnostic.** Blessed-snapshot testing of rendered diagnostics is the
   settled practice; adopt it the first time a message-quality residual (of
   which #133 is one) is promoted to work. (Area 3)
7. **The failure channel is addressee, span, and applicability.** A diagnostic
   names its Author, points at the smallest span that signifies, and marks
   any suggestion as mechanical or not before tooling may apply it.
   (Area 3; extends existing doctrine with the applicability flag.)
8. **Decide the evolution contract before the first external document
   exists.** Lockstep corpus editing is correct until a `.cardlang` file
   lives outside the repo. Any reservation is by REJECTION, never by
   ignoring: a version header, if reserved, parses and statically rejects
   every value but the current version — an accepted-but-ignored header is
   exactly the silent trap "Surface totality" names, and this book may not
   recommend one. (Area 4; the reservation-by-guard pattern is already house
   practice.)
9. **The grammar is the single source; every scrape of it is derived and
   pinned.** Keyword-identifier collision is permanently the grammar
   author's problem under a dynamic lexer; the fusion sweep is shipping
   surface, not scaffolding. (Area 4)
10. **An oracle reaches only what its generator reaches; anchor at least one
    generator to the grammar, not the corpus.** Enumerate where the domain is
    enumerable; go coverage-guided when it stops being. (Area 5; #271-#273's
    thesis with the literature behind it.)
11. **An oracle is trusted only after it has caught a planted fault, and it
    never calls the code it judges.** Redden-before-trust and
    oracle-independence are the two admission tests for any new proof
    machinery. (Area 5; already repo doctrine — cite the oracle survey.)
12. **A solved game is a specified oracle.** Prefer a miniature with a known
    value as the first witness for any new mechanism; only a solved game
    turns a harness bug into a contradiction. (Area 5; this repo's own
    exportable idea.)
13. **Declared-once, emitted-uniformly is the repair of GDL-II; keep it under
    every extension.** Any new expressiveness for observation (computed
    projections, attribute-level visibility, `announce`) must stay a pure
    declared function emitted by the kernel — never a per-game emission
    site. (Area 6; generalization-path axis 2's guardrail, with its
    ancestry named.)
14. **The perfect-recall contract is the export invariant; prove it, never
    assume it.** OpenSpiel states it in a comment and checks it in tests;
    this repo's proof battery is the differentiator and must extend to every
    new form and node kind (simultaneity included) as a condition of
    admission. (Area 6)
15. **When a rule must read knowledge, that is GDL-III territory — a model
    change, not a feature.** The first-order candidate-set model has a named
    ceiling; crossing it is a moat-level event per the domain map's
    stillness test, with the literature's successor system as the reference
    point. (Area 6)

*End of draft.*
