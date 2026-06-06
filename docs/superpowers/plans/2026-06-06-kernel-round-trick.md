# Kernel `round` (trick) — replace `Trick` in Oh Hell

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Introduce a first-class `round` construct (a turn-order card-play pass that binds `outcome`) and use it to replace the opaque `instantiate Trick(...)` mechanic in **Oh Hell**, with `tests/test_playout_oh_hell.py` passing unchanged — proving the kernel can subsume `Trick` correctly.

**Architecture:** `round play_to_trick from <leader> over <participants> source <hand-zone> into <play-zone> outcome <fn> [trump <expr>]` lowers to the *same* `run_trick` core that `Trick` uses (legal-card filtering via the active-rules engine, led-suit tracking, outcome fn), but with routing left to the phase body. The construct binds `outcome` (the winning player) for subsequent statements, exactly like `instantiate`. Behavior is identical by construction; Oh Hell's playout (incl. RNG consumption) is unchanged.

**Tech Stack:** Python 3.11, Lark, frozen-dataclass AST, strict mypy, pytest.

**Scope guard:** NOT in scope (later plans): rule-delta transitions during a round (Hearts/Spades hearts-broken), early-termination (Getaway tochoo), `define`/parameterized reusable `trick`, typed outcomes beyond binding `outcome`. Keep all 88 tests + mypy green. Only Oh Hell changes among the games.

---

## Task A: AST + grammar + parser for `Round`

**Files:** `cardlang/ast/nodes.py`, `cardlang/grammar/cardlang.lark`, `cardlang/parse.py`. Test: `tests/test_round_parse.py`.

- [ ] **Step 1 — failing test** `tests/test_round_parse.py`:

```python
from cardlang.ast import nodes as n
from cardlang.parse import parse_text

SRC = """
game G {
  players: 4
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  captured[player] : PlayerPile<player> }
  state { leader : Player? = none  trump_suit : Suit? = none }
  phase play {
    active_rules: [MustFollowSuit]
    legal_moves: [play_to_trick]
    round play_to_trick from leader over all players source hand into trick_pile outcome highest_trump_or_led_suit trump trump_suit
    leader := outcome
  }
  winner: highest leader
}
rule MustFollowSuit { constrains: play_to_trick  applies_when: state.led_suit is not none  demands: hand.cards_of_suit(state.led_suit) }
"""


def test_round_parses():
    game = parse_text(SRC, "g.cardlang")
    rnd = next(i for i in game.phases[0].items if isinstance(i, n.Round))
    assert rnd.move_type == "play_to_trick"
    assert rnd.source_zone == "hand" and rnd.play_zone == "trick_pile"
    assert rnd.outcome_fn == "highest_trump_or_led_suit"
    assert isinstance(rnd.leader, n.NameRef) and rnd.leader.name == "leader"
    assert isinstance(rnd.participants, n.AllPlayers)
    assert rnd.trump is not None and isinstance(rnd.trump, n.NameRef)
```

- [ ] **Step 2 — run, expect FAIL** (`n.Round` missing / Lark error). `python -m pytest tests/test_round_parse.py -v`

- [ ] **Step 3a — AST** in `cardlang/ast/nodes.py`, add near `Instantiate`:

```python
@dataclass(frozen=True, slots=True)
class Round:
    """`round <move_type> from <leader> over <participants> source <zone> into
    <zone> outcome <fn> [trump <expr>]` — a turn-order pass where each
    participant makes one card play (filtered by the active rules), then the
    outcome function picks the winner, which is bound as `outcome`. Routing is
    left to the surrounding body."""

    move_type: str
    leader: Expr
    participants: Expr
    source_zone: str
    play_zone: str
    outcome_fn: str
    trump: Expr | None
    span: Span | None = None
```

Add `Round` to the `Stmt` and `Node` unions.

- [ ] **Step 3b — grammar** in `cardlang/grammar/cardlang.lark`, add `round_stmt` to `?statement` and the production (near `instantiate`):

```
round_stmt: "round" NAME "from" expr "over" expr "source" NAME "into" NAME "outcome" NAME ["trump" expr]   -> round_stmt
```

Note: the optional `["trump" expr]` — verify the `expr` for `over` doesn't greedily swallow the `source` keyword (Earley should handle it since `source`/`into`/`outcome`/`trump` are keywords; if there's ambiguity, report it).

- [ ] **Step 3c — parser** in `cardlang/parse.py`, add to `_Builder`:

```python
    def round_stmt(self, meta: Meta, c: list[object]) -> n.Round:
        trump = _as_expr(c[6]) if len(c) > 6 and c[6] is not None else None
        return n.Round(
            move_type=str(c[0]),
            leader=_as_expr(c[1]),
            participants=_as_expr(c[2]),
            source_zone=str(c[3]),
            play_zone=str(c[4]),
            outcome_fn=str(c[5]),
            trump=trump,
            span=self._span(meta),
        )
```

Verify child ordering by printing the parse tree if needed (the keyword tokens are filtered by Lark, so `c` should be [NAME, expr(leader), expr(participants), NAME(source), NAME(into), NAME(outcome), expr(trump)?]).

- [ ] **Step 4 — run test, expect PASS.** Then `python -m pytest -q` and `python -m mypy cardlang` — note: adding `Round` to `Stmt` will make `ir._stmt` and `runtime.execute.execute` fail mypy exhaustiveness. Add temporary stubs to BOTH (replaced in Tasks C/D):
  - in `cardlang/ir.py` `_stmt` before `assert_never`: `case n.Round(): raise NotImplementedError("Round IR lowering — Task C")`
  - in `cardlang/runtime/execute.py` `execute` before `assert_never`: `case n.Round(): raise NotImplementedError("Round execution — Task D")`

  Re-run full suite + mypy: expect green.

- [ ] **Step 5 — commit**

```bash
git add cardlang/ast/nodes.py cardlang/grammar/cardlang.lark cardlang/parse.py cardlang/ir.py cardlang/runtime/execute.py tests/test_round_parse.py
git commit -m "kernel: Round AST + grammar + parser (with IR/execute stubs)"
```

---

## Task B: Resolver for `Round`

**Files:** `cardlang/resolve.py`. Test: `tests/test_round_resolve.py`.

The generic `_rewrite` already classifies `Round.leader`, `Round.participants`, `Round.trump` (they're `Expr` fields). The string fields (`source_zone`, `play_zone`, `outcome_fn`, `move_type`) need structural checks.

- [ ] **Step 1 — failing test** `tests/test_round_resolve.py`:

```python
from cardlang.pipeline import check_dsl
from tests.test_round_parse import SRC


def test_round_resolves_clean():
    game = check_dsl(SRC, "g.cardlang")
    assert game.name == "G"


def test_round_unknown_zone_errors():
    bad = SRC.replace("source hand", "source nope")
    try:
        check_dsl(bad, "g.cardlang")
        assert False
    except Exception as exc:
        assert "nope" in str(exc)
```

- [ ] **Step 2 — run, expect FAIL** (unknown zone not caught; possibly outcome_fn unresolved).

- [ ] **Step 3 — resolver** in `cardlang/resolve.py` `_validate_refs`, add a case (after the `Offer` case):

```python
            case n.Round():
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.error(f"round source zone '{nd.source_zone}' is unknown", nd.span)
                if nd.play_zone not in zone_names:
                    bag.error(f"round play zone '{nd.play_zone}' is unknown", nd.span)
                if nd.outcome_fn not in STDLIB_VALUE_NAMES:
                    bag.error(f"round outcome '{nd.outcome_fn}' is unknown", nd.span)
                if nd.move_type not in LIBRARY_MOVE_TYPES:
                    bag.error(f"round move type '{nd.move_type}' is unknown", nd.span)
```

(`STDLIB_VALUE_NAMES` and `LIBRARY_MOVE_TYPES` are already imported in resolve.py. Hoist `zone_names` above the loop if you prefer, matching the `defined_move_types` style.)

- [ ] **Step 4 — run test, expect PASS.** Full suite + mypy green.

- [ ] **Step 5 — commit**

```bash
git add cardlang/resolve.py tests/test_round_resolve.py
git commit -m "kernel: resolve Round zones/outcome/move-type references"
```

---

## Task C: IR emission for `Round`

**Files:** `cardlang/ir.py`. Test: `tests/test_round_ir.py`.

- [ ] **Step 1 — failing test** `tests/test_round_ir.py`:

```python
from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from tests.test_round_parse import SRC


def test_round_ir():
    ir = emit(check_dsl(SRC, "g.cardlang"))
    items = ir["phases"][0]["items"]
    rnd = next(i for i in items if i["kind"] == "round")
    assert rnd["move_type"] == "play_to_trick"
    assert rnd["source_zone"] == "hand" and rnd["play_zone"] == "trick_pile"
    assert rnd["outcome_fn"] == "highest_trump_or_led_suit"
    assert rnd["trump"]["kind"] == "name"
```

- [ ] **Step 2 — run, expect FAIL** (NotImplementedError stub).

- [ ] **Step 3 — REPLACE the `case n.Round()` stub** in `_stmt`:

```python
        case n.Round():
            return {
                "kind": "round",
                "move_type": s.move_type,
                "leader": _expr(s.leader),
                "participants": _expr(s.participants),
                "source_zone": s.source_zone,
                "play_zone": s.play_zone,
                "outcome_fn": s.outcome_fn,
                "trump": _expr(s.trump) if s.trump is not None else None,
            }
```

- [ ] **Step 4 — run test, expect PASS.** Full suite + mypy green. (No golden changes — no existing game uses `round` yet.)

- [ ] **Step 5 — commit**

```bash
git add cardlang/ir.py tests/test_round_ir.py
git commit -m "kernel: emit Round to IR"
```

---

## Task D: Runtime — execute `Round` via the `run_trick` core

**Files:** `cardlang/runtime/execute.py`, `cardlang/runtime/mechanics.py`. Test: `tests/test_round_execute.py`.

The Round executor reuses `run_trick` (in `mechanics.py`) exactly as `instantiate Trick` does, but with `routing_body=()` (routing is in the body) and `early_term=None`. It binds the winner as `outcome`.

- [ ] **Step 1 — failing test** `tests/test_round_execute.py`:

```python
import random
from cardlang.pipeline import check_dsl

SRC = """
game G {
  players: 4
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  trump: spades
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  captured[player] : PlayerPile<player> }
  state { tricks_won[player] : Integer = 0  leader : Player? = none }
  phase deal { shuffle deck  deal 13 cards from deck to each hand  leader := 0 }
  phase play {
    active_rules: [MustFollowSuit]
    legal_moves: [play_to_trick]
    repeat until (all player p: hand[p] is empty) {
      round play_to_trick from leader over all players source hand into trick_pile outcome highest_trump_or_led_suit
      move all cards from trick_pile to captured[outcome]
      tricks_won[outcome] += 1
      leader := outcome
    }
  }
  winner: highest tricks_won
}
rule MustFollowSuit { constrains: play_to_trick  applies_when: state.led_suit is not none  demands: hand.cards_of_suit(state.led_suit) }
"""


def test_round_plays_full_tricks_and_conserves_cards():
    from cardlang.runtime.driver import play_game
    game = check_dsl(SRC, "g.cardlang")
    for seed in range(20):
        plays = []
        tricks = []
        census = {}
        def tr(e, d):
            if e == "play": plays.append(d)
            elif e == "trick": tricks.append(d)
            elif e == "game_end": census.clear(); census.update(d)
        result = play_game(game, random.Random(seed), tr)
        assert len(tricks) == 13 and len(plays) == 52
        assert census["total"] == 52 and census["hands_with_cards"] == 0
        assert sum(result.scores.values()) == 13  # 13 tricks distributed
```

- [ ] **Step 2 — run, expect FAIL** (NotImplementedError stub).

- [ ] **Step 3a — a Round runner in `mechanics.py`.** Add a function that mirrors `instantiate`'s Trick path but for `n.Round`, calling `run_trick`:

```python
def run_round(stmt: n.Round, ctx: Ctx) -> Player:
    participants = evaluate(stmt.participants, ctx)
    leader = evaluate(stmt.leader, ctx)
    outcome_fn = stdlib.value_function(stmt.outcome_fn)
    trump = evaluate(stmt.trump, ctx) if stmt.trump is not None else ctx.rs.trump
    play_rules = phases.compute_active_rules(ctx.current_phase, ctx.rs)
    return run_trick(
        participants=list(participants),
        leader=leader,
        source_family=stmt.source_zone,
        play_zone=stmt.play_zone,
        play_rules=play_rules,
        outcome_fn=outcome_fn,
        routing_body=(),          # routing is done in the surrounding body
        early_term=None,
        trump=trump,
        ctx=ctx,
    )
```

`stdlib` and `evaluate`/`phases`/`run_trick` are already imported in mechanics.py (verify; `value_function` lives in `cardlang.runtime.stdlib`). Add an import if needed.

- [ ] **Step 3b — REPLACE the `case n.Round()` stub** in `cardlang/runtime/execute.py` `execute`:

```python
        case n.Round():
            return ctx.with_outcome(mechanics.run_round(stmt, ctx))
```

(`mechanics` is already imported in execute.py.)

- [ ] **Step 4 — run test, expect PASS.** Full suite + mypy green.

- [ ] **Step 5 — commit**

```bash
git add cardlang/runtime/mechanics.py cardlang/runtime/execute.py tests/test_round_execute.py
git commit -m "kernel: execute Round via the run_trick core (binds outcome)"
```

---

## Task E: Convert Oh Hell to `round`; validate playout unchanged

**Files:** `docs/games/oh-hell.cardlang`, `docs/games/oh-hell.md`. Test: existing `tests/test_playout_oh_hell.py` (unchanged).

- [ ] **Step 1 — baseline.** Run `python -m pytest tests/test_playout_oh_hell.py -q` — confirm it passes BEFORE the change (it should; Oh Hell currently uses `instantiate Trick`).

- [ ] **Step 2 — edit `docs/games/oh-hell.cardlang`.** Replace the `instantiate Trick (...)` block inside the `play` phase's `repeat until` loop with:

```
        round play_to_trick from leader over all players source hand into trick_pile
              outcome highest_trump_or_led_suit trump trump_suit
        move all cards from trick_pile to captured[outcome]
        tricks_won[outcome] += 1
        leader := outcome
```

The surrounding `phase play { active_rules: [MustFollowSuit]  legal_moves: [play_to_trick]  repeat until (all player p: hand[p] is empty) { ... } }` stays. Update the file's header comment to note Oh Hell's trick uses the kernel `round` construct (no longer the `Trick` mechanic).

- [ ] **Step 3 — run the EXISTING playout, expect PASS UNCHANGED:**

```bash
python -m pytest tests/test_playout_oh_hell.py -q
```

Expected: PASS (100 games; per-trick winner correctness, 109 tricks, card conservation all still hold). If it fails, the `round` runtime diverges from `Trick` — debug (likely the routing-in-body ordering or trump arg). Do NOT weaken the test.

- [ ] **Step 4 — mirror the change in `docs/games/oh-hell.md`** (the readable twin) so the fenced DSL matches `oh-hell.cardlang`, and confirm it still checks: `python -c "from cardlang.pipeline import check_source; print(check_source('docs/games/oh-hell.md').name)"`.

- [ ] **Step 5 — full regression:** `python -m pytest -q` (expect all green) and `python -m mypy cardlang` (Success). Commit:

```bash
git add docs/games/oh-hell.cardlang docs/games/oh-hell.md
git commit -m "Oh Hell: play tricks via the kernel round construct (replaces Trick)"
```

---

## Self-Review

- **Goal:** Oh Hell's trick now runs on the first-class `round` kernel construct, not `instantiate Trick`; its playout passes unchanged (Task E Step 3). ✓
- **Round** added end-to-end: AST/grammar/parser (A), resolver (B), IR (C), runtime via `run_trick` reuse (D). ✓
- **Behavior identical by construction:** `run_round` calls the same `run_trick` with the same rules/outcome/trump; routing moved to the body is a deterministic move-all with no RNG. ✓
- **Deferred (not gaps):** rule-delta transitions, early-termination, `define`/reusable `trick`, typed outcomes. Hearts/Getaway/Spades keep `instantiate Trick`. ✓
- **Type consistency:** `n.Round` fields (`move_type/leader/participants/source_zone/play_zone/outcome_fn/trump`) identical across AST, parser, IR, runtime.
