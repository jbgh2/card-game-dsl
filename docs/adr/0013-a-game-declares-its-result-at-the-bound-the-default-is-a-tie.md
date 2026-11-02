# ADR-0013: A game declares its result at the bound — `at max_length: tie`, `as it stands`, or a ranking — and the default is a tie

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator, redirecting both counsels, then decision by decision against Hoyle's single-seat counsel on the sentence
- **Record:** issue #953 (Question 2, decision 4, and the Stop Result's seven decisions; Hoyle's counsel, comment 5); its unit, issue #967, a ruled Merge Lane A part blocked-by #966
- **Governs:** lands with #967 in decisions.md, "Game length as a declared contract"

## Context

Both counsels assumed a game stopped by length is scored as it stands by
its `winner:` clause, and diverged on a `loser:` game — the Architect: a
tie with the selection unread; Hoyle: the uniquely selected seat. The
operator redirected both: the design should be able to say what happens
when the game goes too long, with a sensible default, or a tie. The
declaration is new surface, so its sentence was Hoyle's to counsel under
the two-stage rule and the operator's to rule. Written 2026-11-01 from the
issue's Ruling section.

## Decision

A game MAY declare its outcome at the bound; a game that declares nothing
is a **tie** — every seat a winner, no loser, zero returns — so Coup under
`first` pays every seat 0. The declarable set is closed. Its sentence:

1. **The lead word is `at max_length:`**, one game item in the clause
   register, written beside the bound it qualifies; `at` joins the
   clause-keyword exclusion lists of `CARD_RANK_NAME` and
   `SUIT_RANKING_NAME` and never `NAME`, so `place(at : cell)` stays a
   parameter (38 of 38 corpus and library files parse to the identical
   tree).
2. **The third member is a ranking only** — `highest` or `lowest` a state
   variable, the `winner:` clause's own shape, total at every position,
   through a shared `RESULT_VAR_NAME` terminal that `winner:` takes too.
3. **`as it stands` is kept**, equal to the ranking of the `winner:`
   clause's variable for every `winner:` game and refused in designer words
   for every `loser:` game, with its message fixture.
4. **The default may be written** — `at max_length: tie` is a member with
   a corpus writer, on the `direction: clockwise` precedent.
5. **The corpus principle:** a game's Stop Result matches its written
   rules where they give a basis for a standing, and is the tie otherwise.
   Coup and Tichu declare `as it stands`; Getaway declares nothing;
   faithful morris writes `tie`.
6. **One twin**, for `beyond max_length:` and `after max_length:` — the
   game ends AT its bound and nothing lies beyond it.
7. **The name is Stop Result** — production `stop_result`, node
   `StopResult`, field `Game.stop_result`; "outcome" stays reserved to the
   tagged result.

## Alternatives

- **Scored as it stands for every game, with no declaration.** Lost: it
  decides a `loser:` game by a selection the stop never made.
- **A `the player where <pred>` selection as the third member.** Lost: not
  total at every position; the ranking is.
- **Coup's own loop with a turn counter.** Lost: it checks, states a rule
  nobody plays, and never fires before the pick count.

## Consequences

#967 ships behind #966, and the default tie does not wait on it;
`coup.md` and `tichu.md` re-sentence; the registry pin's Coup column under
`first` is written from the declaration. This matches OpenSpiel's own
convention — a game ending at a bound is drawn — made explicit, flagged and
pinned.
