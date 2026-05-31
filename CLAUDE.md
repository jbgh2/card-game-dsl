# Card Game DSL

A domain-specific language for describing card games played with standard
52-card decks (plus jokers). Target runtime: OpenSpiel, so existing
imperfect-information AI algorithms work on the resulting games.

This file orients agents working on the project. The design lives in `docs/`;
read this file first to know where to look.

## What's here

```
docs/
  principles.md          High-level goal, design principles, architectural principles
  model.md               Primitives + phase/state/move-type/rule relationship
  library.md             The Trick mechanic + standard library catalogue
  decisions.md           Settled design decisions (the load-bearing spec)
  roadmap.md             Explicitly deferred work + suggested next steps
  maintaining.md         Doc hygiene rules — read before editing docs
  appendix.md            Background research synthesis + corpus state catalogue
  games/                 One file per game in the corpus. Living spec examples.
    hearts.md, getaway.md, spades.md, pinochle.md, bridge.md, seven-card-stud.md
    _candidates.md       Pipeline of games to consider next — corpus-first dev
  open-questions/        One file per open design question, with a tiered _index.md
  research/              Two background surveys (verbatim, longer reads)
```

## Where to look for what

- **"What is this language?"** → `docs/principles.md`
- **"How do phases / rules / move types fit together?"** → `docs/model.md`
- **"What's already in the standard library?"** → `docs/library.md`
- **"How does X work?" (knowledge, scoring, mutation, typed outcomes, etc.)** → `docs/decisions.md`
- **"How is game Y described in the DSL?"** → `docs/games/Y.md`
- **"What's still being decided?"** → `docs/open-questions/_index.md` then the named file
- **"What should we build next?"** → `docs/roadmap.md` (and `docs/games/_candidates.md` for the full pipeline)
- **"Which game uses which state variable?"** → `docs/appendix.md` (corpus catalogue)

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

The corpus today: Hearts, Getaway (Bhabhi), Spades, Pinochle, Bridge
(rubber, simplified), Seven-Card Stud, Tichu, Schnapsen, Cribbage
(six-card, two-player), Oh Hell (four-player). Each is a complete
description: a non-player should be able to read the file cold and
play a hand. That's the acceptance test for clarity.

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
explicitly deferred work and the recommended next game (Cribbage).
