"""Grammar-acceptance test for the formalized Hearts.

Hearts is the first real corpus game brought to the grammar. This proves the
grammar accepts the whole file (the syntactic forcing function) into the
expected top-level shape. The typed AST / resolver / checker for Hearts's
constructs grow after the syntax is reviewed.

The corpus-wide ambiguity budget (Hearts included) lives in
tests/test_grammar_ambiguity.py, parametrized over every docs/games/*.cardlang
file rather than pinned to Hearts alone.
"""

from __future__ import annotations

from pathlib import Path

from lark import Tree

from cardlang.parse import parse_to_tree

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def test_hearts_parses_into_one_game_and_two_rules() -> None:
    # The Hearts-specific rules only: MustFollowSuit and
    # NoLeadingSuitUntilBroken live in the standard library, not the file.
    tree = parse_to_tree(HEARTS.read_text(), str(HEARTS))
    top = tree.children
    # game + 2 rules. `PassExactlyThreeCards` was a third until its
    # `demands: actions where` form was guarded as unenforceable
    # (tests/test_rule_surface_reachability.py).
    assert len(top) == 3
    kinds = [t.data for t in top if isinstance(t, Tree)]
    assert kinds.count("game") == 1
    assert kinds.count("rule_def") == 2
