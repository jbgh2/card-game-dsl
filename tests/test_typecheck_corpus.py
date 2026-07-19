"""Corpus regression net for the type checker.

Every executable game in the corpus must type-check clean. This is the guard
against false positives as the checker's precision grows: any new typing rule
that wrongly rejects a real game turns this red.

That includes the `.md` twins. Exempting them, on the grounds that "some
original design docs carry illustrative syntax that isn't executable", is
exactly what lets one rot: `hearts.md` carried a retired quantifier spelling
(`any cumulative_score >= 100`, predating the English register) and a retired
`repeat until all hands empty`, so its DSL block did not parse and nothing said
so. maintaining.md is unambiguous that this is a bug and not a historical
artifact — "a game file that uses obsolete syntax is a bug" — and the corpus is
the living spec, so the doctrine needs a gate rather than a carve-out. The
premise is also simply false: every
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
    # The registry is DERIVED from this same docs/games/ directory
    # (cardlang/openspiel/registry.py `_derive_games`), so "every file is
    # registered" holds by construction — the real guarantees moved INTO the
    # derivation, which raises rather than build a silently-broken map. Here we
    # only confirm the production call maps the real corpus without raising and
    # in the expected shape; the two raise conditions are pinned below with
    # controlled directories. The registry imports nothing third-party, so this
    # core test never needs pyspiel.
    from cardlang.openspiel.registry import _GAMES_DIR, _derive_games

    games = _derive_games(_GAMES_DIR)
    assert sorted(games.values()) == sorted(p.name for p in CORPUS)
    assert all(k.startswith("cardlang_") for k in games)


def test_derive_games_raises_on_an_empty_directory(tmp_path: Path) -> None:
    # The packaging failure made loud: an empty (or missing) corpus directory
    # would derive an empty registry and register no games silently.
    from cardlang.openspiel.registry import _derive_games

    with pytest.raises(RuntimeError, match="no .cardlang games found"):
        _derive_games(tmp_path)


def test_derive_games_raises_on_a_short_name_collision(tmp_path: Path) -> None:
    # Two stems differing only by the character the short-name rule folds away
    # (`-` vs `_`) map to one OpenSpiel name; a dict would keep the last
    # silently, dropping a game.
    from cardlang.openspiel.registry import _derive_games

    (tmp_path / "go-fish.cardlang").write_text("")
    (tmp_path / "go_fish.cardlang").write_text("")
    with pytest.raises(RuntimeError, match="same OpenSpiel short name"):
        _derive_games(tmp_path)


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
