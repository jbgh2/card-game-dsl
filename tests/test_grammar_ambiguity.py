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


def _trick_order_accept_sources() -> list[tuple[str, str]]:
    """Every ACCEPTED source of the `trick_order { }` grid — its boundary
    sentences above all (a row expression running up against the next row's
    key: an `else` then a key, an `elif` chain then a key, a call then a key,
    a suit literal then a key).

    Derived from the grid's own cells rather than re-spelled here, so a
    boundary sentence added there is budgeted here without an edit. The corpus
    pin above cannot stand in for this: the corpus holds ONE shape of the block
    (Doppelkopf's), while the four `trick_order` alternatives all share the
    `_TRICK_ORDER_KW "{"` prefix — which is exactly where a latent `_ambig`
    would sit."""
    from tests.test_trick_order import _grammar_cells

    return [(c.id, c.source) for c in _grammar_cells() if not c.needles]


@pytest.mark.parametrize(
    ("cell_id", "source"),
    _trick_order_accept_sources(),
    ids=[i for i, _ in _trick_order_accept_sources()],
)
def test_trick_order_accepts_with_zero_ambiguity(cell_id: str, source: str) -> None:
    tree = _PARSER.parse(source)
    assert isinstance(tree, Tree)
    ambig = _count_ambig(tree)
    assert ambig == 0, f"grammar ambiguity in {cell_id}: {ambig} site(s)"


def test_the_trick_order_accept_set_is_nonempty() -> None:
    """The sibling of the corpus-glob pin below: a grid whose accept cells all
    grew needles would make the budget above vacuous — zero cases collected,
    suite green."""
    assert len(_trick_order_accept_sources()) >= 8


def test_corpus_glob_is_nonempty() -> None:
    # A silently-empty glob would make every parametrized case above vacuous
    # — pytest collects zero tests and the suite stays green. Pin the corpus
    # size independently so a broken glob path fails loud instead.
    # Corpus SIZE is owned by test_optional_pyspiel.py's glob<->registry
    # equality; this pin only has to catch the glob resolving to nothing.
    assert GAMES, f"the corpus glob matched nothing under {GAMES_DIR}"


# --- the collection spelling's own sentences (issue #472) -------------------
#
# The corpus pin above sees only what the corpus writes, and one game writes
# the collection spelling in one shape. The forms below are the OFF-CORPUS
# sentences the entry's two type slots admit — the spelling in each slot, and
# the boundary tokens a closing `>` can sit against, `>=` fusion included. `<`
# and `>` are the comparison terminals, so an entry slot whose type is followed
# by anything at all is where a second derivation would sit.


def _collection_ambiguity_sources() -> list[tuple[str, str]]:
    """Derived from the entry grid's own adjacency cells, so a boundary
    sentence added there is budgeted here without an edit. The reject cells are
    excluded: a sentence with no derivation cannot have two."""
    from tests.test_primitives_block import _COLLECTION_ADJACENCY, _game

    cells = [
        (cell, _game(block=None, body="").replace("  zones {", clause + "  zones {"))
        for cell, (clause, needle) in sorted(_COLLECTION_ADJACENCY.items())
        if clause and not needle
    ]
    cells += [
        (
            "parameter-slot",
            _game(block="gin_valid_meld(cards : Collection<Card>) : Boolean", body=""),
        ),
        (
            "return-slot",
            _game(block="pinochle_meld_value(p : Player) : Collection<Card>", body=""),
        ),
    ]
    return cells


@pytest.mark.parametrize(
    ("cell_id", "source"),
    _collection_ambiguity_sources(),
    ids=[i for i, _ in _collection_ambiguity_sources()],
)
def test_the_collection_spelling_parses_with_zero_ambiguity(
    cell_id: str, source: str
) -> None:
    tree = _PARSER.parse(source)
    assert isinstance(tree, Tree)
    ambig = _count_ambig(tree)
    assert ambig == 0, f"grammar ambiguity in {cell_id}: {ambig} site(s)"


def test_the_collection_ambiguity_set_is_nonempty() -> None:
    """The sibling of the corpus-glob pin: an adjacency table whose accept
    cells all grew a needle would collect nothing and leave the budget above
    vacuous."""
    assert len(_collection_ambiguity_sources()) >= 5
