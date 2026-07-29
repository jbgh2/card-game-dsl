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
own, spliced flat, with a `requires` contract that may name zones as well as
state. Both the poker anchors and the smuggling family use it, and the smuggling
family is the one that measured how far it reaches: it captures about an eighth
of each member's text, against roughly nine tenths shared.

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

The smuggling family (`experiments/green-lane/`) was the standing candidate, and
the measurement has been made. Its sibling rulesets share roughly 90% of their
text and are a genuine **delta lattice** (v4 is v1 composed with v3, each delta
editing disjoint rule text). The family-library tier was taken to it (issue
\#143) to answer whether parameterization on required state is enough.

**It is — a `with` clause is not forced, and would not have helped.** The
family's members differ three ways: a fine (a per-game constant, carried by
required state exactly as `raise_cap` is), a contraband predicate, and an added
statement inside the shared move. A clause on the import carries constants; it
carries neither a predicate nor a statement. So the axis this question was
waiting on is settled in the negative.

What the same measurement DID surface is where the real pressure sits, and it is
not on a delta form either:

- the varying move (`inspect`, ten bodies over twelve files) stays game-local,
  which costs the family nothing a delta form would recover cheaply — an
  override replacing that move is exactly the silent-redefinition hazard the
  no-override rule exists for;
- the shared material the tier cannot hold is **zones, state declarations and
  the phase tree** — none of which a *delta* form addresses either, since a
  delta shares by patching a base file rather than by naming a common body;
- the one mechanism that would genuinely shrink the duplication is a contract
  over DEFINITIONS — a required function, so the predicate is the game's and the
  move is shared. That is issue \#178's question, not this one's.

So this question stays open, but its evidence is now spent: the smuggling family
has been measured and does not force it. Reopening it needs a family whose
members differ in ways a *shared body* cannot express and a *patch* can —
which is not what a delta lattice of disjoint edits turned out to be.

Related: [decisions.md](../decisions.md) "Family libraries" (the sharing
mechanism that exists, and its deliberate limits);
[games/_candidates.md](../games/_candidates.md) (the pipeline).
