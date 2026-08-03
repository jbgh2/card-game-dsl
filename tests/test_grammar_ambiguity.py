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
    covered:    every corpus game, each parsed independently and asserted
                at 0 ambiguity sites; a failure names the file and the count.
    sampled:    the `is`/`not`/`number` reserved-word narrowing that produced
                this budget is additionally probed off-corpus in
                tests/test_reserved_words.py (rejection + acceptance pins for
                the prefix-split class, including `sum is not_ready` — a
                latent ambiguity this corpus does not itself exercise, found
                and closed while verifying this fix).
    residual:   ambiguity in productions or identifier shapes no corpus game
                exercises is unmeasured by construction — a corpus pin proves
                the corpus, not the grammar's full input space. The
                identifier-split class the `is`/`not`/`number` fix closed is
                no longer part of that residual: every keyword in the grammar
                now carries whole-word anchoring, pinned over Lark's terminal
                table by tests/test_keyword_anchoring.py, so a keyword cannot
                match as a prefix of a longer word whether or not a corpus
                game happens to spell one.
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
    # reintroducing ambiguity anywhere in the corpus, not only Hearts.
    tree = _PARSER.parse(path.read_text())
    assert isinstance(tree, Tree)
    ambig = _count_ambig(tree)
    assert ambig == 0, f"grammar ambiguity in {path.name}: {ambig} site(s)"


def test_corpus_glob_is_nonempty() -> None:
    # A silently-empty glob would make every parametrized case above vacuous
    # — pytest collects zero tests and the suite stays green. Pin the corpus
    # size independently so a broken glob path fails loud instead.
    # Corpus SIZE is owned by test_optional_pyspiel.py's glob<->registry
    # equality; this pin only has to catch the glob resolving to nothing.
    assert GAMES, f"the corpus glob matched nothing under {GAMES_DIR}"
