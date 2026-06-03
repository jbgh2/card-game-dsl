"""Grammar-acceptance test for the formalized Hearts.

Hearts is the first real corpus game brought to the grammar. This proves the
grammar accepts the whole file (the syntactic forcing function) and guards the
two ambiguities that mattered: lambda precedence, and the overall ambiguity
budget. The typed AST / resolver / checker for Hearts's constructs grow after
the syntax is reviewed.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from lark import Lark, Token, Tree

from cardlang.parse import parse_to_tree

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"

TreeNode = Tree[Token]


def _iter_with_parents(tree: TreeNode) -> list[tuple[TreeNode, TreeNode]]:
    """Yield (node, parent) for every Tree node."""
    out: list[tuple[TreeNode, TreeNode]] = []

    def walk(node: TreeNode) -> None:
        for child in node.children:
            if isinstance(child, Tree):
                out.append((child, node))
                walk(child)

    walk(tree)
    return out


def test_hearts_parses_into_one_game_and_five_rules() -> None:
    tree = parse_to_tree(HEARTS.read_text(), str(HEARTS))
    top = tree.children
    assert len(top) == 6
    kinds = [t.data for t in top if isinstance(t, Tree)]
    assert kinds.count("game") == 1
    assert kinds.count("rule_def") == 5


def test_lambda_only_appears_as_a_call_argument() -> None:
    # Regression guard: a lambda's body must extend rightward, so a lambda may
    # only sit under an arg_list — never as an operand of compare/member.
    tree = parse_to_tree(HEARTS.read_text(), str(HEARTS))
    for node, parent in _iter_with_parents(tree):
        if node.data == "lambda":
            assert parent.data == "arg_list", (
                f"lambda parented by {parent.data!r}, expected arg_list "
                "(lambda-precedence regression)"
            )


def test_hearts_ambiguity_budget() -> None:
    # The grammar is not yet LALR-deterministic; the only tolerated residual
    # ambiguities are keyword/identifier overlaps (`none`, `always`), which
    # resolve-mode settles correctly. Lock the budget so new ambiguity is seen.
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    explicit = Lark(
        grammar,
        parser="earley",
        ambiguity="explicit",
        propagate_positions=True,
        maybe_placeholders=True,
    )
    tree = explicit.parse(HEARTS.read_text())
    assert isinstance(tree, Tree)
    ambig = sum(
        1 for node, _ in _iter_with_parents(tree) if node.data == "_ambig"
    )
    assert ambig <= 2, f"ambiguity budget exceeded: {ambig} (expected <= 2)"
