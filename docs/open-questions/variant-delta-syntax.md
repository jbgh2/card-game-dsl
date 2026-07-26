# Explicit syntax for "X is Y but with deltas"

**Tier 4 — low impact, defer until forced.** This is how the literature
describes card-game variants, and how designers describe them to each other:
not as whole rulesets, but as a base game plus a short list of changes.

The current design supports it **implicitly** — a variant is a game that adds
or removes rules and phases relative to a base — but there is no syntax that
says so. A variant is written as a complete game file, and the relationship to
its base lives only in prose.

## What already exists, and what it does not cover

The `uses <library>` import tier (decisions.md "Family libraries") shares
*material* between sibling games: definitions and the state those definitions
own, spliced flat, with a `requires` contract. It is the right mechanism for a
family's irreducible common body, and both poker anchors and the smuggling
family use it that way.

It is not a delta mechanism. A library is additive and cannot express
"the base game, except this phase is replaced" or "the base game, minus this
rule". `active_rules:` carries `add`/`remove` deltas *within* one game's phase
tree, not across files.

## The question

Should there be a game-level delta form — `game Spider extends Klondike { … }`,
or a declarative patch list — and if so, what is the unit of override? Phases,
rules, state declarations, and clauses each want different merge semantics, and
a delta whose base later changes is the copy-drift problem one level up rather
than solved.

Two live tensions:

- **Deltas versus the corpus-as-spec rule.** Each file in `docs/games/` is a
  complete description a non-player can read cold and play from (CLAUDE.md).
  A delta file is by construction *not* that, so either the acceptance test
  changes or the delta form is an authoring convenience that renders to a
  complete file.
- **Deltas versus derived info sets.** An override that replaces a phase
  replaces its decision sites, so the observation emission a proof module
  reasons about moves with it. A delta form has to make that legible, not
  just textually convenient.

## The data point that would force it

The smuggling family (`experiments/green-lane/`) is the standing candidate: its
five sibling rulesets share roughly 90% of their text and are kept aligned by
hand-diffing, and they are a genuine **delta lattice** (v4 is v1 composed with
v3, each delta editing disjoint rule text). That structure is what would test a
delta form rather than merely benefit from one. The family-library tier is
being taken to that family first (issue \#143) precisely to measure whether
parameterization on required state is enough — if it is, this question stays
closed; if the family needs a `with` clause or genuine overrides, this is where
that lands.

Related: [decisions.md](../decisions.md) "Family libraries" (the sharing
mechanism that exists, and its deliberate limits);
[games/_candidates.md](../games/_candidates.md) (the pipeline).
