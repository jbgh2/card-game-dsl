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
construct is deleted), no per-game branch outside the stdlib primitive
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
  corpus-first but every deferral is a loud wall. "Vacuously green" — a
  check presented as a guarantee that cannot fail — is a defect class of
  equal rank to "accepted-but-ignored". Changes to rigor-critical machinery
  ship with their completeness argument (property, domain, coverage,
  residual). The rule is `docs/decisions.md`, "Closed-domain completeness".

## What's here

```
docs/
  principles.md          High-level goal, design principles, architectural principles
  model.md               Primitives + phase/state/move-type/rule relationship
  library.md             The Trick mechanic + standard library catalogue
  decisions.md           Settled design decisions (the load-bearing spec)
  roadmap.md             Explicitly deferred work + suggested next steps
  implementation.md      Plan for building the parser + static checker (tooling)
  building.md            Front-end execution blueprint (pipeline, triage, gates)
  kernel-migration.md    Stage plan: remove per-game Python mechanics → DSL kernel
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
- **"How is game Y described in the DSL?"** → `docs/games/Y.md`
- **"How do we keep info sets derivable / hit the OpenSpiel target?"** → the load-bearing section above, then `docs/design-notes/kernel-extensibility.md`
- **"How do the engine's domains fit together / where does new work dock?"** → `docs/design-notes/domain-map.md`
- **"How complete must a new construct be?"** → `docs/decisions.md`, "Surface totality" (grammar surface) and "Closed-domain completeness" (the machinery beneath it)
- **"What's still being decided?"** → `docs/open-questions/_index.md` then the named file
- **"What should we build next?" / "In what order?"** → `docs/roadmap.md`, "Suggested next steps, in order" — the authority on cross-cutting task sequence. `docs/open-questions/_index.md` owns question *priority*; `docs/games/_candidates.md` holds the full game pipeline.
- **"How do we build the tooling (parser/checker)?"** → `docs/implementation.md`, `docs/building.md`
- **"How do we remove the per-game Python mechanics?"** → `docs/kernel-migration.md`
- **"Which game uses which state variable?"** → `docs/appendix.md` (corpus catalogue)

## Verifying changes — MANDATORY before every `git push`

CI (`.github/workflows/ci.yml`) runs exactly two checks. **Before any `git push`,
run both locally from the repo root and confirm both pass. Do not push until they
do.** This is non-negotiable — pushing on a partial check wastes a CI round-trip
and a PR review cycle.

```
mypy        # strict; covers BOTH cardlang/ AND tests/ (pyproject `files`)
pytest -q
```

Run them as written. In particular:

- Run **`mypy`** (bare), **never** `mypy cardlang` — the latter checks only the
  package and silently skips strict-mode errors in `tests/` (missing annotations,
  untyped helpers, bare `dict`), which then fail CI. Test code is held to the same
  `--strict` bar as the front end.
- Run the **full** `pytest -q`, not a subset — the corpus harness and golden/
  characterization tests catch regressions a narrow run misses. Some exact-score
  tests pin `PYTHONHASHSEED=0`; don't assume a passing subset means a green suite.

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
`docs/roadmap.md` — **Pagat.com (https://www.pagat.com/) is the
authoritative source**. Fetch the page live rather than reconstructing
rules from memory; trick-taking variants drift in small ways that matter
to the DSL (lead order, exact scoring, partnership choice). Don't mirror
or scrape the site — use it on demand, like any other reference.

## Out of scope (current phase)

CCG-style card effects (Magic, Yu-Gi-Oh!), deck-builders, and solitaire
positional layouts are deferred. See `docs/roadmap.md` for the full list of
explicitly deferred work and the ordered next steps.
