# Card Game DSL

A domain-specific language for describing card games played with standard
52-card decks (plus jokers). Target runtime: OpenSpiel, so existing
imperfect-information AI algorithms work on the resulting games.

This file orients agents working on the project. The design lives in `docs/`;
read this file first to know where to look.

## OpenSpiel is the target, and deriving information sets is the hard part (load-bearing)

**OpenSpiel is the invariant output target, not a "later" concern.** Every game
must ultimately compile to OpenSpiel so imperfect-information AI (IS-MCTS, CFR,
deep RL, determinization) works out of the box. That is why the language exists,
and it bounds every design choice *now*: a construct that cannot compile to
OpenSpiel with correct information sets is not done, however cleanly it runs.

**The hardest requirement is that information sets are *derived*, never
hand-authored.** A player's information set must fall out of zone visibility plus
the observation events that moves emit — the GDL-II `sees` semantics made
operational (`docs/decisions.md`, "Knowledge, visibility, and the projection
model"; `docs/principles.md`, "Visibility as a first-class property"). Derived
info sets are the *whole reason* this DSL is worth more than hand-coding each game
against OpenSpiel directly. For hidden hands, face-down cards, bluffs, and
concealed bids this is genuinely hard — and it is exactly where the value is.

**Honest status — the stable invariant, and where the evolving line lives.**
Every corpus game is fully kernel: all games reach OpenSpiel through ONE
general adapter with *derived* information sets — per-observer observations
emitted from the kernel's decision/movement sites through the declared
zone-type projections — proven per game by `tests/openspiel_ready/` (one
proof module per game over a shared harness: indistinguishability with
legal-action agreement, the per-visible-fact soundness matrix, a seed/rng
non-observability pin, adapter agreement, perfect recall; per-game caveats
and rationale live in the proof modules themselves). No per-game
observation rules, no Python escape-hatch mechanic (the `instantiate`
construct is deleted), no per-game branch outside the Primitive
registries. **The evolving honesty line is tracked in two named places,
not here:** `docs/kernel-migration.md` (workstream status and remaining
scope reductions) and `docs/open-questions/structural-infoset-proofs.md`
(proof-coverage caveats and the standing partition caveats). Consult both
before making any completeness claim, and update them in the same change
that alters status.

**So, for every change, treat info-set derivation as a first-class acceptance
criterion** — alongside "does it run" and "is it byte-identical":

- Prefer the kernel path (the `round` forms; the decision-interpreter direction in
  `docs/design-notes/kernel-extensibility.md`) over adding a new Python escape
  hatch. The kernel can emit uniform observation events that *derive* info sets; a
  bespoke Python mechanic cannot.
- When an escape hatch is genuinely unavoidable, record it as **info-set debt** in
  `docs/kernel-migration.md`, not as a finished mechanic.
- A feature that runs but emits no observations from which its info sets derive is
  *incomplete* for the OpenSpiel target. Say so; don't let it read as done.
- New or extended grammar surface must be **total**: every combination the grammar
  accepts is implemented + tested, or statically rejected with a clear message —
  never parsed and silently ignored ("accepted-but-ignored" is a defect class, the
  worst failure mode for a designer tool). Corpus-first gates *which* constructs
  exist, not how completely one works. The rule and the enumeration recipe are in
  `docs/decisions.md`, "Surface totality".
- The same principle governs the machinery below the grammar: foundational
  code (proof harness, projections, encodings, invariants) is complete
  against **its own domain**, never against the corpus — closed enumerable
  domains get exhaustive coverage derived from their defining registry,
  pinned by a static test and a runtime refusal; open design spaces stay
  corpus-first but every deferral is a loud guard. "Vacuously green" — a
  check presented as a guarantee that cannot fail — is a defect class of
  equal rank to "accepted-but-ignored". Changes to rigor-critical machinery
  ship with their completeness argument (property, domain, registry, and
  what a green does not prove). When a gap is found, sweep its whole class (the other members
  of the same closed domain) before patching the instance. The rule is
  `docs/decisions.md`, "Closed-domain completeness".
- **Stop-and-fix at write time.** Two tells mean you are losing information,
  not defending it: (a) you are re-deriving a fact an earlier pass already
  established (a `ref_kind` the resolver stamped, a type the checker
  validated, a projection `ZONE_PROJECTIONS` declares), or (b) you are adding
  a guard for a condition already checked in another file. On either tell,
  STOP — the fix is upstream, never the local edit. Triage the check as
  **Owner Guard / Shadow Guard / missing Owner Guard** before it lands, per
  `docs/decisions.md`, "Closed-domain completeness" (write-time triage): an
  Owner Guard moves to the layer that owns the class; a Shadow Guard's comment
  names the Owner Guard it shadows; a
  guard that can't say which it is doesn't land. Every pass states what it
  assumes, what it establishes, and what becomes illegal after it in the
  `Contract` block of its module docstring — read the owning pass's contract
  before placing a check.

**Execution finds what enumeration cannot.** Every silent-wrong-answer
and wrong-semantics defect this project has found came from an execution
oracle — building a game, a differential against a native implementation,
a metamorphic transform, an instrumented run — and none from inspection,
the audits included. Enumeration proves the domain is covered; only
execution can show the domain was the wrong one, or an assumption inside
a total enumeration was false. So when a choice exists between building
enforcement machinery and building a witness — a game, a differential, a
playout policy that reaches unexercised branches — build the witness.
Implemented-but-never-executed code is where the next silent defect is
already sitting.

## What's here

```
docs/
  principles.md          High-level goal, design principles, architectural principles
  model.md               Primitives + phase/state/move-type/rule relationship
  library.md             The Trick mechanic + standard library catalogue
  decisions.md           Settled design decisions (the load-bearing spec)
  glossary.md            The shared language: what each thing is called, what each name may mean
  roadmap.md             Out-of-scope list + the checker's guards ledger
  implementation.md      Plan for building the parser + static checker (tooling)
  building.md            Front-end execution blueprint (pipeline, triage, gates)
  kernel-migration.md    Stage plan: remove per-game Python mechanics → DSL kernel
  harness.md             The Operating Harness: Merge Lanes, the work graph, Leases, Standing Roles
  maintaining.md         Doc hygiene rules — read before editing docs
  appendix.md            Background research synthesis + corpus state catalogue
  games/                 One file per game in the corpus. Living spec examples.
    _candidates.md       Pipeline of games to consider next — corpus-first dev
  open-questions/        One file per open design question, with a tiered _index.md
  research/              Background surveys (verbatim, longer reads)
  design-notes/          Exploratory design analyses (proposals, not settled spec)
```

## Where to look for what

- **"What is this language?"** → `docs/principles.md`
- **"How do phases / rules / move types fit together?"** → `docs/model.md`
- **"What's already in the standard library?"** → `docs/library.md`
- **"How does X work?" (knowledge, scoring, mutation, typed outcomes, etc.)** → `docs/decisions.md`
- **"What is this thing called?" / "What may this word mean?"** → `docs/glossary.md` — the generated index, one line per term; the entries themselves are one file per term in `docs/glossary/`, so read the index for the whole vocabulary and open an entry only when that term is the thing in question. The naming authority. Its preamble's usage rules (full phrase, Title Case, one name one shape) bind all new code, comments, diagnostics, and issues; its reserved-words table lists the words never to use unqualified, and each term has its own entry under `docs/glossary/`. Where current code diverges: `docs/design-notes/glossary-findings.md`; renames execute via [epic #204](https://github.com/jbgh2/card-game-dsl/issues/204), when-touched unless an issue rules otherwise.
- **"How is game Y described in the DSL?"** → `docs/games/Y.md`
- **"How do we keep info sets derivable / hit the OpenSpiel target?"** → the load-bearing section above, then `docs/design-notes/kernel-extensibility.md`
- **"How do the engine's domains fit together / where does new work dock?"** → `docs/design-notes/domain-map.md`
- **"How do I start a new piece of work?"** → the `cardlang-planning` skill (`.claude/skills/`) — the ordered planning gates; run it before exploring or entering plan mode
- **"How complete must a new construct be?"** → `docs/decisions.md`, "Surface totality" (grammar surface) and "Closed-domain completeness" (the machinery beneath it); the mechanized gate is the `surface-totality-audit` skill (`.claude/skills/`)
- **"What's still being decided?"** → `docs/open-questions/_index.md` then the named file
- **"What should we build next?" / "In what order?"** → the GitHub tracker: [issue #143](https://github.com/jbgh2/card-game-dsl/issues/143), the pinned ordering issue, is the authority on cross-cutting task sequence. `docs/open-questions/_index.md` owns question *priority*; `docs/games/_candidates.md` holds the full game pipeline.
- **"Who merges what?" / "What work may an agent take?"** → `docs/harness.md` — the Operating Harness: Merge Lanes, the work graph and Ready Front, Leases, Standing Roles
- **"How do we build the tooling (parser/checker)?"** → `docs/implementation.md`, `docs/building.md`
- **"How do we remove the per-game Python mechanics?"** → `docs/kernel-migration.md`
- **"Which game uses which state variable?"** → `docs/appendix.md` (corpus catalogue)

## Verifying changes — MANDATORY before every merge

CI (`.github/workflows/ci.yml`) runs three checks on the self-hosted pool,
about 12 minutes end to end. **The merge gate is CI green on all three.
Push early and freely — a push starts the run and costs nothing — but never
merge, and never report a change as done, on less than a green gate.**
The gate is lane-invariant; *who* performs a merge is the Merge Lane's
call (`docs/harness.md`, "The Merge Lanes").

```
mypy                                  # strict; covers cardlang/, tests/ AND experiments/
pytest -q -n 8                        # the language's own gate (CI form)
pytest experiments/llm_eval/tests -q  # the rigs; NOT collected by the above
```

The third exists because `testpaths = ["tests"]` keeps the experiment rigs out
of the language's gate, which is deliberate — but left them run by nobody, so
the leak-freeness pins the LLM harness advertises could go red while CI stayed
green. Keep them a separate step rather than widening `testpaths`: both
properties are wanted.

Locally, run what the change can affect while CI runs concurrently; when
quoting local evidence, run the checks as written. In particular:

- Run **`mypy`** (bare), **never** `mypy cardlang` — the latter checks only the
  package and silently skips strict-mode errors in `tests/` (missing annotations,
  untyped helpers, bare `dict`), which then fail CI. Test code is held to the same
  `--strict` bar as the front end.
- A green suite means the **full** selection, not a subset — the corpus harness
  and golden/characterization tests catch regressions a narrow run misses.
  `-n` does not change the selection or the evidence: pass/skip/xfail counts
  are byte-identical to a serial run (measured 2026-08-05, M5 Air: full suite
  1071.7s serial against 547.6s at `-n 10`), and the partition-coverage
  record is executor-invariant (pinned by
  tests/test_partition_record_modes.py). The weekly `canary` job runs the
  bare serial form on hosted Linux and is the reference.
- The shorter **development** pass, `pytest -q -m "not slow" -n auto`, drops
  every coverage-manifest seed past the first (`tests/openspiel_ready`). It is
  a loop for iterating, **never** the evidence: the evidence is CI's green,
  or a full local `pytest -q [-n N]` when CI is unavailable. Quoting a
  `-m "not slow"` run as a green suite is the silent-cap defect wearing a
  command line.
- **The evidence must be able to fail.** A piped run (`pytest -q | tail -3`)
  reports the pipe's exit status, not the suite's — a killed run surfaces as a
  clean exit. Run the checks bare or under `set -o pipefail`, and treat the
  suite's own summary line (`N passed`) as the evidence, never a wrapper's
  exit code. CI is the authority.

**These two checks are regression gates, not completeness gates.** A change
that adds or extends grammar surface, a checker Owner Guard or diagnostic, a native registry or kernel table, or any closed-domain mechanism — **including a change answering a
review finding on one**, where the finding is a sample of a class and never
the spec for the fix — additionally passes the
**surface-totality audit** — run the `surface-totality-audit` skill
(`.claude/skills/`), the mechanized form of decisions.md "Surface totality"
and "Closed-domain completeness". Its artifacts are mandatory in the change:
the **grid** (the crossed coverage domain as an executable parametrized
test — axes derived in code, expected outcomes authored red BEFORE the
implementation exists), misuse-probe **rejection tests** (the most plausible
wrong sentences, each proven loud in the right layer's failure channel), and the
**completeness ledger** (the judgment the grid cannot state itself, in the
grid module's docstring — the grid IS the coverage record and no row
restates it; an uncovered cell is an `xfail` naming its reason, with a
tracker issue cited as `issue #N`, or the `xfail` reason alone for an R4
auditor-only cell guarding nothing rigor-critical (`docs/decisions.md`,
"Reachability ranks the work"); born-green pins name their reddening
mutation). A green suite must never stand in for this gate: the suite proves
nothing about cells no test names.

## The tracker

Deferred **work** lives in GitHub issues
(<https://github.com/jbgh2/card-game-dsl/issues>), not in `docs/`.
Two sections stay behind, and neither is work: `docs/roadmap.md`, "Out of
scope", and `docs/roadmap.md`, "Grammar surface deferred by the checker".
When you defer a cell, file an issue and cite it as `issue #N` beside the
cell's guard — a deferral with no record does not land. R4 auditor-only
cells guarding nothing rigor-critical are the exception
(`docs/decisions.md`, "Reachability ranks the work"): like the carve-out
below, they record in the owning ledger and need no issue.

One carve-out, because it is what the repo actually does: a **designed
constraint** — a recorded trap, deliberately not-to-be-fixed (`hand[0]`
coercing, `action`'s move-type-specific fields staying `TAny`) — is not work
and needs no issue. It records in the spec, or in a comment at the construct
it constrains, where the next reader of that construct meets it; and it SAYS
it is designed, so "no issue" reads as a decision rather than an omission. If
the cell is something anyone might one day build, it is work: file the
issue.

Keep the label set minimal. The whole vocabulary is five **kinds** — `bug`,
`enhancement`, `documentation`, `tech-debt`, `epic` — two **modifiers**,
`blocked:needs-witness` and `needs-triage`, and the four **reachability**
labels, `reachability:R1`–`R4` (below). Area labels
(checker/runtime/testing) were rejected deliberately — semantic issue search
covers retrieval, so wait for the problem before adding a label.

**Every issue carries at least one KIND.** A modifier never stands in for one:
`blocked:needs-witness` says *when* an issue can be worked, not *what it is*,
so an issue carrying only that label is still unclassified. File the kind with
the issue; if you genuinely cannot pick one yet, add `needs-triage` and say why
in the body.

Every issue carries its reachability as a **label** — `reachability:R1`
… `reachability:R4` (`docs/decisions.md`, "Reachability ranks the work") —
with the one-line why in the body ("R2 — a designer writing X meets it").
`epic` issues are exempt: a container aggregates items of different
reachabilities. The tracker exists to order work; an issue that does not
say who can trigger the defect cannot be ordered. The reachability sweep
is the kind sweep's sibling — absence of the label, asked for by superset:

```bash
gh issue list --repo jbgh2/card-game-dsl --state open --limit 200 \
  --json number,title,labels --jq '.[] | select(([.labels[].name] | any(startswith("reachability:")) or any(. == "epic")) | not) | "\(.number) \(.title)"'
```

An issue's title and Summary speak impact; its Detail speaks
mechanism. The title states what a designer or the engine experiences, not
where the fix goes ("a team typo plays to completion", not
"validate teams at resolve time"). The Summary answers, in a few
sentences: who hits it, what they see, what changes when it's fixed — with
the reachability why doing double duty ("R2 — a plausible one-character
typo"). An issue with no designer or info-set consequence says "internal
only" and names the guarantee it protects and what that guarantee's
failure would look like — even R4 machinery has that sentence. Everything
the implementing agent needs stays in Detail, untouched by this rule.

The sweep is a **derived query**, not a promise to remember the label — an
issue filed with no labels at all is exactly the case a `needs-triage`
convention cannot catch, so the sweep asks for the absence of a kind rather
than the presence of a marker (completeness by superset, never by judgment):

```bash
gh issue list --repo jbgh2/card-game-dsl --state open --limit 200 \
  --json number,title,labels --jq '.[] | select([.labels[].name] | any(. == "bug" or . == "enhancement" or . == "documentation" or . == "tech-debt" or . == "epic") | not) | "\(.number) \(.title)"'
```

Empty output is the clean state. Run it when sweeping the tracker; it needs no
discipline upstream to be correct, which is the point.

- **`blocked:needs-witness`** requires the body to NAME the game or data
  point that unblocks it. A witness-gated issue with no named witness is the
  corpus-first rule stated without its evidence, so the label does not apply.
- **`needs-triage`** means "filed fast, kind not yet decided" — a deliberate,
  visible state, not a resting place. It comes off when a kind goes on.
- **`epic`** issues are checklist containers for multi-stage workstreams;
  they hold sub-items, not work of their own.
- Every migrated issue carries a `## Provenance` line naming its source.
  Keep that habit for new issues that split off an existing one.

Issues relate through the work graph, all of it native and public:
sub-issues for containment, blocked-by dependencies between issues,
`blocked:needs-witness` for the one blocker that is not an issue. The
Ready Front — the derived set of issues an agent may take — and the
Lease protocol live in `docs/harness.md`; its sweep,
`tools/ready-front.sh`, is the third sibling of the two above.

[Issue #143](https://github.com/jbgh2/card-game-dsl/issues/143) is the pinned
ordering issue and the authority on cross-cutting task sequence.

## Operating rules (load-bearing)

These come from `docs/maintaining.md`. They are not stylistic preferences;
violating them silently corrupts the spec.

1. **Spec, not history.** `docs/` describes what the language *is*, not what
   it used to be or how it got there. When a design changes, edit in place —
   no "previously...", "now...", "this used to be a flag", or "RESOLVED" markers.
   Previous designs are not part of the current spec.

2. **Games are the living embodiment of the spec.** When the language
   changes, the files in `docs/games/` must be brought into line in the same
   change. A game file that uses obsolete syntax is a bug, not a historical
   artifact.

3. **Open question → decision promotion.** When an open question is settled,
   move the content from `docs/open-questions/<name>.md` into
   `docs/decisions.md` (rewriting from question-voice into spec-voice),
   delete the open-questions file, and update `docs/open-questions/_index.md`.
   Don't leave a "resolved" stub behind.

4. **Cross-reference, don't duplicate.** If a fact lives in `decisions.md`,
   other files link to it. Two copies will drift.

5. **Reference open questions by title.** `decisions.md` and game files refer
   to open questions as `open-questions/<slug>.md` — not by tier number or
   ordering. Tiers shuffle as questions resolve; the slug is stable.

6. **The corpus state catalogue in `appendix.md` is a stable reference table,
   not a living document.** Don't update it incrementally when games are added;
   replace it wholesale when the language has changed enough that the design
   implications need re-examining.

7. **Names come from the glossary.** `docs/glossary.md` owns what every concept
   is called and what every name may mean — in docs, comments, docstrings,
   diagnostics, and issues alike. Use its terms in full and in Title Case; never
   use a reserved word (see the glossary's reserved-words table) unqualified. A change that needs a word the
   glossary lacks mints the entry in the same change; a change that renames or
   retires a spelling updates the entry in the same change.

## A note on the games

The games in `docs/games/` serve two purposes simultaneously: they are the
canonical worked examples of how the DSL describes real games, AND they are
the test bed that drives language evolution. They must be kept in lockstep
with the current state of the language. When you change the language,
update every game that exercises the changed construct in the same edit.

The corpus is the set of files in `docs/games/` — one game per file, with
each file's header naming its exact variant and player count. Each is a
complete description: a non-player should be able to read the file
cold and play a hand. That's the acceptance test for clarity.

## Rule references

When you need to look up a game's rules — to check a detail of a game
already in `docs/games/`, or to size up a candidate game from
`docs/games/_candidates.md` — **Pagat.com (https://www.pagat.com/) is the
authoritative source**. Fetch the page live rather than reconstructing
rules from memory; trick-taking variants drift in small ways that matter
to the DSL (lead order, exact scoring, team choice). Don't mirror
or scrape the site — use it on demand, like any other reference.

## Out of scope (current phase)

CCG-style card effects (Magic, Yu-Gi-Oh!) and deck-builders are deferred.
See `docs/roadmap.md` for the full list of what is out of scope and which
grammar surface the checker defers; the tracker holds the deferred *work*.
