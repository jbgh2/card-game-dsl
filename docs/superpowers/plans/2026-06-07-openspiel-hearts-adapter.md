# OpenSpiel Hearts Adapter — Implementation Plan

> Tightly-coupled, API-sensitive build; executed inline with TDD (per the
> subagent-driven decision tree: coupled work → manual execution). Conformance
> gate is `pyspiel.random_sim_test`. Final independent code review at the end.

**Goal:** Wrap Hearts as a registered `pyspiel.Game` that passes
`pyspiel.random_sim_test` and plays random rollouts to terminal with correct
returns and perfect-recall info-state strings.

**Spec:** `docs/superpowers/specs/2026-06-07-openspiel-hearts-adapter-design.md`.

**Pinned pyspiel API (from the spike, open_spiel 1.6.15):**
- `pyspiel.GameType(short_name, long_name, dynamics=…SEQUENTIAL, chance_mode=…EXPLICIT_STOCHASTIC, information=…IMPERFECT_INFORMATION, utility=…CONSTANT_SUM, reward_model=…TERMINAL, max_num_players=4, min_num_players=4, provides_information_state_string=True, provides_information_state_tensor=False, provides_observation_string=False, provides_observation_tensor=False, provides_factored_observation_string=False)`
- `pyspiel.GameInfo(num_distinct_actions=52, max_chance_outcomes=K, num_players=4, min_utility, max_utility, utility_sum=0.0, max_game_length)`
- `class G(pyspiel.Game): __init__(self, params=None): super().__init__(_TYPE,_INFO,params or {}); new_initial_state(self)`
- `class S(pyspiel.State): __init__(self, game): super().__init__(game); current_player(); _legal_actions(player)->sorted ascending; chance_outcomes()->[(id,prob)]; _apply_action(action); _action_to_string(player,action); is_terminal(); returns(); information_state_string(player); __str__()`. Clone is handled by C++ via `resample`/copy — Python games override `clone()` is NOT needed if state is reconstructable; but to be safe we keep state as plain copyable fields and DO implement `clone()` if random_sim_test requires it (verify in Task 6).
- `pyspiel.register_game(_TYPE, G)` then `pyspiel.load_game("cardlang_hearts")`.
- Gate: `pyspiel.random_sim_test(game, num_sims=N, serialize=False, verbose=False)`.

---

## Task 1: Runtime seam — `play_game(chooser=)` + `ChooserAbort`

**Files:** `cardlang/runtime/driver.py`, `cardlang/runtime/state.py`. Test: `tests/test_chooser_seam.py`.

- Add to `state.py`: `class ChooserAbort(Exception)` with attributes set by the raiser (`player`, `candidates`) and `rs` attached by the driver.
- `play_game(game, rng, tracer=None, chooser=None)`: use `chooser or random_chooser(rng)`. Wrap the phase-run loop:
  ```python
  try:
      for phase in game.phases:
          run_phase(phase, ctx, hands)
  except ChooserAbort as abort:
      abort.rs = rs
      raise
  ```
- Test: a custom chooser that raises `ChooserAbort` after k calls propagates it with `.rs` set; default `play_game` (no chooser) still works (Hearts playout unchanged — run an existing playout).

## Task 2: `encoding.py`

**Files:** `cardlang/openspiel/__init__.py`, `cardlang/openspiel/encoding.py`. Test: `tests/test_openspiel_encoding.py`.

- `NUM_DISTINCT_ACTIONS = 52`. `card_to_action(card)`/`action_to_card(aid)` using `SUITS`/`RANKS` from `runtime.values` (`SUITS.index(suit)*13 + RANKS.index(rank)`).
- Round-trip test over all 52 cards; out-of-range raises.

## Task 3: `replay.py` — re-sim engine

**Files:** `cardlang/openspiel/replay.py`. Test: `tests/test_openspiel_replay.py`.

- `ReplayChooser`: holds `history` (list of action ids) + a cursor. `__call__(player, candidates, n)`: build `pool = list(candidates)`; pick up to `n` by consuming recorded ids (id→card; remove from pool); if it runs short, raise `ChooserAbort(player, legal=[card_to_action(c) for c in pool], kind=('pass' if n_total>1 else 'play'))`. Record per consumed action `(player, aid, kind)` into `self.observed_log`.
- `HeartsGame` loader: parse+check `docs/games/hearts.cardlang` once, cache.
- `run(seed, history) -> Pause | Terminal`:
  - `Pause(player:int, legal:list[int], rs, observed_log)` on ChooserAbort.
  - `Terminal(returns:list[float])` on normal completion (map GameResult.scores → utilities, mean-recentred).
  - deterministic via `random.Random(seed)`.
- Tests: replay a recorded full game reproduces native `play_game` scores for the same seed; a partial history yields a `Pause` with the right player and legal set (= that player's legal cards).

## Task 4: info-state encoder (in `replay.py` or `infostate.py`)

**Files:** `cardlang/openspiel/infostate.py`. Test: covered by Task 6 no-leak test.

- `hearts_information_state(player, pause) -> str`: canonical string of
  (player's current hand from `pause.rs.zones.instance("hand", player)`, sorted) +
  (the p-observable action log: `[(pl,aid) for (pl,aid,kind) in observed_log if kind=='play' or pl==player]`) +
  (scores from `pause.rs`). Must read ONLY `hand[player]` (never `hand[q≠p]`).

## Task 5: `game.py` + `state.py` — the pyspiel surface

**Files:** `cardlang/openspiel/game.py`. Test: Task 6.

- `K = 4096` seed outcomes (chance). `_TYPE`/`_INFO` as pinned above; `min_utility/max_utility` from Hearts score range (e.g. ±26 per hand × generous hand cap → set wide, e.g. ±200; recentred returns are bounded by that); `max_game_length` generous (e.g. 2000).
- `CardlangHeartsState(pyspiel.State)`: fields `_seed:int|None`, `_history:list[int]`. `current_player` → `CHANCE` if seed None; else re-run `run(seed,history)`: `Pause`→player, `Terminal`→`TERMINAL`. `chance_outcomes` → `[(i, 1/K) for i in range(K)]`. `_legal_actions(p)` → `run(...).legal` (sorted). `_apply_action(a)` → set seed if chance node else append to `_history`. `is_terminal`/`returns` → from `run`. `information_state_string(p)` → Task 4. `clone()`/`__copy__` returns a new state with copied `_seed,_history` (verify random_sim_test passes; add if needed). Cache the `run(...)` result per (seed,tuple(history)) within a call to avoid recomputation.
- `register_game(_TYPE, CardlangHeartsGame)` at import.

## Task 6: tests + pyproject extra

**Files:** `tests/test_openspiel_hearts.py`, `pyproject.toml`.

- `pyproject.toml`: add `[project.optional-dependencies] openspiel = ["open_spiel>=1.6"]`.
- All tests start `pyspiel = pytest.importorskip("pyspiel")` and `import cardlang.openspiel.game` (registers).
- `test_random_sim_conformance`: `pyspiel.load_game("cardlang_hearts")`; `pyspiel.random_sim_test(game, num_sims=5, serialize=False, verbose=False)`. (Small num_sims — re-sim is O(n²).)
- `test_returns_crosscheck`: pick a seed; play the adapter with a uniform-random policy recording actions; assert adapter `returns()` equals mean-recentred native `play_game` scores for that seed.
- `test_infostate_no_leak`: construct two states with the same observable prefix but (forced) different hidden opponent hands; assert `information_state_string(p)` equal for the acting `p`. (If hard to force two deals, assert structurally: the info-state string for p contains no card from `hand[q≠p]` at a pause.)
- `test_perfect_recall_distinct`: two different observable histories for p give different info-state strings.

## Task 7: verify + green

- `python -m mypy` (add `cardlang/openspiel` to the strict set; pyspiel is untyped → `[[tool.mypy.overrides]] module=["pyspiel","pyspiel.*"]` ignore_missing_imports, plus the openspiel package may need `disallow_untyped_defs` relaxation only where subclassing pyspiel forces it — prefer typed).
- `python -m pytest -q` (full suite incl. new tests; openspiel tests run since pyspiel installed).
- Final independent code review (subagent) over the diff; then finish branch.

## Notes / decisions (also in IMPLEMENTATION_LOG)
Explicit-stochastic K-seed chance (finite deal set); Hearts-specific info-state;
generic `ChooserAbort` seam; `open_spiel` optional extra; RuntimeState refactor
stays deferred (adapter goes through `play_game`). O(n²) re-sim → small num_sims.
