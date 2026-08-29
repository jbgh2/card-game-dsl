"""Behaviour-preserving net for the Step-0 trick migration.

Hearts, Spades, and Getaway move their play from the built-in `Trick` mechanic
to the kernel `round` construct. Like the Oh Hell precedent, the migration only
changes *how the trick loop is expressed*, not which card is chosen when: it
moves no chooser calls, so for a fixed playout the per-seed results must stay
**byte-identical**. These goldens are pinned from the pre-migration runtime; a
diff after migrating means the trick behaviour changed (a routing, follow-rule,
or early-termination regression), not a redesign.

(Bridge's play trick also migrates in Step 0; it is already pinned by
`golden/bridge_scores.json` via test_migration_characterization.py.)

A playout does not depend on `PYTHONHASHSEED`
(test_migration_characterization.py's
`test_a_playout_is_hash_seed_independent`), so these goldens reproduce under
whatever hash seed a run draws. The capture runs in a subprocess for
interpreter isolation, not to pin the environment.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).parent.parent
GOLDEN = Path(__file__).parent / "golden"

# The games this module captures. A constant rather than a literal in the
# parametrize below because the hash-seed pin
# (test_migration_characterization.py) derives part of its own axis from it:
# these captures pin no environment, so every game named here is one that pin
# has to cover, and a game added here has to widen it without being copied there.
TRICK_GAMES: tuple[str, ...] = ("hearts", "spades", "getaway")

_CAPTURE = """
import json, random, sys
from pathlib import Path
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

name = sys.argv[1]
game = check_dsl(Path(f"docs/games/{name}.cardlang").read_text(), f"{name}.cardlang")
out = {}
for seed in range(50):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(k): v for k, v in sorted(r.scores.items())},
        "winner": r.winner,
        "loser": r.loser,
        "hands_played": r.hands_played,
    }
print(json.dumps(out))
"""


def _capture_results(name: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE, name],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


@pytest.mark.parametrize("name", TRICK_GAMES)
def test_trick_migration_preserves_per_seed_results(name: str) -> None:
    expected = json.loads((GOLDEN / f"{name}_trick_scores.json").read_text())
    assert _capture_results(name) == expected
