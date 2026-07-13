"""Corpus regression net for the type checker.

Every executable game in the corpus must type-check clean. This is the guard
against false positives as the checker's precision grows: any new typing rule
that wrongly rejects a real game turns this red.

That now includes the `.md` twins. They used to be exempt, on the stated grounds
that "some original design docs carry illustrative syntax that isn't executable"
— and the exemption is exactly what let one rot: `hearts.md` carried a retired
quantifier spelling (`any cumulative_score >= 100`, from before the English
register landed) and a retired `repeat until all hands empty`, so its DSL block
had not parsed for some time and nothing said so. maintaining.md is unambiguous
that this is a bug and not a historical artifact — "a game file that uses
obsolete syntax is a bug" — and the corpus is the living spec, so the doctrine
needed a gate rather than a carve-out. The premise is also simply false now: every
one of the 16 `.md` twins that carries a fenced block is executable. The two that
carry none (doppelkopf, president) are prose-only companions and are skipped, not
failed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.pipeline import check_source

GAMES = Path(__file__).parent.parent / "docs" / "games"
CORPUS = sorted(GAMES.glob("*.cardlang"))

# The `.md` twins that actually carry a DSL block. A prose-only companion has
# nothing to check; a fenced one is a game file and is held to the same bar.
MD_TWINS = sorted(
    p for p in GAMES.glob("*.md") if p.stem != "_candidates" and "```" in p.read_text()
)


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


@pytest.mark.parametrize("path", MD_TWINS, ids=lambda p: p.stem)
def test_md_twin_checks(path: Path) -> None:
    """The `.md` game files are the living spec (CLAUDE.md), so their DSL blocks are
    held to the same bar as the `.cardlang`. Nothing checked them before, and
    `hearts.md` had quietly rotted to two retired spellings — the exact failure
    mode maintaining.md calls a bug."""
    check_source(path)
