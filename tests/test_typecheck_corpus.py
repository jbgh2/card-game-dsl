"""Corpus regression net for the type checker.

Every executable game in the corpus must type-check clean. This is the guard
against false positives as the checker's precision grows: any new typing rule
that wrongly rejects a real game turns this red.

The corpus is the `.cardlang` files. Each `.md` beside one is its rulebook,
linking to the game rather than embedding the DSL (docs/maintaining.md,
"The rulebook twin"), so a rulebook has nothing for this gate to check. A twin
that does carry a fenced block is a second copy of a game and is held to the
same bar as the first, not exempted as "illustrative syntax": an exempted
block is where a retired spelling rots with nothing to say so, and
maintaining.md calls a game file using obsolete syntax a bug. Which twins
carry no block is pinned by name in
`test_the_prose_only_twins_are_the_pinned_set` rather than counted in this
sentence, so the set cannot change silently in either direction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.pipeline import check_source
from tests.empty_axis import may_be_empty

GAMES = Path(__file__).parent.parent / "docs" / "games"
CORPUS = sorted(GAMES.glob("*.cardlang"))

# The `.md` twins that carry a DSL block. A rulebook links to its `.cardlang`
# and has nothing to check; a fenced twin is a game file and is held to the
# same bar.
MD_TWINS = sorted(
    p for p in GAMES.glob("*.md") if p.stem != "_candidates" and "```" in p.read_text()
)

# The twins this gate does NOT cover, by name: every rulebook, since each links
# to its `.cardlang` rather than embedding it. Pinned rather than counted, so a
# new game's rulebook has to be added here deliberately, and a twin that gains
# a block has to be removed.
PROSE_ONLY_TWINS: frozenset[str] = frozenset(
    {
        "belote",
        "big-two",
        "breakthrough",
        "bridge",
        "canasta",
        "cheat",
        "coup",
        "cribbage",
        "doppelkopf",
        "five-hundred",
        "freecell",
        "french-tarot",
        "getaway",
        "gin-rummy",
        "go-fish",
        "gops",
        "hearts",
        "holdem",
        "holdem-heads-up",
        "klondike",
        "kuhn-poker",
        "leduc-poker",
        "oh-hell",
        "pinochle",
        "president",
        "schnapsen",
        "seven-card-stud",
        "skat",
        "spades",
        "tic-tac-toe",
        "tichu",
    }
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


@pytest.mark.parametrize(
    "path",
    may_be_empty(
        MD_TWINS,
        reason="every rulebook twin links to its `.cardlang` rather than embedding "
        "the DSL (docs/maintaining.md, 'The rulebook twin'), so no twin carries a "
        "block; the games themselves are checked by test_corpus_game_type_checks, "
        "and the linking set is pinned by name in PROSE_ONLY_TWINS",
    ),
    ids=[p.stem for p in MD_TWINS],
)
def test_md_twin_checks(path: Path) -> None:
    """A twin carrying a DSL block is a game file and is held to the same bar as
    the `.cardlang`: a block that no longer checks is a second copy of the game
    that has rotted, the failure mode maintaining.md calls a bug."""
    check_source(path)


def _block_facts(game: object) -> dict[str, object] | None:
    """A `primitives { }` block as comparable facts: per entry, the typed
    parameter list, the return spelling, and the reads (name, binder, scope
    tail). None for a legacy game, so regime drift between twins is itself a
    diff.

    The tail is part of a read, not decoration: a [[phase-scoped-read]] present
    in one twin and absent — or naming a different phase — in the other checks
    clean on both sides, so a tuple that dropped it would let exactly that
    drift through."""
    primitives = getattr(game, "primitives")
    if primitives is None:
        return None
    return {
        d.name: (
            tuple((p.name, p.type_name) for p in d.params),
            d.return_type,
            tuple(sorted((r.name, r.binder or "", r.phase or "") for r in d.reads)),
        )
        for d in primitives.decls
    }


_PAIRED_TWINS = sorted(p for p in MD_TWINS if (GAMES / f"{p.stem}.cardlang").exists())


def test_every_fenced_twin_is_paired() -> None:
    """The pairing glob's own control: a fenced twin with no `.cardlang` would
    silently leave the block-agreement pin's domain."""
    assert [p.stem for p in MD_TWINS if p not in _PAIRED_TWINS] == []


@pytest.mark.parametrize(
    "md",
    may_be_empty(
        _PAIRED_TWINS,
        reason="every rulebook twin links to its `.cardlang` rather than embedding "
        "the DSL (docs/maintaining.md, 'The rulebook twin'), so no twin carries a "
        "block to hold against its `.cardlang`; the linking set is pinned by name "
        "in PROSE_ONLY_TWINS",
    ),
    ids=[p.stem for p in _PAIRED_TWINS],
)
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
