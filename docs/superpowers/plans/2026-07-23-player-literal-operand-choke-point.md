# Player-Literal Operand Choke Point Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This change adds a checker wall + a closed-domain registry pin, so it runs the `surface-totality-audit` skill BEFORE writing its tests. Start from `main` (the breakthrough PR that carried the partial wall is expected to be merged first).

**Goal:** Close the "an integer literal in a Player position must name a real seat" class **by construction**, at the correct layer — one operand-check choke point every `assignable(_, Player)` coercion routes through — replacing the current per-site hooks, and prove it closed with a pin that fails the day a new Player position bypasses the check.

## Why this exists (the correct-layer argument)

An integer literal coerces to `Player` (`assignable(Integer, Player)`; the `dealer : Player = 0` rule). A literal that is not a seat of the game (`< 0` or `>= max_players`) names a player who does not exist; the reader crashes at runtime on a game the checker accepted.

The wall for this shipped on the breakthrough PR (#92) as `typecheck._check_player_literal`, **called from five hand-picked sites**. That per-site pattern is the wrong layer, and the evidence is empirical: three Codex review rounds plus an adversarial audit, each finding "you hooked these sites, not that one." Hooking the remaining sites once more just resets that clock.

The test of "correct layer" (from the advisor): **can someone add a new Player-typed position and have the range check silently not apply?** Today, yes. We are at the right layer only when a **pin fails** the moment that happens. That pin — not "I enumerated every site this time" — is the deliverable.

## Architecture

1. **One operand-check choke point.** Introduce `_check_operand(node, got, expected, env, bag, msg)` in `cardlang/typecheck.py`. It does the two things every operand check does, in one place:
   - `if not assignable(got, expected): bag.error(msg, node.span)`
   - `_check_player_literal(node, expected, env, bag)` (already unwraps `Player?`; already two-sided on the bound).
   Every operand check routes through it, each passing its own message. Non-Player expectations make the range check a no-op, so routing them through is harmless and uniform.

2. **The pin is what makes the refactor worth doing.** Once every operand check goes through `_check_operand`, completeness enforcement is a one-line scrape: **no raw `assignable(` appears in `cardlang/typecheck.py` outside `_check_operand`, except an explicit whitelist.** That test (`tests/test_operand_choke_point.py`) is the class-closed proof — a new coercion site that calls `assignable` directly fails it until it either routes through the choke point or is whitelisted with a reason. Without unifying first, the pin would be a fragile semantic scrape that also could not see the untyped clauses below.

3. **`loser:` / `offer to` / `round` are a second, worse bug — fixed for free.** They accept an out-of-range seat because they do **no** Player type-check at all (`loser: "hello"` is accepted, not just `loser: 5`). Routing them through `_check_operand(node, got, TPlayer(), ...)` **types and ranges them in one move.** That two-birds collapse is the signal the layer is right. It is a behavioral change (they now reject non-Player and out-of-range) — verify each is genuinely a Player position and run the full corpus.

## The site inventory (verified 2026-07-23; re-confirm at implementation — line numbers rot)

`grep -n "assignable(" cardlang/typecheck.py`, classified:

- **Operand, Player-capable, ALREADY walled** (the five `_check_player_literal` hooks the choke point subsumes): call argument, zone-family subscript, keyed-state index read, procedure argument, keyed-state index write.
- **Operand, Player-capable, RESIDUAL** (accept out-of-range today — this is the class to close): struct Player field, scalar assignment value (`dealer := 5`), `state` default (`dealer : Player = 5`), `as` binding (`as 5`), `turns from` leader, `turns over [..]` participant (the check is on the collection ELEMENT — handle the list shape), variant Player payload.
- **Operand, non-Player expected** (route through; range no-ops): `for each cell/line in <source>`, assign-RHS-to-Integer, `turns` `at`-to-Boolean.
- **NON-operand — whitelist in the pin with a reason:** the symmetric equality check (`assignable(l,r) or assignable(r,l)`) has no single "expected" and must not be forced through.
- **Untyped Player positions (no `assignable` at all — ADD a `_check_operand(_, _, TPlayer(), _)` check):** `loser:` selection (verified — accepts even a string, so genuinely untyped), `offer to` target (verified — accepts seat 5), `round` from/over (audit-identified). The follow-up authors each red-first.

Verified-accepted-today (the residual is real, not inherited on faith): `dealer : Player = 5`, `dealer := 5`, `turns from 5`, `offer to 5`, `turns over [5]`, `as 5`, a struct Player field, and `loser: 5` (even `loser: "x"`) each type-check on a 2-seat game. NOT cheaply buildable here, so audit-identified (the follow-up confirms red-first): a variant Player payload, the `round` from/over seats.

## Surface-totality artifacts (mandatory — `surface-totality-audit`)

- **The grid** (`tests/test_player_literal_range.py`, grown from the partial grid #92 shipped): every Player position x {in range | over high} x {fixed | range count}, negative pinned once as the shared lower bound. The residual rows (declaration/binding + `loser`/`offer`/`round`) are authored **red first** — each proven currently-ACCEPTED (the bug), then flipped to REJECTED by the choke point. Reuse the existing `card_game` / `_board_game` skeletons.
- **The pin** (`tests/test_operand_choke_point.py`): the no-raw-`assignable`-outside-the-choke-point scrape, born green, with its **reddening mutation** named in the docstring (e.g. "restore a direct `assignable(got, declared)` at the state-default site -> the pin reddens"). This is the closed-domain registry pin; the domain is "operand checks in typecheck.py", the registry is the `assignable` call set.
- **The completeness ledger**: update the `test_player_literal_range.py` module docstring — `covered` becomes the full position set (grid), `residual` shrinks to only what genuinely stays out (Team literals on the team axis, unless swept here; let-alias if it stays runtime-backstopped). Every remaining residual cell keeps a roadmap.md line.
- **Sweep the class**: the Team literal (`team[2]` on a two-team game) is the same shape on the team axis — decide whether the choke point covers it (a `TTeam` bound threaded like `max_players`) or it stays a named residual. Do not patch Player and leave Team silently open.

## Gates & lockstep

- `mypy` (bare, never `mypy cardlang`) + full `pytest -q`, both green, before any push (CLAUDE.md).
- **Goldens byte-identical.** The IR and behavioural goldens must not move — this is a checker-diagnostic change, not a runtime one. A diff is a defect, never regenerated to absorb.
- **Corpus lockstep.** Newly typing `loser:`/`offer`/`round` and the binding positions may reject something a corpus game currently writes. Run the full corpus; if a real game breaks, that game had a latent bug — fix the game in the same change (operating rule 2), do not weaken the wall.
- **Diagnostic quality.** Each routed site keeps its own message (the choke point takes `msg`); the range failure keeps the existing "seat K is out of range: the game has N player(s) (0..N-1)" wording the grid asserts.

## Tasks

- [ ] **Task 1 — Classify + choke point.** Re-run the `assignable(` grep, confirm the inventory above, introduce `_check_operand`, and route the three currently-walled *expression* sites through it (behaviour-preserving; suite stays green). Delete the now-redundant direct `_check_player_literal` calls those sites made.
- [ ] **Task 2 — The residual operand sites.** Route the seven Player-capable residual sites (struct field, scalar assign, state default, as-block, turns leader, turns participant element, variant payload) through `_check_operand`. Grid rows for each authored red first.
- [ ] **Task 3 — The untyped clauses.** Add `_check_operand(_, _, TPlayer(), _)` to `loser:` / `offer to` / `round`. Confirm each red-first (accepts a non-Player today). Corpus run.
- [ ] **Task 4 — The pin.** `tests/test_operand_choke_point.py`: no raw `assignable(` outside `_check_operand` bar the whitelist; born green; reddening mutation documented and RUN (verify-the-plant: assert the mutation reddens the pin for the right reason).
- [ ] **Task 5 — Team axis.** Sweep the Team-literal class: cover it via the choke point (preferred) or record it as a named residual with a roadmap line. No silent gap.
- [ ] **Task 6 — Ledger + roadmap + gates.** Update the `test_player_literal_range.py` ledger (covered = full grid); shrink the roadmap.md "Out-of-range player literals in declaration/binding positions" entry to only what still defers (delete it if nothing does). Bare `mypy` + full `pytest -q`; goldens byte-identical. PR; do NOT self-merge.

## Nothing beyond this

This is a general type-system change; it touches no grammar surface, no runtime, no observation machinery, no board code. It does not add the Team bound *mechanism* unless Task 5 chooses to (else Team stays a recorded residual). It does not revisit the computed-index residual (`hand[0 + 9]`) — that is the separate "Zone-family index strictness" roadmap entry, backstopped by the typed `ZoneStore` miss, out of scope here.
