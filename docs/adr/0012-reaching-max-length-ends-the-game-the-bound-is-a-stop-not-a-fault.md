# ADR-0012: Reaching `max_length` ends the game — the bound is a stop, not a fault, and the bug detector moves to a registry pin

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator, decision by decision against Hoyle's and the Architect's counsels in a two-persona sitting
- **Record:** issue #953 (Question 2 of the Ruling, decisions 1 to 3, 5, 6 and 8 to 10; the counsels, comments 3 and 4); its unit, issue #966, which closes #698
- **Governs:** decisions.md, "Game length as a declared contract" (rewritten by #966); the open question `unbounded-lines-and-max-length.md`, which #966 promotes and deletes

## Context

Every game declares `max_length`, and exceeding it raised, on the theory
that a game past its bound is a non-termination bug. Coup's legally
unbounded exchange line and Tichu's always-call drift are faithful games
the bound truncates: corpus Coup walked down the lowest-id line through
pyspiel raised mid-query after 500 actions (issue #698), so the adapter's
`max_game_length` was a promise the game could not keep. The open question
leaned toward a per-game opt-in declaration. Written 2026-11-01 from the
issue's Ruling section.

## Decision

1. **The Length Stop, for every game.** A game that reaches its declared
   `max_length` ends there and is flagged in every channel —
   `GameResult.ended_by`, the terminal node, both commands' first result
   line. Zero game files move. The bug-detector role moves to a registry
   pin: every registered game ends by its rules under its reference
   playout policy with headroom under its bound; tic-tac-toe at
   `max_length: 5` is the planted fault; Coup under `first` and Tichu under
   the uniform chooser are asserted as stops.
2. **The unit** is exactly `max_length` picks on every route, counted in
   `chooser.decide`; a straddling multi-pick call's remaining picks are
   discarded and never applied; the driver's wrapper goes.
3. **The iteration guards** narrow to decisionless spins — more than
   `max_length` loop boundaries with no pick between them — and stay
   refusals addressed to the author.
4. **Exit codes.** `play` exits 0 at a stop (the table's doing, seats
   named); `demo` exits 1 with the stop line leading.
5. **The proof battery.** Coup's adapter-agreement walk runs to its bound
   now; the six long score-target games stay not-walked with the minutes
   named.
6. **Repetition history stays out**, with a standing constraint for the
   day it enters: a repetition stopping rule is meaningful only in a
   perfect-information game, so the capability, when a witness forces it,
   is admitted for perfect-information games only and refused for a game
   with any concealed zone.
7. **The first witness** is the two-piece shuttle fixture — every line
   infinite, a tie by construction, the stop its only end — built before
   the unit's grid goes green.
8. **The sizing sentence** reads "under the game's reference playout
   policy", uniform random unless the game's twin names another; the pin's
   policy table is derived from the registry.

The outcome at the bound is ADR-0013.

## Alternatives

- **Per-game opt-in truncation** (the question's lean). Lost: a claim the
  engine cannot check, which a designer could write to silence a looping
  `until`.
- **A rules-level turn cap for Coup.** Lost: it never fires before the
  decision bound (a turn costs more than one pick) and states a rule nobody
  plays.
- **Raise, as before.** Lost: it crashes an OpenSpiel consumer mid-query.

## Consequences

The adapter answers a terminal node, so `max_game_length` becomes true for
every registered game; the morris and draughts rungs' draw rules are plain
counters in the ring's `until` with this stop behind them (ADR-0014);
information sets do not move, since every pick reaches every seat through
an existing announce or move event.
