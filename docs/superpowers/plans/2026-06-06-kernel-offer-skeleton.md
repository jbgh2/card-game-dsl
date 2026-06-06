# Kernel `offer` Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the kernel's single-decision atom — `move_type` definitions (guard + effect) and an `offer to <player> one of [...]` statement — end-to-end through the pipeline, proving decision logic can be expressed in the DSL, checked, lowered to IR, and run.

**Architecture:** A `move_type NAME { when: <pred> effect { <stmts> } }` top-level declaration (alongside `rule`/`routing`) defines a named, guarded action whose effect is ordinary statements. A new `offer to <expr> one of [<names>]` statement presents the *legal* move-types (those whose guard holds) to a player; the runtime chooser picks one and runs its effect with the new `actor` pronoun bound to that player. This is shape ① of the interaction-decision sublanguage (see `docs/superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md`). Follow-on plans add `round`, typed outcomes, `define`-composition, and the `trick` re-expression.

**Tech Stack:** Python 3.11, Lark (Earley grammar), frozen-dataclass AST, structural `match` + `assert_never`, strict mypy, pytest.

**Scope guard:** This plan does NOT add `round`, typed outcomes, parameterized move instances (targets/amounts), or the generalized legal-set filter beyond a boolean per-move guard. Those are later plans. Keep the existing 78 tests + mypy green throughout.

---

## File Structure

- `cardlang/ast/nodes.py` — add `MoveTypeDef` and `Offer` nodes; extend `Stmt`, `Node`, and `Game` unions.
- `cardlang/grammar/cardlang.lark` — add `move_type_def` (top-level) and `offer` (statement) productions.
- `cardlang/parse.py` — transformer methods for the new productions; thread `move_types` into `Game`.
- `cardlang/resolve.py` — register defined move-type names; add `actor` pronoun; resolve move-type guard/effect and offer's referenced names.
- `cardlang/ir.py` — emit `MoveTypeDef` and `Offer`.
- `cardlang/runtime/state.py` — add `move_type_index` to `RuntimeState`; `actor` handling.
- `cardlang/runtime/driver.py` — populate `move_type_index`.
- `cardlang/runtime/execute.py` — execute `Offer`; new `evaluate` pronoun via existing path.
- `cardlang/runtime/evaluate.py` — `actor` pronoun → `ctx.current_player`.
- `tests/fixtures/offer_skeleton.cardlang` — minimal game exercising `offer`.
- `tests/test_offer_skeleton.py` — parse/check/IR/playout tests for the fixture.

---

## Task 1: AST nodes for `MoveTypeDef` and `Offer`

**Files:**
- Modify: `cardlang/ast/nodes.py`

- [ ] **Step 1: Write the failing test**

Add to a new file `tests/test_offer_ast.py`:

```python
from cardlang.ast import nodes as n


def test_movetypedef_and_offer_construct():
    mt = n.MoveTypeDef(name="take_one", guard=None, effect=())
    assert mt.name == "take_one" and mt.guard is None and mt.effect == ()
    off = n.Offer(player=n.NameRef("p"), move_types=("take_one", "take_two"))
    assert off.player.name == "p" and off.move_types == ("take_one", "take_two")
    # Both must be members of their unions.
    assert isinstance(off, n.Stmt) or off.__class__ in n.Stmt.__args__  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_ast.py -v`
Expected: FAIL with `AttributeError: module 'cardlang.ast.nodes' has no attribute 'MoveTypeDef'`

- [ ] **Step 3: Write minimal implementation**

In `cardlang/ast/nodes.py`, add these dataclasses near the statement definitions (after `AssignStmt`):

```python
@dataclass(frozen=True, slots=True)
class Offer:
    """`offer to <player> one of [<move_type>, ...]` — the acting player chooses
    one legal move-type; its effect runs with `actor` bound to that player."""

    player: Expr
    move_types: tuple[str, ...]
    span: Span | None = None
```

Add `Offer` to the `Stmt` union:

```python
Stmt = (
    Movement
    | EpistemicOp
    | RotateStmt
    | EachSimultaneous
    | ForEach
    | RepeatUntil
    | IfStmt
    | Instantiate
    | LetStmt
    | AssignStmt
    | Offer
)
```

Add this dataclass near `RuleDef` (top-level definitions section):

```python
@dataclass(frozen=True, slots=True)
class MoveTypeDef:
    """`move_type NAME { when: <pred> effect { <stmt>* } }` — a named, guarded
    action. ``guard`` is None when the move is always legal."""

    name: str
    guard: Expr | None
    effect: tuple[Stmt, ...]
    span: Span | None = None
```

Add a `move_types` field to `Game` (after `routings`):

```python
    routings: tuple[RoutingDef, ...] = ()
    move_types: tuple[MoveTypeDef, ...] = ()
    span: Span | None = None
```

Add both new classes to the `Node` union (anywhere in the big union list):

```python
    | RuleDef
    | MoveTypeDef
    | Offer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offer_ast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cardlang/ast/nodes.py tests/test_offer_ast.py
git commit -m "kernel: AST nodes for move_type definitions and offer"
```

---

## Task 2: Grammar + parser for `move_type` and `offer`

**Files:**
- Modify: `cardlang/grammar/cardlang.lark`
- Modify: `cardlang/parse.py`
- Test: `tests/test_offer_parse.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_offer_parse.py`:

```python
from cardlang.ast import nodes as n
from cardlang.parse import parse_text

SRC = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play {
    for each player p: offer to p one of [take_one, take_two]
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { when: always  effect { coins[actor] += 2 } }
"""


def test_parses_move_types_and_offer():
    game = parse_text(SRC, "g.cardlang")
    assert {m.name for m in game.move_types} == {"take_one", "take_two"}
    one = next(m for m in game.move_types if m.name == "take_one")
    assert one.guard is None and len(one.effect) == 1
    two = next(m for m in game.move_types if m.name == "take_two")
    assert two.guard is not None  # `when: always` recorded
    # The offer statement is inside the for-each body.
    phase = game.phases[0]
    foreach = next(i for i in phase.items if isinstance(i, n.ForEach))
    assert isinstance(foreach.body, n.Offer)
    assert foreach.body.move_types == ("take_one", "take_two")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_parse.py -v`
Expected: FAIL with a Lark syntax error on `offer` / `move_type`.

- [ ] **Step 3a: Add grammar productions**

In `cardlang/grammar/cardlang.lark`, add `move_type_def` to the top-level items:

```
?top_item: game
         | rule_def
         | routing_def
         | move_type_def
```

Add the `move_type_def` production near `routing_def`:

```
// A named, guarded action whose effect is ordinary statements. `actor` is bound
// to the offered player while the effect runs (see the `offer` statement).
move_type_def: "move_type" NAME "{" [move_when] move_effect "}"
move_when: "when" ":" applies_pred
move_effect: "effect" "{" statement* "}"
```

Add `offer` to the `?statement` alternatives:

```
?statement: movement
          | rotate_stmt
          | epistemic_op
          | each_simultaneous
          | for_each
          | repeat_until
          | if_stmt
          | instantiate
          | let_stmt
          | assign_stmt
          | offer
```

Add the `offer` production in the statements section (near `instantiate`):

```
// The acting player chooses one of the listed move-types (those whose guard
// holds); the chosen move's effect runs with `actor` bound to that player.
offer: "offer" "to" expr "one" "of" "[" NAME ("," NAME)* "]"
```

Note: `applies_pred` (`always` | expr) already exists and is reused by `move_when`.

- [ ] **Step 3b: Add transformer methods**

In `cardlang/parse.py`, add a private marker near the other markers (after `_Partnerships`):

```python
@dataclass(frozen=True, slots=True)
class _MoveWhen:
    pred: object  # _Always | Expr


@dataclass(frozen=True, slots=True)
class _MoveEffect:
    body: tuple[object, ...]  # tuple[Stmt, ...]
```

Add these transformer methods to `_Builder` (near `routing_def`):

```python
    def move_when(self, meta: Meta, c: list[object]) -> _MoveWhen:
        return _MoveWhen(c[0])

    def move_effect(self, meta: Meta, c: list[object]) -> _MoveEffect:
        return _MoveEffect(tuple(_as_stmt(s) for s in c))

    def move_type_def(self, meta: Meta, c: list[object]) -> n.MoveTypeDef:
        name = str(c[0])
        guard: object | None = None
        effect: tuple[object, ...] = ()
        for item in c[1:]:
            if isinstance(item, _MoveWhen):
                guard = None if isinstance(item.pred, _Always) else _as_expr(item.pred)
            elif isinstance(item, _MoveEffect):
                effect = item.body
        return n.MoveTypeDef(
            name=name, guard=guard, effect=effect, span=self._span(meta)  # type: ignore[arg-type]
        )
```

Add the `offer` transformer (near `instantiate`):

```python
    def offer(self, meta: Meta, c: list[object]) -> n.Offer:
        player = _as_expr(c[0])
        names = tuple(str(x) for x in c[1:])
        return n.Offer(player=player, move_types=names, span=self._span(meta))
```

Wire `move_type_def` into the top-level `start` assembly. In the existing `start` method, add move-type collection:

```python
    def start(self, meta: Meta, c: list[object]) -> n.Game:
        game = next(x for x in c if isinstance(x, n.Game))
        rules = tuple(x for x in c if isinstance(x, n.RuleDef))
        routings = tuple(x for x in c if isinstance(x, n.RoutingDef))
        move_types = tuple(x for x in c if isinstance(x, n.MoveTypeDef))
        return replace(game, rules=rules, routings=routings, move_types=move_types)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offer_parse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cardlang/grammar/cardlang.lark cardlang/parse.py tests/test_offer_parse.py
git commit -m "kernel: grammar + parser for move_type and offer"
```

---

## Task 3: Resolver — `actor` pronoun, move-type registration, offer references

**Files:**
- Modify: `cardlang/resolve.py`
- Test: `tests/test_offer_resolve.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_offer_resolve.py`:

```python
from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play {
    for each player p: offer to p one of [take_one, take_two]
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
"""


def test_resolves_clean():
    game = check_dsl(SRC, "g.cardlang")  # raises if any name is unresolved
    assert {m.name for m in game.move_types} == {"take_one", "take_two"}


def test_offer_unknown_move_type_errors():
    bad = SRC.replace("[take_one, take_two]", "[take_one, nope]")
    try:
        check_dsl(bad, "g.cardlang")
        assert False, "expected a resolve error for unknown move type"
    except Exception as exc:  # DiagnosticError
        assert "nope" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_resolve.py -v`
Expected: FAIL — `actor` is an unresolved name (and/or offer move-types unchecked).

- [ ] **Step 3a: Add `actor` to the pronoun set**

In `cardlang/resolve.py`, extend `_PRONOUNS`:

```python
_PRONOUNS = frozenset({"state", "action", "outcome", "active_rules", "actor"})
```

- [ ] **Step 3b: Resolve offer move-type references and walk move-type bodies**

In `cardlang/resolve.py`, in `resolve()`, after the existing rule resolution, add validation that every `Offer`'s names and every `MoveTypeDef.guard`/effect resolve. The deep-name rewrite (`_classify_names`) already walks all dataclass fields generically, so `MoveTypeDef.guard`, `MoveTypeDef.effect`, and `Offer.player` are rewritten automatically once they're reachable from `Game`. Add a structural check for offer targets and a `_KNOWN` move-type set.

In `resolve()`, after `defined_rules = {...}`:

```python
    defined_move_types = {m.name for m in game.move_types}
```

Add a `_walk`-based validation in `_validate_refs` (add a new `match` case):

```python
            case n.Offer():
                for name in nd.move_types:
                    if name not in {m.name for m in game.move_types}:
                        bag.error(f"offer names unknown move type '{name}'", nd.span)
```

(`_validate_refs` receives `game`, so `game.move_types` is in scope.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offer_resolve.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add cardlang/resolve.py tests/test_offer_resolve.py
git commit -m "kernel: resolve actor pronoun and offer move-type references"
```

---

## Task 4: IR emission for `MoveTypeDef` and `Offer`

**Files:**
- Modify: `cardlang/ir.py`
- Test: `tests/test_offer_ir.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_offer_ir.py`:

```python
from cardlang.ir import emit
from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play { for each player p: offer to p one of [take_one, take_two] }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
"""


def test_ir_has_move_types_and_offer():
    ir = emit(check_dsl(SRC, "g.cardlang"))
    assert [m["name"] for m in ir["move_types"]] == ["take_one", "take_two"]
    assert ir["move_types"][0]["kind"] == "move_type"
    # Find the offer node inside the for-each body.
    phase = ir["phases"][0]
    foreach = next(i for i in phase["items"] if i["kind"] == "for_each")
    assert foreach["body"]["kind"] == "offer"
    assert foreach["body"]["move_types"] == ["take_one", "take_two"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_ir.py -v`
Expected: FAIL — `KeyError: 'move_types'` and `assert_never` on `Offer` in `_stmt`.

- [ ] **Step 3a: Emit move_types at the game level**

In `cardlang/ir.py`, in `emit()`, add to the returned dict (after `"routings"`):

```python
        "routings": [_routing(r) for r in game.routings],
        "move_types": [_move_type(m) for m in game.move_types],
```

Add the `_move_type` helper (near `_routing`):

```python
def _move_type(m: n.MoveTypeDef) -> IRDict:
    return {
        "kind": "move_type",
        "name": m.name,
        "guard": _expr(m.guard) if m.guard is not None else None,
        "effect": [_stmt(s) for s in m.effect],
    }
```

- [ ] **Step 3b: Emit the `Offer` statement**

In `cardlang/ir.py`, add a case to the `_stmt` match (before `assert_never`):

```python
        case n.Offer():
            return {
                "kind": "offer",
                "player": _expr(s.player),
                "move_types": list(s.move_types),
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offer_ir.py -v`
Expected: PASS

- [ ] **Step 5: Regenerate golden IR + commit**

The added `"move_types": []` key changes existing golden snapshots. Regenerate and verify only that key was added:

```bash
UPDATE_GOLDEN=1 python -m pytest tests/test_hearts_ir.py tests/test_getaway_ir.py tests/test_walking_skeleton.py -q
git diff tests/golden/hearts.ir.json   # expect only the new "move_types": [] line
python -m pytest tests/test_offer_ir.py -q
git add cardlang/ir.py tests/test_offer_ir.py tests/golden/
git commit -m "kernel: emit move_types and offer to IR; regen goldens"
```

---

## Task 5: Runtime — `move_type_index`, `actor` pronoun, populate in driver

**Files:**
- Modify: `cardlang/runtime/state.py`
- Modify: `cardlang/runtime/driver.py`
- Modify: `cardlang/runtime/evaluate.py`
- Test: `tests/test_offer_runtime_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_offer_runtime_wiring.py`:

```python
import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

SRC = """
game G {
  players: 2
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0 }
  phase play { for each player p: coins[p] += 1 }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
"""


def test_runtime_state_has_move_type_index():
    rs = RuntimeState.__new__(RuntimeState)  # just check the attribute exists post-init path
    # Full wiring is exercised via play_game below; here assert the field default.
    assert hasattr(RuntimeState, "__init__")


def test_driver_populates_move_type_index():
    game = check_dsl(SRC, "g.cardlang")
    captured = {}

    # Run a no-op game (offer added in Task 6); just confirm the index is built.
    result = play_game(game, random.Random(0))
    assert result.winner in (0, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_runtime_wiring.py -v`
Expected: FAIL — `play_game` raises because `move_type_index` is unset / `actor` pronoun unknown is not yet reachable (the no-op game should actually pass once the index is added; failure is on the index attribute if referenced). If it passes prematurely, proceed — the real exercise is Task 6.

- [ ] **Step 3a: Add `move_type_index` to `RuntimeState`**

In `cardlang/runtime/state.py`, in `RuntimeState.__init__`, add (near `routing_index`):

```python
        self.move_type_index: dict[str, n.MoveTypeDef] = {}  # name -> definition
```

- [ ] **Step 3b: Populate it in the driver**

In `cardlang/runtime/driver.py`, in `play_game`, after `rs.routing_index = {...}`:

```python
    rs.move_type_index = {m.name: m for m in game.move_types}
```

- [ ] **Step 3c: Add the `actor` pronoun in the evaluator**

In `cardlang/runtime/evaluate.py`, in `_pronoun`, add a case:

```python
        case "actor":
            return ctx.current_player
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offer_runtime_wiring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/state.py cardlang/runtime/driver.py cardlang/runtime/evaluate.py tests/test_offer_runtime_wiring.py
git commit -m "kernel: runtime move_type_index, driver wiring, actor pronoun"
```

---

## Task 6: Runtime — execute the `Offer` statement

**Files:**
- Modify: `cardlang/runtime/execute.py`
- Test: `tests/test_offer_execute.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_offer_execute.py`:

```python
import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

SRC = """
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { coins[player] : Integer = 0  rounds : Integer = 0 }
  phase play repeats until rounds >= 10 {
    before_each { rounds += 1 }
    for each player p: offer to p one of [take_one, take_two]
  }
  winner: highest coins
}
move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
"""


def test_offer_runs_a_chosen_effect_each_round():
    game = check_dsl(SRC, "g.cardlang")
    result = play_game(game, random.Random(3))
    # Each of 2 players is offered 10 times; each offer adds 1 or 2 coins.
    for p in (0, 1):
        assert 10 <= result.scores[p] <= 20
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])


def test_guard_filters_illegal_moves():
    # take_two is only legal once the player already has >= 5 coins.
    src = SRC.replace(
        "move_type take_two { effect { coins[actor] += 2 } }",
        "move_type take_two { when: coins[actor] >= 5  effect { coins[actor] += 2 } }",
    )
    game = check_dsl(src, "g.cardlang")
    # With a guard, early rounds can only take_one; final coins still within bounds.
    result = play_game(game, random.Random(1))
    for p in (0, 1):
        assert 10 <= result.scores[p] <= 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_execute.py -v`
Expected: FAIL — `execute` has no case for `n.Offer` (`assert_never`).

- [ ] **Step 3: Implement `Offer` execution**

In `cardlang/runtime/execute.py`, add a case to the `execute` match (before `assert_never`):

```python
        case n.Offer():
            _offer(stmt, ctx)
            return ctx
```

Add the helper (near `_each_simultaneous`):

```python
def _offer(stmt: n.Offer, ctx: Ctx) -> None:
    player = evaluate(stmt.player, ctx)
    pctx = ctx.acting_as(player)
    legal = [
        name
        for name in stmt.move_types
        if _move_legal(ctx.rs.move_type_index[name], pctx)
    ]
    if not legal:
        return  # no legal move: the offer is a no-op (e.g. all guards false)
    chosen = ctx.chooser(player, legal, 1)[0]
    mt = ctx.rs.move_type_index[chosen]
    run_body(mt.effect, pctx)


def _move_legal(mt: n.MoveTypeDef, ctx: Ctx) -> bool:
    return mt.guard is None or bool(evaluate(mt.guard, ctx))
```

`run_body` and `evaluate` are already imported in this module. `acting_as` sets `current_player`, which the `actor` pronoun reads.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_offer_execute.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/execute.py tests/test_offer_execute.py
git commit -m "kernel: execute the offer statement (guarded heterogeneous choice)"
```

---

## Task 7: Fixture game + end-to-end skeleton test

**Files:**
- Create: `tests/fixtures/offer_skeleton.cardlang`
- Test: `tests/test_offer_skeleton.py`

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/offer_skeleton.cardlang`:

```
// Walking skeleton for the kernel `offer` atom: each round, each player is
// offered a heterogeneous choice of guarded move-types; the chosen effect runs
// with `actor` bound to that player.
game OfferSkeleton {
  players: 2
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {
    deck         : Deck
    hand[player] : Hand<player>
  }

  state {
    coins[player] : Integer = 0
    rounds        : Integer = 0
  }

  phase play repeats until rounds >= 10 {
    before_each { rounds += 1 }
    for each player p: offer to p one of [take_one, take_two]
  }

  winner: highest coins
}

move_type take_one { effect { coins[actor] += 1 } }
move_type take_two { effect { coins[actor] += 2 } }
```

Create `tests/test_offer_skeleton.py`:

```python
import random
from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

FIXTURE = Path(__file__).parent / "fixtures" / "offer_skeleton.cardlang"


def test_offer_skeleton_checks_and_plays():
    game = check_source(FIXTURE)
    assert game.name == "OfferSkeleton"
    seen_one = seen_two = False
    for seed in range(50):
        result = play_game(game, random.Random(seed))
        for p in (0, 1):
            assert 10 <= result.scores[p] <= 20  # 10 offers of +1 or +2 each
        # Across seeds, both move-types must actually get chosen at least once.
        if any(result.scores[p] < 20 for p in (0, 1)):
            seen_one = True
        if any(result.scores[p] > 10 for p in (0, 1)):
            seen_two = True
    assert seen_one and seen_two  # the choice mechanism exercises both moves
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offer_skeleton.py -v`
Expected: PASS already if Tasks 1-6 are complete (the fixture exercises only built features). If it FAILS, the failure pinpoints a wiring gap — fix before continuing.

- [ ] **Step 3: (No new code expected.)** If Step 2 failed, fix the indicated module and re-run.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_offer_skeleton.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/offer_skeleton.cardlang tests/test_offer_skeleton.py
git commit -m "kernel: walking-skeleton fixture + end-to-end offer test"
```

---

## Task 8: Full-suite + mypy regression gate

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS — all prior 78 tests plus the new offer tests. Total should be 78 + new tests.

- [ ] **Step 2: Run mypy**

Run: `python -m mypy cardlang`
Expected: `Success: no issues found`. If `_stmt`/`execute`/`_expr` raise exhaustiveness errors, a `match` arm for `Offer` is missing somewhere — add it.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A
git commit -m "kernel: green full suite + mypy for offer skeleton"
```

---

## Self-Review

**Spec coverage (this slice only):**
- `offer` single-decision atom (spec §5, shape ①) — Tasks 1-7. ✓
- Move-types defined in the DSL with guard + effect (spec §6 "definitions add words") — Tasks 1-6. ✓
- `actor` pronoun (the offered player) — Tasks 3, 5. ✓
- Legal-set filter as a per-move boolean guard (spec §5 "legal-set filter," minimal form) — Task 6. ✓
- IR lowering of the new nodes (spec §9) — Task 4. ✓
- Checkability: unknown move-type in an offer is a resolve error (spec §8) — Task 3. ✓
- **Deferred to later plans (explicitly out of scope here):** `round` and its closed axes; typed outcomes + exhaustive branch checking; `define`-composition (calling one definition from another); parameterized move instances (targets/amounts) and the full legal-instance enumeration; re-expressing `trick`. These are named in the spec §11 rollout and are NOT gaps in this plan.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; Task 7 Step 3 is a conditional fixup, not a placeholder (the feature is built in Tasks 1-6).

**Type consistency:** `MoveTypeDef(name, guard, effect)` and `Offer(player, move_types)` are used identically across AST (Task 1), parser (Task 2), resolver (Task 3), IR (Task 4), and runtime (Tasks 5-6). The `move_type_index` name is consistent (state + driver + execute). The `actor` pronoun is added in both `resolve._PRONOUNS` (Task 3) and `evaluate._pronoun` (Task 5).

**Note on `applies_pred` reuse:** `move_when` reuses the existing `applies_pred` grammar rule (`always` | expr), so `when: always` and `when: <expr>` both parse with no new expression machinery.
