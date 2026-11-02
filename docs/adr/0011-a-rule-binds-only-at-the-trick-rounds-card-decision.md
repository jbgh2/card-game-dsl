# ADR-0011: A rule binds at the trick round's card decision and nowhere else; a board move's legality is its When Clause over a named function

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator, decision by decision against Hoyle's and the Architect's counsels in a two-persona sitting
- **Record:** issue #953 (Question 1 of the Ruling; the counsels, comments 1 and 2); its units, issues #963 (the promotion), #964 (the `dir` lift) and #965 (the memo, filed)
- **Governs:** decisions.md, "Rule demand forms"; the open question `rule-scope-beyond-trick-play.md`, which #963 promotes and deletes

## Context

Rule application had one runtime site, and everything the rule grammar
could express beyond it was validated and never consulted. The board
ladder's two witnesses — nine men's morris's in-mill removal restriction
and english draughts' mandatory capture — were the awaited reusable
constraints on non-trick decisions, and the board-topology note proposed
the wide resolution: rules bind at every kernel decision site through the
decision interpreter's candidate hook. Both counsels proved the narrow form
instead by writing the witnesses: each checks and runs today as one line
on the move behind an `offer`, with a planted fault caught by execution
(morris: 300 seeds, 231 removal offers, 0 wrong, and 8 of 231 wrong
without the restricting conjunct; draughts: 0 steps offered beside a
capture in 163 offers, and 55 of 131 offers unlawful without it). Written
2026-11-01 from the issue's Ruling section.

## Decision

1. **Narrow, permanently.** Every other decision is legal or not by the
   construct that makes it — a move type's When Clause over a named
   function; a constraint a family shares is a function a family library
   carries, never a rule.
2. **The promoted sentence** is Hoyle's with the Architect's last line:
   what reopens this is a legality over the offered list as a whole — a
   maximum over the offer — which neither a When Clause nor a card-shaped
   rule states; it arrives as its own construct, and no corpus game or
   ladder candidate has one.
3. **The `dir` lift.** The board's direction domain is admitted to the
   bare quantifier family (`any dir where`, `all dirs where`, `number of
   dirs where`) and at both declared-type positions, function parameters
   and outcome payloads, under the one Owner Guard that owns them;
   `zone[dir]` and `for each dir` stay refused.
4. **Mandatory capture is spelled as the rulebook's own branch**, `if
   can_jump(t) { offer to t one of [jump] } else { offer to t one of
   [step] }`, one scan per turn. The per-enumeration memo — pure function
   calls remembered for one candidate enumeration — is filed as the
   engine's designed fix for any per-candidate predicate and built when a
   rung's measured harness time needs it.
5. **Two pins** land in the promotion PR: a derived one-caller test over
   the decision-point registry, and a designer-words refusal for a rule
   naming a game's own move type, its message pinned.
6. **Sequencing.** Morris opens as soon as Question 2's unit is on main;
   draughts opens blocked-by the lift and the position-typed-state
   residual (#111). Draughts' witness is ADR-0014.

## Alternatives

- **The wide form** — rules at every decision site via a candidate hook.
  Lost: a second legality language over moves — a demand over moves, the
  candidate bound as `action`, move-type names as values, a narrowing step
  at each of the chooser's seven decision points — for a hook that does
  not exist at a turn-body `offer`.
- **Hoyle's conjunct on the step** as the spelling of mandatory capture.
  Lost on cost: 22 to 23 predicate evaluations per offer against one per
  turn, with identical playouts.

## Consequences

The glossary mints **When Clause** and narrows **Rule**; information sets
do not move; the grammar pass's row 7 (rules folded into filter functions)
is not decided here.
