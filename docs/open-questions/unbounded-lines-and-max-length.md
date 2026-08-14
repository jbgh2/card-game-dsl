# Structurally unbounded games and what `max_length` means for them

**Tier 3 — medium impact, narrow scope.** Every game declares `max_length`,
the decision-count backstop the runtime enforces on every playout
(decisions.md "Game length as a declared contract"): exceeding it raises, on the theory that
a game past its declared bound is a non-termination *bug*. That theory held
for the whole corpus — trick games shed cards, auctions strictly escalate,
betting has bounded streets — until Coup reached real interactive scope.

Interactive Coup has **legally unbounded lines**: `exchange` costs and gains
no coins, so a table that only ever exchanges (and never challenges) makes
no progress toward the forced coup at ten coins, forever. This is faithful —
real Coup also never ends if nobody acts aggressively — and it is not
reachable by the corpus's random or depth-bounded test walks (measured
random-play maximum: 57 decisions over 300 seeds, against a declared bound
of 500). But a deterministic policy CAN walk it: greedy lowest-action-id
play loops on `exchange` and hits the backstop, where the runtime raises —
so an OpenSpiel algorithm following such a line crashes mid-query instead
of reaching a terminal state, and the adapter's declared `max_game_length`
is a promise ("the game ends by then") the game cannot keep.

Tichu at real-call scope is the **second witness**, and a sharper one: a
tichu call is worth about −50 in expectation under indiscriminate play, so
a table that always calls drifts *away* from the 1000-point finish forever
(measured: 2,200+ hands with no terminus under the uniform random chooser).
Unlike Coup's exchange loop, this line IS what the uniform chooser plays —
random walks hit it immediately, not only adversarial policies — so Tichu's
playout tests and goldens drive the call windows through a reference policy
(games/tichu.cardlang, tests/test_playout_tichu.py), and the divergence
stands recorded here rather than being patched out of the rules.

## The options

- **Graceful terminal at the bound.** Reaching `max_length` ends the game
  and scores it as it stands (Coup: `winner: highest alive` already ranks a
  truncated position). Honest for OpenSpiel, but it silently converts every
  *genuine* non-termination bug in every other game into a quiet truncation
  — the backstop loses its bug-detector role, which is what it exists for.
- **Per-game opt-in truncation.** A declaration distinguishing "this bound
  is a bug detector" (the corpus default; raise) from "this game is
  legitimately unbounded; the bound is a rules-level game end" (Coup;
  terminal). Keeps both roles, costs new surface, and the truncation-terminal
  needs defined scoring semantics per game.
- **Rules-level progress forcing.** Amend the game so every line is bounded
  (e.g. a fixed turn cap as part of the description). Departs from the
  published rules; the DSL is supposed to describe the game, not patch it.

**Current lean: per-game opt-in truncation** — it is the only option that
keeps the bug detector for the twenty-odd bounded games while telling the
truth about the unbounded one. Settle when a second structurally-unbounded
game arrives to confirm the shape, or earlier if an OpenSpiel consumer
actually drives Coup down a passive line (today's harness walks are
depth-bounded or random, so nothing in-repo reaches the backstop).

Related: decisions.md "Game length as a declared contract" (the backstop's contract);
[games/coup.cardlang](../games/coup.cardlang) (the unbounded witness);
kernel-migration.md Workstream 5 (the interactive upgrade that surfaced it).
