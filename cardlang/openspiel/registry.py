"""The adapter's game registry — derived from the corpus directory, importable
without pyspiel.

`GAMES` maps each corpus game's OpenSpiel short name to its `docs/games/`
filename. It is DERIVED from the directory rather than hand-listed: the corpus
*is* whatever `.cardlang` files sit in `docs/games/` (CLAUDE.md), and the short
name is mechanical — `cardlang_` + the file stem with `-` turned to `_`
(`go-fish.cardlang` -> `cardlang_go_fish`). A new game needs only its file;
there is no second list to keep in sync, and no numeric count for two branches
to bump into the same silent merge (the failure mode the old hand-listed pin
existed to catch).

`game.py` registers each entry as a `pyspiel.Game` on import, which needs the
optional `openspiel` extra; the registry itself is consumed by pyspiel-free
callers too (the corpus pins in `tests/test_typecheck_corpus.py`), so it lives
here where importing it cannot fail on a core install. The derivation reads the
directory but imports nothing third-party, so that property still holds.
"""

from __future__ import annotations

from pathlib import Path

_GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"


def _short_name(filename: str) -> str:
    """The OpenSpiel short name for a corpus file: `cardlang_` + the stem with
    hyphens turned to underscores (`seven-card-stud.cardlang` ->
    `cardlang_seven_card_stud`)."""
    return "cardlang_" + Path(filename).stem.replace("-", "_")


# short_name -> game file, derived from docs/games/*.cardlang (sorted for a
# stable registration order). Every corpus game is fully kernel.
GAMES: dict[str, str] = {
    _short_name(p.name): p.name for p in sorted(_GAMES_DIR.glob("*.cardlang"))
}
