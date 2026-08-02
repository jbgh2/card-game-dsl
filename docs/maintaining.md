# Maintaining these docs

These docs are a specification, not a journal. They should be readable
end-to-end without external context: a fresh reader should be able to
understand the language as it currently is, not as it became.

A few rules for keeping the docs this way as the design evolves.

## Spec, not history

**Describe what the language is, not how it got there.** When a
design changes, edit the spec in place; don't append a "this used to
be X, now it's Y" note. The previous design isn't part of the current
spec.

**Don't presuppose knowledge of earlier drafts.** Phrases like
"the rewrite", "the original projection model", "now resolved", "was
a flag, now it's a sub-phase" all assume the reader knew the previous
version. Edit them out. Future readers shouldn't have to reconstruct
the history to understand the present.

**No status markers in section titles.** "State scoping — RESOLVED"
announces a historical event. The fact that state scoping is settled
is conveyed by the section being in [decisions.md](decisions.md) rather
than [open-questions/](open-questions/); no marker needed.

**Per-game "Notes on the rewrite" blocks are journal entries.**
Delete them when the game gets refactored. If a game's design embodies
a non-obvious decision, the decision belongs in [decisions.md](decisions.md)
or [open-questions/](open-questions/) (whichever applies); the game
block doesn't need to recapitulate it.

## When history earns its place

History stays in the docs only when omitting it would invite
re-litigation of a settled decision. Two patterns where this
applies:

- **An obvious-looking alternative was tried and didn't work.**
  If a future reader would naturally propose approach X without
  knowing X was already attempted and rejected, the docs should
  say so. Example: the knowledge/visibility model in
  [decisions.md](decisions.md) could plausibly be done with a binary
  hidden/public flag; documenting that this was the original approach
  and explaining why projections replaced it prevents the same
  conversation in six months. Keep the history paragraph short,
  focused on the *reason* for the change, not the chronology.

- **A constraint isn't visible from the current spec.** Some
  constraints are negative — "we chose A because B doesn't
  compose with C." A reader looking only at A and seeing B as a
  candidate alternative would need to rediscover the
  incompatibility. Documenting the constraint with a brief
  rationale is forward-facing spec, not journaling.

The test: does the historical note prevent re-litigation, or
does it just document the journey? If the latter, cut it.

## Names come from the glossary

[glossary.md](glossary.md) is the naming authority: one entry per
concept, one spelling per concept. Prose in these docs — and comments,
docstrings, diagnostics, and issues — uses the glossary's term, in full
and in Title Case (the usage rules in its preamble). A word in its
reserved table (§6) never appears unqualified. When a change needs a
word the glossary lacks, mint the entry in the same change; when a
change renames or retires a spelling, the glossary entry updates in the
same change. Where current code diverges from the glossary,
[design-notes/glossary-findings.md](design-notes/glossary-findings.md)
records it with evidence — renames are tracker work (epic #204),
when-touched unless an issue rules otherwise; the docs never wait for
code to catch up.

## Open questions vs settled design

When an open question gets resolved, **move its content from
[open-questions/](open-questions/) to [decisions.md](decisions.md)**,
retitling as needed. The open-question file's title is a useful
starting point for the decisions section heading, though the spec
form often warrants a longer, more descriptive title. Don't leave a
"RESOLVED" stub behind — that's a journal entry. The decisions entry
should read as spec; the question framing from the open-questions
file gets rewritten into the spec voice. Delete the open-questions
file once its content has landed in `decisions.md`, and update
[open-questions/_index.md](open-questions/_index.md) to remove the
entry.

When a settled design is *reopened* (genuinely uncertain again,
not just being refined), move it back to [open-questions/](open-questions/)
with a clear question framing. This should be rare. Most design
refinement is editing [decisions.md](decisions.md) in place.

## Cross-references

Use relative markdown links between files. Refer to sections by their
heading title rather than position.

**Open-question references use the file slug.** Refer to open questions
as `open-questions/<slug>.md` (e.g.
[open-questions/knowledge-events.md](open-questions/knowledge-events.md))
rather than by tier or ordering. Open questions get added, resolved,
reordered between tiers, and removed; numbering them invites a
renumbering sweep on every change. The slug is stable until the
question is renamed.

When an open question resolves and moves to [decisions.md](decisions.md),
sweep references throughout the docs and point them at the new
decisions section. This conversion is the one cross-reference sweep
that resolving an open question still requires.

## When the corpus changes

Adding a game (a new file in [games/](games/)) often touches the
standard library ([library.md](library.md)) and may surface new open
questions or refine existing design decisions. The game file itself
is forward-facing description of what the game IS in the language. The
*findings* from implementing the game — what it surfaced, what was
hard, what's now blocking — belong in [decisions.md](decisions.md)
(if they led to a decision) or as a new open-questions file (if they
raised a new question), not in the game file.

The game file's job is to be a usable reference for the game.
Findings have their own homes.

## Doc snippet tagging

Every fenced code block in the settled-spec docs — [decisions.md](decisions.md),
[library.md](library.md), [model.md](model.md) — carries an info-string tag on
its opening fence, so `tests/test_doc_snippets.py` can tell DSL from prose and
keep the DSL in lockstep with the language:

- ` ```cardlang ` — a complete game: pipeline-checked verbatim
  (`cardlang.pipeline.check_dsl`).
- ` ```cardlang-fragment <label> ` — a snippet (a rule, a phase, statements, a
  `zones {}` block) that isn't a whole game. The fence carries a **recipe
  label** as its second word; the block is checked by embedding it in a minimal
  game via the wrapper registered under that label
  (`tests/test_doc_snippets.py`, `WRAPPER_RECIPES`). The label rides with the
  block, so moving it or editing prose around it never touches the registry —
  only adding, removing, or renaming a checked fragment does. Every
  `cardlang-fragment` block needs a unique label with a registered recipe.
- ` ```cardlang-bad ` — a complete game the prose shows as a counterexample:
  proven to be *rejected*, verbatim, by the pipeline. Use this only when the
  counterexample is already whole-game shaped, exactly like `cardlang` — a
  fragment checked raw here would "reject" merely for lacking an enclosing
  `game {}`, proving nothing about the mistake it's meant to demonstrate.
- ` ```cardlang-bad-fragment <label> ` — a snippet-shaped counterexample: the
  `cardlang-fragment` treatment for `cardlang-bad`. Wrapped through the recipe
  registered under its label (`WRAPPER_RECIPES`, the same label space as
  `cardlang-fragment`), then proven *rejected*. Because a rejection
  through a broken wrapper — or through a fragment that merely isn't a whole
  game — would prove nothing about the snippet's own content, every
  `cardlang-bad-fragment` block also has a benign filler of the same shape
  in `BAD_FRAGMENT_SMOKE`, proven to *pass* through the identical wrapper
  before the block's own (bad) text is checked against it.
- ` ```text ` (or another accurate non-DSL tag, e.g. ` ```ebnf `) — not DSL;
  the test skips it. Use this for grammar sketches with `<placeholder>`
  tokens, diagrams, and any snippet that describes a proposed or
  not-yet-implemented surface rather than the current one.

A bare fence (no tag) or an unrecognized tag fails the test loudly, naming
the doc file and line — that wall is what keeps a future edit from adding
an unclassified block by accident. `cardlang.extract.extract_blocks` itself
ignores the info string (it always did — Markdown parsing stays the only
thing that module knows about), so tagging every block does not change how
`docs/games/` or any other consumer of `extract_blocks` behaves.

## The corpus state catalogue (appendix.md)

The state catalogue in [appendix.md](appendix.md) is a stable
reference table, not a living document. It's drawn from the first
five games at the time the state-scoping question was settled. Don't
update it incrementally as games are added; instead, replace it
wholesale when the language changes enough that the catalogue's
design implications need re-examining.
