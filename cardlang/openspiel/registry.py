"""The adapter's game registry — derived from the corpus directory, importable
without pyspiel.

`GAMES` maps each corpus [[game]]'s OpenSpiel short name to its `docs/games/`
filename. It is DERIVED from the directory rather than hand-listed: the corpus
*is* whatever `.cardlang` files sit in `docs/games/` (CLAUDE.md), and the short
name is mechanical — `cardlang_` + the file stem with `-` turned to `_`
(`go-fish.cardlang` -> `cardlang_go_fish`). A new game needs only its file;
there is no second list to keep in sync, and no numeric count for two branches
to bump into the same silent merge.

Because the map is derived from the directory, the derivation refuses to
produce a silently-broken registry: `_derive_games` raises if the directory
yields no games (the packaging failure — see below), an unrenderable stem, or
a short-name collision, so each is caught at adapter import rather than
surfacing as a game that mysteriously will not load.

The corpus is one of the sources `game.py` registers, not the only one — a
path offered by a caller or by `CARDLANG_GAMES` reaches the same registration
function, sharing this module's naming rule and its character set. `GAMES`
stays the corpus alone, so the tables keyed on it stay corpus-shaped.

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

import re
from pathlib import Path

from cardlang.runtime.errors import InstallationError

_GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"

# What a stem may contain, hyphens already folded, for `_short_name` to render
# a name `pyspiel.load_game` can reach. OpenSpiel parses a game string as
# `name(param=value,...)`, so a bracket in the name silently truncates it
# there: registering `cardlang_a(b)` succeeds and loading it reports an unknown
# game `cardlang_a`, which nobody wrote. This set is a SUBSET of what OpenSpiel
# would accept — a space and a comma load — and deliberately so: the refusal
# has to precede `pyspiel.register_game`, which has no inverse, so it is a
# static rule about the name rather than an answer read back from a
# registration already made.
SHORT_NAME_CHARS = re.compile(r"[A-Za-z0-9_]+")


def _short_name(filename: str) -> str:
    """The OpenSpiel short name for a game file: `cardlang_` + the stem with
    hyphens turned to underscores (`seven-card-stud.cardlang` ->
    `cardlang_seven_card_stud`).

    The naming rule and nothing else. Whether a given stem can be rendered is
    `SHORT_NAME_CHARS`, applied by each caller in that caller's own failure
    channel: a corpus file that cannot be named is this checkout's problem, a
    path offered to `register_game_file` is its caller's, and one rule with two
    Authors would have to pick.
    """
    return "cardlang_" + Path(filename).stem.replace("-", "_")


def _derive_games(games_dir: Path) -> dict[str, str]:
    """Map each `<games_dir>/*.cardlang` to its OpenSpiel short name, sorted for
    a stable registration order. Raises rather than returning a silently-broken
    registry:

    - a stem outside `SHORT_NAME_CHARS` renders a short name pyspiel registers
      and cannot load, so the game would sit in the map unreachable.
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
        if not SHORT_NAME_CHARS.fullmatch(name):
            raise InstallationError(
                f"{p.name!r} derives the OpenSpiel short name {name!r}, which "
                f"pyspiel cannot load — a stem may hold only letters, digits, "
                f"hyphens and underscores. Rename the file."
            )
        if name in games:
            raise InstallationError(
                f"two corpus files derive the same OpenSpiel short name "
                f"{name!r}: {games[name]!r} and {p.name!r} (their stems differ "
                f"only by '-' vs '_') — rename one."
            )
        games[name] = p.name
    if not games:
        raise InstallationError(
            f"no .cardlang games found under {games_dir} — the OpenSpiel "
            f"registry derives from that directory and would otherwise register "
            f"nothing. In a checkout the path is wrong; in a packaged install "
            f"docs/games/ was not shipped — see issue #97."
        )
    return games


# short_name -> game file. Every corpus game is fully kernel.
GAMES: dict[str, str] = _derive_games(_GAMES_DIR)
