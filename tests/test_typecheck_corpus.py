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
premise is also simply false: every `.md` twin that carries a fenced block is
executable. Twins carrying none are prose-only companions and are skipped, not
failed — which is a hole if it grows silently, so the skipped set is pinned by
name in `test_the_prose_only_twins_are_the_pinned_set` rather than counted in
this sentence.
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

# The twins this gate does NOT cover, by name. A count in prose hid the fact
# that this set had grown from two to six; pinned, a seventh has to be added
# here deliberately, and a twin that gains a block has to be removed.
PROSE_ONLY_TWINS: frozenset[str] = frozenset(
    {"belote", "canasta", "doppelkopf", "five-hundred", "gin-rummy", "president"}
)


def test_the_prose_only_twins_are_the_pinned_set() -> None:
    """The gate's blind spot, named rather than counted."""
    uncovered = {
        p.stem
        for p in GAMES.glob("*.md")
        if p.stem != "_candidates" and "```" not in p.read_text()
    }
    assert uncovered == PROSE_ONLY_TWINS


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
    from cardlang.runtime.errors import InstallationError

    # `InstallationError`, not `RuntimeError`: the type is the claim about WHO
    # must act (the person who installed or checked this out), and it is a
    # sibling of `GameDescriptionError` so a harness reporting illegal games
    # cannot swallow a missing corpus.
    with pytest.raises(InstallationError, match="no .cardlang games found"):
        _derive_games(tmp_path)


def test_derive_games_raises_on_a_short_name_collision(tmp_path: Path) -> None:
    # Two stems differing only by the character the short-name rule folds away
    # (`-` vs `_`) map to one OpenSpiel name; a dict would keep the last
    # silently, dropping a game.
    from cardlang.openspiel.registry import _derive_games
    from cardlang.runtime.errors import InstallationError

    (tmp_path / "go-fish.cardlang").write_text("")
    (tmp_path / "go_fish.cardlang").write_text("")
    with pytest.raises(InstallationError, match="same OpenSpiel short name"):
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


def _block_facts(game: object) -> dict[str, object] | None:
    """A `primitives { }` block as comparable facts: per entry, the typed
    parameter list, the return spelling, and the reads (name, binder). None
    for a legacy game, so regime drift between twins is itself a diff."""
    primitives = getattr(game, "primitives")
    if primitives is None:
        return None
    return {
        d.name: (
            tuple((p.name, p.type_name) for p in d.params),
            d.return_type,
            tuple(sorted((r.name, r.binder or "") for r in d.reads)),
        )
        for d in primitives.decls
    }


_PAIRED_TWINS = sorted(p for p in MD_TWINS if (GAMES / f"{p.stem}.cardlang").exists())


def test_every_fenced_twin_is_paired() -> None:
    """The pairing glob's own control: a fenced twin with no `.cardlang` would
    silently leave the block-agreement pin's domain."""
    assert [p.stem for p in MD_TWINS if p not in _PAIRED_TWINS] == []


@pytest.mark.parametrize("md", _PAIRED_TWINS, ids=lambda p: p.stem)
def test_twin_block_agrees_with_the_cardlang(md: Path) -> None:
    """The two fences differ freely as TEXT; the `primitives { }` block is
    spec, and operating rule 2 holds the pair in lockstep — a read dropped
    from a twin's entry, an extra twin-only entry, or param drift checks
    clean on both sides and lands here.

    red under: drop one name from a twin entry's `reads` clause, or add an
    entry the `.cardlang` lacks — both check clean everywhere else. A twin
    whose fence BODY calls a name its block drops is refused upstream by
    `test_md_twin_checks` (that cell's Owner)."""
    assert _block_facts(check_source(GAMES / f"{md.stem}.cardlang")) == _block_facts(
        check_source(md)
    )
