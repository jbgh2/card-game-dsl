# ADR-0023: A rulebook names the written rules its game is held to, and claims nothing more

- **Status:** Accepted
- **Date:** 2026-11-12
- **Ruled by:** the operator, on the questions issue #1115 put
- **Record:** issue #1115 (the questions, the measurements and the ruling); the PR that lands this record
- **Governs:** maintaining.md, "The rulebook twin" and "The pins a new game joins"

## Context

`docs/maintaining.md` said a rulebook opens with its rules source, and no
test read the line. Measured on main on 2026-11-12: 27 of the 37 rulebooks
carried no `Rules source:` line, and the ten that did spelled what followed
the label several ways. A game could join the corpus naming no source, and a
read taken against a game's file stayed "read" after the file changed. The
set of games not yet read against their source (epic #469) was a hand-kept
list that had to be grown by hand as games arrived.

Issue #1115 put four questions: what the line carries, what reddens a read,
how the 27 arrive, and what counts as a source for a game with no Pagat
page.

## Decision

1. **What the line carries:** "Just the source".
2. **What counts as a source:** "Any url that contains a written copy of the
   rules will do, this will become more important as we do more boardgames".
3. **What the line means:** "The source URL gives a pointer to document that
   was used to implement the game. We can't prove they are linked but there
   is a difference between 'you didn't implement the game properly' and 'you
   didn't implement this version of the game properly' and the second is
   better".

So nothing reddens a read by machine, and the rulebooks arrive together: the
line is a pointer, one change adds it to every rulebook, and the pin lands
green. That last is the desk's reading of the ruling; the operator did not
say "together" in words.

## Alternatives

- **The source and the commit the read was taken at.** Lost to answer 1. A
  test could then redden a read on any change to the `.cardlang` after that
  commit, but the line would become a record of a read, and a respelling
  that changes no rule would redden it as loudly as a rules change.
- **A rules change reddens the read.** Lost to answer 3. A game's play
  goldens approximate it (they move when play changes on a pinned seed and
  stay byte-identical under a respelling), but not every game has one, and
  the link between file and source cannot be proven either way.
- **Each unsourced rulebook as a marked cell naming #469 until its read
  lands.** Not taken: with the line a pointer and not a read, naming the
  source needs no read, so there is nothing for a cell to wait on.
- **Pagat only, or a fixed list of authorities.** Lost to answer 2. The
  board games have no Pagat page, and a commercial game's rules live with
  its publisher.

## Consequences

- Every rulebook carries one `**Rules source:** <URL>` line in its opening,
  and `tests/test_rules_source.py` refuses a missing line, a second line, a
  line after the first heading, and any other spelling of the label.
- The source a rulebook names sets the version its game is held to. For the
  rulebooks that named none, the PR landing this record lists each pick for
  the operator's read at the merge.
- Not decided here: whether and when a game has been read against its
  source. That stays on the tracker (epic #469), and the pin's ledger says it
  proves only that a source is named.
