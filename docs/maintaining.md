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
[open-questions/mechanic-phase-unification.md](open-questions/mechanic-phase-unification.md))
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

## The corpus state catalogue (appendix.md)

The state catalogue in [appendix.md](appendix.md) is a stable
reference table, not a living document. It's drawn from the first
five games at the time the state-scoping question was settled. Don't
update it incrementally as games are added; instead, replace it
wholesale when the language changes enough that the catalogue's
design implications need re-examining.
