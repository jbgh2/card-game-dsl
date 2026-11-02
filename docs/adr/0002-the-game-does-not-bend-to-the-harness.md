# ADR-0002: The game does not bend to the harness; when they disagree, the instrument changes

- **Status:** Accepted
- **Date:** 2026-08-25
- **Ruled by:** the operator, on the review's finding; confirmed 2026-09-17 on the playout policy
- **Record:** issue #415 (the slam cap that could never be reached); PR #446 (merged 2026-08-25), the CLAUDE.md section
- **Governs:** CLAUDE.md, "The game does not bend to the harness"

## Context

Bridge's bid cap of level three made its slam scoring dead code. The cap
had been placed so a uniform-random playout would terminate and exercise
the file, and the trimmed rule left the corpus measuring a game nobody
plays — every proof taken against that file was a proof about the wrong
game, however green it ran. The review that found it (issue #415) could be
answered by trimming the rule or by widening the harness. Backfilled on
2026-11-01 from the PR and the session record.

## Decision

The operator, 2026-08-25: "the game should not change, the harness
should." `docs/games/` describes the game; when the game and the instrument
that measures it disagree, the instrument changes. Two justifications look
alike and are opposite in kind: "the language cannot express it yet" is
legitimate — the game stays whole, the gap gets a witness and an issue,
the language grows to meet it; "the harness will not exercise it" is the
defect, fixed upstream in a better playout policy, a different bound or a
real oracle. A game genuinely played in a reduced form is a variant and its
header names it; a game reduced to suit a test is a measurement error with
a comment.

Confirmed 2026-09-17, when a playout-policy change offered the operator a
choice between two ways of getting the corpus wrong (rank every number
decision as a bid, or draw them all): "What do the rules of the game say
must happen. No compromises on implementing the game just to get the code
to run."

## Alternatives

- **Trim the rule to what the uniform playout reaches.** Lost: the file
  then describes a game nobody plays, and every green proof against it is
  about the wrong game.
- **Put a choice between two wrong implementations to the operator.**
  Refused as a frame: both arms answered a question the rules never asked;
  the missing input (which decision the policy is at) is filed, and only
  what is right under every game's rules ships.

## Consequences

CLAUDE.md's third load-bearing section; the `cardlang-new-game` skill reads
the live rules source before the file; the game-against-rules differentials
own the unconfessed reductions the sweep of confessed ones cannot find. A
measurement that falls after a correct fix names the next gap, never a
reason to revert the fix.
