"""The adapter's game registry — derived from the corpus directory, importable
without pyspiel.

`GAMES` maps each corpus game's OpenSpiel short name to its `docs/games/`
filename. It is DERIVED from the directory rather than hand-listed: the corpus
*is* whatever `.cardlang` files sit in `docs/games/` (CLAUDE.md), and the short
name is mechanical — `cardlang_` + the file stem with `-` turned to `_`
(`go-fish.cardlang` -> `cardlang_go_fish`). A new game needs only its file;
there is no second list to keep in sync, and no numeric count for two branches
to bump into the same silent merge.

Because the map is derived from the directory, the derivation refuses to
produce a silently-broken registry: `_derive_games` raises if the directory
yields no games (the packaging failure — see below) or a short-name collision,
so either is caught at adapter import rather than surfacing as a game that
mysteriously will not load.

`game.py` registers each entry as a `pyspiel.Game` on import, which needs the
optional `openspiel` extra; the registry itself is consumed by pyspiel-free
callers too (the corpus pins in `tests/test_typecheck_corpus.py`), so it lives
here where importing it cannot fail on a core install. The derivation reads the
directory but imports nothing third-party, so that property still holds — in a
checkout, where `docs/games/` is present. A packaged (wheel) install ships only
`cardlang*` + grammar/stdlib data, not `docs/games/`, so the corpus is absent
and the registry cannot be built; that is the standing corpus-packaging
residual (issue #97), and the empty-directory raise
below turns it from a silent no-op into a loud, self-explaining error.
"""

from __future__ import annotations

from pathlib import Path

_GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"


def _short_name(filename: str) -> str:
    """The OpenSpiel short name for a corpus file: `cardlang_` + the stem with
    hyphens turned to underscores (`seven-card-stud.cardlang` ->
    `cardlang_seven_card_stud`)."""
    return "cardlang_" + Path(filename).stem.replace("-", "_")


def _derive_games(games_dir: Path) -> dict[str, str]:
    """Map each `<games_dir>/*.cardlang` to its OpenSpiel short name, sorted for
    a stable registration order. Raises rather than returning a silently-broken
    registry:

    - a short-name COLLISION (two files whose stems differ only by `-` vs `_`)
      would drop a game from the map — a `dict` keeps the last silently.
    - an EMPTY result means the corpus directory is missing or unpopulated. In
      a checkout the path is wrong; in a packaged install `docs/games/` was not
      shipped (issue #97).
      Registering zero games silently is the failure this check exists to catch
      quickly, at adapter import.
    """
    games: dict[str, str] = {}
    for p in sorted(games_dir.glob("*.cardlang")):
        name = _short_name(p.name)
        if name in games:
            raise RuntimeError(
                f"two corpus files derive the same OpenSpiel short name "
                f"{name!r}: {games[name]!r} and {p.name!r} (their stems differ "
                f"only by '-' vs '_') — rename one."
            )
        games[name] = p.name
    if not games:
        raise RuntimeError(
            f"no .cardlang games found under {games_dir} — the OpenSpiel "
            f"registry derives from that directory and would otherwise register "
            f"nothing. In a checkout the path is wrong; in a packaged install "
            f"docs/games/ was not shipped (docs/roadmap.md, 'Packaging the "
            f"corpus for distribution')."
        )
    return games


# short_name -> game file. Every corpus game is fully kernel.
GAMES: dict[str, str] = _derive_games(_GAMES_DIR)
