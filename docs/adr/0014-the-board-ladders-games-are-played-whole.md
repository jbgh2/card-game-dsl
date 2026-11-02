# ADR-0014: The board ladder's games are played whole — faithful morris, draughts under the federation rule, and the 8x8 game draughts' only witness

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator, on the two sittings and the three rung planners' findings; the miniature ruled and then amended the same day on a measurement
- **Record:** issue #953 (Question 1 decision 7, Question 2 decision 7, and the rung-planning rulings); the rung epics, issues #968 (hex), #974 (nine men's morris) and #979 (english draughts); issue #975 (the oracle upgrade)
- **Governs:** the three games' headers and rulebook twins under `docs/games/` when they land; CLAUDE.md, "The game does not bend to the harness"

## Context

Three rung planners read the rules sources and probed the installed
oracle. No morris rules body reached states a move cap; the oracle's
200-turn cap is its own harness bound. English draughts' federation rule
(the American Checker Federation) is a draw claim after each player's own
forty moves with no capture and no man advanced. The installed open_spiel
(1.6.15) never offers a slide onto one morris point, fixed upstream on
2026-07-08. The ruled `grid(4, 4)` miniature against `checkers(rows=4,
columns=4)` cannot exist: `checkers.cc` fills three ranks a side on any
board, so every oracle board under seven rows is terminal at the root, and
the custom-board setter is not exposed to Python. Written 2026-11-01 from
the issue's Ruling section.

## Decision

- **Nine men's morris is faithful:** the two rule termini only, cyclic
  lines ending by the Length Stop (ADR-0012), the oracle's 200-turn cap
  kept in the harness where the differential truncates at 200 completed
  turns on both sides. It plays the traditional in-mill restriction — a
  man in a mill may be taken only when every enemy man stands in one — as
  the oracle plays it; the federation's reported relaxation is named in the
  twin as a variant not pinned.
- **The morris oracle is upgraded**, not masked: the rung's part raises
  open_spiel to 2.0 or later in `pyproject.toml` and on the runner's venv,
  the operator's hands after a local run of the adapter suite.
- **English draughts carries the federation rule in its automatic form:**
  a counter reset by any capture and by any uncrowned man's move, drawn at
  eighty plies, the repetition claim excluded in its header; the oracle's
  forty-ply capture-only rule stays in the harness, each line compared up
  to the oracle's draw point and returns compared on rules-ended terminals
  only.
- **No miniature: the 8x8 game is draughts' only witness**, with sampled
  differential lines against the native `checkers` as breakthrough's are.
- **Hex needs nothing** from the length question.

## Alternatives

- **A 200-turn morris variant and a 40-ply draughts variant, header-named
  to match the oracle.** Lost: each is a reduction to suit the instrument
  (ADR-0002).
- **A 4x4 miniature as draughts' solved first witness.** Ruled, then lost
  the same day on a measurement rather than a judgment: the oracle cannot
  play it. An option carries a premise, and the premise needs the
  measurement before the ruling does.
- **Masking the slide defect in the differential.** Lost: an instrument
  taught to agree with a known-wrong oracle measures nothing.

## Consequences

The morris game's `max_length` is sized from faithful play under the
reference policy (the morris epic quotes the run); the board-family
registry refactor is shared by the three rungs' family parts and lands in
order, morris first, hex adding its row, draughts last; the morris oracle
upgrade (#975) is a part the operator runs.
