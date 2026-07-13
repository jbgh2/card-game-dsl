"""Corpus-wide Earley ambiguity budget: the grammar must parse every corpus
game to a single derivation, never a latent `_ambig` node the default parser
happens to disambiguate for us.

Completeness ledger (docs/decisions.md "Surface totality" /
"Closed-domain completeness"):

    property:   the grammar is unambiguous over the corpus — parsing with
                ``ambiguity="explicit"`` yields 0 ``_ambig`` nodes per game.
    domain:     every file in docs/games/*.cardlang.
    registry:   the glob itself — ``sorted(Path("docs/games").glob("*.cardlang"))``,
                so a new corpus game is covered automatically, with no list to
                keep in sync (the same pattern as the corpus-count pin
                described in kernel-migration.md).
    covered:    all 18 corpus games, each parsed independently and asserted
                at 0 ambiguity sites; a failure names the file and the count.
    sampled:    the `is`/`not`/`number` reserved-word narrowing that produced
                this budget is additionally probed off-corpus in
                tests/test_reserved_words.py (rejection + acceptance pins for
                the prefix-split class, including `sum is not_ready` — a
                latent ambiguity this corpus does not itself exercise, found
                and closed while verifying this fix).
    residual:   ambiguity in productions or identifier shapes no corpus game
                exercises is unmeasured by construction — a corpus pin proves
                the corpus, not the grammar's full input space. In
                particular, other inline keyword literals in the expression
                grammar (`where`, `of`, `over`, `in`, …) are not swept for
                the same identifier-split class the `is`/`not`/`number` fix
                closed; nothing in the corpus currently exercises an
                identifier shaped to trigger them (spot-probed by hand during
                the investigation behind this test, not walled or pinned).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest
from lark import Lark, Token, Tree

TreeNode = Tree[Token]

GAMES_DIR = Path(__file__).parent.parent / "docs" / "games"
GAMES = sorted(GAMES_DIR.glob("*.cardlang"))


def _count_ambig(tree: TreeNode) -> int:
    n = 0
    stack: list[TreeNode] = [tree]
    while stack:
        node = stack.pop()
        if node.data == "_ambig":
            n += 1
        for child in node.children:
            if isinstance(child, Tree):
                stack.append(child)
    return n


def _explicit_parser() -> Lark:
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    return Lark(
        grammar,
        parser="earley",
        ambiguity="explicit",
        propagate_positions=True,
        maybe_placeholders=True,
    )


# Built once and shared across the parametrized cases below: grammar
# compilation is pure and re-running it per game buys nothing.
_PARSER = _explicit_parser()


@pytest.mark.parametrize("path", GAMES, ids=[g.name for g in GAMES])
def test_corpus_game_parses_with_zero_ambiguity(path: Path) -> None:
    # The grammar is still Earley (LALR-tightening is later), but it is
    # deterministic on the corpus today; this guards against a change
    # reintroducing ambiguity anywhere in the 18 games, not only Hearts.
    tree = _PARSER.parse(path.read_text())
    assert isinstance(tree, Tree)
    ambig = _count_ambig(tree)
    assert ambig == 0, f"grammar ambiguity in {path.name}: {ambig} site(s)"


def test_corpus_glob_is_nonempty() -> None:
    # A silently-empty glob would make every parametrized case above vacuous
    # — pytest collects zero tests and the suite stays green. Pin the corpus
    # size independently so a broken glob path fails loud instead.
    assert len(GAMES) >= 18, f"expected at least 18 corpus games, found {len(GAMES)}"
