"""Lexical binder scoping in the resolve pass (`cardlang/resolve.py`).

Collected into one flat game-wide `locals` set, binders would let a stray
`card` anywhere in the file resolve as `local` and fail only at runtime
with a KeyError (wrong failure channel), and a name bound by a `let` in one
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
            statement-tuple sites the sequential `let` fold applies to.
            One thing sits deliberately outside, and it is not a gap:
            one-level shadowing of the implicit binders is legal — the spec
            allows an inner query's `card` inside an outer one
            (decisions.md "The expression register") — so there is no
            shadowing guard for a cell to reach.
registry:   `resolve._introduced_binders` (which kinds bind which names) and
            `resolve._BINDER_SCOPE_FIELDS` (which sub-fields see them);
            tuple sites from the `Stmt`-sequence fields of the AST
            (Phase.items, IfStmt.then/else, RepeatUntil.body,
            BeforeEach/AfterEach.body, MoveTypeDef.effect, ProduceArm.body)
does not prove:  that the sequential `let` fold is exercised at
            ProduceArm.body. That site reaches the same single tuple arm of
            `_rewrite_value` as every site this module probes, and Schnapsen's
            `play produces:` arms bind `game_pts`/`opp` and read them in later
            arm statements — one shared code path and one live corpus witness,
            neither of them a cell here.
"""

from __future__ import annotations

import dataclasses

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.resolve import _BINDER_SCOPE_FIELDS, resolve


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
    # (decisions.md "The expression register") — no guard.
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
    # a let-bound target could never work, and without this guard it would
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


# The three binding node kinds `_rewrite` scopes in its own arms rather than
# through the registry. Each is here for a stated reason, not because it was
# missed: a `let`'s two names scope in opposite directions (its index inward to
# its own value, its name forward to later statements), a `ProduceArm`'s binders
# scope to the arm's body through the outcome machinery, and `_rewrite` returns
# early for a `TypeDef` and scopes its derived fields itself.
_SCOPED_BY_HAND = frozenset({"LetStmt", "ProduceArm", "TypeDef"})


def test_every_binding_node_kind_scopes_its_binder() -> None:
    """A binding node kind reaches `_rewrite` with a row in
    `_BINDER_SCOPE_FIELDS`, or it is one of the three that arm scopes by hand.

    This is the completeness half its sibling below disclaims, and it is worth
    a pin because the failure is SILENT IN BOTH DIRECTIONS. `_rewrite` reads
    this registry with `.get(type(node))`, so a missing row is not an error: the
    binder simply never enters `cats.locals`. Measured, on a `for each` binder
    with its row removed — a body of `tally[0] := tally[0] + seat`:

      row present, no state variable named `seat`  -> refused, `Player` in `+`
      row present, a state variable named `seat`   -> refused (the binder shadows)
      row MISSING,  no state variable named `seat` -> refused, unresolved name
      row MISSING,  a state variable named `seat`  -> ACCEPTED, and the binder
                                                      silently reads the state

    The last row is the one that matters: a program that should refuse instead
    runs, and reads a different value than the sentence says.

    The kind axis is the same scrape `tests/test_family_libraries.py` builds its
    introducer axis from — one derivation, two consumers, rather than a second
    copy of the match-arm walk.

    red under: delete the `n.SubsetQuery` row from `_BINDER_SCOPE_FIELDS`."""
    from tests.test_family_libraries import _binding_node_kinds

    covered = {kind.__name__ for kind in _BINDER_SCOPE_FIELDS} | _SCOPED_BY_HAND
    unscoped = sorted(_binding_node_kinds() - covered)
    assert not unscoped, (
        f"{unscoped} bind a name but have no `_BINDER_SCOPE_FIELDS` row and are "
        f"not scoped by hand in `_rewrite` — the binder will not enter scope, "
        f"and where a declaration shares its spelling the reference silently "
        f"resolves to that declaration instead"
    )
    assert _SCOPED_BY_HAND <= _binding_node_kinds(), (
        "a kind listed as hand-scoped no longer binds anything — drop it"
    )


def test_every_binder_scope_field_is_a_real_field_of_its_node() -> None:
    """`_BINDER_SCOPE_FIELDS` names its scope fields as STRINGS, so `mypy` sees
    nothing when one is renamed — the row goes on pointing at a field that no
    longer exists and the binder silently stops being scoped anywhere.

    That is not hypothetical: renaming `CardQuery.pred` to `.where` left this
    registry behind, and the first thing to notice was a corpus game failing to
    resolve `player` inside a query. It was caught only because a game happened
    to exercise it.

    What this pin does NOT cover, deliberately: a field that SHOULD be scoped
    and has no row. Whether a new field sees the binder is a judgment about the
    construct, not something derivable from the dataclass.

    red under: change any row's field name, e.g. `n.CardQuery: ("pred",)`.
    """
    for node, fields in _BINDER_SCOPE_FIELDS.items():
        actual = {f.name for f in dataclasses.fields(node)}
        missing = sorted(set(fields) - actual)
        assert not missing, (
            f"_BINDER_SCOPE_FIELDS[{node.__name__}] names {missing}, which "
            f"{node.__name__} does not have — the binder is scoped to nothing there"
        )
