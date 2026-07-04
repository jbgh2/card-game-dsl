"""Random-playout smoke harness for stress-test games.

Usage:  python stress-test/run_playout.py <file.cardlang> [n_seeds]

Checks the file, then plays n_seeds (default 20) random games end to end.
Each seed gets a 60-second alarm so a non-terminating game reports TIMEOUT
instead of hanging. Exit 0 iff every seed completes.

This harness lives outside CI on purpose: stress-test/ is an experiment
directory, not part of the canonical corpus.
"""

from __future__ import annotations

import random
import signal
import sys
import traceback
from types import FrameType

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game


def _alarm(signum: int, frame: FrameType | None) -> None:
    raise TimeoutError("playout exceeded 60s — game may not terminate")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = sys.argv[1]
    n_seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    game = check_source(path)
    signal.signal(signal.SIGALRM, _alarm)

    for seed in range(n_seeds):
        signal.alarm(60)
        try:
            result = play_game(game, random.Random(seed))
        except Exception as exc:
            signal.alarm(0)
            print(f"seed {seed}: FAILED: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            return 1
        signal.alarm(0)
        if seed == 0:
            print(
                f"seed 0: hands_played={result.hands_played} "
                f"winner={result.winner} loser={result.loser} "
                f"scores={result.scores}"
            )
    print(f"OK: {n_seeds}/{n_seeds} random playouts completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
