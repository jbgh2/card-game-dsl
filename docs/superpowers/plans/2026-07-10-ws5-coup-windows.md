# WS5-Coup Interactive Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Coup's six rng scope reductions to real player decisions per
the signed-off spec `docs/superpowers/specs/2026-07-10-ws5-coup-interactive-windows-design.md`
(read it first — it is the authority on semantics; this plan is the build order).

**Architecture:** Two kernel additions (a `reveal` epistemic op end-to-end;
`offer`-inside-effect made tested-legal), then the coup.cardlang rewrite onto
window polls + Player-target parameters, then goldens/measures, observational
tests, and lockstep docs.

**Tech Stack:** Python 3.11, lark grammar, pytest, mypy --strict (tests too).

## Global Constraints

- `mypy` (bare, repo root — NEVER `mypy cardlang`) and full `pytest -q` green before any push (CLAUDE.md).
- Branch: `feat/ws5-coup-windows` (off main). Task 5 requires PR #39's harness — rebase onto main after #39 merges before starting Task 5.
- Surface totality: the `reveal` grammar admits ONLY `reveal one card from <zone> [where <lambda>]`; reveal of no matching card fails loudly.
- New goldens are EXPECTED (behaviour change, signed off). Never adjust game logic to preserve an old golden.
- Exact-score/golden tests pin `PYTHONHASHSEED=0` — regenerate goldens under the same convention as the existing ones (see how `tests/golden/coup_scores.json` is consumed in the migration-characterization test before regenerating).

---

### Task 1: the `reveal` epistemic op, end to end

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (epistemic_op rule, ~line 196)
- Modify: `cardlang/parse.py` (~line 470, next to `shuffle_op`)
- Modify: `cardlang/ast/nodes.py` (~line 307, `EpistemicOp`)
- Modify: `cardlang/resolve.py`, `cardlang/typecheck.py` (wherever `EpistemicOp`/shuffle is validated — grep `EpistemicOp` in both; mirror the movement `where`-filter validation for the lambda)
- Modify: `cardlang/runtime/execute.py` (~line 252, the shuffle branch)
- Check: `cardlang/ir.py` — if `EpistemicOp` is serialized generically the new field rides along; run the IR golden tests to confirm no churn (`pytest tests/test_hearts_ir.py tests/test_bridge_ir.py -q`)
- Test: `tests/test_reveal_op.py` (new)

**Interfaces:**
- Produces: grammar `"reveal" "one" "card" "from" zone_expr ["where" lambda] -> reveal_op`; node `n.EpistemicOp(op="reveal", target=<zone expr>, filter=<Lambda | None>)` (add `filter: n.Lambda | None = None` to the dataclass — shuffle leaves it None); runtime emits `("reveal", <zone label>, <card str>)` to EVERY player and leaves the card in place; empty/no-match raises `RuntimeError` naming the zone and filter.

- [ ] **Step 1: Write the failing tests** (`tests/test_reveal_op.py`). Build a tiny inline game source (copy the fixture-game pattern from `tests/test_observe_integration.py` — a game with a `hand[player] : Hand<player>` zone and a phase that runs `reveal one card from hand[0] where c => c.rank == "Q"`; deal known cards first via the fixture's deal). Assert:
  - parse: the statement parses to `EpistemicOp(op="reveal")` with a filter (direct `check_source` on the fixture).
  - execute: running the game with an observer collects `("reveal", "hand[0]", "Q♠")` in EVERY player's log, and `hand[0]` still contains the Q♠ afterwards.
  - loud failure: a reveal whose filter matches nothing raises `RuntimeError` mentioning "reveal".
  - the event reaches the derived information state: `information_state(1, rs, log1)` contains the repr of the reveal event (import from `cardlang.openspiel.infostate`; observers other than the owner must still see it — reveal is public).
- [ ] **Step 2:** Run `pytest tests/test_reveal_op.py -q` — FAIL (grammar error).
- [ ] **Step 3:** Implement: grammar line; `parse.py` transformer `def reveal_op(self, meta, c): return n.EpistemicOp(op="reveal", target=_as_expr(c[0]), filter=<lambda or None>, span=...)` (mirror how movements pick up their optional `where` child); nodes field; resolve/typecheck validation (zone must resolve — mirror shuffle; filter lambda typed like a movement filter: binder is a Card, body Boolean); execute branch:

```python
    # in the EpistemicOp case, after the shuffle branch
    if stmt.op == "reveal":
        zone = _zone_of(...)  # same zone resolution the shuffle branch uses
        matches = [c for c in zone.cards if _passes(stmt.filter, c, ctx)]  # reuse the movement filter helper
        if not matches:
            raise RuntimeError(f"reveal in {label}: no card matches the filter — a game-description bug")
        card = matches[0]
        name, key = ctx.rs.zones.locate(zone)
        label = name if key is None else f"{name}[{key}]"
        if ctx.observer is not None:
            for p in ctx.rs.seating.players:
                ctx.observe(p, ("reveal", label, str(card)))
```

(Use the actual helper names found in execute.py's movement code — do not invent parallel filter machinery.)
- [ ] **Step 4:** `pytest tests/test_reveal_op.py tests/test_hearts_ir.py tests/test_bridge_ir.py -q` — PASS, no IR churn. `mypy` clean.
- [ ] **Step 5:** Commit: `feat(language): reveal epistemic op — public one-card reveal from a zone`

### Task 2: offer-inside-effect, tested-legal

**Files:**
- Test: `tests/test_offer_in_effect.py` (new)
- Modify (only if a static check rejects it): `cardlang/resolve.py`

**Interfaces:**
- Produces: the pinned guarantee Task 3 builds on — an `offer` statement inside a `move_type` effect executes (recurses through `_offer` → `run_body`), the inner decision announces publicly, and the inner actor is the offered player (not the outer actor).

- [ ] **Step 1: Failing tests.** Fixture game: phase offers `[outer]` to player 0; `move_type outer`'s effect sets a state var then runs `offer to 1 one of [inner_yes, inner_no]`; `inner_yes` writes `state flag := true`. Drive with a scripted chooser (see `tests/test_chooser_seam.py` for the seam) picking index 0 at both depths. Assert: flag set; the observer log of EVERY player contains announces for BOTH decisions with the right actors (outer→0, inner→1); player 1's log contains a `chose` for the inner pick only.
- [ ] **Step 2:** Run — if it passes immediately, the combination already works: keep the tests as the pin and skip Step 3. If resolve/typecheck rejects offer-in-effect, remove exactly that rejection (Step 3), never weaken the tests.
- [ ] **Step 3 (conditional):** Minimal resolve change to admit offers in effect bodies.
- [ ] **Step 4:** `pytest tests/test_offer_in_effect.py -q && mypy` — PASS.
- [ ] **Step 5:** Commit: `test(language): pin offer-inside-effect as a legal, announced combination`

### Task 3: the coup.cardlang rewrite + runtime deletions

**Files:**
- Modify: `docs/games/coup.cardlang` (and keep `docs/games/coup.md` in lockstep — same edit, Task 6 polishes prose)
- Modify: `cardlang/runtime/coup.py` (delete `coup_random_target`, `coup_challenger`, `coup_fa_blocker`, `coup_block_roll`, `coup_duke_claim`, `coup_contessa_claim`, `coup_steal_block_claim`, the probability constants, and their registry entries; keep `coup_players_in`, `coup_next_in_game`, `coup_has_char`, `coup_note_reveal`, `coup_game_summary`)
- Modify: any stdlib registry table naming the deleted primitives (grep each name repo-wide)

This task is executed by the main session (it holds the spec context), not a
fresh subagent. The spec's "Architecture decision" section carries the window
pattern and the response move types verbatim — use them exactly. Per-action
structure:

- **New phase state:** `challenged : Boolean = false`, `challenger : Player = 0`, `block_claim : String = ""`, `responder : Player = 0`, `window_open : Boolean = false` (keep `challenge_stands`/`block_stands`).
- **income:** unchanged.
- **foreign_aid:** FA block poll (all others, vocabulary `[block_claiming_duke, allow]`, stop at first block) → if blocked, block-challenge window over all-but-blocker → resolution as today (proven block: `reveal` + return + shuffle + redraw + challenger loses influence; bluffed block: blocker loses influence, aid proceeds).
- **tax / exchange:** challenge window on the actor's claim (Duke / Ambassador) → existing resolution with `reveal` inserted before the proven card's return.
- **steal(target : Player):** `when: coins[actor] < 10 and target != actor and alive[target] == 1 and influence[target] is not empty`; challenge window on Captain → if it stands, offer the TARGET `[block_claiming_captain, block_claiming_ambassador, allow]` → if blocked, block-challenge window (claim = `block_claim`) → resolution as today.
- **assassinate(target : Player):** same guards plus `coins[actor] >= 3`; pay 3; challenge window on Assassin → block offer to target `[block_claiming_contessa, allow]` → block-challenge window → resolution as today.
- **coup(target : Player):** `when: coins[actor] >= 7 and target != actor and alive[target] == 1 and influence[target] is not empty`; pay 7; target loses influence (no windows).
- Every proven-challenge branch inserts `reveal one card from influence[<claimant>] where c => c.rank == <claim>` immediately before the existing filtered move to `court_deck`.
- The turn offer becomes `offer to turn one of [income, foreign_aid, tax, steal, exchange, coup, assassinate]` — unchanged list; `steal`/`assassinate`/`coup` now enumerate targets.

- [ ] **Step 1:** Rewrite `coup.cardlang`; run `python -m cardlang.cli check docs/games/coup.cardlang` (or the pipeline's check entry — see `cardlang/cli.py`) until clean.
- [ ] **Step 2:** Delete the runtime primitives; `grep -rn "coup_random_target\|coup_challenger\|coup_fa_blocker\|coup_block_roll\|coup_duke_claim\|coup_contessa_claim\|coup_steal_block_claim" cardlang tests docs` must return only doc-history-free hits you then fix.
- [ ] **Step 3:** Run a smoke playout sweep (20 seeds) via the driver to confirm termination and conservation invariants; the coup golden test will FAIL (expected — Task 4 re-pins).
- [ ] **Step 4:** Commit: `feat(games): Coup interactive windows — real challenge/block/claim/target decisions`

### Task 4: goldens + max_length re-measure

**Files:**
- Modify: `tests/golden/coup_scores.json` (regenerate), the coup entries in `tests/test_migration_characterization.py` (read it first — follow its own regeneration instructions/comments)
- Modify: `docs/games/coup.cardlang` `max_length:` if the measure says so

- [ ] **Step 1:** Find how `coup_scores.json` is generated (grep "coup_scores" in tests/; the characterization test documents the regen convention, incl. `PYTHONHASHSEED=0` if pinned). Regenerate over the same 40 seeds.
- [ ] **Step 2:** Measure decision counts over ≥250 random seeds (scratchpad script mirroring the game-length-bounds methodology — see memory of PR #35: bound must cover DECISIONS, not iterations); set `max_length` with ~30% headroom; note the measured max in the commit message.
- [ ] **Step 3:** Full `pytest -q` — everything green except (possibly) openspiel_ready parity items handled in Task 5.
- [ ] **Step 4:** Commit: `test(games): re-pin Coup goldens + re-measured max_length (WS5 behaviour change)`

### Task 5: partition proofs + observational tests  **[GATE: rebase onto main with PR #39 merged first]**

**Files:**
- Modify: `tests/openspiel_ready/test_coup.py`

- [ ] **Step 1:** `git fetch && git rebase origin/main` (must bring in `tests/openspiel_ready/partition.py`; if #39 is still unmerged, STOP this task and do Task 6 first).
- [ ] **Step 2:** Re-measure Coup: greedy line length to Terminal (reuse the scratchpad measure script pattern from the partition-checks session) → set `adapter_terminal_steps` (+~40% headroom); confirm `depth=12` still lands a swappable pause (run the suite; adjust depth per the harness's own assertion messages if not).
- [ ] **Step 3:** Add three observational tests to `test_coup.py`, following the existing module's greedy-walk style:
  - `test_challenge_decision_is_public`: walk until any `("announce", q, "challenge")` appears in player 0's log; assert the identical event is in EVERY player's log and in a bystander's `information_state`.
  - `test_reveal_reaches_every_information_state`: walk until a `("reveal", ...)` event appears; assert it is in every player's log and every player's information state verbatim (`repr(e) in info`).
  - `test_blocked_foreign_aid_moves_no_coins`: drive with a scripted chooser (block, then no challenge) at the first foreign_aid; assert actor's coins unchanged.
- [ ] **Step 4:** `pytest tests/openspiel_ready/test_coup.py -q && mypy` — all green, coverage record shows `terminal=True,returns_compared=True` for coup.
- [ ] **Step 5:** Commit: `test(openspiel): Coup partition proofs re-measured + window observational tests`

### Task 6: docs in lockstep

**Files:** exactly the spec's "Docs in lockstep" list: `docs/games/coup.md`, `docs/kernel-migration.md` (WS5 section rewritten in place — done-at-real-scope for Coup, poll pattern replaces the auction-priority direction, Tichu reductions stay), `CLAUDE.md` (honesty caveat narrows to Tichu), `docs/library.md` (reveal built + totality boundary; peek/subset forcing function), `docs/open-questions/structural-infoset-proofs.md` (caveats paragraph → Tichu-only), `docs/decisions.md` ("Coup's challenge and block windows" parenthetical → interactive encoding). Follow `docs/maintaining.md`: spec voice, no history markers.

- [ ] **Step 1:** Make the edits; `grep -rn "coup_challenger\|random-play scope" docs/ | grep -i coup` to catch stragglers.
- [ ] **Step 2:** Commit: `docs: Coup at real interactive scope — WS5 Coup half closed`

### Task 7: full verification + PR

- [ ] **Step 1:** `mypy` (bare) + full `pytest -q` — green.
- [ ] **Step 2:** Push `feat/ws5-coup-windows`; PR titled `feat(games): WS5 — Coup interactive windows (real challenge/block/claim/target decisions)`, body mapping each rng site to its decision + the spec's sign-off note + the epsilon-coarseness residual, ending with the standard Claude Code attribution.
- [ ] **Step 3:** Update memory (`open-threads-triage.md`): WS5-Coup shipped; Tichu half next.
