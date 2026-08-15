# Board Topology Rung 2 (Breakthrough against Stage 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task that adds grammar surface, a wall, a registry, or any closed-domain mechanism runs the `surface-totality-audit` skill BEFORE writing its tests.

**Goal:** Land the movement rung of board-game support — piece **movement** between cells, the minted **movement-direction domain** (`dir`), **per-player frames** (`forward` as a seat-relative transform over one shared grid), the class-1 **neighbour/region query verbs**, **displacement capture** into a captured pile, `for each cell` iteration, and the **reach-region win** — proven by breakthrough: registered in the corpus, differentially validated against OpenSpiel's native `breakthrough`, with a full `openspiel_ready` proof module, and the entire card corpus **and** tic-tac-toe byte-identical.

**Architecture:** Everything docks into rung-1's landed board machinery. Rung 1 built the `board:`/`pieces:` clauses, the `BOARDS` grid family, the minted `cell` named-member position domain (`cardlang/board_domains.py::position_domains_of`), `Cell` capacity, the cell/line query register, and `Card ⊂ Piece`. Rung 2 adds, in one PR-train:

- The **direction domain**: the grid family mints a *second* named-member domain (`dir`, members = the forward directions) riding the same move-parameter enumeration path as `cell` (`position_domains_of`'s union generalizes; IR/driver/encoding follow). Directions are move parameters only — never zone indices, never quantifier binders. Distinct from the turn-order `direction:` clause and the `DIRECTION_VALUES` (clockwise/counterclockwise) passing enum.
- The **grid family's frames, directions, and regions** as closed `BoardEntry` data, integrity-pinned from birth: per-direction offsets + a diagonal flag, per-player frame resolution, and the `home(player)`/`far_row(player)` regions.
- The **class-1 stdlib verbs** `neighbor`, `has_step`, `is_diagonal`, `home`, `far_row` into the three stdlib tables, classified `BOARD_ONLY` (the `lines` twin).
- `for each cell` **iteration** (add `cell` to `_ITERATION_ROLES`) + `cell in <cellset>` **membership**.
- The **move** is `step(from : cell, along : dir)`; the guard short-circuits so a total `neighbor(...)` is never evaluated off-board; the effect does **displacement capture** then moves the piece; **reach** and **wipe-out** wins are set in the effect / detected by the `until` predicate.

The observation moat does not move (wave A: perfect information — every cell zone projects identity to all, every movement announces itself at the existing sites, information sets are singletons). Spec: `docs/design-notes/board-topology.md` (S2.1 frames/regions/directions, S2.4 decisions/movement, S3.2 rung 2, S4 stage 2); requirements: `docs/research/topology-and-query-requirements.md` (class 1 verbs). Oracle ground truth was read directly from `open_spiel/games/breakthrough/breakthrough.cc` (see "Oracle facts" below).

**Tech Stack:** Python 3.11, lark grammar, mypy --strict (covers `tests/` too), pytest, pyspiel (differential oracle + adapter proofs).

## Acceptance criteria (the three, stated up front — CLAUDE.md load-bearing)

1. **Runs.** Breakthrough plays to termination through the driver over random choosers, every seed.
2. **Regression-clean.** `mypy` (bare) and full `pytest -q` green; the 8 IR goldens, every behavioural golden, **and** tic-tac-toe's playout/proof modules byte-identical (rung 2 touches no card or TTT surface — a diff there is a defect, never regenerated to absorb).
3. **Info sets derive.** Breakthrough is perfect information: the `openspiel_ready` proof module proves degenerate indistinguishability for **both** observers, the per-visible-fact soundness matrix, seed/rng non-observability, perfect recall, adapter agreement to Terminal with **returns equality**, and pyspiel conformance; the native-oracle differential proves legal-action-set agreement at every node. Movement emits observations through the existing kernel-movement sites — **no new observation machinery** (the whole point of wave A). Capture is two public kernel movements (piece to `captured[opp]`, then the mover); nothing conceals.

**Corpus-lockstep (operating rule 2):** no card game file changes; `docs/games/tic-tac-toe.{cardlang,md}` unchanged; `docs/games/breakthrough.{cardlang,md}` **added**; `docs/games/_candidates.md` graduates the breakthrough entry. **Witness question:** breakthrough is the end-to-end witness for every new construct; each mechanism task additionally builds a **minimal inline witness fixture** (a hand-rolled board game exercising just that verb/domain) so the unit tests do not wait on the corpus game.

## Oracle facts (read from `breakthrough.cc`, not from rules memory)

- **Action encoding:** `RankActionMixedBase({rows, cols, 6, 2}, {r, c, dir, capture})` = `cell*12 + dir*2 + capture`, where `cell = r*cols + c`, **row 0 = top rank** (rank `rows` for an 8x8), `dir in 0..5`, `capture in {0,1}`. `num_distinct_actions = rows*cols*12` (768 at 8x8; **1:1 with our `cell x dir` after masking**, vs 4096 for a `(from,to)` encoding — the id economy S2.4 mints directions for).
- **Directions** (`kDirRowOffsets={1,1,1,-1,-1,-1}`, `kDirColOffsets={-1,0,1,-1,0,1}`): player 0 uses dirs `{0,1,2}` = row+1 with col `{-1,0,+1}`; player 1 uses `{3,4,5}` = row-1 with col `{-1,0,+1}`. `o=1`/`o=4` are **straight** (col 0); `o=0,2`/`o=3,5` are **diagonal**. So each player has exactly 3 forward directions (left-diag, straight, right-diag), absolute offsets, seat-partitioned.
- **Legality** (`LegalActions`): for each own piece, for each of the 3 forward dirs, if the target is in-bounds: **empty target -> legal move (any of the 3 dirs, capture=0)**; **opponent target -> legal capture only if the dir is diagonal (o in {0,2}), capture=1**; friendly target or off-board -> not legal. (This is the 12-cell legality grid below.)
- **Terminal** (`IsTerminal`): `winner_ >= 0 || pieces_[0] == 0 || pieces_[1] == 0`. `winner_` is set when a piece reaches the opponent's back row (`DoApplyAction`). So there are **two** termini: **reach the far row** OR **the opponent has zero pieces (wipe-out)**. `Returns`: the winner `+1`, loser `-1`; **never a draw** (monotone game). 400 random playouts hit only reach-far-row (max length 102, never stuck), but wipe-out is a real reachable terminus a scripted line can hit — **the `until` predicate must encode both** or the differential diverges late.
- **6x6 is a clean parameter** (`{rows:6, columns:6}` -> 432 actions, 16 legal at start). The corpus pin is **8x8** (the oracle default); a 6x6 variant would be its own game file if tree size ever forces it (roadmap note, not built here).

## Global Constraints

- **Byte-identical card corpus AND tic-tac-toe.** All 8 IR goldens regenerate to zero diff; TTT's `test_playout_tic_tac_toe.py` and `openspiel_ready/test_tic_tac_toe.py` untouched. Never regenerate a golden to absorb a diff — a diff is a defect. Run the IR goldens + TTT modules after every task that touches shared machinery (Tasks 1, 3, 4).
- **The observation moat does not move** (wave A): no new zone-type rows, no new projection levels, no change to `ZONE_PROJECTIONS` / `partition.py::ZONE_PROBES` / `observe.py`. `HiddenCell` is battleship's (stage 4), not built here.
- **Surface totality + closed-domain completeness.** Every task adding grammar surface, a wall, or a registry runs the `surface-totality-audit` skill BEFORE writing its tests and ships its misuse-probe rejection tests + completeness ledger (in the covering module's docstring). The **movement-legality grid** (below) is the centerpiece, authored red first. A residual cell without both a wall and a roadmap.md line fails the task. **Sweep the class** on any found defect before patching the instance.
- **Assert triage** (`tests/test_assert_triage.py`): any `assert`/`AssertionError` under `cardlang/runtime/` or `cardlang/stdlib/` carries a guarantor word or fallthrough marker; game-reachable failures are typed `RuntimeError`s. The backstop inside a total `neighbor(...)` (off-board -> raise) is a **backstop** whose comment names its wall — the guard's `has_step` short-circuit — per write-time triage.
- **Stop-and-fix at write time** (CLAUDE.md): before placing any check, read the owning pass's `Contract` docstring; triage it wall / backstop / missing-wall. A `ref_kind` the resolver stamped or a type the checker validated is not re-derived downstream.
- **Verification commands** (repo root, worktree): `export PYTHONPATH="$PWD"`; `/Users/benh/Projects/Card game DSL/.venv/bin/python -m pytest` / `.venv/bin/mypy`. Bare `mypy` (never `mypy cardlang`), full `pytest -q` before any push. Verify `cardlang.__file__` points into this worktree.
- **ASCII-only prose** in code/docs (no math glyphs; em dash and ellipsis fine). Comment hygiene: failure-mode comments get subjunctive rewording, never deletion. Minimize new code comments (Ben, comment-minimalism) — triage/ledger/red-under artifacts exempt.
- **Nothing beyond the witness.** Later-rung surface stays walled and is NOT built: `HiddenCell` / double-indexed families / `roll` / probe actions / `reachable` / jump-triples / position-typed `state` / **cell literals** / **direction literals** / piece-query grammar forms / collection-noun quantifiers beyond `{cell, line}`. Each is grammatically inexpressible or loudly walled, recorded in roadmap.md.
- Commit after every task; footer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## The movement-legality grid (audit Step 1, authored red BEFORE implementation)

The crossed coverage domain for the move `step(from : cell, along : dir)`. Axes derived in code from the direction domain (`{ahead, ahead_left, ahead_right}`, seat-relative) x the destination occupancy (`{empty, enemy, friendly, off_board}`). Expected outcomes authored red, then verified **differentially** against `breakthrough.cc::LegalActions`:

| `along` \ dest | empty | enemy | friendly | off-board |
|---|---|---|---|---|
| `ahead` (straight, `is_diagonal` false) | **move** | illegal (no straight capture) | illegal | illegal (masked by `has_step`) |
| `ahead_left` (diagonal) | **move** | **capture** (displace) | illegal | illegal (masked) |
| `ahead_right` (diagonal) | **move** | **capture** (displace) | illegal | illegal (masked) |

Plus the **terminus grid**: {mover reaches `far_row(actor)`} -> actor wins `+1`/`-1`; {actor's capture empties the opponent} -> actor wins; {neither} -> running. Every cell is a grid row in `tests/test_breakthrough_movement.py` (an inline witness game), expected outcome authored `xfail(strict=True)` before the guard exists, then confirmed by the differential in Task 6. **Born-green pins name their reddening mutation** (e.g. "delete the `is_diagonal(along)` conjunct -> straight-capture cell flips legal").

## Settled design decisions (the note's S2.4 movement residue, decided here)

Promoted into `decisions.md` in Task 8. These extend rung-1's "Boards and cells" / "Component sets".

1. **The move is `step(from : cell, along : dir)`** — a minted direction domain, **not** `(from : cell, to : cell)`. Rationale is S2.4's, verified against the oracle: `(from,to)` declares 4096 ids of which ~320 are ever legal (~3700 permanently-dead ids that propagate to every later movement rung); `(from,dir)` is 1:1 with OpenSpiel's `cell*12+...` encoding. Breakthrough is the direction-domain witness exactly as roadmap.md predicts (that residual is **not** re-homed).
2. **The direction domain (`dir`) is a SEPARATE per-game named-member source minted by the grid family — NOT in `game.positions`** (framing check, Task 1). Members are the **seat-relative forward directions** `{ahead, ahead_left, ahead_right}` (3), resolved to absolute offsets per player by the frame. Keeping it out of `game.positions` is load-bearing: `cell` rides `positions` and `_position_types` (typecheck.py:859) maps members-named -> `TCell`, while the zone-index wall (`_resolve_zone`), the quantifier wall (`_check_domain_query`) and the for-each wall (`_ITERATION_ROLES`) all admit only `positions`/known-roles. So a non-position `dir` gets its exclusions **for free** — `zone[dir]`, `any dir where`, `for each dir` are all rejected by the existing walls with **no new wall**, and it does not collide with `TCell` (so `along is a1` is rejected, not silently accepted). It rides only the **move-parameter enumeration** (a new `DomainSources.directions` sibling that `enumerate_domain`/`param_domain`/`_vocab_entries` also consult) + IR + encoding. Its members are **not** expression-nameable (no direction literals — `is_diagonal(along)` reads the declared diagonal flag; naming `ahead` stays an unknown-name diagnostic, the cell-literal twin). Name collisions walled: `dir` vs a declared `positions {}` name, vs a built-in role; orthogonal to the turn-order `direction:` clause / `DIRECTION_VALUES{left,right,across,hold}` / `GAME_DIRECTIONS{clockwise,counterclockwise}` (**`direction` is a reserved word** — the domain is named `dir`, never `direction`; no-interaction pinned, not assumed).
   - **The direction VALUE TYPE requires a closed-domain sweep of the `Type` union** (framing check's key risk): unlike the AST node unions, `Type` has **no `assert_never`** — it is handled by permissive isinstance-chains (`unify`, `assignable`, `subscriptable`, `_type_name`), so a brand-new `TDir` would fall through the type walls **silently** (the [[permissive-top]] defect class). The grid's centerpiece for Task 1 is therefore `dir`-value x every `Type`-consumer -> designed accept/reject, proving no permissive fall-through (subscript, ordering, membership, cross-type equality all reject; move-param/dir-vs-dir/verb-arg accept). Sidestep to weigh in Step 3: type directions as `TEnum("<tag>")` (already Type-swept) **without** binding member names (preserves "no literals") + enumerate from the `directions` source — decide by which is fewer honest walls; the grid is type-agnostic.
3. **Effect form: total `neighbor(from, along, actor) : cell` + `has_step(from, along, actor) : bool` + `is_diagonal(along) : bool`.** Verified pre-decision: guard `and` short-circuits (`evaluate.py::_binop`, Python `and`) and `square[<call-expr>]` index-parses (`index_expr: "[" expr "]"`). So the guard orders `has_step(...)` before any `neighbor(...)` read, and `neighbor` is a total function with an **off-board backstop** (raise, unreachable because every call site is `has_step`-gated: the guard by short-circuit, the effect by guard-passed). Prose reads `square[neighbor(from, along, actor)]` directly.
4. **Per-player frames live in `BoardEntry`.** The grid family carries, per direction, a `(d_row, d_col)` offset for player 0 and the seat-flip for player 1 (or equivalently one offset table + a per-player sign) plus a `diagonal` flag. `neighbor`/`has_step` compute geometry from cell coords + the actor-resolved offset (generated, not a literal table — the `lines(k)` precedent).
5. **Regions `home(player)` and `far_row(player)` are grid-family cellsets.** `home` = the player's back two ranks (the 16-piece setup array — the roadmap's named witness for the quantifier/iteration lift); `far_row` = the rank at the far edge of the player's frame (the opponent's back row = the reach goal). Both computed from the grid + frame. Region genericity beyond breakthrough's two (arbitrary-depth home, `crownhead`, etc.) is deferred to its witness (roadmap line). A region types as `TCollection(TCell)` — the **same** cell-collection the `cell` collection-quantifier noun already iterates, so `any cell in far_row(actor) where ...` needs no new noun.
6. **Setup uses `for each cell`.** Add `cell` to `_ITERATION_ROLES` (lift the `positions_for_each` wall for `cell` only; `column`/other integer positions stay walled — no witness). Setup: `for each cell c: if c in home(actor) { move one piece from reserve[actor] to square[c] }`, using `cell in <cellset>` membership. `for each cell in <cellset>:` (a collection for-each) is **not** added — the bare role-lift + membership covers setup with less grammar; recorded as a residual.
7. **Displacement capture is two public kernel movements.** In the effect, when the diagonal target holds an enemy: `move one piece from square[dest] to captured[opp]` (the displaced piece), then `move one piece from square[from] to square[dest]` (the mover). Both emit at the existing movement sites. `captured[player] : PlayerPile<player>` is public.
8. **Two termini, both encoded.** `until (any player where result[player] is 1) or (any player where pieces_left[player] is 0)`. `result[player] in {+1,0,-1}` set in the effect (reach: `if dest in far_row(actor)`; wipe-out: when a capture drives the opponent's `pieces_left` to 0). `pieces_left[player] : Integer = <16>`, decremented for the opponent on capture. Returns match the oracle's `+1`/`-1` by construction.
   - **The opponent is named by a game `function opponent_of(p : Player)`, NOT by `for each player p: if p is not actor`.** That idiom typechecks and runs but its body is DEAD: `runtime/execute.py::_for_each` runs a seat-role body under `ctx.acting_as(member)`, so inside `for each player p` the `actor` pronoun IS `p`, making `p is not actor` always false (and `if p is actor {A} else {B}` silently drops `B`). Measured, not argued: the drafted idiom left both scores `0`; `let w = actor` first (tic-tac-toe's spelling, and why it writes that) marked the non-actor correctly. **Task 8 must not promote this idiom into decisions.md.** A separate concern, recorded and out of rung-2 scope: the always-false guard is silently dead rather than walled — the accepted-but-ignored class.
9. **`side_of(actor)` is a game `function`** connecting seat to piece side for the two places that need it (the guard's "`from` holds my piece", and result assignment). **Verified against the landed tree:** the spelling is `function side_of(p : Player) = if p is 0 then <side0> else <side1>` — the param type is **`Player`** (capitalized), and `p is 0` (Player-vs-integer-literal) typechecks (a guard reading `top_of(square[c]).side is <side>` also checks clean). No state fallback needed. "Enemy at dest" = target not empty and its side is not `side_of(actor)`. (The wipe-out decrement uses `opponent_of`, NOT a `for each player` guard — see decision 8: that idiom typechecks but is a runtime no-op. "Verified accepted" there meant type-level only; the semantic check is what caught it.)
10. **Cell literals STAY walled; re-home the roadmap prediction.** Breakthrough's region-driven setup and quantifier win name **zero** individual cells, so roadmap.md's prediction that breakthrough witnesses cell constants is falsified. Keep the wall; move that residual's witness forward (a later game whose rules name a specific square) in the same PR (spec-not-history; the advisor's flagged correction). Same for direction literals.

---

### Task 1: The movement-direction domain (`dir`) end to end

**Design settled by the framing check** (see the scratchpad axes): `dir` is a **separate per-game source** (a new `DomainSources.directions` sibling of `positions`), NOT a `PositionDecl` in `game.positions`. Consequence — the three exclusions are FREE (no new wall): `zone[dir]` (the zone-index wall admits only `in positions`), `any dir where` (the quantifier wall validates against `game.positions`), `for each dir` (`_ITERATION_ROLES`). The **real** work is (a) wiring `dir` into the move-parameter enumeration only, and (b) the `Type`-union closed-domain sweep, because `Type` has **no `assert_never`** (permissive fall-through risk).

**Files:**
- Modify: `cardlang/board_domains.py` (add a sibling `directions_of(game)` seam + a `DIRECTION_DOMAIN` const beside `BOARD_DOMAIN`; the two are minted together by the board)
- Modify: `cardlang/stdlib/boards.py` (`BoardEntry.directions()` — the member names; grid family mints them)
- Modify: `cardlang/resolve.py` (`_resolve_board` also mints the `dir` source; collision walls extend `_reserved_domain_names` so `dir` cannot clash a `positions {}` name / built-in role; `_check_move_params` (3111-3197) admits `dir` as a legal move-param type)
- Modify: `cardlang/domains.py` (`DomainSources.directions` field; `enumerate_domain`/`role_static_members`/`param_domain` consult it for move-param candidates — the sibling branch to `in positions`), `cardlang/types.py` (the direction value type — new `TDir` **or** reuse `TEnum` per decision 2's sidestep)
- Modify: `cardlang/typecheck.py` — **the `Type`-consumer sweep**: `type_from_name` maps `dir` -> the direction type; then audit every `Type`-consuming site for the new type (`unify`, `assignable`, `subscriptable`, `_type_name`, `_check_equality_operands` 1433, `_check_ordering_operands` 1488, `_check_membership_operands` 1564, subscript-key 1913-1935, assign-key 2221-2233) so each **rejects** the operations directions don't support instead of falling through permissively
- Modify: `cardlang/ir.py` (`_position`-twin emits the `dir` members), `cardlang/runtime/{driver,mechanics}.py` + `cardlang/openspiel/encoding.py` (`driver`/`encoding` build the `directions` source from the AST — identical by construction, the no-drift twin of `position_domains_of`; `_vocab_entries`/encode/decode/match handle a `dir` param value)
- Tests: `tests/test_direction_domain.py` (new; ledger), `tests/rejections/` probes

**Interfaces:**
- Produces: a `board: grid(8, 8)` game exposes a move-parameter domain `dir` with 3 named members in a fixed order; `step(from : cell, along : dir)` enumerates `cells x 3` vocab combos with fixed adapter ids; `along` carries the direction type; `zone[along]`, `any dir where ...`, `for each dir` are all rejected by the existing positions/roles walls (free); `along is a1` (dir-vs-cell), `along < along2` (ordering), `along[x]` (subscript) are type errors (the sweep proves no permissive accept); a direction member is not expression-nameable.

- [ ] **Step 1: The grid, red.** GRID 1 (the centerpiece): `dir`-typed value x every `Type`-consumer (the closed set enumerated by the framing check) -> designed accept/reject, `xfail(strict=True, raises=...)` per cell before the type exists. GRID 2: use-position of the name `dir` (move-param accept; zone-index/quantifier/for-each/literal reject). GRID 3: minting/collision. Author expected outcomes from the reconciled axes (scratchpad), run red. Rejection fixtures: `direction_as_zone_index` (`sq[along]`), `direction_quantifier` (`any dir where`), `direction_literal` (`along is ahead`), `direction_vs_cell` (`along is a1`), `direction_collides_positions` (`positions { dir : ... }`). Confirm the turn-order `direction:` path untouched — a born-green pin whose reddening mutation (rename the domain to `direction`) is recorded.
- [ ] **Step 2: Implement.** Mint the `directions` source; wire the move-param enumeration; add the type + the **full `Type`-consumer sweep** (every site handles the direction type explicitly — no permissive fall-through). Follow each owning pass's `Contract` before placing a check.
- [ ] **Step 3: Full gates + byte-identity** (TTT + Klondike/FreeCell IR and playouts untouched — the `positions`/integer paths are not widened; `directions` is a disjoint new source).
- [ ] **Step 4: Commit** `feat: the movement-direction domain — a separate named-member move-parameter source (dir), with the Type-consumer sweep`

### Task 2: Grid-family frames, directions, and regions (`BoardEntry` grows)

**Landed by Task 1 (`8f3d83c`):** `BoardEntry.directions()` returns the member NAMES only — `("ahead", "ahead_left", "ahead_right")`, that fixed order. `dir` is typed `TDir` (renders `"Dir"`), a separate `DomainSources.directions` source, usable ONLY as a move-param (rejected everywhere else at resolve/typecheck — verified). Task 2 grows `BoardEntry` with the DATA behind those names: per-direction offsets (`ahead` = straight forward, `ahead_left`/`ahead_right` = the two forward diagonals), a `diagonal` flag (ahead False, the others True), the per-player frame that flips the offsets seat-opposite, and the `neighbor`/`has_step` geometry + `home`/`far_row` regions. The seat-relative `left`/`right` convention is internally-consistent-but-arbitrary; Task 6's `to_native` pins it against the oracle. Keep `directions()` returning the same names.

**Files:**
- Modify: `cardlang/stdlib/boards.py` (`BoardEntry` gains direction offsets + diagonal flags, per-player frame resolution, `home`/`far_row` region computations, `neighbor`/`has_step` geometry methods; integrity pins in `__post_init__`)
- Test: `tests/test_boards_registry.py` (extend; ledger)

**Interfaces:**
- Produces: `BoardEntry` methods `directions() -> tuple[str,...]`, `is_diagonal(dir) -> bool`, `neighbor(cell, dir, player) -> str | None` (None off-board — the registry-internal partial; the Builtin verb wraps it total-with-backstop), `has_step(cell, dir, player) -> bool`, `home(player) -> tuple[str,...]`, `far_row(player) -> tuple[str,...]`. All generated from the grid args + declared offsets.

- [ ] **Step 1: Audit.** Domain = grid args x {directions, frames, regions} integrity properties: every direction offset applied to some in-bounds cell lands in-bounds for some frame (no dead direction); `is_diagonal` total over directions; `neighbor` consistent with `has_step` (`has_step` iff `neighbor is not None`); frames are seat-opposite (player-1 offset = the row-flip of player-0); `home`/`far_row` subsets of cells, disjoint, `far_row` = the opposite frame's `home`-back-rank. Residual rows recorded: `crownhead`, arbitrary-depth home, jump-triples (draughts), track frames (backgammon) deliberately absent — roadmap lines.
- [ ] **Step 2: Failing tests**: grid(8,8) directions == the 3 names; `neighbor("a1","ahead",0)`/etc. against a hand-computed table (both frames, edge cells -> None); `home(0)`/`home(1)`/`far_row(0)`/`far_row(1)` == the explicit rank sets; the integrity sweep parametrized over several grids; `far_row(0) == home(1)`'s back rank. Run; expect failure.
- [ ] **Step 3: Implement + integrity pins + run + mypy. Commit** `feat: grid-family frames, directions, and home/far_row regions with integrity pins`

### Task 3: Class-1 movement and region stdlib verbs

**Files:**
- Modify: `cardlang/stdlib/signatures.py` (`neighbor: Sig((TCell,TDir,TPlayer), TCell)`, `has_step: Sig((TCell,TDir,TPlayer), TBool)`, `is_diagonal: Sig((TDir,), TBool)`, `home: Sig((TPlayer,), TCollection(TCell))`, `far_row: Sig((TPlayer,), TCollection(TCell))`), `cardlang/runtime/stdlib.py` (dispatch arms + impls reading `ctx.rs.board`, the `_lines` twin, each with a typed `RuntimeError` naming `board:` when boardless; `neighbor` off-board backstop), `cardlang/stdlib/functions.py` (add all five to `BOARD_ONLY_CALL_FUNCS`, pinned total against `STDLIB_CALL_FUNCS`)
- Modify: `cardlang/runtime/stdlib.py` (occupant/side helper if the game can't express "enemy at dest" from `top_of` alone — decide in audit; prefer expressing it in the game to avoid a verb)
- Tests: `tests/test_movement_verbs.py` (new; ledger), `tests/rejections/` probes

**Interfaces:**
- Consumes: `BoardEntry` methods (Task 2), `TDir`/`TCell` (Task 1). Produces: the five verbs callable in a board game, each a static diagnostic in a boardless game (the classification pin — `lines`'s twin), correct arity/type-checked, `home`/`far_row` yielding cellsets the `cell` collection quantifier iterates.

- [ ] **Step 1: Audit.** Domain = the five verbs x {board game, boardless game, arity, arg types}. `BOARD_ONLY_CALL_FUNCS` total: every `STDLIB_CALL_FUNCS` member classified generic / deck-only / board-only by an explicit table assertion (sweep the whole classification class — the deck-only/board-only twin). Probes: each verb in a boardless game; `neighbor(a1)` wrong arity; `is_diagonal(a1)` (TCell for TDir); `home(a1)` (TCell for TPlayer).
- [ ] **Step 2: Failing tests** (an inline board witness game): each verb's value on a scripted state; the boardless rejections; the classification-total pin. Run; expect failure.
- [ ] **Step 3: Implement** (read the owning pass Contract before each wall). Full gates + byte-identity (no card game calls these). **Commit** `feat: class-1 board verbs — neighbor/has_step/is_diagonal/home/far_row (BOARD_ONLY)`

### Task 4: `for each cell` iteration + `cell in <cellset>` membership

**Files:**
- Modify: `cardlang/domains.py` (add `cell` to the `_ITERATION_ROLES` / `iterable` column), `cardlang/resolve.py` (binder registration for `for each cell`; membership noun), `cardlang/typecheck.py` (`for each cell c` binds `c : TCell`; `TCell in TCollection(TCell)` membership types `TBool`), `cardlang/runtime/evaluate.py` + `execute.py` (iterate `rs.position_domains["cell"]`; membership over an evaluated cellset)
- Tests: `tests/test_cell_iteration.py` (new; ledger), rejection fixtures

**Interfaces:**
- Produces: `for each cell c: <stmt>` iterates the board's cells (binder `c : TCell`); `c in home(actor)` / `c in far_row(actor)` membership. `for each column c` stays walled (integer positions — no witness); `for each cell c in <expr>` (collection for-each) stays grammatically inexpressible (residual).

- [ ] **Step 1: Audit.** Domain = iteration roles x {cell (lifts), column/integer-position (stays walled), player (unchanged)}; membership `TCell in TCollection(TCell)` vs the wrong-element cases. The `positions_for_each` fixture (currently `for each column`) stays red for `column`; add `cell_iteration_ok` positive + `for_each_integer_position_still_walled` + `cell_membership_wrong_element`. Cross-reference the existing `_ITERATION_ROLES` wall (backstop comment names it).
- [ ] **Step 2: Failing tests**: a 3x3 inline game placing a piece on each cell of a scripted region via `for each cell` + membership; the walls. Run; expect failure.
- [ ] **Step 3: Implement; full gates + byte-identity. Commit** `feat: for each cell iteration + cell-in-cellset membership (the positions_for_each lift, cell only)`

### Task 5: The breakthrough corpus game

**Files:**
- Create: `docs/games/breakthrough.cardlang`, `docs/games/breakthrough.md` (readable twin — a non-player can play a hand; the variant pin: 2 players, 8x8, player-0 first, move one square straight-or-diagonal forward, capture diagonally only, reach the far row OR wipe out the opponent to win; oracle note)
- Modify: `docs/games/_candidates.md` (graduate the breakthrough entry, leave the ladder intro)
- Test: `tests/test_playout_breakthrough.py` (new)
- Modify: `cardlang/runtime/values.py` (`breakthrough_men` component set: axes `side=[<side0>,<side1>]`, `kind=[man]`, 16 each) + `cardlang/stdlib/values.py` (size)

**Interfaces:**
- Consumes: every prior task. Produces: `cardlang_breakthrough` auto-registered (glob), typechecking clean, playable to termination.

- [ ] **Step 1: Audit** the component set (the `xo_marks` twin: two-axis, multiplicities) + verify `p is 0` player-literal comparison typechecks for `side_of` (else the state fallback, decision 9). Write the game (guard/effect per the locked design and the movement-legality grid; setup via `for each cell`; termini per the oracle facts). If any landed spelling differs from a sketch, the tests + audit artifacts are the spec of record — adjust the game.
- [ ] **Step 2: Corpus docking** — `test_typecheck_corpus.py` (glob), `openspiel_ready/test_coverage.py` will DEMAND a proof module (red until Task 7 — land Tasks 5-7 as one green push), fuzz grid grows by one game (`tests/fuzz/test_fuzz.py`; record any genuine finding properly, never EXCUSED). Ranking-conventions matrix unaffected (piece set, outside the `DECKS` view — assert by running).
- [ ] **Step 3: Playout test** (`tests/test_playout_breakthrough.py`): random-chooser playouts over 100 seeds asserting per-decision invariants (alternation until terminal; every step lands on an in-bounds forward cell; captures conserve pieces into `captured[opp]`; terminal `result in {(1,-1),(-1,1)}`, never a draw; board+captured conserve 32 men) plus in-process hash-independence (two runs, same final board).
- [ ] **Step 4: Full gates. Commit** `feat: breakthrough — the movement rung enters the corpus`

### Task 6: Native-oracle differential (reuse the walker + breakthrough instance)

**Files:**
- Create: `tests/test_differential_breakthrough.py`
- Reuse `tests/native_oracle.py::walk_paired_alternating` verbatim (perfect-info alternating, no chance — breakthrough is exactly its case; do not modify it)

**Interfaces:**
- Produces: `to_native(("step", cell, dir))` -> `cell_idx*12 + dir_idx*2 + capture`, computing `cell_idx` from our `(file,rank)` to the oracle's top-0 row (`row = rows - rank`, `col = file`), mapping our seat-relative `dir` to the oracle's absolute per-player dir index (**the specific per-seat slots the sketch guessed are superseded -- see the Task 2 correction below**), and the `capture` flag from whether our destination holds an enemy in the current state. `assert_outcomes_agree` compares induced win/loss; breakthrough additionally asserts exact `returns` equality (`result` designed to match +1/-1).
  - **Task 2 correction (landed offsets diverge from this sketch).** Task 2 landed player 1's frame as the exact **180-degree rotation** of player 0 (`_GRID_DIRECTION_OFFSETS` in `cardlang/stdlib/boards.py`, negated by `_offset` via `_player_sign`); p0's `home` is ranks 1-2 and `far_row` is rank 8 (p0 advances toward higher ranks). Two consequences for `to_native`, one verifiable now and one not:
    1. **The diagonals cross between seats on the file axis** (which maps straight to the oracle's `col`, no flip): p1 `ahead_left` has `dcol=+1` and p1 `ahead_right` has `dcol=-1` -- the opposite of p0. The oracle distinguishes its diagonals by column sign, so a naive "+3" on the seat-relative slot sends p1's `ahead_left` to the WRONG oracle diagonal. Derive `dir_idx` by matching the actor-resolved `(row, col)` offset to the oracle's `kDirRowOffsets`/`kDirColOffsets`, never by adding 3 to the seat-relative slot.
    2. **Which seat owns oracle group {0,1,2} vs {3,4,5} is NOT determinable at Task 2** -- it turns on the `row = rows - rank` top-0 flip *together* with the seat mapping, which the differential itself establishes. Do not trust the old sketch's `p0: ahead_left->0, ahead->1, ahead_right->2` slots either; derive the whole map from the offsets and confirm it against the native oracle.
    This is self-catching -- a wrong map makes the differential's legal-set comparison FAIL, not silently pass -- but is the landmine the plan sketch buried. is_diagonal is unaffected (both diagonals capture, for both seats).

- [ ] **Step 1: Write the failing differential**, three coverage layers, recorded in the docstring:
  1. **Exhaustive shallow prefix walk** (breakthrough branches ~22; depth 2-3, measured) comparing mapped legal-action SETS with native at every node — this is where the **movement-legality grid** is verified against the oracle for real positions (empty/enemy/friendly/off-board x 3 dirs all arise near the opening).
  2. **Scripted terminus lines**: a constructed history where player 0 reaches the far row (assert native terminal + returns `[1,-1]`); a player-1 reach; and a **wipe-out** line (capture the opponent's last piece before any reach — assert native terminal + returns, proving decision 8's second terminus).
  3. **Random full trajectories**: 200 policy seeds to terminal, exact `returns` equality, and the sample must contain both p0-wins and p1-wins (the GOPS both-branches discipline).
- [ ] **Step 2: Run** — FAIL before Task 5's game, PASS after; on divergence the assertion carries seed/step/board witness. Budget: well under 60s (if the shallow walk is slow from O(n^2) replay, drop one ply and record the reduction).
- [ ] **Step 3: Commit** `test: native-oracle differential for breakthrough (legality grid + both termini verified vs the oracle)`

### Task 7: The `openspiel_ready` proof module

**Files:**
- Create: `tests/openspiel_ready/test_breakthrough.py`

**Interfaces:**
- Consumes: `ReadinessProofs`, `GameSpec`, the partition helpers — the TTT module (`test_tic_tac_toe.py`) is the two-observer perfect-information template.

- [ ] **Step 1: Write the module** — `class TestReadiness(ReadinessProofs)` with `spec = GameSpec("cardlang_breakthrough", "breakthrough.cardlang", hidden_zone="captured", depth=<measured>, swap_axis="any", adapter_terminal_steps=<measured reach line + slack>)` and the perfect-information overrides (TTT's honest-degeneracy pattern for BOTH observers):
  - indistinguishability override: at a replayed pause, for EACH player no populated zone projects below identity (`hidden_cards == 0`), both info sets singletons; `record(degenerate="perfect information — no hidden pair for either observer")`.
  - soundness override: perturb a visible piece (a board piece and a `captured` piece) and assert BOTH observers' info states change.
  - Inherited: per-visible-fact matrix (load-bearing — every zone x both observers at identity), seed/rng non-observability, perfect recall, adapter agreement to Terminal with **returns equality**, pyspiel conformance.
  - Dedicated: `test_moves_are_public_identity_events` (every move/capture event carries full piece identity, both logs agree); `test_no_shuffle_means_seed_degeneracy` (breakthrough deals no random hand — 3 seeds, byte-identical info states along one history; the adapter root-chance caveat is the stage-3 residual, roadmap line).
- [ ] **Step 2: Run the full `openspiel_ready` suite** — the new module green, `test_coverage.py` green (name matches the registry), all card + TTT modules untouched and green.
- [ ] **Step 3: Commit** `test: breakthrough readiness proofs — two-observer perfect-information degeneracy, adapter + conformance + returns`

### Task 8: Docs promotion + walls bookkeeping

**Files:**
- Modify: `docs/decisions.md` ("Boards and cells" grows a **movement** section in spec voice: the `dir` domain, `step(from,along)`, the frame/region model, `neighbor`/`has_step`/`is_diagonal`/`home`/`far_row`, displacement capture, the two termini, `for each cell`; cross-reference the query register and "Position domains")
- Modify: `docs/library.md` (grid family's directions/frames/regions + the five verbs in the stdlib catalogue; `breakthrough_men` component set)
- Modify: `docs/roadmap.md` — **lift** the `for each cell` residual (cell only; `column`/integer-position and collection-for-each stay); **lift** the movement-direction-domain residual (breakthrough witnessed it); **RE-HOME** the cell-literal witness (breakthrough named no cell — falsified prediction, move witness to a later game) and the direction-literal residual; add new residuals: seat-relative-vs-absolute directions (if the choice was made, record the road not taken as a wall only if a construct is inexpressible), region genericity beyond `home`/`far_row`, sliding/multi-step moves (draughts/chess), collection-for-each
- Modify: `docs/design-notes/board-topology.md` (S5: the movement surface-residue now settled -> pointer to decisions.md; the ladder and stages 3-7 stay; rung 2 marked by its corpus file existing — no "DONE" markers)
- Check (no edit expected): `docs/model.md` (Piece/movement row already covers it — verify), `docs/kernel-migration.md` (no Python escape hatch added — nothing to record), `docs/appendix.md` (stable table — do not update), the open-questions files (their stages are later — untouched)

- [ ] **Step 1: Write the decisions.md movement section** FROM the tests (every claim matches landed behaviour). Follow the existing register (definitional prose + fenced examples + walls-as-behaviour, cross-refs by section name).
- [ ] **Step 2: Sweep the games** — `git diff docs/games/` shows only breakthrough + `_candidates.md` (no card/TTT changes).
- [ ] **Step 3: Run `tests/test_doc_snippets.py`** (decisions.md fenced blocks are pipeline-checked — new `cardlang-fragment` blocks need recipes) and the full suite.
- [ ] **Step 4: Commit** `docs: promote rung-2 board movement into the spec (decisions/library/roadmap)`

### Task 9: Final gates + PR

- [ ] **Step 1: Re-run the surface-totality audit ledgers** (skill Step 4): every ledger's residual rows have walls + roadmap lines; the movement-legality grid's born-green pins name their reddening mutation; confirm no ledger's domain was read off its implementation (fresh-context framing held).
- [ ] **Step 2: Full local CI**: `.venv/bin/mypy` (bare) and `.venv/bin/python -m pytest -q` from the worktree root with `PYTHONPATH` set — both green, run as written, no subsetting. Confirm the suite summary line (`N passed`), not a wrapper exit.
- [ ] **Step 3: Repo review pass**: run the `cardlang-code-review` skill over the branch diff; fix or explicitly answer every finding.
- [ ] **Step 4: Push + PR** onto `main` titled "Board topology rung 2: breakthrough against stage 2" — body: the stage-2 movement scope, the info-set acceptance evidence (byte-identical card+TTT corpus, two-observer proof module, native-oracle differential with both termini), the completeness ledgers' locations, the movement-legality grid, the recorded/lifted/re-homed residuals, and the note that rung 3 (backgammon — the chance rung) is next per the ladder. **Do NOT self-merge** (Ben reviews and merges).

## Execution notes for the orchestrator

- Task order is dependency order; Tasks 5-7 land as one green push (`test_coverage.py` couples the game file to its proof module).
- Tasks 1, 3, 4 touch shared machinery — run the 8 IR goldens + TTT playout/proof modules + full suite after EACH, not just at the end.
- Each implementer subagent gets: this plan's task text, the relevant explorer facts (file:line anchors in the task), the oracle facts above, and the instruction to read the owning pass's `Contract` docstring before placing any check.
- If landed surface diverges from a sketch (spellings, exact messages, the seat-relative-vs-absolute direction choice, `side_of`'s form), the tests + audit artifacts are the spec of record; update this plan file inline when it happens so later tasks read the truth.
