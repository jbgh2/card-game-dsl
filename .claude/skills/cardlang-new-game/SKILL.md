---
name: cardlang-new-game
description: "The one path for a corpus game — adding a game to docs/games/, or reading an existing one against its rules source and correcting it. Orders the motions whose owners are scattered across four documents: the live Pagat read first, the rulebook twin, the game written over the family libraries with natives only for scoring, the pins a new game joins, the execution differential, and every language gap filed as a witness rather than worked around. Invoke for ANY change under docs/games/ or docs/libraries/; it routes, it does not restate, and it returns to cardlang-planning for any gap it files."
---

# Cardlang new game

A game thread's job is the game. Everything below it — the kernel, the
libraries, the proofs, the goldens — exists so the thread never writes a
mechanic twice or bends a rule to fit an instrument. This skill orders the
path; the law lives with its owners and is cited, not copied.

## 1. The read comes first, live

Fetch the rules source before writing a line (CLAUDE.md, "Rule
references": Pagat is the authority, fetched live, never mirrored; a
commercial game's source is the one Pagat's index names). Read it as
issue #469's "What one read is" procedure says: rule by rule, and above
all **who sees what, when, and in what order** at every decision. The
corpus plays the page as written (`docs/decisions.md` via CLAUDE.md, "The
game does not bend to the harness"): a rule the harness cannot exercise
is fixed in the harness; a variant is named in the header, and naming one
is the operator's ruling, never the cheap default.

## 2. Two files, one game

`<game>.cardlang` is the game and `<game>.md` its rulebook twin, link
shape, opening with the variant, the player count, the deck, the link to
the executable spec and the rules source (`docs/maintaining.md`, "When
the corpus changes", the rulebook twin). A twin that embeds a fenced copy
is a second game that drifts.

## 3. Written over what exists

Run the planning skill's Gate 2.5 before every definition: the family
libraries (`docs/libraries/`), the stdlib and the Builtin registries
cover the mechanic or a probe shows they do not. A game names native
Python only to score a holding (`docs/roadmap.md`, "Destinations",
"Python only scores"), declared in its `primitives { }` block with its
reads; a native that decides legality, a seat or a bid ladder is a
language gap, not a shortcut. The third copy of a shape the corpus holds
twice is extracted into a library in this unit (Gate 2.5's converse).

## 4. The gap is a witness, never a workaround

Where the language cannot say the rule, the game stays whole, the gap
gets a witness and an issue (CLAUDE.md, "The game does not bend to the
harness", the first justification), and the thread returns to
`cardlang-planning` with that issue. A rule trimmed to pass is the
second justification, and it is the defect. A gap that bears on an open
milestone's finish line joins that milestone by the parts-join rule
(`docs/harness.md`, "The Ready Front"); a Merge Lane A gap is named on
the epic as the operator's step and never worked in this thread.

## 5. The pins the game joins, and the differential that measures it

A new file joins every glob-driven sweep on arrival and reddens the
hand-authored tables it must join (`docs/maintaining.md`, "The pins a
new game joins"): the proof module under `tests/openspiel_ready/`, the
prose-only twins list, and the rest that section names. Then the
execution differential: the source's rule recomputed independently at
every decision and every hand end, as a repo artifact that moves with
each ruling (`tests/test_tichu_rules_differential.py` and
`tests/test_skat_rules_differential.py` are the pattern), with a
two-world swap witness for every "without knowing" clause. Every defect
a read has found was found this way and none by inspection.

## 6. The evidence

A change under `docs/games/` or `docs/libraries/` sweeps the per-seed
goldens at full width and regenerates at the golden's own width
(CLAUDE.md, "Verifying changes"), and the read's record is a comment on
#469 naming what diverged and what was filed. The PR says which rules
the game now plays that it did not, and which it still cannot, by issue.
