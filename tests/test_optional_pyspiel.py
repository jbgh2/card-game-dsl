"""The `openspiel` extra is genuinely optional — pinned.

pyproject.toml keeps `open_spiel` out of `[dev]`, and the adapter tests
`importorskip` it, but both CI and the usual dev install carry the extra, so
nothing ever RAN the core suite without pyspiel — a core-path import of it
was invisible to every gate (a review on the President PR caught exactly
that: the corpus pin briefly imported `cardlang.openspiel.game`, which
registers against pyspiel at module import time). This test is the missing
pin: a subprocess with pyspiel import-blocked must still run the whole
core path — the pipeline over a real game, and the corpus glob↔registry
check via the pure-data registry module.

A subprocess (not an in-process meta_path hack) because pyspiel may already
be imported by neighbouring adapter tests; blocking must start from a clean
interpreter to prove anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent

_SCRIPT = """
import sys

class _BlockPyspiel:
    def find_spec(self, name, path=None, target=None):
        if name == "pyspiel" or name.startswith("pyspiel."):
            raise ModuleNotFoundError(
                "pyspiel was imported on the core path; the openspiel extra "
                "must stay optional"
            )
        return None

sys.meta_path.insert(0, _BlockPyspiel())

from pathlib import Path

# The core pipeline end to end over a real corpus game.
from cardlang.pipeline import check_source
check_source(Path("docs/games/hearts.cardlang"))

# The corpus pin's own import path and logic must be pyspiel-free too (its
# glob <-> registry equality is OWNED by test_typecheck_corpus.py; it is
# re-run here only to prove the pin itself works without the extra — a
# failure below with matching sets means an import regression, not drift).
from cardlang.openspiel.registry import GAMES
corpus = sorted(p.name for p in Path("docs/games").glob("*.cardlang"))
assert corpus == sorted(GAMES.values()), (corpus, sorted(GAMES.values()))

assert "pyspiel" not in sys.modules
print("CORE-OK", len(GAMES))
"""


def test_core_path_runs_without_pyspiel() -> None:
    proc = subprocess.run(  # noqa: PLW1510 -- the returncode assert below carries proc.stderr; CalledProcessError would not
        [sys.executable, "-c", _SCRIPT],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("CORE-OK"), proc.stdout
