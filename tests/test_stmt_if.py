"""Statement-level `if` (braced blocks) — introduced by Getaway.

Getaway needs conditional *statements* (`if hand[p] is empty { ... }`), distinct
from the existing `if … then … else …` *expression*. The body is a braced block
like `repeat_until` (not a colon-single body), which keeps it unambiguous against
`for_each`/`each_simultaneous` colon bodies and the `if_expr` then/else form.
"""

from __future__ import annotations

from importlib import resources

from lark import Lark, Tree

from cardlang.ast import nodes as n
from cardlang.parse import parse_text


def _phase_stmts(game: n.Game) -> list[n.Stmt]:
    phase = game.phases[0]
    return [it for it in phase.items if not isinstance(it, n.Phase)]  # type: ignore[misc]


def test_if_statement_with_else() -> None:
    text = """
    game T {
      players: 4
      max_length: 1000
      cards: standard52
      phase p {
        if hand is empty { x := 1 } else { x := 2 }
      }
    }
    """
    game = parse_text(text, "t.dsl")
    stmts = _phase_stmts(game)
    assert len(stmts) == 1
    stmt = stmts[0]
    assert isinstance(stmt, n.IfStmt)
    assert isinstance(stmt.cond, n.IsCheck)
    assert len(stmt.then_body) == 1
    assert isinstance(stmt.then_body[0], n.AssignStmt)
    assert stmt.else_body is not None
    assert len(stmt.else_body) == 1
    assert isinstance(stmt.else_body[0], n.AssignStmt)


def test_if_statement_without_else() -> None:
    text = """
    game T {
      players: 4
      max_length: 1000
      cards: standard52
      phase p {
        if hand is empty { x := 1  y := 2 }
      }
    }
    """
    game = parse_text(text, "t.dsl")
    stmt = _phase_stmts(game)[0]
    assert isinstance(stmt, n.IfStmt)
    assert len(stmt.then_body) == 2
    assert stmt.else_body is None


def test_if_statement_parses_with_zero_ambiguity() -> None:
    # Statement-`if` is the flagged ambiguity risk; verify it in isolation.
    text = """
    game T {
      players: 4
      max_length: 1000
      cards: standard52
      phase p {
        for each player q: if hand is empty { x := 1 } else { x := 2 }
        repeat until x is empty {
          if y is empty { z := 1 }
        }
      }
    }
    """
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    explicit = Lark(
        grammar,
        parser="earley",
        ambiguity="explicit",
        propagate_positions=True,
        maybe_placeholders=True,
    )
    tree = explicit.parse(text)
    assert isinstance(tree, Tree)
    ambig = sum(1 for node in tree.iter_subtrees() if node.data == "_ambig")
    assert ambig == 0, f"statement-if introduced {ambig} ambiguity site(s)"
