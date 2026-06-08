# OpenSpiel adapter (Hearts) — design

**Date:** 2026-06-07
**Status:** Approved design; ready for implementation.
**Goal:** Prove invariant #0 — that the DSL's IR/runtime can drive OpenSpiel — by
wrapping one real game (Hearts) as a registered `pyspiel.Game` that passes
OpenSpiel's own API/consistency tester and plays random rollouts to terminal with
correct returns and perfect-recall information-state strings.

## 1. Why

Everything in the project assumes the games can become OpenSpiel
information-set game trees (the stated target runtime), but nothing has
validated it. OpenSpiel requires a **finite, enumerable action space** and a
**steppable, cloneable** `State`; our runtime is a run-to-completion playout
driver that resolves every decision through a synchronous `chooser` callback.
This adapter bridges the two and turns "the IR can drive OpenSpiel" from an
assumption into a passing test.

## 2. Scope

**In:** Hearts only, registered as a `pyspiel.Game`; `current_player`,
`legal_actions`, `apply_action`, `is_terminal`, `returns`, `clone`,
`information_state_string`, and chance handling — enough to pass
`pyspiel.random_sim_test` and run random rollouts.

**Out (noted, not gaps):** information-state *tensors*; explicit per-deal chance
nodes; a *general* (all-games) action encoder; running a solver/bot;
observation (vs information-state) APIs.

## 3. Approach (decided)

- **Control inversion = re-simulation from action history.** The OpenSpiel
  `State` is `(seed, history: list[int])`. Any query re-runs the game with a
  *replay/pause* chooser that returns recorded actions in order and raises a
  `_Pause` at the first decision beyond the history. This makes `clone()` free
  (copy two values) — the property OpenSpiel exercises most — at an O(n²) cost
  acceptable for this proof. Rejected: greenlet/thread suspension (can't clone a
  suspended interpreter, so they need re-sim for `clone()` anyway).
- **Chance = a recorded seed at a root chance node.** A root chance node fixes a
  seed; `random.Random(seed)` reproduces every shuffle (including per-hand
  reshuffles) under replay. Implemented as `ChanceMode = EXPLICIT_STOCHASTIC`
  with K=4096 equiprobable seed outcomes (chosen over `SAMPLED_STOCHASTIC`: it's
  the well-trodden Python-game path — matches the shipped `kuhn_poker` example —
  and keeps `num_distinct_actions = 52` since chance ids live in
  `max_chance_outcomes`; the cost is a finite set of K distinct deals, fine for
  this proof). Rejected: explicit card-by-card chance nodes (52!-scale, large
  runtime change). See `IMPLEMENTATION_LOG.md` for the decision.

## 4. Components

```
cardlang/openspiel/
  __init__.py
  encoding.py   # Card ⇄ action int (0–51); Hearts action space
  replay.py     # re-sim engine: run play_game with a replay/pause chooser → Pause | Terminal
  state.py      # CardlangState(seed, history): the OpenSpiel State API, all via replay
  game.py       # the pyspiel.Game subclass + GameType/GameInfo + register_game
tests/test_openspiel_hearts.py
```

### 4.1 Runtime seam (one small change)
`cardlang/runtime/driver.py`: `play_game(game, rng, tracer=None, chooser=None)` —
accept an injected chooser, defaulting to `random_chooser(rng)` (today hardcoded).
Default behavior unchanged; this is the inversion point.

### 4.2 `encoding.py`
Hearts decisions are all card selections, so the action space is the 52 cards:
`action_id = SUITS.index(suit) * 13 + RANKS.index(rank)`, range 0–51,
`NUM_DISTINCT_ACTIONS = 52`. Functions: `card_to_action(Card) -> int`,
`action_to_card(int) -> Card`. The 3-card pass decomposes into three sequential
single-card actions (§4.3), keeping the space at 52.

### 4.3 `replay.py`
`ReplayChooser(history)` holds a cursor. For any chooser call `(player,
candidates, n)`: consume up to `n` recorded ids from the cursor (each id → the
matching candidate card), removing each from the per-call candidate pool; if the
cursor runs out after `k < n`, raise `_Pause(player, legal_ids)` where `legal_ids`
= the remaining candidate pool as action ids. So **one `n=k` chooser call = k
sequential single-card actions**, uniformly (covers both the n=1 trick play and
the n=3 pass).

`run(seed, history) -> Pause | Terminal`:
- builds `random.Random(seed)` and runs `play_game(game, rng, tracer=capture,
  chooser=ReplayChooser(history))`;
- if a `_Pause` propagates out → `Pause(player, legal_ids, snapshot)` where
  `snapshot` carries what the info-state encoder needs (built from a tracer that
  records the public event log, plus the live zones at pause time);
- if `play_game` returns a `GameResult` → `Terminal(scores)`.

The Hearts game (`hearts.cardlang`) is loaded once and cached.

### 4.4 `state.py` — `CardlangState`
Holds `(seed: int | None, history: list[int])`. `seed is None` ⇒ the root chance
node is unresolved.
- `current_player()` → `PlayerId.CHANCE` if `seed is None`; else `Pause.player`,
  or `PlayerId.TERMINAL` when `run` returns `Terminal`.
- `chance_outcomes()` → K equiprobable seed outcomes `[(i, 1/K) for i in range(K)]`.
- `legal_actions()` → `Pause.legal_ids` (player node) / the chance outcome at the
  chance node.
- `apply_action(a)` → sets `seed` at the chance node, else appends `a` to
  `history`.
- `is_terminal()` / `returns()` → from `Terminal`.
- `information_state_string(p)` → §5.
- `clone()` → copy `(seed, list(history))`.
- `__str__`/`history_str` for debugging.

### 4.5 `game.py`
A `pyspiel.Game` subclass: `GameType` (short_name e.g. `cardlang_hearts`,
imperfect information, sampled-stochastic chance, 4 players), `GameInfo`
(`num_distinct_actions=52`, `max_chance_outcomes`, `num_players=4`, utility
bounds, `max_game_length`), `new_initial_state()`, and `register_game(...)`.

## 5. Information state (perfect recall, per player)

`information_state_string(p)` is built from the re-sim'd world at the pause, from
**p's perspective only**:
- p's dealt hand for the current deal;
- p's own pass selections and the cards p received in the pass;
- the public trick-play log (every played card is public once played), in order;
- accumulated per-hand/per-game scores.

It must **exclude** other players' un-played hand cards and their pass picks (the
pass is sequentialized but strategically simultaneous). Perfect recall: the string
encodes p's entire observed history. **Invariant test:** two states differing only
in another player's hidden cards yield identical `information_state_string(p)`.

## 6. Returns

Hearts is lowest-score-wins; OpenSpiel utilities are higher-is-better and Hearts'
points are constant-sum per hand, so `returns()[p] = mean(final_scores) −
final_score[p]` (recentred to sum to zero). Utility bounds derive from the score
range; `max_game_length` bounded generously (Hearts to 100).

## 7. Testing

- **`pyspiel.random_sim_test`** on the registered game — the conformance gate
  (exercises legal_actions/apply/clone/terminal/chance/info-state).
- **Cross-check:** for a fixed seed, replaying the recorded action sequence
  through the adapter reproduces the native `play_game` final scores exactly.
- **Info-state no-leak** test (§5).
- All tests `pytest.importorskip("pyspiel")` so the core suite is unaffected when
  OpenSpiel isn't installed.

## 8. Dependency / CI

`open_spiel` is an **optional extra** (`[project.optional-dependencies] openspiel`),
not in default `dev`. Local dev/CI is unchanged; the adapter tests skip without
`pyspiel`. A macOS-arm64/cp311 wheel (`open_spiel 1.6.15`) exists, so the work runs
locally. (Enabling the extra in CI to actually run these tests is a follow-up.)

## 9. Risks / known-unknowns

- **pyspiel Python custom-game API** varies by version (subclassing
  `pyspiel.Game`/`State`, `register_game`, exact `GameType`/`GameInfo` fields, how
  sampled-stochastic chance is surfaced in Python, the `random_sim_test`
  signature). The implementation's **first task is a spike** pinning this against
  the installed `open_spiel 1.6.15` before building on it.
- **O(n²) re-simulation** could make `random_sim_test` slow for full Hearts-to-100
  games; mitigate by running the tester with a small number of sims, and/or a
  reduced score target in tests if needed. Logged as a review item if it bites.
- **`RuntimeState` two-phase init** (deferred from PR #2) — this adapter is the
  second construction site (re-sim constructs a runtime per query). The plan may
  fold the config-into-constructor refactor in here; if it adds churn/risk it
  stays deferred. Decision logged either way.

## 10. Integration with project docs

Forward-looking design artifact → lives under `docs/superpowers/specs/`. Settled
outcomes (the runtime `chooser` seam; the OpenSpiel target reached via the IR)
get promoted into `docs/decisions.md` in spec voice once landed. A running
"Decisions to review" list is kept in `IMPLEMENTATION_LOG.md` during the build.
