# `turns` form + joint-predicate selection + Gin Rummy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `turns` kernel form (strict rotation + go-again axis) and the `where jointly` / `some` movement surface, anchored by a full-fidelity Gin Rummy corpus game and a byte-identical Go Fish migration.

**Architecture:** Two new closed constructs ride the existing pipeline (grammar → parse → resolve → typecheck → expand → deckcheck → IR → runtime → OpenSpiel encoding), each added exactly the way the `as` block was: an AST node in the `Stmt`/`Node` unions whose dispatcher arms are forced by `assert_never` under mypy --strict. Gin's combinatorics live in game-local pure primitives (`cardlang/runtime/gin.py`, the Cribbage pattern). Spec: `docs/superpowers/specs/2026-07-17-turns-form-jointly-gin-design.md`.

**Tech Stack:** Python 3.11, lark (Earley), pytest, mypy --strict.

## Global Constraints

- Run `mypy` bare (never `mypy cardlang`) and full `pytest -q` before any push; `PYTHONHASHSEED=0` for exact-score tests.
- Surface-totality audit artifacts are mandatory: misuse-probe rejection tests + a completeness ledger in each construct's test-module docstring (one ledger per construct).
- Every grammar-accepted combination is implemented or statically rejected with a located diagnostic — never accepted-but-ignored; runtime failures are typed errors, never bare asserts (`tests/test_assert_triage.py` gates this).
- Corpus lockstep: `docs/games/*.cardlang` and DSL-bearing `.md` twins move in the same change; new fenced examples in decisions/library/model.md need a tag + (for fragments) a labeled `WRAPPER_RECIPES` entry (`tests/test_doc_snippets.py`).
- Go Fish migration must be byte-identical (existing playout tests + goldens unchanged); new-game goldens get pinned fresh.
- Commit after every green task; commit order: turns → jointly → primitives → gin → go-fish → docs.

---

### Task 1: `turns` grammar + AST + parse

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (statement alternatives ~L141-159; production near `round_stmt` ~L235)
- Modify: `cardlang/ast/nodes.py` (node after `AsBlock`; both `Stmt` ~L631 and `Node` ~L1041 unions)
- Modify: `cardlang/parse.py` (transformer near `as_block` ~L549)
- Create: `tests/test_turns_form.py`

**Interfaces:**
- Produces: `n.Turns(binder: str, leader: Expr, participants: Expr, termination: Expr, again: str | None, body: tuple[Stmt, ...], span)` — every later task consumes this node shape.

- [ ] **Step 1: Write the failing parse test** (`tests/test_turns_form.py`; module docstring carries the completeness ledger, filled through Tasks 1–3):

```python
"""The `turns` form (decisions.md "The `turns` form").

property:   `turns <binder> from <leader> over <participants> until <pred>
            [again <var>] { body }` rotates through the participants in game
            direction, binding the current player (binder + acting player)
            per turn, terminating when the predicate holds at a turn
            boundary; `again <var>` (a declared Boolean state var) repeats
            the same player's turn when true. Every grammar-accepted
            combination executes or is statically rejected.
domain:     clause presence (again present/absent) × (leader, participants,
            termination ∈ Expr) × (body ∈ Stmt*) × runtime states
            (participants empty / current filtered out / again with
            non-Boolean var).
registry:   the Stmt/Node unions (assert_never dispatch in resolve,
            typecheck ×4, ir, deckcheck, execute — mypy-forced) plus the
            generic walkers (expand, openspiel/encoding) whose wall is
            reflection over dataclass fields.
covered:    (filled per task: parse shapes; resolve/typecheck rejections;
            rotation/again/until runtime semantics; no-participant wall.)
sampled:    body statement kinds run through the same execute dispatch used
            by `if`/`as` — the form adds rotation, not per-statement logic.
residual:   `direction` override clause — not grammar (no corpus user);
            recorded in roadmap.md "Grammar surface deferred by the checker".
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _walk
from cardlang.runtime.driver import play_game


def _game(body: str, extra_state: str = "") -> str:
    return (
        "game G {\n"
        "  players: 3\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player>\n"
        "          discard : Discard }\n"
        "  state { dealer : Player = 0\n"
        "          stop : Boolean = false\n"
        f"          {extra_state}\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"{body}\n"
        "}\n"
    )


def test_turns_parses_to_a_turns_node() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop {\n"
        "    score[t] += 1\n"
        "  } }"
    )
    game = parse_text(dsl, "test.cardlang")
    nodes = [nd for nd in _walk(game) if isinstance(nd, n.Turns)]
    assert len(nodes) == 1
    assert nodes[0].binder == "t"
    assert nodes[0].again is None
    assert len(nodes[0].body) == 1


def test_turns_with_again_clause_parses() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop again go {\n"
        "    score[t] += 1\n"
        "  } }",
        extra_state="go : Boolean = false",
    )
    game = parse_text(dsl, "test.cardlang")
    nodes = [nd for nd in _walk(game) if isinstance(nd, n.Turns)]
    assert nodes[0].again == "go"
```

- [ ] **Step 2: Run to verify RED**: `python -m pytest tests/test_turns_form.py -q` — expect syntax error from `parse_to_tree` (no `turns` production).

- [ ] **Step 3: Grammar.** In `cardlang.lark`: add `| turns_stmt` to the `?statement` alternatives, then next to the round productions:

```lark
// The turn loop beneath the round forms (decisions.md "The `turns` form"):
// rotate through the participants in game direction, binding each current
// player (binder + acting player) for a braced body of statements, until the
// termination predicate holds at a turn boundary. `again <var>` names a
// declared Boolean state variable; when a turn ends with it true, the same
// player takes the next turn (Go Fish's go-again). Statement-leading keyword
// like `round`, so no NAME-exclusion guard is needed.
turns_stmt: "turns" NAME "from" expr "over" expr "until" expr ["again" NAME] "{" statement* "}"
```

- [ ] **Step 4: AST node** (`nodes.py`, after `AsBlock`; add `Turns` to BOTH unions):

```python
@dataclass(frozen=True, slots=True)
class Turns:
    """`turns <binder> from <leader> over <participants> until <pred>
    [again <var>] { <stmt>* }` — the turn loop beneath the round forms.
    The binder names the current player, who is also the acting player
    (`for each`'s binding semantics, one player at a time); rotation and
    termination are owned by the form (decisions.md "The `turns` form")."""

    binder: str
    leader: Expr
    participants: Expr
    termination: Expr
    again: str | None
    body: tuple[Stmt, ...]
    span: Span | None = None
```

- [ ] **Step 5: parse transformer** (`parse.py`, next to `as_block`; with `maybe_placeholders=True` the optional `again` NAME is `None` when absent):

```python
def turns_stmt(self, meta: Meta, c: list[object]) -> n.Turns:
    # c: [NAME(binder), expr(leader), expr(participants), expr(until),
    #     NAME(again)|None, statement*]
    return n.Turns(
        binder=str(c[0]),
        leader=_as_expr(c[1]),
        participants=_as_expr(c[2]),
        termination=_as_expr(c[3]),
        again=str(c[4]) if c[4] is not None else None,
        body=tuple(_as_stmt(s) for s in c[5:]),
        span=self._span(meta),
    )
```

- [ ] **Step 6: GREEN on the two parse tests**; mypy will now FAIL on every statement dispatcher (`assert_never` sites) — that failing list is Task 2–3's exact worklist. Run `mypy 2>&1 | grep Turns` and copy the site list into the Task 2 checklist.

- [ ] **Step 7: Commit** `feat(turns): grammar, AST node, parse transformer`.

---

### Task 2: `turns` resolve + typecheck

**Files:**
- Modify: `cardlang/resolve.py` (`_node_binders` match ~L232-301; `_BINDER_SCOPE_FIELDS` ~L1142)
- Modify: `cardlang/typecheck.py` (`_stmt_tree_scoped` ~L513; `_stmt_exprs` ~L1512; `_check_stmt` semantics match ~L1648; `_control_flow_nodes` ~L1916; `check_produces_scope` isinstance chain ~L2049)
- Test: `tests/test_turns_form.py`

**Interfaces:**
- Consumes: `n.Turns` from Task 1.
- Produces: resolve scopes `binder` to the body only; typecheck types the binder `TPlayer()`, requires `leader` assignable to Player, `participants` a player collection, `termination` Boolean, and `again` a declared Boolean state var.

- [ ] **Step 1: Failing rejection tests** (append to `tests/test_turns_form.py`):

```python
def test_binder_is_scoped_to_the_body_only() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop { score[t] += 1 }\n"
        "            score[t] += 1 }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "unresolved name 't'" in e.value.diagnostic.message


def test_non_boolean_until_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until dealer { score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "Boolean" in e.value.diagnostic.message


def test_non_player_leader_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from stop over all players until stop { score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "Player" in e.value.diagnostic.message


def test_undeclared_again_var_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop again ghost {\n"
        "    score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError):
        check_dsl(dsl, "test.cardlang")


def test_non_boolean_again_var_is_rejected() -> None:
    dsl = _game(
        "  phase p { turns t from dealer over all players until stop again dealer {\n"
        "    score[t] += 1 } }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "test.cardlang")
    assert "Boolean" in e.value.diagnostic.message


def test_turns_checks_clean() -> None:
    check_dsl(
        _game(
            "  phase p { turns t from dealer over all players until stop {\n"
            "    score[t] += 1  stop := true\n"
            "  } }"
        ),
        "test.cardlang",
    )
```

- [ ] **Step 2: RED** (assert_never in resolve).

- [ ] **Step 3: resolve.** `_node_binders`: add a binding arm (NOT the binds-nothing group):

```python
case n.Turns():
    return (node.binder,)
```

`_BINDER_SCOPE_FIELDS`: add `n.Turns: ("body",)` — the binder scopes to the body only; leader/participants/termination evaluate in the enclosing scope. The `again` field is a plain `str`, not a NameRef, so `_rewrite`'s generic traversal ignores it; validate it in resolve where `RotateStmt.target`-style state-var names are checked — a `bag.error` if `again` names no declared state variable:

```python
# In the pass that validates statement-level state-var references (with the
# rotate wall), add:
case n.Turns() if nd.again is not None and nd.again not in state_vars:
    bag.error(
        f"`again {nd.again}`: names no declared state variable — the "
        f"go-again flag is ordinary game state the body's effects write",
        nd.span,
    )
```

- [ ] **Step 4: typecheck.** Five arms:

```python
# _stmt_tree_scoped — binder typed Player, body descended:
case n.Turns():
    yield from _seq_tree_scoped(s.body, binders + ((s.binder, TPlayer()),))

# _stmt_exprs — the three expression positions:
case n.Turns():
    return [s.leader, s.participants, s.termination]

# _check_stmt semantics — leader must be a Player, participants a player
# collection, termination Boolean, again (when present) a Boolean state var:
case n.Turns():
    lt = infer(stmt.leader, env)
    if not assignable(lt, TPlayer()):
        bag.error(
            f"`turns … from` names the first player — expected Player, "
            f"got {_type_name(lt)}", stmt.span,
        )
    pt = infer(stmt.participants, env)
    if not (isinstance(pt, TAny) or
            (isinstance(pt, TCollection) and assignable(pt.element, TPlayer()))):
        bag.error(
            f"`turns … over` names the participants — expected a collection "
            f"of players, got {_type_name(pt)}", stmt.span,
        )
    _check_bool(stmt.termination, env, bag, "turns `until` condition")
    if stmt.again is not None:
        at = env.lookup_state(stmt.again)   # mirror how rotate's target type is read
        if at is not None and not assignable(at, TBoolean()):
            bag.error(
                f"`again {stmt.again}`: the go-again flag must be Boolean, "
                f"got {_type_name(at)}", stmt.span,
            )

# _control_flow_nodes — transparent like IfStmt/AsBlock:
case n.Turns():
    for s in stmt.body:
        yield from _control_flow_nodes(s)

# check_produces_scope — a loop: phase producers are NOT available inside
# (same rule as RepeatUntil/ForEach):
elif isinstance(stmt, (n.RepeatUntil, n.ForEach, n.EachSimultaneous, n.Turns)):
    bodies = (
        stmt.body
        if isinstance(stmt, (n.RepeatUntil, n.Turns))
        else (stmt.body,)
    )
```

(Exact helper names — `env.lookup_state`, `TBoolean` — mirror the arms already present in `_check_stmt`; read the neighboring `RotateStmt`/`Round` arms and use the same accessors.)

- [ ] **Step 5: GREEN** on all Task-2 tests. **Step 6: Commit** `feat(turns): resolve + typecheck arms`.

---

### Task 3: `turns` IR + deckcheck + runtime

**Files:**
- Modify: `cardlang/ir.py` (~L296, beside the `as` arm), `cardlang/deckcheck.py` (~L228 beside `RepeatUntil`), `cardlang/runtime/execute.py` (dispatch ~L51; executor beside `_for_each` ~L399)
- Test: `tests/test_turns_form.py`

**Interfaces:**
- Produces: runtime semantics later tasks rely on — until-before-every-turn, direction rotation with per-advance participants re-evaluation, again-repeats, loud no-participant error.

- [ ] **Step 1: Failing runtime-semantics tests:**

```python
def _run(dsl_body: str, extra_state: str = "", seed: int = 0) -> list[Any]:
    game = check_dsl(_game(dsl_body, extra_state), "test.cardlang")
    calls: list[Any] = []

    def chooser(p: int, cands: list[Any], k: int) -> list[Any]:
        calls.append((p, len(cands)))
        return list(cands[:k])

    play_game(game, random.Random(seed), chooser=chooser)
    return calls


def test_rotation_binds_each_participant_in_direction_order() -> None:
    game = check_dsl(
        _game(
            "  phase p { turns t from 1 over all players until score[0] > 0 {\n"
            "    score[t] += 10\n"
            "  } }"
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    # From seat 1 clockwise: 1, 2, then 0 scores and `until` fires before seat 1 again.
    assert result.scores == {0: 10, 1: 10, 2: 10}


def test_until_is_checked_before_the_first_turn() -> None:
    game = check_dsl(
        _game("  phase p { stop := true\n"
              "            turns t from 0 over all players until stop { score[t] += 1 } }"),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    assert all(v == 0 for v in result.scores.values())  # body never ran


def test_participants_reevaluated_per_advance() -> None:
    # Seat 1 is excluded once their score is nonzero — the filter sees mid-loop state.
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over players where score[player] < 10\n"
            "            until score[2] >= 20 {\n"
            "    score[t] += 10\n"
            "  } }"
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    # 0,1,2 each take one turn (all reach 10, leaving the filter), then only
    # seat 2 was needed again — but everyone is now filtered out; until fired
    # exactly at 2's second turn... pin the actual invariant:
    assert result.scores[2] == 20 and result.scores[0] == 10


def test_again_repeats_the_same_player() -> None:
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over all players until score[0] >= 2 again go {\n"
            "    score[t] += 1\n"
            "    go := (t is 0) and (score[0] < 2)\n"
            "  } }",
            extra_state="go : Boolean = false",
        ),
        "test.cardlang",
    )
    result = play_game(game, random.Random(0))
    # Seat 0 goes twice back-to-back; nobody else ever gets a turn.
    assert result.scores == {0: 2, 1: 0, 2: 0}


def test_no_eligible_participant_is_a_loud_error() -> None:
    game = check_dsl(
        _game(
            "  phase p { turns t from 0 over players where score[player] > 99\n"
            "            until stop { score[t] += 1 } }"
        ),
        "test.cardlang",
    )
    with pytest.raises(RuntimeError, match="no eligible participant"):
        play_game(game, random.Random(0))
```

- [ ] **Step 2: RED** (assert_never in execute).

- [ ] **Step 3: IR arm:**

```python
case n.Turns():
    return {
        "kind": "turns",
        "binder": s.binder,
        "leader": _expr(s.leader),
        "participants": _expr(s.participants),
        "termination": _expr(s.termination),
        "again": s.again,
        "body": [_stmt(x) for x in s.body],
    }
```

- [ ] **Step 4: deckcheck arm** (beside `RepeatUntil`, same reasoning — iteration count is runtime data, zero-iteration execution always possible):

```python
case n.Turns():
    # A turn loop's iteration count is runtime data (same currency as
    # `repeat until`): deals inside are not statically boundable, and
    # carrying `carry` across is sound because `until` is checked before
    # the first turn, so the zero-iteration execution always exists.
    return carry, carry
```

- [ ] **Step 5: runtime executor** (`execute.py`; dispatch arm `case n.Turns(): _turns(stmt, ctx); return ctx` plus):

```python
def _turns(stmt: n.Turns, ctx: Ctx) -> None:
    """The turn loop beneath the round forms (decisions.md "The `turns`
    form"). Each iteration: check `until` (a turn boundary — before the
    FIRST turn too, so the zero-iteration run exists); pick the player —
    the previous player again when the `again` state var reads true, else
    the next seat in game direction; skip seats failing the participants
    predicate (re-evaluated per advance, so elimination falls out); bind
    binder + acting player (the seat wall in `acting_as` guards the bind)
    and run the body as a block scope. A full lap with no eligible
    participant is a malformed game (who plays?) — loud, like `offer`'s
    no-legal-move rule, never a silent skip or an infinite spin."""
    order = ctx.rs.seating.players  # already in game direction
    current: Player | None = None
    while not evaluate(stmt.termination, ctx):
        if current is not None and stmt.again is not None and bool(ctx.rs.get(stmt.again)):
            candidate_seq = [current] + _next_seats(order, current)
        elif current is None:
            leader = evaluate(stmt.leader, ctx)
            candidate_seq = [leader] + _next_seats(order, leader)
        else:
            candidate_seq = _next_seats(order, current)
        participants = set(_elements(evaluate(stmt.participants, ctx)))
        player = next((p for p in candidate_seq if p in participants), None)
        if player is None:
            raise RuntimeError(
                "turns: no eligible participant — every seat fails the "
                "`over` predicate; narrow the loop's `until` so the form "
                "is not asked to find a turn nobody can take"
            )
        body_ctx = ctx.with_local(stmt.binder, player).acting_as(player)
        run_body(stmt.body, body_ctx)
        current = player


def _next_seats(order: tuple[Player, ...], frm: Player) -> list[Player]:
    """One full lap starting after `frm`, in seating (game-direction) order."""
    i = order.index(frm)
    return [order[(i + k) % len(order)] for k in range(1, len(order) + 1)]
```

(`_elements` is the existing collection-flattening helper `evaluate` siblings use — import it as `rules.py` does. `Player` import from `runtime.values`.)

- [ ] **Step 6: GREEN + mypy fully clean** (this closes every `Turns` dispatcher). Fix `test_procedures.py`'s `_BODY_ACCEPTED`/`_BODY_REJECTED` partition: `Turns` goes in `_BODY_REJECTED`-style handling ONLY if a wall exists — it does not; a `turns` in a procedure body has no position-dependent validity, so add `"Turns"` to `_BODY_ACCEPTED` and exercise it in the kitchen-sink procedure (`turns w from seat over all players until score[seat] > 0 { score[w] += 0 ... }` — check the existing probe game's vocabulary). If the exercise reveals a genuine wall need, reclassify with a loud resolve wall + roadmap record instead.

- [ ] **Step 7: Commit** `feat(turns): IR, deckcheck, runtime executor — full construct row`.

---

### Task 4: `where jointly` + amount `some` — grammar through typecheck

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (`where_clause` ~L201, `amount` ~L205, anchored terminal near `_IS_KW` ~L520)
- Modify: `cardlang/ast/nodes.py` (`Movement` fields), `cardlang/parse.py` (movement builder), `cardlang/resolve.py` (`_node_binders` Movement arms ~L240), `cardlang/typecheck.py` (movement filter binding + walls)
- Create: `tests/test_jointly_selection.py`

**Interfaces:**
- Produces: `Movement.joint: bool` (False default) and amount value `"some"`; joint filters bind `cards : Collection<Card>`; walls: `jointly ⇒ chosen`, `some ⇒ jointly`.

- [ ] **Step 1: Failing tests** (`tests/test_jointly_selection.py`; its docstring carries the second ledger — property: joint selection offers exactly the subsets of the source satisfying the joint predicate, sized per the amount; domain: verb × selection-mode × amount(one/expr/all/some) × filter-mode(none/each/joint) × destination; registry: the movement grammar matrix; residual: `random`+jointly and dealt+jointly and `some` without jointly — all walled loudly, recorded in roadmap.md):

```python
def test_jointly_parses_with_cards_binder() -> None:
    game = parse_text(_game(
        "  phase p { move chosen some cards from hand[0]\n"
        "            where jointly (number of cards in cards) >= 3 to discard }"
    ), "t.cardlang")
    mv = [nd for nd in _walk(game) if isinstance(nd, n.Movement)][0]
    assert mv.joint and mv.amount == "some"


def test_jointly_requires_chosen() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(_game(
            "  phase p { move some cards from hand[0]\n"
            "            where jointly (number of cards in cards) >= 3 to discard }"
        ), "t.cardlang")
    assert "chosen" in e.value.diagnostic.message


def test_some_requires_jointly() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(_game(
            "  phase p { move chosen some cards from hand[0] to discard }"
        ), "t.cardlang")
    assert "jointly" in e.value.diagnostic.message


def test_cards_binder_is_a_card_collection_and_scoped_to_the_filter() -> None:
    # `cards` resolves inside the joint pred; outside it, unresolved.
    with pytest.raises(DiagnosticError) as e:
        check_dsl(_game(
            "  phase p { move chosen some cards from hand[0]\n"
            "            where jointly (number of cards in cards) >= 3 to discard\n"
            "            score[0] += number of cards in cards }"
        ), "t.cardlang")
    assert "cards" in e.value.diagnostic.message
```

- [ ] **Step 2: RED.** **Step 3: Grammar:**

```lark
where_clause: "where" _JOINTLY_KW expr   -> where_jointly
            | "where" expr               -> where_each
amount: "all"   -> amt_all
      | "one"   -> amt_one
      | "some"  -> amt_some
      | expr    -> amt_count
```

with, beside `_IS_KW` (same identifier-prefix trap — `jointly_valid` must stay one NAME):

```lark
_JOINTLY_KW: "jointly" /(?![A-Za-z0-9_])/
```

`some` is safe as an inline literal in the amount position only if it can never absorb an identifier there — it can (`move chosen some_var cards …` would lex `some` + `_var`); anchor it the same way: `SOME_KW: "some" /(?![A-Za-z0-9_])/` and use `SOME_KW -> amt_some`. Do NOT add `some`/`jointly` to the NAME exclusion (they are value-position words only inside movements; test `test_leading_some_identifier_still_lexes` proves `some_var := 1`-style names survive, mirroring `test_leading_as_identifier_still_lexes_as_a_name`).

- [ ] **Step 4: AST + parse.** `Movement` gains `joint: bool = False`; the two `where_clause` alternatives set it (`where_jointly` → filter=expr, joint=True). Amount `"some"` flows the same string channel as `"all"`/`"one"`.

- [ ] **Step 5: resolve.** `_node_binders` Movement arm splits:

```python
case n.Movement() | n.EpistemicOp() if node.filter is not None:
    return ("cards",) if getattr(node, "joint", False) else ("card",)
```

(EpistemicOp has no `joint` field — `getattr` default keeps it on `card`; alternatively match `n.Movement()` first with its own arm. Prefer the explicit split arm.) Walls in resolve: `joint and mode != "chosen"` → error naming `chosen`; `amount == "some" and not joint` → error naming `jointly`. Both with the movement's span.

- [ ] **Step 6: typecheck.** Where `_check_stmt_exprs` binds `card: TCard()` for movement filters, bind `cards: TCollection(TCard())` when `joint`; `_check_bool` already walls the predicate position. Amount `"some"` joins `"all"`/`"one"` in every `isinstance(amount, str)` branch — grep `amount` in typecheck/deckcheck/ir/execute and extend each string-amount site (mypy/tests catch stragglers; deckcheck: treat `some` like `all`, worst case).

- [ ] **Step 7: GREEN. Commit** `feat(jointly): joint-predicate selection surface — grammar through typecheck`.

---

### Task 5: `jointly` runtime + encoding

**Files:**
- Modify: `cardlang/runtime/execute.py` (`_select`/`_select_filtered` region ~L156-260), `cardlang/openspiel/encoding.py` (chosen-movement candidate encoding — mirror the climb combo codec), `cardlang/deckcheck.py` (amount `"some"` arm)
- Test: `tests/test_jointly_selection.py`

**Interfaces:**
- Consumes: `Movement.joint`, amount `"some"`.
- Produces: the chooser receives ONE decision whose candidates are tuples of cards (the satisfying subsets, source-order within each subset, enumeration order = `itertools.combinations` ascending by size); OpenSpiel encodes them like climb combination plays.

- [ ] **Step 1: Failing runtime tests:**

```python
def test_chooser_is_offered_exactly_the_satisfying_subsets() -> None:
    # Hand: 7♣ 7♦ 7♥ K♠. Joint pred: all same rank, >= 3 — candidates are
    # the two 7-subsets {7♣7♦7♥} only (size-3; the pred rejects any K set).
    ...build via check_dsl + a scripted RuntimeState like
    tests/test_movement_filter_execute.py::_ctx, with pred
    `(number of cards in cards) >= 3 and gin-style same-rank via
    (max of rank_value(card) over cards in cards) is
    (min of rank_value(card) over cards in cards)`...
    assert [set(c) for c in seen_candidates] == [{C7C, C7D, C7H}]


def test_enumeration_bound_is_a_loud_error() -> None:
    # A 17+-card source refuses enumeration rather than hanging.
    ...deal 17 cards to hand, run a jointly movement...
    with pytest.raises(RuntimeError, match="enumeration bound"):
        ...
```

(Write these fully at implementation using `test_movement_filter_execute.py`'s `_parse`/`_ctx` helpers — same harness, new predicate; the plan pins the assertions, the helper reuse is mechanical.)

- [ ] **Step 2: RED.** **Step 3: runtime.** In the movement selection path, before per-card filtering, branch on `stmt.joint`:

```python
_JOINT_ENUMERATION_BOUND = 16

def _select_joint(source: Zone, stmt: n.Movement, ctx: Ctx, player: Player) -> list[Card]:
    pool = list(source.cards)
    if len(pool) > _JOINT_ENUMERATION_BOUND:
        raise RuntimeError(
            f"joint selection over {len(pool)} cards exceeds the enumeration "
            f"bound ({_JOINT_ENUMERATION_BOUND}) — narrow the source pool"
        )
    sizes: range
    if stmt.amount == "some":
        sizes = range(1, len(pool) + 1)
    elif stmt.amount == "all":
        sizes = range(len(pool), len(pool) + 1)
    elif stmt.amount == "one":
        sizes = range(1, 2)
    else:
        k = int(evaluate(stmt.amount, ctx))
        sizes = range(k, k + 1)
    assert stmt.filter is not None  # grammar: jointly IS a where-clause form
    candidates = [
        subset
        for size in sizes
        for subset in itertools.combinations(pool, size)
        if bool(evaluate(stmt.filter, ctx.with_local("cards", list(subset))))
    ]
    if not candidates:
        raise RuntimeError(
            "joint selection: no subset of the source satisfies the "
            "predicate — guard the movement so it is only reached when one "
            "exists (the no-implicit-actions rule)"
        )
    chosen = ctx.chooser(player, candidates, 1)[0]
    return list(chosen)
```

Wire it where `mode == "chosen"` dispatches (joint ⇒ chosen is already walled). Observation emission: unchanged — the movement's existing `observe.movement` covers the moved set.

- [ ] **Step 4: encoding.** Follow the climb form's combination-play encoding end to end (grep `ComboAction` / `combo` in `cardlang/openspiel/encoding.py` and the adapter): joint candidates are card-tuples exactly like climb plays, so they ride the same codec. Add an encoding test in the style of the climb one: a game with one jointly decision registers ≥ 1 distinct combo action and round-trips (encode→decode) a chosen subset.

- [ ] **Step 5: GREEN + full movement-matrix probes**: dealt+jointly (RED test from Task 4 already covers), random+jointly → resolve wall test, `some` in a plain (non-jointly) deal → wall test, `deal some … from deck` deckcheck treats as `all` (test with capacity exactly at the boundary).

- [ ] **Step 6: Commit** `feat(jointly): subset enumeration runtime + combo-codec encoding`.

---

### Task 6: Gin primitives (`cardlang/runtime/gin.py`)

**Files:**
- Create: `cardlang/runtime/gin.py`
- Modify: `cardlang/stdlib/signatures.py` + the runtime registry that binds game-local primitives (mirror `cardlang/runtime/cribbage.py`'s registration exactly — same decorator/table, same ctx-adapter shape)
- Create: `tests/test_gin_primitives.py`

**Interfaces:**
- Produces (DSL-visible):
  - `gin_card_points(c : Card) -> Integer` — A=1, 2–10 pip, J/Q/K=10
  - `gin_valid_meld(cards : Collection<Card>) -> Boolean`
  - `gin_deadwood(p : Player) -> Integer` — optimal partition of `hand[p]`
  - `gin_knock_ok(p : Player, c : Card) -> Boolean` — deadwood(hand[p] − c) ≤ 10
  - `gin_arrange_ok(p : Player, cards : Collection<Card>) -> Boolean` — valid meld AND deadwood(hand[p] − cards) ≤ 10
  - `gin_can_declare(p : Player) -> Boolean` — some subset passes `gin_arrange_ok`
  - `gin_flat_points(p : Player) -> Integer` — sum of card points of `hand[p]`
  - `gin_lay_ok_a/b/c(c : Card) -> Boolean` — c extends `meldA/B/C[knocker]` (knocker read from state)

- [ ] **Step 1: Failing known-value tests** (the Cribbage 29-hand pattern):

```python
def test_card_points() -> None:
    assert points(Card("A", "spades")) == 1
    assert points(Card("7", "hearts")) == 7
    assert points(Card("K", "clubs")) == 10

def test_valid_melds() -> None:
    assert valid_meld([c("7C"), c("7D"), c("7H")])          # set of 3
    assert valid_meld([c("AC"), c("2C"), c("3C")])          # ace-low run
    assert not valid_meld([c("QC"), c("KC"), c("AC")])      # ace never high
    assert not valid_meld([c("7C"), c("7D")])               # too small
    assert not valid_meld([c("7C"), c("8D"), c("9C")])      # mixed-suit run

def test_deadwood_known_hands() -> None:
    # 7♣7♦7♥ + 8♦9♦10♦ + K♠Q♥4♣2♦ -> deadwood K+Q+4+2 = 26
    assert deadwood(hand1) == 26
    # The set-vs-run overlap: 7♠7♥7♦ 8♦9♦ + K♠... —
    # run 7♦8♦9♦ leaves 7♠7♥ (14) vs set leaves 8♦9♦ (17): optimum picks the run... 
    # pin the exact minimal value:
    assert deadwood([c("7S"), c("7H"), c("7D"), c("8D"), c("9D"), c("KS")]) == 24
    # a gin hand -> 0
    assert deadwood(gin_hand) == 0
```

- [ ] **Step 2: RED.** **Step 3: the optimizer** (pure, ≤11 cards — exhaustive recursion over candidate melds is plenty):

```python
def _minimal_deadwood(cards: list[Card]) -> int:
    """Minimal total point value of unmelded cards over every partition of
    `cards` into disjoint valid melds + deadwood. Exhaustive: hands are <= 11
    cards; melds touching the lowest-indexed unused card bound the branching."""
    melds = [m for m in _candidate_melds(cards)]
    order = {id(c): i for i, c in enumerate(cards)}
    best = [sum(_points(c) for c in cards)]

    def go(unused: frozenset[int], acc: int) -> None:
        if acc >= best[0]:
            return
        if not unused:
            best[0] = acc
            return
        first = min(unused)
        # Option 1: `first` is deadwood.
        go(unused - {first}, acc + _points(cards[first]))
        # Option 2: `first` is melded — try every candidate meld containing it.
        for meld_idxs in melds:
            if first in meld_idxs and meld_idxs <= unused:
                go(unused - meld_idxs, acc)

    go(frozenset(range(len(cards))), 0)
    return best[0]
```

with `_candidate_melds` enumerating all rank-sets (3–4 of a rank) and all maximal-run sub-windows (3+ consecutive same suit, ace low) as frozensets of indices. `gin_can_declare` / `gin_arrange_ok` reuse it on `hand − subset`.

- [ ] **Step 4: registration** — mirror `cribbage.py`: ctx-adapters reading `ctx.rs.zones` / state (`knocker`), entries in the game-local signature table so typecheck sees the DSL-visible signatures above. GREEN on known-value tests.

- [ ] **Step 5: Commit** `feat(gin): game-local primitives — points, melds, optimal deadwood`.

---

### Task 7: `gin-rummy.cardlang` + `.md` + playout tests

**Files:**
- Create: `docs/games/gin-rummy.cardlang`, `docs/games/gin-rummy.md` (full prose per the corpus acceptance test: a non-player can play a hand from it)
- Create: `tests/test_playout_gin_rummy.py`
- Modify: the game registry the glob↔registry count test pins (grep `REGISTERED` in `tests/test_typecheck_corpus.py`)

**Interfaces:**
- Consumes: `turns`, `jointly`/`some`, all Task-6 primitives.

- [ ] **Step 1: the game file** — structure (write in full; state/zone names exactly as here so the primitives' ctx-adapters match):

```text
zones: deck, hand[player], newly_drawn[player] (staging), discard_top,
       discard_history, meldA/B/C[player] : PlayerPile, shown_deadwood[player] : PlayerPile
game state: match_score[player], hands_won[player], dealer : Player = 0
hand phase state: knocked/went_gin/no_result : Boolean, knocker : Player? = none,
       arranging_done/layoff_done : Boolean, went_again-free (no again clause),
       first_player : Player = 0, took_upcard : Boolean
phases:
  hand_loop repeat until any player where match_score[player] >= 100 {
    deal: gather all to deck, shuffle, deal 10 to each hand, 1 to discard_top
    upcard ritual: offer non-dealer [take_upcard, pass_upcard];
      if passed -> offer dealer [take_upcard, pass_upcard];
      if both passed -> as non-dealer { draw 1 from deck } and the taker is non-dealer;
      taker discards (chosen 1 from hand+staging to discard flow);
      first_player := the other player
    play: turns t from first_player over all players
          until knocked or (number of cards in deck <= 2) {
      offer to t one of [draw_stock, take_discard]
      offer to t one of [discard_card, knock]      // knock guarded by gin_knock_ok
    }
    if not knocked { no_result handling: score nothing, dealer unchanged, skip to next hand }
    showdown:
      as knocker { repeat until arranging_done { offer [declare_meld, finish_arranging] } }
      as defender { repeat until d_arranging_done { offer [declare_meld_d, finish_d] } }
      if not went_gin { as defender { repeat until layoff_done {
        offer [lay_off_a, lay_off_b, lay_off_c, done_layoff] } } }
      scoring: flat counts of shown_deadwood; knock/gin/undercut arithmetic;
      hands_won, dealer := hand winner
  }
  match end: match_score[p] += 20 * hands_won[p]; winner bonus 100 (200 if
  opponent hands_won is 0 and opponent match_score is 0)
winner: highest match_score
move_type declare_meld { when: gin_can_declare(actor) effect {
  if meldA[actor] is empty { move chosen some cards from hand[actor]
    where jointly gin_arrange_ok(actor, cards) to meldA[actor] }
  else { if meldB[actor] is empty { ...meldB... } else { ...meldC... } } } }
move_type knock(c : Card) { when: gin_knock_ok(actor, c) effect {
  move ... c ... to discard_history
  knocked := true  knocker := actor
  went_gin := (gin_deadwood(actor) is 0) } }
lay_off_a(c : Card) { when: gin_lay_ok_a(c) effect { move c from hand[defender-ish] to meldA[knocker]... } }
```

The "took the discard → must discard a different card" staging flow copies the stress branch's proven shape (`newly_drawn` zone; merge after discard/knock). Write the real file from this skeleton against the checker — every wall it hits is either a game bug or a construct bug; triage each loudly, never work around silently.

- [ ] **Step 2: playout tests** (the Cribbage pattern): 50 seeds — exactly one winner ≥ 100 (plus bonuses), conservation census 52, no-result hands leave scores unchanged, knocked hands end with knocker's shown deadwood flat ≤ 10 (the arrange-guard totality claim, asserted over every seed), undercut/gin bonuses recomputed independently from the trace. Pin one seed's full per-hand score vector as a characterization golden (`PYTHONHASHSEED=0`).

- [ ] **Step 3: GREEN; commit** `feat(gin): corpus game + playout invariants`.

---

### Task 8: OpenSpiel proof module for Gin

**Files:**
- Create: `tests/openspiel_ready/test_gin_rummy.py` (one proof module over the shared harness — copy `test_cribbage.py`'s structure: indistinguishability + legal-action agreement, per-visible-fact soundness matrix, rng non-observability, adapter agreement, perfect recall)

- [ ] **Step 1**: instantiate the harness for gin; run: expect failures only if the constructs leak observations — treat any failure as a construct bug (Task 3/5), not a per-game patch (no per-game observation rules exist).
- [ ] **Step 2**: GREEN; note gin-specific caveats (hidden hands + public melds partition) in the module docstring like the other proofs do.
- [ ] **Step 3: Commit** `test(gin): openspiel_ready proof module`.

---

### Task 9: Go Fish migration (byte-identical)

**Files:**
- Modify: `docs/games/go-fish.cardlang` (+ `.md` twin if it carries DSL — check ```` ``` ```` presence)

- [ ] **Step 1**: capture the pre-migration baseline: 100-seed decision+score sequences via a scripted chooser (the cribbage old-vs-new harness from the `as` PR).
- [ ] **Step 2**: rewrite:

```text
state: - current_player  + went_again : Boolean = false
phase play {
  turns t from 0 over players
        until (deck is empty) or (any player where hand[player] is empty)
        again went_again {
    offer to t one of [ask]
  }
}
move_type ask effect: replace every `current_player := …` with
  went_again := true   (hit, or drew the asked rank)
  went_again := false  (drew a non-matching card)
— written on EVERY path (the go-again contract).
```

- [ ] **Step 3**: diff old-vs-new over 100 seeds — **0 divergences required**; existing `tests/` Go Fish playouts pass unchanged. If rotation diverges, the bug is in `_turns`' direction handling — fix the form, not the game.
- [ ] **Step 4: Commit** `refactor(go-fish): migrate the turn loop onto turns/again — byte-identical`.

---

### Task 10: Docs + audit ledgers + gates

**Files:**
- Modify: `docs/decisions.md` (new "The `turns` form" section — spec-voice promotion; "Joint-predicate selection" under the movement/operation section; fenced examples tagged `cardlang-fragment <label>` with recipes in `tests/test_doc_snippets.py`)
- Delete: the turn-loop-form question (now decisions.md "The `turns` form"); Modify: `docs/open-questions/_index.md`, `docs/open-questions/meld-groups.md` (rewrite in place to the narrowed residual: first-class groups, Canasta forcing), `docs/roadmap.md` (President-bullet correction + residuals: `direction` clause, `random`+jointly, enumeration bound), `docs/library.md` (`turns` beside the round forms), `docs/games/_candidates.md` (drop gin)
- Modify: `docs/appendix.md` — NOT touched (stable reference table; wholesale-replace rule).

- [ ] **Step 1**: write both decisions.md sections + doc-snippet labels/recipes (labels `turns_form`, `jointly_meld`).
- [ ] **Step 2**: sweep every reference to the turn-loop-form question repo-wide (docs AND tests — the `as`-PR lesson) and repoint to the decisions.md title.
- [ ] **Step 3**: finalize both completeness ledgers; run the `surface-totality-audit` skill's checklist against each (misuse probes present per category: omitted-clause-with-absorbing-operand, wrong-typed operand in every predicate context, boundary-token doubling, out-of-scope binder).
- [ ] **Step 4**: gates: `mypy` bare; `PYTHONHASHSEED=0 pytest -q` full; commit `docs: promote turn-loop-form, narrow meld-groups, catalogue turns + jointly`.

---

### Task 11: Review round + PR

- [ ] **Step 1**: run the `cardlang-code-review` skill at ultra effort (the six-angle fan-out; misparse probes on BOTH new grammar surfaces mandatory — `turns` vs a `turns`-named variable, `jointly`/`some` identifier-prefix traps, the `until`/`again` clause-boundary splits).
- [ ] **Step 2**: fix findings (sweep classes, not instances), commit as a review-round commit.
- [ ] **Step 3**: push, `gh pr create` (body: what/pipeline/anchors/ledgers/gates), watch CI + Codex reaction (`+1` on the PR body is the sign-off signal).

## Self-review notes

- Spec coverage: §1→Tasks 1–3, §2→Tasks 4–5, §3→Tasks 6–8, §4→Task 9, §5→Tasks 10–11. President correction → Task 10 roadmap edit.
- Type consistency: `n.Turns` fields identical across Tasks 1/2/3; `Movement.joint` + amount `"some"` across 4/5; primitive names across 6/7.
- Known open integration points (deliberate, resolved at the named precedent): combo-codec wiring (climb encoding), primitive registration (cribbage.py), `env.lookup_state`-style accessor names (neighboring typecheck arms). Each names its precedent file; no invented signatures.
