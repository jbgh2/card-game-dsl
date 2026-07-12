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
    # Two-sided pin: every game file is registered with the OpenSpiel
    # adapter and every registration has a file. Derived, not a literal
    # count — two branches each adding a game used to auto-merge the same
    # numeric bump and leave main red with no conflict marker. The registry
    # module is pure data, so this core test never needs pyspiel.
    from cardlang.openspiel.registry import GAMES as REGISTERED

    assert sorted(p.name for p in CORPUS) == sorted(REGISTERED.values())


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_corpus_game_type_checks(path: Path) -> None:
    check_source(path)  # raises DiagnosticError on any resolve/type error
