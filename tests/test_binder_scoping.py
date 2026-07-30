"""Lexical binder scoping in the resolve pass (`cardlang/resolve.py`).

Collected into one flat game-wide `locals` set, binders would let a stray
`card` anywhere in the file resolve as `local` and fail only at runtime
with a KeyError (wrong failure currency), and a name bound by a `let` in one
phase would resolve everywhere. `_rewrite` scopes every binder to exactly the
sub-fields its construct binds it in (`_BINDER_SCOPE_FIELDS`, driven by the
`_introduced_binders` registry), and `let` names fold sequentially through
their statement tuple — matching the runtime, where `run_body`/`run_stmts`
thread `ctx.locals` forward through a body (including into later nested
sub-phases) but never across sibling phases.

property:   every name a binder introduces resolves only within the binder's
            scope — and outside it, the same bare name is a resolve-time
            diagnostic (with a hint for the implicit `card`/`player`), never
            a runtime KeyError
domain:     binder-introducing node kinds x their scope fields, plus the
            statement-tuple sites the sequential `let` fold applies to
registry:   `resolve._introduced_binders` (which kinds bind which names) and
            `resolve._BINDER_SCOPE_FIELDS` (which sub-fields see them);
            tuple sites from the `Stmt`-sequence fields of the AST
            (Phase.items, IfStmt.then/else, RepeatUntil.body,
            BeforeEach/AfterEach.body, MoveTypeDef.effect, ProduceArm.body)
covered:    - Quantifier: binder in `body` only (out-of-scope-after test)
            - Comprehension: binder in `filter`+`body`, NOT `default`,
              NOT `source` (accept + reject tests; mirrors typecheck.py
              `_check_expr`'s scoping of the same node)
            - CardQuery: `card` in `pred` only, NOT `source` (reject test);
              nested queries shadow legally (accept test)
            - PlayerQuery: `player` in `pred` only (stray-`player` reject)
            - Movement / EpistemicOp: `card` in `filter` only (accept tests)
            - ForEach / EachSimultaneous: binder/role in `body` (accept)
            - LetStmt name: visible to LATER statements of the same tuple
              and to later nested sub-phases (accept), NOT before its let,
              NOT in a sibling phase (reject tests) — the same visibility
              the runtime gives it (`driver.run_body` threads ctx forward
              through one items tuple; `run_phase` returns nothing, so
              locals never cross sibling phases)
            - LetStmt index: visible in the let's own `value` only (reject)
            - rotate of a let-bound local: rejected ("rotate of unknown
              variable") — the runtime `_rotate` reads persistent state
              (`ctx.rs`), never `ctx.locals`, so a local target could only
              ever KeyError at playout; previously the flat classifier let
              it through
            - BeforeEach: a hook `let` is visible later in the same hook
              (accept) and NOT in the phase items (reject) — matching the
              runtime, where `run_stmts(before.body, ctx)` threads locals
              within the hook and discards them before the body runs
            - MoveTypeDef: an effect `let` is visible later in the effect
              (accept) and NOT in the guard (reject) — guard and effect are
              separate fields; only the effect tuple folds
covered-by-design:
            - a `let` in a phase body IS visible inside a later nested
              sub-phase of the same body: not a leak — the runtime threads
              the updated ctx into `run_phase` for nested items, so the
              resolve scope matches the execution scope exactly (accept
              test above pins the behavior)
            - one-level shadowing of the implicit binders stays legal (the
              spec allows an inner query's `card` inside an outer one —
              decisions.md "The expression register"); no shadowing wall
sampled:    the sequential fold at ProduceArm.body goes through the same
            single tuple arm of `_rewrite_value` as every site above and is
            corpus-witnessed (Schnapsen's `play produces:` arms bind
            `game_pts`/`opp` and read them in later arm statements, green in
            the full suite) — one code path, one live witness
residual:   none
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.resolve import resolve


def _game(body: str) -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ hand[player] : Hand<player>  pile : TrickPile  captured[player] : PlayerPile<player> }}
  state {{ score[player] : Integer = 0 }}
{body}
  winner: highest score
}}
"""


def _rejects(body: str, *needles: str) -> None:
    with pytest.raises(DiagnosticError) as e:
        resolve(parse_text(_game(body), "t.cardlang"))
    text = str(e.value)
    for needle in needles:
        assert needle in text, f"missing {needle!r} in: {text}"


def _accepts(body: str) -> None:
    resolve(parse_text(_game(body), "t.cardlang"))  # no diagnostics


# --- stray implicit binders are resolve-time diagnostics, with hints ---


def test_stray_card_in_a_let_is_unresolved_with_hint() -> None:
    _rejects(
        """
  phase p {
    let x = card
  }
""",
        "unresolved name 'card'",
        "(`card` is bound only inside a card query, an aggregation, or a `where` filter)",
    )


def test_stray_card_in_a_phase_qualifier_is_unresolved_with_hint() -> None:
    _rejects(
        """
  phase p repeat until card is none {
    let x = 0
  }
""",
        "unresolved name 'card'",
        "(`card` is bound only inside a card query, an aggregation, or a `where` filter)",
    )


def test_stray_player_is_unresolved_with_hint() -> None:
    _rejects(
        """
  phase p {
    let x = player
  }
""",
        "unresolved name 'player'",
        "(`player` is bound only inside a player query or quantifier)",
    )


def test_quantifier_binder_is_not_visible_after_its_body() -> None:
    _rejects(
        """
  phase p {
    let x = (any player where score[player] > 5)
    score[0] := score[player]
  }
""",
        "unresolved name 'player'",
    )


# --- `let` is sequentially scoped: later statements, same tuple ---


def test_let_referenced_before_its_let_is_unresolved() -> None:
    _rejects(
        """
  phase p {
    let y = x + 1
    let x = 5
  }
""",
        "unresolved name 'x'",
    )


def test_let_is_not_visible_in_a_sibling_phase() -> None:
    _rejects(
        """
  phase p1 {
    let x = 5
  }
  phase p2 {
    let y = x
  }
""",
        "unresolved name 'x'",
    )


def test_let_is_visible_to_later_statements_and_nested_scopes() -> None:
    # The Hearts scoring shape: a let read by a later let and a later loop
    # body — the sequential fold carries the binding down the rest of the
    # phase's items, including into compound statements.
    _accepts(
        """
  phase p {
    let base[p] = sum of rank_value(card) over cards in captured[p]
    let hand_score[p] = if (any player where base[player] is 26) then 0 else base[p]
    for each player p:
      score[p] += hand_score[p]
  }
"""
    )


def test_let_is_visible_in_a_later_nested_phase_of_the_same_body() -> None:
    # Covered-by-design, not a leak: the runtime threads the post-let ctx
    # into a later nested sub-phase (`driver.run_body`), so resolve matches.
    _accepts(
        """
  phase outer {
    let x = 5
    phase inner {
      score[0] := x
    }
  }
"""
    )


def test_let_is_not_visible_in_an_earlier_nested_phase() -> None:
    _rejects(
        """
  phase outer {
    phase inner {
      score[0] := x
    }
    let x = 5
  }
""",
        "unresolved name 'x'",
    )


def test_let_scopes_through_repeat_and_if_bodies() -> None:
    _accepts(
        """
  phase p {
    repeat until score[0] > 10 {
      let bonus = 2
      if score[0] > 5 {
        score[0] += bonus
      }
    }
  }
"""
    )


def test_let_index_binder_scopes_to_its_own_value_only() -> None:
    # `let base[p] = …` binds `p` per key inside the value expression; it is
    # gone afterward (runtime `_let` evaluates value per key and discards).
    _rejects(
        """
  phase p {
    let base[p] = score[p]
    let z = p
  }
""",
        "unresolved name 'p'",
    )


# --- query/aggregation sub-field scoping ---


def test_comprehension_default_is_outside_the_element_scope() -> None:
    # The empty-set default is evaluated when there ARE no cards — `card`
    # must not resolve there (mirrors typecheck.py `_check_expr`).
    _rejects(
        """
  phase p {
    let x = highest rank_value(card) over cards in pile or rank_value(card)
  }
""",
        "unresolved name 'card'",
    )


def test_comprehension_filter_and_body_bind_card() -> None:
    _accepts(
        """
  phase p {
    let x = highest rank_value(card) over cards in pile where card.suit is hearts or 0
  }
"""
    )


def test_card_query_source_is_outside_the_card_scope() -> None:
    _rejects(
        """
  phase p {
    let x = number of cards in captured[card] where true
  }
""",
        "unresolved name 'card'",
    )


def test_nested_card_queries_shadow_legally() -> None:
    # One-level shadowing of the implicit binder is deliberate spec surface
    # (decisions.md "The expression register") — no wall.
    _accepts(
        """
  phase p {
    let z = number of cards in pile where (any card in captured[actor] where card.rank is card.rank)
  }
"""
    )


def test_movement_filter_binds_card() -> None:
    _accepts(
        """
  phase p {
    move all cards from hand[actor] where card.suit is hearts to pile
  }
"""
    )


def test_reveal_filter_binds_card() -> None:
    _accepts(
        """
  phase p {
    reveal one card from pile where card.suit is hearts
  }
"""
    )


def test_each_simultaneous_binds_its_role_in_the_body() -> None:
    _accepts(
        """
  phase p {
    each player simultaneously:
      move chosen 3 cards from hand[player] to pile
  }
"""
    )


# --- lifecycle hooks and move-type effects: same fold, separate scopes ---


def test_let_in_before_each_is_visible_later_in_the_hook() -> None:
    _accepts(
        """
  phase p repeat until score[0] > 10 {
    before_each {
      let bump = 2
      score[0] += bump
    }
  }
"""
    )


def test_let_in_before_each_is_not_visible_in_the_phase_body() -> None:
    # The runtime runs the hook body and discards its locals before the phase
    # items execute (`driver.run_phase` -> `run_stmts(before.body, ctx)`).
    _rejects(
        """
  phase p repeat until score[0] > 10 {
    before_each {
      let bump = 2
    }
    score[0] += bump
  }
""",
        "unresolved name 'bump'",
    )


def _move_type_game(move_type: str) -> str:
    # `move_type` is a top-level item, outside the `game { }` block.
    return _game("  phase p {\n    let x = 1\n  }\n") + move_type


def test_let_in_a_move_effect_is_visible_later_in_the_effect() -> None:
    resolve(
        parse_text(
            _move_type_game(
                """
move_type m {
  effect {
    let pay = 3
    score[actor] += pay
  }
}
"""
            ),
            "t.cardlang",
        )
    )


def test_let_in_a_move_effect_is_not_visible_in_the_guard() -> None:
    # The guard evaluates BEFORE the effect runs; an effect-bound name there
    # could only ever KeyError at playout.
    with pytest.raises(DiagnosticError) as e:
        resolve(
            parse_text(
                _move_type_game(
                    """
move_type m {
  when: pay is 3
  effect {
    let pay = 3
    score[actor] += pay
  }
}
"""
                ),
                "t.cardlang",
            )
        )
    assert "unresolved name 'pay'" in str(e.value)


# --- rotate targets persistent state, never a lexical local ---


def test_rotate_of_a_let_bound_local_is_rejected() -> None:
    # The runtime's `_rotate` reads/writes `ctx.rs` (persistent state) only;
    # a let-bound target could never work, and without this wall it would
    # slip through the classifier to fail at playout.
    _rejects(
        """
  phase p {
    let x = 5
    rotate x through [left, right]
  }
""",
        "cannot rotate 'x': it is a binder",
    )
