# Declared parameter domains (Rank/Player) + arity-N move types — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a `move_type` take N declared parameters ranging over the fixed-from-type domains `Rank` and `Player` (in addition to today's `Suit`/`Card`), enumerate them (guard-filtered cross-product) under a plain `offer`, and promote four-player **Go Fish** into the corpus as the OpenSpiel-proven totality witness.

**Architecture:** Generalize the existing single-parameter enumeration (`mechanics.AuctionForm.candidates`) into a fold over a parameter *tuple*, reuse it at the `offer` decision site, and grow the derived OpenSpiel action space (`encoding.ActionSpace`) into the cross-product. No new kernel mechanism: a decision stays one flat candidate list + one chooser draw + one uniform public announce. Bounded-`Integer` parameters and the `choose` reconciliation are out of scope (deferred; statically rejected with a message).

**Tech Stack:** Python 3.11, `lark` (grammar in `cardlang/grammar/cardlang.lark`), `mypy --strict`, `pytest`, OpenSpiel (`pyspiel`, imported via `pytest.importorskip`).

**Spec:** [docs/superpowers/specs/2026-07-07-move-parameter-domains-design.md](../specs/2026-07-07-move-parameter-domains-design.md)

## Global Constraints

- **Behavior-preserving migration.** Single-parameter and nullary moves must stay byte-identical. A candidate value is `None` (nullary), the **bare** value (arity 1, exactly as today), or a **tuple** (arity ≥ 2). Never wrap an arity-1 value in a 1-tuple — that would change every existing vocab key and break goldens.
- **Both CI checks green before any push:** `mypy` (bare — covers `cardlang/` AND `tests/`) and `pytest -q`. Run from the repo root. Some exact-score tests pin `PYTHONHASHSEED=0`.
- **Surface totality** (CLAUDE.md, decisions.md "Surface totality"): every accepted parameter combination is implemented + tested, or statically rejected with a clear message. No parsed-and-ignored surface.
- **Info-set derivation is a first-class acceptance criterion** (CLAUDE.md), not just "it runs". A feature that emits no observations from which its info sets derive is incomplete.
- **Games are the living spec** (maintaining.md rule 2): the `param → params` migration lands with every parameterized-move corpus game re-run green in the same change.
- Branch: `feat/move-parameter-domains` (already created; the design spec is committed there).
- Commit trailer on every commit: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## ⚠ Execution ordering — the info-set gate (READ FIRST)

Task 8's **indistinguishability proof is the load-bearing go/no-go for the whole feature**, not a routine "tune until green" step. The standard greedy-swap harness assumes *legal replay ⟹ indistinguishable to the observer* — **true for trick/betting games, false for Go Fish**: an ask is public and its transfer *count* is observed (`Hand` projects `count_only` to non-owners), so a hidden-card swap that changes how many of the asked rank the target holds produces a world that replays legally but that P can distinguish — a spurious hard failure, not a real leak.

So: **as soon as Tasks 1–4 + 6 (resolve-accept) + 7 (a minimal registered Go Fish) exist, run ONLY `test_indistinguishability_under_hidden_swap` for Go Fish and settle the approach (Task 8) before investing in render polish (Task 5), the dedicated test (Task 9), the `.md` (Task 10), or docs hygiene (Task 11).** Task 5 is cosmetic (a deterministic ugly render still passes every proof) and may run last. The planned fix — restrict swaps to same-**rank**, different-suit pairs — is the correct indistinguishable-world generator here; the fallback (bespoke test + documented caveat, à la Bridge/Tarot) is in Task 8 if that does not hold.

---

### Task 1: Migrate `MoveTypeDef.param` → `params` (behavior-preserving)

The foundational refactor. Mirrors the existing `FunctionDef.params: tuple[MoveParam, ...]`. After this task the grammar *accepts* multi-parameter moves and every reader compiles against a tuple, but N ≥ 2 enumeration is not yet wired (no corpus game uses it, so nothing breaks). All existing games stay byte-identical.

**Files:**
- Modify: `cardlang/ast/nodes.py:680-690` (`MoveTypeDef`)
- Modify: `cardlang/grammar/cardlang.lark:254-258` (`move_type_def`, `move_param`)
- Modify: `cardlang/parse.py:886-890` (`move_param` builder), `cardlang/parse.py:955-969` (`move_type_def` builder)
- Modify (readers, `.param` → `.params`): `cardlang/ir.py:77-88`, `cardlang/openspiel/encoding.py:162-176`, `cardlang/resolve.py:523-565`, `cardlang/runtime/mechanics.py:295-336`, `cardlang/runtime/evaluate.py` (move-param binding, if any), `cardlang/runtime/execute.py:310-331`
- Test: `tests/test_multiparam_move.py` (new), plus the full existing suite as the byte-identical guard

**Interfaces:**
- Produces: `MoveTypeDef.params: tuple[MoveParam, ...]` (empty tuple = nullary). The old `.param` attribute is gone.
- Produces: helper convention — a nullary move has `params == ()`; a single-parameter move has `len(params) == 1`.

- [ ] **Step 1: Write the failing test** (a two-parameter move parses into a 2-tuple)

Create `tests/test_multiparam_move.py`:

```python
from cardlang.parse import parse_text


def _game(move_src: str) -> str:
    return (
        "game G {\n"
        "  players: 4\n"
        "  max_length: 100\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        f"  {move_src}\n"
        "}\n"
    )


def test_two_parameter_move_parses_to_a_tuple() -> None:
    game = parse_text(
        _game("move_type ask(target : Player, rank : Rank) { effect { } }"),
        "test.cardlang",
    )
    mt = next(m for m in game.move_types if m.name == "ask")
    assert [(p.name, p.type_name) for p in mt.params] == [
        ("target", "Player"),
        ("rank", "Rank"),
    ]


def test_nullary_move_has_empty_params() -> None:
    game = parse_text(_game("move_type pass { effect { } }"), "test.cardlang")
    mt = next(m for m in game.move_types if m.name == "pass")
    assert mt.params == ()
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_multiparam_move.py -v`
Expected: FAIL — either `MoveTypeDef` has no `params` (AttributeError) or the grammar rejects the comma (`No terminal matches ','`).

- [ ] **Step 3: Update the AST node**

`cardlang/ast/nodes.py`, `MoveTypeDef`:

```python
@dataclass(frozen=True, slots=True)
class MoveTypeDef:
    """`move_type NAME [(<param> : <type>, …)] { when: <pred> effect { <stmt>* } }` —
    a named, guarded action. ``guard`` is None when the move is always legal;
    ``params`` is empty for a nullary move (the trick/offer form). Parameters
    enumerate in declaration order (leftmost outermost); see decisions.md
    "The Card move-parameter domain"."""

    name: str
    guard: Expr | None
    effect: tuple[Stmt, ...]
    params: tuple[MoveParam, ...] = ()
    span: Span | None = None
```

- [ ] **Step 4: Update the grammar**

`cardlang/grammar/cardlang.lark`, replace the `move_type_def` / `move_param` productions (mirror `function_def`/`func_param` at lines 264-265):

```
move_type_def: "move_type" NAME ["(" move_param ("," move_param)* ")"] "{" [move_when] move_effect "}"
// An optional, comma-separated parameter list; each parameter is drawn from an
// enumerable domain (Suit/Suit?, Rank, Player) or the state-dependent Card
// domain. Their value-domains flatten into one per-turn candidate list.
move_param: NAME ":" payload_type
```

- [ ] **Step 5: Update the parse builders**

`cardlang/parse.py` — the `move_param` builder is unchanged (the parens are literal terminals, already absent from `c`); rewrite `move_type_def` to collect a tuple (copy the `function_def` pattern at line 977):

```python
    def move_type_def(self, meta: Meta, c: list[object]) -> n.MoveTypeDef:
        name = str(c[0])
        guard: object | None = None
        effect: tuple[object, ...] = ()
        for item in c[1:]:
            if isinstance(item, _MoveWhen):
                guard = None if isinstance(item.pred, _Always) else _as_expr(item.pred)
            elif isinstance(item, _MoveEffect):
                effect = item.body
        params = tuple(x for x in c if isinstance(x, n.MoveParam))
        return n.MoveTypeDef(
            name=name,
            guard=guard,  # type: ignore[arg-type]
            effect=effect,  # type: ignore[arg-type]
            params=params,
            span=self._span(meta),
        )
```

- [ ] **Step 6: Update every `.param` reader to `.params` (behavior-preserving, single-value assumption kept)**

At each site, read the sole parameter as `mt.params[0] if mt.params else None` so behavior is identical for today's games. Do NOT add cross-product logic yet (Tasks 3–4). Exact sites:

- `cardlang/ir.py:77-88` `_move_type` — emit a `params` list (mirror `_function`'s line 95):

```python
def _move_type(m: n.MoveTypeDef) -> IRDict:
    return {
        "kind": "move_type",
        "name": m.name,
        "params": [{"name": p.name, "type_name": p.type_name} for p in m.params],
        "guard": _expr(m.guard) if m.guard is not None else None,
        "effect": [_stmt(s) for s in m.effect],
    }
```

- `cardlang/openspiel/encoding.py:162-176` — replace `mt.param` with `p = mt.params[0] if mt.params else None` and use `p` exactly where `mt.param` was used (a single-parameter or nullary reading; the cross-product comes in Task 4).
- `cardlang/resolve.py:523-565` — the two walls read `move_type_defs[name].param`; change to inspect `move_type_defs[name].params` (see Task 6 for the new logic; for now, preserve today's checks over `params[0] if params else None`).
- `cardlang/runtime/mechanics.py:295-336` (`candidates`) — replace `mt.param` with `p = mt.params[0] if mt.params else None`, keeping today's single-value loop (the fold comes in Task 3). `AuctionForm.apply` (line 345) similarly.
- `cardlang/runtime/evaluate.py` — no move-param reader exists (verified: move params bind in `mechanics`/`execute`, not `evaluate`); no change.
- `cardlang/runtime/execute.py:310-331` (`_offer`) — no `.param` read today (offer is nullary-only); no change in this task.

- [ ] **Step 7: IR golden churn — regenerate the affected golden IR files**

The IR now emits `"params": [...]` instead of `"param": {...}`. Update the golden IR fixtures that pin move-type IR:

Run: `pytest tests/ -k "ir" -v` and inspect failures. For each failing golden (e.g. `tests/golden/bridge.ir.json`, `tests/golden/french-tarot.ir.json`, `tests/golden/getaway.ir.json`), regenerate it via the repo's golden-update mechanism (check the test module header for the `UPDATE_GOLDENS`/`--update` convention; e.g. `PYTHONHASHSEED=0 UPDATE_GOLDENS=1 pytest tests/test_getaway_ir.py`). Verify the diff is *only* `param` → `params` shape, nothing semantic.

- [ ] **Step 8: Run the migration guard — full suite byte-identical**

Run: `PYTHONHASHSEED=0 pytest -q` then `mypy`
Expected: PASS. The new `test_multiparam_move.py` passes; every existing game (Bridge `submit_bid`, Schnapsen `play_card`/`declare_marriage`, Skat `declare_suit`, Pinochle `declare_trump_suit`) re-runs green; score goldens byte-identical.

- [ ] **Step 9: Commit**

```bash
git add cardlang/ast/nodes.py cardlang/grammar/cardlang.lark cardlang/parse.py \
        cardlang/ir.py cardlang/openspiel/encoding.py cardlang/resolve.py \
        cardlang/runtime/mechanics.py tests/test_multiparam_move.py tests/golden/
git commit -m "refactor(language): move_type params become a tuple (arity-N AST)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `enumerate_domain` gains `Rank` and `Player`

**Files:**
- Modify: `cardlang/runtime/mechanics.py:198-215` (`enumerate_domain`)
- Test: `tests/test_enumerate_domain.py` (new)

**Interfaces:**
- Produces: `enumerate_domain(type_name: str, *, suits: Sequence[Any], ranks: Sequence[str], players: Sequence[int]) -> list[Any]`. `Suit` → `suits` (+`None` for `Suit?`); `Rank` → `list(ranks)`; `Player` → `list(players)`. `Card` is never passed here (state-dependent; handled in `candidates`). Any other type raises `NotImplementedError` (unreachable — rejected at resolve, Task 6).

- [ ] **Step 1: Write the failing test**

Create `tests/test_enumerate_domain.py`:

```python
from cardlang.runtime.mechanics import enumerate_domain

SUITS = ["clubs", "diamonds", "hearts", "spades"]
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
PLAYERS = [0, 1, 2, 3]


def test_suit_domain_unchanged() -> None:
    assert enumerate_domain("Suit", suits=SUITS, ranks=RANKS, players=PLAYERS) == SUITS


def test_optional_suit_appends_none() -> None:
    assert enumerate_domain("Suit?", suits=SUITS, ranks=RANKS, players=PLAYERS) == SUITS + [None]


def test_rank_domain() -> None:
    assert enumerate_domain("Rank", suits=SUITS, ranks=RANKS, players=PLAYERS) == RANKS


def test_player_domain() -> None:
    assert enumerate_domain("Player", suits=SUITS, ranks=RANKS, players=PLAYERS) == PLAYERS
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_enumerate_domain.py -v`
Expected: FAIL — `enumerate_domain()` takes 1 positional arg / does not accept `suits=`.

- [ ] **Step 3: Implement**

`cardlang/runtime/mechanics.py`, replace `enumerate_domain`:

```python
def enumerate_domain(
    type_name: str,
    *,
    suits: "Sequence[Any]",
    ranks: "Sequence[str]",
    players: "Sequence[int]",
) -> list[Any]:
    """The *static* value-domain a parameterized move ranges over, in a fixed
    order so the flattened candidate list is deterministic.

    `Suit`/`Suit?` are the game's suits (`Suit?` appends `none`, the no-trump
    strain, which ranks last); `Rank` is the game's ranks; `Player` is its
    seats. `Card` is deliberately absent — its domain is state-dependent (the
    actor's live hand, enumerated by `candidates`) and its actions are the
    shared card block. Bounded-`Integer` is rejected at resolve time (deferred),
    so this dispatch is total over what reaches it."""
    base = type_name.rstrip("?")
    if base == "Suit":
        values: list[Any] = list(suits)
        if type_name.endswith("?"):
            values.append(None)
        return values
    if base == "Rank":
        return list(ranks)
    if base == "Player":
        return list(players)
    raise NotImplementedError(f"move parameter domain '{type_name}' not supported")
```

Add `from collections.abc import Sequence` to the imports if not present.

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/test_enumerate_domain.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/mechanics.py tests/test_enumerate_domain.py
git commit -m "feat(language): enumerate_domain gains Rank and Player

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: The multi-parameter fold in `candidates` + `offer` enumeration

Make Rank/Player/multi-param live in the runtime: a parameterized move expands to its guard-filtered cross-product both in an auction `round` (`AuctionForm.candidates`) and under a plain `offer` (`execute._offer`).

**Files:**
- Modify: `cardlang/runtime/mechanics.py:295-348` (`candidates`, `apply`), add shared helpers
- Modify: `cardlang/runtime/execute.py:310-336` (`_offer`)
- Test: `tests/test_offer_enumeration.py` (new)

**Interfaces:**
- Consumes: `enumerate_domain(...)` (Task 2); `MoveTypeDef.params` (Task 1).
- Produces (module-level helpers in `mechanics.py`, importable by `execute.py`):
  - `param_domain(p: MoveParam, actor: Player, ctx: Ctx) -> list[Any]` — the live hand for `Card`, else `enumerate_domain(...)` sourced from `ctx.rs`.
  - `concrete_moves(mt: MoveTypeDef, actor: Player, ctx: Ctx) -> list[tuple[str, Any]]` — the guard-filtered candidate list for one move type; each entry is `(name, value)` where value is `None` (nullary) / bare (arity 1) / tuple (arity ≥ 2).
  - `bind_params(ctx: Ctx, params, value) -> Ctx` — bind a candidate's value(s) as locals.

- [ ] **Step 1: Write the failing test** (a plain `offer` enumerates a two-parameter move's guard-filtered cross-product)

Create `tests/test_offer_enumeration.py`:

```python
from cardlang.parse import parse_text
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game


GAME = """
game G {
  players: 3
  max_length: 50
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { hand[player] : Hand<player> }
  state { done : Integer = 0 }
  phase play {
    deal 2 cards from ... to each hand   // placeholder; see note
    offer to 0 one of [ping]
    done := 1
  }
  winner: highest done
}
move_type ping(target : Player, rank : Rank) {
  when: target != actor
  effect { done := 1 }
}
"""
```

Note: this test asserts the *enumeration* is reachable via `offer`, not full gameplay. Prefer a focused unit test that calls the helper directly rather than a full `play_game` (simpler, no dealing scaffolding):

```python
def test_concrete_moves_is_the_guard_filtered_cross_product() -> None:
    from cardlang.runtime.mechanics import concrete_moves
    from tests.helpers import build_runtime  # or the repo's existing test harness for a Ctx

    # Construct a 3-player Ctx with actor=0; ping(target: Player, rank: Rank)
    # guarded `target != actor`. Expect 2 targets x 13 ranks = 26 candidates,
    # none with target == 0.
    ...
    cands = concrete_moves(mt_ping, actor=0, ctx=ctx)
    assert len(cands) == 2 * 13
    assert all(v[0] != 0 for _, v in cands)          # target != actor
    assert all(isinstance(v, tuple) and len(v) == 2 for _, v in cands)  # arity-2 tuple
```

Look at `tests/test_chooser_seam.py` and `tests/test_playout_*.py` for the established way to build a `Ctx`/runtime in-test; reuse it rather than inventing a new harness. If no lightweight `Ctx` builder exists, drive it through `play_game` on a minimal game with a scripted chooser and assert the announced candidate list.

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_offer_enumeration.py -v`
Expected: FAIL — `concrete_moves` does not exist.

- [ ] **Step 3: Implement the fold + helpers in `mechanics.py`**

Add near `enumerate_domain`:

```python
import itertools


def param_domain(p: n.MoveParam, actor: Player, ctx: Ctx) -> list[Any]:
    """One parameter's value-domain for the acting player. `Card` is the actor's
    live hand, in hand order (state-dependent); the fixed-from-type domains come
    from the deck/seating via `enumerate_domain`."""
    if p.type_name == "Card":
        return list(ctx.rs.zones.instance("hand", actor).cards)
    ranks = [r for r, _ in sorted(ctx.rs.rank_index.items(), key=lambda kv: kv[1])]
    return enumerate_domain(
        p.type_name,
        suits=ctx.rs.suits,           # the game's declared suits (see note)
        ranks=ranks,
        players=list(ctx.rs.seating.players),
    )


def _pack(combo: tuple[Any, ...]) -> Any:
    """A candidate's value: None (nullary), the bare value (arity 1), or the
    tuple (arity >= 2). Arity 1 stays bare so existing vocab keys are unchanged."""
    if not combo:
        return None
    return combo[0] if len(combo) == 1 else combo


def bind_params(ctx: Ctx, params: "tuple[n.MoveParam, ...]", value: Any) -> Ctx:
    combo = () if value is None else (value,) if len(params) == 1 else tuple(value)
    for p, v in zip(params, combo):
        ctx = ctx.with_local(p.name, v)
    return ctx


def concrete_moves(mt: n.MoveTypeDef, actor: Player, ctx: Ctx) -> list[tuple[str, Any]]:
    """The guard-filtered candidate list for one move type: the cross-product of
    its parameters' domains, in declaration order, each combo guard-checked with
    all parameters bound. Nullary is the empty-product case (one empty combo)."""
    pctx = ctx.acting_as(actor)
    domains = [param_domain(p, actor, pctx) for p in mt.params]
    out: list[tuple[str, Any]] = []
    for combo in itertools.product(*domains):
        vctx = bind_params(pctx, mt.params, _pack(combo))
        if mt.guard is None or bool(evaluate(mt.guard, vctx)):
            out.append((mt.name, _pack(combo)))
    return out
```

Note on `ctx.rs.suits`: if `RuntimeState` has no `suits` attribute, source suits the way `rank_index` is sourced (from the deck at driver setup) or fall back to the module `SUITS` constant for standard decks — Go Fish uses `standard52`, so `SUITS` is correct; the deck-specific side-fix can pass the deck's suits. Verify the available accessor in `cardlang/runtime/state.py` before wiring.

Rewrite `AuctionForm.candidates` (lines 295-336) to use `concrete_moves` per move def, concatenated, preserving the empty-candidate `RuntimeError`. Rewrite `AuctionForm.apply` (lines 338-348) to bind via `bind_params(pctx, mt.params, value)` instead of the single-`with_local`.

- [ ] **Step 4: Wire `offer` to enumerate (`execute._offer`)**

`cardlang/runtime/execute.py`, replace `_offer` (lines 310-331):

```python
def _offer(stmt: n.Offer, ctx: Ctx) -> None:
    from cardlang.runtime.mechanics import bind_params, concrete_moves

    player = evaluate(stmt.player, ctx)
    pctx = ctx.acting_as(player)
    candidates: list[tuple[str, Any]] = []
    for name in stmt.move_types:
        candidates.extend(concrete_moves(ctx.rs.move_type_index[name], player, ctx))
    if not candidates:
        raise RuntimeError(
            f"offer to player {player}: none of {list(stmt.move_types)} is legal. "
            f"Add an always-legal move (an unguarded `pass`/`decline`) or guard the "
            f"offer so it is only made when the player can act."
        )
    chosen = ctx.chooser(player, candidates, 1)[0]
    observe.choice(ctx, player, chosen)
    observe.announce(ctx, player, chosen)
    name, value = chosen
    mt = ctx.rs.move_type_index[name]
    run_body(mt.effect, bind_params(pctx, mt.params, value))
```

- [ ] **Step 5: Run the new test + full suite**

Run: `pytest tests/test_offer_enumeration.py -v` then `PYTHONHASHSEED=0 pytest -q`
Expected: PASS. Existing single-parameter auctions (Bridge etc.) are unchanged: `concrete_moves` over a 1-parameter move yields the same bare-valued candidates in the same order.

- [ ] **Step 6: Commit**

```bash
git add cardlang/runtime/mechanics.py cardlang/runtime/execute.py tests/test_offer_enumeration.py
git commit -m "feat(language): offer enumerates parameterized moves (arity-N cross-product)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: OpenSpiel action space — the cross-product

**Files:**
- Modify: `cardlang/openspiel/encoding.py:144-192` (`ActionSpace.for_game`), `:194-217` (`encode`) as needed
- Test: `tests/test_action_space_multiparam.py` (new)

**Interfaces:**
- Consumes: `enumerate_domain(...)` (Task 2).
- Produces: for a game with `ask(target: Player, rank: Rank)` over 4 players / 13 ranks, `num_distinct_actions` includes 52 distinct `("ask", (t, r))` vocab ids; `encode(("ask", (t, r)))` and `decode` round-trip.

- [ ] **Step 1: Write the failing test**

Create `tests/test_action_space_multiparam.py`:

```python
import pytest

from cardlang.parse import parse_text
from cardlang.openspiel.encoding import ActionSpace

GAME = """
game G {
  players: 4
  max_length: 50
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { hand[player] : Hand<player> }
  state { done : Integer = 0 }
  phase play { offer to 0 one of [ask] done := 1 }
  winner: highest done
}
move_type ask(target : Player, rank : Rank) { when: target != actor effect { done := 1 } }
"""


def test_cross_product_vocab_ids_round_trip() -> None:
    game = parse_text(GAME, "g.cardlang")
    space = ActionSpace.for_game(game)
    # 4 targets x 13 ranks = 52 ask candidates; every (t, r) encodes distinctly
    ids = {space.encode(("ask", (t, r))) for t in range(4) for r in
           ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]}
    assert len(ids) == 52
    for t in range(4):
        aid = space.encode(("ask", (t, "K")))
        assert space.decode(aid) == ("ask", (t, "K"))
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_action_space_multiparam.py -v`
Expected: FAIL — the vocab currently mints ids only for a single-value `enumerate_domain(mt.param.type_name)`; `encode(("ask", (t, r)))` KeyErrors or the count is wrong.

- [ ] **Step 3: Implement the cross-product in `for_game`**

`cardlang/openspiel/encoding.py`, in the `n.Round`/`n.Offer` walk that builds `vocab` (lines 157-176), replace the single-parameter `entries` construction with the cross-product over `mt.params`, sourcing the fixed domains from the game's deck/seating:

```python
def _domains_for(game: n.Game, mt: n.MoveTypeDef) -> list[list[Any]]:
    block = _derived_card_block(game.deck)
    ranks = list(dict.fromkeys(c.rank for c in block))
    suits = list(dict.fromkeys(c.suit for c in block))
    players = list(range(game.players.low))
    return [
        enumerate_domain(p.type_name, suits=suits, ranks=ranks, players=players)
        for p in mt.params
    ]

# per move type mt reachable from an Offer or a round vocabulary:
if any(p.type_name == "Card" for p in mt.params):
    continue  # Card contributes no vocab ids (folded into the card block)
if not mt.params:
    entries = [(mt.name, None)]
else:
    entries = [
        (mt.name, combo[0] if len(mt.params) == 1 else tuple(combo))
        for combo in itertools.product(*_domains_for(game, mt))
    ]
vocab.extend(e for e in entries if e not in vocab)
```

Add `import itertools`. **Route by arity, not by construct.** Today `n.Offer` sends *every* move type to the nullary `names` block (line 157-158); after this task an `Offer` (like a `Round` vocabulary) must send **nullary** moves to `names` and **parameterized** moves through the cross-product into `vocab` — else a parameterized offer move (Go Fish's `ask`) gets a stray, never-used nullary id and no cross-product ids. Concretely, for each move type reachable from an `Offer` or a round vocabulary: if `mt.params` is empty → `names`; if it has a `Card` param → skip (card block); otherwise → the cross-product `entries` above into `vocab`. Confirm `encode` (lines 207-211) already handles the outer `(name, value)` tuple where `value` is itself a tuple — it does: `name, param = value; ... return self._vocab_base + self._vocab_ids[value]` (the multi-param tuple is not a `Card`, so it hits the vocab-id lookup). Verify `decode` inverts it.

- [ ] **Step 4: Run the new test + full suite**

Run: `pytest tests/test_action_space_multiparam.py -v` then `PYTHONHASHSEED=0 pytest -q`
Expected: PASS. Existing games' action spaces unchanged (single-parameter `entries` is the arity-1 case: `combo[0]`).

- [ ] **Step 5: Commit**

```bash
git add cardlang/openspiel/encoding.py tests/test_action_space_multiparam.py
git commit -m "feat(openspiel): action space is the parameter cross-product

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `observe.render` — readable tuple parameters

**Files:**
- Modify: `cardlang/runtime/observe.py:32-46` (`render`)
- Test: `tests/test_render_multiparam.py` (new)

**Interfaces:**
- Produces: `render(("ask", (1, "K"))) == "ask(1,K)"`; single-parameter and nullary rendering unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/test_render_multiparam.py`:

```python
from cardlang.runtime.observe import render


def test_multiparam_renders_each_value() -> None:
    assert render(("ask", (1, "K"))) == "ask(1,K)"


def test_single_param_unchanged() -> None:
    assert render(("submit_bid", "hearts")) == "submit_bid(hearts)"


def test_nullary_unchanged() -> None:
    assert render(("pass", None)) == "pass"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_render_multiparam.py -v`
Expected: FAIL — `render(("ask", (1, "K")))` returns `"ask((1, 'K'))"`.

- [ ] **Step 3: Implement**

`cardlang/runtime/observe.py`, in `render`, replace the `(move_type, param)` branch:

```python
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        name, param = value  # a (move_type, param) candidate
        if param is None:
            return name
        if isinstance(param, tuple):  # a multi-parameter move: render each value
            return f"{name}(" + ",".join(str(v) for v in param) + ")"
        return f"{name}({param})"
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/test_render_multiparam.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/observe.py tests/test_render_multiparam.py
git commit -m "feat(language): render multi-parameter move candidates readably

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Resolve-time acceptance + totality rejections

Relax the two walls to accept `Rank`/`Player`/multi-parameter under both `offer` and `round`; reject the deferred/unsupported combinations with clear messages.

**Files:**
- Modify: `cardlang/resolve.py:523-535` (`n.Offer`), `:536-565` (`n.Round` vocabulary)
- Test: `tests/test_resolve_param_domains.py` (new)

**Interfaces:**
- Produces (resolve accepts): a move type whose every parameter is `Suit`/`Suit?`/`Rank`/`Player`, under `offer` or `round offering`; a single `Card` parameter as today.
- Produces (resolve rejects, each with a message): a `Card` parameter combined with any other parameter; a parameter typed `Integer` (or `Integer in …`) — "bounded-Integer parameter domains are deferred (see open-questions/move-parameter-domains.md)"; an unknown domain type.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resolve_param_domains.py`:

```python
from cardlang.parse import parse_text
from cardlang.pipeline import check_source


def _diags(move_src: str, offer_or_round: str) -> list[str]:
    src = (
        "game G {\n"
        "  players: 4\n  max_length: 50\n  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state { done : Integer = 0 }\n"
        f"  phase play {{ {offer_or_round} done := 1 }}\n"
        "  winner: highest done\n}\n"
        f"{move_src}\n"
    )
    result = check_source(src, "g.cardlang")
    return [d.message for d in result.diagnostics]


def test_player_rank_offer_accepted() -> None:
    diags = _diags(
        "move_type ask(target : Player, rank : Rank) { when: target != actor effect { done := 1 } }",
        "offer to 0 one of [ask]",
    )
    assert not any("parameter" in d for d in diags), diags


def test_integer_parameter_rejected_as_deferred() -> None:
    diags = _diags(
        "move_type bet(amount : Integer) { effect { done := 1 } }",
        "offer to 0 one of [bet]",
    )
    assert any("Integer" in d and "defer" in d.lower() for d in diags), diags


def test_card_with_other_param_rejected() -> None:
    diags = _diags(
        "move_type play(c : Card, s : Suit) { effect { done := 1 } }",
        "offer to 0 one of [play]",
    )
    assert any("Card" in d and "combin" in d.lower() for d in diags), diags
```

- [ ] **Step 2: Run them, verify they fail**

Run: `pytest tests/test_resolve_param_domains.py -v`
Expected: FAIL — `offer` still rejects any parameterized move (`test_player_rank_offer_accepted` sees the old "only an auction round offering can enumerate" error), and the Integer/Card-combo cases are not yet checked.

- [ ] **Step 3: Implement a shared validator and rewire both sites**

`cardlang/resolve.py` — add a helper and call it from the `n.Offer` and `n.Round` cases:

```python
_FIXED_DOMAINS = frozenset({"Suit", "Suit?", "Rank", "Player"})


def _check_move_params(mt: n.MoveTypeDef, bag: DiagnosticBag, span: object) -> None:
    """Totality gate for a parameterized move offered/enumerated in a decision.
    Fixed-from-type domains (Suit/Suit?/Rank/Player) and a single Card are
    allowed; a Card combined with any other parameter, and a bounded-Integer
    parameter (deferred), are rejected with a message."""
    types = [p.type_name for p in mt.params]
    card_count = types.count("Card")
    if card_count and len(types) > 1:
        bag.error(
            f"move '{mt.name}' combines a Card parameter with another parameter; "
            f"Card's domain is the live hand and its actions are the card block, "
            f"so it cannot be crossed with a fixed domain (fold into one parameter)",
            span,
        )
    for t in types:
        base = t.rstrip("?")
        if base == "Integer":
            bag.error(
                f"move '{mt.name}' has parameter domain '{t}'; bounded-Integer "
                f"parameter domains are deferred (see "
                f"open-questions/move-parameter-domains.md)",
                span,
            )
        elif base not in {"Suit", "Rank", "Player", "Card"}:
            bag.error(
                f"move '{mt.name}' has unsupported parameter domain '{t}' "
                f"(expected Suit, Suit?, Rank, Player, or Card)",
                span,
            )
```

In the `n.Offer` case (lines 523-535), replace the "reject parameterized move" branch with: if `move_type_defs[name].params`, call `_check_move_params(move_type_defs[name], bag, nd.span)` (accept when it adds no error). In the `n.Round` vocabulary case (lines 536-565), replace the per-parameter type gate with the same `_check_move_params` call, keeping the existing "at most one Card-parameterized move per vocabulary" and "needs a `hand[player]` zone" checks.

- [ ] **Step 4: Run the tests + full suite**

Run: `pytest tests/test_resolve_param_domains.py -v` then `PYTHONHASHSEED=0 pytest -q` and `mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cardlang/resolve.py tests/test_resolve_param_domains.py
git commit -m "feat(language): resolve accepts Rank/Player/multi-param; rejects Card-combo + Integer (deferred)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Go Fish corpus game — `.cardlang` + registration + playout

Author the Pagat-faithful game using the real `ask(target: Player, rank: Rank)` move, register it for OpenSpiel, and prove it plays to completion across a seed sweep.

**Files:**
- Create: `docs/games/go-fish.cardlang`
- Modify: `cardlang/openspiel/game.py:24-30` (the `_GAMES` dict)
- Test: `tests/test_playout_go_fish.py` (new)

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: registered short name `cardlang_go_fish` → `go-fish.cardlang`; a game that `play_game` runs to a terminal state for seeds 0–29.

- [ ] **Step 1: Write the failing playout test**

Create `tests/test_playout_go_fish.py`:

```python
from pathlib import Path

import pytest

from cardlang.parse import parse_text
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GO_FISH = Path(__file__).parent.parent / "docs" / "games" / "go-fish.cardlang"


def test_go_fish_checks_clean() -> None:
    result = check_source(GO_FISH.read_text(), "go-fish.cardlang")
    assert not result.errors, [d.message for d in result.diagnostics]


@pytest.mark.parametrize("seed", range(30))
def test_go_fish_plays_to_completion(seed: int) -> None:
    game = parse_text(GO_FISH.read_text(), "go-fish.cardlang")
    outcome = play_game(game, seed=seed)   # match the signature used in test_playout_coup.py
    assert outcome is not None
```

Check `tests/test_playout_coup.py` for the exact `play_game` call/return convention and mirror it (do not invent a signature).

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_playout_go_fish.py -v`
Expected: FAIL — `go-fish.cardlang` does not exist.

- [ ] **Step 3: Write the game**

Create `docs/games/go-fish.cardlang` (adapt the stress-branch skeleton at `stress-test/broad-sweep:stress-test/games/go-fish.cardlang`, but replace the two `choose integer` picks + `rank_matches` indirection with the real `ask` move, and drop the `offset_by` target workaround):

```
// Go Fish — four-player, standard 52-card deck. Rules per pagat.com/quartet/gofish.html.
//
// On your turn you name another player and a rank you already hold at least one
// card of; the ask is public. If they hold that rank they give you ALL of it and
// you go again; otherwise "go fish" — draw the top stock card, and if it is the
// asked rank show it and go again, else keep it and pass left. Four of a rank is
// a book, set aside. The game ends the instant any hand empties or the stock runs
// out; most books wins.
//
// This is the corpus witness for declared parameter domains: `ask(target: Player,
// rank: Rank)` enumerates the guard-filtered Player x Rank cross-product under a
// plain `offer`, and the public ask derives every observer's knowledge that the
// asker holds the named rank (decisions.md "Declared parameter domains").

game GoFish {

  players: 4
  direction: clockwise
  max_length: 600

  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck         : Deck                 // face-down stock
    hand[player] : Hand<player>         // private hand
    book[player] : PlayerPile<player>   // completed books, shown then set aside
  }

  state {
    current_player     : Player  = 0
    book_count[player] : Integer = 0
  }

  phase setup {
    shuffle deck
    deal 5 cards from deck to each hand
    for each player p:
      if (max over hand[p] as c: (sum over hand[p] as c2: if c2.rank == c.rank then 1 else 0)) == 4 {
        move all cards from hand[p]
             where c => (sum over hand[p] as c2: if c2.rank == c.rank then 1 else 0) == 4
             to book[p]
        book_count[p] += 1
      }
    current_player := 0
  }

  phase play {
    repeat until (deck is empty) or (any player p: hand[p] is empty) {
      offer to current_player one of [ask]
    }
  }

  winner: highest book_count
}

// The turn: name a live opponent and a rank you hold; the ask is public.
move_type ask(target : Player, rank : Rank) {
  when: target != actor
        and (sum over hand[actor] as c: if c.rank == rank then 1 else 0) > 0
  effect {
    let target_holds = sum over hand[target] as c: if c.rank == rank then 1 else 0
    if target_holds > 0 {
      move all cards from hand[target] where c => c.rank == rank to hand[actor]
      // A hit: current_player unchanged, so the next iteration offers to the same
      // player — "you go again".
    } else {
      let before = sum over hand[actor] as c: if c.rank == rank then 1 else 0
      draw 1 card from deck to hand[actor]
      let after = sum over hand[actor] as c: if c.rank == rank then 1 else 0
      if after == before {                 // drew a non-matching card: pass left
        current_player := actor offset_by left
      }
      // drew the asked rank: go again (current_player unchanged)
    }
    // Book completion (from a transfer or a draw): set aside four of a rank.
    if (max over hand[actor] as c: (sum over hand[actor] as c2: if c2.rank == c.rank then 1 else 0)) == 4 {
      move all cards from hand[actor]
           where c => (sum over hand[actor] as c2: if c2.rank == c.rank then 1 else 0) == 4
           to book[actor]
      book_count[actor] += 1
    }
  }
}
```

Verify against the language: confirm `offset_by left` on a `Player` state variable, `any player p: <pred>`, `draw N card from deck to hand[actor]`, and `max/sum over <zone> as c: <expr>` all match current syntax by grepping the existing corpus (`getaway.cardlang`, `oh-hell.cardlang`). Adjust `max_length` if the decision counter reports overflow for a 4-player game (bump and re-run; the stress file ran green).

- [ ] **Step 4: Register the game**

`cardlang/openspiel/game.py`, add to the `_GAMES` dict (keep alphabetical if the dict is ordered):

```python
    "cardlang_go_fish": "go-fish.cardlang",
```

- [ ] **Step 5: Run the playout test**

Run: `PYTHONHASHSEED=0 pytest tests/test_playout_go_fish.py -v`
Expected: PASS — clean check + all 30 seeds terminate.

- [ ] **Step 6: Run the full suite** (registration triggers `test_coverage.py`)

Run: `PYTHONHASHSEED=0 pytest -q`
Expected: `tests/openspiel_ready/test_coverage.py::test_no_proof_module_without_a_registered_game` now FAILS (missing `test_go_fish.py`). That is expected — Task 8 adds it. Everything else passes. If any *other* test fails, fix before proceeding.

- [ ] **Step 7: Commit**

```bash
git add docs/games/go-fish.cardlang cardlang/openspiel/game.py tests/test_playout_go_fish.py
git commit -m "feat(corpus): Go Fish — four-player, ask(target: Player, rank: Rank)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Go Fish OpenSpiel readiness — the four proofs (info-set GO/NO-GO)

**This is the load-bearing gate (see "⚠ Execution ordering" above). Run its indistinguishability proof the moment a minimal Go Fish is registered.** The greedy-swap harness needs a same-**rank** swap generator for Go Fish; without it, the proof fails on legally-replayed-but-observably-different worlds.

**Files:**
- Modify: `tests/openspiel_ready/harness.py` (`GameSpec`: add a `swap_axis` field; `swap_pairs`: honor it)
- Create: `tests/openspiel_ready/test_go_fish.py`

**Interfaces:**
- Consumes: `cardlang_go_fish` registration (Task 7); the `ReadinessProofs`/`GameSpec` harness.
- Produces: `GameSpec.swap_axis: str` (`"suit"` default — today's behavior; `"rank"`; `"any"`); a `TestReadiness(ReadinessProofs)` whose four proofs pass.

Why same-rank (the reasoning that makes this a real proof, not a workaround): the harness swaps two cards hidden from observer P and replays the same actions, asserting P's info state is byte-identical. For Go Fish, P publicly observes every ask and every transfer *count* (`Hand` → `count_only` to non-owners). A same-rank, different-suit swap (K♠↔K♥ between two opponents) preserves **every player's per-rank counts and every ask's legality**, so *all* of P's observations are identical — a genuinely indistinguishable world. (Same-suit, the trick-game default, is wrong here: swapping K♠→Q♠ changes a King count P may have seen. Books never leak: a completed book is always all four suits of its rank, so it carries no suit information beyond the already-public rank.) This is the same idea as the existing same-suit constraint, keyed to the axis Go Fish's public observations actually preserve.

- [ ] **Step 1: Extend the harness with a swap axis**

`tests/openspiel_ready/harness.py` — add to `GameSpec` (near `swap_any_pair`):

```python
    # Which equivalence class a hidden swap must stay within so the swapped
    # world is genuinely indistinguishable to the observer (the swap must not
    # change any PUBLIC observation). "suit": follow-suit trick games (default,
    # today's behavior). "rank": rank-probing games (Go Fish — a public ask's
    # transfer COUNT is observed, so only same-rank swaps preserve it).
    # "any": no public card/rank observation (a pure betting vocabulary).
    swap_axis: str = "suit"
```

Rewrite `swap_pairs` to honor it (keep the 3♦ carve-out only for the suit axis, where Big Two's opening filter lives):

```python
    def swap_pairs(self, hand1: list[Any], hand2: list[Any]) -> list[Any]:
        """Swappable hidden-card pairs that keep the swapped world indistinguishable."""
        if self.swap_axis == "rank":
            return [(x, y) for x in hand1 for y in hand2 if x.rank == y.rank and x.suit != y.suit]
        if self.swap_axis == "any" or self.swap_any_pair:
            return [(x, y) for x in hand1 for y in hand2 if x != y]
        three_d = ("3", "diamonds")
        return [
            (x, y)
            for x in hand1
            for y in hand2
            if x.suit == y.suit
            and x != y
            and (x.rank, x.suit) != three_d
            and (y.rank, y.suit) != three_d
        ]
```

Run: `PYTHONHASHSEED=0 pytest tests/openspiel_ready/ -q` — every existing game still green (default `swap_axis="suit"` is byte-identical to before).

- [ ] **Step 2: Write the proof module**

Create `tests/openspiel_ready/test_go_fish.py`:

```python
"""Go Fish — OpenSpiel readiness.

Four players, hidden `hand`. A public ask's transfer COUNT is observed
(`Hand` -> count_only to non-owners), so an indistinguishable world requires a
same-RANK swap (K♠↔K♥): it preserves every per-rank count and every ask's
legality, hence every public observation. Same-suit (the trick-game default)
would change a rank count the observer saw. Depth tuned so two opponents still
share a rank at the pause.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_go_fish",
        "go-fish.cardlang",
        hidden_zone="hand",
        depth=6,
        swap_axis="rank",
    )
```

- [ ] **Step 3: Run the indistinguishability proof FIRST — the go/no-go**

Run: `PYTHONHASHSEED=0 pytest tests/openspiel_ready/test_go_fish.py::TestReadiness::test_indistinguishability_under_hidden_swap -v`
Expected: PASS. With `swap_axis="rank"` every candidate swap is genuinely indistinguishable, so the first legally-replayed pair is byte-identical. If it FAILS:
- "no swap pair available" → the two probed opponents share no rank at this depth; lower `depth` or try another seed until a same-rank cross-suit pair exists at the pause.
- byte-identity still breaks on a same-rank swap → a public observation depends on suit somewhere unexpected (investigate which obs-log entry differs). **Fallback:** if same-rank cannot be made to hold, treat Go Fish like Bridge/Tarot — replace this proof with a bespoke indistinguishability test that constructs a known-indistinguishable world pair directly, and document the greedy-harness misfit in the module docstring and CLAUDE.md's honesty note. Do not weaken the property; change how it is exercised.

- [ ] **Step 4: Run the remaining three proofs + coverage**

Run: `PYTHONHASHSEED=0 pytest tests/openspiel_ready/test_go_fish.py tests/openspiel_ready/test_coverage.py -v`
Expected: PASS. Soundness (swapping P's *own* same-rank card changes P's identity view), perfect recall (append-only logs), and conformance (full `random_sim_test`; if slow, set `conformance_steps` to a few hundred and note why) all pass. Coverage confirms the registry ↔ proof-module match.

- [ ] **Step 5: Commit**

```bash
git add tests/openspiel_ready/harness.py tests/openspiel_ready/test_go_fish.py
git commit -m "test(openspiel): Go Fish readiness proofs; same-rank swap generator for rank-probing games

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Go Fish dedicated observational test — the ask derives "A holds R"

The exact semantic Go Fish was chosen to prove, which the four-proof harness does not assert directly (advisor point). Mirrors Coup's `test_influence_flips_derive_hidden_observations`.

**Files:**
- Modify: `tests/openspiel_ready/test_go_fish.py` (add the dedicated test alongside `TestReadiness`)

**Interfaces:**
- Consumes: `replay.run`, `infostate.information_state`, `harness.GAMES_DIR`.
- Produces: a test proving the public ask reaches every observer's log and info state.

- [ ] **Step 1: Write the test**

Append to `tests/openspiel_ready/test_go_fish.py`:

```python
from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, run

from .harness import GAMES_DIR


def test_public_ask_derives_asker_holds_rank() -> None:
    """An ask is public: naming (target, rank) reaches EVERY player's observation
    log and information state. Because a legal ask requires the asker to hold the
    named rank, that public announce is exactly the evidence from which every
    observer derives 'the asker holds this rank' — the info-set content Go Fish
    exists to prove derivable."""
    path = str(GAMES_DIR / "go-fish.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    for _ in range(40):
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause), "greedy line ended before any ask"
        r = nxt
        if any(e[0] == "announce" and str(e[2]).startswith("ask(") for e in r.obs_logs[0]):
            break

    def asks(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return [e for e in log if e[0] == "announce" and str(e[2]).startswith("ask(")]

    assert asks(r.obs_logs[0]), "no ask was announced on the greedy line"
    first = asks(r.obs_logs[0])[0]
    asker = int(first[1])
    rendered = str(first[2])              # e.g. "ask(2,K)"

    # The ask is public: identical announce in every player's log.
    for q in range(4):
        assert first in asks(r.obs_logs[q]), f"P{q} did not observe the public ask"

    # And it reaches a bystander's derived information state verbatim.
    watcher = next(q for q in range(4) if q != asker)
    info = information_state(watcher, r.rs, r.obs_logs[watcher])
    assert rendered in info, "the public ask is absent from a bystander's info state"
```

- [ ] **Step 2: Run it**

Run: `pytest tests/openspiel_ready/test_go_fish.py::test_public_ask_derives_asker_holds_rank -v`
Expected: PASS. If the greedy line (`r.legal[0]` each turn) never produces an ask within 40 steps, widen the search or seed differently — but Go Fish forces an ask every turn, so the first decision on the line is already an ask; the loop should break immediately.

- [ ] **Step 3: Commit**

```bash
git add tests/openspiel_ready/test_go_fish.py
git commit -m "test(openspiel): Go Fish public ask derives 'asker holds rank' for every observer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Go Fish `.md` — the readable rules doc

The corpus acceptance test: a non-player reads it cold and plays a hand.

**Files:**
- Create: `docs/games/go-fish.md`

- [ ] **Step 1: Write the doc**

Create `docs/games/go-fish.md` following the structure of an existing game doc (open `docs/games/getaway.md` for the section shape: prose rules → the DSL walkthrough → what each construct does). Cover: 4 players / 52 cards / 5 each; the public ask (`ask(target: Player, rank: Rank)`, must hold the rank); give-all-matching + go-again; go-fish draw (show + go again on a match); books; end-on-empty-hand-or-empty-stock; most-books-wins. Explicitly call out the info-set point — the ask is public and reveals that the asker holds the named rank — since Go Fish is the corpus's witness for that.

- [ ] **Step 2: Verify it reads cold**

Re-read it as a non-player. Confirm every rule needed to play a hand is present and matches `go-fish.cardlang`. No code changes; this is a prose gate.

- [ ] **Step 3: Commit**

```bash
git add docs/games/go-fish.md
git commit -m "docs(corpus): Go Fish rules writeup

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Docs hygiene — promote the decision, rewrite the open question

Per maintaining.md: settle the resolved surface into `decisions.md`, narrow the open question to the deferred Integer axis, update the index and the corpus roster.

**Files:**
- Modify: `docs/decisions.md` ("The Card move-parameter domain" section, ~461-489)
- Modify: `docs/open-questions/move-parameter-domains.md` (rewrite to the residual scope)
- Modify: `docs/open-questions/_index.md` (Tier 1 entry)
- Modify: `CLAUDE.md` (corpus roster: add Go Fish)

- [ ] **Step 1: Promote to `decisions.md`**

Rewrite the "The Card move-parameter domain" section (or add a sibling "Declared parameter domains") into spec-voice covering: the enumerable domain set is now `{Suit, Suit?, Rank, Player, Card}`; a `move_type` takes N parameters enumerating in declaration order as a guard-filtered cross-product; plain `offer` and auction `round offering` both enumerate them into one flat candidate list (one chooser draw, one public announce); the OpenSpiel action space is the cross-product with per-state legality as a mask; `Card` stays state-dependent (live hand, card-block ids) and may not combine with another parameter; bounded-`Integer` is not yet a domain (open question). Cross-reference Go Fish as the witness. Do **not** write history ("used to be single-parameter") — edit in place (maintaining.md rule 1).

- [ ] **Step 2: Rewrite the open question**

Rewrite `docs/open-questions/move-parameter-domains.md` down to only the residual scope: bounded-`Integer` parameter domains and the `choose integer in lo..hi` reconciliation (retire `_MAX_CHOOSE`; runtime bound → mask; reject/widen/mask decision), with Oh Hell/Ninety-Nine as its data points. Delete the Rank/Player/`offer`-enumeration content now in `decisions.md`. Do not leave a "resolved" stub.

- [ ] **Step 3: Update the index and corpus roster**

`docs/open-questions/_index.md`: rewrite the Tier 1 bullet to the narrowed (bounded-Integer + `choose`) scope. `CLAUDE.md`: add Go Fish to the corpus list (the "corpus today" paragraph and the count).

- [ ] **Step 4: Verify links and run the full suite**

Run: `PYTHONHASHSEED=0 pytest -q` and `mypy`
Expected: PASS (docs-only changes; if any test parses `decisions.md`/open-questions for link integrity, satisfy it).

- [ ] **Step 5: Commit**

```bash
git add docs/decisions.md docs/open-questions/move-parameter-domains.md \
        docs/open-questions/_index.md CLAUDE.md
git commit -m "docs: settle declared parameter domains (Rank/Player); narrow open question to Integer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Final verification + PR

- [ ] **Step 1: Run both CI checks from the repo root**

Run: `mypy` then `PYTHONHASHSEED=0 pytest -q`
Expected: both green. If `pytest` without the pinned seed is the CI default, run it that way too (memory: exact-score tests pin `PYTHONHASHSEED=0`; the suite must pass both).

- [ ] **Step 2: Self-review the diff**

Run: `git diff main...feat/move-parameter-domains --stat`
Confirm: the `param → params` migration touched every reader; every parameterized-move corpus game re-ran green; Go Fish is registered, proven, documented; the open question is narrowed, not stubbed.

- [ ] **Step 3: Open the PR**

```bash
git push -u origin feat/move-parameter-domains
gh pr create --title "Declared parameter domains (Rank/Player) + arity-N move types, proven by Go Fish" --body "$(cat <<'EOF'
Resolves the Rank/Player/arity-N/offer-enumeration slice of
open-questions/move-parameter-domains.md. Bounded-Integer + the choose
reconciliation remain a deferred follow-on.

- `move_type` takes N parameters (tuple), enumerating the guard-filtered
  cross-product under plain `offer` and auction `round offering`.
- `enumerate_domain` gains Rank and Player (fixed-from-type).
- OpenSpiel action space is the cross-product; per-state legality is the mask.
- Go Fish (four-player) enters the corpus as the OpenSpiel-proven witness,
  with a dedicated test that the public ask derives "asker holds rank" for
  every observer.
- Totality: Card-with-other-params and bounded-Integer are statically rejected.

Spec: docs/superpowers/specs/2026-07-07-move-parameter-domains-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage** (§A–G of the design spec → tasks):
- §A arity-N surface → Tasks 1 (AST/grammar/parse), 3 (fold), 5 (render).
- §B domains + totality → Tasks 2 (enumerate_domain), 6 (resolve accept/reject).
- §C enumeration order → Task 3 (`itertools.product` in declaration order; `_pack` keeps arity-1 bare).
- §D OpenSpiel encoding → Task 4 (cross-product vocab, encode/decode).
- §E info-set derivation → Tasks 8 (four proofs; the info-set go/no-go, with the same-rank swap generator + bespoke-test fallback) + 9 (dedicated ask-derives test, robust regardless of Task 8's outcome).
- §F Go Fish corpus game → Tasks 7 (`.cardlang` + register + playout) + 10 (`.md`).
- §G AST blast radius + docs hygiene → Task 1 (readers + corpus re-run) + 11 (decisions.md/open-question/index/CLAUDE.md).

**Placeholder scan:** the one intentional lookup-before-write is the `Ctx` construction in Task 3 Step 1 and the `play_game`/`ctx.rs.suits` accessors — each names the exact existing file to copy the convention from (`test_chooser_seam.py`, `test_playout_coup.py`, `state.py`) rather than inventing a signature. No `TBD`/`handle edge cases`/bare "write tests".

**Type consistency:** `MoveTypeDef.params` (Task 1) is read as `mt.params` everywhere (Tasks 3, 4, 6). Candidate value shape (`None`/bare/tuple via `_pack`) is consistent across `concrete_moves` (Task 3), `ActionSpace` (Task 4), and `render` (Task 5). `enumerate_domain(type_name, *, suits, ranks, players)` (Task 2) is called with the same keyword signature in Task 3 (`param_domain`) and Task 4 (`_domains_for`).
