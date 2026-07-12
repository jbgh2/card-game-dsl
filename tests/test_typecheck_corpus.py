"""Corpus regression net for the type checker.

Every executable game in the corpus must type-check clean. This is the guard
against false positives as the checker's precision grows: any new typing rule
that wrongly rejects a real game turns this red. (The `.md` twins are readable
documentation, not the type-check target — some original design docs carry
illustrative syntax that isn't executable.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.pipeline import check_source

GAMES = Path(__file__).parent.parent / "docs" / "games"
CORPUS = sorted(GAMES.glob("*.cardlang"))


def test_corpus_is_present() -> None:
    assert len(CORPUS) == 16  # guard: all executable games present


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_corpus_game_type_checks(path: Path) -> None:
    check_source(path)  # raises DiagnosticError on any resolve/type error
